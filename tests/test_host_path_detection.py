"""Reproduce Bazzite: host `command -v python3` prints a valid path,
while the Flatpak application's captured output from a host probe is empty.
"""
import subprocess
import unittest
from unittest.mock import patch
import host_bridge as hb


class HostPathDetectionTests(unittest.TestCase):
    def test_host_python_found_by_exit_status_when_stdout_capture_is_empty(self):
        calls=[]
        def fake_host_run(argv, **kw):
            calls.append((argv,kw))
            # Captured stdout from host command discovery is unexpectedly empty.
            if 'command -v' in ' '.join(argv):
                return subprocess.CompletedProcess(argv,0,'','')
            if argv[-1] == '/usr/bin/python3':
                return subprocess.CompletedProcess(argv,0)
            return subprocess.CompletedProcess(argv,1)
        with patch.object(hb,'in_flatpak',return_value=True), \
             patch.object(hb.shutil,'which', side_effect=lambda x: '/usr/bin/'+x if x in ('python3','flatpak-spawn') else None), \
             patch.object(hb,'run_host', side_effect=fake_host_run):
            self.assertEqual(hb.host_executable('python3'),'/usr/bin/python3')
            args=hb.host_shell_argv('/bin/bash','/tmp')
        self.assertEqual(args[-4:], ['--relay','/usr/bin/python3','/bin/bash','/tmp'])
        self.assertFalse(any(a[1].get('capture_output') for a in calls))

    def test_fallback_to_host_shell_without_capture(self):
        def fake_host_run(argv, **kw):
            return subprocess.CompletedProcess(argv,0 if argv[-1]=='/usr/bin/bash' else 1,'','')
        with patch.object(hb,'in_flatpak',return_value=True), \
             patch.object(hb,'run_host', side_effect=fake_host_run), \
             patch.object(hb,'host_which', return_value=None):
            self.assertEqual(hb.host_executable('bash'),'/usr/bin/bash')
            self.assertEqual(hb.account_shell(),hb.HOST_ACCOUNT_SHELL)

    def test_unsupported_or_unverified_binary_is_not_assumed_present(self):
        def fail_run(argv, **kw):
            return subprocess.CompletedProcess(argv,1,'','')
        with patch.object(hb,'in_flatpak',return_value=True), \
             patch.object(hb,'run_host', side_effect=fail_run), \
             patch.object(hb,'host_which', return_value=None):
            self.assertIsNone(hb.host_executable('python3'))
            self.assertIsNone(hb.host_executable('script'))
            self.assertIsNone(hb.host_executable('../python3'))

if __name__ == '__main__':
    unittest.main()
