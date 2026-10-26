# Flatpak interactive host PTY — ttyname repair candidate

## Reported problem

After introducing `host-spawn -pty`, the shell was interactive but the host
could not resolve its slave device name:

```text
sh-5.3$ tty
tty: ttyname error: No such device
sh-5.3$ echo "$-"
himBHs
sh-5.3$ ps -p $$ -o comm=
sh
```

The old helper made the PTY in **Flatpak's mount namespace** and passed the
slave descriptor to the host. `ttyname(0)` on the host cannot reliably map
that descriptor to a path in the host's `/dev/pts` mount.

## Candidate fix

The shell now starts through `flatpak-spawn --host` + the host's util-linux
`script` command:

```text
flatpak-spawn --host --directory=<cwd> --env=TERM=xterm-256color \
  /usr/bin/script --quiet --return --flush \
  --command 'exec /bin/bash -i' /dev/null
```

The actual executable and shell path are discovered from the host. `script`
allocates the PTY **on the host**, so `/dev/pts/N` exists there. Passing
`/dev/null` tells script not to store terminal activity in a typescript log.
No new Flatpak permission or host-installed custom helper is required.

The host needs the standard util-linux `script` executable; if it is missing,
the app now explains the requirement instead of launching a misleading shell.

* Only the interactive session changes. Host package information, command
  discovery, help descriptions and context engine still use the original
  `flatpak-spawn --host` noninteractive bridge.
* The source (non-Flatpak) VTE shell is unchanged.
* A PTY is still created by VTE for on-screen keyboard/selection. This
  solution creates a **second** PTY on the host where the shell is attached.
* The host-shell startup uses no external network requests or logs.

## Rebuild on Bazzite

Replace your project source with the full ZIP and run:

```sh
cd ~/Desktop/Universal-Linux-Terminal
bash flatpak/build-flatpak.sh
flatpak install --user --reinstall ./Universal-Linux-Terminal-v1.0.0-x86_64.flatpak
flatpak run io.github.LionheartTim.UniversalLinuxTerminal
```

## Release gate: real GTK/VTE + Flatpak on Bazzite

Inside the ULT Flatpak, verify `tty`, `echo "$-"`, `ps -p $$ -o comm=`,
`stty size`, `sleep 30` then Ctrl+Z/`jobs`/`fg`/Ctrl+C, `nano`/`top`,
terminal resize, Stop and Reset, then host `cat /etc/os-release` and commands.
A real Bazzite desktop test is needed. Headless tests **cannot** certify
job control or resizing across the Flatpak boundary.

Upstream documentation:
* https://man7.org/linux/man-pages/man1/flatpak-spawn.1.html
* https://github.com/util-linux/util-linux/blob/master/term-utils/script.1.adoc
