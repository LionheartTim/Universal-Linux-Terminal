"""Read-only command descriptions sourced from the *host* documentation.

Used only after the user selects an installed command. The search index itself
must remain fast and must never execute every program. Nothing is guessed from
command names or sent to an external online service.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import re
import subprocess

from host_bridge import run_host, host_which

MAX_DESCRIPTION_BYTES = 96 * 1024


@dataclass(frozen=True)
class DocumentedDescription:
    text: str
    source: str  # 'manual' or 'package' (never silently presented as --help)


def _clean(text: str) -> str:
    """Strip terminal escapes, roff overstrikes and control characters."""
    text = re.sub(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))', '', text)
    # man sometimes highlights with 'c\bc' or 'c\b_'.
    while '\b' in text:
        revised = re.sub(r'.\x08', '', text)
        if revised == text:
            break
        text = revised
    return ''.join(c if c in '\t\n' or ord(c) >= 32 else ' ' for c in text)


def _valid_description(text: str) -> str:
    text = re.sub(r'\s+', ' ', _clean(text)).strip().strip(' -–—')
    if not 4 <= len(text) <= 2000:
        return ''
    # Reject error messages masquerading as the program's purpose.
    if re.match(r'^(?:no manual entry|nothing appropriate|command not found|not found|error:)', text, re.I):
        return ''
    return text[:260]


def _host_read(argv: list[str], timeout: float = 2.5) -> str:
    """Bounded synchronous read; caller already runs off the GTK UI thread."""
    try:
        # /usr/bin/env is standard on supported desktop Linux distributions.
        # Force predictable parser labels without mutating the user's shell.
        result = run_host(['/usr/bin/env', 'LC_ALL=C', *argv],
                          capture_output=True, text=True, timeout=timeout,
                          check=False, stdin=subprocess.DEVNULL)
        if result.returncode != 0:
            return ''
        return (result.stdout or '')[:MAX_DESCRIPTION_BYTES]
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
        return ''


def _parse_whatis(name: str, output: str) -> str:
    for raw in _clean(output).splitlines()[:20]:
        # Entries commonly look like: usbip (8) - manage USB/IP devices
        match = re.match(r'^(.+?)\s*\([^()]{1,12}\)\s*[-–—]\s*(.+)$', raw.strip())
        if not match:
            continue
        listed = [part.strip() for part in match.group(1).split(',')]
        if name not in listed:
            continue
        description = _valid_description(match.group(2))
        if description:
            return description
    return ''


def _parse_manual_name(name: str, output: str) -> str:
    text = _clean(output)
    lines = text.splitlines()[:320]
    in_name = False
    collected = []
    for raw in lines:
        line = raw.strip()
        if not in_name:
            if line.upper() == 'NAME':
                in_name = True
            continue
        if not line:
            if collected:
                break
            continue
        if collected and (line.upper() == line and 2 <= len(line) <= 35):
            break
        collected.append(line)
        if sum(len(c) for c in collected) >= 400:
            break
    paragraph = ' '.join(collected)
    # A rendered NAME section lists the program before the dash.
    match = re.match(r'^(.+?)\s+[-–—]\s+(.+)$', paragraph)
    if not match:
        return ''
    names = [s.strip() for s in match.group(1).split(',')]
    return _valid_description(match.group(2)) if name in names else ''


def _parse_pacman(output: str) -> str:
    match = re.search(r'^Description\s*:\s*(.+?)\s*$', output, re.M)
    return _valid_description(match.group(1)) if match else ''


def _package_description(name: str, location: str) -> str:
    """Package metadata is a last resort and must be labeled as such."""
    path = location if location.startswith('/') else host_which(name)
    if not path or not path.startswith('/'):
        return ''
    # RPM is used by Fedora/Bazzite, RHEL and openSUSE; query-only, no changes.
    # Prefer the genuine package description to an uninformative short label
    # such as 'USB/IP user-space'. A longer paragraph is clipped for the UI.
    rpm = _host_read(['rpm', '-qf', '--qf', '%{DESCRIPTION}\n', path])
    if rpm:
        paragraph = ' '.join(line.strip() for line in rpm.splitlines()[:5] if line.strip())
        candidate = _valid_description(paragraph)
        if candidate:
            return candidate
    rpm = _host_read(['rpm', '-qf', '--qf', '%{SUMMARY}\n', path])
    if rpm:
        candidate = _valid_description(rpm.splitlines()[0])
        if candidate:
            return candidate
    # Debian/Ubuntu derivatives. A path may be owned by more than one package.
    ownership = _host_read(['dpkg-query', '-S', path])
    if ownership:
        package = ownership.splitlines()[0].split(': ', 1)[0].split(',')[0].strip()
        if package and not package.startswith('/'):
            description = _host_read(['dpkg-query', '-W', '-f=${Description}\n', package])
            if description:
                # The Debian Description field begins with the short package
                # label, followed by an explanatory first paragraph.
                paragraphs = []
                for line in description.splitlines()[:8]:
                    if line.strip() == '.':
                        break
                    if not line.strip():
                        break
                    paragraphs.append(line.strip())
                candidate = _valid_description(' '.join(paragraphs))
                if candidate:
                    return candidate
            summary = _host_read(['dpkg-query', '-W', '-f=${binary:Summary}\n', package])
            if summary:
                return _valid_description(summary.splitlines()[0])
    # Arch/Manjaro derivatives: pacman can look up the owner directly.
    info = _host_read(['pacman', '-Qoi', path])
    return _parse_pacman(info) if info else ''


def discover_description(name: str, *, kind: str = 'executable', location: str = '') -> DocumentedDescription | None:
    """Try local manpage descriptions, then package metadata, never invent one.

    This method is only called for selected commands whose --help output lacks
    a useful description. All commands use explicit argv (no shell expansion).
    """
    if kind == 'bash builtin' or not name or '/' in name or '\x00' in name:
        return None
    for request in (['whatis', '--', name], ['man', '-f', '--', name]):
        parsed = _parse_whatis(name, _host_read(request))
        if parsed:
            return DocumentedDescription(parsed, 'manual')
    # Some hosts have manpages but no generated whatis index.
    formatted = _host_read(['man', '-P', 'cat', '--', name], timeout=3.0)
    parsed = _parse_manual_name(name, formatted)
    if parsed:
        return DocumentedDescription(parsed, 'manual')
    package = _package_description(name, location)
    if package:
        return DocumentedDescription(package, 'package')
    return None
