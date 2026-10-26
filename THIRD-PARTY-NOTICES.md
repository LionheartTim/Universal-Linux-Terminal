# Third-party notes

The Flatpak builds VTE and its declared library dependencies in the app, and
uses the GNOME runtime. No additional `host-spawn` binary is bundled in this
revision. The host terminal requires the distro-provided util-linux `script`
command; it is **not** redistributed in the Flatpak.

**Security:** `flatpak-spawn --host` intentionally permits programs to run
with the logged-in user's full host privileges. This app is not a restricted
shell sandbox; install it only from a trusted source.
