# Universal Linux Terminal — v1.0.1

**Version 1.0.1 (testing candidate)** · Linux · GTK 3 / VTE 2.91 · Flatpak · GNU GPL v3.0

Universal Linux Terminal is a real, interactive Linux terminal with a friendly command browser and a context-aware command composer. It helps you discover available commands, understand their options, and prepare commands before choosing to run them yourself.

Created by [LionheartTim](https://github.com/LionheartTim).

## Features

- **Real host terminal:** interactive shell, PTY, command history, terminal resizing, job control, and manual command execution.
- **Command discovery:** search commands installed on the host, including executables on `PATH` and Bash builtins.
- **Helpful descriptions:** available usage information, flags, and command descriptions drawn from `--help`, manuals, and distribution package metadata where available.
- **Command builder:** choose options, supply arguments, review a command preview, then insert the text into the terminal. It does **not** run prepared commands automatically.
- **Context-aware suggestions:** guided workflows for Flatpak applications, files and folders, partitions, system services, network interfaces, and more.
- **Distribution-aware helpers:** detects the Linux host and adjusts native package suggestions for systems using APT, Zypper, pacman, DNF, and rpm-ostree. Atomic or transactional distributions are handled more cautiously.
- **English and Dutch UI**, according to the desktop language.

### Tested desktop environments

| Linux distribution | Desktop environment | Result |
| --- | --- | --- |
| Bazzite 44 | KDE Plasma | Tested, working |
| Xubuntu 26.10 | Xfce | Tested, working; one intermittent prompt-safety warning was observed |
| openSUSE Leap 16.0 | GNOME | User-tested, working without error popups |

These are real-world tests, **not a guarantee of compatibility with every Linux distribution or configuration**. An interactive host shell and available tools still depend on the host system.

## Installation — Flatpak bundle (recommended for the GitHub release)

You need a 64-bit Linux system with Flatpak and a working internet connection to install any missing runtime. On a distribution without Flatpak, install it first:

| Distribution | Install Flatpak |
| --- | --- |
| Ubuntu / Xubuntu | `sudo apt update && sudo apt install flatpak` |
| Fedora | `sudo dnf install flatpak` |
| openSUSE | `sudo zypper install flatpak` |
| Arch Linux | `sudo pacman -S flatpak` |
| Bazzite | Flatpak is normally already provided |

### 1. Add Flathub

Add the Flathub remote for your user account, if it is not already configured:

```bash
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
```

**Why Flathub?** The GitHub `.flatpak` bundle contains this application, while a runtime such as **GNOME Platform 50** can be downloaded through Flathub if it is not installed already. Adding Flathub does **not** mean this application has been published on Flathub.

### 2. Install the downloaded `.flatpak` file

When v1.0.1 has been published, download **`Universal-Linux-Terminal-v1.0.1-x86_64.flatpak`** from its GitHub Release. Until then this ZIP is a **local test candidate**, not a published release. Open a terminal in the directory containing the file. For example, if you put it in Downloads:

```bash
cd ~/Downloads
flatpak install --user ./Universal-Linux-Terminal-v1.0.1-x86_64.flatpak
```

If the file is on your Desktop, use that directory instead. The `.flatpak` file does **not** have to be in Downloads. Accept any required GNOME runtime installation when prompted.

### 3. Run Universal Linux Terminal

Open **Universal Linux Terminal** from your desktop's application menu, or run:

```bash
flatpak run io.github.LionheartTim.UniversalLinuxTerminal
```

To verify its Flatpak permissions:

```bash
flatpak info --show-permissions io.github.LionheartTim.UniversalLinuxTerminal
```

To remove a per-user installation:

```bash
flatpak uninstall --user io.github.LionheartTim.UniversalLinuxTerminal
```

## Installation — directly from Flathub (only after publication)

The Flathub application listing is **separate from the GitHub Release bundle**. If and when Universal Linux Terminal has been accepted and published on Flathub, users will be able to install it with:

```bash
flatpak install --user flathub io.github.LionheartTim.UniversalLinuxTerminal
```

**Until it is listed on Flathub, this command will not work.** Use the GitHub `.flatpak` bundle instructions above in the meantime. Adding the Flathub remote still helps Flatpak obtain the required GNOME runtime.

## Getting started

1. Open Universal Linux Terminal. The right pane is a **real interactive host shell**.
2. Use the left-hand search and categories to browse commands and tasks, including **All installed commands**.
3. Select a command, inspect its description and options, and compose a command such as `lsblk -f`.
4. Choose **Insert into terminal**, review the text at the shell prompt, and press **Enter** yourself to run it.
5. If the application cannot determine that the shell prompt is empty, it may ask for confirmation before inserting text. This is a safety check; do not insert during a running command.

### Pasting multiple lines and stopping

Use **Paste…** (or **Ctrl+Shift+V**) to paste from the clipboard. By default, the application asks for confirmation first. Check **Don't show this warning again** and click **Yes** to remember your choice across app restarts. To re-enable the warning, right-click inside the terminal and enable **Show paste confirmation**. In Bash with *bracketed paste* enabled (the usual default), the entire multi-line block is inserted into the command line **without executing it immediately**. Review it and press **Enter** yourself to execute all its lines. An ordinary **Shift+Enter** is not needed. In shells or programs without bracketed-paste support, pasted line breaks **may still execute commands immediately**. Only paste text you trust, and do not paste while another program is accepting input.

- **Interrupt command (Ctrl+C):** interrupts the foreground command but keeps the terminal window open. It may display `^C`; that is normal terminal feedback.
- **Stop:** closes Universal Linux Terminal after a confirmation dialog, including the active terminal session. You can also close the window using its title-bar close button.


Quick terminal check:

```bash
tty
stty size
ps -p $$ -o comm=
echo "$-"
```

`tty` should report a `/dev/pts/...` device, `stty size` should report rows and columns, and the shell should be interactive (the output of `echo "$-"` includes `i`). Your shell process may differ from Bash if your account is configured to use another shell.

## Important security notice

**Universal Linux Terminal is not a restricted Flatpak sandbox.** It deliberately uses Flatpak host access (`--talk-name=org.freedesktop.Flatpak`) and the host filesystem permission (`--filesystem=host`). This is necessary for its real host shell and host command discovery. Commands run with the privileges of your signed-in account; administrator commands may prompt for additional authorization.

- Review commands, especially commands that delete files, modify disks, install/remove software, or change permissions.
- Prepared commands are not executed automatically, but you control what runs after you press Enter.
- When you select a discovered executable, its `--help` output may be requested. Non-conforming programs can have side effects even when invoked with `--help`; only inspect software you trust.
- Download Flatpak bundles only from releases you trust.

## Build the Flatpak from source

Install `flatpak-builder` through your distribution and configure Flathub. From the extracted source-project root, run:

```bash
bash flatpak/build-flatpak.sh
```

The script builds and exports:

```text
Universal-Linux-Terminal-v1.0.1-x86_64.flatpak
```

The Flatpak manifest is `io.github.LionheartTim.UniversalLinuxTerminal.yml` and uses **GNOME Platform / SDK 50**, bundling GTK3-compatible VTE and its build dependencies. No distribution-specific VTE package is needed to install the Flatpak bundle. Building requires the GNOME SDK, source downloads, and `flatpak-builder`.

### Run the unpackaged Python source instead

For development, install Python 3, PyGObject, GTK 3 and VTE 2.91 using your distribution's package manager. Then:

```bash
bash start.sh
```

The source launcher checks prerequisites and never silently installs dependencies. This native-source method is distinct from using the Flatpak bundle.

## Troubleshooting

**`Failed to open file ... No such file or directory`:** the `.flatpak` file is not in the directory used by the install command. Find its actual location or run the command from the correct directory.

**`No remote refs found` or missing GNOME runtime:** confirm that Flathub is configured for the user installing the bundle using `flatpak remotes`, and that the network works.

**Cannot reach Ubuntu/openSUSE/Fedora package servers inside a VM:** verify the VM has a valid IP address, a default route, working DNS, and functioning virtual-network DHCP. This is not caused by the terminal application.

**The app cannot reach the host shell:** verify your Flatpak permissions using `flatpak info --show-permissions io.github.LionheartTim.UniversalLinuxTerminal`, check host Python 3, and see `FLATPAK-RELEASE.md` and the included diagnostics for host-bridge details.

## License and acknowledgments

Universal Linux Terminal's application source is licensed under the **GNU General Public License version 3 (GPL-3.0-only)**. Copyright © 2026 LionheartTim. You are free to use, study, modify, and redistribute it under the terms of the GPL v3; see the complete [LICENSE](LICENSE). The license comes without any warranty. Its AppStream metadata is licensed **CC0-1.0**. The GNOME runtime, VTE, simdutf, fmt and fast_float have their own third-party licenses and remain subject to their original terms; see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) and the upstream components.

Project author: [LionheartTim](https://github.com/LionheartTim).
