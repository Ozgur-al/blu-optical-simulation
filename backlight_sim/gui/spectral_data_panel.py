"""Spectral Data tab: SPD editor, blackbody generator, chromaticity diagram."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from backlight_sim.sim.spectral import (
    BUILTIN_SPDS,
    _CIE_LAMBDA,
    _CIE_X,
    _CIE_Y,
    _CIE_Z,
    blackbody_spd,
    get_spd,
)
from backlight_sim.gui.theme import TEXT_MUTED


# Built-in SPD names that cannot be edited or deleted
_BUILTIN_SPD_NAMES = frozenset(BUILTIN_SPDS.keys())


def _planckian_locus_xy(
    cct_values: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute CIE 1931 (x, y) points on the Planckian (blackbody) locus."""
    if cct_values is None:
        cct_values = np.concatenate([
            np.arange(1000, 4000, 100),
            np.arange(4000, 10000, 200),
            np.arange(10000, 25001, 500),
        ])
    xs, ys = [], []
    for T in cct_values:
        lam, spd = blackbody_spd(float(T), n_bins=200)
        # Compute XYZ for this SPD
        X = float(np.trapezoid(spd * np.interp(lam, _CIE_LAMBDA, _CIE_X), lam))
        Y = float(np.trapezoid(spd * np.interp(lam, _CIE_LAMBDA, _CIE_Y), lam))
        Z = float(np.trapezoid(spd * np.interp(lam, _CIE_LAMBDA, _CIE_Z), lam))
        s = X + Y + Z
        if s > 0:
            xs.append(X / s)
            ys.append(Y / s)
    return np.array(xs), np.array(ys)


def _spectral_locus_xy() -> tuple[np.ndarray, np.ndarray]:
    """Return CIE 1931 (x, y) spectral locus (closed with line of purples).

    Only returns points where the CIE sum is above a threshold to avoid
    the near-zero long-wavelength points collapsing to (0, 0).
    """
    X = _CIE_X
    Y = _CIE_Y
    Z = _CIE_Z
    s = X + Y + Z
    # Only keep points with meaningful CIE response (> 0.001 of peak)
    valid = s > s.max() * 1e-3
    x_v = X[valid] / s[valid]
    y_v = Y[valid] / s[valid]
    # Close with line of purples (connect last to first point)
    x_closed = np.append(x_v, x_v[0])
    y_closed = np.append(y_v, y_v[0])
    return x_closed, y_closed


class BlackbodyDialog(QDialog):
    """Simple dialog for entering a CCT value to generate a blackbody SPD."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Blackbody SPD Generator")
        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel("Color Temperature (K):"))
        self._spin = QDoubleSpinBox()
        self._spin.setRange(1000.0, 25000.0)
        self._spin.setValue(5000.0)
        self._spin.setSingleStep(100.0)
        self._spin.setDecimals(0)
        row.addWidget(self._spin)
        layout.addLayout(row)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    @property
    def cct_K(self) -> float:
        return float(self._spin.value())


class SpectralDataPanel(QWidget):
    """Combined Spectral Data tab.

    Provides:
    - Source SPD Manager (selector, table editor, plot, blackbody generator)
    - CIE 1931 Chromaticity Diagram (spectral locus, Planckian locus, selected SPD marker)
    """

    spectral_data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project = None
        self._loading_spd_table = False

        main_layout = QHBoxLayout(self)

        # Left: vertical splitter with SPD manager (top) and Material editor (bottom)
        left_splitter = QSplitter(Qt.Orientation.Vertical)

        # ---- SPD Manager ----
        spd_box = QGroupBox("Source SPD Manager")
        spd_layout = QVBoxLayout(spd_box)

        spd_top = QHBoxLayout()
        spd_top.addWidget(QLabel("Profile:"))
        self._spd_selector = QComboBox()
        self._spd_selector.currentTextChanged.connect(self._on_spd_changed)
        spd_top.addWidget(self._spd_selector, 1)
        spd_layout.addLayout(spd_top)

        spd_btns = QHBoxLayout()
        self._spd_import_btn = QPushButton("Import CSV")
        self._spd_import_btn.clicked.connect(self._import_spd)
        self._spd_export_btn = QPushButton("Export CSV")
        self._spd_export_btn.clicked.connect(self._export_spd)
        self._spd_delete_btn = QPushButton("Delete")
        self._spd_delete_btn.clicked.connect(self._delete_spd)
        self._spd_dup_btn = QPushButton("Duplicate")
        self._spd_dup_btn.clicked.connect(self._duplicate_spd)
        self._spd_bb_btn = QPushButton("Blackbody...")
        self._spd_bb_btn.clicked.connect(self._generate_blackbody)
        self._spd_norm_btn = QPushButton("Norm Peak=1")
        self._spd_norm_btn.clicked.connect(self._normalize_spd)
        for btn in (self._spd_import_btn, self._spd_export_btn, self._spd_delete_btn,
                    self._spd_dup_btn, self._spd_bb_btn, self._spd_norm_btn):
            spd_btns.addWidget(btn)
        spd_btns.addStretch()
        spd_layout.addLayout(spd_btns)

        self._spd_table = QTableWidget(0, 2)
        self._spd_table.setHorizontalHeaderLabels(["wavelength_nm", "intensity"])
        self._spd_table.horizontalHeader().setStretchLastSection(True)
        self._spd_table.verticalHeader().setVisible(False)
        self._spd_table.cellChanged.connect(self._on_spd_table_edited)
        spd_layout.addWidget(self._spd_table, 1)

        self._spd_plot = pg.PlotWidget()
        self._spd_plot.setLabel("bottom", "Wavelength (nm)")
        self._spd_plot.setLabel("left", "Relative Intensity")
        self._spd_plot.setTitle("SPD")
        self._spd_plot.showGrid(x=True, y=True, alpha=0.25)
        self._spd_plot.setMouseEnabled(y=False)
        self._spd_plot.setYRange(0, 1.1, padding=0)
        self._spd_plot.setMaximumHeight(160)
        spd_layout.addWidget(self._spd_plot)

        left_splitter.addWidget(spd_box)
        main_layout.addWidget(left_splitter, 2)

        # ---- Chromaticity Diagram ----
        chroma_box = QGroupBox("CIE 1931 Chromaticity")
        chroma_layout = QVBoxLayout(chroma_box)

        self._chroma_plot = pg.PlotWidget()
        self._chroma_plot.setLabel("bottom", "x")
        self._chroma_plot.setLabel("left", "y")
        self._chroma_plot.setTitle("CIE 1931")
        self._chroma_plot.setAspectLocked(True)
        self._chroma_plot.showGrid(x=True, y=True, alpha=0.2)
        chroma_layout.addWidget(self._chroma_plot)

        # Draw static loci
        self._draw_static_loci()

        # Single marker for the selected SPD's chromaticity coordinate
        self._chroma_scatter = pg.ScatterPlotItem(
            size=12, pen=pg.mkPen('w', width=1.5),
            brush=pg.mkBrush(255, 50, 50, 220),
        )
        self._chroma_plot.addItem(self._chroma_scatter)

        # Label for the chromaticity coordinate
        self._chroma_label = QLabel("x=-, y=-")
        self._chroma_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; padding: 2px;")
        chroma_layout.addWidget(self._chroma_label)

        main_layout.addWidget(chroma_box, 1)

    # ------------------------------------------------------------------
    # Static loci drawing
    # ------------------------------------------------------------------

    def _draw_static_loci(self):
        """Draw spectral locus and Planckian locus on the chromaticity diagram."""
        # Spectral locus — use a bold white/light pen so it's visible on dark background
        xl, yl = _spectral_locus_xy()
        locus_pen = pg.mkPen((200, 200, 255), width=2.0)
        self._chroma_plot.plot(xl, yl, pen=locus_pen)

        # Planckian locus
        try:
            xp, yp = _planckian_locus_xy()
            planck_pen = pg.mkPen((255, 180, 80), width=2.0)
            self._chroma_plot.plot(xp, yp, pen=planck_pen)
        except Exception:
            pass  # Non-critical — skip if computation fails

        # Fix view range to the standard CIE 1931 horseshoe region
        self._chroma_plot.setXRange(0.0, 0.85, padding=0.02)
        self._chroma_plot.setYRange(0.0, 0.92, padding=0.02)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_project(self, project):
        """Called by MainWindow when the project changes."""
        self._project = project
        self._refresh_spd_selector()

    def _update_chromaticity_for_spd(self) -> None:
        """Compute CIE 1931 (x, y) of the currently selected SPD and show as a marker."""
        self._chroma_scatter.clear()
        name = self._spd_selector.currentText()
        if not name:
            self._chroma_label.setText("x=-, y=-")
            return

        # Get the SPD data
        lam = intensity = None
        if name in _BUILTIN_SPD_NAMES:
            lam, intensity = get_spd(name)
        elif self._project is not None and name in self._project.spd_profiles:
            entry = self._project.spd_profiles[name]
            lam = np.asarray(entry["wavelength_nm"], dtype=float)
            intensity = np.asarray(entry["intensity"], dtype=float)

        if lam is None or len(lam) < 2:
            self._chroma_label.setText("x=-, y=-")
            return

        # Integrate SPD * CIE color matching functions to get X, Y, Z
        spd_x = np.interp(lam, _CIE_LAMBDA, _CIE_X)
        spd_y = np.interp(lam, _CIE_LAMBDA, _CIE_Y)
        spd_z = np.interp(lam, _CIE_LAMBDA, _CIE_Z)

        X = float(np.trapezoid(intensity * spd_x, lam))
        Y = float(np.trapezoid(intensity * spd_y, lam))
        Z = float(np.trapezoid(intensity * spd_z, lam))

        s = X + Y + Z
        if s < 1e-12:
            self._chroma_label.setText("x=-, y=-")
            return

        cx = X / s
        cy = Y / s
        self._chroma_scatter.setData([cx], [cy])
        self._chroma_label.setText(f"x={cx:.4f}, y={cy:.4f}")

        # Restore fixed CIE 1931 view range
        self._chroma_plot.setXRange(0.0, 0.85, padding=0.02)
        self._chroma_plot.setYRange(0.0, 0.92, padding=0.02)

    # ------------------------------------------------------------------
    # SPD section
    # ------------------------------------------------------------------

    def _refresh_spd_selector(self):
        current = self._spd_selector.currentText()
        blocker = QSignalBlocker(self._spd_selector)
        self._spd_selector.clear()
        # Built-in names first
        for name in sorted(_BUILTIN_SPD_NAMES):
            self._spd_selector.addItem(name)
        # Custom profiles from project
        if self._project is not None:
            for name in sorted(self._project.spd_profiles.keys()):
                self._spd_selector.addItem(name)
        del blocker
        if current and self._spd_selector.findText(current) >= 0:
            self._spd_selector.setCurrentText(current)
        if self._spd_selector.count() > 0:
            self._on_spd_changed(self._spd_selector.currentText())

    def _on_spd_changed(self, name: str):
        if self._loading_spd_table or not name:
            return
        # Load data
        if name in _BUILTIN_SPD_NAMES:
            lam, intensity = get_spd(name)
            editable = False
        elif self._project is not None and name in self._project.spd_profiles:
            entry = self._project.spd_profiles[name]
            lam = np.asarray(entry["wavelength_nm"], dtype=float)
            intensity = np.asarray(entry["intensity"], dtype=float)
            editable = True
        else:
            self._spd_table.setRowCount(0)
            self._spd_plot.clear()
            return

        self._fill_spd_table(lam, intensity, editable=editable)
        self._plot_spd(lam, intensity)
        self._update_chromaticity_for_spd()

    def _fill_spd_table(self, lam: np.ndarray, intensity: np.ndarray, editable: bool = True):
        self._loading_spd_table = True
        self._spd_table.setRowCount(0)
        for wl, iv in zip(lam, intensity):
            row = self._spd_table.rowCount()
            self._spd_table.insertRow(row)
            item_wl = QTableWidgetItem(f"{float(wl):.4g}")
            item_iv = QTableWidgetItem(f"{float(iv):.6g}")
            if not editable:
                item_wl.setFlags(item_wl.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item_iv.setFlags(item_iv.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._spd_table.setItem(row, 0, item_wl)
            self._spd_table.setItem(row, 1, item_iv)
        self._loading_spd_table = False

    def _plot_spd(self, lam: np.ndarray, intensity: np.ndarray):
        self._spd_plot.clear()
        pen = pg.mkPen((255, 200, 50), width=2)
        self._spd_plot.plot(lam, intensity, pen=pen)
        self._spd_plot.setYRange(0, 1.1, padding=0)

    def _on_spd_table_edited(self, row: int, col: int):
        if self._loading_spd_table or self._project is None:
            return
        name = self._spd_selector.currentText()
        if not name or name in _BUILTIN_SPD_NAMES:
            return
        # Re-read table and save back to project
        lam, intensity = self._read_spd_table()
        if lam is None:
            return
        self._project.spd_profiles[name] = {
            "wavelength_nm": lam.tolist(),
            "intensity": intensity.tolist(),
        }
        self._plot_spd(lam, intensity)
        self._update_chromaticity_for_spd()
        self.spectral_data_changed.emit()

    def _read_spd_table(self) -> tuple[np.ndarray | None, np.ndarray | None]:
        lam, intensity = [], []
        for row in range(self._spd_table.rowCount()):
            wi = self._spd_table.item(row, 0)
            ii = self._spd_table.item(row, 1)
            if wi is None or ii is None:
                continue
            try:
                lam.append(float(wi.text()))
                intensity.append(float(ii.text()))
            except ValueError:
                continue
        if len(lam) < 2:
            return None, None
        return np.array(lam, dtype=float), np.array(intensity, dtype=float)

    def _import_spd(self):
        if self._project is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import SPD CSV", "", "CSV files (*.csv *.txt);;All files (*)"
        )
        if not path:
            return
        try:
            data = np.loadtxt(path, delimiter=",", skiprows=1)
            if data.ndim == 1:
                data = data.reshape(1, -1)
            lam = data[:, 0]
            intensity = data[:, 1]
        except Exception as exc:
            QMessageBox.critical(self, "Import Error", str(exc))
            return
        name = self._unique_spd_name(Path(path).stem or "spd")
        self._project.spd_profiles[name] = {
            "wavelength_nm": lam.tolist(),
            "intensity": intensity.tolist(),
        }
        self._refresh_spd_selector()
        self._spd_selector.setCurrentText(name)
        self.spectral_data_changed.emit()

    def _export_spd(self):
        if self._project is None:
            return
        name = self._spd_selector.currentText()
        if not name:
            return
        if name in _BUILTIN_SPD_NAMES:
            lam, intensity = get_spd(name)
        elif name in self._project.spd_profiles:
            entry = self._project.spd_profiles[name]
            lam = np.asarray(entry["wavelength_nm"], dtype=float)
            intensity = np.asarray(entry["intensity"], dtype=float)
        else:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export SPD CSV", f"{name}.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        data = np.column_stack([lam, intensity])
        np.savetxt(path, data, delimiter=",", header="wavelength_nm,intensity", comments="")

    def _delete_spd(self):
        if self._project is None:
            return
        name = self._spd_selector.currentText()
        if not name:
            return
        if name in _BUILTIN_SPD_NAMES:
            QMessageBox.warning(self, "Protected", "Built-in SPD profiles cannot be deleted.")
            return
        self._project.spd_profiles.pop(name, None)
        self._refresh_spd_selector()
        self.spectral_data_changed.emit()

    def _duplicate_spd(self):
        if self._project is None:
            return
        name = self._spd_selector.currentText()
        if not name:
            return
        if name in _BUILTIN_SPD_NAMES:
            lam, intensity = get_spd(name)
        elif name in self._project.spd_profiles:
            entry = self._project.spd_profiles[name]
            lam = np.asarray(entry["wavelength_nm"], dtype=float)
            intensity = np.asarray(entry["intensity"], dtype=float)
        else:
            return
        new_name = self._unique_spd_name(f"{name}_copy")
        self._project.spd_profiles[new_name] = {
            "wavelength_nm": lam.tolist(),
            "intensity": intensity.tolist(),
        }
        self._refresh_spd_selector()
        self._spd_selector.setCurrentText(new_name)
        self.spectral_data_changed.emit()

    def _generate_blackbody(self):
        if self._project is None:
            return
        dlg = BlackbodyDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        cct = dlg.cct_K
        lam, intensity = blackbody_spd(cct)
        name = self._unique_spd_name(f"blackbody_{int(cct)}K")
        self._project.spd_profiles[name] = {
            "wavelength_nm": lam.tolist(),
            "intensity": intensity.tolist(),
        }
        self._refresh_spd_selector()
        self._spd_selector.setCurrentText(name)
        self.spectral_data_changed.emit()

    def _normalize_spd(self):
        if self._project is None:
            return
        name = self._spd_selector.currentText()
        if not name or name in _BUILTIN_SPD_NAMES:
            return
        entry = self._project.spd_profiles.get(name)
        if not entry:
            return
        intensity = np.asarray(entry["intensity"], dtype=float)
        peak = float(intensity.max())
        if peak > 0:
            intensity = intensity / peak
        self._project.spd_profiles[name]["intensity"] = intensity.tolist()
        self._on_spd_changed(name)
        self.spectral_data_changed.emit()

    def _unique_spd_name(self, base: str) -> str:
        if self._project is None:
            return base
        name = base
        idx = 2
        while name in self._project.spd_profiles or name in _BUILTIN_SPD_NAMES:
            name = f"{base}_{idx}"
            idx += 1
        return name

