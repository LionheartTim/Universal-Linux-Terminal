"""User regression: Bazzite GTK Flatpak must not replace the host shell with sh."""
import os
import pty
import select
import time
import errno
import fcntl
import struct
import termios
import pwd
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import host_bridge
import host_pty_bridge
from core import user_shell

class HostLoginShellTests(unittest.TestCase):
    def test_sandbox_probes_do_not_force_bin_sh(self):
        # Simulate GUI case: --host probes cannot be read from stdout.
        with patch.object(host_bridge, 'in_flatpak', return_value=True), \
             patch.object(host_bridge, 'run_host', side_effect=OSError('GUI probe failed')):
            self.assertEqual(host_bridge.account_shell(), host_bridge.HOST_ACCOUNT_SHELL)

    def test_host_getent_result_is_used_when_available(self):
        response = subprocess.CompletedProcess([], 0,
             'tim:x:1000:1000:Tim:/var/home/tim:/bin/bash\n', '')
        with patch.object(host_bridge, 'in_flatpak', return_value=True), \
             patch.object(host_bridge, 'run_host', return_value=response):
            self.assertEqual(host_bridge.account_shell(), '/bin/bash')

    def test_core_shell_is_deferred_to_host(self):
        with patch('core.in_flatpak', return_value=True), \
             patch('core.account_shell', return_value=host_bridge.HOST_ACCOUNT_SHELL):
            self.assertEqual(user_shell(), host_bridge.HOST_ACCOUNT_SHELL)

    def test_host_reads_actual_login_shell(self):
        with patch.object(host_pty_bridge.pwd, 'getpwuid') as lookup, \
             patch.object(host_pty_bridge.os, 'getuid', return_value=1000), \
             patch.object(host_pty_bridge.os, 'access', return_value=True):
            lookup.return_value = type('User', (), {'pw_shell':'/usr/bin/fish'})()
            self.assertEqual(host_pty_bridge._resolve_host_shell(host_bridge.HOST_ACCOUNT_SHELL), '/usr/bin/fish')

    def test_host_fallback_when_login_shell_is_invalid(self):
        with patch.object(host_pty_bridge.pwd, 'getpwuid') as lookup, \
             patch.object(host_pty_bridge.shutil, 'which', side_effect=lambda x: '/bin/bash' if x == 'bash' else None), \
             patch.object(host_pty_bridge.os, 'access', side_effect=lambda path, mode: path == '/bin/bash'), \
             patch.dict(host_pty_bridge.os.environ, {'SHELL':''}):
            lookup.return_value = type('User', (), {'pw_shell':'/bin/false'})()
            self.assertEqual(host_pty_bridge._resolve_host_shell(host_bridge.HOST_ACCOUNT_SHELL), '/bin/bash')

    def test_explicit_unsupported_path_is_rejected(self):
        with self.assertRaises(FileNotFoundError):
            host_pty_bridge._resolve_host_shell('/a/nonexistent-shell')

    def test_script_fallback_resolves_host_user_shell(self):
        with patch.object(host_bridge, 'in_flatpak', return_value=True), \
             patch.object(host_bridge.shutil, 'which', side_effect=lambda x: '/usr/bin/flatpak-spawn' if x == 'flatpak-spawn' else None), \
             patch.object(host_bridge, 'host_executable', side_effect=lambda x: '/usr/bin/script' if x == 'script' else None):
            argv = host_bridge.host_shell_argv(host_bridge.HOST_ACCOUNT_SHELL, '/tmp')
        self.assertEqual(argv[-1], '/dev/null')
        self.assertIn('getent passwd', argv[-2])
        self.assertIn('exec "$login_shell" -i', argv[-2])

    def test_local_pty_with_deferred_host_account_shell(self):
        # Same two-stage PTY protocol as Flatpak, executed locally to validate
        # user shell resolution + controlling tty + interactive input.
        master, slave = pty.openpty()
        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 100, 0, 0))
        bridge_path = str(Path(host_pty_bridge.__file__))
        proc = subprocess.Popen([sys.executable, '-u', bridge_path, '--relay',
                                 sys.executable, host_bridge.HOST_ACCOUNT_SHELL,
                                 '/tmp', '--local-test'],
                                stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        try:
            # Give the startup relay time to prepare raw VTE-side input.
            ready, _, _ = select.select([master], [], [], 1.0)
            if ready:
                os.read(master, 16384)
            os.write(master, b'printf "PTY_OK\\n"; tty; ps -p $$ -o comm=; exit\n')
            output = b''
            end = time.monotonic() + 5
            while time.monotonic() < end:
                ready, _, _ = select.select([master], [], [], 0.2)
                if ready:
                    try: output += os.read(master, 16384)
                    except OSError as exc:
                        if exc.errno != errno.EIO: raise
                        break
                if proc.poll() is not None and not ready:
                    break
            self.assertIn(b'PTY_OK', output)
            # Need the shell to respond with the real controlling tty.
            self.assertIn(b'/dev/pts/', output)
            self.assertIn(b'bash', output)
            self.assertEqual(proc.wait(timeout=3), 0)
        finally:
            if proc.poll() is None:
                proc.kill(); proc.wait(timeout=3)
            os.close(master)

    def test_real_host_preference_when_available(self):
        real = pwd.getpwuid(os.getuid()).pw_shell
        if not real or not Path(real).exists():
            self.skipTest('no configured login shell in test host')
        self.assertEqual(host_pty_bridge._resolve_host_shell(host_bridge.HOST_ACCOUNT_SHELL), real)

if __name__ == '__main__':
    unittest.main()
