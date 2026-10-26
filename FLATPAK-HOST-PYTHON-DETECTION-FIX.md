# Flatpak Host Python Detection Fix — v1.0.0 release source

## Observed on Bazzite

The installed Flatpak displayed a dialog claiming neither host Python 3 nor host `script` was present. The user verified from the same Flatpak app ID that this host command works:

```sh
flatpak run --command=flatpak-spawn \
  io.github.LionheartTim.UniversalLinuxTerminal \
  --host /bin/sh -c 'command -v python3; command -v script'
```

Output: `/usr/bin/python3` (no `script` found). The host permissions and a harmless host command were previously confirmed working.

## Fix

Before this change, the host shell selected Python based only on `host_which('python3')`, which captured the host command's standard output inside the sandbox. A missing or delayed captured result caused a *false negative* and the misleading dialog.

Now the host-executable resolver verifies standard absolute host locations by **host-side command exit status** (`/bin/sh -c 'test -x "$1"'`), without relying on captured stdout. It only falls back to `command -v` when the common paths are absent. The Bash fallback uses the same resolver, so loss of captured output cannot silently force `sh` if Bash is installed in a known location.

No additional Flatpak permissions or extra host packages are required by this change. This is a host detection fix; the actual end-to-end Flatpak PTY/job-control path still needs a live Bazzite test.

## Build/test

```sh
bash flatpak/build-flatpak.sh
flatpak install --user --reinstall ./Universal-Linux-Terminal-v1.0.0-x86_64.flatpak
flatpak run io.github.LionheartTim.UniversalLinuxTerminal
```

Inside the actual Flatpak terminal:

```sh
tty
ps -p $$ -o comm=
echo "$-"
stty size
```

`tty` should report `/dev/pts/...`; test Ctrl+Z, `jobs`, `fg` and Ctrl+C afterward. The system-wide source-run version and the existing combination engine were not changed.
