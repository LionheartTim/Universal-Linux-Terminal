# ULT v1.0.0 — Flatpak host integration follow-up

This build candidate addresses three defects reported after the interactive Bazzite Bash/PTy passed `tty`, `ps`, `echo "$-"`, and `stty size`.

1. The left sidebar reported `Unverified Flatpak host`, could not enumerate host commands, and marked `flatpak` / `ip` as missing. The old cache-file workaround assumed that host and sandbox agreed on a temporary directory path. Capture now uses Flatpak's documented `--forward-fd=FD` support with two anonymous `TemporaryFile` descriptors for stdout and stderr. The host executes each command **once**. No path or directory needs to be shared for return data. This must still be tested in the real Bazzite Flatpak, not only unit tests.
2. `Insert into terminal` was disabled by the above failed tool availability probe. A failed Flatpak discovery does not prove that a *selected* command is missing, so a missing-tool error from the metadata layer no longer disables the preview-insert button in Flatpak mode. The shell, not the metadata subsystem, determines actual command availability when the user deliberately presses Enter. Safety restrictions other than the unreliable missing-tool message remain enforced.
3. The host PTY and VTE are separate terminals. VTE's `paste_text` may wrap input in bracketed paste markers (`ESC[200~`, `ESC[201~`) which the remote shell can then treat as literal input. Sidebar insertion and confirmed clipboard pastes now use VTE `feed_child` with raw UTF-8 (no newline added for sidebar insertion); text already containing bracketed-paste wrappers from the clipboard has those wrappers removed. Clipboard multiline confirmation remains.

## Manual Bazzite test (installed Flatpak)

- Check `Detected system: Bazzite · rpm-ostree · atomic system`.
- Choose `Flatpak > Installed apps`: **Insert into terminal** should be enabled. Click and verify that `flatpak list --app` appears on the same Bash prompt **without running it**. Press Enter yourself.
- Check `All installed commands`: find `lsblk`, see and select `-f`, and insert and execute.
- Test Ctrl+Shift+V for a single safe command to verify `^[[200~` does not appear.
- Confirm `tty`, Bash, and `stty size` are unchanged.

## Release status

Source and tests validated; the actual Flatpak build and Bazzite desktop integration are not verified from this environment. Do not publish the bundle before host metadata, command selection, paste, and PTY tests have passed.
