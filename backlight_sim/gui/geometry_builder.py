"""Geometry builder dialog — generates cavity + LED grid from high-level params."""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QDoubleSpinBox, QSpinBox, QComboBox,
    QLabel, QPushButton, QDialogButtonBox, QCheckBox,
    QMessageBox,
)
from PySide6.QtCore import Qt

from backlight_sim.core.materials import Material
from backlight_sim.core.detectors import DetectorSurface
from backlight_sim.core.project_model import Project
from backlight_sim.io.geometry_builder import build_cavity, build_led_grid


def _dspin(val=0.0, lo=0.0, hi=9999.0, decimals=1, step=1.0):
    w = QDoubleSpinBox()
    w.setRange(lo, hi)
    w.setDecimals(decimals)
    w.setValue(val)
    w.setSingleStep(step)
    return w


def _ispin(val=1, lo=1, hi=9999):
    w = QSpinBox()
    w.setRange(lo, hi)
    w.setValue(val)
    return w


class GeometryBuilderDialog(QDialog):
    """Dialog to build a direct-lit backlight cavity with LED grid."""

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Geometry Builder")
        self.setMinimumWidth(420)
        self._project = project

        root = QVBoxLayout(self)

        # ---- Cavity group ----
        cav = QGroupBox("Cavity Dimensions")
        cf = QFormLayout(cav)
        self._cav_w   = _dspin(120.0, 1.0, 5000.0, 1, 10.0)
        self._cav_h   = _dspin(60.0,  1.0, 5000.0, 1, 10.0)
        self._cav_d   = _dspin(10.0,  0.5, 1000.0, 1, 1.0)
        self._wall_a  = _dspin(0.0,   -60.0, 60.0, 1, 1.0)
        cf.addRow("Width (W):",        self._cav_w)
        cf.addRow("Height (H):",       self._cav_h)
        cf.addRow("Depth (D):",        self._cav_d)
        cf.addRow("Wall Angle (°):",   self._wall_a)
        root.addWidget(cav)

        # ---- Material group ----
        mat = QGroupBox("Surface Materials")
        mf = QFormLayout(mat)
        self._floor_ref = _dspin(0.92, 0.0, 1.0, 3, 0.01)
        self._wall_ref  = _dspin(0.92, 0.0, 1.0, 3, 0.01)
        self._wall_diff = QComboBox()
        self._wall_diff.addItems(["Diffuse (Lambertian)", "Specular"])
        mf.addRow("Floor Reflectance:", self._floor_ref)
        mf.addRow("Wall Reflectance:",  self._wall_ref)
        mf.addRow("Wall Type:",         self._wall_diff)
        root.addWidget(mat)

        # ---- Detector group ----
        det = QGroupBox("Output Detector")
        df = QFormLayout(det)
        self._add_det  = QCheckBox("Add output detector")
        self._add_det.setChecked(True)
        self._det_rx   = _ispin(120, 10, 1000)
        self._det_ry   = _ispin(60,  10, 1000)
        df.addRow("", self._add_det)
        df.addRow("Resolution X:", self._det_rx)
        df.addRow("Resolution Y:", self._det_ry)
        root.addWidget(det)

        # ---- LED Grid group ----
        led = QGroupBox("LED Grid")
        lf = QFormLayout(led)
        self._pitch_x  = _dspin(20.0, 0.1, 1000.0, 1, 1.0)
        self._pitch_y  = _dspin(20.0, 0.1, 1000.0, 1, 1.0)
        self._edge_x   = _dspin(10.0, 0.0, 500.0,  1, 1.0)
        self._edge_y   = _dspin(10.0, 0.0, 500.0,  1, 1.0)
        self._led_flux = _dspin(100.0, 0.0, 1e6, 1, 10.0)
        self._led_dist = QComboBox()
        self._led_dist.addItems(["lambertian", "isotropic"])
        self._led_z    = _dspin(0.5, 0.0, 100.0, 2, 0.1)
        lf.addRow("Pitch X:",           self._pitch_x)
        lf.addRow("Pitch Y:",           self._pitch_y)
        lf.addRow("Edge Offset X:",     self._edge_x)
        lf.addRow("Edge Offset Y:",     self._edge_y)
        lf.addRow("LED Flux (per LED):", self._led_flux)
        lf.addRow("Distribution:",      self._led_dist)
        lf.addRow("Z Offset:",          self._led_z)

        self._count_lbl = QLabel("LED count: ?")
        lf.addRow("", self._count_lbl)
        self._btn_preview = QPushButton("Preview LED Count")
        self._btn_preview.clicked.connect(self._preview_count)
        lf.addRow("", self._btn_preview)
        root.addWidget(led)

        # ---- Buttons ----
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self._on_accept)
        bbox.rejected.connect(self.reject)
        root.addWidget(bbox)

        self._preview_count()

    def _preview_count(self):
        from backlight_sim.io.geometry_builder import _grid_positions
        xs = _grid_positions(-self._cav_w.value()/2, self._cav_w.value()/2,
                             self._pitch_x.value(), self._edge_x.value())
        ys = _grid_positions(-self._cav_h.value()/2, self._cav_h.value()/2,
                             self._pitch_y.value(), self._edge_y.value())
        self._count_lbl.setText(f"LED count: {len(xs) * len(ys)}")

    def _on_accept(self):
        W = self._cav_w.value()
        H = self._cav_h.value()
        D = self._cav_d.value()
        θ = self._wall_a.value()

        # Ensure materials exist
        floor_mat_name = "cavity_floor"
        wall_mat_name  = "cavity_wall"
        self._project.materials[floor_mat_name] = Material(
            name=floor_mat_name,
            surface_type="reflector",
            reflectance=self._floor_ref.value(),
            absorption=1.0 - self._floor_ref.value(),
            is_diffuse=True,
        )
        is_specular = self._wall_diff.currentIndex() == 1
        self._project.materials[wall_mat_name] = Material(
            name=wall_mat_name,
            surface_type="reflector",
            reflectance=self._wall_ref.value(),
            absorption=1.0 - self._wall_ref.value(),
            is_diffuse=not is_specular,
        )

        # Build cavity surfaces
        build_cavity(self._project, W, H, D, θ,
                     floor_material=floor_mat_name,
                     wall_material=wall_mat_name,
                     replace_existing=True)

        # Add output detector
        if self._add_det.isChecked():
            # Remove existing detectors first
            self._project.detectors.clear()
            top_w = W + 2 * D * float(np.tan(np.radians(θ))) if θ != 0 else W
            top_h = H + 2 * D * float(np.tan(np.radians(θ))) if θ != 0 else H
            self._project.detectors.append(
                DetectorSurface.axis_aligned(
                    "Output Plane", [0.0, 0.0, D],
                    (top_w, top_h), 2, 1.0,
                    (self._det_rx.value(), self._det_ry.value()),
                )
            )

        # Build LED grid
        n = build_led_grid(
            self._project, W, H,
            pitch_x=self._pitch_x.value(),
            pitch_y=self._pitch_y.value(),
            edge_offset_x=self._edge_x.value(),
            edge_offset_y=self._edge_y.value(),
            led_flux=self._led_flux.value(),
            distribution=self._led_dist.currentText(),
            z_offset=self._led_z.value(),
            replace_existing=True,
        )

        QMessageBox.information(
            self, "Geometry Built",
            f"Created {len(self._project.surfaces)} surfaces, "
            f"{n} LEDs, "
            f"{len(self._project.detectors)} detector(s)."
        )
        self.accept()
