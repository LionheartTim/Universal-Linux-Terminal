# Flatpak desktop launcher host-probe correction (v1.0.0)

## Reported symptom

After building and installing the Flatpak on Bazzite, opening ULT from KDE still showed:

> Host terminal needs either Python 3 or util-linux 'script' on the host to create a usable PTY.

But this command from the same Flatpak ID did return `/usr/bin/python3`:

```sh
flatpak run --command=flatpak-spawn io.github.LionheartTim.UniversalLinuxTerminal \
  --host /bin/sh -c 'command -v python3; command -v script'
```

`flatpak info --show-permissions` and `flatpak-spawn --host /bin/true` were also successful.

## Concrete cause identified in source

The GTK launch process can lack a valid inherited standard input (fd 0).
`host_bridge.run_host()` previously used `subprocess.run()` with default `stdin=None`.
`flatpak-spawn` forwards fd 0, 1, and 2 by default and fails when one of them is invalid.
The GUI probes already captured or discarded stdout and stderr, but inherited stdin.
Thus short host tests may fail even though host Python is installed.

## Changes

- In Flatpak, **noninteractive** `run_host()` calls now set `stdin=subprocess.DEVNULL` unless the caller explicitly passed `stdin` or `input`.
- If executable discovery still fails for both Python and `script`, the application tries the known `/usr/bin/python3` host interpreter rather than displaying a misleading dependency popup. If Python is truly absent, the host process will emit a concrete failure in the terminal instead.
- The host-created Python PTY relay, GNOME/VTE runtime, shell features, app icon, Flatpak app ID, and permissions are unchanged.
- No extra package layering or `--device=all` is needed.

## Test

```sh
cd ~/Desktop/Universal-Linux-Terminal
bash flatpak/build-flatpak.sh
flatpak install --user --reinstall ./Universal-Linux-Terminal-v1.0.0-x86_64.flatpak
flatpak run io.github.LionheartTim.UniversalLinuxTerminal
```

Then test **inside ULT's Flatpak terminal**:

```sh
tty
ps -p $$ -o comm=
echo "$-"
stty size
```

A working PTY has a `/dev/pts/...` device, interactive flags include `i`, and `stty size` returns dimensions. Then confirm Ctrl+Z/jobs/fg/Ctrl+C.

The full suite has 206 tests: 201 passed, 5 skipped GTK/VTE desktop integration. The actual Bazzite Flatpak PTY has not yet been validated by a user.
