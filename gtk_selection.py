"""Helpers for Gtk.TreeModelFilter iterator results (no GTK imports).

PyGObject 3.x exposes Gtk.TreeModelFilter.convert_child_iter_to_iter()
as a two-item result (success, Gtk.TreeIter). Passing the whole result
instead of the iterator to Gtk.TreeSelection.select_iter() raises TypeError.
"""


def select_visible_child(filtered_model, selection, child_iter):
    """Select a visible child row using the filtered model's real TreeIter.

    Returns False without touching the selection if the child row is not
    visible under the current filter.
    """
    visible, filtered_iter = filtered_model.convert_child_iter_to_iter(child_iter)
    if not visible or filtered_iter is None:
        return False
    selection.select_iter(filtered_iter)
    return True
