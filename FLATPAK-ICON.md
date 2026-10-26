# Approved icon — Universal Linux Terminal v1.0.0

The artwork in `artwork/ULT-approved-original.png` is the user-selected
blue `>_` + `ULT` icon. Derived transparent PNG sizes (16 to 512 px) are in
`flatpak/icons/`. Flatpak installs them under the canonical icon theme name:
`io.github.LionheartTim.UniversalLinuxTerminal`.

The desktop file uses the same application ID, icon name, and StartupWMClass.
`app_icon.py` assigns the GTK3 GLib program name **before the first window**,
so KDE Wayland can match the running window to the exported desktop file.
GTK also uses the selected image in its window icon where the compositor allows.

The original project version remains **1.0.0**; this changes only the icon/
application identity, not the command engine or host bridge.

## Build from the project root

```bash
bash flatpak/build-flatpak.sh
flatpak install --user --reinstall ./Universal-Linux-Terminal-v1.0.0-x86_64.flatpak
flatpak run io.github.LionheartTim.UniversalLinuxTerminal
```

If an older icon remains pinned in KDE Plasma, unpin and pin the app again.
The taskbar icon itself is resolved by the Wayland compositor using the
application ID and exported `.desktop` file, not by drawing an image inside
our own window.

**Test still required:** run the installed bundle on Bazzite, verify the icon
in launcher/taskbar/window and verify that the host-shell PTY still works.
