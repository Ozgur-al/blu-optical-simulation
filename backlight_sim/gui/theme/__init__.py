"""Dark theme module for Blu Optical Simulation.

Provides the apply_dark_theme() function and palette constants used
throughout the application for consistent dark styling with teal accents.

Usage::

    from backlight_sim.gui.theme import ACCENT, TEXT_MUTED, KPI_GREEN
"""

from __future__ import annotations

import os
from PySide6.QtWidgets import QApplication
import pyqtgraph as pg

__all__ = [
    "apply_dark_theme",
    "BG_BASE", "BG_PANEL", "BG_INPUT", "BG_HOVER",
    "ACCENT", "ACCENT_HOVER",
    "TEXT_PRIMARY", "TEXT_MUTED",
    "KPI_GREEN", "KPI_ORANGE", "KPI_RED",
    "GL_BG",
    "BORDER_GAP",
]

# --- Palette constants ---
BG_BASE   = "#1e1e1e"
BG_PANEL  = "#252525"
BG_INPUT  = "#181818"
BG_HOVER  = "#2d2d2d"
ACCENT       = "#00bcd4"
ACCENT_HOVER = "#26c6da"
TEXT_PRIMARY = "#e0e0e0"
TEXT_MUTED   = "#888888"
BORDER_GAP   = 2

# --- KPI threshold colors ---
KPI_GREEN  = "#4caf50"
KPI_ORANGE = "#ff9800"
KPI_RED    = "#f44336"

# --- OpenGL background (QSS doesn't affect GL widgets) ---
GL_BG = (30, 30, 30, 255)


def apply_dark_theme(app: QApplication) -> None:
    """Apply the dark theme to the QApplication instance.

    Must be called AFTER QApplication() is created but BEFORE any
    widgets (especially pyqtgraph widgets) are constructed.

    Args:
        app: The running QApplication instance.
    """
    # Load QSS from the same directory as this module
    qss_path = os.path.join(os.path.dirname(__file__), "dark.qss")
    with open(qss_path, encoding="utf-8") as fh:
        qss_content = fh.read()
    app.setStyleSheet(qss_content)

    # Configure pyqtgraph global defaults — must happen before any pg widget
    # is constructed so plots pick up the dark background automatically.
    # NOTE: use pg.setConfigOption (singular), NOT pg.setConfigOptions (plural)
    pg.setConfigOption("background", BG_BASE)
    pg.setConfigOption("foreground", TEXT_PRIMARY)
    pg.setConfigOption("antialias", True)
