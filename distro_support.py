"""Side-effect-free Linux distribution detection and native package command recipes.

Never infer a package manager solely from PATH: unrelated package tools can coexist.
Never automatically execute or install anything. Immutable/transactional variants are
handled separately from mutable parents such as Fedora or openSUSE.
"""
from dataclasses import dataclass
from pathlib import Path
import os
import re
import shlex
import shutil

_IDENT = re.compile(r'^[a-z0-9._-]+$')
_PKG = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._+@:-]{0,127}$')
_FAMILIES = {
    'debian': {'debian','ubuntu','linuxmint','pop','elementary','zorin','kali','mx','devuan','raspbian','neon','tuxedo','deepin'},
    'fedora': {'fedora','bazzite','nobara','rhel','centos','rocky','almalinux','ol','bluefin','aurora','silverblue','kinoite','sericea'},
    'arch': {'arch','archlinux','manjaro','endeavouros','garuda','cachyos','artix','steamos'},
    'suse': {'opensuse','opensuse-tumbleweed','opensuse-leap','opensuse-microos','sles','sled','suse','sl-micro','sle-micro','microos','aeon','kalpa'},
}
_OSTREE_IDS = {'bazzite','bluefin','aurora','silverblue','kinoite','sericea'}
_TRANSACTIONAL_IDS = {'opensuse-microos','microos','aeon','kalpa','sl-micro','sle-micro'}
# SteamOS uses an Arch-style package database but its root is read-only by default.
# It is not an rpm-ostree deployment and must never be routed to rpm-ostree.
_READONLY_ARCH_IDS = {'steamos'}
_TRANSACTIONAL_VARIANTS = {'transactional','microos','aeon','kalpa'}
_OSTREE_VARIANTS = {'silverblue','kinoite','sericea','onyx','budgie-atomic','sway-atomic','atomic'}


def parse_os_release(text):
    """Parse key=value metadata (no shell execution or variable expansion)."""
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        if not re.fullmatch(r'[A-Z][A-Z0-9_]*', key):
            continue
        value = value.strip()
        if value.startswith(('"', "'")):
            try:
                parts = shlex.split(value, posix=True)
            except ValueError:
                continue
            value = ' '.join(parts)
        result[key] = value
    return result


def _load_release(paths):
    for filename in paths:
        try:
            return parse_os_release(Path(filename).read_text(encoding='utf-8'))
        except OSError:
            continue
    return {}


def _family(ident, likes):
    # Explicit ID wins over ancestral ID_LIKE, even on derivatives.
    for candidate in (ident, *likes):
        for family, ids in _FAMILIES.items():
            if candidate in ids:
                return family
    return 'unknown'


@dataclass(frozen=True)
class DistroProfile:
    ident: str
    name: str
    version: str
    family: str
    backend: str
    atomic: bool
    transactional: bool
    sandbox: bool
    desktop: str
    tools: frozenset

    @property
    def backend_label(self):
        return {'apt':'APT','dnf':'DNF','pacman':'pacman',
                'zypper':'Zypper','rpm-ostree':'rpm-ostree',
                'none':'no native manager detected'}[self.backend]

    def has(self, tool):
        return tool in self.tools


def detect_profile(*, release=None, which=None, exists=None, environ=None):
    """Read os-release and installed capabilities. Injectable for distro tests.

    Sandbox detection stops host-mutation suggestions: package names and program
    paths visible inside a Toolbox/Flatpak are not proof they exist on the host.
    """
    # Inside Flatpak the visible /etc and PATH belong to the runtime.
    # Query the host through Flatpak HostCommand rather than guessing.
    from host_bridge import in_flatpak, host_release, host_path_exists, host_which
    bridge = in_flatpak() and release is None and which is None and exists is None
    if bridge:
        try:
            release = host_release()
            which = host_which
            exists = host_path_exists
        except (OSError, RuntimeError, ValueError, __import__('subprocess').SubprocessError):
            # Don't suggest potentially destructive host commands if we can't
            # establish which distro/backend is really running.
            release = {'ID': 'linux', 'PRETTY_NAME': 'Unverified Flatpak host'}
            which = lambda _tool: None
            exists = lambda _path: False
    if release is None:
        release = _load_release(('/etc/os-release', '/usr/lib/os-release'))
    which = which or shutil.which
    exists = exists or (lambda path: Path(path).exists())
    environ = os.environ if environ is None else environ
    ident = release.get('ID', 'linux').strip().lower()
    if not _IDENT.fullmatch(ident):
        ident = 'linux'
    likes = [x.lower() for x in release.get('ID_LIKE','').split() if _IDENT.fullmatch(x.lower())]
    family = _family(ident, likes)
    variant = release.get('VARIANT_ID','').lower()
    ostree = (ident in _OSTREE_IDS or (family == 'fedora' and
              (variant in _OSTREE_VARIANTS or exists('/run/ostree-booted'))))
    # SUSE products can use 'transactional' or names such as
    # 'server-sap-transactional' in VARIANT_ID. Do not assume that a SUSE
    # system is mutable merely because the ID is the same as regular SLES.
    transactional = (family == 'suse' and
                     (ident in _TRANSACTIONAL_IDS or
                      variant in _TRANSACTIONAL_VARIANTS or
                      variant.endswith('-transactional')))
    readonly_arch = family == 'arch' and ident in _READONLY_ARCH_IDS
    atomic = ostree or transactional or readonly_arch
    sandbox = (False if bridge and release.get('ID') != 'linux' else
               any(exists(x) for x in ('/.flatpak-info','/run/.containerenv','/.dockerenv')))
    candidate_tools = ('apt','apt-cache','dnf','dnf5','pacman','zypper','rpm-ostree',
                       'flatpak','snap','sudo','rpm','ujust','transactional-update')
    tools = frozenset(t for t in candidate_tools if which(t))
    if ostree:
        backend = 'rpm-ostree' if 'rpm-ostree' in tools else 'none'
    elif family == 'debian':
        backend = 'apt' if {'apt','apt-cache'} <= tools else 'none'
    elif family == 'fedora':
        backend = ('dnf' if 'dnf' in tools else 'dnf' if 'dnf5' in tools else 'none')
    elif family == 'arch':
        backend = 'pacman' if 'pacman' in tools else 'none'
    elif family == 'suse':
        backend = 'zypper' if 'zypper' in tools else 'none'
    else:
        backend = 'none'
    pretty = release.get('PRETTY_NAME') or release.get('NAME') or ident.capitalize()
    return DistroProfile(ident, pretty, release.get('VERSION_ID',''), family,
                         backend, atomic, transactional, sandbox,
                         environ.get('XDG_CURRENT_DESKTOP','Unknown'), tools)


@dataclass(frozen=True)
class NativeRecipe:
    title: str
    argv: tuple
    description: str
    changes: bool = False


def native_recipe(profile, action, package=None):
    """Return a verified per-distro argv recipe. No execution or shell strings."""
    backend = profile.backend
    if backend == 'none':
        raise ValueError('No compatible native package manager is available.')
    if action not in ('search','info','installed','updates','install','remove','status'):
        raise ValueError('Unsupported package action.')
    if action in ('search','info','install','remove'):
        if not isinstance(package, str) or not _PKG.fullmatch(package):
            raise ValueError('Enter a valid package name (no spaces, flags, or shell syntax).')
    if profile.sandbox and action in ('install','remove'):
        raise ValueError('Native system changes are disabled inside containers/sandboxes.')
    if profile.atomic and action in ('install','remove'):
        raise ValueError('Atomic/transactional systems need a separate, reviewed installation procedure.')
    # Pacman's package upgrade list is not the system update mechanism on
    # SteamOS; avoid an apparently authoritative but misleading update check.
    if profile.ident in _READONLY_ARCH_IDS and action == 'updates':
        raise ValueError('SteamOS system updates are managed in SteamOS Settings, not by pacman -Qu.')
    tool = 'dnf' if 'dnf' in profile.tools else 'dnf5'
    data = {
        'apt': {
            'search': ('apt-cache','search'), 'info': ('apt-cache','show'),
            'installed': ('apt','list','--installed'), 'updates': ('apt','list','--upgradable'),
            'install': ('sudo','apt','install'), 'remove': ('sudo','apt','remove')},
        'dnf': {
            'search': (tool,'search'), 'info': (tool,'info'),
            'installed': (tool,'list','installed'), 'updates': (tool,'check-update'),
            'install': ('sudo',tool,'install'), 'remove': ('sudo',tool,'remove')},
        'pacman': {
            'search': ('pacman','-Ss'), 'info': ('pacman','-Si'),
            'installed': ('pacman','-Qe'), 'updates': ('pacman','-Qu'),
            'install': ('sudo','pacman','-S'), 'remove': ('sudo','pacman','-R')},
        'zypper': {
            'search': ('zypper','search'), 'info': ('zypper','info'),
            'installed': ('zypper','search','--installed-only'),
            'updates': ('zypper','list-updates'),
            'install': ('sudo','zypper','install'), 'remove': ('sudo','zypper','remove')},
        'rpm-ostree': {
            'status': ('rpm-ostree','status'), 'updates': ('rpm-ostree','upgrade','--check'),
            'installed': ('rpm-ostree','status')},
    }[backend]
    if action not in data:
        raise ValueError('This action is not offered for this type of system.')
    if action in ('install','remove') and 'sudo' not in profile.tools:
        raise ValueError('sudo is not installed; choose an authorized method manually.')
    argv = data[action] + ((package,) if action in ('search','info','install','remove') else ())
    descriptions = {
        'search':'Search repositories for a native package; no changes.',
        'info':'Show information about the named native package; no changes.',
        'installed':'List native packages installed on this system.',
        'updates':'Check available native package updates without installing anything.',
        'status':'Show OS deployment status without changing anything.',
        'install':'Review the package and dependencies before confirming installation in the terminal.',
        'remove':'Review the removal and all dependencies before confirming in the terminal.',
    }
    description = descriptions[action]
    if backend == 'pacman' and action == 'install':
        description += ' On Arch, avoid partial upgrades: perform a full pacman -Syu system update first.'
    if profile.transactional:
        description += ' This is a transactional OS: do not use ordinary package changes on the host.'
    if backend == 'rpm-ostree':
        description += ' OSTree deployments may require reboot; use Flatpak or Distrobox for apps.'
    return NativeRecipe(action.capitalize() + ' (' + profile.backend_label + ')', argv,
                        description, action in ('install','remove'))
