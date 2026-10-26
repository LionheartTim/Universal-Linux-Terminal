# Universal Linux Terminal v1.0.0 — Flatpak host-shell selection fix

This is a targeted source-code fix for the Flatpak showing `sh-5.3$` even
when Bazzite's host account normally uses Bash.

## Root cause
The Flatpak side previously tried to infer the host login shell using
`flatpak-spawn --host getent passwd` and then guessed `/bin/sh` whenever
stdout collection or probing failed in a graphical launch.

## Change
- A successful `getent passwd` lookup still selects the true account shell.
- If the lookup fails, the launcher passes a special marker to the **host-side**
  Python bridge. The host process itself uses `pwd.getpwuid(os.getuid()).pw_shell`.
- If the host passwd shell is invalid, it falls back to a locally available
  shell. It never silently selects `/bin/sh` simply because a sandbox probe
  produced no output.
- The no-Python `script` fallback also resolves the account shell on the host.
- The actual VTE and host-owned PTY relay mechanisms are unchanged.
- All original app files, Flatpak permissions, definitive icon and build fixes
  remain in the release source.

## Local tests
215 discovered tests: 210 passed, 5 GTK/VTE desktop tests skipped.
The regression suite includes a local two-process interactive PTY check with
host-side account shell selection and a valid `/dev/pts/...` response.

## NOT YET CONFIRMED
This is not a precompiled .flatpak. A working Bazzite/KDE host-PTY in Flatpak
has not yet been verified. The screenshot `sh-5.3$ ^C` showed no job-control
errors, but did not establish that the PTY is correct.

## Bazzite install test
Replace your project source with the contents of this ZIP, then:

    bash flatpak/build-flatpak.sh
    flatpak install --user --reinstall ./Universal-Linux-Terminal-v1.0.0-x86_64.flatpak
    flatpak run io.github.LionheartTim.UniversalLinuxTerminal

Inside the GUI terminal run:

    tty
    ps -p $$ -o comm=
    echo "$-"
    stty size
    cat /etc/os-release

`tty` should output /dev/pts/N, `comm` should match the real host login shell,
`echo "$-"` should include i. Then exercise Ctrl+Z/jobs/fg and Ctrl+C
using `sleep 30` only after confirming the above.

Do not publish as final until these are validated on Bazzite.
