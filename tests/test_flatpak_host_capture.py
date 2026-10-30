"""Regression tests for host stdout capture from a GTK Flatpak without a console.

The test executes /bin/sh locally as a stand-in for flatpak-spawn --host.
It verifies shared-file output is read even though the launcher stdout is null.
No real Flatpak service or external network is needed.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import host_bridge as hb


class FlatpakHostCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cache = str(Path(self.temp.name) / 'cache')
        self.fake_flatpak = patch.object(hb, 'in_flatpak', return_value=True)
        self.fake_host_argv = patch.object(hb, 'host_argv', side_effect=lambda argv: [x for x in argv if not x.startswith('--forward-fd=')])
        self.fake_env = patch.dict(os.environ, {'XDG_CACHE_HOME': self.cache})
        self.fake_flatpak.start()
        self.fake_host_argv.start()
        self.fake_env.start()

    def tearDown(self):
        self.fake_env.stop()
        self.fake_host_argv.stop()
        self.fake_flatpak.stop()
        self.temp.cleanup()

    def test_stdout_capture_and_cleanup(self):
        with patch.object(hb.subprocess, 'run', wraps=subprocess.run) as run:
            result = hb.run_host(['/bin/sh', '-c', 'printf "Bazzite\\n"'],
                                 capture_output=True, check=True, text=True, timeout=5)
            self.assertEqual(run.call_args.kwargs['stdout'], subprocess.DEVNULL)
            self.assertEqual(len(run.call_args.kwargs['pass_fds']), 2)
        self.assertEqual(result.stdout, 'Bazzite\n')
        self.assertEqual(result.stderr, '')
        self.assertFalse(Path(self.cache).exists(), 'Capture must not need a shared cache folder')

    def test_stdout_pipe_and_checked_host_path(self):
        result = hb.run_host(['/bin/sh', '-c', 'command -v ls'],
                             stdout=subprocess.PIPE, text=True, timeout=5, check=True)
        self.assertTrue(result.stdout.strip().endswith('/ls'))

    def test_bash_inventory_is_captured(self):
        from command_discovery import installed_commands
        inventory = installed_commands()
        self.assertTrue(any(cmd.name == 'ls' for cmd in inventory))
        self.assertTrue(any(cmd.name == 'cd' and cmd.kind == 'bash builtin' for cmd in inventory))

    def test_binary_file_capture_and_combined_stderr(self):
        with tempfile.TemporaryFile() as output:
            result = hb.run_host(['/bin/sh', '-c', 'printf out; printf err >&2'],
                                 stdout=output, stderr=subprocess.STDOUT,
                                 check=True, timeout=5)
            output.seek(0)
            self.assertEqual(output.read(), b'outerr')
            self.assertIsNone(result.stdout)

    def test_nonzero_exit_code_and_check(self):
        command = ['/bin/sh', '-c', 'printf fail; exit 17']
        result = hb.run_host(command, capture_output=True, text=True, timeout=5)
        self.assertEqual((result.returncode, result.stdout), (17, 'fail'))
        with self.assertRaises(subprocess.CalledProcessError) as error:
            hb.run_host(command, capture_output=True, text=True, timeout=5, check=True)
        self.assertEqual(error.exception.returncode, 17)

    def test_user_supplied_argument_is_never_evaluated(self):
        tricky = 'x; touch /tmp/not-supposed-to-be-executed'
        result = hb.run_host(['/bin/printf', '%s', tricky],
                             capture_output=True, text=True, timeout=5, check=True)
        self.assertEqual(result.stdout, tricky)


if __name__ == '__main__':
    unittest.main()
