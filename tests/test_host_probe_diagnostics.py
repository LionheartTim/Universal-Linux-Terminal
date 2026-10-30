"""Regression coverage for real Flatpak host-probe errors and safe fallback."""
import subprocess
import unittest
from unittest.mock import patch
import host_bridge as hb


class HostProbeDiagnosticsTests(unittest.TestCase):
    def test_diagnostic_script_and_host_permissions_exist(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        script = (root / 'flatpak/diagnose-host.sh').read_text()
        self.assertIn('flatpak info --show-permissions', script)
        self.assertIn('--command=flatpak-spawn', script)
        self.assertIn('--host /bin/true', script)
        self.assertIn('--talk-name=org.freedesktop.Flatpak',
                      (root / 'io.github.LionheartTim.UniversalLinuxTerminal.yml').read_text())

    def test_source_version_never_requires_host_bridge(self):
        with patch.object(hb, 'in_flatpak', return_value=False):
            self.assertTrue(hb.inspect_host_access().ok)

    def test_missing_spawn_gives_specific_reason(self):
        with patch.object(hb, 'in_flatpak', return_value=True), \
             patch.object(hb.shutil, 'which', return_value=None):
            status = hb.inspect_host_access()
        self.assertFalse(status.ok)
        self.assertIn('flatpak-spawn is not available', status.detail)

    def test_permission_error_is_preserved_in_ui_diagnostic(self):
        error = 'GDBus.Error:org.freedesktop.DBus.Error.AccessDenied: Permission denied'
        with patch.object(hb, 'in_flatpak', return_value=True), \
             patch.object(hb.shutil, 'which', return_value='/usr/bin/flatpak-spawn'), \
             patch.object(hb, 'run_host', return_value=subprocess.CompletedProcess([], 1, '', error)) as run:
            status = hb.inspect_host_access()
        self.assertFalse(status.ok)
        self.assertIn('AccessDenied', status.detail)
        self.assertIn('exit code 1', status.detail)
        self.assertEqual(run.call_args.args[0], ['/bin/true'])
        self.assertTrue(run.call_args.kwargs['capture_output'])
        self.assertFalse(run.call_args.kwargs['check'])

    def test_success(self):
        with patch.object(hb, 'in_flatpak', return_value=True), \
             patch.object(hb.shutil, 'which', return_value='/usr/bin/flatpak-spawn'), \
             patch.object(hb, 'run_host', return_value=subprocess.CompletedProcess([], 0, '', '')):
            self.assertTrue(hb.probe_host())

    def test_timeout_does_not_fall_back_to_sandbox(self):
        with patch.object(hb, 'in_flatpak', return_value=True), \
             patch.object(hb.shutil, 'which', return_value='/usr/bin/flatpak-spawn'), \
             patch.object(hb, 'run_host', side_effect=subprocess.TimeoutExpired(['flatpak-spawn'], 8)):
            status = hb.inspect_host_access()
        self.assertFalse(status.ok)
        self.assertIn('did not respond', status.detail)

    def test_exception_does_not_fall_back_to_sandbox(self):
        with patch.object(hb, 'in_flatpak', return_value=True), \
             patch.object(hb.shutil, 'which', return_value='/usr/bin/flatpak-spawn'), \
             patch.object(hb, 'run_host', side_effect=OSError('No session D-Bus')):
            status = hb.inspect_host_access()
        self.assertFalse(status.ok)
        self.assertIn('No session D-Bus', status.detail)


if __name__ == '__main__':
    unittest.main()
