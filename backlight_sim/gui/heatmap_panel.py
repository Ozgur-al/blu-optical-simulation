"""2D heatmap display with KPI statistics and export."""

from __future__ import annotations

import csv
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout as _QVL,  # used in spectrum popup
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QComboBox, QDoubleSpinBox, QLabel, QGroupBox, QPushButton, QFileDialog,
)

from backlight_sim.core.detectors import DetectorResult, SimulationResult

# Uniformity area fractions to evaluate
_FRACTIONS = [("1/4", 0.25), ("1/6", 1 / 6), ("1/10", 0.10)]

# Color uniformity row labels
_COLOR_FRACTIONS = [
    ("Full",       None),
    ("Center 1/4", 0.25),
    ("Center 1/6", 1 / 6),
    ("Center 1/10", 0.10),
]


def _uniformity_in_center(grid: np.ndarray, fraction: float) -> tuple[float, float]:
    """Return (min/avg, min/max) uniformity in the central *fraction* area."""
    ny, nx = grid.shape
    f_side = float(np.sqrt(fraction))
    cy, cx = ny // 2, nx // 2
    half_y = max(1, int(ny * f_side / 2))
    half_x = max(1, int(nx * f_side / 2))
    roi = grid[cy - half_y: cy + half_y, cx - half_x: cx + half_x]
    if roi.size == 0 or roi.max() == 0:
        return 0.0, 0.0
    avg = float(roi.mean())
    mn  = float(roi.min())
    mx  = float(roi.max())
    return (mn / avg if avg > 0 else 0.0, mn / mx if mx > 0 else 0.0)


def _corner_ratio(grid: np.ndarray, corner_frac: float = 0.1) -> float:
    """Average of the four corner patches divided by the full-grid average.

    Each corner patch is *corner_frac* × the grid dimensions (clamped to ≥1 px).
    Returns 0.0 when the grid average is zero.
    """
    ny, nx = grid.shape
    ch = max(1, int(ny * corner_frac))
    cw = max(1, int(nx * corner_frac))
    corners = np.concatenate([
        grid[:ch,   :cw  ].ravel(),
        grid[:ch,  -cw:  ].ravel(),
        grid[-ch:,  :cw  ].ravel(),
        grid[-ch:, -cw:  ].ravel(),
    ])
    full_avg   = float(grid.mean())
    corner_avg = float(corners.mean())
    return corner_avg / full_avg if full_avg > 0 else 0.0


def _edge_center_ratio(grid: np.ndarray) -> float:
    """Ratio of outer-edge average to center-region average.

    Center = inner 50 % × 50 % region (25 % of total area).
    Edge   = outermost 15 % strip on all four sides.
    Returns edge_avg / center_avg; close to 1.0 is most uniform.
    """
    ny, nx = grid.shape
    cy, cx = ny // 2, nx // 2
    half_y = max(1, int(ny * 0.25))
    half_x = max(1, int(nx * 0.25))
    center = grid[cy - half_y: cy + half_y, cx - half_x: cx + half_x]

    ey = max(1, int(ny * 0.15))
    ex = max(1, int(nx * 0.15))
    edge_mask = np.zeros(grid.shape, dtype=bool)
    edge_mask[:ey, :] = True
    edge_mask[-ey:, :] = True
    edge_mask[:, :ex] = True
    edge_mask[:, -ex:] = True
    edge = grid[edge_mask]

    center_avg = float(center.mean()) if center.size > 0 else 0.0
    edge_avg   = float(edge.mean())   if edge.size   > 0 else 0.0
    if center_avg == 0:
        return 0.0
    return edge_avg / center_avg


class HeatmapPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        # ---- detector selector ----
        top = QHBoxLayout()
        top.addWidget(QLabel("Detector:"))
        self._selector = QComboBox()
        self._selector.currentTextChanged.connect(self._on_detector_changed)
        top.addWidget(self._selector)
        self._color_mode = QComboBox()
        self._color_mode.addItems(["Intensity (mono)", "Color (RGB)", "Spectral Color"])
        self._color_mode.currentIndexChanged.connect(self._on_color_mode_changed)
        top.addWidget(QLabel("Display:"))
        top.addWidget(self._color_mode)
        top.addStretch()
        layout.addLayout(top)

        # ---- heatmap ----
        self._plot = pg.PlotWidget()
        self._plot.setAspectLocked(True)
        self._plot.hideAxis("left")
        self._plot.hideAxis("bottom")
        self._img = pg.ImageItem()
        self._plot.addItem(self._img)
        # Click to inspect per-pixel spectrum
        self._img.mouseClickEvent = self._on_image_clicked
        # Interactive ROI for custom region stats
        self._roi = pg.RectROI([10, 10], [30, 30], pen=pg.mkPen('c', width=2))
        self._roi.addScaleHandle([1, 1], [0, 0])
        self._roi.addScaleHandle([0, 0], [1, 1])
        self._plot.addItem(self._roi)
        self._roi.sigRegionChangeFinished.connect(self._update_roi_stats)
        self._roi.hide()
        self._cbar = pg.ColorBarItem(
            values=(0, 1), colorMap=pg.colormap.get("inferno"),
        )
        self._cbar.setImageItem(self._img)
        layout.addWidget(self._plot, stretch=3)

        # ---- ROI stats ----
        roi_row = QHBoxLayout()
        self._roi_toggle = QPushButton("Show ROI")
        self._roi_toggle.setCheckable(True)
        self._roi_toggle.toggled.connect(self._toggle_roi)
        roi_row.addWidget(self._roi_toggle)
        self._roi_lbl = QLabel("ROI: --")
        self._roi_lbl.setStyleSheet("font-family: monospace; color: cyan;")
        roi_row.addWidget(self._roi_lbl, 1)
        layout.addLayout(roi_row)

        # ---- grid statistics ----
        stats_box = QGroupBox("Grid Statistics")
        sg = QGridLayout(stats_box)
        sg.setVerticalSpacing(2)

        def _lbl(text="--"):
            l = QLabel(text)
            l.setStyleSheet("font-family: monospace;")
            return l

        self._lbl_avg    = _lbl(); self._lbl_peak  = _lbl()
        self._lbl_min    = _lbl(); self._lbl_hits  = _lbl()
        self._lbl_std    = _lbl(); self._lbl_cv    = _lbl()
        self._lbl_hot    = _lbl(); self._lbl_ecr   = _lbl()
        self._lbl_rmse   = _lbl(); self._lbl_mad   = _lbl()
        self._lbl_corner = _lbl()

        sg.addWidget(QLabel("Avg:"),         0, 0); sg.addWidget(self._lbl_avg,    0, 1)
        sg.addWidget(QLabel("Peak:"),        0, 2); sg.addWidget(self._lbl_peak,   0, 3)
        sg.addWidget(QLabel("Min:"),         0, 4); sg.addWidget(self._lbl_min,    0, 5)
        sg.addWidget(QLabel("Hits:"),        0, 6); sg.addWidget(self._lbl_hits,   0, 7)
        sg.addWidget(QLabel("Std Dev:"),     1, 0); sg.addWidget(self._lbl_std,    1, 1)
        sg.addWidget(QLabel("CV:"),          1, 2); sg.addWidget(self._lbl_cv,     1, 3)
        sg.addWidget(QLabel("Hotspot:"),     1, 4); sg.addWidget(self._lbl_hot,    1, 5)
        sg.addWidget(QLabel("Edge/Ctr:"),    1, 6); sg.addWidget(self._lbl_ecr,    1, 7)
        sg.addWidget(QLabel("RMSE/avg:"),    2, 0); sg.addWidget(self._lbl_rmse,   2, 1)
        sg.addWidget(QLabel("MAD/avg:"),     2, 2); sg.addWidget(self._lbl_mad,    2, 3)
        corner_lbl = QLabel("Corner/avg:")
        corner_lbl.setToolTip("Average of the 4 corner patches (10 % of grid size each) / full avg")
        sg.addWidget(corner_lbl,             2, 4); sg.addWidget(self._lbl_corner, 2, 5)

        layout.addWidget(stats_box, stretch=0)

        # ---- uniformity ----
        uni_box = QGroupBox("Uniformity")
        ug = QGridLayout(uni_box)
        ug.setVerticalSpacing(2)
        self._uni_labels: dict[str, tuple[QLabel, QLabel]] = {}
        for row_i, (label, _frac) in enumerate(_FRACTIONS):
            ug.addWidget(QLabel(f"U ({label} area)  min/avg:"), row_i, 0)
            la = _lbl(); ug.addWidget(la, row_i, 1)
            ug.addWidget(QLabel("min/max:"), row_i, 2)
            lm = _lbl(); ug.addWidget(lm, row_i, 3)
            self._uni_labels[label] = (la, lm)
        layout.addWidget(uni_box, stretch=0)

        # ---- color uniformity (spectral only) ----
        self._color_uni_box = QGroupBox("Color Uniformity")
        cug = QGridLayout(self._color_uni_box)
        cug.setVerticalSpacing(2)
        # Column headers: delta-CCx, delta-CCy, delta-u', delta-v', CCT avg, CCT range
        _col_hdrs = ["delta-CCx", "delta-CCy", "delta-u'", "delta-v'", "CCT avg", "CCT range"]
        for ci, hdr in enumerate(_col_hdrs):
            lbl = QLabel(hdr)
            lbl.setStyleSheet("font-weight: bold;")
            cug.addWidget(lbl, 0, ci + 1)

        self._color_uni_labels: dict[str, list[QLabel]] = {}
        for row_i, (row_label, _frac) in enumerate(_COLOR_FRACTIONS):
            cug.addWidget(QLabel(row_label + ":"), row_i + 1, 0)
            row_lbls = []
            for ci in range(6):
                lbl = _lbl()
                cug.addWidget(lbl, row_i + 1, ci + 1)
                row_lbls.append(lbl)
            self._color_uni_labels[row_label] = row_lbls

        self._color_uni_box.hide()
        layout.addWidget(self._color_uni_box, stretch=0)

        # ---- energy balance ----
        energy_box = QGroupBox("Energy Balance")
        eg = QGridLayout(energy_box)
        eg.setVerticalSpacing(2)
        self._lbl_eff     = _lbl(); self._lbl_leds  = _lbl()
        self._lbl_absorb  = _lbl(); self._lbl_esc   = _lbl()
        eg.addWidget(QLabel("Efficiency:"),  0, 0); eg.addWidget(self._lbl_eff,    0, 1)
        eg.addWidget(QLabel("LED count:"),   0, 2); eg.addWidget(self._lbl_leds,   0, 3)
        eg.addWidget(QLabel("Absorbed:"),    1, 0); eg.addWidget(self._lbl_absorb, 1, 1)
        eg.addWidget(QLabel("Escaped:"),     1, 2); eg.addWidget(self._lbl_esc,    1, 3)

        # LGP-specific KPI rows (hidden when no solid bodies)
        self._lbl_lgp_coupling_key   = QLabel("Edge Coupling:")
        self._lbl_lgp_extraction_key = QLabel("Extraction Eff:")
        self._lbl_lgp_overall_key    = QLabel("Overall LGP Eff:")
        self._lbl_lgp_coupling   = _lbl()
        self._lbl_lgp_extraction = _lbl()
        self._lbl_lgp_overall    = _lbl()
        self._lbl_lgp_coupling.setToolTip(
            "Fraction of emitted flux entering LGP through coupling edge(s)")
        self._lbl_lgp_extraction.setToolTip(
            "Fraction of coupled flux reaching the detector")
        self._lbl_lgp_overall.setToolTip(
            "End-to-end efficiency (coupling \u00d7 extraction)")

        eg.addWidget(self._lbl_lgp_coupling_key,   2, 0)
        eg.addWidget(self._lbl_lgp_coupling,        2, 1)
        eg.addWidget(self._lbl_lgp_extraction_key, 2, 2)
        eg.addWidget(self._lbl_lgp_extraction,      2, 3)
        eg.addWidget(self._lbl_lgp_overall_key,    3, 0)
        eg.addWidget(self._lbl_lgp_overall,         3, 1)

        # Hide LGP rows by default
        for w in (self._lbl_lgp_coupling_key, self._lbl_lgp_extraction_key,
                  self._lbl_lgp_overall_key,
                  self._lbl_lgp_coupling, self._lbl_lgp_extraction, self._lbl_lgp_overall):
            w.hide()

        layout.addWidget(energy_box, stretch=0)

        # ---- weighted design score ----
        score_box = QGroupBox("Design Score")
        score_box.setToolTip(
            "Weighted composite score ∈ [0, 1]\n"
            "score = (w_eff × η + w_uni × U(1/4 min/avg) + w_hot × 1/hotspot) "
            "/ (w_eff + w_uni + w_hot)")
        sg2 = QGridLayout(score_box)
        sg2.setVerticalSpacing(2)

        def _wspin(default=0.33):
            s = QDoubleSpinBox()
            s.setRange(0.0, 1.0)
            s.setSingleStep(0.05)
            s.setDecimals(2)
            s.setValue(default)
            return s

        self._w_eff  = _wspin(1/3); self._w_uni = _wspin(1/3); self._w_hot = _wspin(1/3)
        self._lbl_score = _lbl()
        for w in (self._w_eff, self._w_uni, self._w_hot):
            w.valueChanged.connect(self._update_score)
        sg2.addWidget(QLabel("w_eff:"),   0, 0); sg2.addWidget(self._w_eff,    0, 1)
        sg2.addWidget(QLabel("w_uni:"),   0, 2); sg2.addWidget(self._w_uni,    0, 3)
        sg2.addWidget(QLabel("w_hot:"),   0, 4); sg2.addWidget(self._w_hot,    0, 5)
        sg2.addWidget(QLabel("Score:"),   0, 6); sg2.addWidget(self._lbl_score, 0, 7)
        layout.addWidget(score_box, stretch=0)

        # ---- export buttons ----
        btn_row = QHBoxLayout()
        btn_png  = QPushButton("Export PNG")
        btn_kpi  = QPushButton("Export KPI CSV")
        btn_grid = QPushButton("Export Grid CSV")
        btn_html = QPushButton("Export HTML Report")
        btn_zip  = QPushButton("Export Batch (ZIP)")
        btn_png.clicked.connect(self._export_png)
        btn_kpi.clicked.connect(self._export_kpi_csv)
        btn_grid.clicked.connect(self._export_grid_csv)
        btn_html.clicked.connect(self._export_html)
        btn_zip.clicked.connect(self._export_batch_zip)
        btn_row.addWidget(btn_png)
        btn_row.addWidget(btn_kpi)
        btn_row.addWidget(btn_grid)
        btn_row.addWidget(btn_html)
        btn_row.addWidget(btn_zip)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._project = None  # set externally for HTML report
        self._sim_result: SimulationResult | None = None
        self._current_result: DetectorResult | None = None
        # Latest KPIs cached for the weighted score widget
        self._last_eff_pct: float = 0.0
        self._last_u14: float = 0.0
        self._last_hot: float = 1.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_results(self, sim_result: SimulationResult):
        self._sim_result = sim_result
        self._selector.clear()
        self._selector.addItems(list(sim_result.detectors.keys()))
        if sim_result.detectors:
            self._show_result(sim_result.detectors[next(iter(sim_result.detectors))])

    def _on_detector_changed(self, name: str):
        if self._sim_result and name in self._sim_result.detectors:
            self._show_result(self._sim_result.detectors[name])

    def _on_color_mode_changed(self, _idx: int):
        if self._current_result is not None:
            self._show_result(self._current_result)

    def _show_result(self, result: DetectorResult):
        self._current_result = result
        grid = result.grid
        if grid.size == 0:
            return

        # Choose display mode
        mode_idx = self._color_mode.currentIndex()
        use_rgb = (mode_idx == 1 and result.grid_rgb is not None)
        use_spectral = (mode_idx == 2 and result.grid_spectral is not None)

        if use_spectral:
            try:
                from backlight_sim.sim.spectral import spectral_grid_to_rgb, spectral_bin_centers
            except ImportError:
                use_spectral = False
        if use_spectral:
            wl = spectral_bin_centers(result.grid_spectral.shape[2])
            rgb = spectral_grid_to_rgb(result.grid_spectral, wl)
            ny, nx = rgb.shape[:2]
            rgba = np.ones((ny, nx, 4), dtype=np.float32)
            rgba[:, :, :3] = rgb
            self._img.setImage(rgba.transpose(1, 0, 2))
            self._cbar.setLevels(values=(0, 1))
        elif use_rgb:
            rgb = result.grid_rgb.copy()
            mx = rgb.max()
            if mx > 0:
                rgb = rgb / mx  # normalize to 0-1
            # Convert to RGBA (ny, nx, 4) for ImageItem
            ny, nx = rgb.shape[:2]
            rgba = np.ones((ny, nx, 4), dtype=np.float32)
            rgba[:, :, :3] = rgb.astype(np.float32)
            self._img.setImage(rgba.transpose(1, 0, 2))  # ImageItem expects (width, height, 4)
            self._cbar.setLevels(values=(0, 1))
        else:
            self._img.setImage(grid.T)
            vmin, vmax = float(grid.min()), float(grid.max())
            if vmax > vmin:
                self._cbar.setLevels(values=(vmin, vmax))

        avg  = float(grid.mean())
        peak = float(grid.max())
        mn   = float(grid.min())
        std  = float(grid.std())
        cv   = std / avg if avg > 0 else 0.0
        hot  = peak / avg if avg > 0 else 0.0
        ecr  = _edge_center_ratio(grid)

        # Normalised error metrics vs ideal uniform field
        rmse_norm  = std / avg if avg > 0 else 0.0   # RMSE vs uniform = std dev / avg
        mad_norm   = float(np.mean(np.abs(grid - avg))) / avg if avg > 0 else 0.0
        corner_r   = _corner_ratio(grid)

        self._lbl_avg.setText(f"{avg:.4g}")
        self._lbl_peak.setText(f"{peak:.4g}")
        self._lbl_min.setText(f"{mn:.4g}")
        self._lbl_hits.setText(str(result.total_hits))
        self._lbl_std.setText(f"{std:.4g}")
        self._lbl_cv.setText(f"{cv:.3f}")
        self._lbl_hot.setText(f"{hot:.3f}")
        self._lbl_ecr.setText(f"{ecr:.3f}")
        self._lbl_rmse.setText(f"{rmse_norm:.4f}")
        self._lbl_mad.setText(f"{mad_norm:.4f}")
        self._lbl_corner.setText(f"{corner_r:.3f}")

        u14, _ = _uniformity_in_center(grid, 0.25)
        for label, frac in _FRACTIONS:
            u_avg, u_max = _uniformity_in_center(grid, frac)
            la, lm = self._uni_labels[label]
            la.setText(f"{u_avg:.3f}")
            lm.setText(f"{u_max:.3f}")

        # Cache KPIs for weighted score
        self._last_u14 = u14
        self._last_hot = hot

        # Energy balance — only if simulation-level data is available
        if self._sim_result and self._sim_result.total_emitted_flux > 0:
            emitted  = self._sim_result.total_emitted_flux
            escaped  = self._sim_result.escaped_flux
            all_det  = sum(dr.total_flux for dr in self._sim_result.detectors.values())
            absorbed = max(0.0, emitted - all_det - escaped)
            eff_pct  = result.total_flux / emitted * 100.0
            abs_pct  = absorbed / emitted * 100.0
            esc_pct  = escaped  / emitted * 100.0
            self._lbl_eff.setText(f"{eff_pct:.1f} %")
            self._lbl_absorb.setText(f"{abs_pct:.1f} %")
            self._lbl_esc.setText(f"{esc_pct:.1f} %")
            self._last_eff_pct = eff_pct
            self._lbl_leds.setText(str(self._sim_result.source_count))
        else:
            self._last_eff_pct = 0.0
            for lbl in (self._lbl_eff, self._lbl_absorb, self._lbl_esc, self._lbl_leds):
                lbl.setText("--")

        # --- LGP metrics (only when solid bodies with coupling edges exist) ---
        show_lgp = (
            self._sim_result is not None
            and hasattr(self._sim_result, "solid_body_stats")
            and bool(self._sim_result.solid_body_stats)
            and self._project is not None
            and bool(getattr(self._project, "solid_bodies", []))
        )

        lgp_widgets = (
            self._lbl_lgp_coupling_key, self._lbl_lgp_extraction_key,
            self._lbl_lgp_overall_key,
            self._lbl_lgp_coupling, self._lbl_lgp_extraction, self._lbl_lgp_overall,
        )

        if show_lgp:
            emitted = self._sim_result.total_emitted_flux
            # Compute coupling efficiency: flux entering through coupling faces
            total_coupling_flux = 0.0
            for box in self._project.solid_bodies:
                box_stats = self._sim_result.solid_body_stats.get(box.name, {})
                for edge_id in box.coupling_edges:
                    face_data = box_stats.get(edge_id, {})
                    total_coupling_flux += face_data.get("entering_flux", 0.0)

            if emitted > 0:
                coupling_eff = total_coupling_flux / emitted
            else:
                coupling_eff = None

            det_flux = sum(dr.total_flux for dr in self._sim_result.detectors.values())
            if total_coupling_flux > 0:
                extraction_eff = det_flux / total_coupling_flux
            else:
                extraction_eff = None

            if coupling_eff is not None and extraction_eff is not None:
                overall_eff = coupling_eff * extraction_eff
            else:
                overall_eff = None

            self._lbl_lgp_coupling.setText(
                f"{coupling_eff * 100:.1f} %" if coupling_eff is not None else "N/A"
            )
            self._lbl_lgp_extraction.setText(
                f"{extraction_eff * 100:.1f} %" if extraction_eff is not None else "N/A"
            )
            self._lbl_lgp_overall.setText(
                f"{overall_eff * 100:.1f} %" if overall_eff is not None else "N/A"
            )
            for w in lgp_widgets:
                w.show()
        else:
            for w in lgp_widgets:
                w.hide()

        self._update_color_uniformity(result)
        self._update_score()
        if self._roi_toggle.isChecked():
            self._update_roi_stats()

    def _update_color_uniformity(self, result: DetectorResult):
        """Update the Color Uniformity KPI section; hide it if no spectral data."""
        if result.grid_spectral is None:
            self._color_uni_box.hide()
            return
        try:
            from backlight_sim.sim.spectral import compute_color_kpis, spectral_bin_centers
            n_bins = result.grid_spectral.shape[2]
            wl = spectral_bin_centers(n_bins)
            kpis = compute_color_kpis(result.grid_spectral, wl)
        except Exception:
            self._color_uni_box.hide()
            return

        def _fmt_delta(v):
            return f"{v:.4f}" if isinstance(v, float) and not (v != v) else "--"

        def _fmt_cct(v):
            if isinstance(v, float) and not (v != v) and v > 0:
                return f"{int(round(v))} K"
            return "--"

        # Full row
        full_lbls = self._color_uni_labels["Full"]
        full_lbls[0].setText(_fmt_delta(kpis.get("delta_ccx", float("nan"))))
        full_lbls[1].setText(_fmt_delta(kpis.get("delta_ccy", float("nan"))))
        full_lbls[2].setText(_fmt_delta(kpis.get("delta_uprime", float("nan"))))
        full_lbls[3].setText(_fmt_delta(kpis.get("delta_vprime", float("nan"))))
        full_lbls[4].setText(_fmt_cct(kpis.get("cct_avg", float("nan"))))
        full_lbls[5].setText(_fmt_delta(kpis.get("cct_range", float("nan"))))

        # Center fraction rows
        for row_label, frac_key in [
            ("Center 1/4", "center_1_4"),
            ("Center 1/6", "center_1_6"),
            ("Center 1/10", "center_1_10"),
        ]:
            center_data = kpis.get(frac_key, {})
            lbls = self._color_uni_labels[row_label]
            lbls[0].setText(_fmt_delta(center_data.get("delta_ccx", float("nan"))))
            lbls[1].setText(_fmt_delta(center_data.get("delta_ccy", float("nan"))))
            lbls[2].setText(_fmt_delta(center_data.get("delta_uprime", float("nan"))))
            lbls[3].setText(_fmt_delta(center_data.get("delta_vprime", float("nan"))))
            lbls[4].setText("--")   # CCT avg/range not computed for center fractions
            lbls[5].setText("--")

        self._color_uni_box.show()

    def _update_score(self, _=None):
        """Recompute the weighted design score from cached KPIs and weight spinboxes."""
        if self._current_result is None:
            self._lbl_score.setText("--")
            return
        w_e = self._w_eff.value()
        w_u = self._w_uni.value()
        w_h = self._w_hot.value()
        total_w = w_e + w_u + w_h
        if total_w <= 0:
            self._lbl_score.setText("--")
            return
        eta_norm = self._last_eff_pct / 100.0   # 0–1
        uni_norm = self._last_u14                # 0–1
        hot_norm = 1.0 / self._last_hot if self._last_hot > 0 else 0.0  # close to 1 = good
        score = (w_e * eta_norm + w_u * uni_norm + w_h * hot_norm) / total_w
        self._lbl_score.setText(f"{score:.3f}")

    def _toggle_roi(self, on: bool):
        if on:
            self._roi.show()
            self._update_roi_stats()
        else:
            self._roi.hide()
            self._roi_lbl.setText("ROI: --")

    def _update_roi_stats(self):
        if self._current_result is None:
            return
        grid = self._current_result.grid
        if grid.size == 0:
            return
        # Get ROI region from image data
        try:
            roi_data = self._roi.getArrayRegion(grid.T, self._img)
        except Exception as exc:
            self._roi_lbl.setText(f"ROI: error ({exc})")
            return
        if roi_data is None or roi_data.size == 0:
            self._roi_lbl.setText("ROI: empty")
            return
        avg = float(roi_data.mean())
        mn = float(roi_data.min())
        mx = float(roi_data.max())
        u_ma = mn / avg if avg > 0 else 0.0
        u_mm = mn / mx if mx > 0 else 0.0
        self._roi_lbl.setText(
            f"ROI: avg={avg:.4g}  min={mn:.4g}  max={mx:.4g}  "
            f"min/avg={u_ma:.3f}  min/max={u_mm:.3f}"
        )

    def _on_image_clicked(self, event):
        """Show per-pixel spectral power distribution popup on image click."""
        if self._current_result is None:
            return
        if self._current_result.grid_spectral is None:
            return
        try:
            pos = event.pos()
            # Convert from image-item local coords to grid indices
            # ImageItem is transposed (width, height) so x->col, y->row
            col = int(pos.x())
            row = int(pos.y())
            grid_spectral = self._current_result.grid_spectral
            ny, nx, n_bins = grid_spectral.shape
            # Clamp
            col = max(0, min(col, nx - 1))
            row = max(0, min(row, ny - 1))
            spectrum = grid_spectral[row, col, :]
        except Exception:
            return

        from backlight_sim.sim.spectral import spectral_bin_centers
        wl = spectral_bin_centers(n_bins)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Pixel ({col}, {row}) Spectrum")
        dlg.setModal(False)
        dlg.resize(400, 280)
        layout = _QVL(dlg)
        pw = pg.PlotWidget()
        pw.setLabel("bottom", "Wavelength (nm)")
        pw.setLabel("left", "Flux")
        pw.setTitle(f"Pixel ({col}, {row}) SPD")
        pw.showGrid(x=True, y=True, alpha=0.25)
        pw.plot(wl, spectrum, pen=pg.mkPen((255, 200, 50), width=2))
        layout.addWidget(pw)
        dlg.show()

    def clear(self):
        self._img.clear()
        self._selector.clear()
        self._sim_result = None
        self._current_result = None
        self._last_eff_pct = 0.0
        self._last_u14 = 0.0
        self._last_hot = 1.0
        self._lbl_score.setText("--")
        _all = [
            self._lbl_avg, self._lbl_peak, self._lbl_min, self._lbl_hits,
            self._lbl_std, self._lbl_cv, self._lbl_hot, self._lbl_ecr,
            self._lbl_rmse, self._lbl_mad, self._lbl_corner,
            self._lbl_eff, self._lbl_leds, self._lbl_absorb, self._lbl_esc,
        ]
        for lbl in _all:
            lbl.setText("--")
        for la, lm in self._uni_labels.values():
            la.setText("--"); lm.setText("--")
        # Hide LGP rows
        for w in (self._lbl_lgp_coupling_key, self._lbl_lgp_extraction_key,
                  self._lbl_lgp_overall_key,
                  self._lbl_lgp_coupling, self._lbl_lgp_extraction, self._lbl_lgp_overall):
            w.hide()
        # Hide color uniformity
        self._color_uni_box.hide()

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def _export_png(self):
        if self._current_result is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Heatmap PNG", "heatmap.png", "PNG images (*.png)")
        if not path:
            return
        pixmap = self._plot.grab()
        pixmap.save(path, "PNG")

    def _export_kpi_csv(self):
        if self._current_result is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export KPI CSV", "kpi.csv", "CSV files (*.csv)")
        if not path:
            return
        r = self._current_result
        grid = r.grid
        avg  = float(grid.mean())
        peak = float(grid.max())
        mn   = float(grid.min())
        std  = float(grid.std())
        cv   = std / avg if avg > 0 else 0.0
        hot  = peak / avg if avg > 0 else 0.0
        ecr  = _edge_center_ratio(grid)

        rmse_norm  = std / avg if avg > 0 else 0.0
        mad_norm   = float(np.mean(np.abs(grid - avg))) / avg if avg > 0 else 0.0
        corner_r   = _corner_ratio(grid)

        rows = [
            ("Metric", "Value"),
            ("Detector", r.detector_name),
            ("Average flux", f"{avg:.6g}"),
            ("Peak flux", f"{peak:.6g}"),
            ("Min flux", f"{mn:.6g}"),
            ("Std Dev", f"{std:.6g}"),
            ("CV (std/avg)", f"{cv:.4f}"),
            ("Hotspot ratio (peak/avg)", f"{hot:.4f}"),
            ("Edge/Center ratio", f"{ecr:.4f}"),
            ("Corner/avg ratio (10 %)", f"{corner_r:.4f}"),
            ("RMSE/avg (vs uniform)", f"{rmse_norm:.4f}"),
            ("MAD/avg (vs uniform)", f"{mad_norm:.4f}"),
        ]
        for label, frac in _FRACTIONS:
            u_avg, u_max = _uniformity_in_center(grid, frac)
            rows.append((f"Uniformity {label} area min/avg", f"{u_avg:.4f}"))
            rows.append((f"Uniformity {label} area min/max", f"{u_max:.4f}"))
        rows.append(("Total hits", str(r.total_hits)))
        rows.append(("Total flux detected", f"{r.total_flux:.6g}"))

        if self._sim_result and self._sim_result.total_emitted_flux > 0:
            emitted  = self._sim_result.total_emitted_flux
            escaped  = self._sim_result.escaped_flux
            all_det  = sum(dr.total_flux for dr in self._sim_result.detectors.values())
            absorbed = max(0.0, emitted - all_det - escaped)
            rows += [
                ("Total emitted flux", f"{emitted:.6g}"),
                ("Extraction efficiency (%)", f"{r.total_flux / emitted * 100:.2f}"),
                ("Absorbed (%)", f"{absorbed / emitted * 100:.2f}"),
                ("Escaped (%)", f"{escaped / emitted * 100:.2f}"),
                ("LED count", str(self._sim_result.source_count)),
            ]

        # Color uniformity KPIs (only when spectral data available)
        if r.grid_spectral is not None:
            try:
                from backlight_sim.sim.spectral import compute_color_kpis, spectral_bin_centers
                n_bins = r.grid_spectral.shape[2]
                wl = spectral_bin_centers(n_bins)
                ckpis = compute_color_kpis(r.grid_spectral, wl)
                rows += [
                    ("delta_ccx",    f"{ckpis.get('delta_ccx', 0):.4f}"),
                    ("delta_ccy",    f"{ckpis.get('delta_ccy', 0):.4f}"),
                    ("delta_uprime", f"{ckpis.get('delta_uprime', 0):.4f}"),
                    ("delta_vprime", f"{ckpis.get('delta_vprime', 0):.4f}"),
                    ("cct_avg_K",    f"{ckpis.get('cct_avg', float('nan')):.0f}"),
                    ("cct_range_K",  f"{ckpis.get('cct_range', 0):.0f}"),
                ]
                for label_key, row_label in [
                    ("center_1_4", "center_1_4"),
                    ("center_1_6", "center_1_6"),
                    ("center_1_10", "center_1_10"),
                ]:
                    cdata = ckpis.get(label_key, {})
                    rows += [
                        (f"{label_key}_delta_ccx",    f"{cdata.get('delta_ccx', 0):.4f}"),
                        (f"{label_key}_delta_ccy",    f"{cdata.get('delta_ccy', 0):.4f}"),
                        (f"{label_key}_delta_uprime", f"{cdata.get('delta_uprime', 0):.4f}"),
                        (f"{label_key}_delta_vprime", f"{cdata.get('delta_vprime', 0):.4f}"),
                    ]
            except Exception:
                pass  # Non-critical — skip color KPIs on error

        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)

    def set_project(self, project):
        self._project = project

    def _export_html(self):
        if self._sim_result is None or self._project is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export HTML Report", "report.html", "HTML files (*.html)")
        if not path:
            return
        from backlight_sim.io.report import generate_html_report
        generate_html_report(self._project, self._sim_result, path)

    def _export_batch_zip(self):
        if self._sim_result is None or self._project is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Batch ZIP", "results.zip", "ZIP files (*.zip)")
        if not path:
            return
        from backlight_sim.io.batch_export import export_batch_zip
        export_batch_zip(self._project, self._sim_result, path)

    def _export_grid_csv(self):
        if self._current_result is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Grid Data", "grid.csv", "CSV files (*.csv)")
        if not path:
            return
        np.savetxt(path, self._current_result.grid, delimiter=",", fmt="%.6g")
