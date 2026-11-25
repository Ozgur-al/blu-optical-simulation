"""Geometry builder dialog - generates cavity + LED grid from high-level params."""

from __future__ import annotations

import copy

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer
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

from backlight_sim.io.geometry_builder import (
    _axis_positions, build_cavity, build_led_grid, build_lgp_scene, build_optical_stack,
)
from backlight_sim.gui.theme import TEXT_MUTED, KPI_GREEN, KPI_ORANGE
from backlight_sim.gui.widgets.screen_fit import fit_to_screen, scrollable


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
        # Build into a working copy; the caller applies it only on accept so a
        # cancelled dialog (incl. after "Build LGP Scene") leaves the project untouched.
        self._project = copy.deepcopy(project)
        self._built_lgp = False

        # Debounce timer for LED count preview (coalesces rapid spinbox edits)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(80)
        self._preview_timer.timeout.connect(self._preview_count)

        root = QVBoxLayout(self)

        self._tabs = QTabWidget()
        # Each tab scrolls on its own so the dialog never outgrows the screen.
        self._tabs.addTab(scrollable(self._create_direct_lit_tab()), "Direct-Lit Cavity")
        self._tabs.addTab(scrollable(self._create_lgp_tab()), "LGP")
        root.addWidget(self._tabs)

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self._on_accept)
        bbox.rejected.connect(self.reject)
        root.addWidget(bbox)

        self._preview_count()
        fit_to_screen(self, (900, 700))

    # ------------------------------------------------------------------
    # Direct-Lit tab
    # ------------------------------------------------------------------

    def _create_direct_lit_tab(self) -> QWidget:
        container = QWidget()
        cols = QHBoxLayout(container)
        cols.setSpacing(12)
        left_col = QVBoxLayout()
        right_col = QVBoxLayout()
        cols.addLayout(left_col, 1)
        cols.addLayout(right_col, 1)
        root = left_col

        cav = QGroupBox("LED Plate && Cavity")
        cf = QFormLayout(cav)
        self._size_mode = QComboBox()
        self._size_mode.addItems(["Enter LED plate size", "From active area"])
        self._size_mode.setToolTip(
            "From active area: plate = active area + margin on each side, "
            "and the LED count is entered directly.")
        cf.addRow("Size from:", self._size_mode)
        self._aa_w = _dspin(110.0, 1.0, 5000.0, 1, 10.0)
        self._aa_h = _dspin(50.0, 1.0, 5000.0, 1, 10.0)
        self._margin_x = _dspin(5.0, 0.0, 500.0, 2, 0.5)
        self._margin_y = _dspin(5.0, 0.0, 500.0, 2, 0.5)
        self._margin_x.setToolTip("How much the LED plate extends past the active area, per side (X)")
        self._margin_y.setToolTip("How much the LED plate extends past the active area, per side (Y)")
        cf.addRow("Active area W:", self._aa_w)
        cf.addRow("Active area H:", self._aa_h)
        cf.addRow("Plate margin X (per side):", self._margin_x)
        cf.addRow("Plate margin Y (per side):", self._margin_y)
        self._cav_w = _dspin(120.0, 1.0, 5000.0, 1, 10.0)
        self._cav_h = _dspin(60.0, 1.0, 5000.0, 1, 10.0)
        self._cav_d = _dspin(10.0, 0.5, 1000.0, 1, 1.0)
        self._cav_d.setToolTip("Height of the output detector above the LED plate top (and wall height)")
        self._walls = QCheckBox("Build cavity walls (metal frame)")
        self._walls.setChecked(True)
        self._wall_angle_x = _dspin(0.0, -60.0, 60.0, 1, 1.0)
        self._wall_angle_y = _dspin(0.0, -60.0, 60.0, 1, 1.0)
        cf.addRow("LED plate W:", self._cav_w)
        cf.addRow("LED plate H:", self._cav_h)
        cf.addRow("Depth / output plane Z:", self._cav_d)
        cf.addRow("", self._walls)
        cf.addRow("Wall Angle Left/Right (deg):", self._wall_angle_x)
        cf.addRow("Wall Angle Front/Back (deg):", self._wall_angle_y)
        root.addWidget(cav)

        mat = QGroupBox("Surface Materials")
        mf = QFormLayout(mat)
        self._floor_ref = _dspin(0.92, 0.0, 1.0, 3, 0.01)
        self._wall_ref = _dspin(0.92, 0.0, 1.0, 3, 0.01)
        self._wall_diff = QComboBox()
        self._wall_diff.addItems(["Diffuse (Lambertian)", "Specular"])
        mf.addRow("LED Plate Reflectance:", self._floor_ref)
        mf.addRow("Wall Reflectance:", self._wall_ref)
        mf.addRow("Wall Type:", self._wall_diff)
        root.addWidget(mat)

        stack = QGroupBox("Optical Stack")
        sf = QFormLayout(stack)
        self._diff_dist = _dspin(0.0, 0.0, 500.0, 1, 0.5)
        self._diff_dist.setToolTip("OD: distance from the LED plate top to the diffuser plate (0 = no diffuser)")
        self._diff_trans = _dspin(0.7, 0.0, 1.0, 3, 0.01)
        self._film1_z = _dspin(0.0, 0.0, 500.0, 1, 0.5)
        self._film1_z.setToolTip("Z height of film placeholder 1 (0 = skip)")
        self._film2_z = _dspin(0.0, 0.0, 500.0, 1, 0.5)
        self._film2_z.setToolTip("Z height of film placeholder 2 (0 = skip)")
        self._film_trans = _dspin(0.9, 0.0, 1.0, 3, 0.01)
        self._film_trans.setToolTip("Transmittance of film placeholders (transmitted light is scattered)")
        sf.addRow("OD (plate top → diffuser):", self._diff_dist)
        sf.addRow("Diffuser transmittance:", self._diff_trans)
        sf.addRow("Film 1 distance (Z):", self._film1_z)
        sf.addRow("Film 2 distance (Z):", self._film2_z)
        sf.addRow("Film transmittance:", self._film_trans)
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
        root.addStretch()

        root = right_col
        led = QGroupBox("LED Grid")
        lf = QFormLayout(led)
        self._use_count = QCheckBox("Specify number of LEDs (auto pitch)")
        self._use_count.setChecked(False)
        self._use_count.toggled.connect(self._schedule_preview)
        self._use_count.toggled.connect(self._sync_count_mode)
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
        self._pitch_lbl = QLabel("Or set Count X/Y and tick 'Specify number of LEDs' to auto-calculate pitch.")
        self._pitch_lbl.setWordWrap(True)
        self._pitch_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 8pt;")
        lf.addRow("", self._pitch_lbl)

        self._edge_x = _dspin(10.0, 0.0, 500.0, 1, 1.0)
        self._edge_y = _dspin(10.0, 0.0, 500.0, 1, 1.0)
        self._edge_x.valueChanged.connect(self._schedule_preview)
        self._edge_y.valueChanged.connect(self._schedule_preview)
        self._edge_x.setToolTip("Takeoff: edge LED centre to LED plate edge (X)")
        self._edge_y.setToolTip("Takeoff: edge LED centre to LED plate edge (Y)")
        lf.addRow("Takeoff X (LED ctr → plate edge):", self._edge_x)
        lf.addRow("Takeoff Y (LED ctr → plate edge):", self._edge_y)
        self._led_len = _dspin(3.0, 0.0, 100.0, 2, 0.1)
        self._led_wid = _dspin(3.0, 0.0, 100.0, 2, 0.1)
        led_size_row = QHBoxLayout()
        led_size_row.addWidget(self._led_len)
        led_size_row.addWidget(QLabel("×"))
        led_size_row.addWidget(self._led_wid)
        lf.addRow("LED size X × Y:", led_size_row)
        self._emit_mode = QComboBox()
        self._emit_mode.addItems(["Whole top face", "Custom emitting area", "Point"])
        self._emit_mode.setToolTip(
            "Surface the light leaves from. Rays start uniformly over it and the "
            "angular distribution is applied about its normal (+Z).")
        lf.addRow("Emitting surface:", self._emit_mode)
        self._emit_x = _dspin(1.5, 0.01, 100.0, 2, 0.1)
        self._emit_y = _dspin(1.5, 0.01, 100.0, 2, 0.1)
        emit_row = QHBoxLayout()
        emit_row.addWidget(self._emit_x)
        emit_row.addWidget(QLabel("×"))
        emit_row.addWidget(self._emit_y)
        lf.addRow("Emitter X × Y:", emit_row)
        self._led_flux = _dspin(100.0, 0.0, 1e7, 1, 10.0)
        self._flux_mode = QComboBox()
        self._flux_mode.addItems(["Per LED", "Total (split evenly)"])
        flux_row = QHBoxLayout()
        flux_row.addWidget(self._led_flux, 1)
        flux_row.addWidget(self._flux_mode)
        lf.addRow("LED Flux:", flux_row)
        self._led_dist = QComboBox()
        self._refresh_distributions()
        self._led_z = _dspin(0.5, 0.0, 100.0, 2, 0.1)
        self._led_z.setToolTip("LED package height above the plate top; the emitter sits on top")
        lf.addRow("Distribution:", self._led_dist)
        lf.addRow("LED height (emitter Z):", self._led_z)

        self._count_lbl = QLabel("LED count: ?")
        self._count_lbl.setWordWrap(True)
        lf.addRow("", self._count_lbl)
        self._warn_lbl = QLabel("")
        self._warn_lbl.setWordWrap(True)
        self._warn_lbl.setStyleSheet(f"color: {KPI_ORANGE};")
        lf.addRow("", self._warn_lbl)
        root.addWidget(led)

        # Top-view preview of the cavity outline and LED positions.
        self._top_view = pg.PlotWidget()
        self._top_view.setAspectLocked(True)
        self._top_view.setMinimumHeight(220)
        self._top_view.setLabel("bottom", "X")
        self._top_view.setLabel("left", "Y")
        self._top_view.addLegend(offset=(5, 5))
        self._tv_floor = self._top_view.plot([], [], pen=pg.mkPen((90, 140, 220), width=2), name="LED plate")
        self._tv_open = self._top_view.plot(
            [], [], pen=pg.mkPen((90, 140, 220), width=1, style=Qt.PenStyle.DashLine), name="Opening")
        self._tv_aa = self._top_view.plot([], [], pen=pg.mkPen((125, 209, 160), width=1), name="Active area")
        self._tv_leds = self._top_view.plot([], [], pen=pg.mkPen((255, 200, 40), width=1), name="LEDs")
        root.addWidget(self._top_view, 1)
        root.addWidget(det)

        # Everything shown in the readout / preview refreshes live.
        for w in (self._cav_w, self._cav_h, self._cav_d, self._wall_angle_x, self._wall_angle_y,
                  self._diff_dist, self._film1_z, self._film2_z, self._led_flux, self._led_z,
                  self._led_len, self._led_wid, self._emit_x, self._emit_y):
            w.valueChanged.connect(self._schedule_preview)
        self._emit_mode.currentIndexChanged.connect(self._sync_count_mode)
        for w in (self._aa_w, self._aa_h, self._margin_x, self._margin_y):
            w.valueChanged.connect(self._sync_size_mode)
        self._size_mode.currentIndexChanged.connect(self._sync_size_mode)
        self._walls.toggled.connect(self._sync_size_mode)
        self._flux_mode.currentIndexChanged.connect(self._schedule_preview)
        self._add_det.toggled.connect(self._schedule_preview)
        self._sync_count_mode()
        self._sync_size_mode()

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

    def built_project(self) -> Project:
        """Return the working-copy project with the built geometry (valid after accept)."""
        return self._project

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

    def _from_active_area(self) -> bool:
        return self._size_mode.currentIndex() == 1

    def _effective_wall_angles(self) -> tuple[float, float]:
        """Wall angles, or 0 when no walls are built (stack/detector stay plate-sized)."""
        if not self._walls.isChecked():
            return 0.0, 0.0
        return self._wall_angle_x.value(), self._wall_angle_y.value()

    def _sync_size_mode(self, _=None):
        """Enable the fields of the chosen size mode; derive plate size from the active area."""
        aa = self._from_active_area()
        for w in (self._aa_w, self._aa_h, self._margin_x, self._margin_y):
            w.setEnabled(aa)
        self._cav_w.setEnabled(not aa)
        self._cav_h.setEnabled(not aa)
        if aa:
            self._cav_w.setValue(self._aa_w.value() + 2.0 * self._margin_x.value())
            self._cav_h.setValue(self._aa_h.value() + 2.0 * self._margin_y.value())
            # Active-area workflow: the LED count is entered, pitch follows.
            self._use_count.setChecked(True)
        self._use_count.setEnabled(not aa)
        self._wall_angle_x.setEnabled(self._walls.isChecked())
        self._wall_angle_y.setEnabled(self._walls.isChecked())
        self._schedule_preview()

    def _sync_count_mode(self, _=None):
        """Grey out whichever of count / pitch the builder will ignore."""
        use_count = self._use_count.isChecked()
        for w in (self._count_x, self._count_y):
            w.setEnabled(use_count)
        for w in (self._pitch_x, self._pitch_y):
            w.setEnabled(not use_count)
        custom = self._emit_mode.currentIndex() == 1
        self._emit_x.setEnabled(custom)
        self._emit_y.setEnabled(custom)
        self._schedule_preview()

    def _emitter_size(self) -> tuple[float, float]:
        mode = self._emit_mode.currentIndex()
        if mode == 0:
            return (self._led_len.value(), self._led_wid.value())
        if mode == 1:
            return (self._emit_x.value(), self._emit_y.value())
        return (0.0, 0.0)

    def _led_positions(self) -> tuple[list[float], list[float]]:
        """LED X/Y positions exactly as build_led_grid() will place them."""
        w, h = self._cav_w.value(), self._cav_h.value()
        use_count = self._use_count.isChecked()
        xs = _axis_positions(-w / 2, w / 2, self._pitch_x.value(), self._edge_x.value(),
                             self._count_x.value() if use_count else None)
        ys = _axis_positions(-h / 2, h / 2, self._pitch_y.value(), self._edge_y.value(),
                             self._count_y.value() if use_count else None)
        return xs, ys

    def _layout_warnings(self) -> str:
        """Human-readable problems with the current layout (shown live)."""
        msgs = []
        xs, ys = self._led_positions()
        for axis, pos, size, takeoff in (("X", xs, self._led_len.value(), self._edge_x.value()),
                                         ("Y", ys, self._led_wid.value(), self._edge_y.value())):
            if len(pos) > 1 and float(np.diff(pos).min()) < size:
                msgs.append(f"LEDs overlap in {axis}: pitch is smaller than the LED size.")
            if takeoff < size / 2.0:
                msgs.append(f"Takeoff {axis} is less than half the LED size: LEDs hang over the plate edge.")
        ex, ey = self._emitter_size()
        if ex > self._led_len.value() or ey > self._led_wid.value():
            msgs.append("Emitting area is larger than the LED package.")
        if self._diff_dist.value() > 0 and self._diff_dist.value() <= self._led_z.value():
            msgs.append("OD is not above the LED height: the diffuser cuts through the LEDs.")
        stack = self._stack_block_warning()
        return "\n".join(msgs + ([stack] if stack else []))

    def _stack_block_warning(self) -> str:
        """Non-empty when a diffuser/film sits on or above the output detector."""
        if not self._add_det.isChecked():
            return ""
        d = self._cav_d.value()
        bad = [f"{name} (Z={z:g})" for name, z in (
            ("Diffuser", self._diff_dist.value()),
            ("Film 1", self._film1_z.value()),
            ("Film 2", self._film2_z.value()),
        ) if z >= d]
        if not bad:
            return ""
        return (f"{', '.join(bad)} is at or above the output detector (Z={d:g}) "
                "and will never be reached. Place it below the cavity depth.")

    def _preview_count(self):
        xs, ys = self._led_positions()
        n = len(xs) * len(ys)
        w, h, d = self._cav_w.value(), self._cav_h.value(), self._cav_d.value()

        flux = self._led_flux.value()
        total = flux if self._flux_mode.currentIndex() == 1 else flux * n
        pitches = [float(np.diff(v).max()) for v in (xs, ys) if len(v) > 1]
        od = self._diff_dist.value()  # plate top is z=0
        lines = [f"LED count: {n} ({len(xs)} × {len(ys)})",
                 f"Total flux: {total:g}" + (f"   ({total / n:g} per LED)" if n else "")]
        if n:
            lines.append(f"LED density: {n / (w * h) * 100.0:.3g} per cm²")
        if pitches:
            pitch = max(pitches)
            lines.append(f"Pitch: {pitch:.4g}   OD: {od:g}   OD/pitch: {od / pitch:.2f}" if od > 0
                         else f"Pitch: {pitch:.4g}   OD/pitch: set a diffuser OD")
        self._count_lbl.setText("\n".join(lines))
        self._warn_lbl.setText(self._layout_warnings())

        # Top view: floor rectangle, opening at z=d (differs when walls are flared).
        def _rect(rw, rh):
            return [-rw / 2, rw / 2, rw / 2, -rw / 2, -rw / 2], [-rh / 2, -rh / 2, rh / 2, rh / 2, -rh / 2]
        ax, ay = self._effective_wall_angles()
        tw = w + 2 * d * float(np.tan(np.radians(min(ax, 89.0))))
        th = h + 2 * d * float(np.tan(np.radians(min(ay, 89.0))))
        self._tv_floor.setData(*_rect(w, h))
        self._tv_open.setData(*_rect(tw, th))
        if self._from_active_area():
            self._tv_aa.setData(*_rect(self._aa_w.value(), self._aa_h.value()))
        else:
            self._tv_aa.setData([], [])
        # LED footprints as closed outlines separated by NaN breaks.
        lx, ly = _rect(max(self._led_len.value(), 0.3), max(self._led_wid.value(), 0.3))
        px, py = [], []
        for y in ys:
            for x in xs:
                px += [x + v for v in lx] + [np.nan]
                py += [y + v for v in ly] + [np.nan]
        self._tv_leds.setData(px, py, connect="finite")

    def _on_accept(self):
        # If on LGP tab and LGP was built, just accept
        if self._tabs.currentIndex() == 1:
            if self._built_lgp:
                self.accept()
            else:
                QMessageBox.information(self, "LGP", "Click 'Build LGP Scene' first, or switch to the Direct-Lit tab.")
            return

        # Direct-Lit tab
        warning = self._stack_block_warning()
        if warning:
            QMessageBox.warning(self, "Optical Stack", warning)
            return
        xs, ys = self._led_positions()
        n_leds = len(xs) * len(ys)
        led_flux = self._led_flux.value()
        if self._flux_mode.currentIndex() == 1 and n_leds:
            led_flux /= n_leds

        w = self._cav_w.value()
        h = self._cav_h.value()
        d = self._cav_d.value()
        wall_x, wall_y = self._effective_wall_angles()

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
            walls=self._walls.isChecked(),
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
            film_mat_name = "film_stack"
            self._project.materials[film_mat_name] = Material(
                name=film_mat_name,
                surface_type="diffuser",
                transmittance=self._film_trans.value(),
                reflectance=1.0 - self._film_trans.value(),
                is_diffuse=True,
            )
            build_optical_stack(
                self._project, w, h, d,
                diffuser_distance=diff_z,
                film_distances=film_zs if film_zs else None,
                diffuser_material=diff_mat_name,
                film_material=film_mat_name,
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
            if self._from_active_area():
                # Score what the cell shows: the detector covers the active area.
                top_w, top_h = self._aa_w.value(), self._aa_h.value()
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
            led_flux=led_flux,
            distribution=self._led_dist.currentText(),
            z_offset=self._led_z.value(),
            replace_existing=True,
            count_x=count_x,
            count_y=count_y,
            emitter_size=self._emitter_size(),
        )

        QMessageBox.information(
            self,
            "Geometry Built",
            f"Created {len(self._project.surfaces)} surfaces, {n} LEDs, {len(self._project.detectors)} detector(s).",
        )
        self.accept()
