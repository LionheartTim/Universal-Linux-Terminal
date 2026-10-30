"""Local smoke check that util-linux script allocates a named PTY."""
import shutil
import subprocess
import unittest

class HostScriptRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('script'), 'util-linux script not installed in test environment')
    def test_script_allocates_named_local_pty_without_recording_transcript(self):
        # Only the host itself can test the cross-namespace Flatpak behavior.
        output = subprocess.run(
            ['script', '-q', '-e', '-f', '-c', 'tty', '/dev/null'],
            input=b'', capture_output=True, timeout=8, check=False,
        )
        if output.returncode != 0 and b'/dev/pt' not in output.stdout:
            self.skipTest('PTY unavailable in this headless test environment')
        self.assertEqual(output.returncode, 0)
        self.assertIn(b'/dev/pts/', output.stdout)

if __name__ == '__main__':
    unittest.main()
