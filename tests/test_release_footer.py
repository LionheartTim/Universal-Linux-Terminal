"""Headless regressions for the 1.0.1 version/author footer."""

import ast
import unittest
from pathlib import Path

from i18n import tr

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'app.py').read_text(encoding='utf-8')


class ReleaseFooterTests(unittest.TestCase):
    def test_release_number_matches_window_title_and_docs(self):
        module = ast.parse(APP)
        version = next(
            ast.literal_eval(stmt.value)
            for stmt in module.body
            if isinstance(stmt, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == 'VERSION'
                    for t in stmt.targets)
        )
        self.assertEqual(version, '1.0.1')
        self.assertIn("title='Universal Linux Terminal — '+VERSION", APP)
        self.assertTrue((ROOT / 'README.md').read_text().startswith(
            '# Universal Linux Terminal — v1.0.1'))

    def test_footer_belongs_to_main_window_not_scrolling_sidebar(self):
        self.assertIn('outer.pack_start(split, True, True, 0)', APP)
        self.assertIn('outer.pack_end(footer_area, False, False, 0)', APP)
        self.assertIn('footer_area.pack_start(footer, False, False, 0)', APP)
        self.assertIn("Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)", APP)
        self.assertIn("Gtk.Label(label=L('Version') + ' ' + VERSION)", APP)

    def test_author_name_is_only_link_with_correct_destination(self):
        expected = '<a href="https://github.com/LionheartTim">LionheartTim</a>'
        self.assertIn(expected, APP)
        self.assertIn('credit.set_markup(', APP)
        self.assertEqual(APP.count('<a href='), 1)
        self.assertIn("credit.set_tooltip_text('https://github.com/LionheartTim')", APP)

    def test_en_nl_footer_translation(self):
        self.assertEqual(tr('Version', 'en'), 'Version')
        self.assertEqual(tr('Made by', 'en'), 'Made by')
        self.assertEqual(tr('Version', 'nl'), 'Versie')
        self.assertEqual(tr('Made by', 'nl'), 'Gemaakt door')


if __name__ == '__main__':
    unittest.main()
