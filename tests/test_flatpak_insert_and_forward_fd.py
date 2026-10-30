"""Host-output and sidebar insertion regressions without requiring GTK installed."""
import ast
import os
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import host_bridge

ROOT = Path(__file__).resolve().parents[1]

class FdCaptureAndAvailabilityTests(unittest.TestCase):
    def test_fd_forwarded_host_stdout_and_stderr(self):
        with patch.object(host_bridge,'in_flatpak',return_value=True), \
             patch.object(host_bridge,'host_argv',side_effect=lambda a: [x for x in a if not x.startswith('--forward-fd=')]):
            result = host_bridge.run_host(['/bin/sh','-c','printf available; printf problem >&2'],
                                          capture_output=True,text=True,timeout=4,check=True)
        self.assertEqual(result.stdout,'available')
        self.assertEqual(result.stderr,'problem')

    def test_status_only_host_which_fallback(self):
        with patch.object(host_bridge,'in_flatpak',return_value=True), \
             patch.object(host_bridge,'run_host',side_effect=[RuntimeError('capture unavailable'),
                            subprocess.CompletedProcess([],0,None,None)]):
            host_bridge.host_which.cache_clear()
            self.assertEqual(host_bridge.host_which('flatpak'),'flatpak')
            host_bridge.host_which.cache_clear()

    def test_status_only_probe_cannot_claim_missing_command_present(self):
        with patch.object(host_bridge,'in_flatpak',return_value=True), \
             patch.object(host_bridge,'run_host',side_effect=[RuntimeError('capture unavailable'),
                            subprocess.CompletedProcess([],127,None,None)]):
            host_bridge.host_which.cache_clear()
            self.assertIsNone(host_bridge.host_which('not-real-command'))
            host_bridge.host_which.cache_clear()

class TerminalInputTests(unittest.TestCase):
    @staticmethod
    def method(name):
        tree = ast.parse((ROOT/'terminal.py').read_text())
        klass = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='TerminalTab')
        fn = next(n for n in klass.body if isinstance(n,ast.FunctionDef) and n.name==name)
        namespace={'os': os, 'signal': signal, 'in_flatpak': lambda: False}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'<test>', 'exec'),namespace)
        return namespace[name]

    def test_insert_does_not_add_enter_or_bracketed_paste(self):
        data=[]
        terminal=SimpleNamespace(feed_child=data.append, paste_text=lambda *_: self.fail('must not wrap bracketed paste'))
        fake=SimpleNamespace(done=False,term=terminal)
        self.method('insert_text')(fake,'flatpak list --app')
        self.assertEqual(data,[b'flatpak list --app'])

    def test_multiline_clipboard_uses_vte_bracketed_paste_when_enabled(self):
        pasted=[]; typed=[]
        terminal=SimpleNamespace(feed_child=typed.append,paste_text=pasted.append)
        fake=SimpleNamespace(done=False,term=terminal)
        self.method('insert_text')(fake,'printf ONE\nprintf TWO\n',clipboard=True)
        self.assertEqual(pasted,['printf ONE\nprintf TWO\n'])
        self.assertEqual(typed, [], 'clipboard must never send Enter directly')

    def test_windows_clipboard_normalized_without_executing(self):
        pasted=[]; typed=[]
        fake=SimpleNamespace(done=False,term=SimpleNamespace(feed_child=typed.append,paste_text=pasted.append))
        self.method('insert_text')(fake,'echo ONE\r\necho TWO\recho THREE',clipboard=True)
        self.assertEqual(pasted,['echo ONE\necho TWO\necho THREE'])
        self.assertEqual(typed, [])
        # Ordinary sidebar insertion still requires the user to press Enter.
        self.method('insert_text')(fake,'lsblk -f')
        self.assertEqual(typed,[b'lsblk -f'])

    def test_clipboard_unicode_and_last_line_not_automatically_executed(self):
        pasted=[];typed=[]
        fake=SimpleNamespace(done=False,term=SimpleNamespace(feed_child=typed.append,paste_text=pasted.append))
        self.method('insert_text')(fake,'echo café\necho klaar',clipboard=True)
        self.assertEqual(pasted,['echo café\necho klaar'])
        self.assertEqual(typed, [])

    def test_stop_and_interrupt_have_distinct_actions(self):
        source=(ROOT/'terminal.py').read_text()
        self.assertIn("button(L('Stop'), lambda *_: self.owner.closing())",source)
        self.assertIn("button(L('Onderbreek opdracht (Ctrl+C)'), self.interrupt_command)",source)
        method=self.method('interrupt_command')
        data=[];focus=[]
        term=SimpleNamespace(feed_child=data.append,grab_focus=lambda:focus.append(True))
        fake=SimpleNamespace(done=False,pid=123,argv=['bash','-i'],term=term)
        method(fake)
        self.assertEqual(data,[b'\x03'])
        self.assertEqual(len(focus),1)
        fake.done=True
        method(fake)
        self.assertEqual(len(data),1)

    def test_insert_does_not_send_empty_or_when_done(self):
        data=[]
        fake=SimpleNamespace(done=True,term=SimpleNamespace(feed_child=data.append))
        self.method('insert_text')(fake,'lsblk -f')
        fake.done=False
        self.method('insert_text')(fake,'')
        self.assertEqual(data,[])

    def test_app_allows_review_when_flatpak_host_metadata_is_unverified(self):
        source=(ROOT/'app.py').read_text()
        self.assertIn("in_flatpak() and issue.startswith('Ontbrekend hulpmiddel: ')",source)
        self.assertIn('self.run_button.set_sensitive(not issue)',source)
        self.assertIn('tab.insert_text(text)',source)

if __name__=='__main__': unittest.main()
