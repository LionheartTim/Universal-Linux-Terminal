"""Host access when ULT is packaged as Flatpak.

The terminal is a HOST terminal.  HostCommand permission is intentional and
powerful: calling flatpak-spawn --host grants the same authority as the user.
Never concatenate user input into shell strings.  Non-Flatpak behavior is
unchanged, including the existing tests and user-installed source build.
"""
import os
import pwd
import shlex
import shutil
import subprocess
import tempfile
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# Resolved INSIDE host_pty_bridge, where the real host account DB is visible.
HOST_ACCOUNT_SHELL = '@host-account-shell'


def in_flatpak():
    # os.path.isfile avoids global Path.is_file mocks in host/source tests.
    return os.path.isfile('/.flatpak-info')


# The Flatpak launcher starts ULT in /app/share/universal-linux-terminal.
# That directory is inside the sandbox only. Flatpak's HostCommand portal
# otherwise tries to reuse that nonexistent directory on the host and fails
# *before executing the command*.  Every noninteractive host operation must
# explicitly pick a directory which exists on any Linux host. The interactive
# host PTY has its own separately managed --directory and is not changed here.
HOST_COMMAND_DIRECTORY = '/'


def host_argv(argv):
    args = list(argv)
    if in_flatpak():
        if not shutil.which('flatpak-spawn'):
            raise RuntimeError('Flatpak host bridge is unavailable: flatpak-spawn is missing')
        return ['flatpak-spawn', '--host',
                '--directory=' + HOST_COMMAND_DIRECTORY, *args]
    return args


# Flatpak's host and sandbox do not necessarily see the same pathname for
# XDG_CACHE_HOME or /tmp. In particular, a successfully running host command
# may not be able to create the shared path used by earlier versions. Forward
# unlinked, app-owned file descriptors through Flatpak's official HostCommand
# D-Bus interface instead. No shared path and no fragile stdout=PIPE required.
# Avoid running any selected command twice; the result is either captured or
# explicitly reported as unavailable.
_HOST_FD_SCRIPT = r'''
output_fd=$1
error_fd=$2
merge_stderr=$3
shift 3
if [ "$merge_stderr" = yes ]; then
    "$@" > "/proc/self/fd/$output_fd" 2>&1
else
    "$@" > "/proc/self/fd/$output_fd" 2> "/proc/self/fd/$error_fd"
fi
'''


def _capture_host_via_fd(argv, **kwargs):
    """Capture one host invocation using explicit extra Flatpak forwarded fds.

    Flatpak-spawn always forwards 0/1/2 already and supports --forward-fd
    for *extra* fds. The app keeps these anonymous files; the host sees only
    open fds, never a sandbox path. Only stdout explicitly requested by a
    caller is exposed. A failure never retries the command.
    """
    requested_stdout = kwargs.get('stdout')
    merge_stderr = kwargs.get('stderr') == subprocess.STDOUT
    want_stdout = kwargs.get('capture_output') or requested_stdout == subprocess.PIPE
    timeout = kwargs.get('timeout', None)
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors_file:
        output_fd, error_fd = output.fileno(), errors_file.fileno()
        command = ['/bin/sh', '-c', _HOST_FD_SCRIPT, 'ult-capture',
                   str(output_fd), str(error_fd),
                   'yes' if merge_stderr else 'no', *argv]
        # pass_fds is required: Python subprocess normally closes >=3.
        launcher = subprocess.run(
            host_argv([f'--forward-fd={output_fd}',
                       f'--forward-fd={error_fd}', *command]),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, timeout=timeout, check=False,
            pass_fds=(output_fd, error_fd),
            env=kwargs.get('env'), cwd=kwargs.get('cwd'),
            start_new_session=kwargs.get('start_new_session', False),
        )
        output.seek(0)
        errors_file.seek(0)
        max_output = 8 * 1024 * 1024
        raw_out = output.read(max_output + 1)
        raw_err = errors_file.read(max_output + 1)
        if len(raw_out) > max_output or len(raw_err) > max_output:
            raise RuntimeError('Host command output exceeds the permitted size')
    if launcher.returncode and not raw_out and not raw_err:
        detail = (launcher.stderr or b'').decode('utf-8', 'replace').strip()
        if detail:
            raise RuntimeError('HostCommand fd forwarding failed: ' + detail[-600:])
    text_mode = kwargs.get('text') or kwargs.get('universal_newlines') or kwargs.get('encoding')
    encoding, errors = kwargs.get('encoding') or 'utf-8', kwargs.get('errors') or 'replace'
    out_data = raw_out.decode(encoding, errors) if text_mode else raw_out
    err_data = raw_err.decode(encoding, errors) if text_mode else raw_err
    if requested_stdout is not None and requested_stdout != subprocess.PIPE:
        if hasattr(requested_stdout, 'write'):
            requested_stdout.write(raw_out)
            requested_stdout.flush()
        out_data = None
    elif not want_stdout:
        out_data = None
    if not kwargs.get('capture_output') and kwargs.get('stderr') != subprocess.PIPE:
        err_data = None
    result = subprocess.CompletedProcess(host_argv(argv), launcher.returncode,
                                         out_data, err_data)
    if kwargs.get('check'):
        result.check_returncode()
    return result


def run_host(argv, **kwargs):
    # A desktop-launched Flatpak may have no valid inherited fd 0. Every
    # noninteractive host probe therefore receives /dev/null unless its caller
    # explicitly supplies input/stdin.
    if in_flatpak() and 'stdin' not in kwargs and 'input' not in kwargs:
        kwargs['stdin'] = subprocess.DEVNULL
    stdout = kwargs.get('stdout')
    wants_capture = (kwargs.get('capture_output') or stdout == subprocess.PIPE
                     or (hasattr(stdout, 'write') and stdout != subprocess.DEVNULL))
    if in_flatpak() and wants_capture and 'input' not in kwargs:
        return _capture_host_via_fd(argv, **kwargs)
    return subprocess.run(host_argv(argv), **kwargs)


@lru_cache(maxsize=512)
def host_which(name):
    if not in_flatpak():
        return shutil.which(name)
    # Single shell argument: no command construction based on user input.
    if not name or '/' in name or '\x00' in name:
        return None
    try:
        result = run_host(['/bin/sh', '-c', 'command -v "$1"', 'sh', name],
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          text=True, timeout=4, check=False)
    except (OSError, subprocess.TimeoutExpired, RuntimeError, subprocess.SubprocessError):
        result = None
    if result is not None and result.returncode == 0 and result.stdout:
        locations = result.stdout.strip().splitlines()
        if locations:
            return locations[0]
    # Even if captured stdout is unavailable, exit status from an ordinary
    # HostCommand probe can confirm a name is present. A name is sufficient
    # for availability checks and execution via the existing host PATH.
    try:
        status = run_host(['/bin/sh', '-c', 'command -v "$1" >/dev/null 2>&1', 'sh', name],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          timeout=5, check=False)
        return name if status.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, RuntimeError):
        return None


def _host_can_execute(absolute_path):
    """Check a host binary by *exit status*, never by captured stdout.

    Some Flatpak versions/launch contexts do not return a useful stdout pipe
    for short HostCommand probes. The GUI needs a reliable host-Python check,
    and the `flatpak-spawn --host ...` exit status already works on Bazzite.
    The path is passed as positional data, not embedded in shell source.
    """
    if not in_flatpak() or not absolute_path.startswith('/') or '\x00' in absolute_path:
        return False
    try:
        result = run_host(
            ['/bin/sh', '-c', 'test -x "$1"', 'sh', absolute_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False, timeout=8,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired, RuntimeError):
        return False


def host_executable(name):
    """Resolve common host executables without relying on text capture.

    First try standard host locations (especially /usr/bin/python3, confirmed
    on Bazzite); then fall back to command -v for nonstandard distributions.
    This does not make guesses: each candidate must pass host-side `test -x`.
    """
    if not in_flatpak():
        return shutil.which(name)
    if not name or '/' in name or '\x00' in name:
        return None
    for directory in ('/usr/bin', '/bin', '/usr/local/bin'):
        path = f'{directory}/{name}'
        if _host_can_execute(path):
            return path
    # PATH-based discovery is still useful on unusual hosts, but it must not
    # be the sole way to find Python3 for the real terminal.
    return host_which(name)


def host_release():
    result = run_host(['/bin/cat', '/etc/os-release'], capture_output=True,
                      text=True, timeout=5, check=True)
    from distro_support import parse_os_release
    return parse_os_release(result.stdout)


def host_path_exists(path):
    if not in_flatpak():
        return Path(path).exists()
    try:
        return run_host(['/usr/bin/test', '-e', path], timeout=4,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    except (OSError, subprocess.TimeoutExpired, RuntimeError):
        return False


def account_shell():
    """Request the real host account shell without guessing from sandbox data.

    A GTK desktop-launched Flatpak can fail to collect stdout from short
    flatpak-spawn probes even when the host command succeeds. Falling back to
    /bin/sh in that situation silently selects the *wrong* user's shell.
    Instead, resolve the shell inside the actual host Python process using
    pwd.getpwuid(). This respects Bash, Zsh, Fish and other configured shells.
    """
    if not in_flatpak():
        return None
    # A successful host lookup also lets the existing command composition
    # logic know if Bash is used. Failure is never an instruction to use sh.
    try:
        result = run_host(['getent', 'passwd', str(os.getuid())],
                          capture_output=True, text=True, timeout=5, check=False)
        lines = result.stdout.strip().splitlines()
        if result.returncode == 0 and lines:
            candidate = lines[0].split(':')[-1].strip()
            if (candidate.startswith('/') and '\x00' not in candidate
                    and Path(candidate).name not in ('false', 'nologin')):
                return candidate
    except (OSError, subprocess.SubprocessError, RuntimeError):
        pass
    return HOST_ACCOUNT_SHELL


def host_shell_argv(shell, cwd):
    """Start an interactive shell on the HOST with a HOST-owned PTY.

    Prefer a stdlib Python bridge: a local relay sets its VTE PTY raw and a
    host Python process allocates the PTY, executes the user shell and relays
    input/output and window sizes. No host package layering is necessary on
    Fedora/Bazzite if host Python 3 is available. When it is unavailable,
    util-linux `script` remains a best-effort fallback.
    """
    if not in_flatpak():
        return [shell, '-i']
    if not shutil.which('flatpak-spawn'):
        raise RuntimeError('Host terminal cannot start: flatpak-spawn is missing.')
    if not Path(cwd).is_dir():
        raise ValueError('The working directory is not accessible by Flatpak')

    # Prefer a self-contained host PTY bridge if host Python is installed.
    # Fedora/Bazzite split `script` into the optional util-linux-script RPM;
    # do not force an rpm-ostree layer + reboot just to open our Flatpak.
    host_python = host_executable('python3')
    host_script = None if host_python else host_executable('script')
    if host_python is None and not host_script:
        # Preflights from a GUI are not conclusive: a real Bazzite host can
        # have /usr/bin/python3 even if its probes fail because a Flatpak
        # child inherited an invalid fd 0. The user already confirmed this
        # path directly through flatpak-spawn --host. Try starting the real
        # PTY with it instead of incorrectly claiming Python is missing.
        # If it really is absent, the relay shows the host-spawn error in VTE.
        host_python = '/usr/bin/python3'
    if host_python:
        relay = Path(__file__).with_name('host_pty_bridge.py')
        return [shutil.which('python3') or '/usr/bin/python3', '-u', str(relay),
                '--relay', host_python, shell, cwd]

    # Hosts where Python is genuinely unavailable but script was identified
    # can still use the util-linux fallback.
    # script -c is necessarily a shell string; quote the absolute shell path.
    # All other parameters use direct argv, including cwd and the output path.
    if shell == HOST_ACCOUNT_SHELL:
        # Without host Python, defer shell resolution to host `getent` via
        # util-linux script's host-side /bin/sh. No untrusted path is
        # interpolated into the command string.
        shell_command = ('login_shell=$(getent passwd "$(id -u)" | cut -d: -f7); '
                         'if [ -z "$login_shell" ] || [ ! -x "$login_shell" ]; '
                         'then login_shell=${SHELL:-/bin/sh}; fi; '
                         'exec "$login_shell" -i')
    else:
        shell_command = 'exec ' + shlex.quote(shell) + ' -i'
    return [
        'flatpak-spawn', '--host', '--directory=' + cwd,
        '--env=TERM=xterm-256color',
        host_script, '--quiet', '--return', '--flush',
        '--command', shell_command, '/dev/null',
    ]


@dataclass(frozen=True)
class HostProbe:
    """Result of a harmless host command, including a useful failure reason."""
    ok: bool
    detail: str = ''


def inspect_host_access():
    """Check host access without executing user commands or changing permissions.

    Never silently fall back to a sandbox shell: that would give incorrect
    distro detection, PATH contents and command execution semantics.  The
    stderr from flatpak-spawn is necessary for a real-world diagnosis.
    """
    if not in_flatpak():
        return HostProbe(True)
    if not shutil.which('flatpak-spawn'):
        return HostProbe(False, 'flatpak-spawn is not available inside the Flatpak runtime.')
    try:
        result = run_host(['/bin/true'], timeout=8, capture_output=True,
                          text=True, check=False)
    except subprocess.TimeoutExpired:
        return HostProbe(False, 'flatpak-spawn --host did not respond within 8 seconds.')
    except (OSError, RuntimeError) as exc:
        return HostProbe(False, 'Could not start flatpak-spawn: ' + str(exc)[:500])
    if result.returncode == 0:
        return HostProbe(True)
    error = (result.stderr or result.stdout or '').strip()
    if not error:
        error = 'flatpak-spawn --host returned exit code ' + str(result.returncode)
    return HostProbe(False, 'flatpak-spawn --host failed (exit code '
                     + str(result.returncode) + '):\n' + error[-1200:])


def probe_host():
    """Legacy boolean API used by source-level tests and integrations."""
    return inspect_host_access().ok
