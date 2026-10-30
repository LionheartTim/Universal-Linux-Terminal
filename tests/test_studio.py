"""Command-studio regressions; runs headless, never mounts or grants access."""
import ast
import json
import os
import shlex
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from command_discovery import Executable, installed_commands, prepare_command, search_installed_commands
from guided_workflows import (Volume, parse_lsblk, check_folder, build_steam_plan,
                              scan_volumes)
from i18n import tr


class CommandDiscoveryTests(unittest.TestCase):
    def test_installed_paths_and_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp)/'a', Path(tmp)/'b'
            a.mkdir(); b.mkdir()
            (a/'mytool').write_text('#!/bin/sh\nexit 0\n')
            (a/'mytool').chmod(0o755)
            (b/'mytool').write_text('hi')
            (b/'mytool').chmod(0o755)
            (a/'noexec').write_text('hi')
            commands = installed_commands(str(a)+os.pathsep+str(b), 'cd\nalias\n')
            byname = {c.name: c for c in commands}
            self.assertEqual(byname['mytool'].location, str(a/'mytool'))
            self.assertNotIn('noexec', byname)
            self.assertEqual(byname['cd'].kind,'bash builtin')
            self.assertEqual(len([c for c in commands if c.name=='mytool']),1)

    def test_shared_search_finds_programs_and_prioritizes_exact_match(self):
        found = [Executable(n,'executable','/usr/bin/'+n)
                 for n in ('splitblock', 'lsblk', 'lsblk2', 'pslsblk', 'other')]
        self.assertEqual([c.name for c in search_installed_commands(found, 'LSBLK')],
                         ['lsblk', 'lsblk2', 'pslsblk'])
        self.assertEqual([c.name for c in search_installed_commands(found, 'lsblk', 2)],
                         ['lsblk', 'lsblk2'])
        self.assertEqual(search_installed_commands(found, ''), [])
        self.assertEqual(search_installed_commands(found, 'missing'), [])

    def test_main_search_indexes_programs_and_opens_preselected_option_builder(self):
        source = (Path(__file__).resolve().parents[1]/'app.py').read_text()
        studio = (Path(__file__).resolve().parents[1]/'studio_ui.py').read_text()
        self.assertIn("search.connect('search-changed', searching)", source)
        self.assertIn('self._refresh_installed_search()', source)
        self.assertIn('search_installed_commands(self._installed_inventory, self.query)', source)
        self.assertIn('self.tree_store.append(self._installed_group, [program.name, program])', source)
        self.assertIn('isinstance(value, Executable)', source)
        self.assertIn('self.options_button.show()', source)
        self.assertIn('initial_command=self._selected_executable.name', source)
        self.assertIn('open_installed_commands(owner, initial_command=None, inventory=None)', studio)
        self.assertIn('search.set_text(initial_command)', studio)
        self.assertNotIn('Request options from this program?', studio)
        self.assertEqual(tr('Choose command options…','nl'),'Commando-opties kiezen…')
        self.assertEqual(tr('Zoek functies of commando’s…','en'),'Search functions or commands…')

    def test_quotes_and_no_execution(self):
        with patch('command_discovery.subprocess.run') as run:
            pool = [Executable('testcmd', 'executable', '/usr/bin/testcmd')]
            cmd = prepare_command('testcmd', "--path '/run/media/My Games' 'hello;touch /tmp/sentinel'", pool)
            self.assertEqual(shlex.split(cmd.preview), cmd.argv)
            self.assertEqual(cmd.argv[2], '/run/media/My Games')
            run.assert_not_called()
        for s in ('bad\nargs', "'unclosed"):
            with self.assertRaises(ValueError): prepare_command('testcmd', s)
        for name in ('../bash','', 'bad\nname'):
            with self.assertRaises(ValueError): prepare_command(name)
        # Quoted metacharacters in a *filename* do not execute as shell syntax.
        self.assertEqual(shlex.split(prepare_command('tool;id').preview), ['tool;id'])
        with self.assertRaises(ValueError): prepare_command('notinstalled', inventory=pool)

    def test_unusual_valid_unix_command_names_remain_discoverable(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            (directory/'bad;name').write_text(''); (directory/'bad;name').chmod(0o755)
            commands=installed_commands(tmp, '[:\n.\n')
            self.assertEqual([c.name for c in commands], ['.', '[:', 'bad;name'])
            self.assertEqual(shlex.split(prepare_command('bad;name').preview), ['bad;name'])


class SteamWizardBackendTests(unittest.TestCase):
    def setUp(self):
        self.sample = json.dumps({'blockdevices': [
            {'type':'disk','path':'/dev/nvme0n1','children':[
                {'type':'part','path':'/dev/nvme0n1p1','fstype':'vfat','size':'500M',
                 'mountpoints':['/boot/efi'],'ro':False},
                {'type':'part','path':'/dev/nvme0n1p2','fstype':'btrfs','size':'200G',
                 'mountpoints':['/','/home'],'ro':False}]},
            {'type':'disk','path':'/dev/sdb','children':[
                {'type':'part','path':'/dev/sdb1','fstype':'ext4',
                 'size':'2T','label':'My Games','mountpoints':['/run/media/user/Games'],'ro':False},
                {'type':'part','path':'/dev/sdb2','fstype':'swap','mountpoints':[None], 'ro':False},
                {'type':'part','path':'/dev/sdb3','fstype':'ntfs','size':'1T',
                 'mountpoints':[None],'ro':False}]},
            {'type':'part','path':'/dev/sdc1','fstype':'crypto_LUKS',
             'mountpoints':[None], 'ro':False},
            {'type':'part','path':'/dev/sdd1','fstype':'ext4',
             'mountpoints':['/run/media/private'],'ro':True},
        ]})

    def test_system_disks_excluded_and_unmounted_visible(self):
        parsed=parse_lsblk(self.sample)
        self.assertEqual([v.path for v in parsed], ['/dev/sdb1','/dev/sdb3'])
        self.assertIsNone(parsed[1].mountpoint)

    def test_mount_command_does_not_mount(self):
        vol=Volume('/dev/sdb3','ntfs','1T','','')
        vol=Volume('/dev/sdb3','ntfs','1T','',None)
        with patch('guided_workflows.shutil.which', return_value='/usr/bin/udisksctl'):
            cmd, steps=build_steam_plan(vol)
        self.assertEqual(cmd.argv, ['udisksctl','mount','-b','/dev/sdb3'])
        self.assertIn('Return to this wizard',steps)
        self.assertEqual(shlex.split(cmd.preview),cmd.argv)

    def test_folder_spaces_and_mount_guard(self):
        with tempfile.TemporaryDirectory(prefix='ult games ') as root:
            mount=Path(root)/'disk'; mount.mkdir()
            chosen=mount/'Steam Library'; chosen.mkdir()
            wrong=Path(root)/'disk-other'; wrong.mkdir()
            vol=Volume('/dev/sdb1','ext4','2T','My Games',str(mount))
            with patch('guided_workflows.shutil.which',return_value='/usr/bin/flatpak'):
                cmd, steps=build_steam_plan(vol,str(chosen),'flatpak')
            self.assertEqual(cmd.argv[0:3],['flatpak','override','--user'])
            self.assertEqual(cmd.argv[3],f'--filesystem={chosen}')
            self.assertEqual(shlex.split(cmd.preview), cmd.argv)
            self.assertIn('Settings > Storage', steps)
            with self.assertRaises(ValueError): check_folder(vol, str(wrong))
            with self.assertRaises(ValueError): check_folder(vol, str(mount/'doesnotexist'))
            cmd, text=build_steam_plan(vol,str(chosen),'native')
            self.assertIsNone(cmd)
            self.assertIn('Steam',text)

    def test_no_auto_formatting_or_unknown_disk(self):
        with self.assertRaises(ValueError): build_steam_plan(Volume('/dev/sdc1;id','ext4','','',None))
        with self.assertRaises(ValueError): build_steam_plan(Volume('/dev/sdc1','swap','','',None))
        # Unsafe device names / unsupported filesystems cannot reach a command.

    def test_listing_subprocess_read_only(self):
        class Return:
            stdout='{"blockdevices":[]}'
        with patch('guided_workflows.shutil.which',return_value='/usr/bin/lsblk'):
            with patch('guided_workflows.subprocess.run',return_value=Return()) as run:
                self.assertEqual(scan_volumes(),[])
                args=run.call_args.args[0]
                self.assertEqual(args[:2],['lsblk','-J'])
                self.assertFalse(any(a in args for a in ('mount','format','erase')))

    def test_gui_wiring_and_english_nl_labels(self):
        root=Path(__file__).resolve().parents[1]
        app=(root/'app.py').read_text()
        terminal=(root/'terminal.py').read_text()
        tree=ast.parse((root/'studio_ui.py').read_text())
        self.assertIn('steam_storage',app)
        self.assertIn('all_commands',app)
        self.assertIn("button(L('Stop')",terminal)
        self.assertTrue(any(isinstance(n,ast.ClassDef) and n.name=='SteamStorageWizard'
                            for n in tree.body))
        self.assertEqual(tr('All installed commands…','nl'),'Alle geïnstalleerde commando’s…')
        self.assertEqual(tr('Stop','en'),'Stop')

if __name__=='__main__':
    unittest.main()
