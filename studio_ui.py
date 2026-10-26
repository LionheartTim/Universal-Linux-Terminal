"""GTK widgets for host command discovery and a genuinely guided Steam workflow."""
import shlex
import threading
from gi.repository import GLib
from gi.repository import Gtk, Pango
from command_discovery import installed_commands
from option_discovery import load_command_info, prepare_with_options
from gtk_selection import select_visible_child
from guided_workflows import scan_volumes, build_steam_plan, steam_installed_as_flatpak
from i18n import tr as L


def _label(value):
    widget = Gtk.Label(label=L(value), xalign=0)
    widget.set_line_wrap(True)
    widget.set_selectable(True)
    return widget


def open_installed_commands(owner, initial_command=None, inventory=None):
    """Open a searchable option builder, optionally focused on a sidebar hit.

    Selecting a command loads its documented options in the lower pane.
    Only user-selected commands are inspected, and no composed command runs.
    """
    try:
        found = inventory if inventory is not None else installed_commands()
    except (OSError, RuntimeError, ValueError) as error:
        owner.message(L('Could not discover host commands: ') + str(error))
        return
    if not found:
        owner.message(L('No installed commands found in PATH.'))
        return
    dialog = Gtk.Dialog(title=L('All installed commands'), transient_for=owner,
                        modal=True)
    dialog.set_default_size(800, 660)
    dialog.add_buttons(L('Annuleren'), Gtk.ResponseType.CANCEL,
                       L('Voorbereiden'), Gtk.ResponseType.OK)
    dialog.set_response_sensitive(Gtk.ResponseType.OK, False)
    root = dialog.get_content_area()
    root.set_border_width(10)
    root.set_spacing(7)
    root.pack_start(_label('Shows programs on your PATH and Bash builtins. '
                           'Aliases and shell functions defined in the current terminal '
                           'cannot always be discovered. Selecting a program loads its '
                           'options using --help; select trusted programs only. '
                           'A prepared command is never run automatically.'), False, False, 0)
    search = Gtk.SearchEntry(placeholder_text=L('Search installed commands…'))
    root.pack_start(search, False, False, 0)
    model = Gtk.ListStore(str, str, str)
    by_name = {cmd.name: cmd for cmd in found}
    for cmd in found:
        model.append([cmd.name, cmd.kind, cmd.location])
    filtered = model.filter_new()
    filtered.set_visible_func(lambda m, it, *_:
        search.get_text().casefold() in m[it][0].casefold())
    search.connect('search-changed', lambda *_: filtered.refilter())
    tree = Gtk.TreeView(model=filtered, headers_visible=True)
    for i, title in enumerate(('Command', 'Type', 'Location')):
        column = Gtk.TreeViewColumn(L(title), Gtk.CellRendererText(), text=i)
        column.set_resizable(True)
        tree.append_column(column)
    scroll = Gtk.ScrolledWindow()
    scroll.set_min_content_height(130)
    scroll.add(tree)
    root.pack_start(scroll, True, True, 0)

    # One selection -> immediate asynchronous options in the lower pane.
    # No second click, no extra confirmation; explain the help-request caveat
    # persistently above. Only the selected executable is inspected.
    option_state = _label('Select a command to see its options below. You can also type arguments manually.')
    root.pack_start(option_state, False, False, 0)
    option_filter = Gtk.SearchEntry(placeholder_text=L('Filter options…'))
    root.pack_start(option_filter, False, False, 0)

    options = []
    # selected, option spelling, description, user-entered value, index
    option_model = Gtk.ListStore(bool, str, str, str, int)
    visible_options = option_model.filter_new()
    visible_options.set_visible_func(
        lambda m, it, *_: option_filter.get_text().casefold() in
        (m[it][1] + ' ' + m[it][2]).casefold())
    option_filter.connect('search-changed', lambda *_: visible_options.refilter())
    option_view = Gtk.TreeView(model=visible_options, headers_visible=True)
    toggle = Gtk.CellRendererToggle()
    option_view.append_column(Gtk.TreeViewColumn(L('Use'), toggle, active=0))
    option_view.append_column(Gtk.TreeViewColumn(L('Option'), Gtk.CellRendererText(), text=1))
    description_renderer = Gtk.CellRendererText()
    description_renderer.set_property('ellipsize', Pango.EllipsizeMode.END)
    desc_column = Gtk.TreeViewColumn(L('Description'), description_renderer, text=2)
    desc_column.set_expand(True)
    desc_column.set_resizable(True)
    option_view.append_column(desc_column)
    value_renderer = Gtk.CellRendererText()
    value_renderer.set_property('editable', True)
    value_column = Gtk.TreeViewColumn(L('Value'), value_renderer, text=3)
    value_column.set_min_width(115)
    def value_editable(column, cell, model_filter, it, *_):
        index = model_filter[it][4]
        cell.set_property('editable', bool(options[index].takes_value))
    value_column.set_cell_data_func(value_renderer, value_editable)
    option_view.append_column(value_column)
    option_scroll = Gtk.ScrolledWindow()
    option_scroll.set_min_content_height(145)
    option_scroll.add(option_view)
    root.pack_start(option_scroll, True, True, 0)

    root.pack_start(_label('Additional arguments (optional; no shell pipes):'), False, False, 0)
    args = Gtk.Entry()
    root.pack_start(args, False, False, 0)
    preview = Gtk.Label(xalign=0, selectable=True, wrap=True)
    root.pack_start(preview, False, False, 0)
    selection = tree.get_selection()
    state = {'active': True, 'generation': 0, 'loading': False, 'cache': {}}

    def get_selected():
        m, it = selection.get_selected()
        return by_name.get(m[it][0]) if it is not None else None

    def prepared():
        target = get_selected()
        if target is None:
            raise ValueError(L('Select a command first.'))
        chosen = [(options[option_model[it][4]], option_model[it][3])
                  for it in range(len(option_model)) if option_model[it][0]]
        return prepare_with_options(target.name, args.get_text(), found, chosen)

    def changed(*_):
        try:
            cmd = prepared()
            preview.set_text(cmd.preview)
            dialog.set_response_sensitive(Gtk.ResponseType.OK, not state['loading'])
        except ValueError as error:
            preview.set_text(L(str(error)))
            dialog.set_response_sensitive(Gtk.ResponseType.OK, False)

    def command_changed(*_):
        # Invalidate previous asynchronous requests before changing the UI.
        state['generation'] += 1
        state['loading'] = False
        option_model.clear()
        options.clear()
        args.set_text('')
        option_filter.set_text('')
        target = get_selected()
        if target is None:
            option_state.set_text(L('Select a command to see its options below. You can also type arguments manually.'))
            changed()
            return
        # Reading help happens only after the user explicitly selects a
        # program, not during full inventory scanning or while typing in search.
        load_selected_options(target, state['generation'])

    def toggled(renderer, path):
        child_it = visible_options.convert_iter_to_child_iter(visible_options.get_iter(Gtk.TreePath.new_from_string(path)))
        option_model[child_it][0] = not option_model[child_it][0]
        changed()

    def value_edited(renderer, path, new_value):
        child_it = visible_options.convert_iter_to_child_iter(visible_options.get_iter(Gtk.TreePath.new_from_string(path)))
        option_model[child_it][3] = new_value
        changed()

    def populate_options(parsed, error=None):
        options.clear()
        options.extend(parsed)
        option_model.clear()
        for index, option in enumerate(options):
            option_model.append([False, option.display, option.description, '', index])
        state['loading'] = False
        if error:
            option_state.set_text(L(error))
        elif options:
            option_state.set_text(L('Options found: ') + str(len(options)) +
                                  '. ' + L('Tick options, then enter values where needed.'))
        else:
            option_state.set_text(L('No recognizable options found. You can still type arguments manually.'))
        changed()

    def load_selected_options(target, generation):
        cache_key = (target.name, target.kind, target.location)
        cached = state['cache'].get(cache_key)
        if cached is not None:
            populate_options(*cached)
            return
        state['loading'] = True
        option_state.set_text(L('Reading command help…'))
        changed()  # Prevent preparing before option discovery has finished.

        def worker():
            try:
                details = (owner.get_cached_command_info(target)
                           if hasattr(owner, 'get_cached_command_info') else None)
                if details is None:
                    details = load_command_info(target)
                parsed, error = list(details.options), None
            except (ValueError, OSError, RuntimeError) as exc:
                details, parsed, error = None, [], str(exc)
            def done():
                # A changed selection or closed dialog must never be updated by
                # an earlier asynchronous request.
                if not state['active'] or state['generation'] != generation:
                    return False
                state['cache'][cache_key] = (parsed, error)
                if details is not None and hasattr(owner, 'cache_command_info'):
                    owner.cache_command_info(target, details)
                populate_options(parsed, error)
                return False
            GLib.idle_add(done)
        threading.Thread(target=worker, daemon=True).start()

    selection.connect('changed', command_changed)
    args.connect('changed', changed)
    toggle.connect('toggled', toggled)
    value_renderer.connect('edited', value_edited)
    if initial_command and initial_command in by_name:
        search.set_text(initial_command)
        filtered.refilter()
        child = model.get_iter_first()
        while child is not None:
            if model[child][0] == initial_command:
                # PyGObject returns (was_visible, Gtk.TreeIter), not just
                # the iterator.  Never pass its _ResultTuple to select_iter().
                select_visible_child(filtered, selection, child)
                break
            child = model.iter_next(child)
    tree.connect('row-activated', lambda *_: dialog.response(Gtk.ResponseType.OK)
                 if dialog.get_widget_for_response(Gtk.ResponseType.OK).get_sensitive() else None)
    dialog.show_all()
    response = dialog.run()
    state['active'] = False
    if response == Gtk.ResponseType.OK:
        try:
            cmd = prepared()
        except ValueError as error:
            dialog.destroy()
            owner.message(L(str(error)))
            return
        target = get_selected()
        chosen = [(options[option_model[it][4]], option_model[it][3])
                  for it in range(len(option_model)) if option_model[it][0]]
        dialog.destroy()
        owner.stage(cmd)
        if target is not None and hasattr(owner, 'show_command_info'):
            owner.show_command_info(target, chosen)
        return
    dialog.destroy()


class SteamStorageWizard(Gtk.Assistant):
    """Choice sequence: Steam -> storage -> volume -> folder -> review."""
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.set_title(L('Steam storage helper'))
        self.set_transient_for(owner)
        self.set_modal(True)
        self.set_default_size(590, 445)
        self.volumes = []
        self.prepared_command = None
        self.steps = ''

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(16)
        page.pack_start(_label('1. Steam  →  Mount / storage  →  Volume  →  Folder'), False, False, 0)
        page.pack_start(_label('Goal: use a Steam game library on another Linux drive.'), False, False, 0)
        page.pack_start(_label('How is Steam installed?'), False, False, 0)
        self.method = Gtk.ComboBoxText()
        self.method.append('flatpak', L('Steam Flatpak'))
        self.method.append('native', L('Steam native (RPM, DEB, Arch, etc.)'))
        self.method.set_active_id('flatpak' if steam_installed_as_flatpak() else 'native')
        page.pack_start(self.method, False, False, 0)
        page.pack_start(_label('The builder detects real volumes and never formats disks. '
                               'You review the final command before using it.'), False, False, 0)
        self.append_page(page)
        self.set_page_title(page, L('Steam and action'))
        self.set_page_type(page, Gtk.AssistantPageType.INTRO)
        self.set_page_complete(page, True)

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(16)
        page.pack_start(_label('2. Select a real data volume (not the entire disk).'), False, False, 0)
        self.volcombo = Gtk.ComboBoxText()
        page.pack_start(self.volcombo, False, False, 0)
        refresh = Gtk.Button(label=L('Refresh volumes'))
        refresh.connect('clicked', lambda *_: self.refresh())
        page.pack_start(refresh, False, False, 0)
        self.volstatus = _label('')
        page.pack_start(self.volstatus, False, False, 0)
        self.volcombo.connect('changed', self.changed_volume)
        self.volpage = page
        self.append_page(page)
        self.set_page_title(page, L('Choose drive'))
        self.set_page_type(page, Gtk.AssistantPageType.CONTENT)
        self.set_page_complete(page, False)

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(16)
        page.pack_start(_label('3. Choose an existing folder on the selected volume.'), False, False, 0)
        self.folder = Gtk.FileChooserButton.new(L('Choose library folder'), Gtk.FileChooserAction.SELECT_FOLDER)
        page.pack_start(self.folder, False, False, 0)
        self.folderstatus = _label('')
        page.pack_start(self.folderstatus, False, False, 0)
        self.folder.connect('file-set', lambda *_: self.set_page_complete(page, True))
        self.folderpage = page
        self.append_page(page)
        self.set_page_title(page, L('Library folder'))
        self.set_page_type(page, Gtk.AssistantPageType.CONTENT)
        self.set_page_complete(page, True)

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(16)
        page.pack_start(_label('4. Review your generated command and the next steps.'), False, False, 0)
        self.preview = _label('')
        page.pack_start(self.preview, False, False, 0)
        self.reviewpage = page
        self.append_page(page)
        self.set_page_title(page, L('Review command'))
        self.set_page_type(page, Gtk.AssistantPageType.CONFIRM)
        self.set_page_complete(page, False)
        self.connect('prepare', self.page_prepared)
        self.connect('cancel', lambda *_: self.destroy())
        self.connect('close', lambda *_: self.destroy())
        self.connect('apply', self.apply)
        self.refresh()
        self.show_all()

    def selected_volume(self):
        index = self.volcombo.get_active()
        return self.volumes[index] if 0 <= index < len(self.volumes) else None

    def refresh(self):
        previous = self.selected_volume()
        try:
            self.volumes = scan_volumes()
        except RuntimeError as error:
            self.volumes = []
            self.volstatus.set_text(str(error))
        self.volcombo.remove_all()
        for vol in self.volumes:
            label = f'{vol.path}  |  {vol.label or vol.fstype}  |  {vol.size}  |  '
            label += vol.mountpoint or L('not mounted')
            self.volcombo.append_text(label)
        if self.volumes:
            index = next((i for i,v in enumerate(self.volumes)
                          if previous and v.path == previous.path), 0)
            self.volcombo.set_active(index)
        else:
            self.volstatus.set_text(L('No suitable data partitions found. Attach a disk and refresh.'))
        self.set_page_complete(self.volpage, bool(self.volumes))

    def changed_volume(self, *_):
        vol = self.selected_volume()
        if vol:
            self.volstatus.set_text((L('Mounted at: ') + vol.mountpoint) if vol.mountpoint
                                    else L('This volume must be mounted before browsing folders.'))

    def page_prepared(self, assistant, page):
        volume = self.selected_volume()
        if page == self.folderpage:
            if volume is None:
                self.folderstatus.set_text(L('Select a volume first.'))
                self.folder.set_sensitive(False)
            elif volume.mountpoint is None:
                self.folder.set_sensitive(False)
                self.folderstatus.set_text(L('Not mounted: prepare the mount command first, '
                                              'then come back to choose a folder.'))
            else:
                self.folder.set_sensitive(True)
                self.folderstatus.set_text(L('Folder must be on: ') + volume.mountpoint)
                self.folder.set_current_folder(volume.mountpoint)
            self.set_page_complete(page, True)
        if page == self.reviewpage:
            self.prepared_command = None
            if volume is None:
                self.preview.set_text(L('Select a volume first.'))
                self.set_page_complete(page, False)
                return
            try:
                folder = self.folder.get_filename() if volume.mountpoint else None
                cmd, steps = build_steam_plan(volume, folder, self.method.get_active_id())
                self.prepared_command, self.steps = cmd, steps
                text = (L('Command to prepare (you press Enter yourself):') + '\n' +
                        (cmd.preview if cmd else L('No terminal command needed.')) + '\n\n' + L(steps))
                self.preview.set_text(text)
                self.set_page_complete(page, True)
            except (ValueError, OSError) as error:
                self.preview.set_text(L(str(error)))
                self.set_page_complete(page, False)

    def apply(self, *_):
        cmd = self.prepared_command
        steps = self.steps
        self.destroy()
        if cmd is not None:
            self.owner.stage(cmd)
            self.owner.message(steps)
        else:
            self.owner.message(steps)


def open_steam_storage(owner):
    return SteamStorageWizard(owner)
