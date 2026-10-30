"""Regression coverage for Flatpak PTY interrupt routing and GUI behavior."""
import ast
import os
import pty
import select
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _interrupt_method():
    source = (ROOT / 'terminal.py').read_text(encoding='utf-8')
    module = ast.parse(source)
    cls = next(node for node in module.body
               if isinstance(node, ast.ClassDef) and node.name == 'TerminalTab')
    method = next(node for node in cls.body
                  if isinstance(node, ast.FunctionDef) and node.name == 'interrupt_command')
    namespace = {'os': os, 'signal': signal, 'in_flatpak': lambda: True}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 '<interrupt_command>', 'exec'), namespace)
    return namespace['interrupt_command'], namespace


class InterruptControlTests(unittest.TestCase):
    def test_flatpak_python_host_bridge_uses_out_of_band_signal(self):
        method, namespace = _interrupt_method()
        events = []
        fake = SimpleNamespace(done=False, pid=123456,
                               argv=['/usr/bin/python3', '-u', '/app/share/host_pty_bridge.py',
                                     '--relay', '/usr/bin/python3', '/bin/bash', '/tmp'],
                               term=SimpleNamespace(feed_child=lambda text: events.append(('char', text)),
                                                    grab_focus=lambda: events.append(('focus',))))
        with patch.object(os, 'kill', side_effect=lambda pid, sig: events.append(('signal', pid, sig))):
            method(fake)
        self.assertEqual(events, [('signal', 123456, signal.SIGUSR1), ('focus',)])

    def test_native_shell_uses_ctrl_c_without_host_signal(self):
        method, namespace = _interrupt_method()
        namespace['in_flatpak'] = lambda: False
        events = []
        fake = SimpleNamespace(done=False, pid=99, argv=['bash','-i'],
                               term=SimpleNamespace(feed_child=lambda data: events.append(('text', data)),
                                                    grab_focus=lambda: events.append(('focus',))))
        with patch.object(os, 'kill', side_effect=AssertionError('must not send signal')):
            method(fake)
        self.assertEqual(events, [('text', b'\x03'), ('focus',)])

    def test_absent_child_does_not_send_signal(self):
        method, namespace = _interrupt_method()
        events = []
        fake = SimpleNamespace(done=True, pid=1234, argv=['host_pty_bridge.py','--relay'],
                               term=SimpleNamespace(feed_child=lambda data: events.append(data),
                                                    grab_focus=lambda: events.append('focus')))
        with patch.object(os, 'kill', side_effect=AssertionError('must not signal exited')):
            method(fake)
        self.assertEqual(events, [])

    def test_host_signal_interrupts_foreground_job_even_with_tty_isig_disabled(self):
        """0x03 may display ^C with ISIG off; explicit host-pgrp SIGINT must work."""
        master, slave = pty.openpty()
        runner = subprocess.Popen([sys.executable, '-u', str(ROOT / 'host_pty_bridge.py'),
                                   '--relay', sys.executable, '/bin/bash', '/tmp', '--local-test'],
                                  stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        def collect(needle=b'', seconds=2.0):
            deadline = time.monotonic() + seconds
            output = bytearray()
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [],
                                            min(0.08, max(0, deadline-time.monotonic())))
                if ready:
                    try:
                        output.extend(os.read(master, 65536))
                    except OSError:
                        break
                    if needle and needle in output:
                        break
            return bytes(output)
        try:
            collect(seconds=1.0)
            # A foreground job after disabling terminal-generated signals.
            os.write(master, b'stty -isig; echo ULT_BEGIN; sleep 15; echo ULT_BAD_END\n')
            self.assertIn(b'ULT_BEGIN\r\n', collect(b'ULT_BEGIN\r\n', 3))
            start = time.monotonic()
            os.kill(runner.pid, signal.SIGUSR1)
            # It must not wait out the 15-second sleep.
            os.write(master, b'echo ULT_POST_INTERRUPT\n')
            output = collect(b'ULT_POST_INTERRUPT\r\n', 4)
            self.assertIn(b'ULT_POST_INTERRUPT\r\n', output)
            self.assertNotIn(b'ULT_BAD_END\r\n', output)
            self.assertLess(time.monotonic() - start, 8)
            os.write(master, b'stty isig; exit\n')
            runner.wait(timeout=5)
        finally:
            if runner.poll() is None:
                runner.kill()
                runner.wait(timeout=4)
            os.close(master)


if __name__ == '__main__':
    unittest.main()
