"""Splash screen widget for Blu Optical Simulation.

Shown immediately on launch while heavy modules (PySide6, pyqtgraph, NumPy)
are imported and the main window is constructed.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QFontMetrics
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QHBoxLayout, QSizePolicy

from backlight_sim.gui.theme import BG_BASE, BG_INPUT, ACCENT, TEXT_PRIMARY, TEXT_MUTED
from backlight_sim.__version__ import __version__

__all__ = ["SplashScreen"]

_SPLASH_W = 480
_SPLASH_H = 280
_BORDER_COLOR = "#333333"


class SplashScreen(QWidget):
    """Frameless splash screen shown during application startup.

    Displays the app name, subtitle, an animated progress bar, status text
    and the current version number in the bottom-right corner.
    """

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.SplashScreen)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setFixedSize(_SPLASH_W, _SPLASH_H)

        # Centre on the primary screen
        screen = self.screen()
        if screen is not None:
            geom = screen.availableGeometry()
            self.move(
                geom.center().x() - _SPLASH_W // 2,
                geom.center().y() - _SPLASH_H // 2,
            )

        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"QWidget {{ background-color: {BG_BASE}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 30)
        root.setSpacing(0)

        # ---- App name ------------------------------------------------
        self._lbl_title = QLabel("Blu Optical Simulation")
        font_title = QFont()
        font_title.setPointSize(24)
        font_title.setBold(True)
        self._lbl_title.setFont(font_title)
        self._lbl_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._lbl_title.setStyleSheet(f"color: {ACCENT}; background: transparent;")
        root.addWidget(self._lbl_title)

        root.addSpacing(6)

        # ---- Subtitle ------------------------------------------------
        self._lbl_subtitle = QLabel("Backlight Unit Optical Simulator")
        font_sub = QFont()
        font_sub.setPointSize(10)
        self._lbl_subtitle.setFont(font_sub)
        self._lbl_subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._lbl_subtitle.setStyleSheet(f"color: {TEXT_MUTED}; background: transparent;")
        root.addWidget(self._lbl_subtitle)

        root.addSpacing(32)

        # ---- Progress bar --------------------------------------------
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(7)
        self._progress.setFixedWidth(300)
        self._progress.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {BG_INPUT};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {ACCENT};
                border-radius: 3px;
            }}
        """)

        pb_row = QHBoxLayout()
        pb_row.setContentsMargins(0, 0, 0, 0)
        pb_row.addStretch()
        pb_row.addWidget(self._progress)
        pb_row.addStretch()
        root.addLayout(pb_row)

        root.addSpacing(10)

        # ---- Status text ---------------------------------------------
        self._lbl_status = QLabel("Starting…")
        font_status = QFont()
        font_status.setPointSize(9)
        self._lbl_status.setFont(font_status)
        self._lbl_status.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._lbl_status.setStyleSheet(f"color: {TEXT_MUTED}; background: transparent;")
        root.addWidget(self._lbl_status)

        root.addStretch()

        # ---- Version (bottom-right) ----------------------------------
        self._lbl_version = QLabel(f"v{__version__}")
        font_ver = QFont()
        font_ver.setPointSize(8)
        self._lbl_version.setFont(font_ver)
        self._lbl_version.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        self._lbl_version.setStyleSheet(f"color: {TEXT_MUTED}; background: transparent;")
        root.addWidget(self._lbl_version)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_progress(self, value: int) -> None:
        """Set the progress bar value (0–100)."""
        self._progress.setValue(max(0, min(100, value)))

    def set_status(self, text: str) -> None:
        """Update the status label text."""
        self._lbl_status.setText(text)

    def fade_out(self, callback=None) -> None:
        """Fade the splash out over 300 ms, then call *callback*.

        If PySide6 property animation is available, a smooth opacity fade is
        performed.  Otherwise the window is closed immediately and *callback*
        is invoked directly.
        """
        self.setWindowOpacity(1.0)
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(300)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InQuad)
        if callback is not None:
            anim.finished.connect(callback)
        anim.finished.connect(self.close)
        anim.start()
        # Keep a reference so the GC doesn't collect it mid-flight
        self._fade_anim = anim

    # ------------------------------------------------------------------
    # Paint event — dark background + subtle border
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fill background
        painter.fillRect(self.rect(), QColor(BG_BASE))

        # Subtle 1-px border
        pen = QPen(QColor(_BORDER_COLOR))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        painter.end()
