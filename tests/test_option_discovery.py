"""Pure parser and automatic help-display tests; never actually execute a composed command."""
import ast
import os
import shlex
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from command_discovery import Executable
from option_discovery import (CliOption, parse_help_options, option_arguments,
                              compose_selected_options, prepare_with_options,
                              load_options)
from i18n import tr

LSBLK_HELP = '''Usage: lsblk [options]
Options:
 -A, --noempty        don't print empty devices
 -E, --dedup <column> de-duplicate output by <column>
 -J, --json           use JSON output format
 -T, --tree[=<column>]  tree output
 -f, --fs             output info about filesystems
 -o, --output <list>  output columns (see --list-columns)
     --sysroot <dir>  use specified directory as system root
'''
DF_HELP = '''Usage: df [OPTION]...
  -h, --human-readable  print sizes in powers of 1024
  -B, --block-size=SIZE  scale sizes by SIZE
      --output[=FIELD_LIST]  use format defined by FIELD_LIST
'''

class OptionsTests(unittest.TestCase):
    def test_lsblk_flags_explained_and_values(self):
        options = parse_help_options(LSBLK_HELP)
        by_flag = {name:o for o in options for name in o.names}
        self.assertIn('-f', by_flag)
        self.assertIn('-E', by_flag)
        self.assertIn('-T', by_flag)
        self.assertEqual(by_flag['-f'].flag, '-f')
        self.assertIn('filesystems', by_flag['-f'].description)
        self.assertEqual(option_arguments(by_flag['-f']), ['-f'])
        self.assertEqual(option_arguments(by_flag['-o'], 'NAME,SIZE'), ['-o','NAME,SIZE'])
        self.assertEqual(option_arguments(by_flag['--sysroot'], '/mnt/check'), ['--sysroot','/mnt/check'])
        self.assertTrue(by_flag['--tree'].optional_value)
        self.assertEqual(option_arguments(by_flag['--tree'],'NAME'), ['--tree=NAME'])
        with self.assertRaisesRegex(ValueError, 'needs a value'):
            option_arguments(by_flag['-o'])

    def test_optional_values_gnu_style(self):
        by_flag = {o.flag:o for o in parse_help_options(DF_HELP)}
        self.assertTrue(by_flag['--output'].optional_value)
        self.assertEqual(option_arguments(by_flag['--output'], 'SOURCE,SIZE'),
                         ['--output=SOURCE,SIZE'])
        self.assertEqual(option_arguments(by_flag['--output']), ['--output'])
        self.assertEqual(option_arguments(by_flag['-B'],'1G'), ['-B','1G'])

    def test_strict_lines_dedup_and_no_invention(self):
        text = ''' -f, --fs    show filesystems
 -f, --fs    duplicate
 This flag --delete is NOT a help option
 --delete now if you want
 --junk, --other, --third  incorrect grouping
 -o, --output FILE  write
'''
        flags = parse_help_options(text)
        self.assertEqual([o.flag for o in flags], ['-f','-o'])
        self.assertEqual(flags[0].description, 'show filesystems')
        self.assertEqual(parse_help_options('this command has no parsable options'), [])

    def test_no_shell_interpolation_or_execution_during_composition(self):
        fs = CliOption(('-f','--fs'),'show filesystems')
        output = CliOption(('-o','--output'),'columns', True, False, 'LIST')
        command = Executable('lsblk','executable','/usr/bin/lsblk')
        with patch('option_discovery.subprocess.run') as run:
            cmd = prepare_with_options('lsblk', "'/run/media/My Drive'",
                                       [command], [(fs,''),(output,'NAME;$(touch /tmp/not-run)')])
            run.assert_not_called()
        self.assertEqual(cmd.argv, ['lsblk','-f','-o','NAME;$(touch /tmp/not-run)',
                                    '/run/media/My Drive'])
        self.assertEqual(shlex.split(cmd.preview), cmd.argv)
        with self.assertRaises(ValueError):
            prepare_with_options('lsblk','', [command],[(output,'')])
        with self.assertRaises(ValueError):
            option_arguments(fs,'bad\nline')

    def test_selected_command_help_bounded(self):
        # No execution during inventory/search. The dialog loads help when
        # the user selects a specific command, never while filtering.
        fake = Executable('lsblk','executable','/usr/bin/lsblk')
        with patch('option_discovery.subprocess.run') as run, \
                patch('option_discovery.Path.is_file',return_value=True), \
                patch('option_discovery.os.access',return_value=True):
            def write_help(*args,**kwargs):
                kwargs['stdout'].write(LSBLK_HELP.encode())
                return None
            run.side_effect = write_help
            options = load_options(fake)
            self.assertIn('-f',[o.flag for o in options])
            self.assertEqual(run.call_args.args[0],['/usr/bin/lsblk','--help'])
            self.assertEqual(run.call_args.kwargs['stdin'], __import__('subprocess').DEVNULL)
            self.assertLessEqual(run.call_args.kwargs['timeout'],4)
            self.assertTrue(run.call_args.kwargs['start_new_session'])
        # There is no shell=True and no user-provided command passed to shell.

    def test_real_lsblk_when_available(self):
        binary = shutil.which('lsblk')
        if not binary:
            self.skipTest('lsblk unavailable')
        options = load_options(Executable('lsblk','executable',binary))
        by_name = {name:o for o in options for name in o.names}
        self.assertIn('-f',by_name)
        self.assertIn('-o',by_name)
        self.assertTrue(by_name['-o'].takes_value)

    def test_selection_automatically_loads_lower_option_list(self):
        source = (Path(__file__).resolve().parents[1]/'studio_ui.py').read_text()
        tree = ast.parse(source)
        ui = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'open_installed_commands')
        methods = {n.name: n for n in ui.body if isinstance(n, ast.FunctionDef)}
        self.assertIn('command_changed', methods)
        self.assertIn('load_selected_options', methods)
        self.assertIn('populate_options', methods)
        changed = ast.get_source_segment(source, methods['command_changed'])
        loader = ast.get_source_segment(source, methods['load_selected_options'])
        self.assertIn('load_selected_options(target, state[\'generation\'])', changed)
        self.assertIn('load_command_info(target)', loader)
        self.assertIn("state['cache']", loader)
        self.assertIn("state['generation'] != generation", loader)
        self.assertIn("state['active']", loader)
        self.assertIn('threading.Thread(target=worker, daemon=True).start()', loader)
        self.assertNotIn("Gtk.Button(label=L('Show available options…'))", source)
        self.assertNotIn("load_button.connect", source)
        self.assertIn("option_model.append([False, option.display, option.description", source)

    def test_builtin_help(self):
        if not shutil.which('bash'):
            self.skipTest('bash unavailable')
        options = load_options(Executable('cd','bash builtin','Bash'))
        self.assertIn('-P',[o.flag for o in options])

    def test_ui_boundaries_and_locale(self):
        source = (Path(__file__).resolve().parents[1]/'studio_ui.py').read_text()
        self.assertIn('threading.Thread(target=worker, daemon=True).start()',source)
        self.assertIn('load_command_info(target)',source)
        self.assertNotIn('Gtk.MessageDialog', source.split('def load_selected_options(target, generation):')[1].split("    selection.connect(")[0])
        self.assertIn('if target is None:', source)
        self.assertIn('owner.stage(cmd)',source)
        self.assertEqual(tr('Select a command to see its options below. You can also type arguments manually.', 'nl'), 'Kies een commando om de opties hieronder te zien. Je kunt ook argumenten zelf typen.')
        self.assertEqual(tr('This option needs a value','nl'), 'Deze optie heeft een waarde nodig')

if __name__ == '__main__':
    unittest.main()
