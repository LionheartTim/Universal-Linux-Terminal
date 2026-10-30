"""Flatpak host-shell/package smoke tests, no GUI or Flatpak daemon needed."""
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import host_bridge as hb

ROOT = Path(__file__).resolve().parents[1]
APP_ID = 'io.github.LionheartTim.UniversalLinuxTerminal'


class HostBridgeTests(unittest.TestCase):
    def test_normal_source_exec_unchanged(self):
        with patch.object(hb, 'in_flatpak', return_value=False):
            self.assertEqual(hb.host_argv(['lsblk', '-f']), ['lsblk', '-f'])
            self.assertEqual(hb.host_shell_argv('/bin/bash', '/tmp'), ['/bin/bash', '-i'])

    def test_flatpak_passes_real_host_shell_and_pty(self):
        with patch.object(hb, 'in_flatpak', return_value=True), \
             patch.object(hb.shutil, 'which', return_value='/usr/bin/flatpak-spawn'), \
             patch.object(hb, 'host_which', side_effect=lambda n: '/usr/bin/script' if n == 'script' else None):
            cmd = hb.host_shell_argv('/usr/bin/fish', '/tmp')
            self.assertEqual(cmd[:3], ['flatpak-spawn', '--host', '--directory=/tmp'])
            self.assertEqual(cmd[-2:], ['exec /usr/bin/fish -i', '/dev/null'])
            self.assertFalse(any(part.startswith('--forward-fd=') for part in cmd),
                             'flatpak-spawn automatically forwards fds 0, 1, and 2')
            self.assertEqual(hb.host_argv(['lsblk', '-f']),
                             ['flatpak-spawn', '--host', '--directory=/', 'lsblk', '-f'])

    def test_no_shell_injection_in_which(self):
        hb.host_which.cache_clear()
        try:
            with patch.object(hb, 'in_flatpak', return_value=True), \
                 patch.object(hb, 'run_host', return_value=subprocess.CompletedProcess([], 0, '/bin/lsblk\n', '')) as run:
                self.assertEqual(hb.host_which('lsblk; echo UNSAFE'), '/bin/lsblk')
                self.assertEqual(run.call_args.args[0][-1], 'lsblk; echo UNSAFE')
                self.assertIn('"$1"', run.call_args.args[0][2])
                self.assertIsNone(hb.host_which('../foo'))
        finally:
            hb.host_which.cache_clear()

    def test_discovery_uses_host_inventory_in_flatpak(self):
        from command_discovery import installed_commands
        fake = subprocess.CompletedProcess([], 0, 'lsblk\ncat\npwd\n', '')
        builtin = subprocess.CompletedProcess([], 0, 'pwd\ncd\n', '')
        with patch('command_discovery.in_flatpak', return_value=True), \
             patch('command_discovery.run_host', side_effect=[fake, builtin]) as run:
            inventory = installed_commands()
        self.assertEqual([x.name for x in inventory], ['cat', 'lsblk', 'pwd'])
        self.assertEqual(next(x.kind for x in inventory if x.name == 'pwd'), 'bash builtin')
        self.assertEqual(next(x.location for x in inventory if x.name == 'lsblk'), 'Host PATH')
        self.assertEqual(run.call_count, 2)

    def test_help_of_host_command_does_not_lookup_sandbox_path(self):
        from command_discovery import Executable
        from option_discovery import load_command_info
        # Running a real program is not needed; only the chosen host argv is relevant.
        def write_help(argv, **kw):
            self.assertEqual(argv, ['lsblk', '--help'])
            kw['stdout'].write(b'Usage: lsblk [options]\n  -f, --fs    output filesystem information\n')
            return subprocess.CompletedProcess(argv, 0)
        with patch('option_discovery.in_flatpak', return_value=True), \
             patch('option_discovery.host_which', return_value='/usr/bin/lsblk'), \
             patch('option_discovery.run_host', side_effect=write_help):
            doc = load_command_info(Executable('lsblk', 'executable', 'Host PATH'))
        self.assertTrue(any('-f' in item.names for item in doc.options))

    def test_bad_host_bridge_fails_closed(self):
        with patch.object(hb, 'in_flatpak', return_value=True), \
             patch.object(hb, 'run_host', side_effect=OSError('Denied')):
            self.assertFalse(hb.probe_host())

    def test_host_distro_is_not_runtime(self):
        from distro_support import detect_profile
        host_release = {'ID':'bazzite','ID_LIKE':'fedora', 'PRETTY_NAME':'Bazzite'}
        tools = {'rpm-ostree', 'flatpak'}
        with patch('host_bridge.in_flatpak', return_value=True), \
             patch('host_bridge.host_release', return_value=host_release), \
             patch('host_bridge.host_path_exists', side_effect=lambda p: p=='/run/ostree-booted'), \
             patch('host_bridge.host_which', side_effect=lambda x: '/usr/bin/'+x if x in tools else None):
            profile = detect_profile()
        self.assertEqual(profile.ident, 'bazzite')
        self.assertEqual(profile.backend, 'rpm-ostree')
        self.assertTrue(profile.atomic)
        self.assertFalse(profile.sandbox)


class FlatpakPackageTests(unittest.TestCase):
    def test_manifest_runtime_vte_permissions_and_metadata(self):
        source = (ROOT/(APP_ID+'.yml')).read_text()
        self.assertIn('org.gnome.Platform',source)
        self.assertIn("runtime-version: '50'", source)
        self.assertIn('name: vte', source)
        self.assertIn('-Dgtk3=true', source)
        self.assertIn('--talk-name=org.freedesktop.Flatpak', source)
        self.assertIn('--filesystem=host', source)
        self.assertIn('flatpak/ult-launch',source)
        self.assertIn('flatpak/'+APP_ID+'.desktop',source)
        self.assertTrue((ROOT/'flatpak/ult-launch').stat().st_mode & 0o111)

    def test_vte_dependencies_are_built_inside_flatpak(self):
        # No third-party YAML parser is required to run the release tests.
        import re
        source = (ROOT / (APP_ID + '.yml')).read_text()
        names = re.findall(r'^  - name: (\S+)\s*$', source, re.MULTILINE)
        self.assertEqual(names[:4], ['simdutf', 'fmt', 'fast_float', 'vte'])
        versions = {'simdutf': 'v8.0.0', 'fmt': '12.1.0', 'fast_float': 'v8.2.3'}
        for name, tag in versions.items():
            section = source.split(f'  - name: {name}\n', 1)[1].split('  - name:', 1)[0]
            self.assertRegex(section, r"tag: ['\"]?" + re.escape(tag) + r"['\"]?(?:\n|$)")
        vte = source.split('  - name: vte\n', 1)[1].split('  - name:', 1)[0]
        self.assertIn('--wrap-mode=nofallback', vte)
        self.assertIn('-Dgir=true', vte)
        self.assertIn('-Dgtk3=true', vte)
        self.assertIn('-Dgnutls=true', vte)
        self.assertNotIn('-Dgnutls=false', vte)
        pc_path = ROOT / 'flatpak/fast_float.pc'
        pc = pc_path.read_text()
        self.assertIn('Name: fast_float', pc)
        self.assertIn('Cflags: -I${includedir}', pc)
        self.assertIn('path: flatpak/fast_float.pc', source)

    def test_release_pipeline_exists(self):
        workflow = (ROOT/'.github/workflows/flatpak.yml').read_text()
        self.assertIn('flatpak-builder@v6',workflow)
        self.assertIn('Universal-Linux-Terminal-v1.0.1-x86_64.flatpak',workflow)
        self.assertIn('action-gh-release',workflow)


if __name__ == '__main__':
    unittest.main()
