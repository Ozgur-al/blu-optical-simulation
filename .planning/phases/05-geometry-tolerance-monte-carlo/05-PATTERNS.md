# Phase 5: Geometry Tolerance Monte Carlo — Pattern Map

**Mapped:** 2026-04-19
**Files analyzed:** 8 new/modified files
**Analogs found:** 8 / 8

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backlight_sim/core/sources.py` | model | CRUD | `backlight_sim/core/sources.py` (self — extend existing dataclass) | exact |
| `backlight_sim/core/project_model.py` | model | CRUD | `backlight_sim/core/project_model.py` (self — extend existing dataclasses) | exact |
| `backlight_sim/sim/ensemble.py` | service | batch | `backlight_sim/gui/parameter_sweep_dialog.py` (_SweepThread loop logic) | role-match |
| `backlight_sim/io/project_io.py` | utility | CRUD | `backlight_sim/io/project_io.py` (self — extend existing round-trip) | exact |
| `backlight_sim/gui/ensemble_dialog.py` | component | event-driven | `backlight_sim/gui/parameter_sweep_dialog.py` | exact |
| `backlight_sim/gui/properties_panel.py` | component | request-response | `backlight_sim/gui/properties_panel.py` (self — SourceForm Thermal/Binning section) | exact |
| `backlight_sim/gui/main_window.py` | component | request-response | `backlight_sim/gui/main_window.py` (self — Simulation menu) | exact |
| `backlight_sim/tests/test_ensemble.py` | test | batch | `backlight_sim/tests/test_uq.py` | role-match |

---

## Pattern Assignments

### `backlight_sim/core/sources.py` (model, CRUD — add `position_sigma_mm`)

**Analog:** `backlight_sim/core/sources.py` (self extension)

**Existing pattern to replicate** (lines 1-42 — entire file read):

```python
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class PointSource:
    """A point light source in 3D space."""

    name: str
    position: np.ndarray  # (3,)
    flux: float = 100.0
    direction: np.ndarray = None
    distribution: str = "isotropic"
    enabled: bool = True
    flux_tolerance: float = 0.0  # ±% bin tolerance (e.g. 10 = ±10%)
    current_mA: float = 0.0
    flux_per_mA: float = 0.0
    thermal_derate: float = 1.0
    color_rgb: tuple[float, float, float] = (1.0, 1.0, 1.0)
    spd: str = "white"
```

**New field to add** — insert after `flux_tolerance`, mirroring its inline-field pattern:

```python
    # Phase 5 — per-source position jitter override (0 = use project-level default)
    position_sigma_mm: float = 0.0  # isotropic 3D σ in mm (Gaussian or uniform per project setting)
```

**Instruction:** Append `position_sigma_mm: float = 0.0` to the `PointSource` dataclass after `flux_tolerance`. No new methods required. No `__post_init__` change needed (scalar field, no numpy conversion).

---

### `backlight_sim/core/project_model.py` (model, CRUD — add 2 fields)

**Analog:** `backlight_sim/core/project_model.py` (self extension)

**Existing `SimulationSettings` pattern** (lines 13-35 — entire class):

```python
@dataclass
class SimulationSettings:
    rays_per_source: int = 10_000
    max_bounces: int = 50
    energy_threshold: float = 0.001
    random_seed: int = 42
    distance_unit: str = "mm"
    flux_unit: str = "lm"
    angle_unit: str = "deg"
    record_ray_paths: int = 200
    use_multiprocessing: bool = False
    adaptive_sampling: bool = True
    convergence_cv_target: float = 2.0
    check_interval: int = 1000
    uq_batches: int = 10
    uq_include_spectral: bool = True
```

**New fields to add** — append to `SimulationSettings`:

```python
    # Phase 5 — ensemble tolerance defaults
    source_position_sigma_mm: float = 0.0       # project-level isotropic σ in mm
    source_position_distribution: str = "gaussian"  # "gaussian" | "uniform"
```

**Existing `Project` dataclass pattern** (lines 38-59):

```python
@dataclass
class Project:
    name: str = "Untitled"
    sources: list[PointSource] = field(default_factory=list)
    surfaces: list[Rectangle] = field(default_factory=list)
    materials: dict[str, Material] = field(default_factory=dict)
    optical_properties: dict[str, OpticalProperties] = field(default_factory=dict)
    detectors: list[DetectorSurface] = field(default_factory=list)
    ...
    settings: SimulationSettings = field(default_factory=SimulationSettings)
```

**New field to add** — append to `Project`:

```python
    # Phase 5 — cavity build recipe for ensemble realization (empty = no cavity tolerances)
    # Schema: {"width": float, "height": float, "depth": float,
    #          "wall_angle_x_deg": float, "wall_angle_y_deg": float,
    #          "floor_material": str, "wall_material": str,
    #          "depth_sigma_mm": float, "wall_angle_x_sigma_deg": float,
    #          "wall_angle_y_sigma_deg": float,
    #          "depth_distribution": str, "wall_angle_distribution": str}
    cavity_recipe: dict = field(default_factory=dict)
```

---

### `backlight_sim/sim/ensemble.py` (service, batch — NEW FILE)

**Analog:** `backlight_sim/gui/parameter_sweep_dialog.py` — the `_SweepThread.run()` loop at lines 121-130 and `_apply_param()` at lines 85-104 form the structural template for the headless ensemble service.

**Import pattern** (from sweep dialog lines 1-26, adapted for headless sim layer):

```python
from __future__ import annotations

import copy
from typing import Iterator

import numpy as np

from backlight_sim.core.project_model import Project
from backlight_sim.io.geometry_builder import build_cavity
```

**No PySide6/GUI imports** — this is `sim/` layer; identical constraint to `sim/tracer.py`.

**Core jitter pattern** — derived from the flux_tolerance precedent in `tracer.py` and the sweep dialog's `copy.deepcopy` + mutate pattern (sweep dialog lines 121-130):

```python
def apply_jitter(
    project: Project,
    rng: np.random.Generator,
    param_overrides: dict | None = None,
) -> Project:
    """Return a deep-copy of project with all tolerance jitters applied.

    Jitter is applied to src.position IN-PLACE on the deep-copy so that
    _serialize_project() picks up the jittered coordinates (pre-serialization
    pattern; mirrors flux_tolerance handling in tracer.py).
    """
    p = copy.deepcopy(project)
    sigma_default = p.settings.source_position_sigma_mm
    dist = p.settings.source_position_distribution

    for src in p.sources:
        if not src.enabled:
            continue
        sigma = src.position_sigma_mm if src.position_sigma_mm > 0 else sigma_default
        if sigma > 0:
            if dist == "uniform":
                # Scale so RMS = sigma: uniform on [-sqrt(3)*sigma, sqrt(3)*sigma]
                dx, dy, dz = rng.uniform(-sigma * np.sqrt(3), sigma * np.sqrt(3), 3)
            else:  # gaussian
                dx, dy, dz = rng.normal(0.0, sigma, 3)
            src.position = src.position + np.array([dx, dy, dz])
    ...
```

**Cavity jitter sub-pattern:**

```python
def _jitter_cavity(p: Project, rng: np.random.Generator, overrides: dict | None = None) -> None:
    """Re-invoke build_cavity() on the cloned project with jittered recipe args."""
    recipe = dict(p.cavity_recipe)  # shallow copy; all values are scalars/strings
    # Apply depth jitter
    depth_sigma = recipe.get("depth_sigma_mm", 0.0)
    if depth_sigma > 0:
        dist = recipe.get("depth_distribution", "gaussian")
        recipe["depth"] = recipe["depth"] + (
            rng.normal(0.0, depth_sigma) if dist == "gaussian"
            else rng.uniform(-depth_sigma * np.sqrt(3), depth_sigma * np.sqrt(3))
        )
    # Apply wall angle jitter (both axes independently)
    for axis in ("x", "y"):
        key_sigma = f"wall_angle_{axis}_sigma_deg"
        key_val = f"wall_angle_{axis}_deg"
        sigma = recipe.get(key_sigma, 0.0)
        if sigma > 0:
            dist = recipe.get("wall_angle_distribution", "gaussian")
            recipe[key_val] = recipe.get(key_val, 0.0) + (
                rng.normal(0.0, sigma) if dist == "gaussian"
                else rng.uniform(-sigma * np.sqrt(3), sigma * np.sqrt(3))
            )
    build_cavity(
        p,
        width=recipe["width"],
        height=recipe["height"],
        depth=recipe["depth"],
        wall_angle_x_deg=recipe.get("wall_angle_x_deg", 0.0),
        wall_angle_y_deg=recipe.get("wall_angle_y_deg", 0.0),
        floor_material=recipe.get("floor_material", "default_reflector"),
        wall_material=recipe.get("wall_material", "default_reflector"),
        replace_existing=True,
    )
```

**OAT sensitivity pattern** (from RESEARCH.md Pattern 4, matches project conventions):

```python
def build_oat_sample(project: Project, seed: int) -> list[tuple[Project, str]]:
    """Return [(project_clone, param_label)] for OAT.

    Index 0 = baseline (no jitter). Indices 1..k = each tolerance +1σ.
    Total = k+1 runs; safe for fast "cheap mode" analysis.
    """
    rng = np.random.default_rng(seed & 0x7FFFFFFF)  # int32 mask (Phase 4 D-08 pattern)
    results: list[tuple[Project, str]] = [(copy.deepcopy(project), "baseline")]
    # ... (iterate active tolerance params; copy; apply single +1sigma perturbation)
    return results


def compute_oat_sensitivity(
    baseline_kpis: dict[str, float],
    perturbed_kpis: list[dict[str, float]],
    param_names: list[str],
    param_sigmas: list[float],
) -> dict[str, list[float]]:
    """Return {kpi_name: [normalized_sensitivity_per_param]}.

    Sensitivity index = |ΔKPI| / sigma_param.  Zero for zero-sigma params.
    """
    results: dict[str, list[float]] = {}
    for kpi_key, base_val in baseline_kpis.items():
        sens = []
        for pert_kpis, sigma in zip(perturbed_kpis, param_sigmas):
            delta = abs(pert_kpis.get(kpi_key, base_val) - base_val)
            sens.append(delta / sigma if sigma > 0 else 0.0)
        results[kpi_key] = sens
    return results
```

**Sobol sample pattern** (from RESEARCH.md Pattern 5):

```python
def build_sobol_sample(project: Project, N: int, seed: int) -> list[tuple[Project, np.ndarray]]:
    """Generate N Saltelli A/B matrix realizations.

    N is rounded up to next power of 2; minimum 32 enforced.
    Returns [(jittered_project_clone, param_vector)] where param_vector is
    the [0,1]^k uniform draw (caller maps to actual σ values).
    """
    from scipy.stats import qmc  # available: scipy 1.17.1 verified
    k = _count_active_tolerance_params(project)
    if k == 0:
        return []
    N_pow2 = int(2 ** np.ceil(np.log2(max(N, 32))))
    sampler = qmc.Sobol(d=2 * k, scramble=True, seed=seed & 0x7FFFFFFF)
    raw = sampler.random(N_pow2)   # (N, 2k) in [0, 1]
    ...
```

**Seed masking pattern** (int32 safety, established Phase 4 Wave 2):

```python
seed & 0x7FFFFFFF  # mask to signed int32 range — Windows ProcessPoolExecutor safety
```

---

### `backlight_sim/io/project_io.py` (utility, CRUD — extend round-trip)

**Analog:** `backlight_sim/io/project_io.py` (self — extend existing patterns)

**Serialization pattern** — `_src_to_dict()` (lines 69-83) is the template for adding new source fields:

```python
def _src_to_dict(s: PointSource) -> dict:
    return {
        "name": s.name,
        "position": _v(s.position),
        "flux": s.flux,
        "direction": _v(s.direction),
        "distribution": s.distribution,
        "enabled": s.enabled,
        "flux_tolerance": s.flux_tolerance,     # ← existing pattern
        "current_mA": s.current_mA,
        "flux_per_mA": s.flux_per_mA,
        "thermal_derate": s.thermal_derate,
        "color_rgb": list(s.color_rgb),
        "spd": s.spd,
        # Phase 5: add here:
        # "position_sigma_mm": s.position_sigma_mm,
    }
```

**Deserialization `.get()` pattern** — `_dict_to_src()` (lines 255-269):

```python
def _dict_to_src(d: dict) -> PointSource:
    return PointSource(
        name=d["name"],
        position=_a(d["position"]),
        flux=d.get("flux", 100.0),
        ...
        flux_tolerance=d.get("flux_tolerance", 0.0),  # ← backwards-compat template
        ...
        # Phase 5: add here:
        # position_sigma_mm=max(0.0, d.get("position_sigma_mm", 0.0)),
    )
```

**Settings round-trip pattern** — `project_to_dict()` settings block (lines 187-206) and `load_project()` settings block (lines 322-337):

```python
# project_to_dict() — serialization:
"settings": {
    ...
    "uq_batches": s.uq_batches,
    "uq_include_spectral": s.uq_include_spectral,
    # Phase 5: add here:
    # "source_position_sigma_mm": s.source_position_sigma_mm,
    # "source_position_distribution": s.source_position_distribution,
},

# load_project() — deserialization:
settings = SimulationSettings(
    ...
    uq_batches=s.get("uq_batches", 10),
    uq_include_spectral=s.get("uq_include_spectral", True),
    # Phase 5: add here:
    # source_position_sigma_mm=max(0.0, s.get("source_position_sigma_mm", 0.0)),
    # source_position_distribution=s.get("source_position_distribution", "gaussian"),
)
```

**`cavity_recipe` round-trip** — `project_to_dict()` and `load_project()`:

```python
# project_to_dict() (add alongside other top-level project fields):
"cavity_recipe": project.cavity_recipe,   # dict of build_cavity kwargs + tolerance fields

# load_project() (add with .get() fallback — backwards compat):
return Project(
    ...
    cavity_recipe=data.get("cavity_recipe", {}),
)
```

**Clamping pattern for sigma fields** (security hardening, from RESEARCH.md threat register):

```python
# Always clamp sigma fields on load to prevent negative/NaN injection:
source_position_sigma_mm=max(0.0, s.get("source_position_sigma_mm", 0.0))
```

---

### `backlight_sim/gui/ensemble_dialog.py` (component, event-driven — NEW FILE)

**Analog:** `backlight_sim/gui/parameter_sweep_dialog.py` — entire file (497 lines). The `_EnsembleThread` mirrors `_SweepThread`; the dialog structure mirrors `ParameterSweepDialog`.

**Import pattern** (from sweep dialog lines 1-27, adapted):

```python
from __future__ import annotations

import copy

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QSplitter,
    QComboBox, QDoubleSpinBox, QSpinBox, QLabel, QWidget,
    QPushButton, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QCheckBox,
)
from PySide6.QtCore import Qt

from backlight_sim.core.project_model import Project
from backlight_sim.core.kpi import compute_scalar_kpis
from backlight_sim.sim.ensemble import build_oat_sample, build_sobol_sample, apply_jitter
from backlight_sim.sim.tracer import RayTracer
```

**`_EnsembleThread` QThread pattern** — copy from `_SweepThread` (lines 107-130), adapt signals:

```python
class _EnsembleThread(QThread):
    step_done    = Signal(int, object, object)   # (member_idx, SimulationResult, Project clone)
    sweep_finished = Signal()

    def __init__(self, base_project: Project, n_members: int, mode: str, seed: int):
        super().__init__()
        self._base = base_project
        self._n = n_members
        self._mode = mode          # "oat" | "sobol"
        self._seed = seed
        self._cancelled = False
        self._member_projects: list[Project] = []   # for worst-case drill-down

    def cancel(self):
        self._cancelled = True     # ← identical to _SweepThread.cancel()

    def run(self):
        from backlight_sim.sim.ensemble import build_oat_sample, build_sobol_sample
        if self._mode == "oat":
            samples = build_oat_sample(self._base, self._seed)
        else:
            samples = build_sobol_sample(self._base, self._n, self._seed)
        for i, (proj, _param_vec) in enumerate(samples):
            if self._cancelled:
                break
            tracer = RayTracer(proj)    # ← identical to _SweepThread.run()
            result = tracer.run()
            self._member_projects.append(proj)
            self.step_done.emit(i, result, proj)
        self.sweep_finished.emit()      # ← identical to _SweepThread
```

**`_run_sweep()` launch pattern** (from sweep dialog lines 362-437):

```python
def _run_ensemble(self):
    # Validation guards (same pattern as sweep dialog):
    if not [s for s in self._project.sources if s.enabled]:
        QMessageBox.warning(self, "No Active Sources", "Enable at least one source.")
        return
    if not self._project.detectors:
        QMessageBox.warning(self, "No Detectors", "Add a detector first.")
        return

    self._run_btn.setEnabled(False)          # ← matches sweep dialog
    self._cancel_btn.setEnabled(True)        # ← matches sweep dialog
    self._progress.setValue(0)               # ← matches sweep dialog
    self._progress.setMaximum(self._n_spin.value())

    n = self._n_spin.value()
    mode = "sobol" if self._sobol_check.isChecked() else "oat"
    if mode == "sobol" and n < 32:
        QMessageBox.warning(self, "Sobol Minimum",
                            "Sobol mode requires N ≥ 32. N will be rounded up.")
    seed = self._project.settings.random_seed & 0x7FFFFFFF

    self._thread = _EnsembleThread(copy.deepcopy(self._project), n, mode, seed)
    self._thread.step_done.connect(self._on_step_done)
    self._thread.sweep_finished.connect(self._on_sweep_finished)
    self._thread.start()                     # ← identical pattern
```

**Live-streaming histogram pattern** (from RESEARCH.md Pattern 6):

```python
# Setup in __init__:
pw = pg.PlotWidget()
pw.setLabel("bottom", "Uniformity")
pw.setLabel("left", "Count")
self._hist_item = pg.BarGraphItem(x=[0.5], height=[0], width=0.05,
                                   brush=pg.mkBrush(80, 160, 255, 180))
pw.addItem(self._hist_item)
self._p5_line  = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen('r', width=1))
self._p50_line = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen('w', width=2))
self._p95_line = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen('g', width=1))
pw.addItem(self._p5_line)
pw.addItem(self._p50_line)
pw.addItem(self._p95_line)

# Per-step update (called from _on_step_done):
def _update_histogram(self, kpi_values: list[float]) -> None:
    counts, edges = np.histogram(kpi_values, bins=20)
    centers = (edges[:-1] + edges[1:]) / 2
    width = edges[1] - edges[0] if len(edges) > 1 else 0.05
    self._hist_item.setOpts(x=centers, height=counts.astype(float), width=width)
    if len(kpi_values) >= 5:
        p5, p50, p95 = np.percentile(kpi_values, [5, 50, 95])
        self._p5_line.setValue(p5)
        self._p50_line.setValue(p50)
        self._p95_line.setValue(p95)
```

**`closeEvent` cancel pattern** (sweep dialog lines 611-615):

```python
def closeEvent(self, event):
    if self._thread and self._thread.isRunning():
        self._thread.cancel()
        self._thread.wait(2000)
    super().closeEvent(event)
```

**Worst-case variant storage pattern** (from `main_window.py` lines 1195-1214):

```python
# Signal from EnsembleDialog to MainWindow:
save_variant = Signal(str, object)   # (name, Project)

# Emission when user clicks "Load worst case":
self.save_variant.emit(f"Ensemble worst case (U={worst_u:.3f})", worst_project)

# In MainWindow connection:
dlg.save_variant.connect(self._on_save_ensemble_variant)

def _on_save_ensemble_variant(self, name: str, project: Project):
    self._variants[name] = project  # already deep-copied by ensemble thread
    self._refresh_variants_menu()
```

---

### `backlight_sim/gui/properties_panel.py` (component, request-response — modify SourceForm)

**Analog:** `backlight_sim/gui/properties_panel.py` — `SourceForm` Thermal/Binning section (lines 344-388) is the direct template.

**`CollapsibleSection` pattern** (collapsible_section.py lines 19-94 and SourceForm lines 344-388):

```python
# Template from Thermal/Binning section (lines 344-388) — replicate for Position Tolerance:
sec_thermal = CollapsibleSection("Thermal / Binning", collapsed=True)
fl_thermal = QFormLayout()
self._tolerance = _dspin(0, 100, 1, 0.0, 1.0)
self._tolerance.setToolTip("LED flux bin tolerance ±% (0 = exact)")
fl_thermal.addRow("Flux tolerance ±%:", self._tolerance)
sec_thermal.addLayout(fl_thermal)
vbox.addWidget(sec_thermal)

# New section for Phase 5 (insert after Thermal/Binning, before vbox.addStretch()):
sec_tolerance = CollapsibleSection("Position Tolerance", collapsed=True)
fl_tol = QFormLayout()
self._pos_sigma = _dspin(0, 100, 3, 0.0, 0.001)
self._pos_sigma.setToolTip(
    "LED placement σ in mm (Gaussian). Value is σ — standard deviation.\n"
    "0 = use project-level default. 1σ ≈ 68% of placements within this distance."
)
fl_tol.addRow("Position σ (mm):", self._pos_sigma)
sec_tolerance.addLayout(fl_tol)
vbox.addWidget(sec_tolerance)
```

**`load()` + `_loading` guard pattern** (lines 414-458):

```python
def load(self, src, distribution_names=None):
    self._loading = True
    self._src = src
    blockers = [
        QSignalBlocker(self._name),
        ...
        QSignalBlocker(self._tolerance),   # existing field — add pos_sigma alongside:
        # QSignalBlocker(self._pos_sigma),
    ]
    self._tolerance.setValue(src.flux_tolerance)
    # Phase 5 addition:
    # self._pos_sigma.setValue(src.position_sigma_mm)
    self._loading = False
    del blockers
```

**`_apply()` changes list pattern** (lines 498-524):

```python
def _apply(self):
    if self._src is None or self._loading:
        return
    name = self._name.text().strip()
    if not name:
        return
    changes = [
        ...
        ('flux_tolerance', self._tolerance.value()),
        # Phase 5 addition:
        # ('position_sigma_mm', self._pos_sigma.value()),
    ]
    _push_or_apply_changes(self._src, changes, ...)
```

**`_dspin()` helper** (lines 100-106 — use for all new spinboxes):

```python
def _dspin(lo=-9999.0, hi=9999.0, dec=2, val=0.0, step=0.1):
    w = QDoubleSpinBox()
    w.setRange(lo, hi)
    w.setDecimals(dec)
    w.setValue(val)
    w.setSingleStep(step)
    return w
```

---

### `backlight_sim/gui/main_window.py` (component, request-response — add menu item)

**Analog:** `backlight_sim/gui/main_window.py` (self — Simulation menu pattern)

**Existing "Parameter Sweep…" menu item pattern** (lines 373-376):

```python
# In _setup_menu(), Simulation menu block (lines 365-376):
sm = mb.addMenu("&Simulation")
act = sm.addAction("Settings", self._show_settings)
...
sm.addSeparator()
act = sm.addAction("Parameter Sweep...", self._open_parameter_sweep)
act.setStatusTip("Run a batch of simulations varying one or two parameters")
```

**New "Tolerance Ensemble…" item to add** — insert after "Parameter Sweep…":

```python
act = sm.addAction("Tolerance Ensemble...", self._open_ensemble_dialog)
act.setStatusTip("Run an ensemble of simulations sampling from tolerance distributions")
```

**`_open_parameter_sweep()` method pattern** (lines 1320-1323) — copy for ensemble:

```python
def _open_parameter_sweep(self):
    from backlight_sim.gui.parameter_sweep_dialog import ParameterSweepDialog
    dlg = ParameterSweepDialog(self._project, self)
    dlg.exec()

# New method (same pattern):
def _open_ensemble_dialog(self):
    from backlight_sim.gui.ensemble_dialog import EnsembleDialog
    dlg = EnsembleDialog(self._project, self)
    dlg.save_variant.connect(self._on_save_ensemble_variant)
    dlg.exec()

def _on_save_ensemble_variant(self, name: str, project: Project):
    self._variants[name] = project
    self._refresh_variants_menu()
```

**Variant dict pattern** (lines 1199-1214 — existing, reused unchanged):

```python
self._variants: dict[str, Project] = {}   # existing dict at __init__ line ~107

def _refresh_variants_menu(self):
    self._variants_menu.clear()
    if not self._variants:
        a = self._variants_menu.addAction("No variants saved")
        a.setEnabled(False)
    else:
        for vname in self._variants:
            self._variants_menu.addAction(
                vname, lambda _=False, n=vname: self._load_variant(n))
        ...
```

---

### `backlight_sim/tests/test_ensemble.py` (test, batch — NEW FILE)

**Analog:** `backlight_sim/tests/test_uq.py` (headless, pytest, fixture-based) and `backlight_sim/tests/test_tracer.py` (scene factory helper).

**Import + scene factory pattern** (from test_tracer.py lines 1-40):

```python
"""Tests for backlight_sim.sim.ensemble — tolerance Monte Carlo service."""

from __future__ import annotations

import copy

import numpy as np
import pytest

from backlight_sim.core.geometry import Rectangle
from backlight_sim.core.materials import Material
from backlight_sim.core.sources import PointSource
from backlight_sim.core.detectors import DetectorSurface
from backlight_sim.core.project_model import Project, SimulationSettings
from backlight_sim.sim.ensemble import apply_jitter, build_oat_sample, compute_oat_sensitivity
from backlight_sim.io.project_io import save_project, load_project


def _make_tolerance_scene(
    pos_sigma_mm: float = 0.0,
    project_sigma_mm: float = 0.0,
) -> Project:
    """Minimal scene with one LED, one detector — fast for ensemble tests."""
    materials = {"wall": Material(name="wall", surface_type="reflector",
                                  reflectance=0.9, absorption=0.1)}
    surfaces = [Rectangle.axis_aligned("floor", [0, 0, -5], (20, 20), 2, -1.0, "wall")]
    detectors = [DetectorSurface.axis_aligned("det", [0, 0, 5], (20, 20), 2, 1.0, (10, 10))]
    src = PointSource("led1", np.array([0.0, 0.0, 0.0]), flux=100.0,
                      position_sigma_mm=pos_sigma_mm)
    settings = SimulationSettings(rays_per_source=500, max_bounces=10,
                                  random_seed=42,
                                  source_position_sigma_mm=project_sigma_mm)
    return Project(name="test_ens", sources=[src], surfaces=surfaces,
                   materials=materials, detectors=detectors, settings=settings)
```

**Test structure pattern** (from test_uq.py lines 26-90 — one assertion per behaviour):

```python
def test_apply_jitter_gaussian_moves_positions():
    """apply_jitter() shifts source positions when sigma > 0."""
    project = _make_tolerance_scene(project_sigma_mm=0.5)
    rng = np.random.default_rng(99)
    jittered = apply_jitter(project, rng)
    # Positions should differ from original
    original_pos = project.sources[0].position.copy()
    assert not np.allclose(jittered.sources[0].position, original_pos)


def test_apply_jitter_does_not_mutate_base():
    """apply_jitter() must deep-copy; base project positions are unchanged."""
    project = _make_tolerance_scene(project_sigma_mm=0.5)
    original_pos = project.sources[0].position.copy()
    rng = np.random.default_rng(99)
    _ = apply_jitter(project, rng)
    np.testing.assert_array_equal(project.sources[0].position, original_pos)


def test_json_roundtrip_tolerance_fields(tmp_path):
    """position_sigma_mm and cavity_recipe survive save/load round-trip."""
    project = _make_tolerance_scene(pos_sigma_mm=0.25, project_sigma_mm=0.1)
    project.cavity_recipe = {"width": 50.0, "depth_sigma_mm": 0.05}
    path = tmp_path / "test.json"
    save_project(project, path)
    loaded = load_project(path)
    assert loaded.sources[0].position_sigma_mm == pytest.approx(0.25)
    assert loaded.settings.source_position_sigma_mm == pytest.approx(0.1)
    assert loaded.cavity_recipe["depth_sigma_mm"] == pytest.approx(0.05)


def test_json_backward_compat_no_tolerance_fields(tmp_path):
    """Older JSON files without tolerance fields load with defaults (0.0 / {})."""
    import json
    old_project_dict = {"name": "old", "sources": [{"name": "s1", "position": [0,0,0]}]}
    path = tmp_path / "old.json"
    path.write_text(json.dumps(old_project_dict))
    loaded = load_project(path)
    assert loaded.sources[0].position_sigma_mm == 0.0
    assert loaded.settings.source_position_sigma_mm == 0.0
    assert loaded.cavity_recipe == {}
```

**pytest.importorskip for optional scipy** (from test_uq.py line 28 — use for Sobol tests):

```python
def test_sobol_sample_count_power_of_2():
    qmc = pytest.importorskip("scipy.stats.qmc")
    project = _make_tolerance_scene(project_sigma_mm=0.5)
    project.settings.source_position_sigma_mm = 0.5
    samples = build_sobol_sample(project, N=10, seed=42)
    # N=10 must be rounded up to 16 (next power of 2, minimum 32 → actually 32)
    assert len(samples) == 32
```

---

## Shared Patterns

### Deep-copy isolation (apply everywhere in ensemble service and QThread)
**Source:** `backlight_sim/gui/parameter_sweep_dialog.py` lines 121-130 and 153-158
```python
# Template: always deepcopy before mutating — never touch self._base
proj = copy.deepcopy(self._base)
# Then apply changes to proj, not base
```

### QThread cancel flag (apply to `_EnsembleThread`)
**Source:** `backlight_sim/gui/parameter_sweep_dialog.py` lines 118-119, 122
```python
def cancel(self):
    self._cancelled = True

def run(self):
    for i, v in enumerate(self._values):
        if self._cancelled:   # ← checked at top of each iteration
            break
```

### `.get(key, default)` backwards compat (apply to all new fields in project_io.py)
**Source:** `backlight_sim/io/project_io.py` lines 255-269
```python
flux_tolerance=d.get("flux_tolerance", 0.0),
current_mA=d.get("current_mA", 0.0),
# Every new field MUST use .get() with a sensible default, never d["key"]
```

### `_loading` guard + `QSignalBlocker` (apply to all new spinboxes in SourceForm)
**Source:** `backlight_sim/gui/properties_panel.py` lines 414-458
```python
def load(self, src, ...):
    self._loading = True
    blockers = [QSignalBlocker(w) for w in (...all spinboxes...)]
    # set values
    self._loading = False
    del blockers

def _apply(self):
    if self._src is None or self._loading:
        return   # ← prevents value-leak on selection changes
```

### Seed int32 masking (apply wherever rng seeds are created from project.settings.random_seed)
**Source:** Phase 4 STATE.md; pattern visible in parameter_sweep_dialog.py usage
```python
seed = project.settings.random_seed & 0x7FFFFFFF
rng = np.random.default_rng(seed)
```

### CollapsibleSection (apply to new SourceForm tolerance subsection)
**Source:** `backlight_sim/gui/widgets/collapsible_section.py` lines 19-94
```python
sec = CollapsibleSection("Position Tolerance", collapsed=True)
fl = QFormLayout()
fl.addRow("Position σ (mm):", self._pos_sigma)
sec.addLayout(fl)
vbox.addWidget(sec)
```

### KPI extraction (apply in _EnsembleThread.run() and sensitivity functions)
**Source:** `backlight_sim/gui/parameter_sweep_dialog.py` lines 446-447
```python
from backlight_sim.core.kpi import compute_scalar_kpis
k = compute_scalar_kpis(result)
eff, u14, hot = k["efficiency_pct"], k["uniformity_1_4_min_avg"], k["hotspot_peak_avg"]
```

### closeEvent cancel + wait pattern (apply to EnsembleDialog)
**Source:** `backlight_sim/gui/parameter_sweep_dialog.py` lines 611-615
```python
def closeEvent(self, event):
    if self._thread and self._thread.isRunning():
        self._thread.cancel()
        self._thread.wait(2000)
    super().closeEvent(event)
```

---

## No Analog Found

All 8 files have close analogs in the codebase. No files require falling back to RESEARCH.md patterns exclusively — RESEARCH.md patterns are referenced above as supplements where codebase analogs cover the structure but not the new content (e.g., Sobol math, histogram widget).

---

## Metadata

**Analog search scope:**
- `backlight_sim/core/` — all files read
- `backlight_sim/sim/` — tracer.py (patterns noted in RESEARCH.md; not re-read; ensemble.py is new)
- `backlight_sim/io/` — project_io.py, geometry_builder.py read
- `backlight_sim/gui/` — parameter_sweep_dialog.py (full), properties_panel.py (lines 1-544), main_window.py (Simulation menu section), widgets/collapsible_section.py read
- `backlight_sim/tests/` — test_tracer.py, test_uq.py read

**Files scanned:** 10 source files read directly; 4 test files globbed

**Pattern extraction date:** 2026-04-19
