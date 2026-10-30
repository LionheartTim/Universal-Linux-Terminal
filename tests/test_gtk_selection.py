"""Regression for GTK3 PyGObject TreeModelFilter/TreeSelection return types.

Run headlessly: mimics the binding's (bool, Gtk.TreeIter) _ResultTuple.
"""
import unittest
from pathlib import Path
from gtk_selection import select_visible_child


class _ResultTuple(tuple):
    """Matching the PyGObject wrapper which caused the Bazzite crash."""


class _TreeIter:
    pass


class _FakeFilter:
    def __init__(self, visible=True):
        self.visible = visible
        self.iter = _TreeIter()
        self.child_seen = None

    def convert_child_iter_to_iter(self, child_iter):
        self.child_seen = child_iter
        return _ResultTuple((self.visible, self.iter if self.visible else None))


class _FakeSelection:
    def __init__(self):
        self.selected = None
        self.calls = 0

    def select_iter(self, filtered_iter):
        # GTK's real select_iter rejects the _ResultTuple received before.
        if not isinstance(filtered_iter, _TreeIter):
            raise TypeError('argument iter: Expected Gtk.TreeIter')
        self.calls += 1
        self.selected = filtered_iter


class GtkFilterSelectionTests(unittest.TestCase):
    def test_visible_initial_command_receives_real_tree_iter(self):
        child = _TreeIter()
        filtered = _FakeFilter()
        selection = _FakeSelection()
        self.assertTrue(select_visible_child(filtered, selection, child))
        self.assertIs(filtered.child_seen, child)
        self.assertIs(selection.selected, filtered.iter)
        self.assertEqual(selection.calls, 1)

    def test_hidden_initial_command_is_not_selected(self):
        filtered = _FakeFilter(visible=False)
        selection = _FakeSelection()
        self.assertFalse(select_visible_child(filtered, selection, _TreeIter()))
        self.assertIsNone(selection.selected)
        self.assertEqual(selection.calls, 0)

    def test_option_window_uses_the_safe_select_helper(self):
        src = (Path(__file__).resolve().parents[1]/'studio_ui.py').read_text()
        self.assertIn('select_visible_child(filtered, selection, child)', src)
        self.assertNotIn('selection.select_iter(filtered_it)', src)


if __name__ == '__main__':
    unittest.main()
