# Third-party notes

The Flatpak builds VTE and its declared library dependencies in the app, and
uses the GNOME runtime. No additional `host-spawn` binary is bundled in this
revision. For the interactive host PTY the application prefers the host's
installed Python 3; where that is unavailable it may fall back to the
host-provided util-linux `script` command. Neither program is redistributed
by the Flatpak.

**Security:** `flatpak-spawn --host` intentionally permits programs to run
with the logged-in user's full host privileges. This app is not a restricted
shell sandbox; install it only from a trusted source.
