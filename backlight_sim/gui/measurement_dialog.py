"""Point-to-point measurement dialog."""

from __future__ import annotations

import numpy as np
from backlight_sim.gui.theme import TEXT_MUTED
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QDoubleSpinBox,
)


def _dspin(val=0.0):
    w = QDoubleSpinBox()
    w.setRange(-99999.0, 99999.0)
    w.setDecimals(3)
    w.setValue(val)
    w.setSingleStep(0.5)
    return w


class MeasurementDialog(QDialog):
    def __init__(self, selected_point_callback, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Measure Distance")
        self._get_selected_point = selected_point_callback

        root = QVBoxLayout(self)
        form = QWidget()
        fg = QGridLayout(form)
        fg.addWidget(QLabel("Point"), 0, 0)
        fg.addWidget(QLabel("X"), 0, 1)
        fg.addWidget(QLabel("Y"), 0, 2)
        fg.addWidget(QLabel("Z"), 0, 3)

        fg.addWidget(QLabel("A"), 1, 0)
        self._ax = _dspin()
        self._ay = _dspin()
        self._az = _dspin()
        fg.addWidget(self._ax, 1, 1)
        fg.addWidget(self._ay, 1, 2)
        fg.addWidget(self._az, 1, 3)
        self._use_a = QPushButton("Use Selected -> A")
        self._use_a.clicked.connect(self._set_a_from_selected)
        fg.addWidget(self._use_a, 1, 4)

        fg.addWidget(QLabel("B"), 2, 0)
        self._bx = _dspin()
        self._by = _dspin()
        self._bz = _dspin()
        fg.addWidget(self._bx, 2, 1)
        fg.addWidget(self._by, 2, 2)
        fg.addWidget(self._bz, 2, 3)
        self._use_b = QPushButton("Use Selected -> B")
        self._use_b.clicked.connect(self._set_b_from_selected)
        fg.addWidget(self._use_b, 2, 4)
        root.addWidget(form)

        res_form = QFormLayout()
        self._dx = QLabel("--")
        self._dy = QLabel("--")
        self._dz = QLabel("--")
        self._dist = QLabel("--")
        for label in (self._dx, self._dy, self._dz, self._dist):
            label.setStyleSheet("font-family: monospace;")
        res_form.addRow("Delta X:", self._dx)
        res_form.addRow("Delta Y:", self._dy)
        res_form.addRow("Delta Z:", self._dz)
        res_form.addRow("Distance:", self._dist)
        root.addLayout(res_form)

        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bbox.rejected.connect(self.reject)
        bbox.accepted.connect(self.accept)
        root.addWidget(bbox)

        for w in (self._ax, self._ay, self._az, self._bx, self._by, self._bz):
            w.valueChanged.connect(self._recompute)

        # Explicit tab order: A coords → use-A button → B coords → use-B button
        self.setTabOrder(self._ax, self._ay)
        self.setTabOrder(self._ay, self._az)
        self.setTabOrder(self._az, self._use_a)
        self.setTabOrder(self._use_a, self._bx)
        self.setTabOrder(self._bx, self._by)
        self.setTabOrder(self._by, self._bz)
        self.setTabOrder(self._bz, self._use_b)

        self._recompute()

    def _selected_point(self):
        p = self._get_selected_point() if self._get_selected_point else None
        if p is None:
            return None
        return np.asarray(p, dtype=float)

    def _set_a_from_selected(self):
        p = self._selected_point()
        if p is None:
            return
        self._ax.setValue(float(p[0]))
        self._ay.setValue(float(p[1]))
        self._az.setValue(float(p[2]))

    def _set_b_from_selected(self):
        p = self._selected_point()
        if p is None:
            return
        self._bx.setValue(float(p[0]))
        self._by.setValue(float(p[1]))
        self._bz.setValue(float(p[2]))

    def _recompute(self):
        a = np.array([self._ax.value(), self._ay.value(), self._az.value()], dtype=float)
        b = np.array([self._bx.value(), self._by.value(), self._bz.value()], dtype=float)
        d = b - a
        dist = float(np.linalg.norm(d))
        self._dx.setText(f"{d[0]:.4f}")
        self._dy.setText(f"{d[1]:.4f}")
        self._dz.setText(f"{d[2]:.4f}")
        self._dist.setText(f"{dist:.4f}")
