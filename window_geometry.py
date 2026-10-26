"""Pure GTK-independent sizing policy for the active monitor workarea."""


def fit_dimensions(work_width: int, work_height: int) -> tuple[int, int, int]:
    """Just under half the workarea width and safely below its full height.

    GDK's workarea coordinates are logical pixels (already DPI-aware).
    Keep the helper sidebar usable even on smaller laptop screens.
    """
    if work_width <= 0 or work_height <= 0:
        raise ValueError('Ongeldige schermgrootte')
    # Reserve room for client-side decorations and WM workarea rounding.
    # On KDE/Wayland the reported monitor workarea can still be larger than
    # the drawable client area; a small inset keeps the bottom toolbar visible.
    width = max(1, work_width // 2 - 12)
    height = max(1, work_height - 72)
    sidebar_width = min(340, max(210, round(width * 0.36)))
    sidebar_width = min(sidebar_width, max(120, width // 2))
    return width, height, sidebar_width
