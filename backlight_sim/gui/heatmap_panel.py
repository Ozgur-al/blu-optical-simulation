"""2D heatmap display with KPI statistics and export."""

from __future__ import annotations

import csv
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QComboBox, QLabel, QGroupBox, QPushButton, QFileDialog,
)

from backlight_sim.core.detectors import DetectorResult, SimulationResult

# Uniformity area fractions to evaluate
_FRACTIONS = [("1/4", 0.25), ("1/6", 1 / 6), ("1/10", 0.10)]


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
        top.addStretch()
        layout.addLayout(top)

        # ---- heatmap ----
        self._plot = pg.PlotWidget()
        self._plot.setAspectLocked(True)
        self._plot.hideAxis("left")
        self._plot.hideAxis("bottom")
        self._img = pg.ImageItem()
        self._plot.addItem(self._img)
        self._cbar = pg.ColorBarItem(
            values=(0, 1), colorMap=pg.colormap.get("inferno"),
        )
        self._cbar.setImageItem(self._img)
        layout.addWidget(self._plot, stretch=3)

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

        sg.addWidget(QLabel("Avg:"),         0, 0); sg.addWidget(self._lbl_avg,  0, 1)
        sg.addWidget(QLabel("Peak:"),        0, 2); sg.addWidget(self._lbl_peak, 0, 3)
        sg.addWidget(QLabel("Min:"),         0, 4); sg.addWidget(self._lbl_min,  0, 5)
        sg.addWidget(QLabel("Hits:"),        0, 6); sg.addWidget(self._lbl_hits, 0, 7)
        sg.addWidget(QLabel("Std Dev:"),     1, 0); sg.addWidget(self._lbl_std,  1, 1)
        sg.addWidget(QLabel("CV:"),          1, 2); sg.addWidget(self._lbl_cv,   1, 3)
        sg.addWidget(QLabel("Hotspot:"),     1, 4); sg.addWidget(self._lbl_hot,  1, 5)
        sg.addWidget(QLabel("Edge/Ctr:"),    1, 6); sg.addWidget(self._lbl_ecr,  1, 7)
        sg.addWidget(QLabel("RMSE/avg:"),    2, 0); sg.addWidget(self._lbl_rmse, 2, 1)
        sg.addWidget(QLabel("MAD/avg:"),     2, 2); sg.addWidget(self._lbl_mad,  2, 3)

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
        layout.addWidget(energy_box, stretch=0)

        # ---- export buttons ----
        btn_row = QHBoxLayout()
        btn_png  = QPushButton("Export PNG")
        btn_kpi  = QPushButton("Export KPI CSV")
        btn_grid = QPushButton("Export Grid CSV")
        btn_png.clicked.connect(self._export_png)
        btn_kpi.clicked.connect(self._export_kpi_csv)
        btn_grid.clicked.connect(self._export_grid_csv)
        btn_row.addWidget(btn_png)
        btn_row.addWidget(btn_kpi)
        btn_row.addWidget(btn_grid)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._sim_result: SimulationResult | None = None
        self._current_result: DetectorResult | None = None

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

    def _show_result(self, result: DetectorResult):
        self._current_result = result
        grid = result.grid
        if grid.size == 0:
            return

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
        rmse_norm = std / avg if avg > 0 else 0.0   # RMSE vs uniform = std dev / avg
        mad_norm  = float(np.mean(np.abs(grid - avg))) / avg if avg > 0 else 0.0

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

        for label, frac in _FRACTIONS:
            u_avg, u_max = _uniformity_in_center(grid, frac)
            la, lm = self._uni_labels[label]
            la.setText(f"{u_avg:.3f}")
            lm.setText(f"{u_max:.3f}")

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
            self._lbl_leds.setText(str(self._sim_result.source_count))
        else:
            for lbl in (self._lbl_eff, self._lbl_absorb, self._lbl_esc, self._lbl_leds):
                lbl.setText("--")

    def clear(self):
        self._img.clear()
        self._selector.clear()
        self._sim_result = None
        self._current_result = None
        _all = [
            self._lbl_avg, self._lbl_peak, self._lbl_min, self._lbl_hits,
            self._lbl_std, self._lbl_cv, self._lbl_hot, self._lbl_ecr,
            self._lbl_rmse, self._lbl_mad,
            self._lbl_eff, self._lbl_leds, self._lbl_absorb, self._lbl_esc,
        ]
        for lbl in _all:
            lbl.setText("--")
        for la, lm in self._uni_labels.values():
            la.setText("--"); lm.setText("--")

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

        rmse_norm = std / avg if avg > 0 else 0.0
        mad_norm  = float(np.mean(np.abs(grid - avg))) / avg if avg > 0 else 0.0

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

        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)

    def _export_grid_csv(self):
        if self._current_result is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Grid Data", "grid.csv", "CSV files (*.csv)")
        if not path:
            return
        np.savetxt(path, self._current_result.grid, delimiter=",", fmt="%.6g")
