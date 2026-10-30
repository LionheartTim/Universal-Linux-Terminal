"""Regression for desktop launcher with no inherited fd 0.

`flatpak-spawn --host` can fail before reaching even `test -x` if a GTK
application is launched without the controlling stdin provided by Konsole.
"""
import subprocess
import unittest
from unittest.mock import patch
import host_bridge as hb


class FlatpakGuiStdinTests(unittest.TestCase):
    def test_flatpak_host_probes_get_valid_stdin_when_not_explicit(self):
        with patch.object(hb, 'in_flatpak', return_value=True), \
             patch.object(hb, 'shutil') as shutil, \
             patch.object(hb.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as runner:
            shutil.which.return_value = '/usr/bin/flatpak-spawn'
            hb.run_host(['/bin/true'], stdout=subprocess.DEVNULL)
            self.assertEqual(runner.call_args.kwargs['stdin'], subprocess.DEVNULL)

    def test_explicit_input_and_stdin_are_respected(self):
        with patch.object(hb, 'in_flatpak', return_value=True), \
             patch.object(hb.shutil, 'which', return_value='/usr/bin/flatpak-spawn'), \
             patch.object(hb.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as runner:
            hb.run_host(['/bin/cat'], input=b'stuff')
            self.assertNotIn('stdin', runner.call_args.kwargs)
            hb.run_host(['/bin/cat'], stdin=subprocess.PIPE)
            self.assertEqual(runner.call_args.kwargs['stdin'], subprocess.PIPE)

    def test_regular_source_launch_does_not_force_stdin(self):
        with patch.object(hb, 'in_flatpak', return_value=False), \
             patch.object(hb.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as runner:
            hb.run_host(['/bin/true'])
            self.assertNotIn('stdin', runner.call_args.kwargs)

    def test_failed_gui_preflight_does_not_claim_host_python_missing(self):
        with patch.object(hb, 'in_flatpak', return_value=True), \
             patch.object(hb.shutil, 'which', side_effect=lambda name: '/usr/bin/' + name if name in ('python3', 'flatpak-spawn') else None), \
             patch.object(hb, 'host_executable', return_value=None):
            argv = hb.host_shell_argv('/bin/bash', '/tmp')
        self.assertEqual(argv[-4:], ['--relay', '/usr/bin/python3', '/bin/bash', '/tmp'])


if __name__ == '__main__':
    unittest.main()
