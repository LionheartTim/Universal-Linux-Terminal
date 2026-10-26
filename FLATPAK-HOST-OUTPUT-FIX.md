# Flatpak host metadata and installed commands: stdout capture correction

The interactive host Bash/PTTY connection in v1.0.0 was verified on Bazzite:
`tty` returned `/dev/pts/2`, the shell was `bash` and `stty size` returned
`70 97`. However, the *sidebar* reported "Unverified Flatpak host", "no
native manager detected", "Missing tool: ip", and an empty installed-command
inventory. These are distinct from the PTY and were not corrected by shell
selection changes.

## Cause and correction

`host_bridge.run_host()` previously used `subprocess.run(..., stdout=PIPE)`
for short `flatpak-spawn --host` queries. In the GTK-launched Flatpak context,
these requests could return no captured output even while the interactive host
shell worked. The sidebar depends on this output for `/etc/os-release`, host
`command -v`, Bash `compgen -c`, and the documented `--help` options.

For host queries explicitly requesting output, the new bridge executes each
command **once** via `flatpak-spawn --host` and captures the output in an
unpredictable, user-private temporary directory under Flatpak's XDG cache.
The host and the app use the same user-owned path; the app reads the results,
then immediately deletes the temporary directory. The actual command is passed
as an argument vector via `"$@"` without shell interpolation. Exit codes and
stderr are preserved. Ordinary commands that do not capture output, and the
working VTE/Python host PTY, are not modified.

If an output cache cannot be reached from the host, the bridge reports an
explicit error instead of silently mistaking a broken data channel for an
empty host PATH. The Flatpak's existing `--filesystem=host` and
`--talk-name=org.freedesktop.Flatpak` permissions remain unchanged.

## Bazzite verification after rebuilding the bundle

1. Confirm the title shows **Detected system: Bazzite · rpm-ostree · atomic system**.
2. Search for `lsblk` in the main search, and open *All installed commands*.
3. Select `lsblk` and check that `-f` appears among its available options.
4. Verify `ip` no longer falsely shows as missing.
5. In the right-side terminal, check `tty`, `ps -p $$ -o comm=` and `stty size`.
6. Test Stop/Reset and the contextual combination engine to verify no regression.

The new output mechanism has automatic simulated-host tests, but the GTK/Flatpak
runtime must still be validated on Bazzite before distribution.
