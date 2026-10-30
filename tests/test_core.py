import tempfile
import unittest
import shlex
from pathlib import Path
from unittest.mock import patch
from core import Command, bundle, build, app_remove, catalog, availability

class Commands(unittest.TestCase):
    def test_shell_characters_remain_arguments(self):
        cmd = Command('x', ['echo', "a'; $(touch /tmp/should-not-exist)"], '')
        self.assertEqual(shlex.split(cmd.preview), cmd.argv)

    def test_remove_scope(self):
        for scope in ('user', 'system'):
            self.assertEqual(app_remove('org.example.App', scope).argv, ['flatpak','uninstall','--'+scope,'org.example.App'])

    def test_reject_bad_ids(self):
        for app in ('--help', 'a; reboot', 'x\ny', ''):
            with self.assertRaises(ValueError): app_remove(app,'user')
        with self.assertRaises(ValueError): app_remove('org.example.App','host')

    def test_bundle_checks_and_quotes(self):
        with tempfile.TemporaryDirectory(prefix='ult space ') as root:
            p = Path(root)
            with self.assertRaises(ValueError): bundle(root,str(p/'out.flatpak'),'org.example.App','master')
            (p/'objects').mkdir(); (p/'config').write_text('[core]\n')
            cmd = bundle(root,str(p/'out.flatpak'),'org.example.App','master')
            self.assertEqual(shlex.split(cmd.preview), cmd.argv)
            (p/'out.flatpak').touch()
            with self.assertRaises(ValueError): bundle(root,str(p/'out.flatpak'),'org.example.App','master')

    def test_build_wont_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root); manifest = p/'app.json'; manifest.write_text('{}')
            self.assertEqual(build(root,str(manifest),str(p/'repo')).cwd,root)
            (p/'ult-build').mkdir()
            with self.assertRaises(ValueError): build(root,str(manifest),str(p/'repo'))

    def test_distro_filter(self):
        with patch('core.detect', return_value={'bazzite':False}):
            self.assertNotIn('Bazzite',[x[0] for x in catalog()])
        with patch('core.detect', return_value={'bazzite':True}):
            self.assertGreaterEqual(len(catalog()),34)

    def test_missing_and_sandbox(self):
        with patch('core.detect',return_value={'sandbox':False}), patch('core.shutil.which',return_value=None):
            self.assertIn('Ontbrekend',availability(Command('', ['absent'], '')))
        with patch('core.detect',return_value={'sandbox':True}):
            self.assertIn('geblokkeerd', availability(Command('', ['true'], '', True)))

if __name__ == '__main__': unittest.main()

class ExtendedCommands(unittest.TestCase):
    def test_exact_flatpak_installation(self):
        from core import flatpak_action
        ref='app/org.example.App/x86_64/beta'
        self.assertEqual(flatpak_action('uninstall',ref,'extra').argv,
                         ['flatpak','uninstall','--installation=extra',ref])
        self.assertIn('--show-permissions', flatpak_action('permissions',ref,'user').argv)
        for bad in ['--delete-data','app/org.example.App/x86_64/stable;id','runtime/org.foo.Bar/x86_64/stable']:
            with self.assertRaises(ValueError): flatpak_action('uninstall',bad,'user')

    def test_parse_multiple_branches(self):
        from core import parse_apps
        rows=parse_apps('org.example.App/x86_64/stable\tApp\t1\tflathub\tuser\norg.example.App/x86_64/beta\tApp\t2\tbeta\tsystem\n')
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0][1],'app/org.example.App/x86_64/stable')
        self.assertNotEqual(rows[0][1],rows[1][1])
        self.assertEqual(rows[1][4],'system')

    def test_parameter_injection(self):
        from core import parameter_command
        for kind in ('ping','service','logs','container','install'):
            for value in ('--help','foo;id','x\ny'):
                with self.assertRaises(ValueError): parameter_command(kind,value)
        cmd=parameter_command('search','hello; $(id)')
        self.assertEqual(cmd.argv[-1],'hello; $(id)')
        self.assertEqual(shlex.split(cmd.preview),cmd.argv)

    def test_manifest_metadata(self):
        from core import manifest_info
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'app.json'
            p.write_text('{"app-id":"org.example.App","branch":"beta","sdk":"org.kde.Sdk","runtime-version":"6.10"}')
            self.assertEqual(manifest_info(p)['branch'],'beta')
            p.write_text('[]')
            with self.assertRaises(ValueError): manifest_info(p)

    def test_hash_spaces_and_shell_syntax(self):
        from core import parameter_command
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'name $(id) with spaces'; p.write_text('hi')
            cmd=parameter_command('hash',str(p))
            self.assertEqual(cmd.argv,['sha256sum','--',str(p)])

    def test_all_catalog_previews_roundtrip(self):
        with patch('core.detect', return_value={'bazzite':True}):
            for _, cmd in catalog(): self.assertEqual(shlex.split(cmd.preview),cmd.argv)

class TerminalInput(unittest.TestCase):
    def test_prepared_line_never_executes(self):
        from core import terminal_line
        cmd=Command('test',['echo','hello; $(id)'],'')
        line=terminal_line(cmd)
        self.assertNotIn('\n',line)
        self.assertEqual(shlex.split(line),cmd.argv)
        with self.assertRaises(ValueError): terminal_line(Command('bad',['echo','x\ny'],''))

    def test_build_keeps_working_directory(self):
        from core import terminal_line
        cmd=Command('build',['flatpak-builder','output','manifest.json'],'',True,"/tmp/project's folder")
        self.assertEqual(shlex.split(terminal_line(cmd)),['cd','--',cmd.cwd,'&&',*cmd.argv])
