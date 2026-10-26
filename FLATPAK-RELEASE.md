# Flatpak packaging — Universal Linux Terminal v1.0.0

## What is included

* The GNOME Flatpak runtime automatically supplies Python 3, GTK 3, PyGObject
  and common GNOME libraries. The manifest builds a GTK3-compatible VTE 2.91
  module in the app so the user's distribution does **not** need `vte291`.
* The desktop entry/icon and the launcher are shipped with the app.
* The Flatpak manifest explicitly builds VTE's **simdutf 8.0.0** and
  **fmt 12.1.0** libraries and installs **fast_float 8.2.3** headers before
  building VTE. Meson wraps are disabled so it will not attempt to download
  hidden subprojects during the build. This fixes the Meson `simdutf` error
  seen on Bazzite during the first build attempt.
* Installed Flatpak runtimes are managed by Flatpak itself. Installing a
  single-file `.flatpak` bundle requires a remote such as Flathub to provide
  its GNOME runtime when not already installed.
* The real login shell, distribution metadata, PATH inventory, command help,
  Flatpak apps and disks are queried through `flatpak-spawn --host`.

## Security / trust model

**This is not a normally isolated Flatpak application.** It deliberately uses
`--talk-name=org.freedesktop.Flatpak` so it can start a host shell. That
permission permits host command execution with the current user's authority.
The manifest also grants `--filesystem=host` for file browsing and project
building. Only install bundles from releases you trust. The terminal never
requires an automatic administrator password at installation. Privileged
commands in the terminal can still request authorization when executed.

## Build on Bazzite or a Linux build host

Install and configure Flatpak and flatpak-builder first; ensure Flathub is
configured. The GNOME SDK/runtime branch used here is `50`. You may use
`bash flatpak/build-flatpak.sh` for a guarded, repeatable local build.

```sh
flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub org.gnome.Sdk//50 org.gnome.Platform//50
flatpak-builder --force-clean --repo=repo build-dir io.github.LionheartTim.UniversalLinuxTerminal.yml
flatpak build-bundle repo Universal-Linux-Terminal-v1.0.0-x86_64.flatpak io.github.LionheartTim.UniversalLinuxTerminal
```

Install the bundle locally:

```sh
flatpak install --user ./Universal-Linux-Terminal-v1.0.0-x86_64.flatpak
flatpak run io.github.LionheartTim.UniversalLinuxTerminal
```

If Flatpak reports a missing runtime, make sure Flathub is configured and
install `org.gnome.Platform//50`. Verify the installed permissions using:

```sh
flatpak info --show-permissions io.github.LionheartTim.UniversalLinuxTerminal
```

## GitHub releases

The included `.github/workflows/flatpak.yml` can build the bundle on GitHub
Actions using the official Flatpak Builder action. Use Actions → Flatpak bundle
→ Run workflow; successful results appear as an Actions artifact. To attach a
`.flatpak` file to a Release automatically, push a tag such as `v1.0.0`.

## Failed build: missing simdutf

If the previous Flatpak release-source ZIP produced:

```
Run-time dependency simdutf found: NO
ERROR: Automatic wrap-based subproject downloading is disabled
```

replace **all** source files with this corrected release-source ZIP and run
`bash flatpak/build-flatpak.sh` again. The script uses `--force-clean`, so a
failed build directory is discarded. Existing `~/.flatpak-builder` download
cache can be reused. Do not manually install simdutf into the Bazzite host;
this dependency belongs **inside the Flatpak**.

The manifest has been syntax-checked and its dependency list regression-tested,
but a complete Flatpak build on Bazzite is still needed to validate the VTE,
PTY and host bridge together.

## Testing before publishing

This package has source-level automated checks, but its GTK/VTE UI, host PTY
forwarding and actual Flatpak installation need testing on a real desktop.
Tests: type `pwd`, run `cd /tmp`, run `pwd` again; try interactive `top`,
check Stop/Reset, `cat /etc/os-release`, main search `lsblk`, options `-f`,
Native packages detection, external drive selection, host Flatpak search,
clipboard and clean close. No host package installs should occur automatically.

## Publication notice

This ZIP contains a **buildable source proposal**, not a precompiled `.flatpak`.
No real Flatpak SDK/GUI installation was available in the development environment.
Do not claim runtime/PTY validation until the Actions build and Bazzite Flatpak
installation have completed. The app source remains at version 1.0.0.
Project-source licensing has not been chosen; decide that before publishing on
GitHub. The icon/metainfo are separately created packaging assets.

## If the installed Flatpak says host access is unavailable

The original diagnostic build displayed the exact error from the harmless `flatpak-spawn --host
/bin/true` check, rather than hiding stderr. Run `bash flatpak/diagnose-host.sh`
from the project directory for a no-change diagnostic against the **installed**
bundle. See `FLATPAK-HOST-DIAGNOSTICS.md` for next steps. No additional
permissions are added automatically.


#### Host startup correction

See `FLATPAK-HOST-START-FIX.md`. The UI now attempts the actual host
shell directly, since a separate preflight could block working host access.

## Host job control and `tty` path — updated

See `FLATPAK-HOST-PTY-PYTHON-FIX.md`. **On Bazzite/Fedora 44, `script`
is a separate optional package** (`util-linux-script`), so making it a
requirement prevented the app from opening. The Flatpak now uses host Python
3 to create a genuine **host-owned PTY** and pass raw terminal bytes and
resize messages between the VTE frontend and the host shell. The old host
`script` route is a fallback on machines without host Python 3. No host
packages or extra Flatpak permissions are installed by the app.

The local nested-PTY test checks `tty`, job control and resize. Actual
Flatpak D-Bus host transport still needs Bazzite validation. See the new
file for the exact test commands.
