# Diagnosing Flatpak host access (v1.0.0)

Universal Linux Terminal intentionally runs an **actual host shell**. This
means its Flatpak needs the powerful `org.freedesktop.Flatpak` D-Bus permission,
already present in the manifest. It does **not** silently fall back to a shell
inside the Flatpak runtime if that access is unavailable.

For older builds showing **Flatpak host access is unavailable**, run from
the normal system terminal (Konsole, etc.):

```bash
cd ~/Desktop/Universal-Linux-Terminal
bash flatpak/diagnose-host.sh
```

Or run manually:

```bash
flatpak info --show-permissions io.github.LionheartTim.UniversalLinuxTerminal
flatpak run --command=flatpak-spawn io.github.LionheartTim.UniversalLinuxTerminal --host /bin/true
```

`/bin/true` does nothing and should exit silently with code 0. Both commands
are safe to run; they neither install packages nor write to the host. The
script prints the **actual error text** returned by Flatpak/D-Bus. The updated
app also displays that diagnostic rather than hiding it behind a generic
permission error. Record the error verbatim before changing permissions.

* If Flatpak reports `AccessDenied` or mentions `org.freedesktop.Flatpak`,
  check that **the installed app** (not merely the source manifest) grants
  `--talk-name=org.freedesktop.Flatpak`. If missing, install/reinstall the
  bundle built from this manifest. Overrides or Flatseal settings may also
  affect the effective permissions; review them before changing anything.
* If Flatpak reports that `flatpak-spawn` is unavailable, it is a runtime
  tooling issue. Do not install `flatpak-spawn` on the host blindly.
* If the D-Bus session is unavailable or the probe times out, inspect the
  exact error and your desktop session; do not grant extra permissions as a
  workaround without understanding the failure.

To reinstall your new bundle after replacing the project files and rebuilding:

```bash
bash flatpak/build-flatpak.sh
flatpak install --user --reinstall ./Universal-Linux-Terminal-v1.0.0-x86_64.flatpak
```

**Security:** HostCommand provides broad unsandboxed execution rights to ULT,
as expected from a host terminal. Keep this permission explicit and only
install releases you trust. It is not appropriate to distribute an unverified
bundle on GitHub before confirming the host PTY and command discovery on Bazzite.

### Revised launch behavior

The newest build no longer blocks the real host shell on the secondary
`/bin/true` probe. See `FLATPAK-HOST-START-FIX.md`. Host permission is
still required and enforced by Flatpak itself.
