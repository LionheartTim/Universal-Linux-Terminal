#!/usr/bin/env bash
# Non-destructive host bridge check for an installed Universal Linux Terminal.
set -u
APP_ID='io.github.LionheartTim.UniversalLinuxTerminal'

printf '%s\n' '=== Universal Linux Terminal — Flatpak host diagnostics ==='
if ! command -v flatpak >/dev/null 2>&1; then
  echo 'ERROR: flatpak is not installed on this host.' >&2
  exit 1
fi
printf '\nInstalled app:\n'
if ! flatpak info "$APP_ID"; then
  printf '\nERROR: ULT is not installed. Install the built bundle first.\n' >&2
  exit 1
fi
printf '\nEffective Flatpak permissions:\n'
flatpak info --show-permissions "$APP_ID"
printf '\nChecking whether this app can spawn a harmless command on the host:\n'
flatpak run --command=flatpak-spawn "$APP_ID" --host /bin/true
status=$?
if [ "$status" -eq 0 ]; then
  echo 'PASS: flatpak-spawn --host works for this installed app.'
else
  printf '\nFAIL: host probe exited with code %s.\n' "$status" >&2
  printf '%s\n' \
    'Check the printed error and whether the installed permissions include:' \
    '  [Session Bus Policy] org.freedesktop.Flatpak=talk' \
    'If this permission is missing, reinstall the bundle built from the latest manifest.' \
    'Do not install a system package or modify files merely to satisfy this probe.' >&2
fi
exit "$status"
