"""Headless regression tests for the new per-command sidebar documentation."""
import ast
import shutil
import unittest
from types import SimpleNamespace
from pathlib import Path
from command_discovery import Executable
from option_discovery import (parse_command_help, format_command_help,
                              load_command_info, CommandHelp, CliOption)
from i18n import tr

ROOT=Path(__file__).resolve().parents[1]

SAMPLE="""\x1b[1mUsage: lsblk [options] [<device> ...]\x1b[0m

List information about block devices.

Options:
 -A, --noempty        don't print empty devices
 -f, --fs             output info about filesystems
 -o, --output <list>  output columns (see --list-columns)
 -h, --help           display this help
"""

class InformationTests(unittest.TestCase):
    def test_realistic_help_summary_usage_and_options(self):
        details=parse_command_help(SAMPLE)
        self.assertEqual(details.summary, 'List information about block devices.')
        self.assertEqual(details.usage, 'Usage: lsblk [options] [<device> ...]')
        self.assertIn('-f', [o.flag for o in details.options])
        en=format_command_help('lsblk',details)
        self.assertIn('What it does:\nList information about block devices.',en)
        self.assertIn('Usage:\nlsblk [options]',en)
        self.assertIn('• -f',format_command_help('lsblk',details,
                           [(next(o for o in details.options if o.flag=='-f'),'')]))
        nl=format_command_help('lsblk',details,translate=lambda s:tr(s,'nl'))
        self.assertIn('Wat doet dit commando:',nl)
        self.assertIn('Gedocumenteerde opties:',nl)

    def test_multiline_description_and_synopsis(self):
        df='''Usage: df [OPTION]... [FILE]...
Show information about the file system on which each FILE resides,
or all file systems by default.

Options:
 -h, --human-readable   print human readable sizes
'''
        details=parse_command_help(df)
        self.assertIn('file system',details.summary)
        self.assertFalse(details.summary.endswith(','),details.summary)
        sysctl='''systemctl [OPTIONS...] COMMAND ...

Query or send control commands to the system manager.

Unit Commands:
 status PATTERN  Show status
'''
        details=parse_command_help(sysctl)
        self.assertEqual(details.summary,'Query or send control commands to the system manager.')
        self.assertIn('systemctl [OPTIONS...]',details.usage)

    def test_lsb_release_complete_wrapped_description(self):
        # Realistic util-linux/LSB help: a sentence wraps at "and" and must
        # not lose the remaining words even in a narrow sidebar.
        output = ("lsb-release v3.3 prints certain LSB (Linux Standard Base) and\n"
                  "distribution-specific information.\n\n"
                  "Usage: lsb-release [OPTION]...\n\n"
                  "Options:\n -h, --help  display help\n")
        info = parse_command_help(output)
        self.assertEqual(info.summary,
                         "lsb-release v3.3 prints certain LSB (Linux Standard Base) "
                         "and distribution-specific information.")
        self.assertIn('distribution-specific information.',
                      format_command_help('lsb-release', info))
        self.assertNotIn('Usage:', info.summary)

    def test_description_stops_before_new_sections(self):
        output = ("Displays current files and\n"
                  "directories with file details.\n"
                  "Options:\n"
                  " -h, --help   display help\n")
        info = parse_command_help(output)
        self.assertEqual(info.summary,
                         "Displays current files and directories with file details.")
        self.assertNotIn('Options:', info.summary)

    def test_description_keeps_long_prose_but_remains_bounded(self):
        output = 'This tool provides diagnostics and\n' + ('detailed information.\n' * 180)
        info = parse_command_help(output)
        self.assertGreater(len(info.summary), 100)
        self.assertLessEqual(len(info.summary), 800)

    def test_bounded_plain_text_unknown_help(self):
        details=parse_command_help('Invalid help text\x1b[31m\x1b[0m\x01\n')
        self.assertTrue(all('\x1b' not in s for s in (details.summary,details.usage)))
        self.assertIn('No description', format_command_help('mystery',CommandHelp('', '', ())))
        option=CliOption(('--output',),'Choose output',True,False,'LIST')
        text=format_command_help('tool',CommandHelp('', '', (option,)),[(option,'NAME,SIZE')])
        self.assertIn('--output NAME,SIZE — Choose output',text)

    def test_real_lsblk_or_skip(self):
        binary=shutil.which('lsblk')
        if not binary: self.skipTest('No lsblk')
        doc=load_command_info(Executable('lsblk','executable',binary))
        self.assertIn('block devices',doc.summary.lower())
        self.assertGreaterEqual(len(doc.options),10)

    def test_stale_help_response_does_not_overwrite_new_sidebar_command(self):
        """Exercise the actual GTK-independent callback body with fake widgets."""
        src=(ROOT/'app.py').read_text()
        module=ast.parse(src)
        klass=next(x for x in module.body if isinstance(x,ast.ClassDef) and x.name=='Window')
        method=next(x for x in klass.body if isinstance(x,ast.FunctionDef) and x.name=='show_command_info')
        callbacks=[]
        class FakeThread:
            def __init__(self,target,daemon=True): self.target=target
            def start(self): self.target()
        docs={
            'lsblk': CommandHelp('List information about block devices.','Usage: lsblk',(CliOption(('-f',), 'filesystems'),)),
            'df': CommandHelp('Show filesystem space.','Usage: df',()),
        }
        bindings={'threading':SimpleNamespace(Thread=FakeThread),
                  'GLib':SimpleNamespace(idle_add=lambda cb: callbacks.append(cb)),
                  'load_command_info':lambda cmd:docs[cmd.name],
                  'format_command_help':format_command_help,
                  'L':lambda x:x}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),
                     '<command info>', 'exec'),bindings)
        class Label:
            def __init__(self):self.text=''
            def set_text(self,s):self.text=s
        class Scroll:
            def get_vadjustment(self):return SimpleNamespace(set_value=lambda x: None)
        class Owner:
            _command_info_generation=0
            destroyed=False
            def __init__(self):
                self._command_help_cache={}; self.description=Label()
                self.heading=Label(); self.options_button=SimpleNamespace(show=lambda:None)
                self.info_scroll=Scroll()
            def _help_key(self,exe):return (exe.name,exe.kind,exe.location)
            def get_cached_command_info(self,exe):return self._command_help_cache.get(self._help_key(exe))
            def cache_command_info(self,exe,help):self._command_help_cache[self._help_key(exe)]=help
        owner=Owner()
        show=bindings['show_command_info']
        show(owner, Executable('lsblk','executable','/usr/bin/lsblk'))
        show(owner, Executable('df','executable','/usr/bin/df'))
        self.assertEqual(len(callbacks),2)
        callbacks[0]()
        self.assertEqual(owner.description.text, 'Reading command information…')
        callbacks[1]()
        self.assertIn('Show filesystem space.',owner.description.text)
        self.assertNotIn('List information',owner.description.text)
        # Cached help shouldn't start another help subprocess.
        show(owner, Executable('df','executable','/usr/bin/df'))
        self.assertEqual(len(callbacks),2)
        self.assertIn('Show filesystem space.',owner.description.text)

    def test_sidebar_async_cache_stale_guards_and_scroll(self):
        code=(ROOT/'app.py').read_text()
        source=(ROOT/'studio_ui.py').read_text()
        self.assertIn('self.info_scroll.add(self.description)', code)
        self.assertIn('class CommandDescriptionView(Gtk.TextView)', code)
        self.assertIn('wrap_mode=Gtk.WrapMode.WORD_CHAR', code)
        self.assertIn('self.show_command_info(value)',code)
        self.assertIn('generation != self._command_info_generation',code)
        self.assertIn('self._selected_executable != target',code)
        self.assertIn('load_command_info(target)',code)
        self.assertIn('owner.show_command_info(target, chosen)',source)
        self.assertIn('owner.cache_command_info(target, details)',source)
        self.assertIn('self._command_info_generation += 1',code)
        # The async path must not block GTK or execute on every search keystroke.
        method=ast.parse(code)
        klass=next(x for x in method.body if isinstance(x,ast.ClassDef) and x.name=='Window')
        show=next(x for x in klass.body if isinstance(x,ast.FunctionDef) and x.name=='show_command_info')
        self.assertTrue(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
                            and n.func.attr=='start' for n in ast.walk(show)))

if __name__=='__main__': unittest.main()
