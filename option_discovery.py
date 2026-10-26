"""Bounded CLI help discovery for an explicitly selected program.

Do not run programs while scanning PATH or filtering the search index.
The dialog invokes the selected program with --help when the user selects it;
nonconforming programs may have side effects. A persistent warning remains.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile

from command_discovery import Executable
from host_bridge import in_flatpak, run_host, host_which
from command_descriptions import discover_description

MAX_HELP_BYTES = 128 * 1024
MAX_OPTIONS = 160
MAX_SUMMARY_CHARS = 800  # several wrapped --help lines, still bounded

# Drop terminal-formatting escapes from untrusted help text before displaying
# it in the sidebar. Help is displayed as plain text, never as GTK markup.
_ANSI = re.compile(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))')


@dataclass(frozen=True)
class CommandHelp:
    """Small, read-only documentation snapshot from one selected executable."""
    summary: str
    usage: str
    options: tuple['CliOption', ...]
    summary_source: str = 'help'


def parse_command_help(help_text: str) -> CommandHelp:
    """Extract the program's own description, usage and documented options.

    No generated/invented meanings. A tool with unusual help syntax may
    legitimately lack a description or usage.
    """
    clean = _ANSI.sub('', help_text[:MAX_HELP_BYTES])
    clean = ''.join(c if c == '\n' or c == '\t' or ord(c) >= 32 else ' '
                    for c in clean)
    lines = clean.splitlines()[:2400]
    usage = ''
    summary = ''
    usage_at = -1
    cutoff = len(lines)
    for i, raw in enumerate(lines):
        line = raw.strip()
        if re.match(r'^(options|optional arguments|arguments|flags):\s*$', line, re.I):
            cutoff = i
            break
        if not usage and re.match(r'^usage\s*:', line, re.I):
            usage = line[:250]
            usage_at = i
            if usage.lower() in ('usage:', 'usage :') and i + 1 < len(lines):
                continuation = lines[i + 1].strip()
                if continuation and len(continuation) < 250:
                    usage = 'Usage: ' + continuation
    # Other tools (e.g. systemctl) print a bare synopsis instead of 'Usage:'.
    if not usage:
        for i, raw in enumerate(lines[:min(cutoff, 8)]):
            line = raw.strip()
            if re.match(r'^\S+\s+\[(?:OPTIONS?|--?[A-Za-z])[\w. -]*\].*', line, re.I):
                usage = 'Usage: ' + line[:230]
                usage_at = i
                break
    for i, raw in enumerate(lines[:cutoff]):
        line = raw.strip()
        if (not line or i == usage_at or
            (i == usage_at + 1 and usage.endswith(line)) or
            line.startswith('-') or len(line) > 300 or
            re.match(r'^\S+\s+(?:\[[^\]]+\]\s*)+.*$', line) or
            re.match(r'^(usage|synopsis|options|arguments|examples|commands|flags|description)\s*:', line, re.I) or
            re.match(r'^(copyright|license|report bugs|for more|try |available |help:)', line, re.I)):
            continue
        if re.match(r'^[A-Za-z][\w .-]*\s*$', line) and line.endswith(':'):
            continue
        if len(line) >= 12 and (line.endswith(('.', '!', ',')) or len(line.split()) >= 4):
            # Help text commonly wraps ordinary sentences after words like
            # "and" (lsb_release is a real example), not just after commas.
            # Gather the rest of this contiguous paragraph, stopping at a
            # blank line, usage heading, option, or command-list heading.
            paragraph = [line]
            for following in lines[i + 1:cutoff]:
                part = following.strip()
                if (not part or part.startswith('-') or part.startswith('•') or
                    re.match(r'^(?:usage|synopsis|options?|arguments|flags|commands|examples|description|copyright|license|report bugs|try |help:)(?:\s|:|$)', part, re.I) or
                    re.match(r'^[A-Z][A-Z0-9 _-]{2,40}:?$', part) or
                    re.match(r'^\S+\s+\[(?:OPTIONS?|--?[A-Za-z])', part, re.I)):
                    break
                if len(' '.join(paragraph)) + len(part) + 1 > MAX_SUMMARY_CHARS:
                    break
                paragraph.append(part)
            summary = ' '.join(paragraph)
            break
    # Avoid pulling spurious option-like rows from later examples into the
    # sidebar summary. The existing parser remains responsible for flags.
    return CommandHelp(summary, usage, tuple(parse_help_options(clean)))


def format_command_help(name: str, details: CommandHelp, selected=(), translate=lambda x:x) -> str:
    """Short human-readable sidebar summary; never contains shell actions."""
    L = translate
    chunks = []
    if details.summary:
        label = ('Package description:' if details.summary_source == 'package' else 'What it does:')
        chunks.append(L(label) + '\n' + details.summary)
    else:
        chunks.append(L('No description found in installed help, manual or package information.'))
    if details.usage:
        chunks.append(L('Usage:') + '\n' + details.usage.partition(':')[2].strip())
    if selected:
        rows = []
        for option, value in selected[:8]:
            label = option.flag + ((' ' + value) if value else '')
            rows.append('• ' + label + (' — ' + option.description if option.description else ''))
        chunks.append(L('Selected options:') + '\n' + '\n'.join(rows))
    elif details.options:
        sample = [o for o in details.options if '--help' not in o.names and '--version' not in o.names][:3]
        if sample:
            chunks.append(L('Available options (examples):') + '\n' +
                          '\n'.join('• ' + o.flag + (' — ' + o.description if o.description else '')
                                    for o in sample))
    if details.options:
        chunks.append(L('Documented options:') + ' ' + str(len(details.options)) +
                      '. ' + L('Choose command options to select flags.'))
    else:
        chunks.append(L('No recognizable options were found.'))
    return '\n\n'.join(chunks)


@dataclass(frozen=True)
class CliOption:
    """One option from the target's help, not a verified execution contract."""
    names: tuple[str, ...]
    description: str
    takes_value: bool = False
    optional_value: bool = False
    placeholder: str = ''

    @property
    def flag(self):
        # Prefer familiar short forms (-f for lsblk) if documented.
        return next((name for name in self.names if name.startswith('-') and not name.startswith('--')),
                    self.names[0])

    @property
    def display(self):
        return ', '.join(self.names) + (('  ' + self.placeholder) if self.placeholder else '')


# A single option name, possibly with =NAME or [=NAME] and a value placeholder.
_NAME = re.compile(r'(?<!\S)(--[A-Za-z0-9][\w-]*|-[A-Za-z0-9])(?=$|[\s,=\[])')
_VALUE = re.compile(r'^(?:=\s*(<[^>]+>|\[[^\]]+\]|[A-Z][\w-]*)|\s+(<[^>]+>|\[[A-Z][\w-]*\]|[A-Z][A-Z_0-9-]*))')


def parse_help_options(help_text: str) -> list[CliOption]:
    """Conservatively parse common util-linux, GNU, Python argparse help rows.

    Return only individually documented flag rows. No synthesis of flags from
    prose, synopsis, piped output, or other untrusted text.
    """
    found = {}
    for raw in help_text.splitlines()[:2400]:
        if not raw or len(raw) > 600:
            continue
        # Most help generators indent rows and separate the explanation with
        # at least 2 spaces, or a tab. Some flags have no description.
        if not re.match(r'^\s{1,12}-{1,2}[A-Za-z0-9]', raw):
            continue
        line = raw.strip()
        parts = re.split(r'(?: {2,}|\t+)', line, maxsplit=1)
        syntax = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else ''
        if len(parts) == 1:
            # util-linux sometimes separates '<argument>' and its explanation
            # by just ONE space (e.g. lsblk --dedup <column> de-duplicate).
            # Only split when an explicit value suffix was present; a loose
            # sentence after '--delete' is never evidence of an option row.
            single_space = re.match(
                r'^(.*?(?:<[^>]+>|\[=(?:<[^>]+>|[A-Z][\w-]*)\]|=[A-Z][\w-]*)) (\S.*)$',
                syntax)
            if single_space:
                syntax, description = single_space.group(1), single_space.group(2)
        # Recognize \"-A, --all\", but not multiple ungrouped options or help examples.
        matches = list(_NAME.finditer(syntax))
        if not matches or len(matches) > 2:
            continue
        names = tuple(dict.fromkeys(m.group(1) for m in matches))
        # A free-form sentence after the flag is not a documented option.
        tail = syntax[matches[-1].end():].strip()
        if tail and not re.fullmatch(r'(?:=)?(?:<[^>]+>|\[=?(?:<[^>]+>|[A-Za-z_][\w-]*)\]|[A-Z][A-Z0-9_-]*)', tail):
            continue
        if len(matches) == 2 and ',' not in syntax and not re.search(r'\s+-{1,2}', syntax):
            continue
        # If punctuation other than comma/whitespace/value suffix appears
        # between options, the line probably isn't an option definition.
        if len(matches) == 2:
            between = syntax[matches[0].end():matches[1].start()].strip()
            if between not in ('', ','):
                continue
        takes = optional = False
        placeholder = ''
        for match in matches:
            trailing = syntax[match.end():]
            if len(matches) > 1 and match != matches[-1]:
                trailing = syntax[match.end():matches[matches.index(match)+1].start()].rstrip(', ')
            value_match = _VALUE.match(trailing)
            if value_match:
                value = value_match.group(1) or value_match.group(2)
                if value.startswith('[') and '=' in trailing[:value_match.end()]:
                    optional = True
                if trailing.startswith('[='):
                    optional = True
                takes = True
                placeholder = placeholder or value.strip('<>[]')
        # Handle '[=VALUE]' directly, before the regular --value syntax.
        optional_form = re.search(r'\[=(?:<([^>]+)>|([A-Za-z_][\w-]*))\]', syntax)
        if optional_form:
            takes = optional = True
            placeholder = optional_form.group(1) or optional_form.group(2)
        # Reject likely compound switches or option-with-attached-fixed-text.
        if syntax.startswith('--') and len(matches) == 1 and not re.match(r'^--[\w-]+(?:[=\s\[]|$)', syntax):
            continue
        key = names[-1] if names[-1].startswith('--') else names[0]
        if key not in found:
            found[key] = CliOption(names, description[:260], takes, optional, placeholder)
        if len(found) >= MAX_OPTIONS:
            break
    return list(found.values())


def option_arguments(option: CliOption, value: str = '') -> list[str]:
    """Return exact argv fragments, not a shell snippet."""
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Option values must be on one line')
    if option.takes_value and not option.optional_value and not value.strip():
        raise ValueError('This option needs a value')
    if not option.takes_value:
        return [option.flag]
    if not value.strip():
        return [option.flag] if option.optional_value else []
    if option.optional_value:
        # GNU optional arguments need attached syntax; a separate argv element
        # may be interpreted as a positional argument by the target program.
        long_flag = next((n for n in option.names if n.startswith('--')), '')
        return [long_flag + '=' + value] if long_flag else [option.flag + value]
    return [option.flag, value]


def compose_selected_options(options: list[tuple[CliOption, str]]) -> list[str]:
    result = []
    for option, value in options:
        result.extend(option_arguments(option, value))
    return result


def load_command_info(target: Executable, timeout: float = 3.0, *,
                      include_description: bool = True) -> CommandHelp:
    """Bounded help introspection, no shell/privilege escalation.

    Use stdout file rather than PIPE to prevent unbounded memory from a tool
    which ignores --help and prints infinitely; read no more than 128 KiB.
    Timeout limits the direct process; a command spawning children may not be
    fully containable without a sandbox. Caller runs this only after a user has selected a program.
    """
    if target.kind == 'bash builtin':
        bash = host_which('bash')
        if not bash:
            return CommandHelp('', '', ())
        argv = [bash, '--noprofile', '--norc', '-c', 'help -- "$1"', 'bash', target.name]
    else:
        if in_flatpak():
            if not host_which(target.name):
                raise ValueError('Selected executable is no longer installed on the host')
            argv = [target.name, '--help']
        else:
            location = Path(target.location)
            if not location.is_file() or not os.access(location, os.X_OK):
                raise ValueError('Selected executable is no longer available')
            argv = [str(location), '--help']
    env = dict(os.environ)
    # Predictable parsing independent of desktop locale; only for child.
    env['LC_ALL'] = 'C'
    # Do not run help inside the terminal PTY; always use a bounded subprocess.
    try:
        with tempfile.TemporaryFile() as output:
            run_host(argv, stdin=subprocess.DEVNULL, stdout=output,
                           stderr=subprocess.STDOUT, check=False, timeout=timeout,
                           env=env, start_new_session=True)
            output.seek(0)
            help_text = output.read(MAX_HELP_BYTES).decode('utf-8', 'replace')
    except subprocess.TimeoutExpired as error:
        raise ValueError('Help request timed out') from error
    except (OSError, ValueError, RuntimeError) as error:
        raise ValueError('Could not read command help: ' + str(error)[:250]) from error
    details = parse_command_help(help_text)
    if include_description and not details.summary:
        documented = discover_description(target.name, kind=target.kind, location=target.location)
        if documented is not None:
            return CommandHelp(documented.text, details.usage, details.options, documented.source)
    return details


def load_options(target: Executable, timeout: float = 3.0) -> list[CliOption]:
    """Compatibility interface used by scripts/tests that only need flags."""
    return list(load_command_info(target, timeout=timeout, include_description=False).options)


def prepare_with_options(name, argument_text='', inventory=None, selected=()):
    """Combine checked help options and manually entered argv for one draft."""
    from command_discovery import prepare_command
    manual = prepare_command(name, argument_text, inventory)
    flags = compose_selected_options(selected)
    manual.argv = [name, *flags, *manual.argv[1:]]
    return manual
