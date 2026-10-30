"""Run under a real desktop or xvfb-run. Does not modify host packages."""
import sys
import unittest
import time
import shutil
try:
    import gi
    gi.require_version('Gtk','3.0')
    gi.require_version('Vte','2.91')
    from gi.repository import Gtk, GLib, Gio, Vte
    AVAILABLE = Gtk.init_check()[0]
except (ImportError, ValueError):
    AVAILABLE = False

@unittest.skipUnless(AVAILABLE, 'GTK/VTE en een grafische display vereist')
class TerminalIntegration(unittest.TestCase):
    def setUp(self):
        from terminal import TerminalTab
        self.window = Gtk.Window()
        self.tabs = Gtk.Notebook(); self.window.add(self.tabs)
        self.finished = []
        self.tab = TerminalTab(self, [sys.executable,'-c','print("ULT_PTY_OK")'], '/tmp', 'Test', True)
        self.tabs.append_page(self.tab, Gtk.Label(label='Test'))
        self.window.show_all()

    def session_finished(self, tab): self.finished.append(tab)
    def confirm(self, text): return False
    def message(self, text): raise AssertionError(text)

    def wait(self):
        deadline = time.monotonic()+10
        while not self.tab.done and time.monotonic() < deadline:
            while GLib.MainContext.default().iteration(False): pass
            time.sleep(.01)
        self.assertTrue(self.tab.done, 'PTY did not complete')
        self.assertEqual(len(self.finished),1)

    def test_real_pty_and_scrollback(self):
        self.tab.start(); self.wait()
        stream=Gio.MemoryOutputStream.new_resizable()
        self.tab.term.write_contents_sync(stream,Vte.WriteFlags.DEFAULT,None)
        stream.close(None)
        self.assertIn(b'ULT_PTY_OK',stream.steal_as_bytes().get_data())
        from i18n import tr
        self.assertIn(tr('geslaagd'), self.tab.label.get_text())

    def test_interactive_stdin_via_vte(self):
        self.tab.argv = [sys.executable, '-u', '-c',
                         'import sys; print("READY", flush=True); '
                         'print("INPUT=" + sys.stdin.readline().strip(), flush=True)']
        self.tab.start()
        # VTE paste passes input to the actual PTY attached to a child process.
        GLib.timeout_add(250, lambda: (self.tab.insert_text('TEST_INPUT\n'), False)[1])
        self.wait()
        stream = Gio.MemoryOutputStream.new_resizable()
        self.tab.term.write_contents_sync(stream, Vte.WriteFlags.DEFAULT, None)
        stream.close(None)
        self.assertIn(b'INPUT=TEST_INPUT', stream.steal_as_bytes().get_data())

    @unittest.skipUnless(shutil.which('sh'), 'Een POSIX shell is vereist')
    def test_real_shell_keyboard_input_and_selection(self):
        # Same PTY used by manual typing and command helpers. A shell can
        # change directory and return to its prompt without being replaced.
        self.tab.argv = [shutil.which('sh'), '-i']
        self.tab.start()
        def send_when_started():
            if self.tab.done:
                return False
            if self.tab.pid is None:
                return True
            self.tab.insert_text('printf ULT_SHELL_OK')
            self.tab.term.feed_child(b'\r')
            self.tab.insert_text('cd /tmp')
            self.tab.term.feed_child(b'\r')
            self.tab.insert_text('pwd')
            self.tab.term.feed_child(b'\r')
            self.tab.insert_text('exit')
            self.tab.term.feed_child(b'\r')
            return False
        GLib.timeout_add(40, send_when_started)
        self.wait()
        stream = Gio.MemoryOutputStream.new_resizable()
        self.tab.term.write_contents_sync(stream, Vte.WriteFlags.DEFAULT, None)
        stream.close(None)
        result = stream.steal_as_bytes().get_data()
        self.assertIn(b'ULT_SHELL_OK', result)
        self.assertIn(b'/tmp', result)
        self.tab.term.select_all()
        self.assertTrue(self.tab.term.get_has_selection())

    def test_spawn_error_releases_session(self):
        self.tab.argv=['/nonexistent/ult-test-command']
        self.tab.start(); self.wait()
        from i18n import tr
        self.assertIn(tr('Startfout: '), self.tab.label.get_text())

    def test_nonzero_exit_report(self):
        self.tab.argv=[sys.executable,'-c','raise SystemExit(7)']
        self.tab.start(); self.wait()
        self.assertIn('exitcode 7',self.tab.label.get_text())

    def tearDown(self):
        if not self.tab.done: self.tab.finish('test cleanup')
        self.window.destroy()
