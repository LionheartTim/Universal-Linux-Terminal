"""Universal Linux Terminal window and desktop identity for GTK3."""
from pathlib import Path

APP_ID = 'io.github.LionheartTim.UniversalLinuxTerminal'


def icon_fallback_path():
    """Use the packaged artwork, or the development-tree icon."""
    candidates = (
        Path('/app/share/universal-linux-terminal/icon.png'),
        Path(__file__).resolve().parent / 'flatpak' / 'icons' / '256x256' / (APP_ID + '.png'),
    )
    return next((path for path in candidates if path.is_file()), None)


def configure_application_identity(Gtk, GLib, Gdk):
    """Called before creating the first toplevel window."""
    GLib.set_prgname(APP_ID)
    GLib.set_application_name('Universal Linux Terminal')
    # X11/Wayland GTK3 apps without Gtk.Application rely on a correct
    # program class/name for taskbar grouping and icon matching.
    if hasattr(Gdk, 'set_program_class'):
        Gdk.set_program_class(APP_ID)
    Gtk.Window.set_default_icon_name(APP_ID)


def apply_window_icon(window):
    path = icon_fallback_path()
    if path is not None:
        window.set_icon_from_file(str(path))
    else:
        window.set_icon_name(APP_ID)
