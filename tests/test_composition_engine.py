"""Typed composition registry regression tests; all pure/headless."""
import shlex
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core import Command
from context_composer import SelectedApp
from guided_workflows import Volume
from composition_engine import (CompositionEngine, Rule, Subject,
                                default_engine)


class SubjectTests(unittest.TestCase):
    def test_strict_types_and_injection(self):
        for kind, value in [
            ('app', 'org.example.App'), ('service', 'bad;echo hi'),
            ('host','-evil.example'),('host','evil;id'),
            ('interface','wlan0;id'),('container','--help'),
            ('container','evil\nname'),('unregistered','test')]:
            with self.subTest(kind=kind,value=value), self.assertRaises(ValueError):
                Subject(kind,value)
        self.assertEqual(Subject('service','NetworkManager').value,'NetworkManager.service')
        self.assertEqual(Subject('host','2001:db8::1').value,'2001:db8::1')
        self.assertEqual(Subject('interface','enp4s0').value,'enp4s0')

    def test_path_is_verified_and_resolved(self):
        with tempfile.TemporaryDirectory(prefix='ult engine ') as tmp:
            root = Path(tmp)
            sample = root / 'semi;colon file.txt'; sample.write_text('hello')
            self.assertEqual(Subject('file',str(sample)).value,str(sample))
            with self.assertRaises(ValueError): Subject('folder',str(sample))
            with self.assertRaises(ValueError): Subject('file',str(root))
            with self.assertRaises(ValueError): Subject('file',str(root / 'absent'))


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.engine=default_engine()
        self.app=SelectedApp('org.example.App','Test App',True)
        # Tests use installed commands available in the CI environment.
        self.available=patch('composition_engine.shutil.which',side_effect=lambda tool:'/usr/bin/'+tool)
        self.available.start()
        self.addCleanup(self.available.stop)

    def test_schema_based_suggestions_not_name_matching(self):
        self.assertFalse(self.engine.suggestions())
        self.engine.choose(Subject('app',self.app))
        suggestions={s.key:s for s in self.engine.suggestions()}
        self.assertIn('app.info',suggestions)
        self.assertIn('app.permissions',suggestions)
        self.assertEqual(suggestions['app.folder_access'].missing, ('volume','folder'))
        self.assertNotIn('service.logs',suggestions)
        self.assertEqual(self.engine.compose('app.info')[0].argv,
                         ['flatpak','info','org.example.App'])
        with self.assertRaisesRegex(ValueError,'Choose first'):
            self.engine.compose('app.folder_access')

    def test_mounted_volume_and_folder_complete_recipe(self):
        with tempfile.TemporaryDirectory(prefix='ult-mount ') as base:
            root=Path(base)/'Mounted';root.mkdir()
            folder=root/'Steam Games';folder.mkdir()
            vol=Volume('/dev/sdb1','ext4','2T','games',str(root))
            self.engine.choose(Subject('app',self.app))
            self.engine.choose(Subject('volume',vol))
            self.engine.choose(Subject('folder',str(folder)))
            prepared, notes=self.engine.compose('app.folder_access')
            self.assertEqual(prepared.argv, ['flatpak','override','--user',
                             f'--filesystem={folder}',self.app.app_id])
            self.assertTrue(prepared.changes)
            self.assertEqual(shlex.split(prepared.preview),prepared.argv)
            self.assertEqual(self.engine.compose('volume.free')[0].argv,
                             ['df','-h','--',str(root)])
            self.assertNotIn('mkfs',prepared.preview)
            # Changing the selected volume clears stale folder context.
            self.engine.choose(Subject('volume',Volume('/dev/sdb2','ntfs','1T','',None)))
            self.assertNotIn('folder',self.engine.selected)
            self.assertEqual(self.engine.compose('volume.mount')[0].argv,
                             ['udisksctl','mount','-b','/dev/sdb2'])

    def test_stale_context_cannot_cross_subject_types(self):
        self.engine.choose(Subject('app',self.app))
        self.engine.choose(Subject('service','sshd'))
        self.assertNotIn('app',self.engine.selected)
        self.assertEqual(self.engine.compose('service.errors')[0].argv,
                        ['journalctl','--no-pager','-u','sshd.service','-p','err','-n','100'])
        with self.assertRaisesRegex(ValueError,'Choose first'):
            self.engine.compose('app.info')

    def test_directory_files_network_container_reusable(self):
        with tempfile.TemporaryDirectory() as root:
            file=Path(root)/'strange ;file';file.touch()
            cases=[('file',str(file),'file.hash',['sha256sum','--',str(file)]),
                   ('folder',root,'folder.size',['du','-sh','--',root]),
                   ('host','example.org','host.dns',['getent','ahosts','example.org']),
                   ('container','test_box','container.logs',['podman','logs','--','test_box']),
                   ('interface','enp4s0','interface.address',['ip','address','show','dev','enp4s0'])]
            for kind,value,rule,args in cases:
                with self.subTest(kind=kind):
                    self.engine.choose(Subject(kind,value))
                    cmd,_=self.engine.compose(rule)
                    self.assertEqual(cmd.argv,args)
                    self.assertEqual(shlex.split(cmd.preview),args)
                    self.assertFalse(cmd.changes)

    def test_app_search_result_not_installed_is_inspect_only(self):
        app=SelectedApp('org.example.Download','Download',False,'flathub')
        self.engine.choose(Subject('app',app))
        self.assertEqual(self.engine.compose('app.info')[0].argv,
                         ['flatpak','remote-info','flathub','org.example.Download'])
        with self.assertRaisesRegex(ValueError,'does not apply'):
            self.engine.compose('app.permissions')

    def test_unavailable_tool_does_not_construct(self):
        self.engine.choose(Subject('service','cups'))
        with patch('composition_engine.shutil.which',return_value=None):
            self.assertEqual(self.engine.suggestions(),[])
            with self.assertRaisesRegex(ValueError,'Required tool'):
                self.engine.compose('service.logs')

    def test_recipe_extensions_are_data_driven_but_checked(self):
        calls=[]
        def builder(selected):
            calls.append('compiled')
            return Command('Test',['echo',selected['host'].value],''),''
        engine=CompositionEngine()
        rule=Rule('host.echo','Display hostname','Demo',('host',),'echo',builder)
        engine.register(rule)
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            engine.register(rule)
        engine.choose(Subject('host','example.com'))
        self.assertEqual(engine.compose('host.echo')[0].argv,['echo','example.com'])
        self.assertEqual(calls,['compiled'])
        engine.clear()
        self.assertEqual(engine.suggestions(),[])

    def test_read_only_rules_cannot_hide_side_effect(self):
        engine=CompositionEngine([Rule('test.unsafe','Unsafe','',('host',),'echo',
                                 lambda c:(Command('x',['echo','test'],'',True),''))])
        engine.choose(Subject('host','example.org'))
        with self.assertRaisesRegex(ValueError,'Read-only'):
            engine.compose('test.unsafe')

    def test_no_implicit_shell_execution(self):
        with patch('subprocess.run',side_effect=AssertionError('must not execute')):
            self.engine.choose(Subject('service','sshd'))
            self.engine.suggestions()
            self.engine.compose('service.logs')


if __name__ == '__main__':
    unittest.main()
