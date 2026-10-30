"""Real host-shell launch should not be blocked by a separate false-negative probe."""
import unittest
from pathlib import Path
from unittest.mock import patch
import host_bridge as hb

ROOT = Path(__file__).resolve().parents[1]


class HostStartWithoutProbeTests(unittest.TestCase):
    def test_gui_does_not_gate_real_host_shell_on_preflight(self):
        source = (ROOT / 'app.py').read_text()
        self.assertNotIn('self._host_probe = inspect_host_access()', source)
        self.assertNotIn('if not self._host_bridge_ok:', source)
        self.assertIn('self.shell()\n', source)
        self.assertIn('flatpak-spawn --host', source)

    def test_real_host_shell_is_always_the_command_in_flatpak(self):
        with patch.object(hb, 'in_flatpak', return_value=True), \
             patch.object(hb.shutil, 'which', return_value='/usr/bin/flatpak-spawn'), \
             patch.object(hb, 'host_which', side_effect=lambda n: '/usr/bin/script' if n == 'script' else None):
            command = hb.host_shell_argv('/bin/bash', '/tmp')
        self.assertEqual(command[:2], ['flatpak-spawn', '--host'])
        self.assertEqual(command[-2:], ['exec /bin/bash -i', '/dev/null'])

    def test_missing_flatpak_spawn_fails_closed(self):
        with patch.object(hb, 'in_flatpak', return_value=True), \
             patch.object(hb.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'flatpak-spawn is missing'):
                hb.host_shell_argv('/bin/bash', '/tmp')

    def test_error_label_is_shown_when_host_shell_ends(self):
        source = (ROOT / 'terminal.py').read_text()
        self.assertIn('self.label.get_parent() is None', source)
        self.assertIn('self.label.show()', source)

if __name__ == '__main__':
    unittest.main()
