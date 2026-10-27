"""Small, user-scoped preferences for terminal paste confirmation.

Use XDG_CONFIG_HOME (Flatpak app config inside ~/.var/app/<app-id>/config)
when available, otherwise the ordinary per-user ~/.config directory.
Failure to load/corrupt settings is safe: paste confirmation stays enabled.
"""
import json
import os
import tempfile
from pathlib import Path


def preferences_path(environ=None, home=None):
    env = os.environ if environ is None else environ
    xdg = env.get('XDG_CONFIG_HOME', '')
    if xdg and Path(xdg).is_absolute():
        base = Path(xdg)
    else:
        base = Path.home() / '.config' if home is None else Path(home) / '.config'
    return base / 'universal-linux-terminal' / 'preferences.json'


def paste_confirmation_enabled(path=None):
    """Absent, corrupt, or untrusted settings never turn off the warning."""
    target = preferences_path() if path is None else Path(path)
    try:
        contents = json.loads(target.read_text(encoding='utf-8'))
        return contents.get('confirm_paste') is not False if isinstance(contents, dict) else True
    except (OSError, ValueError, UnicodeError):
        return True


def set_paste_confirmation_enabled(enabled, path=None):
    """Atomically persist an explicit choice; report I/O errors to the caller."""
    target = preferences_path() if path is None else Path(path)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=str(target.parent),
                                         prefix='.preferences-', delete=False) as stream:
            temp = Path(stream.name)
            os.fchmod(stream.fileno(), 0o600)
            json.dump({'confirm_paste': bool(enabled)}, stream)
            stream.write('\n')
        os.replace(temp, target)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
