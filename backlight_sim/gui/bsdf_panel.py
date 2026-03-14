"""BSDF management panel — import, view, and manage BSDF profiles."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from backlight_sim.io.bsdf_io import load_bsdf_csv, validate_bsdf


class BSDFPanel(QWidget):
    """Panel for importing, viewing, and managing BSDF scatter profiles.

    Left: list of profile names with Import/Delete buttons.
    Right: tab widget showing 2D heatmap (reflection/transmission) and a 1D
    line plot for the selected theta_in row.
    """

    bsdf_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project = None
        self._current_profile_name: str | None = None
        self._selected_theta_in_idx: int = 0

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # ---- Left panel: profile list ----
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("<b>BSDF Profiles</b>"))
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_profile_selected)
        left_layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        self._import_btn = QPushButton("Import CSV")
        self._import_btn.clicked.connect(self._import_csv)
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.clicked.connect(self._delete_profile)
        btn_row.addWidget(self._import_btn)
        btn_row.addWidget(self._delete_btn)
        left_layout.addLayout(btn_row)

        left_widget.setMaximumWidth(220)
        main_layout.addWidget(left_widget)

        # ---- Right panel: views ----
        right_splitter = QSplitter()
        right_splitter.setOrientation(pg.Qt.QtCore.Qt.Orientation.Vertical)

        # Tabs: Reflection / Transmission (2D heatmap)
        self._tabs = QTabWidget()
        self._refl_img = pg.ImageItem()
        self._trans_img = pg.ImageItem()
        self._refl_plot = self._make_heatmap_plot(self._refl_img, "Reflection")
        self._trans_plot = self._make_heatmap_plot(self._trans_img, "Transmission")
        self._tabs.addTab(self._refl_plot["widget"], "Reflection")
        self._tabs.addTab(self._trans_plot["widget"], "Transmission")
        self._tabs.currentChanged.connect(self._refresh_plots)
        right_splitter.addWidget(self._tabs)

        # 1D line plot for selected theta_in row
        self._line_plot_widget = pg.PlotWidget(title="Selected row: I(theta_out)")
        self._line_plot_widget.setLabel("bottom", "theta_out (deg)")
        self._line_plot_widget.setLabel("left", "Intensity")
        self._line_curve_refl = self._line_plot_widget.plot(pen=pg.mkPen("r", width=2))
        self._line_curve_trans = self._line_plot_widget.plot(pen=pg.mkPen("b", width=2),
                                                              name="Trans")
        right_splitter.addWidget(self._line_plot_widget)
        right_splitter.setSizes([300, 150])

        main_layout.addWidget(right_splitter, 1)

    def _make_heatmap_plot(self, img_item, title: str) -> dict:
        """Create a PlotWidget with an ImageItem for 2D heatmap."""
        pw = pg.PlotWidget(title=title)
        pw.setLabel("bottom", "theta_out (deg)")
        pw.setLabel("left", "theta_in (deg)")
        pw.addItem(img_item)
        # Click to select theta_in row
        img_item.scene().sigMouseClicked.connect(self._on_heatmap_click)
        cbar = pg.ColorBarItem(values=(0, 1), colorMap="inferno", label="Intensity")
        cbar.setImageItem(img_item)
        return {"widget": pw, "cbar": cbar}

    def set_project(self, project):
        self._project = project
        self.refresh()

    def refresh(self):
        """Reload profile list from the project."""
        self._list.clear()
        if self._project is None:
            return
        profiles = getattr(self._project, "bsdf_profiles", {})
        for name in profiles:
            self._list.addItem(name)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)
        else:
            self._current_profile_name = None
            self._clear_plots()

    def _on_profile_selected(self, row: int):
        if row < 0 or self._project is None:
            self._current_profile_name = None
            self._clear_plots()
            return
        item = self._list.item(row)
        if item is None:
            return
        self._current_profile_name = item.text()
        self._selected_theta_in_idx = 0
        self._refresh_plots()

    def _refresh_plots(self):
        if self._project is None or self._current_profile_name is None:
            self._clear_plots()
            return
        profiles = getattr(self._project, "bsdf_profiles", {})
        profile = profiles.get(self._current_profile_name)
        if profile is None:
            self._clear_plots()
            return

        theta_in = np.asarray(profile["theta_in"])
        theta_out = np.asarray(profile["theta_out"])
        refl = np.asarray(profile["refl_intensity"])
        trans = np.asarray(profile["trans_intensity"])

        # Update heatmaps — ImageItem expects (width, height) indexed [x, y]
        self._refl_img.setImage(refl.T, autoLevels=True)
        self._trans_img.setImage(trans.T, autoLevels=True)

        # Set scale so axes show angles
        if len(theta_in) > 1 and len(theta_out) > 1:
            dt_in = (theta_in[-1] - theta_in[0]) / max(1, len(theta_in) - 1)
            dt_out = (theta_out[-1] - theta_out[0]) / max(1, len(theta_out) - 1)
            self._refl_img.resetTransform()
            self._refl_img.setRect(pg.QtCore.QRectF(
                float(theta_out[0]), float(theta_in[0]),
                float(theta_out[-1] - theta_out[0]),
                float(theta_in[-1] - theta_in[0]),
            ))
            self._trans_img.setRect(pg.QtCore.QRectF(
                float(theta_out[0]), float(theta_in[0]),
                float(theta_out[-1] - theta_out[0]),
                float(theta_in[-1] - theta_in[0]),
            ))

        # Update 1D line plot for selected row
        idx = min(self._selected_theta_in_idx, len(theta_in) - 1)
        self._line_plot_widget.setTitle(
            f"Row: theta_in = {theta_in[idx]:.1f} deg"
        )
        self._line_curve_refl.setData(theta_out, refl[idx])
        self._line_curve_trans.setData(theta_out, trans[idx])

    def _on_heatmap_click(self, event):
        """Select theta_in row by clicking on the heatmap."""
        if self._project is None or self._current_profile_name is None:
            return
        profiles = getattr(self._project, "bsdf_profiles", {})
        profile = profiles.get(self._current_profile_name)
        if profile is None:
            return
        try:
            vb = self._refl_plot["widget"].getPlotItem().getViewBox()
            pos = vb.mapSceneToView(event.scenePos())
            theta_in = np.asarray(profile["theta_in"])
            y = float(pos.y())
            idx = int(np.argmin(np.abs(theta_in - y)))
            self._selected_theta_in_idx = idx
            self._refresh_plots()
        except Exception:
            pass

    def _clear_plots(self):
        self._refl_img.clear()
        self._trans_img.clear()
        self._line_curve_refl.setData([], [])
        self._line_curve_trans.setData([], [])

    def _import_csv(self):
        """Import a BSDF CSV file into the current project."""
        if self._project is None:
            QMessageBox.warning(self, "No Project", "Open a project first.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import BSDF CSV", "",
            "CSV files (*.csv);;Text files (*.txt);;All files (*)"
        )
        if not path:
            return
        try:
            profile = load_bsdf_csv(path)
        except Exception as exc:
            QMessageBox.critical(self, "Import Error", str(exc))
            return

        valid, msg = validate_bsdf(profile)
        if not valid:
            ret = QMessageBox.warning(
                self, "BSDF Validation Warning",
                f"BSDF profile may not conserve energy:\n{msg}\n\nImport anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ret != QMessageBox.StandardButton.Yes:
                return

        # Use the filename stem as the profile name (deduplicate if needed)
        from pathlib import Path as _Path
        base_name = _Path(path).stem
        name = base_name
        profiles = getattr(self._project, "bsdf_profiles", {})
        counter = 1
        while name in profiles:
            name = f"{base_name}_{counter}"
            counter += 1

        profiles[name] = profile
        self._project.bsdf_profiles = profiles
        self.refresh()
        # Select the newly imported profile
        for i in range(self._list.count()):
            if self._list.item(i).text() == name:
                self._list.setCurrentRow(i)
                break
        self.bsdf_changed.emit()

    def _delete_profile(self):
        """Delete the selected BSDF profile (with reference check)."""
        if self._project is None or self._current_profile_name is None:
            return
        name = self._current_profile_name

        # Check for references in optical_properties
        refs = []
        for op in self._project.optical_properties.values():
            if getattr(op, "bsdf_profile_name", "") == name:
                refs.append(op.name)

        if refs:
            QMessageBox.warning(
                self, "Cannot Delete",
                f"BSDF profile '{name}' is referenced by:\n"
                + "\n".join(f"  - {r}" for r in refs)
                + "\n\nRemove those references first.",
            )
            return

        ret = QMessageBox.question(
            self, "Delete BSDF Profile",
            f"Delete BSDF profile '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return

        profiles = getattr(self._project, "bsdf_profiles", {})
        profiles.pop(name, None)
        self._project.bsdf_profiles = profiles
        self.refresh()
        self.bsdf_changed.emit()
