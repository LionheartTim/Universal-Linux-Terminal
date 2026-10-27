"""Transport a *host-owned* interactive PTY into VTE inside Flatpak.

The sandbox-side relay is spawned on VTE's PTY.  It puts that PTY in raw
mode, then starts this same source over flatpak-spawn --host using the host's
Python interpreter.  The host process creates its own PTY with pty.fork();
that fixes /dev/pts namespace mismatches and provides true shell job control.

No helper is installed on the host; this code is transported through Python
-c. Shell commands are exec'd by absolute pathname, not interpolated.

Protocol from relay to host on stdin (binary, separate from the PTY stream):
 one-byte kind, 4-byte big-endian length, then payload; I=input, W=winsize.
Output from host to relay remains raw PTY bytes on stdout.
The 'S' frame means SIGINT for the current host PTY foreground process group.
A SIGUSR1 sent to the local relay asks it to issue this control frame; this
works even if the foreground program has disabled the tty ISIG flag.

"""
import errno
import fcntl
import os
import pty
import pwd
import shutil
import selectors
import signal
import struct
import subprocess
import sys
import termios
import tty
from pathlib import Path

HEADER = struct.Struct('!cI')
WINSIZE = struct.Struct('HHHH')
MAX_FRAME = 65536
HOST_ACCOUNT_SHELL = '@host-account-shell'


def _write_all(fd, payload):
    view = memoryview(payload)
    while view:
        try:
            n = os.write(fd, view)
        except InterruptedError:
            continue
        if n <= 0:
            raise BrokenPipeError('PTY transport closed')
        view = view[n:]


def _frame(kind, payload):
    if len(payload) > MAX_FRAME:
        raise ValueError('frame too large')
    return HEADER.pack(kind, len(payload)) + payload


def _size(fd):
    try:
        rows, cols, _, _ = WINSIZE.unpack(fcntl.ioctl(fd, termios.TIOCGWINSZ, b'\0' * 8))
    except OSError:
        return (24, 80)
    return (max(1, rows), max(1, cols))


def _send_size(fd, size):
    rows, cols = size
    _write_all(fd, _frame(b'W', WINSIZE.pack(rows, cols, 0, 0)))


def _resolve_host_shell(requested):
    """Run only on the host; sandbox passwd and PATH can be misleading.

    An explicit non-placeholder shell is honored. For the standard shell,
    use the host's actual user database and only fall back to installed
    executables. Neither the shell nor its parameters come from a shell string.
    """
    if requested != HOST_ACCOUNT_SHELL:
        if requested.startswith('/') and os.access(requested, os.X_OK):
            return requested
        raise FileNotFoundError('Requested host shell is unavailable: ' + repr(requested))
    try:
        candidate = pwd.getpwuid(os.getuid()).pw_shell
        if candidate and candidate.startswith('/') and os.access(candidate, os.X_OK) \
                and os.path.basename(candidate) not in ('false', 'nologin'):
            return candidate
    except KeyError:
        pass
    for candidate in (os.environ.get('SHELL', ''), shutil.which('bash'),
                      shutil.which('sh'), '/bin/bash', '/bin/sh'):
        if (candidate and candidate.startswith('/') and os.access(candidate, os.X_OK)
                and os.path.basename(candidate) not in ('false', 'nologin')):
            return candidate
    raise RuntimeError('No usable login shell found on Linux host')


def _interrupt_host_foreground(master, shell_pid):
    """Signal only the process group currently controlling this host PTY.

    Flatpak VTE's control-C byte may be displayed as ^C yet fail to interrupt
    programs with ISIG disabled. Use the host PTY's actual foreground pgrp,
    not the launcher/Flatpak proxy and never an arbitrary process PID.
    """
    try:
        fg_pgrp = os.tcgetpgrp(master)
        if fg_pgrp <= 1:
            return False
        # Confirm the group is in the session started by our pty.fork child;
        # this prevents a stale/misdirected signal from hitting another job.
        if os.getsid(fg_pgrp) != os.getsid(shell_pid):
            return False
        os.killpg(fg_pgrp, signal.SIGINT)
        return True
    except (OSError, ProcessLookupError):
        return False


def _host_child(shell):
    """Host code.  Parent mediates between pipes and a real controlling PTY."""
    shell = _resolve_host_shell(shell)
    pid, master = pty.fork()
    if pid == 0:
        os.environ['TERM'] = os.environ.get('TERM') or 'xterm-256color'
        # An absolute shell path is obtained from the real host's user account.
        os.execv(shell, [os.path.basename(shell), '-i'])

    selector = selectors.DefaultSelector()
    selector.register(0, selectors.EVENT_READ, 'input')
    selector.register(master, selectors.EVENT_READ, 'pty')
    pending = bytearray()
    stdin_open = True
    master_open = True
    try:
        while master_open:
            for key, _ in selector.select(timeout=0.5):
                if key.data == 'input':
                    try:
                        data = os.read(0, 16384)
                    except OSError:
                        data = b''
                    if not data:
                        selector.unregister(0)
                        stdin_open = False
                        continue
                    pending.extend(data)
                    while len(pending) >= HEADER.size:
                        kind, count = HEADER.unpack(pending[:HEADER.size])
                        if count > MAX_FRAME:
                            raise ValueError('Invalid PTY frame length')
                        if len(pending) < HEADER.size + count:
                            break
                        payload = bytes(pending[HEADER.size:HEADER.size + count])
                        del pending[:HEADER.size + count]
                        if kind == b'I':
                            try:
                                _write_all(master, payload)
                            except OSError as exc:
                                if exc.errno not in (errno.EIO, errno.EBADF):
                                    raise
                        elif kind == b'W' and count == WINSIZE.size:
                            fcntl.ioctl(master, termios.TIOCSWINSZ, payload)
                        elif kind == b'S' and count == 0:
                            _interrupt_host_foreground(master, pid)
                        else:
                            raise ValueError('Invalid PTY frame type')
                else:
                    try:
                        data = os.read(master, 16384)
                    except OSError as exc:
                        if exc.errno != errno.EIO:
                            raise
                        data = b''
                    if not data:
                        master_open = False
                        break
                    _write_all(1, data)
            # When the graphical terminal has closed, terminate the child.
            if not stdin_open:
                try:
                    os.kill(pid, signal.SIGHUP)
                except ProcessLookupError:
                    pass
                break
    finally:
        selector.close()
        os.close(master)
        try:
            _, status = os.waitpid(pid, 0)
        except ChildProcessError:
            status = 1
    return os.waitstatus_to_exitcode(status) if isinstance(status, int) else 1


def _relay(host_python, shell, cwd, local_test=False):
    """Sandbox code, started by VTE.  VTE owns an ordinary PTY locally."""
    if not Path(cwd).is_dir():
        raise RuntimeError('Working directory inaccessible')
    source = Path(__file__).read_text(encoding='utf-8')
    if local_test:
        argv = [sys.executable, '-u', '-c', source, '--host', shell]
    else:
        argv = ['flatpak-spawn', '--host', '--directory=' + cwd,
                '--env=TERM=' + (os.environ.get('TERM') or 'xterm-256color'),
                host_python, '-u', '-c', source, '--host', shell]
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, bufsize=0, close_fds=True,
                            cwd=cwd if local_test else None)
    stdin_fd = sys.stdin.fileno()
    old_term = termios.tcgetattr(stdin_fd) if os.isatty(stdin_fd) else None
    if old_term is not None:
        tty.setraw(stdin_fd)
    # GUI sends SIGUSR1 to this *local relay*; never signal the Flatpak GUI
    # process or forward the signal blindly to the host PID namespace.
    interrupt_pending = False
    def queue_interrupt(signum, frame):
        nonlocal interrupt_pending
        interrupt_pending = True
    previous_interrupt_handler = signal.signal(signal.SIGUSR1, queue_interrupt)
    try:
        selector = selectors.DefaultSelector()
        selector.register(stdin_fd, selectors.EVENT_READ, 'user')
        selector.register(proc.stdout, selectors.EVENT_READ, 'output')
        selector.register(proc.stderr, selectors.EVENT_READ, 'error')
        last_size = _size(stdin_fd)
        _send_size(proc.stdin.fileno(), last_size)
        while True:
            if interrupt_pending:
                interrupt_pending = False
                _write_all(proc.stdin.fileno(), _frame(b'S', b''))
            new_size = _size(stdin_fd)
            if new_size != last_size:
                last_size = new_size
                _send_size(proc.stdin.fileno(), new_size)
            if proc.poll() is not None and len(selector.get_map()) <= 1:
                break
            for key, _ in selector.select(0.15):
                if key.data == 'user':
                    try:
                        data = os.read(stdin_fd, 8192)
                    except OSError as exc:
                        if exc.errno != errno.EIO:
                            raise
                        data = b''
                    if not data:
                        selector.unregister(stdin_fd)
                        proc.stdin.close()
                    else:
                        _write_all(proc.stdin.fileno(), _frame(b'I', data))
                else:
                    data = os.read(key.fileobj.fileno(), 16384)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    _write_all(1 if key.data == 'output' else 2, data)
            if proc.poll() is not None and not any(key.data in ('output', 'error') for key in selector.get_map().values()):
                break
        return proc.wait()
    finally:
        signal.signal(signal.SIGUSR1, previous_interrupt_handler)
        if old_term is not None:
            termios.tcsetattr(stdin_fd, termios.TCSANOW, old_term)
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def main(argv):
    if len(argv) == 2 and argv[0] == '--host':
        return _host_child(argv[1])
    if len(argv) == 5 and argv[0] == '--relay':
        return _relay(argv[1], argv[2], argv[3], local_test=(argv[4] == '--local-test'))
    if len(argv) == 4 and argv[0] == '--relay':
        return _relay(argv[1], argv[2], argv[3])
    raise SystemExit('Usage: host_pty_bridge.py --relay HOST_PYTHON SHELL CWD [--local-test]')


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
