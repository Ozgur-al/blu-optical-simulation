"""2D top-view LED layout editor with drag-and-drop positioning."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialogButtonBox,
)

from backlight_sim.core.project_model import Project
from backlight_sim.gui.theme import TEXT_MUTED


class _DraggableLED(pg.TargetItem):
    """A draggable LED marker on the 2D layout."""

    moved = Signal(str, float, float)  # (source_name, new_x, new_y)

    def __init__(self, name: str, x: float, y: float, enabled: bool = True):
        color = (255, 200, 40) if enabled else (120, 120, 120)
        super().__init__(
            pos=(x, y),
            size=8,
            movable=True,
            pen=pg.mkPen(color, width=2),
            brush=pg.mkBrush(*color, 180),
            symbol="o",
        )
        self.led_name = name
        from backlight_sim.gui.theme import TEXT_PRIMARY
        self.setLabel(name, {"color": TEXT_PRIMARY, "size": "8pt"})
        self.sigPositionChanged.connect(self._on_moved)

    def _on_moved(self):
        pos = self.pos()
        self.moved.emit(self.led_name, float(pos[0]), float(pos[1]))


class LEDLayoutEditor(QDialog):
    """2D top-view editor for dragging LED positions on the XY plane."""

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LED Layout Editor (Top View)")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self._project = project
        self._markers: dict[str, _DraggableLED] = {}

        layout = QVBoxLayout(self)

        info = QLabel("Drag LEDs to reposition. Changes apply immediately to the project.")
        info.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(info)

        # 2D plot
        self._plot = pg.PlotWidget()
        self._plot.setAspectLocked(True)
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._plot.setLabel("bottom", "X (mm)")
        self._plot.setLabel("left", "Y (mm)")
        layout.addWidget(self._plot, 1)

        # Status
        self._status = QLabel("")
        self._status.setStyleSheet("font-family: monospace;")
        layout.addWidget(self._status)

        # Buttons
        btn_row = QHBoxLayout()
        snap_btn = QPushButton("Snap to Grid (1mm)")
        snap_btn.clicked.connect(lambda: self._snap_all(1.0))
        btn_row.addWidget(snap_btn)
        snap5_btn = QPushButton("Snap to Grid (5mm)")
        snap5_btn.clicked.connect(lambda: self._snap_all(5.0))
        btn_row.addWidget(snap5_btn)
        reset_btn = QPushButton("Reset to Original")
        reset_btn.clicked.connect(self._reset_positions)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bbox.rejected.connect(self.accept)
        layout.addWidget(bbox)

        # Store original positions for reset
        self._original_positions: dict[str, tuple[float, float]] = {}

        self._draw_scene()

    def _draw_scene(self):
        self._plot.clear()
        self._markers.clear()

        # Draw surfaces as outlines
        for surf in self._project.surfaces:
            cx, cy = float(surf.center[0]), float(surf.center[1])
            hw, hh = surf.size[0] / 2, surf.size[1] / 2
            rect = pg.QtWidgets.QGraphicsRectItem(cx - hw, cy - hh, surf.size[0], surf.size[1])
            rect.setPen(pg.mkPen((100, 130, 180, 120), width=1, style=Qt.PenStyle.DashLine))
            self._plot.addItem(rect)

        # Draw detectors as outlines
        for det in self._project.detectors:
            cx, cy = float(det.center[0]), float(det.center[1])
            hw, hh = det.size[0] / 2, det.size[1] / 2
            rect = pg.QtWidgets.QGraphicsRectItem(cx - hw, cy - hh, det.size[0], det.size[1])
            rect.setPen(pg.mkPen((80, 200, 80, 150), width=2))
            self._plot.addItem(rect)

        # Add draggable LED markers
        for src in self._project.sources:
            x, y = float(src.position[0]), float(src.position[1])
            self._original_positions[src.name] = (x, y)
            marker = _DraggableLED(src.name, x, y, src.enabled)
            marker.moved.connect(self._on_led_moved)
            self._plot.addItem(marker)
            self._markers[src.name] = marker

        self._update_status()

    def _on_led_moved(self, name: str, new_x: float, new_y: float):
        src = next((s for s in self._project.sources if s.name == name), None)
        if src is not None:
            src.position[0] = new_x
            src.position[1] = new_y
        self._update_status()

    def _update_status(self):
        n = len(self._project.sources)
        enabled = sum(1 for s in self._project.sources if s.enabled)
        self._status.setText(f"LEDs: {n} total, {enabled} enabled")

    def _snap_all(self, grid_size: float):
        for src in self._project.sources:
            src.position[0] = round(float(src.position[0]) / grid_size) * grid_size
            src.position[1] = round(float(src.position[1]) / grid_size) * grid_size
        # Redraw markers at snapped positions
        for src in self._project.sources:
            marker = self._markers.get(src.name)
            if marker:
                marker.setPos(float(src.position[0]), float(src.position[1]))

    def _reset_positions(self):
        for src in self._project.sources:
            orig = self._original_positions.get(src.name)
            if orig:
                src.position[0], src.position[1] = orig
                marker = self._markers.get(src.name)
                if marker:
                    marker.setPos(orig[0], orig[1])
