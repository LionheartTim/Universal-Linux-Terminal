# Flatpak build fix — VTE dependency resolution

The previous source package stopped at VTE 0.82.3 Meson configuration:

```
Run-time dependency simdutf found: NO
ERROR: Automatic wrap-based subproject downloading is disabled
```

This update includes three explicit Flatpak build modules BEFORE VTE:

1. simdutf v8.0.0 (CMake)
2. fmt 12.1.0 (CMake)
3. fast_float v8.2.3 (installed headers and pkg-config description)

The VTE module uses `--wrap-mode=nofallback`; it should find each of these dependencies inside `/app`, without downloading Meson subprojects.

## Rebuild on Bazzite

Unzip and REPLACE the entire source tree, then in the new project folder:

```bash
bash flatpak/build-flatpak.sh
```

On success, the existing script produces `Universal-Linux-Terminal-v1.0.0-x86_64.flatpak`.

## Verification

- Manifest YAML parsing passed.
- Shell script syntax check passed.
- Python compilation passed.
- 173 automated tests ran: 168 passed, 5 skipped for missing GTK/VTE desktop session.

Note: This environment cannot run `flatpak-builder` with GNOME SDK branch 50. This fix has NOT yet been verified as a completed Flatpak build. Keep the original working Bazzite source-code version available until the bundle passes interactive desktop testing.
