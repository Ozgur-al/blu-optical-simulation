"""Keep top-level windows and dialogs inside the visible screen area.

Laptop screens at 125-150 % scaling expose only ~1500x800 logical pixels, so
hard-coded window sizes routinely overflow. ``install_screen_fit(app)`` adds
an application-wide event filter that, the first time any top-level window is
shown, shrinks it to the available geometry of its screen and moves it fully
on-screen. ``fit_to_screen()`` does the same on demand with a preferred size.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QRect, QSize, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QFrame, QScrollArea, QWidget

# Fraction of the available screen a window may occupy when we resize it.
_MAX_FRACTION = 0.94

_FITTED_PROP = "_screen_fit_done"


def _available_rect(widget: QWidget) -> QRect:
    screen = None
    parent = widget.parentWidget()
    if parent is not None and parent.window().isVisible():
        screen = parent.window().screen()
    if screen is None:
        screen = widget.screen() or QGuiApplication.primaryScreen()
    return screen.availableGeometry()


def _frame_extra(widget: QWidget) -> QSize:
    """Size of the window decorations (title bar + borders)."""
    fg, g = widget.frameGeometry(), widget.geometry()
    extra_w = max(0, fg.width() - g.width())
    extra_h = max(0, fg.height() - g.height())
    if extra_h == 0:  # not yet decorated — assume a typical Windows title bar
        extra_w, extra_h = 16, 39
    return QSize(extra_w, extra_h)


def fit_to_screen(widget: QWidget, preferred: QSize | tuple[int, int] | None = None,
                  center: bool = True) -> None:
    """Resize *widget* to *preferred* (or its current size), clamped to its screen."""
    avail = _available_rect(widget)
    extra = _frame_extra(widget)
    max_w = int(avail.width() * _MAX_FRACTION) - extra.width()
    max_h = int(avail.height() * _MAX_FRACTION) - extra.height()

    if preferred is None:
        want = widget.size()
    elif isinstance(preferred, tuple):
        want = QSize(*preferred)
    else:
        want = QSize(preferred)

    w = max(min(want.width(), max_w), min(widget.minimumWidth(), max_w))
    h = max(min(want.height(), max_h), min(widget.minimumHeight(), max_h))
    # Never let a layout minimum force the window past the screen edge.
    widget.setMinimumSize(min(widget.minimumWidth(), max_w), min(widget.minimumHeight(), max_h))
    widget.resize(w, h)

    if center:
        parent = widget.parentWidget()
        anchor = parent.window().frameGeometry() if (parent and parent.window().isVisible()) else avail
        frame_w, frame_h = w + extra.width(), h + extra.height()
        x = anchor.center().x() - frame_w // 2
        y = anchor.center().y() - frame_h // 2
        _move_inside(widget, QRect(x, y, frame_w, frame_h), avail)
    else:
        _move_inside(widget, widget.frameGeometry(), avail)


def _move_inside(widget: QWidget, frame: QRect, avail: QRect) -> None:
    x = min(max(frame.x(), avail.left()), avail.right() - frame.width() + 1)
    y = min(max(frame.y(), avail.top()), avail.bottom() - frame.height() + 1)
    widget.move(max(x, avail.left()), max(y, avail.top()))


def ensure_on_screen(widget: QWidget) -> None:
    """Shrink/move a shown window only if it overflows its screen."""
    if widget.isMaximized() or widget.isFullScreen():
        return
    avail = _available_rect(widget)
    frame = widget.frameGeometry()
    if avail.contains(frame):
        return
    if frame.width() > avail.width() or frame.height() > avail.height():
        fit_to_screen(widget, widget.size(), center=True)
    else:
        _move_inside(widget, frame, avail)


class _ScreenFitFilter(QObject):
    def eventFilter(self, obj, event):  # noqa: N802 (Qt naming)
        if event.type() == QEvent.Type.Show and isinstance(obj, QWidget) and obj.isWindow():
            flags = obj.windowFlags()
            win_type = flags & Qt.WindowType.WindowType_Mask
            if win_type in (Qt.WindowType.Window, Qt.WindowType.Dialog) \
                    and not obj.property(_FITTED_PROP):
                obj.setProperty(_FITTED_PROP, True)
                ensure_on_screen(obj)
        return False


_filter: _ScreenFitFilter | None = None


def install_screen_fit(app: QApplication) -> None:
    """Install the app-wide screen-fit filter once."""
    global _filter
    if _filter is None:
        _filter = _ScreenFitFilter(app)
        app.installEventFilter(_filter)


def scrollable(widget: QWidget) -> QScrollArea:
    """Wrap *widget* in a frameless, vertically scrolling area."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(widget)
    return area
