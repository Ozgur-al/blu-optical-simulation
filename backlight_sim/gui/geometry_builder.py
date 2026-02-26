"""Geometry builder dialog - generates cavity + LED grid from high-level params."""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from backlight_sim.core.detectors import DetectorSurface
from backlight_sim.core.materials import Material
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
        self.setMinimumWidth(460)
        self._project = project

        root = QVBoxLayout(self)

        cav = QGroupBox("Cavity Dimensions")
        cf = QFormLayout(cav)
        self._cav_w = _dspin(120.0, 1.0, 5000.0, 1, 10.0)
        self._cav_h = _dspin(60.0, 1.0, 5000.0, 1, 10.0)
        self._cav_d = _dspin(10.0, 0.5, 1000.0, 1, 1.0)
        self._wall_angle_x = _dspin(0.0, -60.0, 60.0, 1, 1.0)
        self._wall_angle_y = _dspin(0.0, -60.0, 60.0, 1, 1.0)
        cf.addRow("Width (W):", self._cav_w)
        cf.addRow("Height (H):", self._cav_h)
        cf.addRow("Depth (D):", self._cav_d)
        cf.addRow("Wall Angle Left/Right (deg):", self._wall_angle_x)
        cf.addRow("Wall Angle Front/Back (deg):", self._wall_angle_y)
        root.addWidget(cav)

        mat = QGroupBox("Surface Materials")
        mf = QFormLayout(mat)
        self._floor_ref = _dspin(0.92, 0.0, 1.0, 3, 0.01)
        self._wall_ref = _dspin(0.92, 0.0, 1.0, 3, 0.01)
        self._wall_diff = QComboBox()
        self._wall_diff.addItems(["Diffuse (Lambertian)", "Specular"])
        mf.addRow("Floor Reflectance:", self._floor_ref)
        mf.addRow("Wall Reflectance:", self._wall_ref)
        mf.addRow("Wall Type:", self._wall_diff)
        root.addWidget(mat)

        det = QGroupBox("Output Detector")
        df = QFormLayout(det)
        self._add_det = QCheckBox("Add output detector")
        self._add_det.setChecked(True)
        self._det_rx = _ispin(120, 10, 1000)
        self._det_ry = _ispin(60, 10, 1000)
        df.addRow("", self._add_det)
        df.addRow("Resolution X:", self._det_rx)
        df.addRow("Resolution Y:", self._det_ry)
        root.addWidget(det)

        led = QGroupBox("LED Grid")
        lf = QFormLayout(led)
        self._use_count = QCheckBox("Specify number of LEDs (auto pitch)")
        self._use_count.setChecked(False)
        self._use_count.toggled.connect(self._preview_count)
        lf.addRow("", self._use_count)

        self._count_x = _ispin(4, 1, 999)
        self._count_y = _ispin(2, 1, 999)
        self._count_x.valueChanged.connect(self._preview_count)
        self._count_y.valueChanged.connect(self._preview_count)
        lf.addRow("Count X:", self._count_x)
        lf.addRow("Count Y:", self._count_y)

        self._pitch_x = _dspin(20.0, 0.1, 1000.0, 1, 1.0)
        self._pitch_y = _dspin(20.0, 0.1, 1000.0, 1, 1.0)
        self._pitch_x.valueChanged.connect(self._preview_count)
        self._pitch_y.valueChanged.connect(self._preview_count)
        lf.addRow("Pitch X:", self._pitch_x)
        lf.addRow("Pitch Y:", self._pitch_y)
        self._pitch_lbl = QLabel("(or set Count X/Y and check 'Specify number of LEDs' to auto-calculate)")
        self._pitch_lbl.setStyleSheet("color: gray; font-size: 9px;")
        lf.addRow("", self._pitch_lbl)

        self._edge_x = _dspin(10.0, 0.0, 500.0, 1, 1.0)
        self._edge_y = _dspin(10.0, 0.0, 500.0, 1, 1.0)
        self._edge_x.valueChanged.connect(self._preview_count)
        self._edge_y.valueChanged.connect(self._preview_count)
        lf.addRow("Edge Offset X:", self._edge_x)
        lf.addRow("Edge Offset Y:", self._edge_y)
        self._led_flux = _dspin(100.0, 0.0, 1e6, 1, 10.0)
        lf.addRow("LED Flux (per LED):", self._led_flux)
        self._led_dist = QComboBox()
        self._refresh_distributions()
        self._led_z = _dspin(0.5, 0.0, 100.0, 2, 0.1)
        lf.addRow("Distribution:", self._led_dist)
        lf.addRow("Z Offset:", self._led_z)

        self._count_lbl = QLabel("LED count: ?")
        lf.addRow("", self._count_lbl)
        self._btn_preview = QPushButton("Preview LED Count")
        self._btn_preview.clicked.connect(self._preview_count)
        lf.addRow("", self._btn_preview)
        root.addWidget(led)

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self._on_accept)
        bbox.rejected.connect(self.reject)
        root.addWidget(bbox)

        self._preview_count()

    def _refresh_distributions(self):
        current = self._led_dist.currentText()
        names = ["lambertian", "isotropic"] + sorted(self._project.angular_distributions.keys())
        unique = []
        seen = set()
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            unique.append(name)
        self._led_dist.clear()
        self._led_dist.addItems(unique)
        if current and current in unique:
            self._led_dist.setCurrentText(current)

    def _preview_count(self):
        from backlight_sim.io.geometry_builder import _grid_positions

        w = self._cav_w.value()
        h = self._cav_h.value()
        ex = self._edge_x.value()
        ey = self._edge_y.value()
        if self._use_count.isChecked():
            cx = max(1, self._count_x.value())
            cy = max(1, self._count_y.value())
            span_x = w - 2.0 * ex
            span_y = h - 2.0 * ey
            pitch_x = span_x / max(cx - 1, 1) if span_x > 0 else 0.0
            pitch_y = span_y / max(cy - 1, 1) if span_y > 0 else 0.0
        else:
            pitch_x = self._pitch_x.value()
            pitch_y = self._pitch_y.value()
        xs = _grid_positions(-w / 2, w / 2, pitch_x, ex)
        ys = _grid_positions(-h / 2, h / 2, pitch_y, ey)
        self._count_lbl.setText(f"LED count: {len(xs) * len(ys)}")

    def _on_accept(self):
        w = self._cav_w.value()
        h = self._cav_h.value()
        d = self._cav_d.value()
        wall_x = self._wall_angle_x.value()
        wall_y = self._wall_angle_y.value()

        floor_mat_name = "cavity_floor"
        wall_mat_name = "cavity_wall"
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

        build_cavity(
            self._project,
            w,
            h,
            d,
            wall_angle_x_deg=wall_x,
            wall_angle_y_deg=wall_y,
            floor_material=floor_mat_name,
            wall_material=wall_mat_name,
            replace_existing=True,
        )

        if self._add_det.isChecked():
            self._project.detectors.clear()
            top_w = w + 2 * d * float(np.tan(np.radians(wall_x)))
            top_h = h + 2 * d * float(np.tan(np.radians(wall_y)))
            self._project.detectors.append(
                DetectorSurface.axis_aligned(
                    "Output Plane",
                    [0.0, 0.0, d],
                    (top_w, top_h),
                    2,
                    1.0,
                    (self._det_rx.value(), self._det_ry.value()),
                )
            )

        use_count = self._use_count.isChecked()
        count_x = self._count_x.value() if use_count else None
        count_y = self._count_y.value() if use_count else None
        n = build_led_grid(
            self._project,
            w,
            h,
            pitch_x=self._pitch_x.value(),
            pitch_y=self._pitch_y.value(),
            edge_offset_x=self._edge_x.value(),
            edge_offset_y=self._edge_y.value(),
            led_flux=self._led_flux.value(),
            distribution=self._led_dist.currentText(),
            z_offset=self._led_z.value(),
            replace_existing=True,
            count_x=count_x,
            count_y=count_y,
        )

        QMessageBox.information(
            self,
            "Geometry Built",
            f"Created {len(self._project.surfaces)} surfaces, {n} LEDs, {len(self._project.detectors)} detector(s).",
        )
        self.accept()
