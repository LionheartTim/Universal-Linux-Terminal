"""Command descriptions are discovered from the host, not hard-coded per tool."""
import shutil
import subprocess
import unittest
from unittest.mock import patch

from command_discovery import Executable
from command_descriptions import (
    DocumentedDescription, _parse_whatis, _parse_manual_name, _parse_pacman,
    _package_description, discover_description,
)
from option_discovery import load_command_info, format_command_help, CommandHelp
from i18n import tr


class DescriptionTests(unittest.TestCase):
    def test_whatis_looks_up_exact_name(self):
        output = ('usbipd (8) - USB/IP daemon\n'
                  'usbip (8) - manage USB/IP devices over a network\n')
        self.assertEqual(_parse_whatis('usbip', output),
                         'manage USB/IP devices over a network')
        self.assertEqual(_parse_whatis('usbip-other', output), '')
        self.assertEqual(_parse_whatis('usb', output), '')
        self.assertEqual(_parse_whatis('unrelated', 'unrelated (1) - an app\n'), 'an app')

    def test_manual_name_section_without_whatis_index(self):
        man = '''USBIP(8)                     System Administration                   USBIP(8)

NAME
       usbip - manage USB/IP devices over IP networks

SYNOPSIS
       usbip [options] command <args>
'''
        self.assertEqual(_parse_manual_name('usbip', man),
                         'manage USB/IP devices over IP networks')
        self.assertEqual(_parse_manual_name('wrong', man), '')

    def test_source_order_whatis_before_man_or_package(self):
        seen=[]
        def read(argv, timeout=2.5):
            seen.append(argv)
            return 'usbip (8) - manage USB/IP devices' if argv[0]=='whatis' else ''
        with patch('command_descriptions._host_read', side_effect=read):
            found=discover_description('usbip', location='Host PATH')
        self.assertEqual(found,DocumentedDescription('manage USB/IP devices','manual'))
        self.assertEqual(seen, [['whatis','--','usbip']])

    def test_rendered_man_page_fallback(self):
        seen=[]
        def read(argv, timeout=2.5):
            seen.append(argv)
            if argv[:3] == ['man', '-P', 'cat']:
                return 'NAME\n usbip - a USB-over-IP tool\n\nSYNOPSIS\n usbip [OPTIONS]\n'
            return ''
        with patch('command_descriptions._host_read', side_effect=read):
            found=discover_description('usbip',location='Host PATH')
        self.assertEqual(found.text,'a USB-over-IP tool')
        self.assertEqual(found.source,'manual')
        self.assertEqual(len(seen),3)

    def test_fedora_rpm_package_fallback_is_labeled(self):
        def read(argv,timeout=2.5):
            if argv[0]=='rpm':
                return ('USB/IP allows USB devices to be shared over a network.\n'
                        'A client can attach remote devices.\n') if any('%{DESCRIPTION}' in arg for arg in argv) else 'USB/IP user-space\n'
            return ''
        with patch('command_descriptions._host_read', side_effect=read), \
             patch('command_descriptions.host_which', return_value='/usr/bin/usbip'):
            found=discover_description('usbip', location='Host PATH')
        self.assertIn('allows USB devices to be shared',found.text)
        self.assertEqual(found.source,'package')
        formatted=format_command_help('usbip',CommandHelp(found.text,'Usage: usbip [options]',(),found.source),
                                       translate=lambda s:tr(s,'nl'))
        self.assertIn('Pakketbeschrijving:\nUSB/IP allows',formatted)
        self.assertIn('Gebruik:',formatted)

    def test_debian_package_description_fallback(self):
        seen=[]
        def read(argv,timeout=2.5):
            seen.append(argv)
            if argv[0]=='dpkg-query' and argv[1]=='-S':
                return 'usbip: /usr/bin/usbip\n'
            if argv[0]=='dpkg-query' and argv[1]=='-W':
                return 'USB/IP user-space utilities\n USB/IP permits sharing devices over a network.\n'
            return ''
        with patch('command_descriptions._host_read',side_effect=read), \
             patch('command_descriptions.host_which',return_value='/usr/bin/usbip'):
            found=discover_description('usbip',location='Host PATH')
        self.assertEqual(found.source,'package')
        self.assertIn(['dpkg-query','-W','-f=${Description}\n','usbip'],seen)

    def test_arch_package_description_fallback(self):
        def read(argv,timeout=2.5):
            if argv[0]=='pacman':
                return 'Name            : usbip\nDescription     : userspace USB/IP tools\n'
            return ''
        with patch('command_descriptions._host_read',side_effect=read), \
             patch('command_descriptions.host_which',return_value='/usr/bin/usbip'):
            found=discover_description('usbip',location='Host PATH')
        self.assertEqual(found.text,'userspace USB/IP tools')
        self.assertEqual(_parse_pacman('Description : userspace USB/IP tools'),
                         'userspace USB/IP tools')

    def test_no_invented_description_and_skip_builtins(self):
        with patch('command_descriptions._host_read',return_value=''), \
             patch('command_descriptions.host_which',return_value=None):
            self.assertIsNone(discover_description('usbip',location='Host PATH'))
            self.assertIsNone(discover_description('cd',kind='bash builtin',location='Bash'))
        empty=format_command_help('usbip',CommandHelp('', 'Usage: usbip',()))
        self.assertIn('No description found in installed help',empty)
        self.assertIn('Usage:\nusbip',empty)

    def test_help_summary_does_not_trigger_fallback(self):
        target=Executable('lsblk','executable',shutil.which('lsblk') or '/usr/bin/lsblk')
        with patch('option_discovery.run_host') as run, \
             patch('option_discovery.discover_description') as discover, \
             patch('option_discovery.Path.is_file',return_value=True), \
             patch('option_discovery.os.access',return_value=True):
            def fake_help(argv,**kwargs):
                kwargs['stdout'].write(b'Usage: lsblk [options]\nList information about block devices.\n')
                return subprocess.CompletedProcess(argv,0)
            run.side_effect=fake_help
            help=load_command_info(target)
        self.assertIn('block devices',help.summary)
        discover.assert_not_called()

    def test_end_to_end_help_without_summary_uses_host_man(self):
        target=Executable('usbip','executable','/usr/bin/usbip')
        with patch('option_discovery.run_host') as run, \
             patch('option_discovery.discover_description',
                   return_value=DocumentedDescription('manage USB/IP devices','manual')) as discover, \
             patch('option_discovery.Path.is_file',return_value=True), \
             patch('option_discovery.os.access',return_value=True):
            def fake_help(argv,**kwargs):
                kwargs['stdout'].write(b'Usage: usbip [--debug] [--log] COMMAND\n')
                return subprocess.CompletedProcess(argv,0)
            run.side_effect=fake_help
            help=load_command_info(target)
        self.assertEqual(help.summary,'manage USB/IP devices')
        self.assertIn('usbip',help.usage)
        self.assertEqual(help.summary_source,'manual')
        discover.assert_called_once_with('usbip',kind='executable',location='/usr/bin/usbip')

if __name__=='__main__': unittest.main()
