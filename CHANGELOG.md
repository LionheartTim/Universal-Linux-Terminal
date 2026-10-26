## v1.0.0 — Full descriptions in the scrolling sidebar (2026-10-26)

- Fix help paragraphs such as `lsb-release` that wrap at ordinary words: the
  parser now joins consecutive prose lines instead of discarding the last line.
- Replace the static Gtk.Label-in-viewport help area with a read-only,
  selectable Gtk.TextView that wraps against the actual sidebar width.
- Keep the existing vertical scroll area; no manual truncation of on-screen
  lines, and no changes to the host Bash/PTY bridge or Flatpak permissions.

## v1.0.0 — Flatpak host command descriptions (2026-10-26)

- Improve the left sidebar descriptions for discovered host commands whose
  `--help` text contains only usage, e.g. `usbip`.
- Reuse the established Flatpak host bridge to query local `whatis` / `man`
  documentation; fall back to read-only RPM, dpkg or pacman package metadata.
- Clearly label package-level descriptions and show an honest no-documentation
  message if none of the local sources provide a reliable description.
- Fetch only after a command is selected in the existing background worker;
  preserve options, preview, command insertion, search and host Bash/PTY.
- No extra Flatpak permissions or host system packages are required by this change.

## v1.0.0 Flatpak integration candidate — host data and insert repair

- Read host command output through explicit forwarded, anonymous file descriptors rather than assuming the host can access a Flatpak-private temporary pathname.
- Allow reviewed host commands to be inserted when Flatpak metadata falsely reports a missing executable; no Enter is added.
- Prevent VTE bracketed-paste markers being injected into the bridged host terminal from the helper and clipboard buttons.
- Keep host Bash/PTy relay, Flatpak permissions, icon, distro composition and menu identity unchanged.
- Unit tests do not establish real Flatpak integration; a Bazzite rebuild and in-app test remain mandatory.

## v1.0.0 — Flatpak host metadata / command inventory correction (test build)

- Fix output capture for host-side `/etc/os-release`, PATH discovery and help options when started via KDE/GTK.
- Use one-shot host output files in the private Flatpak cache; avoid repeated command execution.
- Preserve the verified real Bash host PTY and existing Flatpak permissions.
- Improve error reporting for failed host command discovery and unavailable help output.

## v1.0.0 Flatpak host PTY fallback — October 2026

- Fix popup requiring `util-linux-script` on Bazzite/Fedora 44: prefer the host's existing Python 3 for a host-owned PTY, with `script` fallback only if Python 3 is absent.
- Add separate binary-safe keyboard/output and window-resize relay, retaining normal Bash job control and host `/dev/pts` visibility.
- Leave local source build, command discovery, GTK layout, and the combination engine unchanged.
- Automated local PTY integration tests pass; actual installed Flatpak on Bazzite still requires validation.

## v1.0.0 — Flatpak host `ttyname` correction candidate
- Fix reported `tty: ttyname error: No such device` in Flatpak interactive shell.
- Allocate shell PTY via util-linux `script` **on the host** using
  `flatpak-spawn --host --directory=...` and a safe, quoted shell command.
- Remove bundled host-spawn binary: its PTY belonged to the sandbox mount
  namespace and was not visible to host `ttyname(0)`.
- Preserve the official icon, VTE/GnuTLS build, command discovery, distro
  and context-composition engine, without adding extra Flatpak permissions.
- Requires host util-linux `script`; Bazzite/GTK/VTE validation pending.

## v1.0.0 — Flatpak host job-control / real PTY correction
- Replace `flatpak-spawn --host` **for the interactive shell only** with
  `host-spawn` v1.6.2, bundled and downloaded with a pinned SHA256 at build time.
- Start the host login shell with an actual controlling PTY to restore
  Ctrl+C, Ctrl+Z, `jobs`, `fg`, `bg`, full-screen applications, and resizing.
- Keep the non-interactive distribution/package/command queries on
  `flatpak-spawn --host` and leave source-run behavior unchanged.
- Keep original Flatpak rights, official ULT icon, GNOME/VTE build fixes.
- Add dedicated host-spawn packaging tests and documentation.
- Real Flatpak PTY operation still needs validation on Bazzite.

## Flatpak host PTY FD and GnuTLS correction (release-source update)
- Remove redundant `--forward-fd=0/1/2` from `flatpak-spawn --host` interactive shell: fixes `Invalid fd '0'` reported on Bazzite.
- Re-enable GnuTLS in bundled VTE 0.82.3 via `-Dgnutls=true` to avoid unencrypted disk-backed stream warning.
- Add source-level regression tests for both, without changing GUI or extra Flatpak permissions.
- Requires a new Flatpak build and real interactive host-PTY check before GitHub release.

## v1.0.0 — Flatpak host startup correction

- Do not block host shell on redundant preflight that can falsely fail at app startup.
- Attempt the real host shell via `flatpak-spawn --host` directly, never a sandbox shell.
- Make terminal child exit/spawn failure status visible even without a heading.
- Add a missing-flatpak-spawn error and dedicated regressions.

# Flatpak host diagnostics update — 1.0.0 source package

- Preserve the approved official ULT icon and all previous Flatpak build modules.
- Replace generic `Flatpak host access is unavailable` startup popup with the actual
  stderr and return code from the harmless `flatpak-spawn --host /bin/true` probe.
- Include `flatpak/diagnose-host.sh`, which checks the **installed** app's
  permissions and host command access without changing host configuration.
- No new permissions are granted; no fallback into a misleading sandbox shell.
- This improves diagnosis only: live Bazzite host bridge still requires validation.

# Changelog

## Version 1.0.0 — sidebar description display adjustment
- Full multi-line `--help` descriptions are preserved in the sidebar (including `lsb-release` sentences wrapped across lines).
- Command information uses a read-only wrapping GTK text view inside the existing scroll area; no horizontal clipping.
- Host PTY, Flatpak permissions, command discovery and the combination engine are unchanged.


## 1.0.0 (2026-10-25)

- Add a thin, fixed footer at the bottom of the main window (under both panes).
- Show "Version 1.0.0" and "Made by LionheartTim", with the name linking to
  https://github.com/LionheartTim in the default web browser.
- Respect English and Dutch UI locales in the footer; update the title bar
  and displayed version to 1.0.0.
- Preserve the v0.3.9-alpha Bazzite-tested terminal, combination engine,
  package detection and dynamic command-help behavior without changes.


## 0.3.9-alpha (2026-10-25)

- Fix SteamOS classification: still Arch/pacman for read-only queries, but
  treat its host as read-only and block ordinary pacman install/remove suggestions.
- Do not present pacman -Qu as a SteamOS OS update check; do not confuse
  SteamOS with an rpm-ostree deployment even if rpm-ostree is on PATH.
- Recognize transactional SUSE `VARIANT_ID` including `transactional` and
  `server-sap-transactional`; withhold ordinary zypper host mutations.
- Recognize `ID_LIKE=suse` and legacy SUSE Linux Micro identifiers.
- Add the audit's 40 simulated distro fingerprints and 16 safety scenarios
  to permanent unit tests, plus 5 focused regression checks.
- No changes to the working Bazzite VTE shell, GUI, command options, or
  context-aware combination engine.

## 0.3.8-alpha (2026-10-25)

- Replace generic discovered-command information with dynamically retrieved
  command purpose, usage and example flags in the left description area.
- Make that area independently scrollable to keep the bottom controls visible.
- After preparing options in the dialog, show which flags were selected and
  their descriptions in the same sidebar panel.
- Reuse bounded `--help` introspection and cache results across sidebar/dialog;
  run lookups in a background thread, ignoring outdated requests.
- Do not change the interactive VTE terminal, package detection, combination
  engine, existing help options dialog, or command insertion behavior.
- Add headless parser/integration regressions for real command descriptions,
  UTF/terminal-control sanitization, translations and UI wiring.

## 0.3.7-alpha (2026-10-25)

- Automatically fill the lower option pane after selecting an installed
  command; remove the Show available options button entirely.
- Retain option filtering, checkbox selection, Value editing, manually entered
  extra arguments and live command preview.
- Fetch help in a background worker; invalidate late responses when selection
  changes, cache per selected command, and disable Prepare until loading ends.
- Keep explicit warning: automatic `--help` inspection may have side effects
  in nonconforming programs; prepared shell commands never auto-execute.
- Add UI regression checks for selection-triggered help discovery.

## 0.3.6-alpha (2026-10-25)

- Fix **Choose command options…** raising `TypeError: argument iter:
  Expected Gtk.TreeIter, but got studio_ui._ResultTuple` on Bazzite.
  The Gtk.TreeModelFilter binding yields `(visible, Gtk.TreeIter)`;
  unpack and select only the valid iterator, not the result pair.
- Keep direct search, the option dialog, help parsing, the terminal,
  combination engine and existing package/distro features unchanged.
- Add regression tests simulating the actual PyGObject result tuple,
  including a filtered-out entry that must not be selected.


## 0.3.5-alpha (2026-10-25)

- Main left-hand search now finds matching installed commands as well as the
  built-in actions, using one cached, asynchronously scanned PATH/Bash index.
- Clicking a direct command result stages a quoted draft in the existing
  terminal command preview; **Choose command options…** opens the option
  builder with that command already selected.
- Remove the unnecessary modal warning that appeared when requesting `--help`.
  Keep the request user-initiated, and explain the residual risk persistently
  within the options dialog. Help requests remain bounded and not sandboxed.
- Leave Bazzite detection, shell PTY, native packages, typed combination rules,
  English/Dutch UI, Stop/Reset and existing full command browser in place.
- Add regression tests for shared searching, ranking and GUI wiring.

## 0.3.4-alpha (2026-10-25)

- Added `option_discovery.py`: a generic, opt-in help-option parser for installed
  executables (bounded `--help`) and Bash builtins (`help`). No per-command flag
  table, no automatic execution during inventory or selection.
- Added filterable checkboxes, human-readable help descriptions, editable
  value fields for parameterized options, and a live shell-escaped preview in
  the existing All installed commands dialog. `lsblk -f` and `-o NAME,SIZE`
  can now be built with clicks instead of manually entering flags.
- Preserve the original manual argument field for commands with unusual help
  syntax or nested subcommands. Require explicit warning/consent before
  requesting `--help` from arbitrary installed executables.
- Keep the confirmed Bazzite v0.3.3-alpha baseline: GTK3/VTE PTY, composition
  engine, distro detection, locale handling, Stop/Reset, and all sidebar groups.
- Added regression tests for parser formats, option values, safe quoting,
  explicitly requested help, Bash builtin help and real `lsblk` help.
- GTK/VTE desktop tests still need real Bazzite validation.

## 0.3.3-alpha (2026-10-25)

- Added `distro_support.py` detection via the freedesktop `/etc/os-release`
  standard plus `ID_LIKE` and actual executable checks. Detect Debian/Ubuntu,
  Fedora, Arch, openSUSE and key derivative/atomic variants.
- Added Native packages sidebar for OS-appropriate search/info, package lists,
  read-only update checks and reviewed install/remove proposals on mutable hosts.
- Treat Bazzite / rpm-ostree and transactional openSUSE differently; do not
  propose traditional host-package install/remove operations on these systems.
- Show detected distribution and package manager in the sidebar. Add
  typed package rules and context-aware suggestions to the existing engine.
- Keep terminal, command finder, Bazzite helpers, localization, Stop/Reset,
  Steam wizard and other tested composition routes unchanged.
- Added simulated cross-distro detection, command safety and integration tests;
  real desktop validations still pending. See `DISTRO-SUPPORT.md`.


## 0.3.2-alpha (2026-10-25)

- Add independent, extensible `composition_engine.py`: typed subjects, declarative
  registered recipes, required slots, availability checks and explicit risks.
- Offer context-aware read-only suggestions for Flatpak apps, real disk
  partitions, local files/folders, systemd services, hosts/IPs, Podman
  containers and network interfaces. No generic shell string concatenation.
- Route the existing Flatpak app + volume + folder command through the same
  engine; keep the separate Steam helper under **Extra**.
- Add sidebar actions in the existing Files/Network/Containers categories;
  no standalone Mix & Match category. Keep the dynamic installed-command list.
- Preserve the one real VTE/PTy, Stop/Reset, en/nl locale, and half-screen layout.
- Add typed-slot, guard, quoting, missing dependency and no-execution tests.
- Desktop widget behavior still needs testing on GTK/VTE in Bazzite.


## 0.3.1-alpha (2026-10-25)

- Remove separate Mix & Match sidebar category. Give All installed commands its own category; move the unchanged Steam storage wizard under Extra as the last category.
- Add a contextual command preview based on selecting a Flatpak app and then a data volume/folder. A useful suggestion popup offers the next step and a clear/restart action.
- Search real Flatpak AppStream results by app ID/name; allow selecting an app rather than only preparing a raw search term. Existing App information and App permissions selectors also preserve app context.
- Recognize both System > Disks and partitions and a dedicated HDD/SSD folder entry as disk-selection steps after an app is selected.
- Validate app identifiers, chosen disk partition and existing target folder; never silently concatenate commands or execute anything. Only installed Flatpak apps can receive app-specific filesystem overrides. Unmounted volumes first get a mount command proposal.
- Preserve one VTE PTY, manual Enter, distro shell banner, terminal reset/Stop, English/Dutch localization and automatic window sizing.
- Add contextual composition and sidebar wiring regressions.

## 0.3.0-alpha (2026-10-25)

- Add dynamic installed-command finder (PATH executables and Bash builtins), filter and safe argument staging.
- Add beginner-friendly Mix & Match Steam storage workflow using actual `lsblk` volume inventory, mount preparation, chosen library folder, Flatpak access command or native Steam instructions. No hidden execution.
- Translate new builder explanations into Dutch; keep English fallback.
- Rename Ctrl+C button to Stop, preserving SIGINT behavior.
- Add headless regression tests for command discovery, quoting and disk workflow.


## 0.2.6-alpha (2026-10-25)

- Reduce initial half-screen width slightly and leave a 72-logical-pixel height allowance to keep bottom controls above the screen edge on KDE/Wayland.
- Remove sidebar Copy command and Open terminal buttons; retain Insert into terminal.
- Add Reset Terminal to the bottom toolbar, clearing VTE display and scrollback without replacing or interrupting the running shell. Redraw the prompt via Ctrl+L when the shell is definitely foreground.
- Make bottom toolbar responsive so buttons wrap instead of clipping on narrower displays.
- Add automatic Dutch/English GUI translations based on the system message locale; English fallback for other locales. Shell arguments remain untouched.
- Allow distro-specific shell banners to appear naturally (no Bazzite-specific suppression).
- Update launcher diagnostics and add locale, reset, and geometry regression tests.

# 0.2.5-alpha

Compacter hoofdvenster zonder de bovenste applicatietitel, uitleg en
statusregel. Gewone terminals tonen geen status/argv-labels boven de
shellprompt. Shellstart met `-i` in plaats van `-l`, zodat het Bazzite login-MOTD
niet verschijnt en normale interactieve shellconfiguratie blijft werken.
Werkruimte van actieve monitor uitlezen via GDK; vensterbreedte 50%, hoogte
100% en zijbalk responsief. Werkruimte/resolutie/schaal opnieuw detecteren
bij monitorwijziging (met lichte periodieke controle voor Wayland-backends).
Geen globale Bazzite/gebruikersconfiguratie aangepast.

# 0.2.4-alpha

Herstelt de startfout die in 0.2.3-alpha nog aanwezig was op Bazzite.
PyGObject kan voor Vte.Terminal.spawn_async `child_setup_data` als extra
positioneel argument verwachten: nu staat de verplichte `None` vóór de
numerieke timeout (-1). Dit voorkomt dat `None` op argument 9 terechtkomt.
De oude GLib.unix_signal_add-aanroep is vervangen door GLibUnix.signal_add
met fallback voor oudere distributies; dit voorkomt de PyGIDeprecationWarning.
Regressietest simuleert expliciet de Bazzite-argumentcontrole; desktopvalidatie
van de daadwerkelijke PTY blijft nodig.

# 0.2.3-alpha

Bazzite startfout opgelost: VTE GTK3 `spawn_async` accepteert niet de expliciet
meegegeven extra `None` voor `user_data`; die is verwijderd. Normaal typen,
outputselectie, shellprocessen en commandohulp delen één VTE/PTY. Contextmenu
voor selectie/kopiëren/plakken; nette GTK-afsluiting en SIGINT-afhandeling
tegen de terugkerende KeyboardInterrupt-traceback in de launcher. PTY-procesgroep-
check heeft nu een onbekend-resultaat in plaats van onterecht blokkeren.

# 0.2.2-alpha

PTy/shell-functionaliteit verbeterd zonder de enkele terminal of read-only
voorbereiding van commando's te veranderen. Terminal start ook in container;
systeemwijzigende commandohulp is daar nog geblokkeerd. Veiliger plakken via
VTE met oudere-VTE-fallback; shellfallback en distro-onafhankelijker startscript.

# 0.2.1-alpha

Direct één normale terminal bij openen. Welkom-tab verwijderd. Geen onderscheid
meer tussen vrije terminal en opdrachtterminal. De linker hulpmiddelen plakken
commando's zonder Enter in de bestaande terminal. Uitvoeren gebeurt via de shell.
Normaal sluiten met bevestiging, geen blokkade omdat de shell nog openstaat.
