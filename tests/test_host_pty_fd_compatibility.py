"""Regression for `tty: ttyname error: No such device` from host-spawn."""
import unittest
from pathlib import Path
from unittest.mock import patch
import host_bridge as hb

ROOT = Path(__file__).resolve().parents[1]

class HostPtyFdCompatibilityTests(unittest.TestCase):
    def test_host_shell_does_not_pass_sandbox_pty_slave_to_host(self):
        with patch.object(hb, 'in_flatpak', return_value=True), \
             patch.object(hb.shutil, 'which', return_value='/usr/bin/flatpak-spawn'), \
             patch.object(hb, 'host_which', side_effect=lambda n: '/usr/bin/script' if n == 'script' else None):
            cmd = hb.host_shell_argv('/bin/bash', '/tmp')
        self.assertEqual(cmd[:2], ['flatpak-spawn', '--host'])
        self.assertIn('/usr/bin/script', cmd)
        self.assertEqual(cmd[-1], '/dev/null')
        self.assertFalse(any('--forward-fd=' in arg for arg in cmd))
        self.assertNotIn('-pty', cmd)

    def test_unpacked_source_keeps_shell_unchanged(self):
        with patch.object(hb, 'in_flatpak', return_value=False):
            self.assertEqual(hb.host_shell_argv('/bin/bash', '/tmp'), ['/bin/bash', '-i'])

    def test_vte_gnutls_stays_enabled(self):
        manifest=(ROOT/'io.github.LionheartTim.UniversalLinuxTerminal.yml').read_text()
        vte=manifest.split('  - name: vte\n', 1)[1].split('  - name:', 1)[0]
        self.assertIn('-Dgnutls=true', vte)

if __name__=='__main__':
    unittest.main()
