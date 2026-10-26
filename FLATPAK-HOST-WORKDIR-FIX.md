# Flatpak host working-directory correction (v1.0.0 test build)

## Symptom

The graphical Flatpak opens a fully functioning Bazzite Bash/PTTY, but the
left-side host command inventory, OS detection and options discovery fail with:

```
Portal call failed: Failed to start command:
Failed to change to directory '/app/share/universal-linux-terminal'
(No such file or directory)
```

## Cause

`flatpak/ult-launch` intentionally switches to
`/app/share/universal-linux-terminal` to start the packaged Python GUI.
That path exists only *inside* the Flatpak sandbox. By default,
`flatpak-spawn --host` attempts to reuse the current working directory, but
that directory does not exist on the Linux host. The Flatpak portal rejects
such calls before executing the requested program.

## Correction

`host_bridge.host_argv` now supplies `--directory=/` for noninteractive
host commands. `/` is present on every supported Linux host, and is a
neutral starting point for read-only command discovery and host probes.
The launcher, host PTY relay, shell selection, and native/source-run behavior
are unchanged. The interactive host Bash already has a separate, explicit
working directory, and continues to use that existing route.

No additional permissions or host packages were introduced.

## Regression tests

- Simulated Flatpak portal rejects sandbox-only cwd in the absence of
  `--directory=` and accepts `--directory=/`.
- Both stdout/stderr via forwarded file descriptors and direct status-only
  commands work under the simulated failure conditions.
- Non-Flatpak behavior and the dedicated host PTY route remain unchanged.
- All original unit tests continue to pass.

## Bazzite follow-up

Rebuild and reinstall the Flatpak using `bash flatpak/build-flatpak.sh` and
`flatpak install --user --reinstall ./Universal-Linux-Terminal-v1.0.0-x86_64.flatpak`.
Then check (1) Bazzite/rpm-ostree/atomic detection, (2) installed commands
listing (e.g. `lsblk`) and its options, (3) `IP addresses` and `Flatpak
installed apps`, and (4) the working host Bash PTY and insertion button.

The current environment cannot run Flatpak-builder or a graphical Bazzite
session, so these last integration checks remain user-side.

Flatpak references:
- https://man7.org/linux/man-pages/man1/flatpak-spawn.1.html
- https://github.com/flatpak/flatpak/issues/6631
