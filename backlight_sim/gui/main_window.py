"""Main application window."""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QTabWidget,
    QProgressBar, QStatusBar, QMessageBox, QFileDialog, QPushButton,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QActionGroup

from backlight_sim.core.project_model import Project
from backlight_sim.core.geometry import Rectangle
from backlight_sim.core.materials import Material
from backlight_sim.core.sources import PointSource
from backlight_sim.core.detectors import DetectorSurface, SimulationResult
from backlight_sim.sim.tracer import RayTracer
from backlight_sim.gui.object_tree import ObjectTree
from backlight_sim.gui.properties_panel import PropertiesPanel
from backlight_sim.gui.viewport_3d import Viewport3D
from backlight_sim.gui.heatmap_panel import HeatmapPanel
from backlight_sim.gui.angular_distribution_panel import AngularDistributionPanel
from backlight_sim.io.angular_distributions import merge_default_profiles


class SimulationThread(QThread):
    progress     = Signal(float)
    finished_sim = Signal(object)

    def __init__(self, project: Project):
        super().__init__()
        self.tracer = RayTracer(project)

    def run(self):
        result = self.tracer.run(progress_callback=self.progress.emit)
        self.finished_sim.emit(result)

    def cancel(self):
        self.tracer.cancel()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Blu Optical Simulation")
        self.resize(1440, 920)

        self._project = Project()
        self._init_default_materials()
        merge_default_profiles(self._project)
        self._sim_thread = None
        self._counter = {"Sources": 0, "Surfaces": 0, "Materials": 0, "Detectors": 0}
        self._last_save_path = None
        self._selected_group = None
        self._selected_name = None

        self._setup_ui()
        self._setup_menu()
        self._connect_signals()
        self._refresh_all()

    def _init_default_materials(self):
        self._project.materials["default_reflector"] = Material(
            "default_reflector", "reflector", reflectance=0.9, absorption=0.1)
        self._project.materials["absorber"] = Material(
            "absorber", "absorber", reflectance=0.0, absorption=1.0)

    def _setup_ui(self):
        main_split = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(main_split)

        self._tree = ObjectTree()
        self._tree.setMinimumWidth(180)
        main_split.addWidget(self._tree)

        self._center_tabs = QTabWidget()
        self._viewport = Viewport3D()
        self._heatmap = HeatmapPanel()
        self._ang_dist = AngularDistributionPanel()
        self._ang_dist.set_project(self._project)
        self._center_tabs.addTab(self._viewport, "3D View")
        self._center_tabs.addTab(self._heatmap, "Heatmap")
        self._center_tabs.addTab(self._ang_dist, "Angular Dist.")
        main_split.addWidget(self._center_tabs)

        self._properties = PropertiesPanel()
        main_split.addWidget(self._properties)
        main_split.setSizes([200, 820, 300])

        status = QStatusBar()
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setFixedWidth(200)
        self._progress.setVisible(False)
        self._run_btn = QPushButton("Run")
        self._run_btn.clicked.connect(self._run_simulation)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._cancel_simulation)
        self._cancel_btn.setEnabled(False)
        status.addPermanentWidget(self._run_btn)
        status.addPermanentWidget(self._cancel_btn)
        status.addPermanentWidget(self._progress)
        self.setStatusBar(status)

    def _setup_menu(self):
        mb = self.menuBar()

        fm = mb.addMenu("&File")
        fm.addAction("New Project",    self._new_project)
        fm.addAction("Open...",        self._open_project)
        fm.addAction("Save",           self._save_project)
        fm.addAction("Save As...",     self._save_project_as)
        fm.addSeparator()
        fm.addAction("Exit",           self.close)

        pm = mb.addMenu("&Presets")
        from backlight_sim.io.presets import PRESETS
        for name, factory in PRESETS.items():
            pm.addAction(name, lambda f=factory: self._load_preset(f))

        am = mb.addMenu("&Add")
        am.addAction("Point Source",   lambda: self._add_object("Sources"))
        am.addAction("Surface",        lambda: self._add_object("Surfaces"))
        am.addAction("Detector",       lambda: self._add_object("Detectors"))
        am.addAction("Material",       lambda: self._add_object("Materials"))

        bm = mb.addMenu("&Build")
        bm.addAction("Geometry Builder...", self._open_geometry_builder)

        sm = mb.addMenu("&Simulation")
        sm.addAction("Settings",       self._show_settings)
        sm.addAction("Run",            self._run_simulation)
        sm.addAction("Cancel",         self._cancel_simulation)

        vm = mb.addMenu("&View")
        self._view_mode_group = QActionGroup(self)
        self._view_mode_group.setExclusive(True)
        for label, mode in (
            ("Wireframe", "wireframe"),
            ("Solid", "solid"),
            ("Transparent", "transparent"),
        ):
            action = vm.addAction(label)
            action.setCheckable(True)
            if mode == "wireframe":
                action.setChecked(True)
            action.triggered.connect(lambda _checked=False, m=mode: self._set_view_mode(m))
            self._view_mode_group.addAction(action)

    def _connect_signals(self):
        self._tree.object_selected.connect(self._on_object_selected)
        self._tree.add_requested.connect(self._add_object)
        self._tree.delete_requested.connect(self._delete_object)
        self._properties.properties_changed.connect(self._on_properties_changed)
        self._ang_dist.distributions_changed.connect(self._on_distributions_changed)

    def _set_view_mode(self, mode: str):
        self._viewport.set_view_mode(mode)
        self.statusBar().showMessage(f"3D view mode: {mode}", 2000)

    def _clear_selected_object(self):
        self._selected_group = None
        self._selected_name = None
        self._viewport.clear_selection(redraw=False)

    def _new_project(self):
        if self._sim_thread and self._sim_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Stop the simulation first."); return
        self._project = Project()
        self._init_default_materials()
        merge_default_profiles(self._project)
        self._counter = {k: 0 for k in self._counter}
        self._last_save_path = None
        self._clear_selected_object()
        self._ang_dist.set_project(self._project)
        self._properties.clear_selection()
        self._heatmap.clear()
        self._viewport.clear_ray_paths()
        self._refresh_all()
        self.setWindowTitle("Blu Optical Simulation - Untitled")

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "JSON files (*.json);;All files (*)")
        if not path: return
        from backlight_sim.io.project_io import load_project
        try:
            self._project = load_project(path)
            merge_default_profiles(self._project)
            self._last_save_path = path
            self._counter = {k: 0 for k in self._counter}
            self._clear_selected_object()
            self._ang_dist.set_project(self._project)
            self._properties.clear_selection()
            self._heatmap.clear()
            self._viewport.clear_ray_paths()
            self._refresh_all()
            self.setWindowTitle(f"Blu Optical Simulation - {self._project.name}")
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", str(exc))

    def _save_project(self):
        if self._last_save_path:
            self._do_save(self._last_save_path)
        else:
            self._save_project_as()

    def _save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", f"{self._project.name}.json",
            "JSON files (*.json);;All files (*)")
        if path:
            self._last_save_path = path
            self._do_save(path)

    def _do_save(self, path):
        from backlight_sim.io.project_io import save_project
        try:
            save_project(self._project, path)
            self.statusBar().showMessage(f"Saved to {path}", 4000)
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))

    def _load_preset(self, factory):
        if QMessageBox.question(
            self, "Load Preset",
            "This will replace the current project. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes: return
        self._project = factory()
        merge_default_profiles(self._project)
        self._counter = {k: 0 for k in self._counter}
        self._last_save_path = None
        self._clear_selected_object()
        self._ang_dist.set_project(self._project)
        self._properties.clear_selection()
        self._heatmap.clear()
        self._viewport.clear_ray_paths()
        self._refresh_all()
        self.setWindowTitle(f"Blu Optical Simulation - {self._project.name}")

    def _open_geometry_builder(self):
        from backlight_sim.gui.geometry_builder import GeometryBuilderDialog
        dlg = GeometryBuilderDialog(self._project, self)
        if dlg.exec():
            self._clear_selected_object()
            self._properties.clear_selection()
            self._refresh_all()

    def _refresh_all(self):
        self._tree.refresh(self._project)
        self._viewport.set_selected(self._selected_group, self._selected_name, redraw=False)
        self._viewport.refresh(self._project)
        self._ang_dist.refresh()

    def _on_object_selected(self, group, name):
        self._selected_group = group
        self._selected_name = name
        self._viewport.set_selected(group, name)
        if group == "Sources":
            obj = next((s for s in self._project.sources if s.name == name), None)
            if obj:
                self._properties.show_source(obj, distribution_names=list(self._project.angular_distributions.keys()))
        elif group == "Surfaces":
            obj = next((s for s in self._project.surfaces if s.name == name), None)
            if obj: self._properties.show_surface(obj, list(self._project.materials.keys()))
        elif group == "Materials":
            obj = self._project.materials.get(name)
            if obj: self._properties.show_material(obj)
        elif group == "Detectors":
            obj = next((d for d in self._project.detectors if d.name == name), None)
            if obj: self._properties.show_detector(obj)

    def _on_properties_changed(self):
        self._refresh_all()

    def _on_distributions_changed(self):
        if self._selected_group == "Sources" and self._selected_name:
            src = next((s for s in self._project.sources if s.name == self._selected_name), None)
            if src:
                self._properties.show_source(src, distribution_names=list(self._project.angular_distributions.keys()))
        self._refresh_all()

    def _add_object(self, group):
        self._counter[group] += 1
        n = self._counter[group]
        if group == "Sources":
            self._project.sources.append(
                PointSource(f"Source_{n}", np.array([0.0, 0.0, 0.5]),
                            flux=100.0, direction=np.array([0.0, 0.0, 1.0]),
                            distribution="lambertian"))
        elif group == "Surfaces":
            self._project.surfaces.append(
                Rectangle.axis_aligned(f"Surface_{n}", [0, 0, 0], (10, 10), 2, 1.0))
        elif group == "Detectors":
            self._project.detectors.append(
                DetectorSurface.axis_aligned(f"Detector_{n}", [0, 0, 5], (10, 10), 2, 1.0))
        elif group == "Materials":
            mn = f"Material_{n}"
            self._project.materials[mn] = Material(mn)
        self._refresh_all()

    def _delete_object(self, group, name):
        if group == "Sources":
            self._project.sources = [s for s in self._project.sources if s.name != name]
        elif group == "Surfaces":
            self._project.surfaces = [s for s in self._project.surfaces if s.name != name]
        elif group == "Detectors":
            self._project.detectors = [d for d in self._project.detectors if d.name != name]
        elif group == "Materials":
            self._project.materials.pop(name, None)
        self._clear_selected_object()
        self._properties.clear_selection()
        self._refresh_all()

    def _show_settings(self):
        self._clear_selected_object()
        self._properties.show_settings(self._project.settings)
        self._refresh_all()

    def _run_simulation(self):
        if self._sim_thread and self._sim_thread.isRunning():
            self.statusBar().showMessage("Simulation already running."); return
        if not self._project.sources:
            QMessageBox.warning(self, "No Sources", "Add at least one light source."); return
        if not self._project.detectors:
            QMessageBox.warning(self, "No Detectors", "Add at least one detector."); return

        self._progress.setVisible(True)
        self._progress.setValue(0)
        self.statusBar().showMessage("Running simulation...")
        self._viewport.clear_ray_paths()
        self._run_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)

        self._sim_thread = SimulationThread(self._project)
        self._sim_thread.progress.connect(lambda f: self._progress.setValue(int(f * 100)))
        self._sim_thread.finished_sim.connect(self._on_sim_finished)
        self._sim_thread.start()

    def _cancel_simulation(self):
        if self._sim_thread and self._sim_thread.isRunning():
            self._sim_thread.cancel()
            self.statusBar().showMessage("Cancelling...")
            self._cancel_btn.setEnabled(False)

    def _on_sim_finished(self, result):
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self.statusBar().showMessage("Simulation complete.", 5000)
        self._heatmap.update_results(result.detectors)
        self._center_tabs.setCurrentWidget(self._heatmap)
        if result.ray_paths:
            self._viewport.show_ray_paths(result.ray_paths)
