"""Exercises the host-owned PTY bridge using two local processes (no Flatpak daemon)."""
import fcntl
import os
import pty
import select
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import host_bridge as hb

ROOT = Path(__file__).resolve().parents[1]


class HostPythonPtyTests(unittest.TestCase):
    def test_selects_self_contained_host_python_bridge_before_script(self):
        with patch.object(hb, 'in_flatpak', return_value=True), \
             patch.object(hb.shutil, 'which', side_effect=lambda x: '/usr/bin/'+x if x in ('flatpak-spawn', 'python3') else None), \
             patch.object(hb, 'host_which', side_effect=lambda x: '/usr/bin/python3' if x == 'python3' else None):
            argv = hb.host_shell_argv('/bin/bash', '/tmp')
        self.assertEqual(argv[-4:], ['--relay', '/usr/bin/python3', '/bin/bash', '/tmp'])
        self.assertEqual(Path(argv[2]).name, 'host_pty_bridge.py')
        self.assertFalse(any('--forward-fd=' in s for s in argv))

    def test_can_still_use_script_on_host_without_python(self):
        with patch.object(hb, 'in_flatpak', return_value=True), \
             patch.object(hb.shutil, 'which', side_effect=lambda x: '/usr/bin/flatpak-spawn' if x == 'flatpak-spawn' else None), \
             patch.object(hb, 'host_which', side_effect=lambda x: '/usr/bin/script' if x == 'script' else None):
            argv = hb.host_shell_argv('/bin/bash', '/tmp')
        self.assertEqual(argv[:3], ['flatpak-spawn','--host','--directory=/tmp'])
        self.assertEqual(argv[-1], '/dev/null')

    def test_bracketed_multiline_paste_over_host_pty_relay(self):
        """Host PTY carries Readline mode + pasted block without early execution.

        VTE itself supplies the paste wrappers only after the shell enables
        bracketed paste; this integration test drives the same PTY bytes and
        verifies that the relay keeps the entire block intact.
        """
        master, slave = pty.openpty()
        runner = subprocess.Popen([sys.executable, '-u', str(ROOT/'host_pty_bridge.py'),
                                   '--relay', sys.executable, '/bin/bash', '/tmp', '--local-test'],
                                  stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        def collect(seconds=0.7):
            deadline=time.monotonic()+seconds
            buf=b''
            while time.monotonic()<deadline:
                ready,_,_=select.select([master], [], [], min(0.08, max(0.0,deadline-time.monotonic())))
                if ready:
                    try: buf+=os.read(master, 65536)
                    except OSError: break
            return buf
        try:
            # The host's interactive shell should enable DECSET bracketed paste.
            startup=collect(1.5)
            if b'\x1b[?2004h' not in startup:
                self.skipTest('Bash host configuration disabled bracketed paste')
            os.write(master,b'\x1b[200~echo ULT_PASTE_A\necho ULT_PASTE_B\n\x1b[201~')
            before=collect(0.6)
            self.assertNotIn(b'\r\nULT_PASTE_A\r\n',before)
            self.assertNotIn(b'\r\nULT_PASTE_B\r\n',before)
            os.write(master,b'\r')
            after=collect(1.2)
            self.assertIn(b'ULT_PASTE_A\r\n',after)
            self.assertIn(b'ULT_PASTE_B\r\n',after)
        finally:
            if runner.poll() is None:
                runner.kill(); runner.wait(timeout=3)
            os.close(master)

    def test_pty_shell_job_control_and_resize_without_util_linux(self):
        master, slave = pty.openpty()
        runner = subprocess.Popen([sys.executable, '-u', str(ROOT/'host_pty_bridge.py'),
                                   '--relay', sys.executable, '/bin/bash', '/tmp', '--local-test'],
                                  stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        def gather(needle, timeout=3):
            buf=b''; deadline=time.monotonic()+timeout
            while time.monotonic()<deadline and needle not in buf:
                ready,_,_=select.select([master], [], [], 0.1)
                if ready:
                    try: buf += os.read(master, 65536)
                    except OSError: break
            return buf
        try:
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH', 31, 102, 0, 0))
            gather(b'$ ', 2)
            os.write(master, b'tty; echo ready; stty size\n')
            output = gather(b'31 102', 3)
            self.assertIn(b'/dev/pts/', output)
            self.assertIn(b'31 102', output)
            os.write(master, b'sleep 20\n')
            time.sleep(0.3)
            os.write(master, b'\x1a')
            output = gather(b'Stopped', 2)
            self.assertIn(b'Stopped', output)
            os.write(master, b'jobs\n')
            self.assertIn(b'Stopped', gather(b'Stopped', 2))
            os.write(master, b'fg\n')
            time.sleep(0.3)
            os.write(master, b'\x03')
            gather(b'$ ', 2)
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH', 52, 143, 0, 0))
            time.sleep(0.4)
            os.write(master, b'stty size\n')
            self.assertIn(b'52 143', gather(b'52 143', 2))
            os.write(master, b'exit\n')
            runner.wait(timeout=3)
            self.assertEqual(runner.returncode, 0)
        finally:
            if runner.poll() is None:
                runner.kill(); runner.wait(timeout=3)
            os.close(master)


if __name__=='__main__':
    unittest.main()
