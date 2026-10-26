"""Extensible, typed composition of Linux commands; no execution, no GTK.

A command is assembled from selections and registered semantic rules, rather
than concatenating strings or treating an executable discovered in PATH as a
safe schema. Third-party profiles can be registered after review.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
import ipaddress
import re
import shutil
from host_bridge import in_flatpak, host_which

from core import Command, validate_text
from context_composer import APP_ID, SelectedApp, combine_app_storage
from guided_workflows import Volume, DEVICE, SAFE_FS, prepare_volume_mount
from distro_support import _PKG

KINDS = frozenset(('app', 'volume', 'folder', 'file', 'service', 'host',
                   'container', 'interface', 'package'))

@dataclass(frozen=True)
class Subject:
    kind: str
    value: object
    label: str = ''

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError('Unknown selection type')
        if self.label:
            validate_text(self.label)
        value = self.value
        if self.kind == 'app':
            if not isinstance(value, SelectedApp):
                raise ValueError('Choose an actual Flatpak app')
        elif self.kind == 'volume':
            if (not isinstance(value, Volume) or not DEVICE.fullmatch(value.path)
                    or '..' in value.path or value.fstype not in SAFE_FS):
                raise ValueError('Choose a supported disk partition')
        elif self.kind in ('folder', 'file'):
            if not isinstance(value, str):
                raise ValueError('Choose a local path')
            validate_text(value)
            try:
                path = Path(value).expanduser().resolve(strict=True)
            except OSError as exc:
                raise ValueError('Choose an existing accessible file or folder') from exc
            if (self.kind == 'folder' and not path.is_dir() or
                    self.kind == 'file' and not path.is_file()):
                raise ValueError('The selected path has the wrong type')
            object.__setattr__(self, 'value', str(path))
        elif self.kind == 'service':
            if not isinstance(value, str):
                raise ValueError('Choose a systemd service')
            value = validate_text(value.strip())
            if not value.endswith('.service'):
                value += '.service'
            if not re.fullmatch(r'[A-Za-z0-9_.@\\-]+\.service', value) or value.startswith(('-', '.')):
                raise ValueError('Invalid service unit name')
            object.__setattr__(self, 'value', value)
        elif self.kind == 'host':
            if not isinstance(value, str):
                raise ValueError('Choose a host name')
            value = validate_text(value.strip())
            try:
                ipaddress.ip_address(value)
            except ValueError:
                if (len(value) > 253 or not all(
                        re.fullmatch(r'[A-Za-z0-9_](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9_])?', part)
                        for part in value.rstrip('.').split('.'))):
                    raise ValueError('Invalid host name or IP address')
            object.__setattr__(self, 'value', value)
        elif self.kind == 'package':
            if not isinstance(value, str) or not _PKG.fullmatch(value):
                raise ValueError('Invalid native package name')
        elif self.kind == 'container':
            if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value):
                raise ValueError('Invalid container name')
        elif self.kind == 'interface':
            if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.:@-]{0,63}', value):
                raise ValueError('Invalid interface name')


@dataclass(frozen=True)
class Rule:
    key: str
    title: str
    description: str
    required: tuple[str, ...]
    tool: str
    factory: Callable[[dict[str, Subject]], tuple[Command, str]]
    risk: str = 'read'  # read | changes
    guard: Callable[[dict[str, Subject]], bool] = lambda _: True

    def __post_init__(self):
        if (not self.key or not self.required or any(k not in KINDS for k in self.required)
                or self.risk not in ('read', 'changes')):
            raise ValueError('Invalid combination rule')


@dataclass(frozen=True)
class Suggestion:
    key: str
    title: str
    description: str
    missing: tuple[str, ...]
    risk: str
    available: bool


class CompositionEngine:
    """Per-window draft; knows semantic inputs, never executes a command."""
    def __init__(self, rules=()):
        self.rules: dict[str, Rule] = {}
        self.selected: dict[str, Subject] = {}
        for rule in rules:
            self.register(rule)

    def register(self, rule: Rule):
        if not isinstance(rule, Rule) or rule.key in self.rules:
            raise ValueError('Duplicate or invalid combination rule')
        self.rules[rule.key] = rule

    def clear(self):
        self.selected.clear()

    def choose(self, subject: Subject):
        if not isinstance(subject, Subject):
            raise ValueError('Expected a typed selection')
        # App + volume + folder is the cross-category draft. Other subjects
        # start a separate semantic task (no accidental stale composition).
        if subject.kind not in ('app', 'volume', 'folder'):
            self.clear()
        elif subject.kind == 'app':
            self.clear()
        elif subject.kind == 'volume':
            self.selected.pop('folder', None)
            if 'app' not in self.selected:
                self.clear()
        elif subject.kind == 'folder':
            if 'app' not in self.selected and 'volume' not in self.selected:
                self.clear()
        self.selected[subject.kind] = subject
        return subject

    def suggestions(self, include_incomplete=True, include_unavailable=False):
        result = []
        for rule in self.rules.values():
            if not set(rule.required) & self.selected.keys():
                continue
            missing = tuple(k for k in rule.required if k not in self.selected)
            if missing and not include_incomplete:
                continue
            if not missing and not rule.guard(self.selected):
                continue
            available = not rule.tool or (host_which(rule.tool) if in_flatpak() else shutil.which(rule.tool)) is not None
            if not available and not include_unavailable:
                continue
            result.append(Suggestion(rule.key, rule.title, rule.description,
                                     missing, rule.risk, available))
        return result

    def compose(self, key: str):
        if key not in self.rules:
            raise ValueError('Unknown combination rule')
        rule = self.rules[key]
        missing = [k for k in rule.required if k not in self.selected]
        if missing:
            raise ValueError('Choose first: ' + ', '.join(missing))
        if not rule.guard(self.selected):
            raise ValueError('This combination does not apply to the selection')
        if rule.tool and not (host_which(rule.tool) if in_flatpak() else shutil.which(rule.tool)):
            raise ValueError('Required tool is not installed: ' + rule.tool)
        command, note = rule.factory(self.selected.copy())
        if not isinstance(command, Command) or not isinstance(note, str):
            raise ValueError('Invalid recipe output')
        if rule.risk == 'read' and command.changes:
            raise ValueError('Read-only rule produced a modifying command')
        if not command.argv or any(not isinstance(s, str) for s in command.argv):
            raise ValueError('Invalid command arguments')
        for part in command.argv:
            validate_text(part)
        # Ensures shell preview quoting is always generated, not concatenated.
        _ = command.preview
        return command, note


def _build(title, argv, description='', changes=False, note=''):
    return (Command(title, argv, description or title, changes), note)


def default_engine():
    rules: list[Rule] = []
    def add(key, title, requires, tool, factory, *, description='', risk='read', guard=None):
        rules.append(Rule(key, title, description or title, tuple(requires), tool,
                          factory, risk, guard or (lambda _: True)))

    add('app.info', 'Show app information', ('app',), 'flatpak',
        lambda c: _build('Flatpak app information',
            (['flatpak', 'info', c['app'].value.app_id] if c['app'].value.installed
             else ['flatpak', 'remote-info', c['app'].value.origin, c['app'].value.app_id])),
        description='Show details of this Flatpak app.',
        guard=lambda c: c['app'].value.installed or bool(c['app'].value.origin))
    add('app.permissions', 'Show app permissions', ('app',), 'flatpak',
        lambda c: _build('Flatpak app permissions', ['flatpak', 'info', '--show-permissions', c['app'].value.app_id]),
        description='Show which access this Flatpak app declares.',
        guard=lambda c: c['app'].value.installed)
    add('app.folder_access', 'Allow app access to folder on selected disk',
        ('app','volume','folder'), 'flatpak',
        lambda c: combine_app_storage(c['app'].value,c['volume'].value,c['folder'].value),
        description='Review a Flatpak permission change for an existing folder.',risk='changes',
        guard=lambda c: c['app'].value.installed and c['volume'].value.mountpoint is not None)
    add('volume.details', 'Show disk partition details', ('volume',), 'lsblk',
        lambda c: _build('Disk details', ['lsblk', '-f', '--', c['volume'].value.path]),
        description='Inspect the selected volume without writing anything.')
    add('volume.free', 'Show free space on disk', ('volume',), 'df',
        lambda c: _build('Disk free space', ['df', '-h', '--', c['volume'].value.mountpoint]),
        description='Show free space on the selected mounted volume.',
        guard=lambda c: bool(c['volume'].value.mountpoint))
    add('volume.mount', 'Prepare mounting the disk', ('volume',), 'udisksctl',
        lambda c: (prepare_volume_mount(c['volume'].value),
                   'This may ask for desktop authorization. Mounting is never automatic.'),
        description='Prepare a desktop mount command; never format or modify partitions.', risk='changes',
        guard=lambda c: c['volume'].value.mountpoint is None)

    add('folder.size', 'Calculate folder size', ('folder',), 'du',
        lambda c: _build('Folder size', ['du', '-sh', '--', c['folder'].value]))
    add('folder.list', 'List folder contents', ('folder',), 'ls',
        lambda c: _build('Folder contents', ['ls','-la','--',c['folder'].value]))
    add('file.hash', 'Calculate SHA256 hash', ('file',), 'sha256sum',
        lambda c: _build('File SHA256', ['sha256sum','--',c['file'].value]))
    add('file.stat', 'Show file details', ('file',), 'stat',
        lambda c: _build('File metadata', ['stat','--',c['file'].value]))

    add('service.status', 'Show service status', ('service',), 'systemctl',
        lambda c: _build('Service status', ['systemctl','--no-pager','status',c['service'].value]))
    add('service.logs', 'Show service logs', ('service',), 'journalctl',
        lambda c: _build('Service logs', ['journalctl','--no-pager','-u',c['service'].value,'-n','100']))
    add('service.errors', 'Show service errors', ('service',), 'journalctl',
        lambda c: _build('Service errors', ['journalctl','--no-pager','-u',c['service'].value,'-p','err','-n','100']))
    add('host.ping', 'Ping host (four packets)', ('host',), 'ping',
        lambda c: _build('Ping host', ['ping','-c','4', '--', c['host'].value]))
    add('host.dns', 'Look up host addresses', ('host',), 'getent',
        lambda c: _build('DNS lookup', ['getent','ahosts',c['host'].value]))
    add('container.inspect', 'Inspect container', ('container',), 'podman',
        lambda c: _build('Container details', ['podman','inspect','--',c['container'].value]))
    add('container.logs', 'Show container logs', ('container',), 'podman',
        lambda c: _build('Container logs', ['podman','logs','--',c['container'].value]))
    add('interface.address', 'Show network interface addresses', ('interface',), 'ip',
        lambda c: _build('Network interface addresses', ['ip','address','show','dev',c['interface'].value]))
    add('interface.stats', 'Show network interface statistics', ('interface',), 'ip',
        lambda c: _build('Network interface statistics', ['ip','-s','link','show','dev',c['interface'].value]))
    return CompositionEngine(rules)


def register_native_rules(engine, profile):
    """Extend an existing engine with supported, distro-aware package actions.

    Uses the same strict Subject/Rule system as the established app/disk engine.
    No distro-specific shell fragments are concatenated or executed.
    """
    if profile.backend in ('none', 'rpm-ostree'):
        return engine
    from core import native_command
    native_tool = {'apt':'apt-cache','dnf':'dnf' if 'dnf' in profile.tools else 'dnf5',
                   'pacman':'pacman','zypper':'zypper'}[profile.backend]
    for action, title, risk in (
        ('search','Search this native package','read'),
        ('info','Show this package information','read'),
        ('install','Prepare installation of this package','changes'),
    ):
        if risk == 'changes' and (profile.atomic or profile.sandbox or not profile.has('sudo')):
            continue
        engine.register(Rule(
            'package.' + action, title,
            'Build a command for the detected package manager.',
            ('package',), native_tool,
            lambda c, operation=action: (
                native_command(operation, c['package'].value, profile),
                'Review the command and package manager confirmation before running.'),
            risk,
        ))
    return engine
