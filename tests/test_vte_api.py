"""Regression tests: VTE 2.91 binding bug and clean application exit."""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]

class VteApiRegression(unittest.TestCase):
    @staticmethod
    def start_method_ast():
        tree = ast.parse((ROOT/'terminal.py').read_text(encoding='utf-8'))
        klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TerminalTab')
        return next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == 'start')

    def test_spawn_async_vte_2_91_positional_contract(self):
        # Fedora/Bazzite/PyGObject exposes an additional child_setup_data
        # argument.  A 9-argument call shifted `None` into the timeout slot.
        start = self.start_method_ast()
        calls = [n for n in ast.walk(start) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and n.func.attr == 'spawn_async']
        self.assertEqual(len(calls), 1)
        args = calls[0].args
        self.assertEqual(len(args), 10)
        self.assertIsInstance(args[6], ast.Constant)
        self.assertIsNone(args[6].value)  # child_setup_data
        self.assertIsInstance(args[7], ast.UnaryOp)
        self.assertIsInstance(args[7].op, ast.USub)
        self.assertEqual(args[7].operand.value, 1)  # timeout
        self.assertIsInstance(args[9], ast.Attribute)
        self.assertEqual(args[9].attr, 'spawned')

    def test_spawn_against_simulated_bazzite_binding(self):
        # Execute the real TerminalTab.start() method with a test double for
        # the PyGObject binding, independent of GUI packages.  Older static
        # tests accepted the broken 9-arg call; this catches it.
        start = self.start_method_ast()
        namespace = {
            'Vte': SimpleNamespace(PtyFlags=SimpleNamespace(DEFAULT=1)),
            'GLib': SimpleNamespace(SpawnFlags=SimpleNamespace(SEARCH_PATH=2), Error=Exception),
        }
        module = ast.fix_missing_locations(ast.Module(body=[start], type_ignores=[]))
        exec(compile(module, '<actual TerminalTab.start>', 'exec'), namespace)
        calls = []
        def spawn_async(*args):
            calls.append(args)
            if len(args) != 10 or args[7] != -1:
                raise TypeError('Argument 9 does not allow None as a value')
            assert args[8] is None
            assert callable(args[9])
        term = SimpleNamespace(spawn_async=spawn_async, grab_focus=lambda: None)
        class FakeTab:
            cwd = '/tmp'
            argv = ['/bin/bash','-l']
            spawn_pending = False
            def __init__(self): self.term = term; self.failures = []
            def spawned(self, *args): pass
            def finish(self, error): self.failures.append(error)
        tab=FakeTab()
        namespace['start'](tab)
        self.assertTrue(tab.spawn_pending)
        self.assertFalse(tab.failures)
        self.assertEqual(len(calls), 1)

    def test_clean_sigint_catching_and_normal_window_close(self):
        text = (ROOT/'app.py').read_text(encoding='utf-8')
        self.assertIn('GLibUnix.signal_add', text)
        self.assertIn('except KeyboardInterrupt:', text)
        self.assertIn('Gtk.main_quit()', text)
        self.assertIn('def shutdown(self)', text)

if __name__ == '__main__':
    unittest.main()
