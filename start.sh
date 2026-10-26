#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

# Match the desktop's message locale, rather than hard-coding Dutch.
SYSTEM_LANGUAGE="${LC_ALL:-${LC_MESSAGES:-${LANGUAGE:-${LANG:-en}}}}"
case "${SYSTEM_LANGUAGE,,}" in
  nl|nl_*|nl.*|nl:*)
    no_python='Python 3 ontbreekt; installeer Python 3, PyGObject, GTK3 en VTE 2.91.'
    missing_dep='Ontbrekende of incompatibele afhankelijkheden voor deze Python:'
    package_hint='Installeer deze via de pakketbeheerder van je distributie.'
    no_install='Er wordt niets automatisch geïnstalleerd.'
    ;;
  *)
    no_python='Python 3 is missing; install Python 3, PyGObject, GTK3 and VTE 2.91.'
    missing_dep='Missing or incompatible dependencies for this Python interpreter:'
    package_hint='Install these using your Linux distribution package manager.'
    no_install='Nothing is installed automatically.'
    ;;
esac

if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' "$no_python" >&2
  exit 1
fi
PYTHON_BIN="${ULT_PYTHON:-$(command -v python3)}"
if ! "$PYTHON_BIN" -c 'import gi; gi.require_version("Gtk", "3.0"); gi.require_version("Vte", "2.91"); from gi.repository import Gtk, Vte' 2>/dev/null; then
  printf '%s\n' "$missing_dep" \
    'PyGObject, GTK3, VTE 2.91.' "$package_hint" \
    'Fedora/Bazzite: python3-gobject gtk3 vte291.' \
    'Debian/Ubuntu: python3-gi gir1.2-gtk-3.0 gir1.2-vte-2.91.' \
    'Arch: python-gobject gtk3 vte3.' \
    'openSUSE: python3-gobject typelib-1_0-Gtk-3_0 typelib-1_0-Vte-2.91.' \
    "$no_install" >&2
  exit 1
fi
exec "$PYTHON_BIN" app.py
