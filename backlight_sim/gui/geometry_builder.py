"""Geometry builder dialog - generates cavity + LED grid from high-level params."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from backlight_sim.core.detectors import DetectorSurface
from backlight_sim.core.materials import Material
from backlight_sim.core.project_model import Project

from backlight_sim.io.geometry_builder import build_cavity, build_led_grid, build_optical_stack, build_lgp_scene
from backlight_sim.gui.theme import TEXT_MUTED, KPI_GREEN


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
    """Dialog to build direct-lit backlight cavity or edge-lit LGP scene."""

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Geometry Builder")
        self.setMinimumWidth(480)
        self._project = project
        self._built_lgp = False

        # Debounce timer for LED count preview (coalesces rapid spinbox edits)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(80)
        self._preview_timer.timeout.connect(self._preview_count)

        root = QVBoxLayout(self)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._create_direct_lit_tab(), "Direct-Lit Cavity")
        self._tabs.addTab(self._create_lgp_tab(), "LGP")
        root.addWidget(self._tabs)

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self._on_accept)
        bbox.rejected.connect(self.reject)
        root.addWidget(bbox)

        self._preview_count()

    # ------------------------------------------------------------------
    # Direct-Lit tab
    # ------------------------------------------------------------------

    def _create_direct_lit_tab(self) -> QWidget:
        container = QWidget()
        root = QVBoxLayout(container)

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

        stack = QGroupBox("Optical Stack")
        sf = QFormLayout(stack)
        self._diff_dist = _dspin(0.0, 0.0, 500.0, 1, 0.5)
        self._diff_dist.setToolTip("Z height of diffuser plane (0 = no diffuser)")
        self._diff_trans = _dspin(0.7, 0.0, 1.0, 3, 0.01)
        self._film1_z = _dspin(0.0, 0.0, 500.0, 1, 0.5)
        self._film1_z.setToolTip("Z height of film placeholder 1 (0 = skip)")
        self._film2_z = _dspin(0.0, 0.0, 500.0, 1, 0.5)
        self._film2_z.setToolTip("Z height of film placeholder 2 (0 = skip)")
        sf.addRow("Diffuser distance (Z):", self._diff_dist)
        sf.addRow("Diffuser transmittance:", self._diff_trans)
        sf.addRow("Film 1 distance (Z):", self._film1_z)
        sf.addRow("Film 2 distance (Z):", self._film2_z)
        root.addWidget(stack)

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
        self._use_count.toggled.connect(self._schedule_preview)
        lf.addRow("", self._use_count)

        self._count_x = _ispin(4, 1, 999)
        self._count_y = _ispin(2, 1, 999)
        self._count_x.valueChanged.connect(self._schedule_preview)
        self._count_y.valueChanged.connect(self._schedule_preview)
        lf.addRow("Count X:", self._count_x)
        lf.addRow("Count Y:", self._count_y)

        self._pitch_x = _dspin(20.0, 0.1, 1000.0, 1, 1.0)
        self._pitch_y = _dspin(20.0, 0.1, 1000.0, 1, 1.0)
        self._pitch_x.valueChanged.connect(self._schedule_preview)
        self._pitch_y.valueChanged.connect(self._schedule_preview)
        lf.addRow("Pitch X:", self._pitch_x)
        lf.addRow("Pitch Y:", self._pitch_y)
        self._pitch_lbl = QLabel("(or set Count X/Y and check 'Specify number of LEDs' to auto-calculate)")
        self._pitch_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 9px;")
        lf.addRow("", self._pitch_lbl)

        self._edge_x = _dspin(10.0, 0.0, 500.0, 1, 1.0)
        self._edge_y = _dspin(10.0, 0.0, 500.0, 1, 1.0)
        self._edge_x.valueChanged.connect(self._schedule_preview)
        self._edge_y.valueChanged.connect(self._schedule_preview)
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

        root.addStretch()
        return container

    # ------------------------------------------------------------------
    # LGP tab
    # ------------------------------------------------------------------

    def _create_lgp_tab(self) -> QWidget:
        container = QWidget()
        root = QVBoxLayout(container)

        dim = QGroupBox("LGP Dimensions")
        df = QFormLayout(dim)
        self._lgp_w = _dspin(80.0, 5.0, 500.0, 1, 5.0)
        self._lgp_h = _dspin(50.0, 5.0, 500.0, 1, 5.0)
        self._lgp_t = _dspin(3.0, 0.5, 50.0, 2, 0.5)
        df.addRow("LGP Width (mm):", self._lgp_w)
        df.addRow("LGP Height (mm):", self._lgp_h)
        df.addRow("LGP Thickness (mm):", self._lgp_t)
        root.addWidget(dim)

        mat = QGroupBox("Material")
        mf = QFormLayout(mat)
        self._lgp_mat_combo = QComboBox()
        self._lgp_mat_combo.addItems(["PMMA (n=1.49)", "Custom"])
        self._lgp_mat_combo.currentIndexChanged.connect(self._on_lgp_mat_changed)
        self._lgp_ri = _dspin(1.49, 1.0, 3.0, 3, 0.01)
        mf.addRow("Material:", self._lgp_mat_combo)
        mf.addRow("Refractive Index:", self._lgp_ri)
        root.addWidget(mat)

        edges = QGroupBox("Coupling Edges")
        ef = QFormLayout(edges)
        self._lgp_edge_checks: dict[str, QCheckBox] = {}
        edges_row = QHBoxLayout()
        for edge_id in ("left", "right", "front", "back"):
            cb = QCheckBox(edge_id.capitalize())
            self._lgp_edge_checks[edge_id] = cb
            edges_row.addWidget(cb)
        self._lgp_edge_checks["left"].setChecked(True)  # default: left edge
        ef.addRow("Coupling edges:", edges_row)
        root.addWidget(edges)

        leds = QGroupBox("LED Parameters")
        lf = QFormLayout(leds)
        self._lgp_led_count = _ispin(6, 1, 100)
        self._lgp_led_flux = _dspin(100.0, 0.0, 1e6, 1, 10.0)
        self._lgp_led_dist = QComboBox()
        self._lgp_led_dist.addItems(["lambertian", "isotropic"])
        extra = sorted(self._project.angular_distributions.keys())
        for name in extra:
            if name not in ("lambertian", "isotropic"):
                self._lgp_led_dist.addItem(name)
        lf.addRow("LEDs per edge:", self._lgp_led_count)
        lf.addRow("LED Flux:", self._lgp_led_flux)
        lf.addRow("LED Distribution:", self._lgp_led_dist)
        root.addWidget(leds)

        spacing = QGroupBox("Detector & Reflector Spacing")
        sf = QFormLayout(spacing)
        self._lgp_det_gap = _dspin(2.0, 0.0, 50.0, 1, 0.5)
        self._lgp_ref_gap = _dspin(1.0, 0.0, 50.0, 1, 0.5)
        self._lgp_det_gap.setToolTip("Gap between LGP top face and detector plane (mm)")
        self._lgp_ref_gap.setToolTip("Gap between LGP bottom face and reflector surface (mm)")
        sf.addRow("Detector gap (mm):", self._lgp_det_gap)
        sf.addRow("Reflector gap (mm):", self._lgp_ref_gap)
        root.addWidget(spacing)

        self._lgp_status_lbl = QLabel("")
        self._lgp_status_lbl.setStyleSheet(f"color: {KPI_GREEN}; font-size: 10px;")
        root.addWidget(self._lgp_status_lbl)

        self._lgp_build_btn = QPushButton("Build LGP Scene")
        self._lgp_build_btn.clicked.connect(self._on_build_lgp)
        root.addWidget(self._lgp_build_btn)

        root.addStretch()
        return container

    def _on_lgp_mat_changed(self, idx: int):
        if idx == 0:  # PMMA preset
            self._lgp_ri.setValue(1.49)

    def _on_build_lgp(self):
        coupling_edges = [eid for eid, cb in self._lgp_edge_checks.items() if cb.isChecked()]
        if not coupling_edges:
            QMessageBox.warning(self, "No Coupling Edge", "Select at least one coupling edge.")
            return

        try:
            build_lgp_scene(
                self._project,
                width=self._lgp_w.value(),
                height=self._lgp_h.value(),
                thickness=self._lgp_t.value(),
                coupling_edges=coupling_edges,
                led_count=self._lgp_led_count.value(),
                led_flux=self._lgp_led_flux.value(),
                led_distribution=self._lgp_led_dist.currentText(),
                detector_gap=self._lgp_det_gap.value(),
                reflector_gap=self._lgp_ref_gap.value(),
                refractive_index=self._lgp_ri.value(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "LGP Build Error", str(exc))
            return

        n_leds = len(self._project.sources)
        n_edges = len(coupling_edges)
        self._lgp_status_lbl.setText(
            f"LGP scene created: {n_leds} LEDs on {n_edges} edge(s)"
        )
        self._built_lgp = True

    # ------------------------------------------------------------------
    # Direct-lit helpers
    # ------------------------------------------------------------------

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

    def _schedule_preview(self, _=None):
        """Debounce rapid spinbox edits — delay _preview_count by 80 ms."""
        self._preview_timer.start()

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
        # If on LGP tab and LGP was built, just accept
        if self._tabs.currentIndex() == 1:
            if self._built_lgp:
                self.accept()
            else:
                QMessageBox.information(self, "LGP", "Click 'Build LGP Scene' first, or switch to the Direct-Lit tab.")
            return

        # Direct-Lit tab
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
            record_recipe=True,    # Phase 5: write recipe back to project.cavity_recipe
        )

        # Optical stack (diffuser + film placeholders)
        diff_z = self._diff_dist.value()
        film_zs = [z for z in (self._film1_z.value(), self._film2_z.value()) if z > 0]
        if diff_z > 0 or film_zs:
            diff_mat_name = "diffuser_stack"
            self._project.materials[diff_mat_name] = Material(
                name=diff_mat_name,
                surface_type="diffuser",
                transmittance=self._diff_trans.value(),
                reflectance=1.0 - self._diff_trans.value(),
                is_diffuse=True,
            )
            build_optical_stack(
                self._project, w, h, d,
                diffuser_distance=diff_z,
                film_distances=film_zs if film_zs else None,
                diffuser_material=diff_mat_name,
                film_material=wall_mat_name,
                wall_angle_x_deg=wall_x,
                wall_angle_y_deg=wall_y,
            )

        if self._add_det.isChecked():
            self._project.detectors.clear()
            # Clamp wall angles to < 89° to avoid near-infinite detector sizes
            safe_wx = min(wall_x, 89.0)
            safe_wy = min(wall_y, 89.0)
            top_w = w + 2 * d * float(np.tan(np.radians(safe_wx)))
            top_h = h + 2 * d * float(np.tan(np.radians(safe_wy)))
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
