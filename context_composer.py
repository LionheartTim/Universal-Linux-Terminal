"""Safe, read-only contextual command composition.

The only *supported* cross-category recipe here is a selected, installed
Flatpak app + chosen storage volume + existing folder. Anything else remains
an independent command; never blindly concatenate shell statements.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
from core import Command, validate_text
from guided_workflows import Volume, check_folder, prepare_volume_mount, SAFE_FS, DEVICE

APP_ID = re.compile(r'^[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z_][A-Za-z0-9_-]*){1,}$')
REMOTE = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_.-]*$')


@dataclass(frozen=True)
class SelectedApp:
    app_id: str
    display_name: str
    installed: bool
    origin: str = ''

    def __post_init__(self):
        if not APP_ID.fullmatch(self.app_id):
            raise ValueError('Invalid Flatpak app ID')
        validate_text(self.display_name)
        if self.origin and not REMOTE.fullmatch(self.origin):
            raise ValueError('Invalid Flatpak remote')


def parse_flatpak_search(text):
    """Parse --columns=name,application,version,remotes TSV; ignore headings.

    The search output is localized on some Flatpak versions, so validate the
    actual app ID rather than depending on any particular header spelling.
    """
    found = []
    seen = set()
    for line in text.splitlines():
        values = line.split('\t')
        if len(values) != 4:
            continue
        name, app_id, version, origins = (x.strip() for x in values)
        if not APP_ID.fullmatch(app_id) or app_id in seen:
            continue
        origin = next((x for x in re.split(r'[,\s]+', origins)
                       if REMOTE.fullmatch(x)), '')
        if any(ord(ch) < 32 for ch in name + version + origin):
            continue
        seen.add(app_id)
        found.append((name or app_id, app_id, version, origin))
    return found


def app_preview(app: SelectedApp, search_term=''):
    """Show an informative, read-only command for the selected app."""
    if app.installed:
        return Command('Selected app: ' + app.display_name,
                       ['flatpak', 'info', app.app_id],
                       'Installed app selected. Choose HDD/SSD next to prepare folder access.')
    if app.origin:
        return Command('Selected app: ' + app.display_name,
                       ['flatpak', 'remote-info', app.origin, app.app_id],
                       'App is not installed. You can inspect it, but install it before granting disk access.')
    return Command('Selected app: ' + app.display_name,
                   ['flatpak', 'search', validate_text(search_term.strip() or app.app_id)],
                   'Select an installed app before preparing folder access.')


def combine_app_storage(app: SelectedApp, volume: Volume, folder=None):
    """Construct a single checked command, never execute it.

    For unmounted partitions, prepare a *mount* command first. Once the user
    has mounted the drive, the same app selection can be used again.
    """
    if not isinstance(volume, Volume) or volume.fstype not in SAFE_FS or not DEVICE.fullmatch(volume.path):
        raise ValueError('Select a supported data partition')
    if volume.mountpoint is None:
        # Use a generic mount recipe: contextual composition is not tied to Steam.
        command = prepare_volume_mount(volume)
        return command, ('Mount this partition first. Then select the app and the drive again '
                         'and choose a folder. This does not format the disk.')
    if not app.installed:
        raise ValueError('Install this Flatpak app first, then choose the drive again.')
    if not folder:
        raise ValueError('Choose an existing folder on the selected drive.')
    path = check_folder(volume, folder)
    cmd = Command('Allow folder access for ' + app.display_name,
                  ['flatpak', 'override', '--user', '--filesystem=' + path, app.app_id],
                  'Grant this installed Flatpak app access to the selected folder. '
                  'This does NOT move the app or change its own download/library settings.', True)
    advice = ('Review the permission command and press Enter yourself. Restart the app afterward. '
              'If the app has its own storage/library settings, set the folder there as well.')
    if app.app_id == 'com.valvesoftware.Steam':
        advice += (' For Steam: open Settings > Storage, add this folder, and set '
                   'the default library inside Steam. This command cannot change that setting.')
    return cmd, advice
