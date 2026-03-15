"""Generate assets/icon.ico — the Blu Optical Simulation application icon.

Design: stylized optical simulation motif — a bright LED point source at
centre emitting converging/diverging light rays, with a subtle arc
representing an optical lens element.  Teal (#00bcd4) primary graphic on
a transparent background.

Run this script standalone to (re-)generate the icon:

    python assets/icon.py

Requirements: PySide6 (already a project dependency).
Optional:     Pillow — enables true multi-size .ico files.
              Falls back to single-size (256×256) .ico if Pillow is absent.
"""

from __future__ import annotations

import io
import os
import sys

# ---------------------------------------------------------------------------
# Allow running from repo root or from inside assets/
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ---------------------------------------------------------------------------
# Qt bootstrap — QApplication is required before any QPainter / QImage usage
# ---------------------------------------------------------------------------
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import (
    QImage, QPainter, QPen, QColor, QBrush,
    QRadialGradient, QLinearGradient, QFont,
)
from PySide6.QtCore import Qt, QPointF, QRectF

_app = QApplication.instance() or QApplication(sys.argv)

# ---------------------------------------------------------------------------
# Target sizes for the ICO file
# ---------------------------------------------------------------------------
ICO_SIZES = [16, 32, 48, 64, 128, 256]

# ---------------------------------------------------------------------------
# Brand colours
# ---------------------------------------------------------------------------
TEAL         = QColor("#00bcd4")
TEAL_LIGHT   = QColor("#80deea")
TEAL_DARK    = QColor("#006064")
WHITE_GLOW   = QColor(255, 255, 255, 200)
TRANSPARENT  = QColor(0, 0, 0, 0)


def _draw_icon(size: int) -> QImage:
    """Paint the icon into a QImage of *size* × *size* pixels (ARGB32)."""
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(TRANSPARENT)

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    cx = size / 2.0
    cy = size / 2.0
    r  = size / 2.0          # half-extent of the canvas
    s  = size / 256.0        # uniform scale factor (designed at 256 px)

    # ------------------------------------------------------------------
    # 1. Subtle circular background glow (very dark teal) for visibility
    # ------------------------------------------------------------------
    if size >= 48:
        bg_grad = QRadialGradient(cx, cy, r * 0.88)
        bg_grad.setColorAt(0.0, QColor(0, 60, 70, 180))
        bg_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(bg_grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), r * 0.88, r * 0.88)

    # ------------------------------------------------------------------
    # 2. Light rays — 5 rays fanning out from centre (30° spacing, centred
    #    on top direction), with tapering alpha and width
    # ------------------------------------------------------------------
    import math

    RAY_COUNT   = 5
    RAY_SPREAD  = 110.0           # total angular spread in degrees
    BASE_ANGLE  = -90.0           # centre ray points straight up
    RAY_LEN_FAC = 0.82            # fraction of radius

    for i in range(RAY_COUNT):
        # Angle for this ray
        if RAY_COUNT == 1:
            angle_deg = BASE_ANGLE
        else:
            angle_deg = BASE_ANGLE - RAY_SPREAD / 2 + i * RAY_SPREAD / (RAY_COUNT - 1)

        angle_rad = math.radians(angle_deg)
        dx = math.cos(angle_rad)
        dy = math.sin(angle_rad)

        # Centre rays are brighter / wider; edge rays fade
        t = abs(i - (RAY_COUNT - 1) / 2) / ((RAY_COUNT - 1) / 2)  # 0 = centre, 1 = edge
        alpha = int(255 * (0.9 - 0.5 * t))
        width = max(1.0, (3.5 - 2.5 * t) * s)

        ray_len = r * RAY_LEN_FAC

        # Draw ray as a gradient line using a LinearGradient pen workaround:
        # QPen can't do gradient, so we draw a series of segments with
        # decreasing alpha instead (simple approximation).
        SEGS = max(4, size // 16)
        for seg in range(SEGS):
            frac0 = seg / SEGS
            frac1 = (seg + 1) / SEGS
            seg_alpha = int(alpha * (1.0 - frac0 * 0.85))   # fades toward tip
            seg_color = QColor(TEAL)
            seg_color.setAlpha(seg_alpha)
            pen = QPen(seg_color, width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            x0 = cx + dx * ray_len * frac0
            y0 = cy + dy * ray_len * frac0
            x1 = cx + dx * ray_len * frac1
            y1 = cy + dy * ray_len * frac1
            p.drawLine(QPointF(x0, y0), QPointF(x1, y1))

    # ------------------------------------------------------------------
    # 3. Optical lens arc — a subtle arc across the lower portion
    #    suggesting a plano-convex lens element
    # ------------------------------------------------------------------
    if size >= 24:
        arc_pen = QPen(TEAL, max(1.0, 2.0 * s))
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        arc_color = QColor(TEAL)
        arc_color.setAlpha(180)
        arc_pen.setColor(arc_color)
        p.setPen(arc_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        # Arc centred slightly below centre, spanning ~140°
        arc_r = r * 0.58
        arc_cx = cx
        arc_cy = cy + r * 0.10
        arc_rect = QRectF(arc_cx - arc_r, arc_cy - arc_r,
                          arc_r * 2, arc_r * 2)
        # Qt angles: 0° = 3 o'clock, CCW positive
        # We want an arc from bottom-left to bottom-right (upper half of ellipse)
        start_angle = 30 * 16   # 30° in Qt 1/16-degree units
        span_angle  = 120 * 16  # span 120°
        p.drawArc(arc_rect, start_angle, span_angle)

    # ------------------------------------------------------------------
    # 4. Central LED source — bright white-teal glow with solid core
    # ------------------------------------------------------------------
    core_r = max(2.5, 14.0 * s)

    # Outer glow
    glow_grad = QRadialGradient(cx, cy, core_r * 2.8)
    glow_grad.setColorAt(0.0, QColor(255, 255, 255, 220))
    glow_grad.setColorAt(0.3, QColor(0, 188, 212, 160))
    glow_grad.setColorAt(1.0, QColor(0, 188, 212, 0))
    p.setBrush(QBrush(glow_grad))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(cx, cy), core_r * 2.8, core_r * 2.8)

    # Solid bright core
    core_grad = QRadialGradient(cx - core_r * 0.25, cy - core_r * 0.25, core_r)
    core_grad.setColorAt(0.0, QColor(255, 255, 255, 255))
    core_grad.setColorAt(0.5, QColor(128, 222, 234, 255))
    core_grad.setColorAt(1.0, QColor(0, 188, 212, 255))
    p.setBrush(QBrush(core_grad))
    p.drawEllipse(QPointF(cx, cy), core_r, core_r)

    p.end()
    return img


def _qimage_to_png_bytes(img: QImage) -> bytes:
    """Encode a QImage to PNG bytes using Qt's built-in encoder."""
    buf = io.BytesIO()
    # Qt can write to a QByteArray; use a temporary file approach via io
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtCore import QByteArray
    ba = QByteArray()
    qbuf = QBuffer(ba)
    qbuf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(qbuf, "PNG")
    qbuf.close()
    return bytes(ba.data())


def generate_ico(output_path: str) -> None:
    """Generate a multi-size .ico file at *output_path*."""
    images: dict[int, QImage] = {s: _draw_icon(s) for s in ICO_SIZES}

    # Try Pillow for a proper multi-size ICO
    try:
        from PIL import Image as PilImage  # type: ignore[import]

        # Build Pillow RGBA images for each target size
        pil_by_size: dict[int, "PilImage.Image"] = {}
        for size in ICO_SIZES:
            png_bytes = _qimage_to_png_bytes(images[size])
            pil_img = PilImage.open(io.BytesIO(png_bytes)).convert("RGBA")
            # Ensure the Pillow image is exactly the right dimensions
            if pil_img.size != (size, size):
                pil_img = pil_img.resize((size, size), PilImage.Resampling.LANCZOS)
            pil_by_size[size] = pil_img

        # Pillow's ICO writer: use the largest image as the anchor and pass
        # append_images in *descending* size order so all frames are written.
        sorted_sizes = sorted(ICO_SIZES, reverse=True)
        anchor = pil_by_size[sorted_sizes[0]]
        rest   = [pil_by_size[s] for s in sorted_sizes[1:]]
        anchor.save(
            output_path,
            format="ICO",
            append_images=rest,
        )
        print(f"[icon.py] Wrote multi-size ICO ({', '.join(str(s) for s in ICO_SIZES)} px) -> {output_path}")

    except ImportError:
        # Pillow not available — fall back to saving the largest size via Qt
        largest = images[max(ICO_SIZES)]
        ok = largest.save(output_path)
        if not ok:
            # Qt ICO writer may not work on non-Windows; write as PNG and rename
            png_path = output_path.replace(".ico", "_fallback.png")
            largest.save(png_path)
            print(
                f"[icon.py] WARNING: Qt could not write .ico directly.\n"
                f"          Saved PNG fallback to {png_path}\n"
                f"          Install Pillow for proper ICO output: pip install Pillow"
            )
            return
        print(f"[icon.py] Wrote single-size ICO (256 px, Pillow not available) -> {output_path}")


if __name__ == "__main__":
    out = os.path.join(_SCRIPT_DIR, "icon.ico")
    generate_ico(out)
    size = os.path.getsize(out)
    print(f"[icon.py] icon.ico size: {size:,} bytes")
