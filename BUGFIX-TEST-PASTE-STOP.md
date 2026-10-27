# Universal Linux Terminal v1.0.1 — test candidate

This ZIP contains the **v1.0.1 source candidate** for local verification.
The already published GitHub v1.0.0 release is unchanged. Do not publish
v1.0.1 until the paste and Stop tests pass on real hardware.

## Paste-warning preference test (new small GUI update)

- By default, **Paste…** shows the familiar safety confirmation with a
  **Don't show this warning again** checkbox.
- Choose **No** (even with the box checked): the next paste must still warn.
- Tick the box and choose **Yes**: this paste continues and subsequent pastes
  do not show the warning, even after restarting the Flatpak.
- Right-click inside the terminal, enable **Show paste confirmation**, and
  check that the next paste shows the dialog again.
- This preference only affects clipboard warning visibility; it does not alter
  bracketed paste, Enter behavior, Stop, or the separate Ctrl+C button.

## What changed

- **Clipboard Paste… / Ctrl+Shift+V:** uses VTE `paste_text` instead of writing
  Enter/CR after every line. With Bash Readline bracketed paste enabled,
  the full multi-line text appears in the editable prompt; review and
  press Enter once to execute the block. `Shift+Enter` is not required.
  Where bracketed paste is not active, normal terminal paste can execute
  line breaks immediately; the confirmation prompt remains important.
- **Insert into terminal** from the left panel still inserts text without Enter.
- **Stop** asks confirmation and closes the app; **Interrupt command (Ctrl+C)**
  interrupts a running command while leaving the app open. In the Flatpak Python
  PTY bridge, the Interrupt button now sends a signal to the actual host-side
  foreground process group rather than relying only on a Ctrl+C byte, which
  might display `^C` without stopping some running programs.
- Version label, Flatpak bundle filename and metadata are now **1.0.1**.

## Rebuild from the extracted project on Bazzite

```bash
cd ~/Desktop/Universal-Linux-Terminal
bash flatpak/build-flatpak.sh
flatpak install --user --reinstall ./Universal-Linux-Terminal-v1.0.1-x86_64.flatpak
flatpak run io.github.LionheartTim.UniversalLinuxTerminal
```

If Flatpak Builder fails with `Failed to check out cache: Couldn't find file
object`, remove **only this project's generated cache/build directories**,
then rebuild:

```bash
cd ~/Desktop/Universal-Linux-Terminal
rm -rf -- .flatpak-builder flatpak-build repo
bash flatpak/build-flatpak.sh
```

After the build completes successfully, install the v1.0.1 bundle above.
An existing Flatpak may still open after a failed build: opening alone does
not mean the new version is installed. Verify the GUI shows **Version 1.0.1**.

## Live tests

1. In the embedded Bash, copy both lines below together, then Paste…,
   confirm and **do not press Enter yet**. Neither marker should appear.
   Press **Enter once**; then both markers should print and the next prompt
   should appear:

   ```bash
   echo ULT-REGEL-1
   echo ULT-REGEL-2
   ```

2. Repeat with text copied from Windows (CRLF) if practical; try a
   final line without a trailing newline. It must still be included.
3. Click **Insert into terminal** for a sidebar command. It must not
   execute until you press Enter.
4. Run `sleep 30` in the built-in terminal, click **Interrupt command (Ctrl+C)**,
   and verify you get the shell prompt back immediately, without closing the GUI.
5. For a stronger regression test, run `stty -isig; sleep 30` then click
   **Interrupt command (Ctrl+C)**. The app must return to the Bash prompt even
   if ordinary Ctrl+C characters cannot cause terminal-generated signals.
   Run `stty isig` afterward to restore the normal terminal setting.
6. Click **Stop**, confirm **Yes**, and verify the **whole app window closes**.
   This is different from interrupting a running command. If it does not,
   verify the GUI footer shows **Version 1.0.1** and the Flatpak rebuild and
   installation both succeeded.

The local headless tests are not a substitute for testing the actual
Flatpak on Bazzite, Xubuntu and openSUSE.
