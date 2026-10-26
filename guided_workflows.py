"""Pure, testable back end for user-guided disk + Steam library workflows.

Only *prepares* commands; no mount, permission grant, or Steam setting runs here.
"""
from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from core import Command
from host_bridge import run_host, host_which

SAFE_FS = {'ext2', 'ext3', 'ext4', 'btrfs', 'xfs', 'ntfs', 'ntfs3',
           'exfat', 'vfat', 'f2fs', 'zfs', 'hfsplus', 'udf'}
PROTECTED = {'/', '/boot', '/boot/efi', '/efi', '/sysroot', '/var', '/home'}
DEVICE = re.compile(r'^/dev/[A-Za-z0-9_./+-]+$')

@dataclass(frozen=True)
class Volume:
    path: str
    fstype: str
    size: str
    label: str
    mountpoint: str | None


def parse_lsblk(text):
    """Discover mountable data volumes; exclude critical system mounts."""
    data = json.loads(text)
    result = []
    def walk(node):
        if not isinstance(node, dict):
            return
        path = node.get('path')
        fstype = (node.get('fstype') or '').lower()
        mounts = node.get('mountpoints') or []
        if isinstance(mounts, str):
            mounts = [mounts]
        mounts = [v for v in mounts if v and isinstance(v, str)]
        mountpoint = mounts[0] if mounts else None
        is_system = any(p.rstrip('/') in PROTECTED for p in mounts)
        # The user chooses the disk; don't assume which is 'second'.
        if (isinstance(path, str) and DEVICE.fullmatch(path) and '..' not in path
                and fstype in SAFE_FS and not is_system
                and str(node.get('ro', '0')).lower() not in ('1', 'true')
                and str(node.get('type', '')) in ('part', 'disk', 'lvm', 'crypt')):
            result.append(Volume(path, fstype, str(node.get('size') or ''),
                                 str(node.get('label') or ''), mountpoint))
        for child in node.get('children') or []:
            walk(child)
    for drive in data.get('blockdevices') or []:
        walk(drive)
    return result


def scan_volumes():
    if not host_which('lsblk'):
        raise RuntimeError('lsblk is not installed')
    try:
        result = run_host(
            ['lsblk','-J','-o','PATH,TYPE,FSTYPE,SIZE,LABEL,MOUNTPOINTS,RO'],
            capture_output=True, text=True, timeout=8, check=True)
        return parse_lsblk(result.stdout)
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError,
            json.JSONDecodeError) as error:
        raise RuntimeError('Cannot read the disk list: '+str(error)) from error


def check_folder(volume, folder):
    if not volume.mountpoint:
        raise ValueError('Mount this volume before selecting a library folder')
    try:
        mount = Path(volume.mountpoint).resolve(strict=True)
        dest = Path(folder).expanduser().resolve(strict=True)
    except OSError as error:
        raise ValueError('Select an existing accessible folder on the mounted disk') from error
    if not dest.is_dir():
        raise ValueError('Select an existing folder')
    if os.path.commonpath((str(mount), str(dest))) != str(mount):
        raise ValueError('Folder must be on the selected volume')
    # Avoid granting all of / or user home to a Flatpak.
    if str(mount) == '/':
        raise ValueError('Select a separate mounted data volume')
    if not os.access(dest, os.W_OK):
        raise ValueError('You need write permission for the selected folder')
    return str(dest)


def prepare_volume_mount(volume):
    """Prepare a safe generic desktop mount for a listed data partition."""
    if (not isinstance(volume, Volume) or volume.fstype not in SAFE_FS
            or not DEVICE.fullmatch(volume.path) or '..' in volume.path):
        raise ValueError('Select a supported disk partition')
    if volume.mountpoint is not None:
        raise ValueError('This partition is already mounted')
    if not host_which('udisksctl'):
        raise ValueError('udisksctl is not installed; mount this drive with your file manager first')
    return Command('Mount storage volume', ['udisksctl','mount','-b',volume.path],
                   'Mount this partition with your desktop authorization. No formatting is performed.', True)


def build_steam_plan(volume, folder=None, install='flatpak'):
    """Returns command and explanation; Steam default still set in its own UI."""
    if volume.fstype not in SAFE_FS or not DEVICE.fullmatch(volume.path):
        raise ValueError('Select a supported disk partition')
    if install not in ('flatpak', 'native'):
        raise ValueError('Unknown Steam installation type')
    if volume.mountpoint is None:
        return (prepare_volume_mount(volume),
                '1. Review and run the mount command.\n'
                '2. Return to this wizard and select the now-mounted volume and folder.\n'
                '3. Then add the folder in Steam Settings > Storage.')
    if not folder:
        raise ValueError('Select the intended Steam library folder')
    folder = check_folder(volume, folder)
    steps = ('1. Steam must have write access to the chosen folder.\n'
             '2. Fully quit and restart Steam after changing Flatpak permissions.\n'
             '3. In Steam, open Settings > Storage, add the selected folder, '
             'then set the desired default library there.\n'
             '4. Mounting at login may need a separate persistent-mount setup.')
    if install == 'flatpak':
        if not host_which('flatpak'):
            raise ValueError('Flatpak is not installed')
        cmd = Command('Allow Steam library folder',
            ['flatpak','override','--user',f'--filesystem={folder}','com.valvesoftware.Steam'],
            'Give only Steam (Flatpak) read/write access to this exact folder.', True)
        return cmd, steps
    return None, ('The disk and folder are ready. No terminal command can reliably set Steam\'s '
                  'default library. Open Steam > Settings > Storage, add the selected folder '
                  'and set it as the default. Ensure the folder stays mounted after reboot.')


def steam_installed_as_flatpak():
    if not host_which('flatpak'):
        return False
    try:
        r = run_host(['flatpak','info','com.valvesoftware.Steam'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=4, check=False)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False
