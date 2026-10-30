"""Monitor-resize, UI header and shell-banner regression tests (without GTK)."""
import ast
import unittest
from pathlib import Path
from window_geometry import fit_dimensions

BASE = Path(__file__).resolve().parents[1]


class WindowGeometryTests(unittest.TestCase):
    def test_screen_sizes_and_sidebar(self):
        self.assertEqual(fit_dimensions(1920, 1040), (948, 968, 340))
        self.assertEqual(fit_dimensions(2560, 1400), (1268, 1328, 340))
        self.assertEqual(fit_dimensions(1366, 728), (671, 656, 242))
        self.assertEqual(fit_dimensions(1024, 768), (500, 696, 210))
        self.assertEqual(fit_dimensions(800, 600), (388, 528, 194))

    def test_odd_width_and_nonpositive(self):
        self.assertEqual(fit_dimensions(1919, 1080)[:2], (947, 1008))
        for width, height in [(0, 1080), (1920, 0), (-1, 1080)]:
            with self.subTest(size=(width, height)):
                with self.assertRaises(ValueError):
                    fit_dimensions(width, height)

    def test_regular_shell_interactive_and_nonlogin(self):
        source = (BASE/'app.py').read_text()
        tree = ast.parse(source)
        cls = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == 'Window')
        method = next(item for item in cls.body if isinstance(item, ast.FunctionDef) and item.name == 'shell')
        calls = [n for n in ast.walk(method) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr == 'spawn']
        self.assertEqual(len(calls), 1)
        args = calls[0].args[0]
        self.assertIsInstance(args, ast.Name)
        self.assertEqual(args.id, 'argv')
        self.assertIn('host_shell_argv(shell_path, self.workdir)', ast.get_source_segment(source, method))
        self.assertNotIn("'-l'", ast.get_source_segment(source, method))

    def test_no_visible_app_header_or_extra_terminal_command_label(self):
        app = (BASE/'app.py').read_text()
        term = (BASE/'terminal.py').read_text()
        self.assertNotIn("outer.pack_start(title", app)
        self.assertNotIn("outer.pack_start(self.status", app)
        self.assertIn('if guided:', term)
        self.assertNotIn("Gtk.Button(label='Commando kopiëren')", app)
        self.assertNotIn("Gtk.Button(label='Terminal openen')", app)
        self.assertIn('monitor.get_workarea()', app)
        self.assertIn("GLib.timeout_add_seconds(3, self._refresh_workarea)", app)


if __name__ == '__main__':
    unittest.main()
