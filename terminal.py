"""VTE PTY terminal: keyboard, selection and helper pastes share one shell."""
import os
import signal
import time
import shlex
from pathlib import Path
from gi.repository import Gtk, Gdk, GLib, Vte, Pango, Gio
from i18n import tr as L
from host_bridge import in_flatpak
from paste_preferences import paste_confirmation_enabled, set_paste_confirmation_enabled

class TerminalTab(Gtk.Box):
    def __init__(self, owner, argv, cwd, title, guided=False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.owner, self.argv, self.cwd = owner, list(argv), cwd
        self.guided, self.done, self.started = guided, False, time.monotonic()
        self.pid = None
        self.spawn_pending = False
        self.term = Vte.Terminal()
        self.font_size = 11
        self.term.set_font(Pango.FontDescription('Monospace 11'))
        self.term.set_scrollback_lines(20000)
        bg = Gdk.RGBA(); bg.parse('#10151f')
        fg = Gdk.RGBA(); fg.parse('#e2e8f0')
        self.term.set_colors(fg, bg, [])
        self.term.set_scroll_on_output(False)
        self.term.set_scroll_on_keystroke(True)
        self.term.set_input_enabled(True)
        self.term.set_mouse_autohide(True)
        self.label = Gtk.Label(label=L(title)+' • '+L('starten…'), xalign=0)
        command_label = Gtk.Label(label=shlex.join(argv), xalign=0, selectable=True, wrap=True)
        # Ordinary shell: terminal's very first visible line is its own prompt.
        # Keep the status/argv labels for guided sessions and regression tests.
        if guided:
            self.pack_start(self.label, False, False, 0)
            self.pack_start(command_label, False, False, 0)
        area = Gtk.Box()
        area.pack_start(self.term, True, True, 0)
        area.pack_start(Gtk.Scrollbar(orientation=Gtk.Orientation.VERTICAL, adjustment=self.term.get_vadjustment()), False, False, 0)
        self.pack_start(area, True, True, 0)
        # FlowBox wraps the toolbar on narrower displays instead of clipping
        # the final buttons outside a half-width application window.
        actions = Gtk.FlowBox()
        actions.set_selection_mode(Gtk.SelectionMode.NONE)
        actions.set_column_spacing(5)
        actions.set_row_spacing(5)
        actions.set_min_children_per_line(1)
        actions.set_max_children_per_line(8)
        self.pack_start(actions, False, False, 0)
        def button(text, callback):
            b = Gtk.Button(label=text); b.connect('clicked', callback)
            actions.add(b)
            return b
        # Stop ends the application; Ctrl+C is a separate, non-destructive action.
        self.stop = button(L('Stop'), lambda *_: self.owner.closing())
        self.stop.set_tooltip_text(L('Sluit de applicatie na bevestiging.'))
        self.interrupt = button(L('Onderbreek opdracht (Ctrl+C)'), self.interrupt_command)
        button(L('Kopiëren'), lambda *_: self.term.copy_clipboard_format(Vte.Format.TEXT))
        button(L('Plakken…'), self.paste)
        button(L('Uitvoer opslaan'), self.save)
        button('−', lambda *_: self.zoom(-1))
        button('+', lambda *_: self.zoom(1))
        self.reset_button = button(L('Reset Terminal'), self.reset_terminal)
        self.close = button(L('Terminal opnieuw openen'), lambda *_: self.owner.shell())
        self.close.set_sensitive(False)
        self.term.connect('child-exited', self.exited)
        self.term.connect('key-press-event', self.key)
        self.term.connect('button-press-event', self.mouse)
        self.title = title
        self.timer = GLib.timeout_add_seconds(1, self.tick)
        self.show_all()

    def start(self):
        # IMPORTANT: On some PyGObject/VTE 2.91 bindings `child_setup_data`
        # is a separate Python parameter even though the published shortcut
        # signature omits it.  Without that extra None, the timeout's place
        # receives None -> 'Argument 9 does not allow None as a value'.
        # Expected on the affected bindings:
        # (pty_flags, cwd, argv, envv, spawn_flags, child_setup,
        #  child_setup_data, timeout, cancellable, callback)
        # See https://bugs.debian.org/996084 (2021, same traceback).
        self.spawn_pending = True
        try:
            self.term.spawn_async(
                Vte.PtyFlags.DEFAULT,
                self.cwd,
                self.argv,
                None,
                GLib.SpawnFlags.SEARCH_PATH,
                None,       # child_setup
                None,       # child_setup_data: required on Bazzite/PyGObject
                -1,         # timeout must be an int
                None,       # cancellable
                self.spawned,
            )
        except (TypeError, ValueError, GLib.Error, RuntimeError, OSError) as error:
            self.spawn_pending = False
            self.finish(L('Startfout: ') + str(error))
        self.term.grab_focus()

    def spawned(self, terminal, pid, error, *_):
        self.spawn_pending = False
        if self.done:
            return
        if error is not None or pid <= 0:
            self.finish(L('Startfout: ') + (str(error) if error else L('proces kon niet starten')))
        else:
            self.pid = pid
            self.label.set_text(f'{L(self.title)} • {L("shell actief")}')
            self.term.grab_focus()

    def at_shell(self):
        """True=shell foreground, False=busy, None=unknown (TTY lookup failed)."""
        if self.done or self.pid is None:
            return False
        if in_flatpak():
            # Our process is a Flatpak HostCommand proxy, not the host shell's
            # process group. Do not mislabel an interactive host shell busy.
            return None
        try:
            pty = self.term.get_pty()
            if pty is None:
                return None
            return os.tcgetpgrp(pty.get_fd()) == os.getpgid(self.pid)
        except (AttributeError, OSError, ProcessLookupError):
            # On some PTY implementations querying the master is unsupported.
            # Do not mistake that limitation for a dead or busy shell.
            return None

    def tick(self):
        if self.done: return False
        self.label.set_text(f'{L(self.title)} • {L("actief")} • {int(time.monotonic()-self.started)} s')
        return True

    def exited(self, _, status):
        try: code = os.waitstatus_to_exitcode(status)
        except ValueError: code = status
        result = L('geslaagd') if code == 0 else (f'{L("gestopt door signaal")} {-code}' if code < 0 else f'exitcode {code}')
        self.finish(f'{L(self.title)} • {result} • {int(time.monotonic()-self.started)} s')

    def finish(self, text):
        if self.done: return
        self.done = True
        if self.timer: GLib.source_remove(self.timer); self.timer = None
        self.label.set_text(text)
        # Ordinary shells deliberately start without an extra heading.
        # If a Flatpak host proxy fails immediately, still show the error
        # visibly rather than leaving a blank terminal pane.
        if not self.guided and self.label.get_parent() is None:
            self.pack_start(self.label, False, False, 0)
            self.reorder_child(self.label, 0)
            self.label.show()
        self.stop.set_sensitive(True); self.interrupt.set_sensitive(False); self.close.set_sensitive(True)
        self.reset_button.set_sensitive(False)
        self.owner.session_finished(self)

    def reset_terminal(self, *_):
        """Reset VTE display and scrollback, not the running PTY/shell.

        A screen-only reset must not kill user processes or change cwd.
        Ctrl+L asks an interactive shell to redraw the prompt. Never inject
        this key into a foreground program (editor, top, etc.).
        """
        if self.done or self.pid is None:
            return
        shell_foreground = self.at_shell()
        self.term.reset(True, True)
        if shell_foreground is True:
            self.term.feed_child(b'\x0c')
        self.term.grab_focus()

    def close_tab(self, *_):
        if self.done:
            self.owner.tabs.remove_page(self.owner.tabs.page_num(self))

    def zoom(self, amount):
        self.font_size = max(7, min(28, self.font_size+amount))
        self.term.set_font(Pango.FontDescription(f'Monospace {self.font_size}'))

    def interrupt_command(self, *_):
        """Interrupt foreground job, leaving the GUI and host shell open.

        On Flatpak's Python host PTY bridge the real foreground process lives
        on the *host* PTY, not VTE's relay PTY. Signal the local relay; it
        forwards a dedicated request to the host to interrupt its foreground
        process group. Keep normal Ctrl+C semantics for native shells and the
        util-linux script fallback.
        """
        if self.done or self.pid is None:
            return
        python_relay = (in_flatpak() and '--relay' in self.argv
                        and any(os.path.basename(arg) == 'host_pty_bridge.py'
                                for arg in self.argv))
        if python_relay:
            try:
                os.kill(self.pid, signal.SIGUSR1)
            except (ProcessLookupError, PermissionError):
                # The PTY might have exited during the click. Do not send a
                # literal ^C to a potentially unrelated or already-dead job.
                pass
        else:
            self.term.feed_child(b'\x03')
        self.term.grab_focus()

    def confirm_clipboard_paste(self, text):
        """Ask once unless the user explicitly chose to suppress the warning.

        Tick + Yes remembers the choice. Tick + No never disables future
        warnings: declining a paste cannot silently weaken the safeguard.
        The terminal's context menu lets the user re-enable this at any time.
        """
        if not paste_confirmation_enabled():
            return True
        message = L('Controleer de tekst. Bij Bash met bracketed paste worden alle regels eerst ingevoegd; druk daarna zelf op Enter. Zonder die ondersteuning kunnen nieuwe regels direct opdrachten uitvoeren.')
        dialog = Gtk.MessageDialog(transient_for=self.owner, modal=True,
                                   message_type=Gtk.MessageType.QUESTION,
                                   buttons=Gtk.ButtonsType.YES_NO,
                                   text=message + '\n\n' + text[:1500])
        check = Gtk.CheckButton(label=L('Deze plakwaarschuwing niet meer tonen'))
        check.set_tooltip_text(L('Je kunt de plakwaarschuwing opnieuw inschakelen via het rechtermuisknopmenu van de terminal.'))
        check.set_margin_start(12)
        check.set_margin_bottom(8)
        dialog.get_content_area().pack_start(check, False, False, 0)
        check.show()
        try:
            allowed = dialog.run() == Gtk.ResponseType.YES
            remember = allowed and check.get_active()
        finally:
            dialog.destroy()
        if remember:
            try:
                set_paste_confirmation_enabled(False)
            except OSError as error:
                self.owner.message(L('Kon de plakvoorkeur niet opslaan: ') + str(error))
        return allowed

    def set_paste_warning(self, enabled):
        """Explicitly toggle the warning via the right-click context menu."""
        try:
            set_paste_confirmation_enabled(enabled)
            return True
        except OSError as error:
            self.owner.message(L('Kon de plakvoorkeur niet opslaan: ') + str(error))
            return False

    def paste(self, *_):
        if self.done: return
        def received(clipboard, text, data):
            if not text or self.done: return
            if self.confirm_clipboard_paste(text):
                clean = text.replace('\x1b[200~', '').replace('\x1b[201~', '')
                self.insert_text(clean, clipboard=True)
                self.term.grab_focus()
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).request_text(received, None)

    def insert_text(self, text, clipboard=False):
        """Insert into the real PTY without changing ordinary keyboard input.

        Side-panel commands are inserted literally and never auto-executed.
        Clipboard content is handed to VTE's paste API, which honors the
        bracketed-paste state announced by the foreground application.
        Bash/Readline in that mode accepts an entire multi-line paste as one
        editable buffer until the user presses Enter. Raw CR injection would
        instead execute each line during paste and can lose later lines.

        For shells/programs that do not enable bracketed paste, normal
        terminal paste semantics apply and newlines MAY execute immediately.
        Default to a confirmation dialog unless the user opts out. The
        right-click context menu can restore the warning at any time.
        """
        if self.done or not isinstance(text, str) or not text:
            return
        if clipboard:
            # Preserve logical newlines, including a trailing newline; VTE
            # handles bracketed mode itself. Never append an extra Enter.
            text = text.replace('\r\n', '\n').replace('\r', '\n')
            self.term.paste_text(text)
        else:
            self.term.feed_child(text.encode('utf-8'))

    def save(self, *_):
        path = self.owner.choose(L('Terminaluitvoer opslaan (kan persoonlijke gegevens bevatten)'), save=True)
        if not path: return
        try:
            stream = Gio.File.new_for_path(path).create(Gio.FileCreateFlags.PRIVATE, None)
            try:
                self.term.write_contents_sync(stream, Vte.WriteFlags.DEFAULT, None)
            finally:
                stream.close(None)
        except (OSError, GLib.Error) as e: self.owner.message(str(e))

    def mouse(self, widget, event):
        if event.type != Gdk.EventType.BUTTON_PRESS or event.button != 3:
            return False
        # Mouse selection and dragging are handled by VTE itself.
        menu = Gtk.Menu()
        def item(label, callback, enabled=True):
            entry = Gtk.MenuItem(label=label)
            entry.set_sensitive(enabled)
            entry.connect('activate', callback)
            menu.append(entry)
        item(L('Kopiëren (Ctrl+Shift+C)'), lambda *_: widget.copy_clipboard_format(Vte.Format.TEXT),
             widget.get_has_selection())
        item(L('Plakken (Ctrl+Shift+V)'), self.paste, not self.done)
        paste_warning_item = Gtk.CheckMenuItem(label=L('Plakwaarschuwing tonen'))
        paste_warning_item.set_active(paste_confirmation_enabled())
        def warning_toggled(entry):
            requested = entry.get_active()
            if not self.set_paste_warning(requested):
                entry.handler_block(handler_id)
                entry.set_active(not requested)
                entry.handler_unblock(handler_id)
        handler_id = paste_warning_item.connect('toggled', warning_toggled)
        menu.append(paste_warning_item)
        item(L('Alles selecteren'), lambda *_: widget.select_all())
        menu.show_all()
        menu.popup_at_pointer(event)
        return True

    def key(self, widget, event):
        if event.state & Gdk.ModifierType.CONTROL_MASK and event.state & Gdk.ModifierType.SHIFT_MASK:
            key = (Gdk.keyval_name(event.keyval) or '').lower()
            if key == 'c': widget.copy_clipboard_format(Vte.Format.TEXT); return True
            if key == 'v': self.paste(); return True
            if key == 'a': widget.select_all(); return True
        return False
