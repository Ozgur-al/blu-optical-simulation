"""Dark theme module for Blu Optical Simulation.

Provides ``apply_dark_theme()`` and palette constants used across the
application. The palette is the *Raydient* warm-neutral dark scheme:
warm-tinted greys, cyan secondary, amber primary action accent.

All previously-exported names are preserved so existing imports keep
working — only the values changed.

Usage::

    from backlight_sim.gui.theme import ACCENT, TEXT_MUTED, KPI_GREEN
"""

from __future__ import annotations

import os

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication
import pyqtgraph as pg

__all__ = [
    "apply_dark_theme",
    "BG_BASE", "BG_PANEL", "BG_INPUT", "BG_HOVER",
    "ACCENT", "ACCENT_HOVER",
    "ACTION_AMBER", "ACTION_AMBER_HOVER",
    "TEXT_PRIMARY", "TEXT_MUTED",
    "KPI_GREEN", "KPI_ORANGE", "KPI_RED",
    "GL_BG",
    "BORDER_GAP",
    "LINE_COLOR",
    "FONT_UI", "FONT_MONO",
]

# --- Palette constants (Raydient warm-neutral) ---
# Approximations of oklch values from the design spec.
BG_BASE   = "#221f1c"   # oklch(0.16 0.008 60) — viewport / window
BG_PANEL  = "#272421"   # oklch(0.19 0.008 60) — dock / panel background
BG_INPUT  = "#1c1a18"   # darker than base — recessed input fields
BG_HOVER  = "#36322e"   # oklch(0.26 0.008 60) — hover / segment-active

# Secondary accent (cyan) — selection, focus rings, group titles
ACCENT       = "#7ec3d6"   # oklch(0.82 0.12 210)
ACCENT_HOVER = "#9fd2e0"

# Primary action accent (amber) — Run button, active tab, progress fill
ACTION_AMBER       = "#e8b04a"  # oklch(0.82 0.16 75)
ACTION_AMBER_HOVER = "#f4c265"  # oklch(0.90 0.18 80)

TEXT_PRIMARY = "#f1ede4"   # oklch(0.96 0.005 80)
TEXT_MUTED   = "#807c74"   # oklch(0.58 0.010 70)
LINE_COLOR   = "#48433e"   # oklch(0.32 0.008 60)
BORDER_GAP   = 2

# --- KPI threshold colors (warm-shifted to match palette) ---
KPI_GREEN  = "#7dd1a0"
KPI_ORANGE = "#e8b04a"
KPI_RED    = "#df7565"

# --- OpenGL background (QSS doesn't affect GL widgets) ---
GL_BG = (34, 31, 28, 255)  # matches BG_BASE

# --- Font stacks ---
FONT_UI = "Inter"
FONT_MONO = "JetBrains Mono"


def _register_application_fonts(app: QApplication) -> None:
    """Set the application default font to Inter (or fallback) at 10pt."""
    families = QFontDatabase.families()
    ui_family = FONT_UI if FONT_UI in families else (
        "Segoe UI" if "Segoe UI" in families else app.font().family()
    )
    font = QFont(ui_family, 10)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)


def apply_dark_theme(app: QApplication) -> None:
    """Apply the Raydient dark theme to the QApplication instance.

    Must be called AFTER QApplication() is created but BEFORE any
    widgets (especially pyqtgraph widgets) are constructed.
    """
    _register_application_fonts(app)

    qss_path = os.path.join(os.path.dirname(__file__), "dark.qss")
    with open(qss_path, encoding="utf-8") as fh:
        qss_content = fh.read()
    app.setStyleSheet(qss_content)

    # pyqtgraph defaults — must precede any pg widget construction
    pg.setConfigOption("background", BG_BASE)
    pg.setConfigOption("foreground", TEXT_PRIMARY)
    pg.setConfigOption("antialias", True)
