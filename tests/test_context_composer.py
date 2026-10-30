"""Context builder tests. No actual installs, permissions, mounting or shell runs."""
import ast
import shlex
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core import Command
from context_composer import (SelectedApp, parse_flatpak_search,
                              app_preview, combine_app_storage)
from guided_workflows import Volume
from i18n import tr

class ContextCompositionTests(unittest.TestCase):
    def test_search_results_validate_app_ids_and_allow_spaces(self):
        rows = parse_flatpak_search(
            'Name\tApplication\tVersion\tRemotes\n'
            'Steam\tcom.valvesoftware.Steam\t3.0\tflathub\n'
            'An App\torg.example.App\t1.0\tflathub,system\n'
            'Bad\t; rm -rf ~\t0\tflathub\n'
            'Duplicate\tcom.valvesoftware.Steam\t3.0\tflathub\n'
        )
        self.assertEqual([r[1] for r in rows], ['com.valvesoftware.Steam','org.example.App'])
        self.assertEqual(rows[1][3], 'flathub')

    def test_safe_app_selection_and_read_only_preview(self):
        for bad in ('../Steam', '--help', 'com.fake;id', 'bad\nname'):
            with self.assertRaises(ValueError): SelectedApp(bad, 'oops', False)
        app=SelectedApp('com.valvesoftware.Steam', 'Steam', True, 'flathub')
        self.assertEqual(app_preview(app).argv, ['flatpak','info','com.valvesoftware.Steam'])
        other=SelectedApp('org.example.Other','Example',False,'flathub')
        self.assertEqual(app_preview(other).argv,
                         ['flatpak','remote-info','flathub','org.example.Other'])
        self.assertFalse(app_preview(other).changes)

    def test_combine_installed_app_with_real_folder(self):
        app=SelectedApp('com.valvesoftware.Steam','Steam',True)
        with tempfile.TemporaryDirectory(prefix='ult v31') as base:
            root=Path(base)/'Other Drive'; root.mkdir()
            target=root/'Games & Stuff'; target.mkdir()
            volume=Volume('/dev/sdb1','ext4','2T','Games',str(root))
            cmd,advice=combine_app_storage(app,volume,str(target))
            self.assertEqual(cmd.argv,
                ['flatpak','override','--user',f'--filesystem={target}',app.app_id])
            self.assertTrue(cmd.changes)
            self.assertEqual(shlex.split(cmd.preview),cmd.argv)
            self.assertIn('Settings > Storage', advice)
            self.assertNotIn('mkfs',cmd.preview)
            self.assertNotIn('fstab',cmd.preview)
            with self.assertRaises(ValueError):
                combine_app_storage(app,volume,base)
            with self.assertRaises(ValueError):
                combine_app_storage(app,volume,None)

    def test_uninstalled_app_cannot_get_unwanted_access(self):
        app=SelectedApp('org.example.App','Example',False)
        with tempfile.TemporaryDirectory() as root:
            volume=Volume('/dev/sdb1','ext4','2T','',root)
            with self.assertRaisesRegex(ValueError,'Install'):
                combine_app_storage(app, volume,root)

    def test_unmounted_volume_only_prepares_mount_no_changes(self):
        app=SelectedApp('org.example.App','Example',True)
        with patch('guided_workflows.shutil.which',return_value='/usr/bin/udisksctl'):
            cmd, notes = combine_app_storage(app,Volume('/dev/sdb3','ntfs','1T','',None))
        self.assertEqual(cmd.argv,['udisksctl','mount','-b','/dev/sdb3'])
        self.assertTrue(cmd.changes)
        self.assertIn('Mount',notes)
        for vol in (Volume('/dev/sdb3;id','ext4','1T','',None),
                    Volume('/dev/sdb3','swap','1T','',None)):
            with self.assertRaises(ValueError):combine_app_storage(app,vol)

    def test_generic_app_no_fake_library_setting(self):
        app=SelectedApp('org.example.App','Example',True)
        with tempfile.TemporaryDirectory() as root:
            cmd,helptext=combine_app_storage(app,Volume('/dev/sdb1','ext4','','',root),root)
            self.assertIn('--filesystem='+root,cmd.argv)
            self.assertNotIn('Steam',helptext)
            self.assertNotIn('install',cmd.argv)

    def test_gui_categories_and_multi_click_hooks(self):
        root=Path(__file__).resolve().parents[1]
        app=(root/'app.py').read_text()
        ui=(root/'studio_ui.py').read_text()
        self.assertIn("('All installed commands', 'Browse installed commands…'",app)
        self.assertIn("('Extra', 'Steam → Mount → Disk → Folder…'",app)
        self.assertNotIn("('Mix & Match',",app)
        self.assertLess(app.index("('All installed commands', 'Browse"),
                        app.index("('Extra', 'Steam"))
        self.assertIn("('Systeem','HDD/SSD-map kiezen…','disk_picker')",app)
        self.assertIn("value.argv[:2] == ['lsblk', '-f']", app)
        self.assertIn('self.picked_app(app, app_preview(app, term))',app)
        self.assertIn('self.stage(cmd, keep_app=True)',app)
        self.assertIn('self.show_app_suggestion',app)
        self.assertIn("self.selected_app = None\n        self.update_app_context()",app)
        self.assertIn("self.set_title(L('Steam storage helper'))",ui)
        self.assertEqual(tr('Browse installed commands…','nl'),
                         'Geïnstalleerde commando’s bekijken…')
        ast.parse(app)

if __name__=='__main__': unittest.main()
