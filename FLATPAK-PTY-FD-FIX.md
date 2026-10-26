**Superseded for interactive shells:** see `FLATPAK-HOST-JOB-CONTROL.md`.

# Flatpak host PTY FD + VTE GnuTLS build correction (v1.0.0)

The prior source build produced two user-visible warnings upon launching the
Flatpak on Bazzite:

    WARNING: GnuTLS not enabled; data will be written to disk unencrypted!
    Invalid fd '0'

## PTY fix

`flatpak-spawn` already forwards the inherited standard input, standard output,
and standard error (FDs 0, 1, 2). Explicit `--forward-fd=0`, `=1`, and `=2`
are redundant and were rejected on the tested Bazzite installation. They have
been removed. The host-shell launch remains:

    flatpak-spawn --host --watch-bus --directory=<working-directory> <shell> -i

The interactive VTE PTY and `flatpak-spawn` host permissions are unchanged.
There is **no fallback to a sandbox shell** and no new Flatpak permissions.

## GnuTLS change

VTE 0.82.3 is now configured with `-Dgnutls=true` rather than `false`,
so its disk-backed stream is built with crypto support. The GNOME 50 SDK
must provide the `gnutls` development library. You can check before building:

    flatpak run --command=pkg-config org.gnome.Sdk//50 --modversion gnutls

If this fails, do not turn GnuTLS back off merely to suppress the warning;
resolve the missing dependency first. The change has been statically tested
but not built against the SDK here.

## Bazzite test

    bash flatpak/build-flatpak.sh
    flatpak install --user --reinstall ./Universal-Linux-Terminal-v1.0.0-x86_64.flatpak
    flatpak run io.github.LionheartTim.UniversalLinuxTerminal

Then verify a working interactive prompt, `tty`, `pwd`, `whoami`, `cat /etc/os-release`,
`lsblk -f`, Stop and Reset Terminal. Confirm output is from the **host**.
This source package is not a precompiled Flatpak bundle.
