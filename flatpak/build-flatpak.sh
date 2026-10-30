#!/usr/bin/env bash
# Run inside the project root. Never install a system package automatically.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
ID='io.github.LionheartTim.UniversalLinuxTerminal'
BUNDLE='Universal-Linux-Terminal-v1.0.1-x86_64.flatpak'
if ! command -v flatpak >/dev/null; then
  echo 'Flatpak is missing; install it through your distribution first.' >&2
  exit 1
fi
if ! command -v flatpak-builder >/dev/null; then
  echo 'flatpak-builder is missing; install it through your distribution first.' >&2
  exit 1
fi
if ! flatpak remotes --columns=name | grep -Fxq flathub; then
  echo 'Flathub remote is missing. Add it before building:' >&2
  echo 'flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo' >&2
  exit 1
fi
flatpak install --user -y flathub org.gnome.Sdk//50 org.gnome.Platform//50
flatpak-builder --force-clean --repo="$(pwd)/repo" "$(pwd)/flatpak-build" "$ID.yml"
flatpak build-bundle "$(pwd)/repo" "$BUNDLE" "$ID"
echo "Bundle built at: $(pwd)/$BUNDLE"
echo "Install using: flatpak install --user ./$BUNDLE"
