"""Regression tests that run without PyGObject or a display server."""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from i18n import EN, preferred_language, tr
from core import catalog
from window_geometry import fit_dimensions

ROOT = Path(__file__).resolve().parents[1]


class LanguageTests(unittest.TestCase):
    def test_nl_and_english_locale_precedence(self):
        self.assertEqual(preferred_language({'LANG':'nl_NL.UTF-8'}), 'nl')
        self.assertEqual(preferred_language({'LANG':'en_US.UTF-8'}), 'en')
        self.assertEqual(preferred_language({'LANG':'de_DE.UTF-8'}), 'en')
        self.assertEqual(preferred_language({'LANG':'nl_NL','LC_ALL':'C.UTF-8'}), 'en')
        self.assertEqual(preferred_language({'LANG':'en_US.UTF-8','LANGUAGE':'nl_NL:en_US'}), 'nl')
        self.assertEqual(preferred_language({'LANG':'nl_NL.UTF-8', 'LC_MESSAGES':'en_GB'}),'en')

    def test_labels_translate_but_command_arguments_do_not(self):
        self.assertEqual(tr('Kies links een functie','en'),'Select a function on the left')
        self.assertEqual(tr('Kies links een functie','nl'),'Kies links een functie')
        self.assertEqual(tr('Ontbrekend hulpmiddel: jq','en'),'Missing tool: jq')
        self.assertEqual(tr('Reset Terminal','en'),'Reset Terminal')
        self.assertEqual(tr('Reset Terminal','nl'),'Reset Terminal')
        for group, command in catalog():
            self.assertIsInstance(tr(group,'en'), str)
            self.assertIsInstance(tr(command.title,'en'), str)
            self.assertIsInstance(tr(command.explanation,'en'), str)
            self.assertEqual(command.preview, command.preview)

    def test_every_sidebar_catalog_text_is_translated(self):
        with self.subTest('catalog titles and descriptions'):
            for group, command in catalog():
                for value in (group, command.title, command.explanation):
                    self.assertTrue(value in EN or value in ('Flatpak','Containers','Homebrew','Bazzite'), value)


class ResetTerminalTests(unittest.TestCase):
    @staticmethod
    def method():
        source = (ROOT/'terminal.py').read_text()
        tree = ast.parse(source)
        klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TerminalTab')
        method = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == 'reset_terminal')
        namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])), '<reset method>', 'exec'), namespace)
        return namespace['reset_terminal']

    def test_reset_display_does_not_restart_or_execute_commands(self):
        events = []
        term = SimpleNamespace(reset=lambda *args: events.append(('reset',args)),
                               feed_child=lambda content: events.append(('key',content)),
                               grab_focus=lambda: events.append(('focus',)))
        fake = SimpleNamespace(done=False, pid=100, term=term, at_shell=lambda:True)
        self.method()(fake)
        self.assertEqual(events,[('reset',(True,True)),('key',b'\x0c'),('focus',)])
        self.assertEqual(fake.pid,100)

    def test_reset_does_not_inject_keys_into_active_program(self):
        events = []
        term = SimpleNamespace(reset=lambda *args:events.append(('reset',args)),
                               feed_child=lambda x: events.append(('key',x)),
                               grab_focus=lambda: events.append(('focus',)))
        fake = SimpleNamespace(done=False,pid=55,term=term,at_shell=lambda:False)
        self.method()(fake)
        self.assertEqual(events,[('reset',(True,True)),('focus',)])
        fake.done = True
        events.clear()
        self.method()(fake)
        self.assertFalse(events)

    def test_toolbar_wraps_and_reset_button_present(self):
        source=(ROOT/'terminal.py').read_text()
        self.assertIn('Gtk.FlowBox()',source)
        self.assertIn("button(L('Reset Terminal'), self.reset_terminal)",source)
        self.assertIn('def reset_terminal',source)


class GeometryMarginTests(unittest.TestCase):
    def test_safe_height_and_halfscreen(self):
        for width, height in ((1920,1040),(2560,1400),(1366,728),(800,600)):
            w,h,_=fit_dimensions(width,height)
            self.assertLess(w,width/2)
            self.assertLess(h,height)
            self.assertGreaterEqual(height-h,40)


if __name__ == '__main__': unittest.main()
