# Universal Linux Terminal — distribution support (v0.3.9-alpha)

This release adds **OS detection and distribution-specific command preparation** without changing the previously tested VTE shell or its typed command-combination engine. It is not a software installer or an exhaustive package manager.

## How it detects Linux

- Read `/etc/os-release`, falling back to `/usr/lib/os-release`. Parse `ID`, `ID_LIKE`, `PRETTY_NAME`, `VERSION_ID`, `VARIANT_ID`; never `source` or execute this file.
- Prefer the explicit `ID` over the family hints in `ID_LIKE`.
- Check installed executables before offering a native manager, including the difference between `dnf` and `dnf5`.
- Detect known image-based variants and `/run/ostree-booted`; do **not** treat an atomic Fedora-based desktop like a regular DNF host. SteamOS is treated as an Arch-based read-only host, **not** an rpm-ostree host.
- Recognize SUSE `ID_LIKE=suse` and transactional `VARIANT_ID` values, including `transactional` and `server-sap-transactional`.
- In a detected sandbox/container, read-only native queries can refer to that environment; native host-changing command proposals are withheld.
- Unknown distributions and missing managers remain usable for normal terminal commands, Flatpak helper commands and the separate dynamically discovered command inventory. No manager is guessed from the mere existence of an unrelated executable.

## Native command availability

| OS group | Examples | Backend | Native helper actions |
|---|---|---|---|
| Debian family | Debian, Ubuntu, Xubuntu, Linux Mint, Pop!_OS, KDE neon | APT (`apt`, `apt-cache`) | Search, info, installed, pending updates; install/remove proposals when permitted |
| Fedora family | Fedora Workstation, Nobara | DNF (`dnf` or `dnf5`) | Search, info, installed, pending updates; install/remove proposals when permitted |
| Arch family | Arch, Manjaro, EndeavourOS, CachyOS | pacman | Search, info, explicitly installed, pending updates; install/remove proposals when permitted |
| SteamOS (read-only Arch-based) | SteamOS 3 | pacman (queries only) | Search, info, installed; no ordinary host install/remove; no pacman-based SteamOS OS-update check |
| openSUSE family | openSUSE Leap, Tumbleweed | Zypper | Search, info, installed, pending updates; install/remove proposals when permitted |
| Fedora image-based | Bazzite, Silverblue, Kinoite, other known OSTree variants | rpm-ostree | Deployment status and read-only upgrade check. Native install/remove intentionally not proposed |
| SUSE transactional | MicroOS, Aeon, Kalpa, immutable SLES/SLES for SAP, SUSE Linux Micro | Zypper read-only | Queries only; host package modification proposals intentionally withheld |
| SUSE-derived | Distributions with `ID_LIKE=suse` | Zypper when available | Backend matches the actual installed tool; ordinary mutation proposals only when not transactional |
| Unknown or missing backend | Any other Linux | None | Standard terminal and available command discovery remain functional |

**Cautions:** Native install/remove proposals use `sudo` only when present. The app stages commands but never runs them by itself. Package managers may ask for authorization or dependency confirmation when the user presses Enter. On Arch, avoid partial upgrades and update your whole system first. On image-based systems, Flatpak/Distrobox is often preferable for desktop apps. On Bazzite, the existing `ujust`/`rpm-ostree` helpers are kept.

## Command composition

The existing typed engine remains unchanged for Flatpak + volume + folder, services, files, network, and containers. A new `package` selection is validated by `distro_support.py`; the engine registers only relevant `package.search`, `package.info` and (for mutable non-sandboxed systems with sudo) `package.install` recipes. The popup suggests other actions using the same selected package name, without changing the live shell until **Insert into terminal** and Enter.

The native helper's Search and Package information actions accept **exactly one package name or search token**, not complex regex strings/flags. Full, unrestricted arguments are still available by typing in the terminal or using All installed commands. Package removal is an explicit separate action with a warning, not an automatic suggestion.

## Known limits and test recommendations

- Automated distro fixtures are **simulations**, now included as `tests/test_universality_matrix.py` (40 distribution fingerprints, 16 safety transitions, additional regression tests). Use real Ubuntu/Xubuntu, Arch, SUSE and SteamOS desktop installations before calling multi-distro support fully verified. Bazzite has been validated by the user.
- A package manager may be missing or use different options in a future distribution release. The app leaves missing tools disabled; it does not install dependencies automatically.
- `rpm-ostree upgrade --check`, `dnf check-update`, `pacman -Qu` and equivalent update commands can have special exit codes or stale package metadata; the terminal shows their actual output.
- GUI needs GTK3, PyGObject and **VTE 2.91** (GTK3 binding), so a minimal installation may need distro-specific packages. The startup script prints hints; consult the distro package manager for precise package names if they change.
- Package search is text output in the terminal for now, not a universal graphical software-store browser. That can be a future extension without changing the backend.

## Source boundaries

- `distro_support.py`: pure identification, allowlist of supported native backends, argument recipes.
- `core.py`: maps `NativeRecipe` to the existing `Command` interface, adds appropriate catalog entries.
- `composition_engine.py`: registers package-context rules only when appropriate.
- `app.py`: distro indicator, sidebar actions, dialogs and staging; no backend subprocess execution.
- `tests/test_distro_support.py`: distro families, immutable/transactional/sandbox boundaries, invalid arguments, engine integration.
- `tests/test_universality_matrix.py`: permanent 40-distribution fixture matrix, 16 additional safety checks and specific SteamOS/SUSE regression tests.

OS identification standard: https://www.freedesktop.org/software/systemd/man/latest/os-release.html

References: [SUSE OS identification](https://susedoc.github.io/doc-modular/main/html/SLE-os-identification/index.html), [SteamOS read-only package-management context](https://partner.steamgames.com/doc/steamhardware/steamframe/debugging).
