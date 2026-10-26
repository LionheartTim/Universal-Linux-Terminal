# Distribution safety verification — v0.3.9-alpha

- Baseline: v0.3.8-alpha, validated by the user on Bazzite.
- Scope of this patch: native distro detection and safe command suggestions.
- Result: 40/40 simulated distro fingerprints pass; 16/16 non-mutating safety
  scenarios pass; 6 targeted SteamOS/SUSE tests pass.
- Full test suite: 159 tests run, 154 passed, 5 skipped (requires GTK/VTE desktop).
- Fedora/Bazzite, Debian/Ubuntu, Arch/Manjaro, openSUSE and remaining audit
  fixtures retain their original detected backend.
- SteamOS: Arch family, pacman backend for read-only queries, atomic=True;
  direct pacman host install/remove and pacman-based OS update proposal blocked.
- SLES and SAP immutable: transactionality detected via VARIANT_ID.
- SUSE derivatives: ID_LIKE=suse now recognized, but a missing zypper
  executable still results in no native backend.
- The test suite does **not** simulate real package management transactions,
  the installed system's permission or dependency model, GTK/VTE behavior on
  other distributions, or real SteamOS/SUSE desktops.

To run the tests from this directory:

```bash
python3 -m unittest discover -s tests -v
bash -n start.sh
python3 -m compileall -q .
```

Sources:
- https://www.freedesktop.org/software/systemd/man/latest/os-release.html
- https://susedoc.github.io/doc-modular/main/html/SLE-os-identification/index.html
- https://partner.steamgames.com/doc/steamhardware/steamframe/debugging
