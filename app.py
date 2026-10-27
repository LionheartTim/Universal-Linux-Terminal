#!/usr/bin/env python3
import os
import signal
import subprocess
import threading
import uuid
import shlex
from pathlib import Path
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Vte', '2.91')
from gi.repository import Gtk, Gdk, GLib, Vte, Pango
try:
    # Modern namespace for GLib Unix signal handlers.  The old
    # GLib.unix_signal_add alias warns on Fedora's current PyGObject.
    gi.require_version('GLibUnix', '2.0')
    from gi.repository import GLibUnix
except (ImportError, ValueError):
    GLibUnix = None  # compatibility for older distributions
from core import (Command, catalog, availability, bundle, build, user_shell,
                  flatpak_action, parse_apps, parameter_command, manifest_info, terminal_line, native_command)
from terminal import TerminalTab
from window_geometry import fit_dimensions
from i18n import tr as L
from context_composer import SelectedApp, parse_flatpak_search, app_preview, combine_app_storage
from guided_workflows import scan_volumes
from composition_engine import Subject, default_engine, register_native_rules
from distro_support import detect_profile
from command_discovery import Executable, installed_commands, prepare_command, search_installed_commands
from option_discovery import load_command_info, format_command_help
from host_bridge import in_flatpak, run_host, host_shell_argv, HOST_ACCOUNT_SHELL
from app_icon import configure_application_identity, apply_window_icon

VERSION = '1.0.1'


class CommandDescriptionView(Gtk.TextView):
    """Read-only, selectable help text that wraps to the sidebar viewport.

    Gtk.Label inside a Gtk.Viewport can request the width of a long line and
    visually clip it even when horizontal scrolling is disabled. TextView is
    Gtk.Scrollable and wraps against the actual allocated viewport width.
    Keep a set_text() method so the existing command-info callbacks, tests and
    translations continue to use their established interface.
    """

    def __init__(self, text):
        super().__init__(editable=False, cursor_visible=False,
                         wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.set_left_margin(2)
        self.set_right_margin(8)
        self.set_top_margin(2)
        self.set_bottom_margin(2)
        self.set_text(text)

    def set_text(self, text):
        self.get_buffer().set_text(text)


class Window(Gtk.Window):
    def __init__(self):
        super().__init__(title='Universal Linux Terminal — '+VERSION)
        apply_window_icon(self)
        # Width/height are determined per monitor in _refresh_workarea().
        # GTK uses logical pixels here, so HiDPI scaling is handled by GDK.
        self.set_default_size(960, 720)
        self._workarea_fingerprint = None
        self._moved_on_startup = False
        self.destroyed = False
        self.connect('destroy', lambda *_: setattr(self, 'destroyed', True))
        self.running = 0
        self.guided_running = 0
        self.workdir = str(Path.home())
        self.history = []
        self.last_manifest = {}
        self.command = None
        self.selected_app = None  # pending until inserted or cleared
        self.composer = default_engine()  # typed composition draft, no command execution
        self.distro = detect_profile()
        register_native_rules(self.composer, self.distro)
        self.connect('delete-event', self.closing)
        settings = Gtk.Settings.get_default()
        settings.set_property('gtk-application-prefer-dark-theme', True)
        # No app heading, subtitle or changing status line above the console.
        # The status label remains internal for legacy action feedback callers.
        self.status = Gtk.Label(label='')
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_border_width(8)
        self.add(outer)
        split = Gtk.Paned()
        self.split = split
        outer.pack_start(split, True, True, 0)
        # Persistent, compact footer across both panes. Keep it outside the
        # split so it stays at the very bottom, independent of sidebar scroll.
        footer_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        footer_area.set_margin_top(5)
        footer_area.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
                               False, False, 0)
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        footer.pack_start(Gtk.Label(label=L('Version') + ' ' + VERSION),
                          False, False, 0)
        # GTK3 hyperlinks inside labels are accessible, clickable, and do not
        # take the height of a full button. Only the author name is linked.
        credit = Gtk.Label(xalign=1)
        credit.set_markup(L('Made by') + ' '
                          '<a href="https://github.com/LionheartTim">LionheartTim</a>')
        credit.set_tooltip_text('https://github.com/LionheartTim')
        footer.pack_end(credit, False, False, 0)
        footer_area.pack_start(footer, False, False, 0)
        outer.pack_end(footer_area, False, False, 0)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.sidebar = left
        left.set_size_request(260, -1)
        split.pack1(left, False, False)
        search = Gtk.SearchEntry(placeholder_text=L('Zoek functies of commando’s…'))
        left.pack_start(search, False, False, 0)
        distro_text = L('Detected system: ') + self.distro.name + '  ·  ' + self.distro.backend_label
        if self.distro.atomic:
            distro_text += '  ·  ' + L('atomic system')
        if self.distro.sandbox:
            distro_text += '  ·  ' + L('container/sandbox')
        distro_label = Gtk.Label(label=distro_text, xalign=0, wrap=True)
        distro_label.set_selectable(True)
        left.pack_start(distro_label, False, False, 0)
        self.tree_store = Gtk.TreeStore(str, object)
        groups = {}
        for group, cmd in catalog():
            if group not in groups:
                groups[group] = self.tree_store.append(None, [L(group), None])
            self.tree_store.append(groups[group], [L(cmd.title), cmd])
        for group, title, action in [('Flatpak','App verwijderen…','remove'), ('Flatpak','Lokale bundle installeren…','install'), ('Bouwen','Project bouwen…','build'), ('Bouwen','Bundle exporteren…','bundle'), ('Terminal','Werkmap kiezen…','cwd'), ('Terminal','Opdrachtgeschiedenis…','history'), ('Flatpak','Apps zoeken…','search'), ('Flatpak','App-ID installeren…','remote_install'), ('Flatpak','App-informatie…','info'), ('Systeem','HDD/SSD-map kiezen…','disk_picker'), ('Flatpak','App bijwerken…','app_update'), ('Bestanden','Choose folder actions…','folder_actions'), ('Netwerk','Choose network interface…','interface_actions'), ('Containers','Choose Podman container…','podman_actions'), ('Flatpak','App-rechten bekijken…','permissions'), ('Netwerk','Verbinding testen…','ping'), ('Diagnose','Service bekijken…','service'), ('Diagnose','Servicelogboek…','logs'), ('Bestanden','SHA256 berekenen…','hash'), ('Containers','Container openen…','container')]:
            if group not in groups:
                groups[group] = self.tree_store.append(None, [L(group),None])
            self.tree_store.append(groups[group], [L(title), action])
        # Native package tools are offered only when the OS family and the
        # actual installed backend agree. Never treat Bazzite as mutable Fedora.
        if self.distro.backend not in ('none', 'rpm-ostree'):
            native_actions = [
                ('Search native packages…', 'native_search'),
                ('Native package information…', 'native_info'),
            ]
            if not self.distro.atomic and not self.distro.sandbox and self.distro.has('sudo'):
                native_actions.extend([
                    ('Prepare native package installation…', 'native_install'),
                    ('Prepare native package removal…', 'native_remove'),
                ])
            if 'Native packages' not in groups:
                groups['Native packages'] = self.tree_store.append(None, [L('Native packages'), None])
            for label, action in native_actions:
                self.tree_store.append(groups['Native packages'], [L(label), action])
        # The installed-command index is a separate category. Extra is last.
        # No standalone Mix & Match category: the existing preview composes
        # supported multi-click actions contextually.
        for group, title, action in [
            ('All installed commands', 'Browse installed commands…', 'all_commands'),
            ('Extra', 'Steam → Mount → Disk → Folder…', 'steam_storage')]:
            if group not in groups:
                groups[group] = self.tree_store.append(None, [L(group), None])
            self.tree_store.append(groups[group], [L(title), action])
        # The same top search indexes built-in actions AND programs discovered
        # from PATH. Search results are temporary children of the existing
        # All installed commands category (never a separate Mix & Match group).
        self.query = ''
        self._installed_inventory = None
        self._installed_error = None
        self._installed_scan_running = False
        self._installed_hits = []
        self._installed_group = groups['All installed commands']
        self._selected_executable = None
        self._command_help_cache = {}  # only inspected commands, never PATH-wide scanning
        self._command_info_generation = 0
        filtered = self.tree_store.filter_new()
        filtered.set_visible_func(self.visible)
        tree = Gtk.TreeView(model=filtered, headers_visible=False)
        tree.append_column(Gtk.TreeViewColumn(L('Functie'), Gtk.CellRendererText(), text=0))
        tree.get_selection().connect('changed', self.selected)
        tree.expand_all()
        self._sidebar_filter = filtered
        self._sidebar_tree = tree
        def searching(entry):
            self.query = entry.get_text().casefold().strip()
            self._refresh_installed_search()
        search.connect('search-changed', searching)
        scroll = Gtk.ScrolledWindow()
        scroll.add(tree)
        left.pack_start(scroll, True, True, 0)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_start=16)
        split.pack2(right, True, False)
        self.heading = Gtk.Label(label=L('Kies een functie'), xalign=0)
        self.heading.set_markup('<b>'+L('Kies links een functie')+'</b>')
        left.pack_start(self.heading, False, False, 0)
        self.description = CommandDescriptionView(
            L('Typ rechts zoals in elke terminal. Kies links een taak om een commando samen te stellen. Zet het in de terminal en druk zelf op Enter.'))
        # The entire documented description stays selectable and scrollable,
        # including multi-line help and long unbroken strings. No horizontal
        # clipping and no extra manual line breaks at a fixed character count.
        self.info_scroll = Gtk.ScrolledWindow()
        self.info_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.info_scroll.set_size_request(-1, 118)
        self.info_scroll.add(self.description)
        left.pack_start(self.info_scroll, False, False, 0)
        self.context_label = Gtk.Label(label='', xalign=0, wrap=True)
        left.pack_start(self.context_label, False, False, 0)
        self.clear_button = Gtk.Button(label=L('Start a new command'))
        self.clear_button.connect('clicked', self.clear_composition)
        left.pack_start(self.clear_button, False, False, 0)
        self.clear_button.set_no_show_all(True)
        self.clear_button.hide()
        self.preview = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        preview_scroll = Gtk.ScrolledWindow(min_content_height=72)
        preview_scroll.add(self.preview)
        left.pack_start(preview_scroll, False, False, 0)
        self.options_button = Gtk.Button(label=L('Choose command options…'))
        self.options_button.connect('clicked', self.choose_command_options)
        left.pack_start(self.options_button, False, False, 0)
        self.options_button.set_no_show_all(True)
        self.options_button.hide()
        bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.run_button = Gtk.Button(label=L('In terminal zetten'))
        self.run_button.set_sensitive(False)
        self.run_button.connect('clicked', self.run)
        bar.pack_start(self.run_button, False, False, 0)
        left.pack_start(bar, False, False, 0)
        self.tabs = Gtk.Notebook(show_tabs=False, show_border=False)
        right.pack_start(self.tabs, True, True, 0)
        self.show_all()
        self.clear_button.hide()
        self.options_button.hide()
        # Read workarea after mapping, and watch for resolution, scaling and
        # monitor changes. Polling is a fallback for backends that do not emit
        # one of these signals (notably some Wayland compositor combinations).
        self._refresh_workarea()
        display = Gdk.Display.get_default()
        if display:
            display.connect('monitor-added', self._monitors_changed)
            display.connect('monitor-removed', self._monitors_changed)
            self._subscribe_monitor_properties(display)
        screen = self.get_screen()
        if screen is not None:
            screen.connect('monitors-changed', self._monitors_changed)
            screen.connect('size-changed', self._monitors_changed)
        self._monitor_timer = GLib.timeout_add_seconds(3, self._refresh_workarea)
        # Launch the real host shell directly. A separate --host /bin/true
        # preflight was prone to false negatives during cold D-Bus startup,
        # even when Flatpak actually permitted host commands. The real
        # flatpak-spawn --host process enforces permissions and reports errors
        # in the terminal; we NEVER fall back to a sandbox shell.
        self.shell()

    def _subscribe_monitor_properties(self, display):
        if not hasattr(self, '_tracked_monitors'):
            self._tracked_monitors = set()
        for n in range(display.get_n_monitors()):
            monitor = display.get_monitor(n)
            if monitor is None or monitor in self._tracked_monitors:
                continue
            self._tracked_monitors.add(monitor)
            for name in ('geometry', 'workarea', 'scale-factor'):
                monitor.connect('notify::'+name, self._monitors_changed)

    def _monitors_changed(self, *_):
        if not self.destroyed:
            display = Gdk.Display.get_default()
            if display:
                self._subscribe_monitor_properties(display)
            # An idle callback must return False after one update; the
            # periodic timer uses the regular True-returning method.
            GLib.idle_add(self._refresh_workarea_once)

    def _refresh_workarea_once(self):
        self._refresh_workarea()
        return False

    def _get_monitor_area(self):
        display = Gdk.Display.get_default()
        if display and display.get_n_monitors() > 0:
            monitor = None
            gdk_window = self.get_window()
            if gdk_window:
                monitor = display.get_monitor_at_window(gdk_window)
            if monitor is None:
                monitor = display.get_primary_monitor() or display.get_monitor(0)
            if monitor is not None:
                area = monitor.get_workarea()
                if area.width < 1 or area.height < 1:
                    area = monitor.get_geometry()
                return (monitor, area)
        return None, None

    def _refresh_workarea(self, *_):
        if self.destroyed:
            return False
        monitor, area = self._get_monitor_area()
        if area is None:
            return True
        stamp = (id(monitor), area.x, area.y, area.width, area.height,
                 monitor.get_scale_factor())
        if stamp == self._workarea_fingerprint:
            return True
        width, height, sidebar_width = fit_dimensions(area.width, area.height)
        self._workarea_fingerprint = stamp
        self.sidebar.set_size_request(sidebar_width, -1)
        self.split.set_position(sidebar_width)
        self.set_default_size(width, height)
        self.resize(width, height)
        if not self._moved_on_startup:
            # Wayland compositors may ignore explicit window placement; GTK
            # still supplies the correct size for the active display.
            self.move(area.x, area.y)
            self._moved_on_startup = True
        return True

    def _refresh_installed_search(self):
        """Refresh the sidebar using a cached system command index.

        Scanning PATH happens on a worker only when a search is first used.
        All Gtk.TreeStore modifications happen on the GTK main thread.
        """
        if self._installed_hits:
            self._sidebar_tree.get_selection().unselect_all()
            for it in self._installed_hits:
                self.tree_store.remove(it)
            self._installed_hits.clear()
        if self.query and self._installed_inventory is None:
            if not self._installed_scan_running:
                self._installed_scan_running = True
                def worker():
                    try:
                        inventory, error = installed_commands(), None
                    except (OSError, ValueError, RuntimeError) as exc:
                        inventory, error = [], str(exc)
                    GLib.idle_add(self._installed_index_ready, inventory, error)
                threading.Thread(target=worker, daemon=True).start()
        elif self.query:
            for program in search_installed_commands(self._installed_inventory, self.query):
                row = self.tree_store.append(self._installed_group, [program.name, program])
                self._installed_hits.append(row)
        self._sidebar_filter.refilter()
        self._sidebar_tree.expand_all()

    def _installed_index_ready(self, inventory, error=None):
        if self.destroyed:
            return False
        self._installed_inventory = inventory
        self._installed_error = error
        self._installed_scan_running = False
        if error:
            self.heading.set_text(L('All installed commands'))
            self.description.set_text('Host command discovery failed: ' + error[:400])
        self._refresh_installed_search()
        return False

    def choose_command_options(self, *_):
        if self._selected_executable is None:
            return
        from studio_ui import open_installed_commands
        open_installed_commands(self, initial_command=self._selected_executable.name,
                                inventory=self._installed_inventory)

    def visible(self, model, it, *_):
        if not self.query or self.query in model[it][0].casefold():
            return True
        parent = model.iter_parent(it)
        if parent and self.query in model[parent][0].casefold():
            return True
        child = model.iter_children(it)
        while child:
            if self.query in model[child][0].casefold():
                return True
            child = model.iter_next(child)
        return False

    def selected(self, selection):
        model, it = selection.get_selected()
        if it is None:
            return
        value = model[it][1]
        if isinstance(value, Executable):
            self.stage(prepare_command(value.name, inventory=self._installed_inventory))
            self.show_command_info(value)
        elif isinstance(value, Command):
            if self.selected_app and value.argv[:2] == ['lsblk', '-f']:
                self.choose_app_storage()
            else:
                self.stage(value)
        elif value:
            {'remove': self.remove, 'bundle': self.bundle_form, 'build': self.build_form,
             'install': self.install, 'shell': self.shell, 'cwd': self.choose_workdir,
             'history': self.show_history, 'search': self.search_apps,
             'remote_install': lambda: self.parameter('install'), 'ping': lambda: self.parameter('ping'),
             'service': lambda: self.parameter('service'), 'logs': lambda: self.parameter('logs'),
             'hash': lambda: self.parameter('hash'), 'container': lambda: self.parameter('container'),
             'info': lambda: self.remove('info'), 'app_update': lambda: self.remove('update'),
             'permissions': lambda: self.remove('permissions'),
             'steam_storage': self.steam_storage, 'disk_picker': self.choose_app_storage,
             'all_commands': self.all_commands, 'folder_actions': self.choose_folder_actions,
             'interface_actions': self.choose_interface_actions, 'podman_actions': self.choose_podman_actions,
             'native_search': lambda: self.native_action('search'),
             'native_info': lambda: self.native_action('info'),
             'native_install': lambda: self.native_action('install'),
             'native_remove': lambda: self.native_action('remove')}[value]()

    def native_action(self, action):
        """Prepare, never run, a command for the detected native manager."""
        if action not in ('search', 'info', 'install', 'remove'):
            return
        if action in ('install', 'remove') and (self.distro.atomic or self.distro.sandbox):
            self.message(L('Host package changes are unavailable in this environment.'))
            return
        result = self.fields(L('Native package name'), [(L('Package name'), '')])
        if not result:
            return
        try:
            command = native_command(action, result[0], self.distro)
        except ValueError as error:
            self.message(L(str(error)))
            return
        if action == 'remove' and not self.confirm(L('This may remove dependencies or system components. Review every change in the terminal. Prepare a removal command?')):
            return
        self.stage(command)
        # Keep this package as a typed draft so subsequent suggestions reuse it.
        self.remember_subject('package', result[0])

    def steam_storage(self):
        from studio_ui import open_steam_storage
        open_steam_storage(self)

    def all_commands(self):
        if self._installed_error:
            self.message('Host command discovery failed: ' + self._installed_error[:400])
            return
        from studio_ui import open_installed_commands
        open_installed_commands(self, inventory=self._installed_inventory)

    def stage(self, command, keep_app=False, keep_context=False):
        self._command_info_generation += 1
        self._selected_executable = None
        self.options_button.hide()
        if not keep_app:
            self.selected_app = None
            self.update_app_context()
        # App drafts remain composable while the app is pending; otherwise a
        # second disk selection would lose the app and become invalid.
        if not (keep_context or keep_app):
            self.composer.clear()
        self.command = command
        self.heading.set_text(L(command.title))
        issue = availability(command)
        # A Flatpak host-metadata failure does not prove that the tool is
        # missing. Permit review/insertion into a healthy host Bash session;
        # the shell itself determines whether the command can run.
        if in_flatpak() and issue.startswith('Ontbrekend hulpmiddel: '):
            issue = ''
        self.description.set_text(L(command.explanation) + '\n' + L('Invoegen op een lege opdrachtregel; daarna zelf Enter drukken.') + ('\n'+L(issue) if issue else ''))
        self.preview.get_buffer().set_text(command.preview)
        self.run_button.set_sensitive(not issue)

    @staticmethod
    def _help_key(target):
        return (target.name, target.kind, target.location)

    def get_cached_command_info(self, target):
        return self._command_help_cache.get(self._help_key(target))

    def cache_command_info(self, target, details):
        if len(self._command_help_cache) >= 100:
            self._command_help_cache.pop(next(iter(self._command_help_cache)))
        self._command_help_cache[self._help_key(target)] = details

    def show_command_info(self, target, selected=()):
        """Populate the exact sidebar information area from the program help.

        Never run arbitrary commands on search or while browsing the inventory.
        Run bounded --help only when a command was explicitly selected, off
        the UI thread. Stale responses cannot overwrite a newer selection.
        """
        self._command_info_generation += 1
        generation = self._command_info_generation
        self._selected_executable = target
        self.options_button.show()
        self.heading.set_text(target.name)
        self.description.set_text(L('Reading command information…'))
        self.info_scroll.get_vadjustment().set_value(0)
        selections = tuple(selected)
        key = self._help_key(target)
        cached = self.get_cached_command_info(target)
        if cached is not None:
            self.description.set_text(format_command_help(target.name, cached, selections, L))
            return

        def worker():
            try:
                details, error = load_command_info(target), None
            except (ValueError, OSError, RuntimeError) as exc:
                details, error = None, str(exc)
            def done():
                if self.destroyed or generation != self._command_info_generation:
                    return False
                if self._selected_executable != target:
                    return False
                if details is not None:
                    self.cache_command_info(target, details)
                    text = format_command_help(target.name, details, selections, L)
                else:
                    text = (L('Command help is unavailable:') + ' ' + L(error) + '\n' +
                            L('You can still enter options manually.'))
                self.description.set_text(text)
                self.info_scroll.get_vadjustment().set_value(0)
                return False
            GLib.idle_add(done)
        threading.Thread(target=worker, daemon=True).start()

    def update_app_context(self):
        if self.selected_app:
            self.context_label.set_text(L('Selected app: ') + self.selected_app.display_name +
                '\n' + (L('Next: choose Disks & partitions to select an HDD/SSD folder.')
                        if self.selected_app.installed else
                        L('Install this app first, then you can choose an HDD/SSD folder.')))
            self.clear_button.show()
        else:
            self.context_label.set_text('')
            self.clear_button.hide()

    def clear_composition(self, *_):
        self._command_info_generation += 1
        self._selected_executable = None
        self.options_button.hide()
        self.selected_app = None
        self.command = None
        self.composer.clear()
        self.update_app_context()
        self.heading.set_text(L('Select a function on the left'))
        self.description.set_text(L('Choose a function to prepare a command.'))
        self.preview.get_buffer().set_text('')
        self.run_button.set_sensitive(False)

    def picked_app(self, app, preview=None):
        self.selected_app = app
        self.update_app_context()
        self.stage(preview or app_preview(app), keep_app=True)
        self.composer.choose(Subject('app', app))
        # Suggest only a relevant next step, not an unrequested shell action.
        GLib.idle_add(self.show_app_suggestion, app)

    def show_app_suggestion(self, app):
        """Offer typed recipe choices; keep the existing disk-picker shortcut."""
        if self.destroyed or self.selected_app != app:
            return False
        dialog = Gtk.Dialog(title=L('Suggested next actions'), transient_for=self, modal=True)
        dialog.add_buttons(L('Not now'), Gtk.ResponseType.CANCEL,
                           L('Prepare suggestion'), Gtk.ResponseType.OK)
        area = dialog.get_content_area()
        area.set_spacing(8)
        area.set_border_width(12)
        area.pack_start(Gtk.Label(label=L('Selected app: ') + app.display_name,
                                  xalign=0), False, False, 0)
        area.pack_start(Gtk.Label(label=L('Choose what you want to do next; nothing runs automatically.'),
                                  xalign=0, wrap=True), False, False, 0)
        choices = Gtk.ComboBoxText()
        keys = []
        if app.installed:
            choices.append_text(L('Choose HDD/SSD folder…'))
            keys.append('storage')
        for option in self.composer.suggestions(include_incomplete=False):
            if option.key.startswith('app.'):
                choices.append_text(L(option.title))
                keys.append(option.key)
        choices.set_active(0)
        area.pack_start(choices, False, False, 0)
        if app.app_id == 'com.valvesoftware.Steam':
            area.pack_start(Gtk.Label(label=L('Steam library default must still be set in Steam Settings > Storage.'),
                                      xalign=0, wrap=True), False, False, 0)
        dialog.show_all()
        answer = dialog.run()
        index = choices.get_active()
        dialog.destroy()
        if answer == Gtk.ResponseType.OK and self.selected_app == app and 0 <= index < len(keys):
            if keys[index] == 'storage':
                self.choose_app_storage()
            else:
                self.prepare_recipe(keys[index])
        return False

    def prepare_recipe(self, key):
        """Stage a checked command; executing still requires Insert and Enter."""
        try:
            cmd, note = self.composer.compose(key)
        except (ValueError, OSError) as exc:
            self.message(L(str(exc)))
            return
        self.stage(cmd, keep_app=self.selected_app is not None, keep_context=True)
        if note:
            self.description.set_text(L(cmd.explanation) + '\n' + L(note) +
                                      '\n' + L('Review the command before inserting it.'))

    def show_rule_suggestions(self, kind, subject):
        """Popup with relevant alternatives from the registry, not text matches."""
        if self.destroyed or self.composer.selected.get(kind) != subject:
            return False
        options = [item for item in self.composer.suggestions(include_incomplete=False)
                   if kind in self.composer.rules[item.key].required]
        if len(options) < 2:
            return False
        dialog = Gtk.Dialog(title=L('Suggested next actions'), transient_for=self, modal=True)
        dialog.add_buttons(L('Not now'), Gtk.ResponseType.CANCEL,
                           L('Prepare suggestion'), Gtk.ResponseType.OK)
        area = dialog.get_content_area()
        area.set_spacing(8)
        area.set_border_width(12)
        area.pack_start(Gtk.Label(label=L('Choose what you want to do next; nothing runs automatically.'),
                                  xalign=0, wrap=True), False, False, 0)
        choices = Gtk.ComboBoxText()
        for item in options:
            choices.append_text(L(item.title))
        choices.set_active(0)
        area.pack_start(choices, False, False, 0)
        dialog.show_all()
        response = dialog.run()
        index = choices.get_active()
        dialog.destroy()
        if response == Gtk.ResponseType.OK and 0 <= index < len(options):
            if self.composer.selected.get(kind) == subject:
                self.prepare_recipe(options[index].key)
        return False

    def remember_subject(self, kind, value):
        """Remember a concrete object and offer compatible actions."""
        try:
            subject = self.composer.choose(Subject(kind, value))
        except (ValueError, OSError) as exc:
            self.message(L(str(exc)))
            return
        if subject.kind == 'volume':
            display_name = subject.value.path + (' — ' + subject.value.label if subject.value.label else '')
        else:
            display_name = subject.label or getattr(subject.value, 'display_name', str(subject.value))
        self.context_label.set_text(L('Selected: ') + display_name)
        GLib.idle_add(self.show_rule_suggestions, kind, subject)

    def _choose_item(self, title, values):
        """Simple selection UI for already-discovered, real system objects."""
        if not values:
            self.message(L('No suitable items found.'))
            return None
        dialog = Gtk.Dialog(title=L(title), transient_for=self, modal=True)
        dialog.add_buttons(L('Cancel'), Gtk.ResponseType.CANCEL,
                           L('Choose'), Gtk.ResponseType.OK)
        combo = Gtk.ComboBoxText()
        for label, _ in values:
            combo.append_text(label)
        combo.set_active(0)
        dialog.get_content_area().pack_start(combo, False, False, 12)
        dialog.show_all()
        result = values[combo.get_active()][1] if dialog.run() == Gtk.ResponseType.OK else None
        dialog.destroy()
        return result

    def choose_folder_actions(self):
        path = self.choose(L('Choose an existing folder'), folder=True)
        if path:
            try:
                subject = Subject('folder', path)
                self.composer.choose(subject)
                self.prepare_recipe('folder.list')
                self.remember_subject('folder', path)
            except (ValueError, OSError) as exc:
                self.message(str(exc))

    def choose_interface_actions(self):
        # Read-only discovery, don't guess the user's interface.
        try:
            interfaces = sorted(p.name for p in Path('/sys/class/net').iterdir())
        except OSError:
            interfaces = []
        selected = self._choose_item('Choose network interface', [(s,s) for s in interfaces])
        if selected:
            self.stage(Command('Network interfaces', ['ip','address','show','dev',selected],
                               'Show the selected network interface.'))
            self.remember_subject('interface', selected)

    def choose_podman_actions(self):
        # A name supplied by the user is validated; no container is started.
        fields = self.fields(L('Choose Podman container'), [(L('Existing Podman container name or ID'), '')])
        if fields and fields[0]:
            try:
                subject = Subject('container', fields[0])
                self.composer.choose(subject)
                self.prepare_recipe('container.inspect')
                self.remember_subject('container', fields[0])
            except (ValueError, OSError) as exc:
                self.message(str(exc))

    def choose_volume_actions(self):
        try:
            volumes = scan_volumes()
        except RuntimeError as exc:
            self.message(str(exc))
            return
        pairs = [(f'{v.path} | {v.label or v.fstype} | {v.mountpoint or L("not mounted")}', v)
                 for v in volumes]
        volume = self._choose_item('Choose HDD/SSD', pairs)
        if volume:
            try:
                self.composer.choose(Subject('volume', volume))
                self.prepare_recipe('volume.details')
                self.remember_subject('volume', volume)
            except (ValueError, OSError) as exc:
                self.message(str(exc))

    def search_apps(self):
        """Search actual Flatpak appstream results and select one as context."""
        issue = availability(Command('', ['flatpak'], ''))
        if issue:
            self.message(issue)
            return
        args = self.fields(L('Search apps'), [(L('Search term'), '')])
        if not args or not args[0].strip():
            return
        term = args[0].strip()
        try:
            fallback = parameter_command('search', term)
        except ValueError as error:
            self.message(str(error))
            return
        self.stage(fallback)
        def worker():
            installed_ids = set()
            try:
                result = run_host(
                    ['flatpak', 'search', '--columns=name,application,version,remotes', '--', term],
                    capture_output=True, text=True, timeout=35,
                    env={**os.environ, 'LC_ALL': 'C'}, check=True)
                rows, error = parse_flatpak_search(result.stdout), None
                try:
                    installed = run_host(
                        ['flatpak', 'list', '--app', '--columns=application'],
                        capture_output=True, text=True, timeout=10, check=True,
                        env={**os.environ, 'LC_ALL': 'C'})
                    installed_ids = set(installed.stdout.splitlines())
                except (OSError, subprocess.SubprocessError):
                    pass
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                rows, error = [], str(exc)
            GLib.idle_add(self.show_search_results, term, rows, error, installed_ids)
        threading.Thread(target=worker, daemon=True).start()

    def show_search_results(self, term, rows, error, installed_ids):
        if self.destroyed:
            return False
        if error:
            self.message(L('Could not load search results: ') + error)
            return False
        if not rows:
            self.message(L('No apps found; the search command remains in the preview.'))
            return False
        d = Gtk.Dialog(title=L('Choose an app'), transient_for=self, modal=True)
        d.set_default_size(680, 410)
        d.add_buttons(L('Cancel'), Gtk.ResponseType.CANCEL,
                      L('Select app'), Gtk.ResponseType.OK)
        model = Gtk.ListStore(str, str, str, str)
        for row in rows:
            model.append(row)
        query = Gtk.SearchEntry(placeholder_text=L('Filter apps…'))
        filtered = model.filter_new()
        filtered.set_visible_func(lambda m, it, *_: query.get_text().casefold() in
                                  ' '.join(m[it]).casefold())
        query.connect('search-changed', lambda *_: filtered.refilter())
        view = Gtk.TreeView(model=filtered)
        for idx, name in enumerate(('Name', 'App ID', 'Version', 'Remote')):
            col = Gtk.TreeViewColumn(L(name), Gtk.CellRendererText(), text=idx)
            col.set_resizable(True)
            view.append_column(col)
        scroll = Gtk.ScrolledWindow()
        scroll.add(view)
        d.get_content_area().pack_start(query, False, False, 6)
        d.get_content_area().pack_start(scroll, True, True, 0)
        d.show_all()
        if d.run() == Gtk.ResponseType.OK:
            selected_model, it = view.get_selection().get_selected()
            if it is not None:
                name, app_id, version, origin = (selected_model[it][i] for i in range(4))
                d.destroy()
                # The installed app list was fetched in the worker thread;
                # selecting a result never blocks GTK waiting for Flatpak.
                try:
                    app = SelectedApp(app_id, name, app_id in installed_ids, origin)
                    self.picked_app(app, app_preview(app, term))
                except ValueError as exc:
                    self.message(str(exc))
                return False
        d.destroy()
        return False

    def choose_app_storage(self):
        app = self.selected_app
        if app is None:
            self.choose_volume_actions()
            return
        try:
            volumes = scan_volumes()
        except RuntimeError as exc:
            self.message(str(exc))
            return
        if not volumes:
            self.message(L('No suitable data partitions found.'))
            return
        dialog = Gtk.Dialog(title=L('Choose HDD/SSD folder for ') + app.display_name,
                            transient_for=self, modal=True)
        dialog.set_default_size(550, 260)
        dialog.add_buttons(L('Cancel'), Gtk.ResponseType.CANCEL,
                           L('Prepare command'), Gtk.ResponseType.OK)
        area = dialog.get_content_area()
        area.set_spacing(9)
        area.set_border_width(14)
        tip = Gtk.Label(label=L('Select the disk, then an existing folder. '
                                'Unmounted disks receive a mount command first.'),
                        xalign=0, wrap=True)
        area.pack_start(tip, False, False, 0)
        combo = Gtk.ComboBoxText()
        for v in volumes:
            combo.append_text(f'{v.path}  |  {v.label or v.fstype}  |  '
                              f'{v.size}  |  {v.mountpoint or L("not mounted")}')
        area.pack_start(combo, False, False, 0)
        folder_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        path_text = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.MIDDLE)
        pick_button = Gtk.Button(label=L('Choose folder…'))
        folder_box.pack_start(pick_button, False, False, 0)
        folder_box.pack_start(path_text, True, True, 0)
        area.pack_start(folder_box, False, False, 0)
        warning = Gtk.Label(label='', xalign=0, wrap=True)
        area.pack_start(warning, False, False, 0)
        chosen = [None]
        def current():
            idx = combo.get_active()
            return volumes[idx] if 0 <= idx < len(volumes) else None
        def changed(*_):
            chosen[0] = None
            path_text.set_text('')
            volume = current()
            pick_button.set_sensitive(bool(volume and volume.mountpoint))
            if volume is None:
                warning.set_text('')
            elif not volume.mountpoint:
                warning.set_text(L('This disk is not mounted. First prepare a mount command.'))
            elif not app.installed:
                warning.set_text(L('This app is not installed. Install it before granting folder access.'))
            else:
                warning.set_text(L('This command grants folder access; it does not move the app.'))
        def choose_folder(*_):
            vol = current()
            if vol is None or not vol.mountpoint:
                return
            chooser = Gtk.FileChooserDialog(title=L('Choose folder…'), transient_for=dialog,
                                            action=Gtk.FileChooserAction.SELECT_FOLDER)
            chooser.add_buttons(L('Cancel'), Gtk.ResponseType.CANCEL,
                                L('Choose'), Gtk.ResponseType.OK)
            chooser.set_current_folder(vol.mountpoint)
            if chooser.run() == Gtk.ResponseType.OK:
                chosen[0] = chooser.get_filename()
                path_text.set_text(chosen[0] or '')
            chooser.destroy()
        pick_button.connect('clicked', choose_folder)
        combo.connect('changed', changed)
        combo.set_active(0)
        dialog.show_all()
        answer = dialog.run()
        volume = current()
        folder = chosen[0]
        dialog.destroy()
        if answer != Gtk.ResponseType.OK or volume is None:
            return
        try:
            # The same registry now handles app + disk + folder, not a
            # one-off UI command branch. A not-yet-mounted volume offers a
            # separate mount proposal, never a combined hidden side effect.
            self.composer.choose(Subject('volume', volume))
            if volume.mountpoint:
                if folder:
                    self.composer.choose(Subject('folder', folder))
                cmd, notes = self.composer.compose('app.folder_access')
            else:
                cmd, notes = self.composer.compose('volume.mount')
        except (ValueError, OSError) as error:
            self.message(L(str(error)))
            return
        self.stage(cmd, keep_app=True)
        self.description.set_text(L(cmd.explanation) + '\n' + L(notes) +
                                  '\n' + L('Review the command before inserting it.'))

    def message(self, text):
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.INFO,
                              buttons=Gtk.ButtonsType.OK, text=L(text))
        d.run(); d.destroy()

    def confirm(self, text):
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                             buttons=Gtk.ButtonsType.YES_NO, text=L(text))
        answer = d.run(); d.destroy()
        return answer == Gtk.ResponseType.YES

    def run(self, *_):
        cmd = self.command
        if not cmd: return
        issue = availability(cmd)
        if issue and not (in_flatpak() and issue.startswith('Ontbrekend hulpmiddel: ')):
            self.message(L(issue)); return
        tab = self.tabs.get_nth_page(0)
        if tab is None or tab.done:
            self.message('Open eerst de terminal.'); return
        if tab.pid is None:
            self.message('De shell wordt nog gestart. Probeer het opnieuw zodra de prompt verschijnt.')
            return
        shell_state = tab.at_shell()
        if shell_state is False:
            self.message('Een programma gebruikt momenteel de terminal. Sluit dit programma of ga terug naar de shellprompt. Dan kun je het commando invoegen.')
            return
        if shell_state is None:
            # Some platforms cannot inspect foreground process group via the
            # PTY master. Do not permanently block guided commands on these.
            if not self.confirm(L('Niet vast te stellen of de shellprompt actief is.\n\nVoeg alleen in wanneer je bij een lege shellprompt staat. Toch invoegen?')):
                return
        if user_shell() != HOST_ACCOUNT_SHELL and Path(user_shell()).name not in ('bash','sh','dash','ash','zsh','ksh','mksh','fish'):
            self.message('Deze shell heeft mogelijk andere aanhalingstekens. Controleer de syntaxis voordat je de opdracht uitvoert.'); return
        try:
            text = terminal_line(cmd)
        except ValueError as e:
            self.message(str(e)); return
        # No newline: the user reviews/edits the line and presses Enter personally.
        tab.insert_text(text)
        tab.term.grab_focus()
        self.composer.clear()
        self.selected_app = None
        self.update_app_context()
        self.history.append(cmd)
        self.history = self.history[-100:]
        self.status.set_text(L('Commando ingevoegd. Controleer de hele opdrachtregel en druk zelf op Enter.'))
        self.selected_app = None
        self.update_app_context()

    def shell(self):
        # A regular terminal should work inside containers too. Guided actions
        # that assume host access remain disabled via core.availability().
        current = self.tabs.get_nth_page(0)
        if current is not None:
            if not current.done:
                current.term.grab_focus(); return
            self.tabs.remove_page(0)
        try:
            shell_path = user_shell()
        except RuntimeError as e:
            self.message(str(e)); return
        # Run the user's own interactive shell with its standard rc files.
        # Some distributions also show a startup banner in their shell rc;
        # leave this untouched so distro-specific behavior remains native.
        try:
            argv = host_shell_argv(shell_path, self.workdir)
        except (ValueError, RuntimeError) as error:
            self.message(str(error)); return
        self.spawn(argv, self.workdir, 'Terminal')

    def spawn(self, argv, cwd, title, guided=False):
        if not Path(cwd).is_dir():
            self.message('De werkmap bestaat niet meer.'); return
        tab = TerminalTab(self, argv, cwd, title, guided=guided)
        self.running += 1
        self.tabs.append_page(tab, Gtk.Label(label=L('Terminal')))
        self.tabs.set_current_page(0)
        tab.start()

    def session_finished(self, tab):
        self.running -= 1
        self.status.set_text(L('Terminal afgesloten. Gebruik Terminal opnieuw openen voor een nieuwe sessie.'))

    def choose_workdir(self):
        path = self.choose(L('Werkmap kiezen'), folder=True)
        if path:
            self.stage(Command('Werkmap wijzigen', ['cd', '--', path], 'Zet cd klaar; druk in de terminal op Enter om van map te wisselen.'))

    def show_history(self):
        if not self.history: self.message('Nog geen begeleide opdrachten uitgevoerd.'); return
        d = Gtk.Dialog(title=L('Opdracht opnieuw voorbereiden'), transient_for=self, modal=True)
        d.add_buttons(L('Annuleren'), Gtk.ResponseType.CANCEL, L('Voorbereiden'), Gtk.ResponseType.OK)
        combo = Gtk.ComboBoxText()
        for command in reversed(self.history): combo.append_text(command.preview)
        combo.set_active(0); d.get_content_area().add(combo); d.show_all()
        if d.run() == Gtk.ResponseType.OK:
            self.stage(list(reversed(self.history))[combo.get_active()])
        d.destroy()

    def parameter(self, kind):
        if kind == 'logs' and self.composer.selected.get('service'):
            self.prepare_recipe('service.logs')
            return
        if kind == 'service' and self.composer.selected.get('service'):
            self.prepare_recipe('service.status')
            return
        if kind == 'hash':
            value = self.choose(L('Bestand voor SHA256'))
            if not value: return
            args = [value]
        else:
            labels = {'search':'Zoekterm', 'install':'App-ID', 'ping':'Hostnaam of IP',
                      'service':'Systeemservice', 'logs':'Systeemservice', 'container':'Bestaande containernaam'}
            fields = [(L(labels[kind]), '')]
            if kind == 'install': fields.append((L('Bestaande Flatpak-bron'), 'flathub'))
            args = self.fields(L(labels[kind]), fields)
            if not args: return
        try:
            # For the same service, switching between status and logs should
            # update the current draft instead of prompting for the name again.
            command = parameter_command(kind, *args)
            self.stage(command)
            category = {'service':'service', 'logs':'service', 'hash':'file', 'ping':'host'}.get(kind)
            if category:
                self.remember_subject(category, args[0])
        except ValueError as e: self.message(str(e))

    def choose(self, title, folder=False, save=False):
        action = Gtk.FileChooserAction.SELECT_FOLDER if folder else (Gtk.FileChooserAction.SAVE if save else Gtk.FileChooserAction.OPEN)
        d = Gtk.FileChooserDialog(title=L(title), transient_for=self, action=action)
        d.add_buttons(L('Annuleren'), Gtk.ResponseType.CANCEL, L('Kiezen'), Gtk.ResponseType.OK)
        result = d.get_filename() if d.run() == Gtk.ResponseType.OK else None
        d.destroy(); return result

    def fields(self, title, names):
        d = Gtk.Dialog(title=L(title), transient_for=self, modal=True)
        d.add_buttons(L('Annuleren'), Gtk.ResponseType.CANCEL, L('Voorbereiden'), Gtk.ResponseType.OK)
        content = d.get_content_area(); content.set_spacing(8); content.set_border_width(16)
        entries = []
        for name, default in names:
            content.add(Gtk.Label(label=L(name), xalign=0))
            entry = Gtk.Entry(text=default); entry.set_width_chars(48)
            content.add(entry); entries.append(entry)
        d.show_all()
        result = [e.get_text().strip() for e in entries] if d.run() == Gtk.ResponseType.OK else None
        d.destroy(); return result

    def bundle_form(self):
        repo = self.choose('Kies een gebouwde Flatpak-repository', folder=True)
        if not repo: return
        values = self.fields(L('Bundle exporteren'), [(L('App-ID'), self.last_manifest.get('app-id') or self.last_manifest.get('id','')), (L('Branch'), self.last_manifest.get('branch') or 'master')])
        if not values: return
        output = self.choose('Nieuwe .flatpak-bundle opslaan', save=True)
        if not output: return
        if not output.endswith('.flatpak'): output += '.flatpak'
        try: self.stage(bundle(repo, output, *values))
        except ValueError as e: self.message(str(e))

    def build_form(self):
        project = self.choose('Kies de vertrouwde projectmap', folder=True)
        if not project: return
        candidates = [p for p in Path(project).iterdir() if p.is_file() and p.suffix in ('.json','.yml','.yaml')]
        manifest = str(candidates[0]) if len(candidates) == 1 else self.choose('Kies het JSON/YAML-manifest')
        if not manifest: return
        try:
            try:
                self.last_manifest = {}
                self.last_manifest = manifest_info(manifest)
                self.message(L('Manifest: ')+str(self.last_manifest)+'\n'+L('Controleer of runtime en SDK geïnstalleerd zijn.'))
            except (ValueError, OSError) as e:
                self.message(L('Manifestgegevens niet uitgelezen: ')+str(e))
            target = Path(project)/'ult-build'
            if target.exists(): target = Path(project)/('ult-build-'+uuid.uuid4().hex[:8])
            self.stage(build(project, manifest, str(Path(project)/'ult-repo'), str(target)))
        except ValueError as e: self.message(str(e))

    def install(self):
        path = self.choose('Kies een .flatpak of .flatpakref')
        if not path: return
        if Path(path).suffix not in ('.flatpak', '.flatpakref'):
            self.message('Kies een .flatpak- of .flatpakref-bestand.'); return
        self.stage(Command('Lokale Flatpak installeren', ['flatpak','install','--user',str(Path(path).resolve())],
                           'Installeert voor de huidige gebruiker. Flatpak toont de benodigde onderdelen.', True))

    def remove(self, action='uninstall'):
        issue = availability(Command('', ['flatpak'], ''))
        if issue: self.message(issue); return
        self.status.set_text(L('Flatpak-apps worden geladen…'))
        def work():
            rows = []; error = None
            try:
                result = run_host(['flatpak','list','--app','--columns=ref,name,version,origin,installation'],
                    capture_output=True, text=True, timeout=30, env={**os.environ, 'LC_ALL':'C'}, check=True)
                rows = parse_apps(result.stdout)
            except (OSError, ValueError, subprocess.SubprocessError) as e:
                error = (getattr(e, 'stderr', None) or str(e))
            GLib.idle_add(self.show_apps, rows, error, action)
        threading.Thread(target=work, daemon=True).start()

    def show_apps(self, rows, error, action):
        if self.destroyed: return False
        self.status.set_text(L('App-lijst geladen') if not error else L('Ophalen mislukt'))
        if error: self.message(error); return False
        if not rows: self.message('Geen Flatpak-apps gevonden.'); return False
        d = Gtk.Dialog(title='Flatpak — '+action, transient_for=self, modal=True)
        d.set_default_size(900, 450)
        d.add_buttons(L('Annuleren'), Gtk.ResponseType.CANCEL, L('Commando voorbereiden'), Gtk.ResponseType.OK)
        model = Gtk.ListStore(str, str, str, str, str)
        for row in sorted(rows, key=lambda x:x[0].casefold()): model.append(row)
        search = Gtk.SearchEntry(placeholder_text=L('Zoek app, branch of installatie…'))
        filtered = model.filter_new()
        filtered.set_visible_func(lambda m, it, _: search.get_text().casefold() in ' '.join(m[it]).casefold())
        search.connect('search-changed', lambda *_: filtered.refilter())
        sortable = Gtk.TreeModelSort(model=filtered)
        tree = Gtk.TreeView(model=sortable)
        for i, name in enumerate(['App', 'App/architectuur/branch', 'Versie', 'Bron', 'Installatie']):
            col = Gtk.TreeViewColumn(L(name), Gtk.CellRendererText(), text=i)
            col.set_resizable(True); col.set_sort_column_id(i); tree.append_column(col)
        scroll = Gtk.ScrolledWindow(); scroll.add(tree)
        d.get_content_area().pack_start(search, False, False, 6)
        d.get_content_area().pack_start(scroll, True, True, 0)
        d.show_all()
        if d.run() == Gtk.ResponseType.OK:
            m, it = tree.get_selection().get_selected()
            if it is not None:
                try:
                    cmd = flatpak_action(action, m[it][1], m[it][4])
                    if action in ('info', 'permissions'):
                        chosen = SelectedApp(m[it][1].split('/')[1], m[it][0], True, m[it][3])
                        d.destroy()
                        self.picked_app(chosen, cmd)
                        return False
                    self.stage(cmd)
                except ValueError as e: self.message(str(e))
        d.destroy(); return False

    def shutdown(self):
        if self.destroyed:
            return False
        self.destroyed = True
        self.destroy()
        if Gtk.main_level() > 0:
            Gtk.main_quit()
        return False

    def closing(self, *_):
        if self.running and not self.confirm('Terminal afsluiten? Eventuele lopende programma’s kunnen hierdoor stoppen.'):
            return True
        self.shutdown()
        return True

    def interrupted(self):
        # SIGINT belongs to the launcher Konsole, not to the PTY child.
        # Use GLib's main loop handler to exit without KeyboardInterrupt dump.
        self.shutdown()
        return GLib.SOURCE_REMOVE

if __name__ == '__main__':
    configure_application_identity(Gtk, GLib, Gdk)
    window = Window()
    try:
        if GLibUnix is not None:
            GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, window.interrupted)
        else:
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, window.interrupted)
        Gtk.main()
    except KeyboardInterrupt:
        # Defensive fallback if another library handles SIGINT in Python.
        window.shutdown()
    finally:
        # The app is leaving; avoid removing an already-dispatched SIGINT
        # source (which causes an unnecessary GLib critical warning).
        if not window.destroyed:
            window.shutdown()
