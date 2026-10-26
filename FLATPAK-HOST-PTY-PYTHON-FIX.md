# Universal Linux Terminal v1.0.0 — host PTY without util-linux-script

## Why this correction exists

On Fedora/Bazzite 44, `/usr/bin/script` is provided by the optional
`util-linux-script` package. The earlier Flatpak build required `script`
and refused to open the terminal when the host did not have that package.
The Flatpak GNOME runtime cannot install an executable into the host OS.

This edition **prefers host Python 3**, and keeps host `script` as a fallback
when Python 3 is unavailable. **No additional host package is installed**.
This is not a sandboxed shell: the app explicitly uses the approved Flatpak
HostCommand permission to run commands as the signed-in host user.

## How the Python bridge works

1. VTE opens its normal PTY inside the Flatpak for keyboard/display.
2. The local Python relay sets that PTY to raw mode (restored on exit).
3. `flatpak-spawn --host` runs the host's `python3 -u -c <source> --host <shell>`.
   The source is sent as an argv string, not a path inside `/app`, which
   the host cannot access.
4. Python's `pty.fork()` creates a *second* PTY on the host, providing a
   resolvable `/dev/pts/N` and proper controlling terminal for the actual
   account shell, without injecting commands into its input.
5. The relay transports bytes, plus terminal-size changes, using a separate
   framed control protocol. Keyboard shortcuts such as Ctrl+C/Ctrl+Z are
   processed by the host terminal's own line discipline.
6. No passwords or command transcripts are persisted by this helper.

On hosts lacking Python 3 but having `script`, the previous `script` method
is still available. If neither is available, the app shows a clear error.

## Regression checks

The local non-Flatpak integration test starts a real Bash session through the
same Python relay and host-worker processes. It checks `tty`, shell
interactivity, `stty size`, Ctrl+Z, `jobs`, `fg`, Ctrl+C, and window resizing.
This **does not** prove the cross-namespace Flatpak D-Bus transport; the
Bazzite installed-bundle test remains mandatory before public release.

## Build / install on Bazzite

Unzip into a fresh working directory (or replace all old project files), then:

```bash
cd ~/Desktop/Universal-Linux-Terminal
bash flatpak/build-flatpak.sh
flatpak install --user --reinstall ./Universal-Linux-Terminal-v1.0.0-x86_64.flatpak
flatpak run io.github.LionheartTim.UniversalLinuxTerminal
```

Inside **the ULT Flatpak** try:

```bash
tty
ps -p $$ -o comm=
echo "$-"
stty size
pwd
```

Expected: a valid `/dev/pts/…`, the user's normal shell, interactive flag
`i`, and sensible rows/columns. Then run `sleep 30`, Ctrl+Z, `jobs`, `fg`,
Ctrl+C. Resize the window and re-check `stty size`. Finally verify host
commands via `cat /etc/os-release` and `rpm-ostree status`.

Do not publish a prebuilt Flatpak as fully validated until those tests
pass in the installed Bazzite bundle. The normal, non-Flatpak source
launch and the existing command-combination engine are unchanged.
