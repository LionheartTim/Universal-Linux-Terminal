# Flatpak host-shell startup fix (v1.0.0 packaging revision)

A Bazzite user verified that the installed Flatpak has
`org.freedesktop.Flatpak=talk` and that
`flatpak run --command=flatpak-spawn io.github.LionheartTim.UniversalLinuxTerminal --host /bin/true`
succeeds, but the app showed a generic "host access unavailable" startup popup.

The prior Python GUI blocked ALL terminal startup when a separate
`flatpak-spawn --host /bin/true` preflight failed or timed out. This was a
redundant, potentially false-negative check. Now the GTK/VTE app **directly
attempts to launch the real host shell**, using the existing Flatpak
`flatpak-spawn --host` path (stdio descriptors are forwarded automatically). The Flatpak portal still
**enforces actual host permission**; no additional permissions are granted,
and the app never falls back to running commands in the sandbox.

On shell exit or spawn failure the terminal displays its status, rather than
remaining blank. The separate `flatpak/diagnose-host.sh` script and
`host_bridge.inspect_host_access()` remain available for troubleshooting.

Rebuild, reinstall and test on Bazzite:

```sh
bash flatpak/build-flatpak.sh
flatpak install --user --reinstall ./Universal-Linux-Terminal-v1.0.0-x86_64.flatpak
flatpak run io.github.LionheartTim.UniversalLinuxTerminal
```

If it still fails, collect the *exact* terminal output and additionally test
from the same Python runtime as the app (not the `flatpak-spawn` main command):

```sh
flatpak run --command=python3 io.github.LionheartTim.UniversalLinuxTerminal \
  -c 'import shutil,subprocess; print("spawn:",shutil.which("flatpak-spawn")); r=subprocess.run(["flatpak-spawn","--host","/bin/true"],capture_output=True,text=True,timeout=12); print("exit:",r.returncode,"stderr:",repr(r.stderr))'
```

The Flatpak host shell/PTy integration still requires a graphical runtime test.
