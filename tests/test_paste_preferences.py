"""Headless regression tests: confirmation opt-out and XDG persistence."""
import ast
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import paste_preferences
from i18n import tr

ROOT = Path(__file__).resolve().parents[1]


class PreferenceStorageTests(unittest.TestCase):
    def test_default_and_corruption_fail_safe_to_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'preferences.json'
            self.assertTrue(paste_preferences.paste_confirmation_enabled(target))
            target.write_text('not json')
            self.assertTrue(paste_preferences.paste_confirmation_enabled(target))
            target.write_text('{"confirm_paste": "false"}')
            self.assertTrue(paste_preferences.paste_confirmation_enabled(target))
            target.write_text('{"confirm_paste": null}')
            self.assertTrue(paste_preferences.paste_confirmation_enabled(target))
            target.write_text('{"confirm_paste": false}')
            self.assertFalse(paste_preferences.paste_confirmation_enabled(target))

    def test_persist_opt_out_then_reenable_across_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'app' / 'preferences.json'
            paste_preferences.set_paste_confirmation_enabled(False, target)
            self.assertFalse(paste_preferences.paste_confirmation_enabled(target))
            self.assertEqual(json.loads(target.read_text()), {'confirm_paste': False})
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            paste_preferences.set_paste_confirmation_enabled(True, target)
            self.assertTrue(paste_preferences.paste_confirmation_enabled(target))
            self.assertEqual(list(target.parent.glob('.preferences-*')), [])

    def test_flatpak_xdg_config_and_native_home_fallback(self):
        self.assertEqual(
            paste_preferences.preferences_path({'XDG_CONFIG_HOME':'/tmp/flatpak-private'}),
            Path('/tmp/flatpak-private/universal-linux-terminal/preferences.json'))
        self.assertEqual(
            paste_preferences.preferences_path({'XDG_CONFIG_HOME':'relative'}, home='/tmp/tester'),
            Path('/tmp/tester/.config/universal-linux-terminal/preferences.json'))

    def test_does_not_create_prefs_file_just_by_reading(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp) / 'config' / 'preferences.json'
            self.assertTrue(paste_preferences.paste_confirmation_enabled(target))
            self.assertFalse(target.exists())


class StubCheckButton:
    def __init__(self, label):
        self.label = label
        self.active = False
    def set_tooltip_text(self, text): self.tip=text
    def set_margin_start(self, _): pass
    def set_margin_bottom(self, _): pass
    def show(self): pass
    def get_active(self): return self.active


class StubDialog:
    def __init__(self, owner, response, checked):
        self.owner, self.response, self.checked = owner, response, checked
        self.area = SimpleNamespace(pack_start=self.add_child)
        self.destroyed = False
    def get_content_area(self): return self.area
    def add_child(self, child, *_):
        self.owner.check = child
        child.active = self.checked
    def run(self): return self.response
    def destroy(self): self.destroyed = True


class ConfirmationGuiLogicTests(unittest.TestCase):
    @staticmethod
    def get_method(method_name, fake_gtk, check_pref, save_pref):
        root = ast.parse((ROOT / 'terminal.py').read_text())
        clazz = next(n for n in root.body if isinstance(n, ast.ClassDef) and n.name == 'TerminalTab')
        meth = next(n for n in clazz.body if isinstance(n, ast.FunctionDef) and n.name == method_name)
        namespace = dict(Gtk=fake_gtk, L=lambda x: tr(x, 'en'),
                         paste_confirmation_enabled=check_pref,
                         set_paste_confirmation_enabled=save_pref)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[meth], type_ignores=[])),
                     '<paste settings test>', 'exec'), namespace)
        return namespace[method_name]

    def test_yes_checked_remembers_and_later_pastes_without_dialog(self):
        saves=[]
        state=[True]
        calls=[]
        fake_gtk=SimpleNamespace(
            MessageType=SimpleNamespace(QUESTION=1), ButtonsType=SimpleNamespace(YES_NO=2),
            ResponseType=SimpleNamespace(YES=1), CheckButton=StubCheckButton)
        def dialog(**kwargs):
            calls.append(kwargs)
            result=StubDialog(owner, 1, True)
            calls.append(result)
            return result
        fake_gtk.MessageDialog=dialog
        def save(value):
            saves.append(value); state[0]=value
        owner=SimpleNamespace(message=Mock())
        fake=SimpleNamespace(owner=owner)
        method=self.get_method('confirm_clipboard_paste',fake_gtk,
                               lambda:state[0],save)
        self.assertTrue(method(fake, 'echo ONE\necho TWO'))
        self.assertEqual(saves,[False])
        self.assertEqual(owner.check.label, "Don't show this warning again")
        self.assertEqual(calls[0]['buttons'],2)
        self.assertTrue(calls[1].destroyed)
        self.assertTrue(method(fake, 'echo THREE'))
        self.assertEqual(len(calls),2,'second paste should not display dialog')

    def test_no_with_checkbox_does_not_save(self):
        saves=[]
        fake_gtk=SimpleNamespace(
            MessageType=SimpleNamespace(QUESTION=1), ButtonsType=SimpleNamespace(YES_NO=2),
            ResponseType=SimpleNamespace(YES=1), CheckButton=StubCheckButton)
        owner=SimpleNamespace(message=Mock())
        fake_gtk.MessageDialog=lambda **kwargs: StubDialog(owner, 0, True)
        method=self.get_method('confirm_clipboard_paste',fake_gtk,
                               lambda:True,saves.append)
        self.assertFalse(method(SimpleNamespace(owner=owner),'rm -rf /tmp/example'))
        self.assertEqual(saves,[])

    def test_yes_unchecked_does_not_save(self):
        saves=[]
        fake_gtk=SimpleNamespace(
            MessageType=SimpleNamespace(QUESTION=1), ButtonsType=SimpleNamespace(YES_NO=2),
            ResponseType=SimpleNamespace(YES=1), CheckButton=StubCheckButton)
        owner=SimpleNamespace(message=Mock())
        fake_gtk.MessageDialog=lambda **kwargs: StubDialog(owner, 1, False)
        method=self.get_method('confirm_clipboard_paste',fake_gtk,
                               lambda:True,saves.append)
        self.assertTrue(method(SimpleNamespace(owner=owner),'echo fine'))
        self.assertEqual(saves,[])

    def test_context_menu_can_reenable_paste_warning(self):
        saves=[]
        fake_gtk=SimpleNamespace()
        method=self.get_method('set_paste_warning',fake_gtk,lambda:False,saves.append)
        self.assertTrue(method(SimpleNamespace(owner=SimpleNamespace(message=Mock())),True))
        self.assertEqual(saves,[True])
        source=(ROOT/'terminal.py').read_text()
        self.assertIn("Gtk.CheckMenuItem(label=L('Plakwaarschuwing tonen'))", source)
        self.assertIn('self.set_paste_warning(requested)', source)


if __name__ == '__main__':
    unittest.main()
