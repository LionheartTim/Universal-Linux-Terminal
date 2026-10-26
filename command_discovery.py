"""Read-only discovery of commands actually installed on this Linux host.

Shell aliases/functions in the *currently running interactive PTY* are intentionally
not inferred by starting a second shell; those may be session-specific.
"""
from __future__ import annotations
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from host_bridge import in_flatpak, run_host

def _safe_name(name):
    # Linux command file names are not limited to alphanumeric characters.
    # Avoid terminal control characters but keep names like '[', ':', '+', and
    # Unicode names. shlex.join always quotes shell metacharacters.
    return (isinstance(name, str) and 0 < len(name) <= 255 and '/' not in name
            and all(32 <= ord(c) != 127 for c in name))

@dataclass(frozen=True)
class Executable:
    name: str
    kind: str
    location: str


def installed_commands(path=None, builtin_output=None):
    """Fast, non-executing discovery from PATH, plus known Bash builtins.

    PATH can contain symlinks or broken paths.  Names are deduplicated in
    the same left-to-right precedence used for shell executable lookup.
    """
    entries = {}
    if in_flatpak() and path is None and builtin_output is None:
        # Shell-native enumeration sees the host PATH, not the runtime PATH.
        # This queries names only, never executes discovered programs.
        try:
            found = run_host(['/bin/bash', '--noprofile', '--norc', '-c', 'compgen -c'],
                             capture_output=True, text=True, timeout=8, check=True)
            builtins = run_host(['/bin/bash', '--noprofile', '--norc', '-c', 'compgen -b'],
                                capture_output=True, text=True, timeout=5, check=True)
            builtin_names = set(builtins.stdout.splitlines())
            for name in found.stdout.splitlines():
                if _safe_name(name) and name not in entries:
                    kind = 'bash builtin' if name in builtin_names else 'executable'
                    entries[name] = Executable(name, kind, 'Bash' if kind == 'bash builtin' else 'Host PATH')
            return sorted(entries.values(), key=lambda e: e.name.casefold())
        except (OSError, subprocess.SubprocessError, RuntimeError) as error:
            # A broken Flatpak host-output channel must never masquerade as a
            # host with zero programs installed.
            raise RuntimeError('Host command inventory unavailable: ' + str(error)[:250]) from error
    if path is None:
        path = os.environ.get('PATH', os.defpath)
    for directory in path.split(os.pathsep):
        if not directory:
            continue  # do not scan working directory via empty PATH elements
        try:
            with os.scandir(directory) as children:
                for child in children:
                    if child.name in entries or not _safe_name(child.name):
                        continue
                    try:
                        if child.is_file(follow_symlinks=True) and os.access(child.path, os.X_OK):
                            entries[child.name] = Executable(child.name, 'executable', child.path)
                    except OSError:
                        continue
        except (OSError, PermissionError):
            continue
    if builtin_output is None:
        shell = shutil.which('bash')
        if shell:
            try:
                builtin_output = subprocess.run(
                    [shell, '--noprofile', '--norc', '-c', 'compgen -b'],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True, timeout=3, check=False).stdout
            except (OSError, subprocess.TimeoutExpired):
                builtin_output = ''
    for line in (builtin_output or '').splitlines():
        name = line.strip()
        if _safe_name(name) and name not in entries:
            entries[name] = Executable(name, 'bash builtin', 'Bash')
    return sorted(entries.values(), key=lambda e: e.name.casefold())


def prepare_command(name, argument_text='', inventory=None):
    """Safely quote user-selected executable and optional argv; never execute."""
    from core import Command
    if not _safe_name(name):
        raise ValueError('Invalid command name')
    if inventory is not None and name not in {entry.name for entry in inventory}:
        raise ValueError('The selected command is no longer available')
    if any(ord(c) < 32 and c not in ('\t',) for c in argument_text):
        raise ValueError('Arguments must be on one line')
    try:
        args = shlex.split(argument_text)
    except ValueError as error:
        raise ValueError('Invalid quotation marks in arguments') from error
    if any(any(ord(c) < 32 for c in arg) for arg in args):
        raise ValueError('Invalid control character')
    return Command(name, [name, *args],
                   'Discovered on this system. Review all flags and arguments before pressing Enter.')


def search_installed_commands(commands, query, limit=75):
    """Rank live PATH/Bash inventory for the main sidebar's single search.

    Exact names win, then prefix matches, then names containing the query.
    No programs are executed to perform a search.
    """
    term = (query or '').casefold().strip()
    if not term or limit <= 0:
        return []
    matching = (command for command in commands if term in command.name.casefold())
    return sorted(matching, key=lambda c: (
        0 if c.name.casefold() == term else
        1 if c.name.casefold().startswith(term) else 2,
        c.name.casefold()))[:limit]
