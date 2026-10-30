import os
import unittest
from unittest.mock import patch
from core import Command, availability, user_shell

class Portability(unittest.TestCase):
    def test_login_shell_kept(self):
        with patch('core.pwd.getpwuid') as getpw, patch('core.os.access', return_value=True), patch('core.Path.is_file', return_value=True):
            getpw.return_value.pw_shell = '/usr/bin/fish'
            self.assertEqual(user_shell(), '/usr/bin/fish')

    def test_shell_fallback_not_bash_only(self):
        # This verifies fallback without assuming /bin/bash is installed.
        with patch('core.pwd.getpwuid', side_effect=KeyError), patch('core.os.environ', {}), \
             patch('core.shutil.which', side_effect=lambda name: '/usr/bin/sh' if name == 'sh' else None), \
             patch('core.Path.is_file', return_value=True), \
             patch('core.os.access', return_value=True):
            self.assertEqual(user_shell(), '/usr/bin/sh')

    def test_read_only_allowed_in_sandbox(self):
        with patch('core.detect', return_value={'sandbox': True}), patch('core.shutil.which', return_value='/usr/bin/echo'):
            self.assertEqual(availability(Command('Echo',['echo','ok'],'')), '')
            self.assertIn('geblokkeerd', availability(Command('Update',['echo','ok'],'',True)))

if __name__ == '__main__': unittest.main()
