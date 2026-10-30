"""Regression for Flatpak HostCommand inheriting ULT's sandbox-only cwd.

Real Flatpak portals reject /app/share/universal-linux-terminal as a host
working directory before running the requested command.  This test uses a
local stand-in for flatpak-spawn which reproduces that rejection and checks
both captured output and a normal status-only host command.  The GTK/VTE PTY
and its dedicated shell directory are deliberately not changed.
"""
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

import host_bridge as hb


class FlatpakHostWorkingDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.sandbox_cwd = base / 'sandbox-only' / 'app' / 'share' / 'universal-linux-terminal'
        self.sandbox_cwd.mkdir(parents=True)
        bindir = base / 'bin'
        bindir.mkdir()
        fake = bindir / 'flatpak-spawn'
        fake.write_text(textwrap.dedent('''\
            #!/usr/bin/env python3
            import os
            import sys
            args = sys.argv[1:]
            if not args or args.pop(0) != '--host':
                sys.exit(90)
            directory = None
            while args and args[0].startswith('--'):
                opt = args.pop(0)
                if opt.startswith('--directory='):
                    directory = opt.split('=', 1)[1]
                elif opt.startswith('--forward-fd='):
                    pass  # fds were passed by the caller, as through the real portal
                else:
                    sys.exit(91)
            if directory is None and 'sandbox-only' in os.getcwd():
                print('Portal call failed: Failed to change to directory '
                      '"/app/share/universal-linux-terminal" (No such file or directory)',
                      file=sys.stderr)
                sys.exit(1)
            os.chdir(directory or os.getcwd())
            os.execvp(args[0], args)
        '''))
        fake.chmod(0o755)
        self.env = patch.dict(os.environ, {'PATH': str(bindir) + ':' + os.environ['PATH']})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.flatpak = patch.object(hb, 'in_flatpak', return_value=True)
        self.flatpak.start()
        self.addCleanup(self.flatpak.stop)

    def test_captured_host_output_does_not_inherit_sandbox_app_dir(self):
        result = hb.run_host(['/bin/sh', '-c', 'pwd; printf host-err >&2'],
                             capture_output=True, text=True, check=True,
                             timeout=5, cwd=str(self.sandbox_cwd))
        self.assertEqual(result.stdout.strip(), '/')
        self.assertEqual(result.stderr, 'host-err')

    def test_status_only_host_probe_does_not_inherit_sandbox_app_dir(self):
        result = hb.run_host(['/bin/true'], stdout=subprocess.DEVNULL,
                             stderr=subprocess.PIPE, text=True,
                             timeout=5, cwd=str(self.sandbox_cwd))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')

    def test_direct_host_commands_keep_existing_cwd_outside_flatpak(self):
        with patch.object(hb, 'in_flatpak', return_value=False):
            self.assertEqual(hb.host_argv(['/bin/true']), ['/bin/true'])

    def test_host_pty_launch_still_has_its_own_directory(self):
        source = (Path(__file__).resolve().parents[1] / 'host_pty_bridge.py').read_text()
        self.assertIn("'flatpak-spawn', '--host', '--directory=' + cwd", source)


if __name__ == '__main__':
    unittest.main()
