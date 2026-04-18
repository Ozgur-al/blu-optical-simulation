"""Main application window."""

from __future__ import annotations

import datetime
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QMainWindow,
    QProgressBar, QStatusBar, QMessageBox, QFileDialog, QPushButton,
    QTextEdit, QLabel, QToolBar, QSplitter, QTabWidget, QWidget,
)
from PySide6.QtCore import Qt, QThread, QTimer, Signal, QSettings, QSize
from PySide6.QtGui import QActionGroup, QKeySequence, QAction, QShortcut, QUndoStack

from backlight_sim.gui.commands import (
    AddSourceCommand, DeleteSourceCommand,
    AddSurfaceCommand, DeleteSurfaceCommand,
    AddDetectorCommand, DeleteDetectorCommand,
    AddSphereDetectorCommand, DeleteSphereDetectorCommand,
    AddMaterialCommand, DeleteMaterialCommand,
    AddOpticalPropertiesCommand, DeleteOpticalPropertiesCommand,
    AddSolidBodyCommand, DeleteSolidBodyCommand,
)

from backlight_sim.core.project_model import Project
from backlight_sim.core.geometry import Rectangle
from backlight_sim.core.materials import Material
from backlight_sim.core.sources import PointSource
from backlight_sim.core.detectors import DetectorSurface, SphereDetector, SimulationResult
from backlight_sim.core.solid_body import SolidBox, SolidCylinder, SolidPrism
from backlight_sim.sim.tracer import RayTracer
from backlight_sim.gui.object_tree import ObjectTree
from backlight_sim.gui.properties_panel import PropertiesPanel
from backlight_sim.gui.viewport_3d import Viewport3D
from backlight_sim.gui.heatmap_panel import HeatmapPanel
from backlight_sim.gui.angular_distribution_panel import AngularDistributionPanel
from backlight_sim.gui.bsdf_panel import BSDFPanel
from backlight_sim.gui.far_field_panel import FarFieldPanel
from backlight_sim.gui.measurement_dialog import MeasurementDialog
from backlight_sim.gui.plot_tab import PlotTab
from backlight_sim.gui.convergence_tab import ConvergenceTab
from backlight_sim.gui.receiver_3d import Receiver3DWidget
from backlight_sim.gui.spectral_data_panel import SpectralDataPanel
from backlight_sim.io.angular_distributions import merge_default_profiles
# Native C++ acceleration is mandatory post Phase 02 Plan 03 (D-05/D-06):
# the Numba accel.py layer is gone and the C++ blu_tracer extension is
# always loaded by tracer.py at import time. If it fails to load, the
# RayTracer import raises RuntimeError — so reaching this module means
# native acceleration is active.
_CPP_ACTIVE = True


def _warmup_native_kernels() -> bool:
    """No-op warmup retained for UI timing parity.

    The C++ extension does not need LLVM-style warmup (it's AOT-compiled),
    but we keep this helper so the status-bar dispatch stays the same.
    """
    return True
from backlight_sim.gui.theme import ACCENT, TEXT_MUTED


class SimulationThread(QThread):
    progress       = Signal(float)
    convergence    = Signal(int, int, float)   # (src_idx, n_rays, cv_pct)
    partial_result = Signal(object)            # SimulationResult snapshot
    finished_sim   = Signal(object)

    def __init__(self, project: Project):
        super().__init__()
        self.tracer = RayTracer(project)

    def run(self):
        result = self.tracer.run(
            progress_callback=self.progress.emit,
            convergence_callback=self.convergence.emit,
            partial_result_callback=self.partial_result.emit,
        )
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
        self._counter = {"Sources": 0, "Surfaces": 0, "Materials": 0, "Optical Properties": 0, "Detectors": 0, "Sphere Detectors": 0, "Solid Bodies": 0}
        # Convergence plot data: src_idx -> (rays_list, cv_list)
        self._conv_data: dict[int, tuple[list, list]] = {}
        self._conv_curves: dict[int, pg.PlotDataItem] = {}
        self._conv_target_line = None
        self._last_save_path = None
        self._selected_group = None
        self._selected_name = None
        self._dirty = False
        self._variants: dict[str, "Project"] = {}
        self._variants_menu = None
        # Design history: list of (label, Project) — newest first, capped at 20
        self._history: list[tuple[str, "Project"]] = []
        self._history_menu = None

        # Undo/redo stack
        self._undo_stack = QUndoStack(self)
        self._pushing_property = 0  # counter for nested macro/push operations
        self._undo_stack.indexChanged.connect(self._on_undo_index_changed)

        # Debounce timer: coalesces rapid property edits into a single refresh
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(50)  # 50 ms debounce
        self._refresh_timer.timeout.connect(self._refresh_all)

        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_shortcuts()
        self._connect_signals()
        self._wire_property_undo()
        self._restore_layout()
        self._refresh_all()

        # Native C++ acceleration is mandatory (Plan 02-03); no warmup needed
        # for an AOT-compiled extension. Retain logging for UX parity.
        if _CPP_ACTIVE:
            _warmup_native_kernels()
            self._log("Native C++ acceleration active (blu_tracer extension loaded)")
        else:
            self._log("Native acceleration unavailable — running pure Python")

    def _init_default_materials(self):
        self._project.materials["default_reflector"] = Material(
            "default_reflector", "reflector", reflectance=0.9, absorption=0.1)
        self._project.materials["absorber"] = Material(
            "absorber", "absorber", reflectance=0.0, absorption=1.0)

    def _setup_ui(self):
        # ---- Create all panels ----
        self._viewport = Viewport3D()
        self._tree = ObjectTree()
        self._tree.setMinimumWidth(180)
        self._tree.setAccessibleName("Scene object tree")

        self._heatmap = HeatmapPanel()
        self._heatmap.set_project(self._project)

        self._ang_dist = AngularDistributionPanel()
        self._ang_dist.set_project(self._project)

        self._plot_tab = PlotTab()
        # Phase 4 UQ: cumulative-KPI + CI band convergence plot (distinct
        # from the existing live CV%-per-source convergence plot).
        self._convergence_tab = ConvergenceTab()
        self._receiver_3d = Receiver3DWidget()

        self._spectral_panel = SpectralDataPanel()
        self._spectral_panel.set_project(self._project)

        self._bsdf_panel = BSDFPanel()
        self._bsdf_panel.set_project(self._project)

        self._far_field_panel = FarFieldPanel()

        self._properties = PropertiesPanel()

        # ---- Central layout: left sidebar + center tabs ----
        # Left sidebar: scene tree (top) + properties (bottom)
        left_splitter = QSplitter(Qt.Orientation.Vertical)
        left_splitter.addWidget(self._tree)
        left_splitter.addWidget(self._properties)
        left_splitter.setStretchFactor(0, 1)
        left_splitter.setStretchFactor(1, 1)
        left_splitter.setSizes([400, 400])

        # Center: tabbed panel area
        self._center_tabs = QTabWidget()
        self._center_tabs.setTabsClosable(True)
        self._center_tabs.setMovable(True)
        self._center_tabs.tabCloseRequested.connect(self._on_tab_close)

        # Registry: maps tab title -> widget (for opening/focusing existing tabs)
        self._tab_registry: dict[str, QWidget] = {}

        # Default tabs: 3D View and Heatmap
        self._open_tab("3D View", self._viewport, closable=False)
        self._open_tab("Heatmap", self._heatmap, closable=False)

        # Main splitter: left sidebar | center tabs
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(self._center_tabs)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([320, 1120])

        self.setCentralWidget(main_splitter)

        # ---- Convergence plot (not docked — opened as a tab when needed) ----
        self._conv_plot = pg.PlotWidget()
        self._conv_plot.setLabel("left", "CV", units="%")
        self._conv_plot.setLabel("bottom", "Rays traced")
        self._conv_plot.setTitle("Convergence (CV% per source)")
        self._conv_plot.showGrid(x=True, y=True, alpha=0.3)
        self._conv_plot.addLegend()

        # ---- Log panel (opened as a tab when needed) ----
        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)

        # ---- Status bar ----
        status = QStatusBar()
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setFixedWidth(200)
        self._progress.setVisible(False)
        self._progress.setAccessibleName("Simulation progress")
        self._run_btn = QPushButton("Run")
        self._run_btn.setAccessibleName("Run simulation")
        self._run_btn.setToolTip("Run simulation (F5)")
        self._run_btn.clicked.connect(self._run_simulation)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setAccessibleName("Cancel simulation")
        self._cancel_btn.setToolTip("Cancel running simulation (Escape)")
        self._cancel_btn.clicked.connect(self._cancel_simulation)
        self._cancel_btn.setEnabled(False)

        # Native C++ acceleration status indicator (was JIT / Numba pre-02-03)
        self._jit_label = QLabel("C++: Active" if _CPP_ACTIVE else "C++: Off")
        self._jit_label.setAccessibleName("Native C++ acceleration status")
        if _CPP_ACTIVE:
            self._jit_label.setStyleSheet(f"color: {ACCENT}; font-weight: bold; padding: 0 6px;")
        else:
            self._jit_label.setStyleSheet(f"color: {TEXT_MUTED}; padding: 0 6px;")

        status.addWidget(self._jit_label)
        status.addPermanentWidget(self._run_btn)
        status.addPermanentWidget(self._cancel_btn)
        status.addPermanentWidget(self._progress)
        self.setStatusBar(status)

    # ------------------------------------------------------------------
    # Tab management
    # ------------------------------------------------------------------

    def _open_tab(self, title: str, widget: QWidget, closable: bool = True):
        """Open a panel as a tab, or focus it if already open."""
        if title in self._tab_registry:
            idx = self._center_tabs.indexOf(self._tab_registry[title])
            if idx >= 0:
                self._center_tabs.setCurrentIndex(idx)
                return
            # Widget was closed — re-add
            del self._tab_registry[title]
        idx = self._center_tabs.addTab(widget, title)
        self._tab_registry[title] = widget
        self._center_tabs.setCurrentIndex(idx)
        if not closable:
            # Remove close button for non-closable tabs
            self._center_tabs.tabBar().setTabButton(
                idx, self._center_tabs.tabBar().ButtonPosition.RightSide, None
            )

    def _on_tab_close(self, index: int):
        """Handle tab close — remove from registry but don't destroy widget."""
        widget = self._center_tabs.widget(index)
        # Find and remove from registry
        for title, w in list(self._tab_registry.items()):
            if w is widget:
                del self._tab_registry[title]
                break
        self._center_tabs.removeTab(index)

    # ------------------------------------------------------------------
    # Available panels for the Window menu
    # ------------------------------------------------------------------

    def _get_openable_panels(self) -> list[tuple[str, QWidget]]:
        """Return list of (title, widget) for all panels that can be opened as tabs."""
        return [
            ("3D View", self._viewport),
            ("Heatmap", self._heatmap),
            ("Plots", self._plot_tab),
            ("Convergence (UQ)", self._convergence_tab),
            ("Angular Dist.", self._ang_dist),
            ("Far-field", self._far_field_panel),
            ("3D Receiver", self._receiver_3d),
            ("Spectral Data", self._spectral_panel),
            ("BSDF", self._bsdf_panel),
            ("Convergence", self._conv_plot),
            ("Log", self._log_edit),
        ]

    def _setup_menu(self):
        mb = self.menuBar()

        fm = mb.addMenu("&File")
        self._new_action = fm.addAction("New Project", self._new_project)
        self._new_action.setShortcut(QKeySequence.StandardKey.New)
        self._new_action.setStatusTip("Create a new empty project")
        self._open_action = fm.addAction("Open...", self._open_project)
        self._open_action.setShortcut(QKeySequence.StandardKey.Open)
        self._open_action.setStatusTip("Open an existing project file")
        self._save_action = fm.addAction("Save", self._save_project)
        self._save_action.setShortcut(QKeySequence.StandardKey.Save)
        self._save_action.setStatusTip("Save the current project")
        act = fm.addAction("Save As...", self._save_project_as)
        act.setShortcut(QKeySequence.StandardKey.SaveAs)
        act.setStatusTip("Save the current project to a new file")
        fm.addSeparator()
        act = fm.addAction("Clone as Variant...", self._clone_as_variant)
        act.setStatusTip("Save a copy of the current project as a named variant for comparison")
        fm.addSeparator()
        act = fm.addAction("Exit", self.close)
        act.setShortcut(QKeySequence.StandardKey.Quit)
        act.setStatusTip("Exit the application")

        em = mb.addMenu("&Edit")
        undo_action = self._undo_stack.createUndoAction(self, "Undo")
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.setStatusTip("Undo the last action")
        redo_action = self._undo_stack.createRedoAction(self, "Redo")
        redo_action.setShortcut(QKeySequence("Ctrl+Y"))
        redo_action.setStatusTip("Redo the last undone action")
        em.addAction(undo_action)
        em.addAction(redo_action)
        self._undo_action = undo_action
        self._redo_action = redo_action

        pm = mb.addMenu("&Presets")
        from backlight_sim.io.presets import PRESETS
        for name, factory in PRESETS.items():
            pm.addAction(name, lambda f=factory: self._load_preset(f))

        am = mb.addMenu("&Add")
        am.addAction("Point Source",       lambda: self._add_object("Sources"))
        am.addAction("Surface",            lambda: self._add_object("Surfaces"))
        am.addAction("Detector",           lambda: self._add_object("Detectors"))
        am.addAction("Sphere Detector",    lambda: self._add_object("Sphere Detectors"))
        am.addAction("Material",           lambda: self._add_object("Materials"))
        am.addAction("Optical Properties", lambda: self._add_object("Optical Properties"))
        am.addAction("Cylinder",           lambda: self._add_object("Solid Bodies:cylinder"))
        am.addAction("Prism",              lambda: self._add_object("Solid Bodies:prism"))

        bm = mb.addMenu("&Build")
        act = bm.addAction("Geometry Builder...", self._open_geometry_builder)
        act.setStatusTip("Open the geometry builder to create cavity, LED grid, or LGP scene")

        self._variants_menu = mb.addMenu("&Variants")
        self._refresh_variants_menu()

        self._history_menu = mb.addMenu("&History")
        self._refresh_history_menu()

        sm = mb.addMenu("&Simulation")
        act = sm.addAction("Settings", self._show_settings)
        act.setStatusTip("Edit simulation settings (rays, bounces, convergence)")
        self._run_action = sm.addAction("Run", self._run_simulation)
        self._run_action.setShortcut(QKeySequence("F5"))
        self._run_action.setStatusTip("Run the ray tracing simulation (F5 or Ctrl+R)")
        self._cancel_action = sm.addAction("Cancel", self._cancel_simulation)
        self._cancel_action.setShortcut(QKeySequence("Escape"))
        self._cancel_action.setStatusTip("Cancel the running simulation")
        sm.addSeparator()
        act = sm.addAction("Parameter Sweep...", self._open_parameter_sweep)
        act.setStatusTip("Run a batch of simulations varying one or two parameters")

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

        vm.addSeparator()
        preset_menu = vm.addMenu("Preset Views")
        for label, preset in (
            ("XY+", "xy+"),
            ("XY-", "xy-"),
            ("YZ+", "yz+"),
            ("YZ-", "yz-"),
            ("XZ+", "xz+"),
            ("XZ-", "xz-"),
        ):
            preset_menu.addAction(label, lambda p=preset: self._set_view_preset(p))

        # Window menu — open panels as tabs
        wm = mb.addMenu("&Window")
        for title, widget in self._get_openable_panels():
            wm.addAction(title, lambda t=title, w=widget: self._open_tab(t, w))

        tm = mb.addMenu("&Tools")
        act = tm.addAction("Measure...", self._open_measure_dialog)
        act.setStatusTip("Measure point-to-point distances between objects")
        act = tm.addAction("LED Layout Editor...", self._open_led_layout)
        act.setStatusTip("Open a 2D top-view editor to drag and reposition LEDs")

    def _setup_toolbar(self):
        """Create the main toolbar with icon+text action buttons."""
        toolbar = QToolBar("Main")
        toolbar.setObjectName("main_toolbar")
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        # File actions (reuse actions created in _setup_menu)
        toolbar.addAction(self._new_action)
        toolbar.addAction(self._open_action)
        toolbar.addAction(self._save_action)
        toolbar.addSeparator()

        # Undo/Redo actions (created after _setup_menu is called)
        toolbar.addAction(self._undo_action)
        toolbar.addAction(self._redo_action)
        toolbar.addSeparator()

        # Simulation actions
        toolbar.addAction(self._run_action)
        toolbar.addAction(self._cancel_action)
        toolbar.addSeparator()

        # Quick-add buttons
        for label, group, tip in (
            ("Add LED",      "Sources",             "Add a new point light source"),
            ("Add Surface",  "Surfaces",            "Add a new reflective/diffuse surface"),
            ("Add Detector", "Detectors",           "Add a new planar detector"),
            ("Add SolidBox", "Solid Bodies:box",    "Add a solid box (LGP slab)"),
            ("Add Cylinder", "Solid Bodies:cylinder","Add a solid cylinder"),
            ("Add Prism",    "Solid Bodies:prism",  "Add a solid prism"),
        ):
            act = QAction(label, self)
            act.setToolTip(tip)
            act.triggered.connect(lambda _=False, g=group: self._add_object(g))
            toolbar.addAction(act)

    def _connect_signals(self):
        self._tree.object_selected.connect(self._on_object_selected)
        self._tree.multi_selected.connect(self._on_multi_selected)
        self._tree.add_requested.connect(self._add_object)
        self._tree.delete_requested.connect(self._delete_object)
        self._tree.duplicate_requested.connect(self._duplicate_object)
        self._properties.properties_changed.connect(self._on_properties_changed)
        self._ang_dist.distributions_changed.connect(self._on_distributions_changed)
        self._spectral_panel.spectral_data_changed.connect(self._mark_dirty)
        self._bsdf_panel.bsdf_changed.connect(self._on_bsdf_changed)

    def _setup_shortcuts(self):
        """Register application-wide keyboard shortcuts."""
        # Ctrl+R: secondary shortcut for run simulation (F5 is on the menu action)
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self._run_simulation)
        # Delete: delete selected object (with undo support)
        QShortcut(QKeySequence("Delete"), self).activated.connect(self._delete_selected)
        # Ctrl+D: duplicate selected object
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self._duplicate_selected)

    def _delete_selected(self):
        """Delete the currently selected object (Delete key shortcut)."""
        if self._selected_group and self._selected_name:
            name = self._selected_name
            self._delete_object(self._selected_group, name)
            self.statusBar().showMessage(f"Deleted {name} (Ctrl+Z to undo)", 4000)

    def _duplicate_selected(self):
        """Duplicate the currently selected object (Ctrl+D shortcut)."""
        if self._selected_group and self._selected_name:
            self._duplicate_object(self._selected_group, self._selected_name)

    def _duplicate_object(self, group, name):
        """Duplicate the named object with an incremented name."""
        import copy
        counter_key = group.split(":")[0] if ":" in group else group
        if counter_key not in self._counter:
            self._counter[counter_key] = 0
        self._counter[counter_key] += 1
        n = self._counter[counter_key]

        if group == "Sources":
            orig = next((s for s in self._project.sources if s.name == name), None)
            if orig is None:
                return
            dup = copy.deepcopy(orig)
            dup.name = f"Source_{n}"
            self._undo_stack.push(AddSourceCommand(self._project, dup, self._refresh_all))
        elif group == "Surfaces":
            orig = next((s for s in self._project.surfaces if s.name == name), None)
            if orig is None:
                return
            dup = copy.deepcopy(orig)
            dup.name = f"Surface_{n}"
            self._undo_stack.push(AddSurfaceCommand(self._project, dup, self._refresh_all))
        elif group == "Detectors":
            orig = next((d for d in self._project.detectors if d.name == name), None)
            if orig is None:
                return
            dup = copy.deepcopy(orig)
            dup.name = f"Detector_{n}"
            self._undo_stack.push(AddDetectorCommand(self._project, dup, self._refresh_all))
        elif group == "Sphere Detectors":
            orig = next((d for d in self._project.sphere_detectors if d.name == name), None)
            if orig is None:
                return
            dup = copy.deepcopy(orig)
            dup.name = f"SphereDetector_{n}"
            self._undo_stack.push(AddSphereDetectorCommand(self._project, dup, self._refresh_all))
        elif group == "Materials":
            orig = self._project.materials.get(name)
            if orig is None:
                return
            mn = f"Material_{n}"
            dup = copy.deepcopy(orig)
            dup.name = mn
            self._undo_stack.push(AddMaterialCommand(self._project, mn, dup, self._refresh_all))
        elif group == "Solid Bodies:box":
            orig = next((b for b in self._project.solid_bodies if b.name == name), None)
            if orig is None:
                return
            dup = copy.deepcopy(orig)
            dup.name = f"Box_{n}"
            self._undo_stack.push(AddSolidBodyCommand(self._project, dup, "box", self._refresh_all))
        elif group == "Solid Bodies:cylinder":
            lst = getattr(self._project, "solid_cylinders", [])
            orig = next((c for c in lst if c.name == name), None)
            if orig is None:
                return
            dup = copy.deepcopy(orig)
            dup.name = f"Cylinder_{n}"
            self._undo_stack.push(AddSolidBodyCommand(self._project, dup, "cylinder", self._refresh_all))
        elif group == "Solid Bodies:prism":
            lst = getattr(self._project, "solid_prisms", [])
            orig = next((p for p in lst if p.name == name), None)
            if orig is None:
                return
            dup = copy.deepcopy(orig)
            dup.name = f"Prism_{n}"
            self._undo_stack.push(AddSolidBodyCommand(self._project, dup, "prism", self._refresh_all))

    # ------------------------------------------------------------------
    # Layout persistence via QSettings
    # ------------------------------------------------------------------

    def _save_layout(self):
        """Persist window geometry and tab state to QSettings."""
        settings = QSettings("BluOptical", "BluSim")
        settings.setValue("geometry", self.saveGeometry())
        # Save open tab titles (order preserved)
        tab_titles = [self._center_tabs.tabText(i)
                      for i in range(self._center_tabs.count())]
        settings.setValue("open_tabs", tab_titles)
        settings.setValue("active_tab", self._center_tabs.currentIndex())

    def _restore_layout(self):
        """Restore window geometry and tab state from QSettings."""
        settings = QSettings("BluOptical", "BluSim")
        geom = settings.value("geometry")
        if geom is not None:
            self.restoreGeometry(geom)
        # Restore tabs
        saved_tabs = settings.value("open_tabs")
        if isinstance(saved_tabs, str):
            saved_tabs = [saved_tabs]  # Windows QSettings single-element list edge case
        if saved_tabs and isinstance(saved_tabs, list):
            panel_map = {title: widget for title, widget in self._get_openable_panels()}
            for title in saved_tabs:
                if title in panel_map and title not in self._tab_registry:
                    closable = title not in ("3D View", "Heatmap")
                    self._open_tab(title, panel_map[title], closable=closable)
            active = settings.value("active_tab")
            if active is not None:
                try:
                    self._center_tabs.setCurrentIndex(int(active))
                except (ValueError, TypeError):
                    pass

    # ------------------------------------------------------------------
    # Dirty-flag & unsaved-changes guard
    # ------------------------------------------------------------------

    def _mark_dirty(self):
        self._dirty = True

    def _maybe_save(self) -> bool:
        """Prompt to save if unsaved changes exist. Returns True if OK to proceed."""
        if not self._dirty:
            return True
        ret = QMessageBox.question(
            self, "Unsaved Changes",
            "The project has unsaved changes. Save before continuing?",
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel,
        )
        if ret == QMessageBox.StandardButton.Save:
            self._save_project()
            return not self._dirty  # False if save was cancelled/failed
        if ret == QMessageBox.StandardButton.Discard:
            return True
        return False  # Cancel

    def closeEvent(self, event):
        if self._sim_thread and self._sim_thread.isRunning():
            ret = QMessageBox.question(
                self, "Simulation Running",
                "A simulation is still running. Quit anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ret != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._sim_thread.cancel()
        if not self._maybe_save():
            event.ignore()
            return
        self._save_layout()
        event.accept()

    def _log(self, msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._log_edit.append(f"[{ts}] {msg}")

    def _set_view_mode(self, mode: str):
        self._viewport.set_view_mode(mode)
        self.statusBar().showMessage(f"3D view mode: {mode}", 2000)

    def _set_view_preset(self, preset: str):
        self._viewport.set_camera_preset(preset)
        self.statusBar().showMessage(f"Camera view: {preset}", 2000)

    def _clear_selected_object(self):
        self._selected_group = None
        self._selected_name = None
        self._viewport.clear_selection(redraw=False)

    def _selected_object_center(self):
        if self._selected_group == "Sources":
            obj = next((s for s in self._project.sources if s.name == self._selected_name), None)
            return obj.position if obj is not None else None
        if self._selected_group == "Surfaces":
            obj = next((s for s in self._project.surfaces if s.name == self._selected_name), None)
            return obj.center if obj is not None else None
        if self._selected_group == "Detectors":
            obj = next((d for d in self._project.detectors if d.name == self._selected_name), None)
            return obj.center if obj is not None else None
        return None

    def _open_measure_dialog(self):
        dlg = MeasurementDialog(self._selected_object_center, self)
        dlg.exec()

    def _open_led_layout(self):
        if not self._project.sources:
            QMessageBox.information(self, "No LEDs", "Add light sources first.")
            return
        from backlight_sim.gui.led_layout_editor import LEDLayoutEditor
        dlg = LEDLayoutEditor(self._project, self)
        dlg.exec()
        self._mark_dirty()
        self._refresh_all()

    def _new_project(self):
        if self._sim_thread and self._sim_thread.isRunning():
            QMessageBox.warning(self, "Busy", "Stop the simulation first."); return
        if not self._maybe_save():
            return
        self._dirty = False
        self._project = Project()
        self._init_default_materials()
        merge_default_profiles(self._project)
        self._counter = {k: 0 for k in self._counter}
        self._last_save_path = None
        self._undo_stack.clear()
        self._clear_selected_object()
        self._ang_dist.set_project(self._project)
        self._heatmap.set_project(self._project)
        self._spectral_panel.set_project(self._project)
        self._bsdf_panel.set_project(self._project)
        self._properties.clear_selection()
        self._heatmap.clear()
        self._plot_tab.clear()
        self._convergence_tab.clear()
        self._viewport.clear_ray_paths()
        self._refresh_all()
        self.setWindowTitle("Blu Optical Simulation - Untitled")

    def _open_project(self):
        if not self._maybe_save():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "JSON files (*.json);;All files (*)")
        if not path: return
        from backlight_sim.io.project_io import load_project
        try:
            self._project = load_project(path)
            merge_default_profiles(self._project)
            self._dirty = False
            self._last_save_path = path
            self._counter = {k: 0 for k in self._counter}
            self._undo_stack.clear()
            self._clear_selected_object()
            self._ang_dist.set_project(self._project)
            self._heatmap.set_project(self._project)
            self._spectral_panel.set_project(self._project)
            self._bsdf_panel.set_project(self._project)
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
            self._dirty = False
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
        self._dirty = False
        self._counter = {k: 0 for k in self._counter}
        self._last_save_path = None
        self._undo_stack.clear()
        self._clear_selected_object()
        self._ang_dist.set_project(self._project)
        self._heatmap.set_project(self._project)
        self._spectral_panel.set_project(self._project)
        self._bsdf_panel.set_project(self._project)
        self._properties.clear_selection()
        self._heatmap.clear()
        self._viewport.clear_ray_paths()
        self._refresh_all()
        self.setWindowTitle(f"Blu Optical Simulation - {self._project.name}")

    def _open_geometry_builder(self):
        from backlight_sim.gui.geometry_builder import GeometryBuilderDialog
        dlg = GeometryBuilderDialog(self._project, self)
        if dlg.exec():
            self._mark_dirty()
            self._clear_selected_object()
            self._properties.clear_selection()
            self._refresh_all()

    def _refresh_all(self):
        self._refresh_timer.stop()  # cancel pending debounced refresh
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
            if obj: self._properties.show_surface(obj, list(self._project.materials.keys()),
                                                   list(self._project.optical_properties.keys()))
        elif group == "Materials":
            obj = self._project.materials.get(name)
            if obj: self._properties.show_material(obj, project=self._project)
        elif group == "Optical Properties":
            obj = self._project.optical_properties.get(name)
            if obj:
                bsdf_names = list(getattr(self._project, "bsdf_profiles", {}).keys())
                self._properties.show_optical_properties(obj, bsdf_names=bsdf_names)
        elif group == "Detectors":
            obj = next((d for d in self._project.detectors if d.name == name), None)
            if obj: self._properties.show_detector(obj)
        elif group == "Sphere Detectors":
            obj = next((d for d in self._project.sphere_detectors if d.name == name), None)
            if obj: self._properties.show_sphere_detector(obj)
        elif group == "Solid Bodies" and "::" in name:
            # Face node: "BodyName::face_id" — determine parent body type
            body_name, face_id = name.split("::", 1)
            # Check all solid body types for a matching name
            box = next((b for b in self._project.solid_bodies if b.name == body_name), None)
            if box:
                self._properties.show_face(box, face_id, list(self._project.optical_properties.keys()))
            # Cylinder/prism face nodes don't have per-face property editors yet — skip
        elif group == "Solid Bodies:box":
            box = next((b for b in self._project.solid_bodies if b.name == name), None)
            if box:
                self._properties.show_solid_box(box, list(self._project.materials.keys()))
        elif group == "Solid Bodies:cylinder":
            cyl = next((c for c in getattr(self._project, "solid_cylinders", []) if c.name == name), None)
            if cyl:
                self._properties.show_solid_cylinder(cyl, list(self._project.materials.keys()))
        elif group == "Solid Bodies:prism":
            prism = next((p for p in getattr(self._project, "solid_prisms", []) if p.name == name), None)
            if prism:
                self._properties.show_solid_prism(prism, list(self._project.materials.keys()))

    def _on_multi_selected(self, group: str, names: list):
        """Handle Ctrl+click multi-selection of objects in the same group."""
        objects = []
        if group == "Sources":
            objects = [s for s in self._project.sources if s.name in names]
        elif group == "Surfaces":
            objects = [s for s in self._project.surfaces if s.name in names]
        elif group == "Materials":
            objects = [self._project.materials[n] for n in names if n in self._project.materials]
        elif group == "Detectors":
            objects = [d for d in self._project.detectors if d.name in names]
        if objects:
            self._properties.show_batch(
                group, objects,
                distribution_names=list(self._project.angular_distributions.keys()),
                mat_names=list(self._project.materials.keys()),
            )

    def _on_properties_changed(self):
        self._mark_dirty()
        self._refresh_timer.start()  # debounced — coalesces rapid edits

    # ── Property undo infrastructure ─────────────────────────────────────

    def _wire_property_undo(self):
        """Give the properties panel access to the undo stack."""
        self._properties.set_undo_stack(
            self._undo_stack,
            self._push_property_command,
            self._begin_property_macro,
            self._end_property_macro,
            self._refresh_for_property_edit,
        )

    def _push_property_command(self, cmd):
        """Push a property command with flag guard to suppress form reload."""
        self._pushing_property += 1
        self._undo_stack.push(cmd)
        self._pushing_property -= 1

    def _begin_property_macro(self, text):
        self._pushing_property += 1
        self._undo_stack.beginMacro(text)

    def _end_property_macro(self):
        self._undo_stack.endMacro()
        self._pushing_property -= 1

    def _refresh_for_property_edit(self):
        """Lightweight refresh used as command callback — starts debounce timer."""
        self._refresh_timer.start()

    def _on_undo_index_changed(self, _idx):
        self._mark_dirty()
        if self._pushing_property == 0:
            # Undo/redo happened externally (Ctrl+Z/Y) — reload the form
            self._reload_current_form()
            self._refresh_timer.start()

    def _reload_current_form(self):
        """Re-populate the properties panel for the current selection."""
        if self._selected_group and self._selected_name:
            self._on_object_selected(self._selected_group, self._selected_name)
        elif self._properties.currentWidget() is self._properties._settingsform:
            self._properties.show_settings(self._project.settings)

    # ─────────────────────────────────────────────────────────────────────

    def _on_bsdf_changed(self):
        """Called when a BSDF profile is imported or deleted."""
        self._mark_dirty()
        # Refresh BSDF dropdown in properties panel if an optical property is selected
        if self._selected_group == "Optical Properties" and self._selected_name:
            op = self._project.optical_properties.get(self._selected_name)
            if op:
                bsdf_names = list(getattr(self._project, "bsdf_profiles", {}).keys())
                self._properties.show_optical_properties(op, bsdf_names=bsdf_names)
        self._refresh_all()

    def _on_distributions_changed(self):
        self._mark_dirty()
        if self._selected_group == "Sources" and self._selected_name:
            src = next((s for s in self._project.sources if s.name == self._selected_name), None)
            if src:
                self._properties.show_source(src, distribution_names=list(self._project.angular_distributions.keys()))
        self._refresh_all()

    def _unique_name(self, base: str, existing: set[str]) -> str:
        """Return *base* if unique, otherwise append _2, _3, ... until unique."""
        if base not in existing:
            return base
        i = 2
        while f"{base}_{i}" in existing:
            i += 1
        return f"{base}_{i}"

    def _add_object(self, group):
        # Normalize legacy group key for counter lookup
        counter_key = group.split(":")[0] if ":" in group else group
        if counter_key not in self._counter:
            self._counter[counter_key] = 0
        self._counter[counter_key] += 1
        n = self._counter[counter_key]
        default_mat = next(iter(self._project.materials), "pmma")

        if group == "Sources":
            existing = {s.name for s in self._project.sources}
            name = self._unique_name(f"Source_{n}", existing)
            src = PointSource(name, np.array([0.0, 0.0, 0.5]),
                              flux=100.0, direction=np.array([0.0, 0.0, 1.0]),
                              distribution="lambertian")
            self._undo_stack.push(AddSourceCommand(self._project, src, self._refresh_all))
        elif group == "Surfaces":
            existing = {s.name for s in self._project.surfaces}
            name = self._unique_name(f"Surface_{n}", existing)
            surf = Rectangle.axis_aligned(name, [0, 0, 0], (10, 10), 2, 1.0)
            self._undo_stack.push(AddSurfaceCommand(self._project, surf, self._refresh_all))
        elif group == "Detectors":
            existing = {d.name for d in self._project.detectors}
            name = self._unique_name(f"Detector_{n}", existing)
            det = DetectorSurface.axis_aligned(name, [0, 0, 5], (10, 10), 2, 1.0)
            self._undo_stack.push(AddDetectorCommand(self._project, det, self._refresh_all))
        elif group == "Materials":
            existing = set(self._project.materials.keys())
            mn = self._unique_name(f"Material_{n}", existing)
            mat = Material(mn)
            self._undo_stack.push(AddMaterialCommand(self._project, mn, mat, self._refresh_all))
        elif group == "Sphere Detectors":
            existing = {d.name for d in self._project.sphere_detectors}
            name = self._unique_name(f"SphereDetector_{n}", existing)
            sd = SphereDetector(name, np.array([0.0, 0.0, 0.0]), radius=20.0)
            self._undo_stack.push(AddSphereDetectorCommand(self._project, sd, self._refresh_all))
        elif group == "Optical Properties":
            from backlight_sim.core.materials import OpticalProperties
            existing = set(self._project.optical_properties.keys())
            on = self._unique_name(f"OptProp_{n}", existing)
            op = OpticalProperties(on)
            self._undo_stack.push(AddOpticalPropertiesCommand(self._project, on, op, self._refresh_all))
        elif group in ("Solid Bodies", "Solid Bodies:box"):
            existing = {b.name for b in self._project.solid_bodies}
            box_name = self._unique_name(f"Box_{n}", existing)
            box = SolidBox(
                name=box_name,
                center=np.array([0.0, 0.0, 0.0]),
                dimensions=(50.0, 30.0, 3.0),
                material_name=default_mat,
            )
            self._undo_stack.push(AddSolidBodyCommand(self._project, box, "box", self._refresh_all))
        elif group == "Solid Bodies:cylinder":
            if not hasattr(self._project, "solid_cylinders"):
                self._project.solid_cylinders = []
            existing = {c.name for c in self._project.solid_cylinders}
            name = self._unique_name(f"Cylinder_{n}", existing)
            cyl = SolidCylinder(
                name=name,
                center=np.array([0.0, 0.0, 0.0]),
                axis=np.array([0.0, 0.0, 1.0]),
                radius=5.0,
                length=10.0,
                material_name=default_mat,
            )
            self._undo_stack.push(AddSolidBodyCommand(self._project, cyl, "cylinder", self._refresh_all))
        elif group == "Solid Bodies:prism":
            if not hasattr(self._project, "solid_prisms"):
                self._project.solid_prisms = []
            existing = {p.name for p in self._project.solid_prisms}
            name = self._unique_name(f"Prism_{n}", existing)
            prism = SolidPrism(
                name=name,
                center=np.array([0.0, 0.0, 0.0]),
                axis=np.array([0.0, 0.0, 1.0]),
                n_sides=6,
                circumscribed_radius=5.0,
                length=10.0,
                material_name=default_mat,
            )
            self._undo_stack.push(AddSolidBodyCommand(self._project, prism, "prism", self._refresh_all))

    def _delete_object(self, group, name):
        # Clear selection first regardless of what we delete
        self._clear_selected_object()
        self._properties.clear_selection()

        if group == "Sources":
            obj = next((s for s in self._project.sources if s.name == name), None)
            if obj is None:
                return
            idx = self._project.sources.index(obj)
            self._undo_stack.push(DeleteSourceCommand(self._project, obj, idx, self._refresh_all))
        elif group == "Surfaces":
            obj = next((s for s in self._project.surfaces if s.name == name), None)
            if obj is None:
                return
            idx = self._project.surfaces.index(obj)
            self._undo_stack.push(DeleteSurfaceCommand(self._project, obj, idx, self._refresh_all))
        elif group == "Detectors":
            obj = next((d for d in self._project.detectors if d.name == name), None)
            if obj is None:
                return
            idx = self._project.detectors.index(obj)
            self._undo_stack.push(DeleteDetectorCommand(self._project, obj, idx, self._refresh_all))
        elif group == "Sphere Detectors":
            obj = next((d for d in self._project.sphere_detectors if d.name == name), None)
            if obj is None:
                return
            idx = self._project.sphere_detectors.index(obj)
            self._undo_stack.push(DeleteSphereDetectorCommand(self._project, obj, idx, self._refresh_all))
        elif group == "Materials":
            obj = self._project.materials.get(name)
            if obj is None:
                return
            self._undo_stack.push(DeleteMaterialCommand(self._project, name, obj, self._refresh_all))
        elif group == "Optical Properties":
            obj = self._project.optical_properties.get(name)
            if obj is None:
                return
            self._undo_stack.push(DeleteOpticalPropertiesCommand(self._project, name, obj, self._refresh_all))
        elif group == "Solid Bodies" and "::" in name:
            # Face node — clear the face optics override (not undoable for now)
            box_name, face_id = name.split("::", 1)
            box = next((b for b in self._project.solid_bodies if b.name == box_name), None)
            if box:
                box.face_optics.pop(face_id, None)
            self._mark_dirty()
            self._refresh_all()
        elif group == "Solid Bodies:box":
            obj = next((b for b in self._project.solid_bodies if b.name == name), None)
            if obj is None:
                return
            idx = self._project.solid_bodies.index(obj)
            self._undo_stack.push(DeleteSolidBodyCommand(self._project, obj, "box", idx, self._refresh_all))
        elif group == "Solid Bodies:cylinder":
            lst = getattr(self._project, "solid_cylinders", [])
            obj = next((c for c in lst if c.name == name), None)
            if obj is None:
                return
            idx = lst.index(obj)
            self._undo_stack.push(DeleteSolidBodyCommand(self._project, obj, "cylinder", idx, self._refresh_all))
        elif group == "Solid Bodies:prism":
            lst = getattr(self._project, "solid_prisms", [])
            obj = next((p for p in lst if p.name == name), None)
            if obj is None:
                return
            idx = lst.index(obj)
            self._undo_stack.push(DeleteSolidBodyCommand(self._project, obj, "prism", idx, self._refresh_all))

    # ------------------------------------------------------------------
    # Variant management (#6)
    # ------------------------------------------------------------------

    def _clone_as_variant(self):
        import copy
        from PySide6.QtWidgets import QInputDialog
        default = f"{self._project.name}_v{len(self._variants) + 1}"
        name, ok = QInputDialog.getText(
            self, "Clone as Variant", "Variant name:", text=default)
        if not ok or not name.strip():
            return
        name = name.strip()
        self._variants[name] = copy.deepcopy(self._project)
        self._refresh_variants_menu()
        self._log(f"Variant saved: '{name}'")

    def _refresh_variants_menu(self):
        self._variants_menu.clear()
        if not self._variants:
            a = self._variants_menu.addAction("No variants saved")
            a.setEnabled(False)
        else:
            for vname in self._variants:
                self._variants_menu.addAction(
                    vname, lambda _=False, n=vname: self._load_variant(n))
            self._variants_menu.addSeparator()
            compare_menu = self._variants_menu.addMenu("Compare with...")
            for vname in self._variants:
                compare_menu.addAction(
                    vname, lambda _=False, n=vname: self._compare_variant(n))
            self._variants_menu.addSeparator()
            self._variants_menu.addAction("Clear All Variants", self._clear_variants)

    def _load_variant(self, name: str):
        import copy
        v = self._variants.get(name)
        if v is None:
            return
        if QMessageBox.question(
            self, "Load Variant",
            f"Load variant '{name}'?\nUnsaved changes to the current project will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._project = copy.deepcopy(v)
        merge_default_profiles(self._project)
        self._dirty = False
        self._counter = {k: 0 for k in self._counter}
        self._last_save_path = None
        self._undo_stack.clear()
        self._clear_selected_object()
        self._ang_dist.set_project(self._project)
        self._heatmap.set_project(self._project)
        self._spectral_panel.set_project(self._project)
        self._bsdf_panel.set_project(self._project)
        self._properties.clear_selection()
        self._heatmap.clear()
        self._viewport.clear_ray_paths()
        self._refresh_all()
        self.setWindowTitle(f"Blu Optical Simulation - {self._project.name} [variant: {name}]")
        self._log(f"Loaded variant: '{name}'")

    def _compare_variant(self, name: str):
        v = self._variants.get(name)
        if v is None:
            return
        from backlight_sim.gui.comparison_dialog import ComparisonDialog
        dlg = ComparisonDialog(self._project, name, v, self)
        dlg.exec()

    def _clear_variants(self):
        self._variants.clear()
        self._refresh_variants_menu()

    # ------------------------------------------------------------------
    # Design history auto-snapshots (#7)
    # ------------------------------------------------------------------

    _MAX_HISTORY = 20

    def _snapshot_history(self):
        """Save a timestamped deep-copy of the current project to history."""
        import copy
        from datetime import datetime
        label = datetime.now().strftime("%H:%M:%S")
        self._history.insert(0, (label, copy.deepcopy(self._project)))
        if len(self._history) > self._MAX_HISTORY:
            self._history = self._history[: self._MAX_HISTORY]
        self._refresh_history_menu()

    def _refresh_history_menu(self):
        self._history_menu.clear()
        if not self._history:
            a = self._history_menu.addAction("No history yet")
            a.setEnabled(False)
        else:
            for label, _ in self._history:
                self._history_menu.addAction(
                    label, lambda _=False, lbl=label: self._restore_history(lbl))
            self._history_menu.addSeparator()
            self._history_menu.addAction("Clear History", self._clear_history)

    def _restore_history(self, label: str):
        import copy
        snap = next((p for lbl, p in self._history if lbl == label), None)
        if snap is None:
            return
        if QMessageBox.question(
            self, "Restore from History",
            f"Restore project snapshot '{label}'?\nCurrent unsaved changes will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._project = copy.deepcopy(snap)
        merge_default_profiles(self._project)
        self._dirty = False
        self._counter = {k: 0 for k in self._counter}
        self._last_save_path = None
        self._undo_stack.clear()
        self._clear_selected_object()
        self._ang_dist.set_project(self._project)
        self._heatmap.set_project(self._project)
        self._spectral_panel.set_project(self._project)
        self._bsdf_panel.set_project(self._project)
        self._properties.clear_selection()
        self._heatmap.clear()
        self._viewport.clear_ray_paths()
        self._refresh_all()
        self.setWindowTitle(f"Blu Optical Simulation - {self._project.name} [history: {label}]")
        self._log(f"Restored history snapshot: {label}")

    def _clear_history(self):
        self._history.clear()
        self._refresh_history_menu()

    # ------------------------------------------------------------------

    def _open_parameter_sweep(self):
        from backlight_sim.gui.parameter_sweep_dialog import ParameterSweepDialog
        dlg = ParameterSweepDialog(self._project, self)
        dlg.exec()

    def _show_settings(self):
        self._clear_selected_object()
        self._properties.show_settings(self._project.settings)
        self._refresh_all()

    def _run_simulation(self):
        if not self._run_btn.isEnabled():
            return
        if self._sim_thread and self._sim_thread.isRunning():
            self.statusBar().showMessage("Simulation already running."); return
        if not self._project.sources:
            QMessageBox.warning(self, "No Sources", "Add at least one light source."); return
        if not any(s.enabled for s in self._project.sources):
            QMessageBox.warning(self, "No Active Sources", "Enable at least one light source."); return
        if not self._project.detectors and not self._project.sphere_detectors:
            QMessageBox.warning(self, "No Detectors", "Add at least one detector."); return

        self._progress.setVisible(True)
        self._progress.setValue(0)
        self.statusBar().showMessage("Running simulation...")
        self._viewport.clear_ray_paths()
        self._run_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)

        s = self._project.settings
        self._log(
            f"Simulation started — {len(self._project.sources)} source(s), "
            f"{len(self._project.surfaces)} surface(s), "
            f"{len(self._project.detectors)} detector(s) | "
            f"{s.rays_per_source:,} rays/src, {s.max_bounces} max bounces"
        )

        # Reset convergence plot
        self._conv_data.clear()
        self._conv_curves.clear()
        self._conv_plot.clear()
        self._conv_plot.addLegend()
        cv_target = getattr(self._project.settings, "convergence_cv_target", 2.0)
        self._conv_target_line = self._conv_plot.addLine(
            y=cv_target, pen=pg.mkPen("r", style=pg.QtCore.Qt.PenStyle.DashLine)
        )

        self._sim_thread = SimulationThread(self._project)
        self._sim_thread.progress.connect(lambda f: self._progress.setValue(int(f * 100)))
        self._sim_thread.convergence.connect(self._on_convergence_update)
        self._sim_thread.partial_result.connect(self._on_partial_result)
        self._sim_thread.finished_sim.connect(self._on_sim_finished)
        self._sim_thread.start()

        # Inform user if live preview is disabled due to multiprocessing
        if self._project.settings.use_multiprocessing:
            self._log("Live preview disabled in multiprocessing mode")

    def _cancel_simulation(self):
        if self._sim_thread and self._sim_thread.isRunning():
            self._sim_thread.cancel()
            self.statusBar().showMessage("Cancelling...")
            self._cancel_btn.setEnabled(False)
            self._log("Simulation cancelled.")

    def _on_partial_result(self, result):
        """Update heatmap with partial simulation results for live preview."""
        self._heatmap.update_results(result)

    def _on_sim_finished(self, result):
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self.statusBar().showMessage("Simulation complete.", 5000)
        self._heatmap.update_results(result)
        self._plot_tab.update_results(result)
        self._convergence_tab.update_from_result(result)
        self._receiver_3d.update_results(result)
        self._spectral_panel.update_from_result(result)  # Chromaticity scatter

        # Update far-field panel if any far-field sphere detector has results
        showed_farfield = False
        for sd in self._project.sphere_detectors:
            if getattr(sd, "mode", "near_field") == "far_field":
                sd_result = result.sphere_detectors.get(sd.name) if hasattr(result, "sphere_detectors") else None
                if sd_result is not None and getattr(sd_result, "candela_grid", None) is not None:
                    self._far_field_panel.show_result(sd, sd_result)
                    self._open_tab("Far-field", self._far_field_panel)
                    self._viewport.clear_farfield_lobe()
                    self._viewport.refresh(self._project)
                    try:
                        self._viewport._draw_farfield_lobe(sd, sd_result)
                    except Exception as exc:
                        self._log(f"Far-field lobe rendering failed: {exc}")
                    showed_farfield = True
                    break

        # Focus the heatmap tab only when no far-field results were shown
        if not showed_farfield:
            self._open_tab("Heatmap", self._heatmap, closable=False)
        if result.ray_paths:
            self._viewport.show_ray_paths(result.ray_paths)

        # Log summary
        det_flux = sum(dr.total_flux for dr in result.detectors.values())
        if result.total_emitted_flux > 0:
            eff = det_flux / result.total_emitted_flux * 100.0
            esc = result.escaped_flux / result.total_emitted_flux * 100.0
            self._log(
                f"Simulation complete — efficiency: {eff:.1f} %, "
                f"escaped: {esc:.1f} %, "
                f"absorbed: {max(0, 100 - eff - esc):.1f} %"
            )
        else:
            self._log("Simulation complete.")

        self._snapshot_history()

    def _on_convergence_update(self, src_idx: int, n_rays: int, cv_pct: float):
        """Update the live convergence plot with a new data point from the tracer."""
        if src_idx not in self._conv_data:
            self._conv_data[src_idx] = ([], [])
            src_name = (
                self._project.sources[src_idx].name
                if src_idx < len(self._project.sources)
                else f"Source {src_idx}"
            )
            colors = ["y", "c", "g", "m", "w", "r", "b"]
            color = colors[src_idx % len(colors)]
            curve = self._conv_plot.plot(
                [], [], pen=pg.mkPen(color, width=1.5), name=src_name
            )
            self._conv_curves[src_idx] = curve
            # Open convergence tab on first data point
            if "Convergence" not in self._tab_registry:
                self._open_tab("Convergence", self._conv_plot)

        rays_list, cv_list = self._conv_data[src_idx]
        rays_list.append(n_rays)
        cv_list.append(cv_pct)
        self._conv_curves[src_idx].setData(rays_list, cv_list)

