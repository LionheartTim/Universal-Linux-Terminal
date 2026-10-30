"""Host-owned PTY path tests: prevent the Flatpak namespace ttyname regression."""
import unittest
from pathlib import Path
from unittest.mock import patch
import host_bridge as hb

ROOT = Path(__file__).resolve().parents[1]


def mocked_which(name):
    return {'flatpak-spawn': '/usr/bin/flatpak-spawn'}.get(name)


class HostPtyBundleTests(unittest.TestCase):
    def test_manifest_avoids_bundling_a_sandbox_pty_helper(self):
        manifest = (ROOT / 'io.github.LionheartTim.UniversalLinuxTerminal.yml').read_text()
        self.assertNotIn('  - name: host-spawn\n', manifest)
        self.assertIn('--talk-name=org.freedesktop.Flatpak', manifest)
        self.assertNotIn('--device=all', manifest)

    def test_pty_created_on_host_through_util_linux_script(self):
        with patch.object(hb, 'in_flatpak', return_value=True), \
             patch.object(hb.shutil, 'which', side_effect=mocked_which), \
             patch.object(hb, 'host_which', side_effect=lambda n: '/usr/bin/script' if n == 'script' else None):
            argv = hb.host_shell_argv('/bin/bash', '/tmp')
            self.assertEqual(argv, ['flatpak-spawn', '--host', '--directory=/tmp',
                                    '--env=TERM=xterm-256color', '/usr/bin/script',
                                    '--quiet', '--return', '--flush', '--command',
                                    'exec /bin/bash -i', '/dev/null'])
            self.assertEqual(hb.host_argv(['lsblk', '-f']),
                             ['flatpak-spawn', '--host', '--directory=/', 'lsblk', '-f'])

    def test_shell_path_is_quoted_in_script_command(self):
        with patch.object(hb, 'in_flatpak', return_value=True), \
             patch.object(hb.shutil, 'which', side_effect=mocked_which), \
             patch.object(hb, 'host_which', side_effect=lambda n: '/usr/bin/script' if n == 'script' else None):
            argv = hb.host_shell_argv('/home/a; echo bad/bash', '/tmp')
        self.assertEqual(argv[-2], "exec '/home/a; echo bad/bash' -i")

    def test_spaces_in_directory_do_not_get_interpolated(self):
        import tempfile
        with tempfile.TemporaryDirectory(prefix='ULT two words ') as cwd:
            with patch.object(hb, 'in_flatpak', return_value=True), \
                 patch.object(hb.shutil, 'which', side_effect=mocked_which), \
                 patch.object(hb, 'host_which', side_effect=lambda n: '/usr/bin/script' if n == 'script' else None):
                argv = hb.host_shell_argv('/bin/bash', cwd)
            self.assertEqual(argv[2], '--directory=' + cwd)
            self.assertEqual(argv[-2:], ['exec /bin/bash -i', '/dev/null'])

    def test_false_negative_preflights_still_attempt_host_python(self):
        # The GUI can lose stdin before the first host probe.  Since the host
        # shell runs asynchronously in VTE, don't claim a missing host package
        # on the strength of such an unreliable preflight.
        with patch.object(hb, 'in_flatpak', return_value=True), \
             patch.object(hb.shutil, 'which', side_effect=mocked_which), \
             patch.object(hb, 'host_executable', return_value=None):
            argv = hb.host_shell_argv('/bin/bash', '/tmp')
        self.assertEqual(argv[-4:], ['--relay', '/usr/bin/python3', '/bin/bash', '/tmp'])

    def test_regular_source_shell_untouched(self):
        with patch.object(hb, 'in_flatpak', return_value=False):
            self.assertEqual(hb.host_shell_argv('/bin/bash', '/tmp'), ['/bin/bash', '-i'])


if __name__ == '__main__':
    unittest.main()
