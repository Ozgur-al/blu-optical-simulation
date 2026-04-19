# Phase 5: Geometry Tolerance Monte Carlo — Research

**Researched:** 2026-04-19
**Domain:** Ensemble Monte Carlo, sensitivity analysis, PyQt6 background threading, JSON data model extension
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01: v1 Toleranced Parameter Scope**
- D-01a: LED position drift — per-PointSource dx/dy/dz jitter. Per-source, per-realization.
- D-01b: LED flux/binning drift — re-use existing `PointSource.flux_tolerance` (±%). Jitter re-drawn per realization; no new field.
- D-01c: Cavity wall-angle + depth drift — tolerances on the cavity build recipe, not on resulting Rectangles.
- Deferred: generic Rectangle pose tolerances, detector tolerances, material property tolerances.

**D-02: LED Position Tolerance Specification**
- Project-level default `source_position_sigma_mm` (scalar, isotropic 3D σ) in `SimulationSettings`.
- Per-source override via optional sigma fields on `PointSource`.
- UI: project-level default in settings panel; per-source override in a new collapsible tolerance subsection in SourceForm.

**D-03: Cavity Tolerance Via Build Recipe**
- `Project` persists the original `build_cavity()` arguments + tolerances as a build recipe.
- Each ensemble realization re-invokes `build_cavity(**jittered_args)` on a cloned project.
- Models coherent wall drift (all four walls move together when the mold angle drifts).
- Build recipe must round-trip through JSON with `.get(key, default)` backwards compat.

**D-04: Tolerance Units**
- Absolute: position in mm, angle in degrees, depth in mm.
- Exception: `flux_tolerance` keeps ±% units (already shipped).
- No per-field unit toggle.

**D-05: Distribution Shape Per Tolerance**
- Gaussian (default) or uniform, per-tolerance-field.
- Gaussian value = σ (not 3σ or FWHM) — must be documented in tooltip.

**D-06: Phase 4 Dependency Handling**
- Execution blocked on Phase 4. Planning proceeds in parallel.
- No stub CI in Phase 5. Ensemble-vs-MC variance separation uses Phase 4's batch-CI.

**D-07: Phase 4 Prerequisites Locked For Phase 5**
Phase 4 MUST deliver both before Phase 5 executes:
1. `compute_kpis(result, project) -> dict[str, float]` (or equivalent) — no GUI imports.
2. `KpiWithCI` data struct (stable dataclass: `{mean, low, high, n_batches, confidence_level}`).

**Phase 02 decisions that carry over:**
- D-09 hard-crash pattern: `blu_tracer` C++ extension is mandatory; no silent Python fallback.
- Flux tolerance jitter applied in Python before serializing to C++ dict.
- `_project_uses_cpp_unsupported_features` dispatch predicate applies to ensemble members.

### Claude's Discretion

- Tolerance data model shape — inline fields on each dataclass vs unified `ToleranceSpec` struct vs sibling `project.tolerances` dict.
- Sensitivity method — Sobol first-order vs OAT vs Morris. Suggested: OAT for cheap mode, Sobol for full.
- Ensemble runner UI container — new dedicated dialog vs extending `parameter_sweep_dialog`. Scout flagged sweep dialog (497L) as a reference, not container.
- Worst-case drill-down — save full Project clone vs reconstruct from (seed, member_idx).
- Visual indicator — ghosted ±σ wireframe vs tree-icon badge vs skip in v1.
- Live-streaming histogram vs post-run display.
- Default ensemble size N and ensemble-member parallelism via ProcessPoolExecutor.

### Deferred Ideas (OUT OF SCOPE)

- Correlated tolerances (covariance matrix between parameters).
- Temperature-coupled tolerances (depends on Phase 7 thermal model).
- Generic Rectangle pose tolerances (arbitrary floor/wall/diffuser Rectangles).
- Tolerance data model refactor (if v1 inline fields need a unified ToleranceSpec later).
- Robust design optimization (Phase 6 consumes this).
</user_constraints>

---

## Summary

Phase 5 adds a geometry tolerance ensemble runner on top of the Phase 4 UQ infrastructure. The core loop is: (1) draw N realizations from tolerance distributions, (2) for each realization deep-copy the project, apply jitter, re-invoke `build_cavity()` if cavity tolerances are set, and run `RayTracer.run()`, (3) collect a `dict[str, float]` of scalar KPIs per realization, and (4) post-process into histograms, P5/P50/P95 stats, and a sensitivity ranking.

Phase 4 already delivered the two prerequisites from D-07: `compute_scalar_kpis(result) -> dict[str, float]` in `core/kpi.py` and `CIEstimate` in `core/uq.py`. Phase 5 adds a thin jitter layer (`sim/ensemble.py`), new fields on `PointSource`, `SimulationSettings`, and a `Project.cavity_recipe` dict, a new ensemble dialog in `gui/`, and an ensemble results tab.

**Key planning insight:** The entire ensemble loop is structurally identical to `_SweepThread` in `parameter_sweep_dialog.py` — iterate over N realizations, deep-copy project, modify it, run tracer, emit step_done signal. The difference is that modifications come from random draws rather than a linspace grid. New dialog is the right container (sweep dialog is 497 L and contains irrelevant sweep-range UI).

**Primary recommendation:** Implement tolerance fields as inline dataclass fields (not a unified `ToleranceSpec`). Use OAT sensitivity for the default "cheap mode" (k+1 runs). Use Saltelli Sobol sampling (via `scipy.stats.qmc.Sobol`) for the optional full-sensitivity mode. Default N=50 ensemble size. Store worst-case realizations as saved Project variants (not seed/index) — at N=50 the memory cost is negligible and it reuses the existing variant system.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Tolerance field definitions | `core/` (dataclasses) | — | Pure data; no simulation logic |
| Jitter sampling (Gaussian / uniform draws) | `sim/ensemble.py` (new) | — | Sim layer owns sampling; no GUI imports |
| Cavity rebuild per realization | `io/geometry_builder.py` | `sim/ensemble.py` | `build_cavity()` is already in `io/`; caller in `sim/` orchestrates |
| Ensemble runner loop | `sim/ensemble.py` | — | Headless; callable from tests without Qt |
| Ensemble QThread wrapper | `gui/ensemble_dialog.py` (new) | — | Qt threading lives in `gui/` |
| KPI collection per member | `core/kpi.compute_scalar_kpis` | `core/kpi.compute_all_kpi_cis` | Already extracted in Phase 4 |
| Sensitivity index calculation | `sim/ensemble.py` | — | Pure-numpy post-processing |
| Results histogram / P5/P50/P95 display | `gui/ensemble_dialog.py` | — | UI only; no physics |
| Worst-case variant storage | `MainWindow._variants` (existing) | — | Reuses existing variant dict |
| JSON save/load of new fields | `io/project_io.py` | — | Already owns serialization |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| NumPy | 2.4.2 [VERIFIED: pip show] | Jitter sampling, histogram binning, sensitivity arrays | Already in project |
| scipy.stats.qmc.Sobol | 1.17.1 [VERIFIED: pip show] | Sobol quasi-random sequence for Saltelli sensitivity | Built into scipy, available in env |
| copy.deepcopy (stdlib) | stdlib | Per-member project isolation | Already used in sweep dialog |
| PySide6 + pyqtgraph | 6.10.2 / 0.14.0 [VERIFIED: pip show] | Dialog, QThread, BarGraphItem histogram | Already in project |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| dataclasses.replace | stdlib | Copy SimulationSettings with overrides | Already used in tracer.py for UQ batch |
| json (stdlib) | stdlib | Project JSON round-trip | Already used in project_io.py |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| scipy.stats.qmc.Sobol | SALib | SALib not installed; scipy Sobol QMC sufficient for Saltelli Si estimation |
| inline tolerance fields | Unified `ToleranceSpec` dataclass | ToleranceSpec adds indirection; inline fields match existing pattern (flux_tolerance is inline) and keep JSON schema flat |
| BarGraphItem histogram | matplotlib | matplotlib not always available (golden suite degrades gracefully); pyqtgraph BarGraphItem is sufficient and consistent with existing plots |

**Installation:** No new packages required. All dependencies already in `requirements.txt`.

**Version verification:** `numpy==2.4.2`, `scipy==1.17.1`, `PySide6==6.10.2`, `pyqtgraph==0.14.0` all verified via `pip show`. [VERIFIED: pip show numpy scipy PySide6 pyqtgraph]

---

## Architecture Patterns

### System Architecture Diagram

```
User sets tolerance fields
       │
       ▼
[Ensemble Dialog — N, mode, KPI selector]
       │ starts _EnsembleThread(QThread)
       ▼
[_EnsembleThread.run()]
  │
  ├── Sensitivity mode = OAT?
  │      └── build_oat_sample(base_project, N) → list[Project]
  │
  └── Sensitivity mode = Sobol?
         └── build_sobol_sample(base_project, N) → list[Project]  (N must be power-of-2)
              uses scipy.stats.qmc.Sobol
       │
       ▼  for each realization_project:
[sim/ensemble.py::apply_jitter(base_project, param_sample, rng)]
  ├── jitter PointSource positions
  ├── re-draw flux_tolerance per source (existing field)
  └── re-invoke build_cavity(**jittered_cavity_args) if cavity_recipe present
       │
       ▼
[RayTracer(realization_project).run()]  ← existing tracer, no changes
       │
       ▼
[core/kpi.compute_scalar_kpis(result)] → dict[str, float]
  optionally also: compute_all_kpi_cis(result)  ← Phase 4 API
       │
       ▼  step_done signal → GUI
[_EnsembleThread] accumulates:
  kpi_matrix: (N, k_kpis) array
  param_matrix: (N, k_params) array
  realization_projects: list[Project] (for worst-case drill-down)
       │
       ▼  on sweep_finished:
[EnsembleResultsWidget]
  ├── histogram + P5/P50/P95 per KPI  (pyqtgraph BarGraphItem)
  ├── sensitivity table (OAT: delta KPI / σ_param; Sobol: Si)
  └── "Load worst case as variant" button → MainWindow._variants
```

### Recommended Project Structure

New/changed files:
```
backlight_sim/
├── core/
│   └── project_model.py        # +source_position_sigma_mm in SimulationSettings
│                               # +per-source position_sigma_mm override on PointSource
│                               # +Project.cavity_recipe dict
├── sim/
│   └── ensemble.py             # NEW: apply_jitter(), build_oat_sample(),
│                               #      build_sobol_sample(), compute_oat_sensitivity(),
│                               #      compute_sobol_sensitivity()
├── io/
│   └── project_io.py           # +new fields round-trip (source_position_sigma_mm,
│                               #  cavity_recipe, per-source position_sigma_mm)
└── gui/
    ├── ensemble_dialog.py      # NEW: EnsembleDialog + _EnsembleThread + results widget
    ├── properties_panel.py     # +tolerance subsection in SourceForm
    └── main_window.py          # +"Tolerance Ensemble..." menu item
backlight_sim/tests/
    └── test_ensemble.py        # NEW: headless tests for sim/ensemble.py
```

### Pattern 1: Tolerance Data Model — Inline Fields

**What:** Add tolerance fields directly on existing dataclasses, mirroring how `flux_tolerance` already lives on `PointSource`.

**When to use:** Chosen here because: (1) it matches the established pattern, (2) JSON round-trip is simpler (one extra key per object, not a nested dict), (3) UI forms can add one `_dspin` per tolerance field without restructuring.

**Example:**
```python
# Source: backlight_sim/core/sources.py (existing pattern)
# Existing:
flux_tolerance: float = 0.0   # ±% bin tolerance

# New fields (Phase 5):
position_sigma_mm: float = 0.0  # per-source position σ override (0 = use project default)
```

```python
# Source: backlight_sim/core/project_model.py (existing SimulationSettings)
# New field on SimulationSettings:
source_position_sigma_mm: float = 0.0   # project-level default isotropic σ (mm)
source_position_distribution: str = "gaussian"  # "gaussian" | "uniform"
```

```python
# Source: backlight_sim/core/project_model.py (new field on Project)
# Cavity build recipe — empty dict means no cavity tolerances defined
cavity_recipe: dict = field(default_factory=dict)
# Schema: {
#   "width": float, "height": float, "depth": float,
#   "wall_angle_x_deg": float, "wall_angle_y_deg": float,
#   "floor_material": str, "wall_material": str,
#   # tolerance fields (all optional, default 0):
#   "depth_sigma_mm": float, "wall_angle_x_sigma_deg": float,
#   "wall_angle_y_sigma_deg": float,
#   "depth_distribution": str, "wall_angle_distribution": str,
# }
```

**JSON backwards compat:** All new fields use `.get(key, default)` in `_dict_to_src()` and `load_project()`. Older files load with all tolerances = 0 (no jitter). [VERIFIED: pattern confirmed in existing `_dict_to_src` at project_io.py L255-269]

### Pattern 2: Ensemble Runner QThread

**What:** Mirrors `_SweepThread` exactly — inherit from QThread, store base_project, emit `step_done(idx, result, realization_project)` and `sweep_finished(kpi_matrix, sensitivity)`.

**When to use:** Every ensemble run.

**Example:**
```python
# Source: backlight_sim/gui/parameter_sweep_dialog.py L107-130 (established pattern)
class _EnsembleThread(QThread):
    step_done = Signal(int, object, object)   # (member_idx, SimulationResult, Project clone)
    sweep_finished = Signal()

    def __init__(self, base_project: Project, n_members: int, mode: str, rng_seed: int):
        super().__init__()
        self._base = base_project
        self._n = n_members
        self._mode = mode          # "oat" | "sobol"
        self._seed = rng_seed
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        import copy
        from backlight_sim.sim.ensemble import build_oat_sample, build_sobol_sample, apply_jitter
        from backlight_sim.sim.tracer import RayTracer
        samples = build_oat_sample(self._base, self._n, self._seed) if self._mode == "oat" \
                  else build_sobol_sample(self._base, self._n, self._seed)
        for i, (proj, param_vec) in enumerate(samples):
            if self._cancelled:
                break
            result = RayTracer(proj).run()
            self.step_done.emit(i, result, proj)
        self.sweep_finished.emit()
```

### Pattern 3: Jitter Application (Pre-serialization)

**What:** Apply jitter to Python project objects BEFORE the C++ serialization boundary, following Phase 02 Wave 3 decision for flux_tolerance.

**When to use:** Every ensemble member, both C++ and Python tracer paths.

**Example:**
```python
# Source: backlight_sim/sim/tracer.py Wave 3 decision (confirmed in STATE.md)
# Existing (flux tolerance, applied before _serialize_project):
if s.flux_tolerance > 0:
    jitter = self.rng.uniform(-s.flux_tolerance / 100.0, s.flux_tolerance / 100.0)
    effective = s.effective_flux * (1.0 + jitter)

# Phase 5 pattern (same tier, sim/ensemble.py):
def apply_jitter(project: Project, param_sample: dict, rng: np.random.Generator) -> Project:
    """Return a deep-copy of project with all tolerance jitters applied."""
    p = copy.deepcopy(project)
    sigma = p.settings.source_position_sigma_mm
    dist = p.settings.source_position_distribution
    for src in p.sources:
        s = max(src.position_sigma_mm, sigma) if src.position_sigma_mm > 0 else sigma
        if s > 0:
            if dist == "uniform":
                dx, dy, dz = rng.uniform(-s * np.sqrt(3), s * np.sqrt(3), 3)
            else:  # gaussian
                dx, dy, dz = rng.normal(0, s, 3)
            src.position = src.position + np.array([dx, dy, dz])
    # Cavity recipe jitter (if present):
    if p.cavity_recipe:
        _jitter_cavity(p, param_sample, rng)
    return p
```

### Pattern 4: OAT Sensitivity

**What:** One-At-a-Time sensitivity — run baseline, then k additional runs each perturbing one parameter by +1σ. Sensitivity index = |ΔKPI| / σ_param.

**When to use:** Default "cheap mode" — requires only k+1 total runs per KPI. Sufficient for v1 with k=3 parameters (LED position, flux tolerance, cavity angle) → 4 runs total.

**How to implement:**
```python
def compute_oat_sensitivity(
    baseline_kpis: dict[str, float],
    perturbed_kpis: list[dict[str, float]],   # one per parameter
    param_names: list[str],
    param_sigmas: list[float],
) -> dict[str, list[float]]:
    """Return {kpi_name: [sensitivity_index_per_param]} normalized by σ."""
    results = {}
    for kpi_key, base_val in baseline_kpis.items():
        sens = []
        for i, (pert_kpis, sigma) in enumerate(zip(perturbed_kpis, param_sigmas)):
            delta = abs(pert_kpis.get(kpi_key, base_val) - base_val)
            sens.append(delta / sigma if sigma > 0 else 0.0)
        results[kpi_key] = sens
    return results
```

### Pattern 5: Sobol First-Order Sensitivity (Full Mode)

**What:** Saltelli (2002) pick-freeze estimator for Sobol first-order indices using `scipy.stats.qmc.Sobol` for the sample matrix. Requires N*(k+2) evaluations where N is a power of 2.

**When to use:** Optional "full sensitivity" mode when ensemble N ≥ 32 (user checkbox).

**Critical sample-count implication:** For v1 k=3 parameters and N=64: 64*(3+2) = 320 runs. At 10k rays/source that is ~35 seconds on the benchmark hardware — acceptable for a background thread. For k=5 parameters: 64*(5+2) = 448 runs. User should be warned.

**Example:**
```python
# Source: scipy.stats.qmc documentation (ASSUMED - verified scipy 1.17.1 is available)
from scipy.stats import qmc
import numpy as np

def build_sobol_sample(project, N: int, seed: int):
    """Generate Saltelli A/B matrix for Sobol Si estimation."""
    k = _count_active_tolerance_params(project)
    # N must be power of 2 for scrambled Sobol
    N = int(2 ** np.ceil(np.log2(max(N, 4))))
    sampler = qmc.Sobol(d=2 * k, scramble=True, seed=seed)
    raw = sampler.random(N)   # shape (N, 2k) in [0, 1]
    A = raw[:, :k]
    B = raw[:, k:]
    # Build A, B, and k AB_i matrices (Saltelli 2002 eq. 2)
    ...
```

### Pattern 6: Live-Streaming Histogram

**What:** Incrementally update a `pg.BarGraphItem` as each ensemble member finishes. Bins are pre-allocated from KPI min/max estimate; counts are updated via `setOpts(height=new_counts)`.

**When to use:** Ensemble run with N > 10 to give user feedback before all N members complete.

**Implementation note:** `pg.BarGraphItem.setOpts()` is a full redraw, not incremental, but at N=50-200 this is fast enough. The histogram needs to handle bin edges that are set before the first result arrives (use a reasonable default range, e.g. [0, 1] for uniformity metrics), then widen on data range violations.

### Anti-Patterns to Avoid

- **Mutating the base project directly:** `apply_jitter()` must always deep-copy before modifying. The sweep dialog pattern (`copy.deepcopy(self._base)` at L125) is the reference.
- **Sobol with non-power-of-2 N:** `scipy.stats.qmc.Sobol` requires power-of-2 sample counts; silently wrong otherwise. Enforce `N = 2**ceil(log2(N))` before sampling.
- **Running ensemble members in ProcessPoolExecutor at the outer level:** The inner `RayTracer.run()` already uses ProcessPoolExecutor when `settings.use_multiprocessing=True`. Nesting two `ProcessPoolExecutor` pools would saturate CPU. The ensemble must either (a) run members serially in the QThread, or (b) disable inner MP when using ensemble-level parallelism. Simplest for v1: members run serially; inner MP is available per-member.
- **Storing N full Project objects for sensitivity reconstruction:** For OAT mode only 1 baseline + k perturbed projects need tracking. For distribution ensemble: only worst-case outliers need to be saved as variants.
- **Adding `source_position_sigma_mm` to the C++ serialization dict:** Position jitter is applied to `src.position` in Python before `_serialize_project()`. The C++ extension reads the already-jittered position. No change to `_serialize_project()` is needed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sobol quasi-random sequence | Custom van-der-Corput sequences | `scipy.stats.qmc.Sobol` | Scrambling, seed control, correct Saltelli layout all handled; hand-rolling QMC sequences is error-prone |
| Student-t CI for ensemble batch means | Custom t-table | `core/uq.batch_mean_ci` (Phase 4) | Already ships with the project; same API used by heatmap panel |
| KPI computation | Re-derive from result grids | `core/kpi.compute_scalar_kpis` | Already extracted in Phase 4; bitwise parity verified against GUI reference |
| Deep-copy project for member isolation | Manual field-by-field copy | `copy.deepcopy(project)` | Already used in sweep dialog; numpy arrays are correctly copied by deepcopy |
| QThread background runner | Raw Python threading | `QThread` + `Signal` | Already the pattern in `_SweepThread`; raw threads can deadlock with Qt event loop |

**Key insight:** The sweep dialog already solves 80% of the ensemble UI problem. The main additions are: (1) a sampling function instead of `np.linspace`, (2) a histogram widget instead of a table, and (3) a sensitivity table.

---

## Common Pitfalls

### Pitfall 1: Cavity Recipe Round-Trip

**What goes wrong:** `Project.cavity_recipe` dict is saved to JSON but `load_project()` doesn't read it, so tolerances are lost on reload.

**Why it happens:** `project_to_dict()` at project_io.py L187-220 must be updated alongside `load_project()`. The pattern is established but the new field is new.

**How to avoid:** Add `cavity_recipe` to both `project_to_dict()` serialization and `load_project()` deserialization with `.get("cavity_recipe", {})` fallback. Test with an older JSON that lacks the key.

**Warning signs:** Tolerance fields appear in the UI after saving and reloading but are all zero.

### Pitfall 2: Position Sigma Applied Before C++ Serialization

**What goes wrong:** `source_position_sigma_mm` stored on `PointSource` but the C++ extension never sees jittered positions because `_serialize_project()` uses `s.position` — which is the original unjittered position when jitter is a separate dict field rather than an in-place mutation.

**Why it happens:** The C++ dict is built from `project.sources[i].position`. If jitter is applied to a side-channel rather than directly to `src.position`, the C++ extension gets the nominal position.

**How to avoid:** `apply_jitter()` in `sim/ensemble.py` must mutate (or rather, set) `src.position` on the deep-copied project object directly, so `_serialize_project()` picks up the jittered coordinates. This matches the flux_tolerance pattern (STATE.md: "flux_tolerance jitter applied in Python BEFORE serializing the project dict").

**Warning signs:** Ensemble KPI distribution is a Dirac spike (zero variance) — all members look identical despite non-zero sigma.

### Pitfall 3: Sobol Sensitivity with Too Few Samples

**What goes wrong:** User runs Sobol mode with N=10 (not a power of 2; gets rounded up to 16). With k=4 parameters that's 16*(4+2)=96 runs but the Saltelli estimator is noisy below N~32. First-order indices may be negative (statistically consistent with zero, but confusing).

**Why it happens:** Saltelli (2002) Sobol indices have high variance at small N. The Sobol QMC sampler does not warn about this.

**How to avoid:** (1) Enforce minimum N=32 for Sobol mode (display a warning if user enters <32). (2) Clamp the displayed Si to [0, 1] — negative values are numerical artifacts to be clamped. (3) Add "N must be ≥ 32 for reliable Sobol estimates" tooltip on the N spinbox when Sobol mode is selected.

**Warning signs:** Negative Sobol Si values in the sensitivity table.

### Pitfall 4: Nested ProcessPoolExecutor Deadlock

**What goes wrong:** Ensemble QThread calls `RayTracer.run()` with `settings.use_multiprocessing=True`, which spawns a `ProcessPoolExecutor`. If the host process is itself inside a worker (unlikely) or if the OS limits child process nesting, this fails silently.

**Why it happens:** Python's `ProcessPoolExecutor` uses `spawn` on Windows. Nested executors on Windows can hit pickling limits or deadlock.

**How to avoid:** For each ensemble member, force `use_multiprocessing=False` in the cloned project settings (or document that ensemble mode disables inner MP). The ensemble thread is serial over members; per-member MP is wasteful anyway at typical N=50 × short run times.

**Warning signs:** Ensemble thread hangs indefinitely without progress signals.

### Pitfall 5: cavity_recipe Not Reset After GUI Geometry Builder Invocation

**What goes wrong:** User runs the Geometry Builder dialog → `build_cavity()` is called but `project.cavity_recipe` is not updated to reflect the new geometry arguments. Tolerance MC then re-runs `build_cavity()` with the stale recipe.

**Why it happens:** `io/geometry_builder.py::build_cavity()` currently accepts width/height/depth/angles as parameters but does not update any recipe field on `project`. The GUI geometry builder at `gui/geometry_builder.py` wraps this call.

**How to avoid:** When `build_cavity()` is called from the GUI builder dialog, also write the recipe to `project.cavity_recipe`. Make `build_cavity()` optionally accept a `record_recipe=True` flag that writes back to `project.cavity_recipe` after clearing surfaces.

**Warning signs:** Ensemble members produce geometry inconsistent with what the user sees in the 3D viewport (different cavity dimensions).

### Pitfall 6: Histogram Bin Width Changes Mid-Run

**What goes wrong:** First 10 members produce uniformity in [0.80, 0.88]. Histogram is initialized with 10 bins in that range. Members 11-50 include bad outliers at 0.55 — they fall outside the pre-set bin range and are silently dropped.

**Why it happens:** Static bin edges set before data arrives.

**How to avoid:** Use dynamic bin edges that widen as data arrives. On each `step_done`: recompute `np.histogram(all_kpis_so_far, bins=20)` from scratch and call `setOpts(x=new_centers, height=new_counts, width=new_bin_width)`. O(N) per step but at N=200 this is negligible.

---

## Code Examples

Verified patterns from the codebase:

### KPI extraction (Phase 4 API — available now)
```python
# Source: backlight_sim/core/kpi.py L104-142 [VERIFIED: read file]
from backlight_sim.core.kpi import compute_scalar_kpis, compute_all_kpi_cis

result = RayTracer(project).run()
kpis = compute_scalar_kpis(result)
# keys: "efficiency_pct", "uniformity_1_4_min_avg", "hotspot_peak_avg"

cis = compute_all_kpi_cis(result, conf_level=0.95)
# keys: "avg", "peak", "min", "cv", "hot", "ecr", "corner",
#       "uni_1_4_min_avg", "uni_1_6_min_avg", "uni_1_10_min_avg", "efficiency_pct"
# values: CIEstimate or None (None when UQ off / n_batches < 4)
```

### Deep-copy project for ensemble member isolation
```python
# Source: backlight_sim/gui/parameter_sweep_dialog.py L125-130 [VERIFIED: read file]
import copy
proj = copy.deepcopy(self._base)
# Then apply jitter to proj (not base)
# Then: tracer = RayTracer(proj); result = tracer.run()
```

### CollapsibleSection for new tolerance subsection in SourceForm
```python
# Source: backlight_sim/gui/widgets/collapsible_section.py [VERIFIED: read file]
# Existing usage pattern (thermal/binning section):
sec_tolerance = CollapsibleSection("Position Tolerance", collapsed=True)
fl_tol = QFormLayout()
self._pos_sigma = _dspin(0, 10, 3, 0.0, 0.01)
self._pos_sigma.setToolTip(
    "LED placement σ in mm (Gaussian). Value is σ — standard deviation.\n"
    "0 = use project-level default. 1σ ≈ 68% of placements within this distance."
)
fl_tol.addRow("Position σ (mm):", self._pos_sigma)
sec_tolerance.addLayout(fl_tol)
vbox.addWidget(sec_tolerance)
```

### Variant storage for worst-case drill-down
```python
# Source: backlight_sim/gui/main_window.py L1195 [VERIFIED: read file]
# Existing idiom:
self._variants[name] = copy.deepcopy(self._project)
self._refresh_variants_menu()
# For ensemble worst-case, emit a signal from EnsembleDialog:
# main_window.connect(ensemble_dialog.save_variant, self._on_save_ensemble_variant)
# def _on_save_ensemble_variant(self, name: str, project: Project):
#     self._variants[name] = project  # already a deep-copy from ensemble runner
#     self._refresh_variants_menu()
```

### Sobol quasi-random sampling
```python
# Source: scipy.stats.qmc docs [VERIFIED: scipy 1.17.1 available, Sobol import tested]
from scipy.stats import qmc
import numpy as np

def build_sobol_matrix(k: int, N: int, seed: int = 42):
    """Build Saltelli A/B matrices for Sobol Si estimation.

    Returns (A, B, AB_list) where AB_list has k matrices each with column i
    taken from B and all other columns from A.
    """
    N_pow2 = int(2 ** np.ceil(np.log2(max(N, 32))))
    sampler = qmc.Sobol(d=2 * k, scramble=True, seed=seed)
    raw = sampler.random(N_pow2)   # (N, 2k) in [0, 1]
    A = raw[:, :k]   # shape (N, k)
    B = raw[:, k:]   # shape (N, k)
    AB_list = [np.column_stack([
        B[:, i:i+1] if j == i else A[:, j:j+1]
        for j in range(k)
    ]) for i in range(k)]
    return A, B, AB_list
```

### OAT sensitivity (cheap mode)
```python
# Pattern: one baseline + k perturbed runs [ASSUMED - standard practice]
def build_oat_sample(project: Project, seed: int):
    """Return list of (project_clone, param_label) for OAT.

    Index 0 = baseline (no jitter).
    Indices 1..k = each tolerance perturbed by +1σ.
    """
    rng = np.random.default_rng(seed)
    results = [(copy.deepcopy(project), "baseline")]
    active = _active_tolerance_params(project)  # list of (param_name, sigma)
    for param_name, sigma in active:
        p = copy.deepcopy(project)
        _apply_single_perturbation(p, param_name, sigma, rng)
        results.append((p, param_name))
    return results
```

### Pyqtgraph BarGraphItem histogram (live-updating)
```python
# Source: pyqtgraph 0.14.0 [VERIFIED: hasattr check passed]
import pyqtgraph as pg
import numpy as np

# Initial setup (in dialog __init__):
pw = pg.PlotWidget()
pw.setLabel("bottom", "Uniformity")
pw.setLabel("left", "Count")
self._hist_item = pg.BarGraphItem(x=[0.5], height=[0], width=0.05,
                                   brush=pg.mkBrush(80, 160, 255, 180))
pw.addItem(self._hist_item)
# P5/P50/P95 vertical lines:
self._p5_line  = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen('r', width=1))
self._p50_line = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen('w', width=2))
self._p95_line = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen('g', width=1))

# Per-step update (called on step_done signal):
def _update_histogram(self, kpi_values: list[float]):
    counts, edges = np.histogram(kpi_values, bins=20)
    centers = (edges[:-1] + edges[1:]) / 2
    width = edges[1] - edges[0] if len(edges) > 1 else 0.05
    self._hist_item.setOpts(x=centers, height=counts, width=width)
    if len(kpi_values) >= 5:
        p5, p50, p95 = np.percentile(kpi_values, [5, 50, 95])
        self._p5_line.setValue(p5)
        self._p50_line.setValue(p50)
        self._p95_line.setValue(p95)
```

---

## Recommendations for Claude's Discretion Items

### Tolerance Data Model: Inline Fields (Recommended)

Use inline fields on `PointSource` and `SimulationSettings`. Rationale:

1. `flux_tolerance: float = 0.0` is already on `PointSource` as an inline field — the pattern is established.
2. Inline fields require zero structural changes to `project_io.py` beyond adding `.get("field", default)` in deserialization.
3. A `ToleranceSpec` dataclass adds a nested dict to JSON that breaks simpler parsers and increases the schema surface area.
4. The deferred v2 refactor to `ToleranceSpec` can be done without breaking existing JSON files (add it as an optional parallel schema).

The `cavity_recipe` dict on `Project` is the one exception — it is inherently a dict because it mirrors the `build_cavity()` kwargs signature (which may evolve). [VERIFIED: build_cavity signature inspected at io/geometry_builder.py L15-26]

### Sensitivity Method: OAT Default + Optional Sobol (Recommended)

Default "cheap mode" = OAT:
- Only k+1 runs (4 runs for v1 scope: baseline + LED position + flux tolerance + cavity angle).
- Sufficient to rank parameters; cannot detect interactions.
- Runs in < 1 second at 2k rays.

Optional "full Sobol" mode (user checkbox):
- N*(k+2) evaluations where N is a power of 2 (minimum 32).
- At N=64, k=3: 320 runs ≈ 7 seconds at 10k rays. Acceptable for background thread.
- Provides first-order + total-order indices; detects interactions.
- Uses `scipy.stats.qmc.Sobol` (available; tested). [VERIFIED: import tested in session]

The UI should show a "Sensitivity Mode" combo: "Fast (OAT)" / "Full (Sobol, N≥32)". The ensemble N spinbox is shared — for Sobol mode, N is rounded up to the next power of 2 automatically.

### Ensemble Runner UI: New Dialog (Recommended)

New `gui/ensemble_dialog.py`. The `parameter_sweep_dialog.py` is 497 lines with sweep-range UI (Start/End/Steps spinboxes, 2-parameter grid) that is irrelevant to ensemble runs. A new dialog:
- Avoids inheriting confusing sweep-range controls.
- Can be sized for the histogram + sensitivity table layout without fighting existing table layout.
- Follows the same template (`QDialog`, `QSplitter`, `QProgressBar`, `_EnsembleThread`).

Estimated dialog size: ~350-450 lines (smaller than sweep dialog due to simpler parameter setup section).

### Worst-Case Drill-Down: Save Project Clone as Variant (Recommended)

The ensemble thread stores the `Project` clone for each member that finishes. When the user clicks "Load this realization as variant" in the histogram, the thread has the clone ready — no reconstruction needed.

Memory cost: At N=200, each Project clone (excluding simulation results) is roughly ~50-200 KB depending on number of surfaces. Total: ~10-40 MB — well within desktop memory constraints.

Implementation: `_EnsembleThread` stores `self._member_projects: list[Project] = []`. On `step_done`, append the realization clone. On histogram bin click, find members whose KPI falls in the bin, and emit a signal to main_window with the worst-case clone.

The existing `self._variants` dict in `MainWindow` (verified at L107) and the `_clone_as_variant()` / `_load_variant()` idiom (verified at L1186-1243) make this a 3-line addition in the dialog-to-mainwindow signal path.

### Visual Indicator: Tree-Icon Badge (Recommended for v1)

The ghosted ±σ wireframe in the 3D viewport would require extending `Viewport3D.update_scene()` to detect tolerance fields and draw additional semi-transparent mesh items. This is non-trivial and adds viewport complexity for a debugging aid.

A simpler v1 approach: add a badge character or icon to the tree item label when `source.position_sigma_mm > 0` or the project-level default is set. The `ObjectTree` already builds item text from object names — adding a `⚙` or `±` prefix is a 5-line change to `_build_tree()`.

Defer the 3D wireframe to a v2 polish pass.

### Live-Streaming Histogram: Yes (Recommended)

At N=50-200, each step takes 22-110 ms. Without live updates, the user sees a frozen progress bar for 1-22 seconds with no indication of the developing distribution. The `step_done` signal already fires per-member (same as sweep dialog) and histogram update is O(N) per step but negligible at N=200. Implement live streaming from day one.

### Default Ensemble Size N and Parallelism

Default N = 50 (sufficient for reliable P5/P50/P95 estimates; fast at 2k rays; reasonable at 10k rays).

Parallelism recommendation: Run ensemble members SERIALLY in the QThread for v1. Rationale:
- Each `RayTracer.run()` already uses `ProcessPoolExecutor` when `settings.use_multiprocessing=True`. Member-level parallelism would require either (a) disabling inner MP, or (b) spawning a nested executor, both of which add complexity.
- At N=50 × 110 ms/member = 5.5 seconds serial at 10k rays — acceptable for a background thread.
- For users who want faster ensemble runs, recommend setting `use_multiprocessing=True` (inner parallelism) which gives 2-6x speedup per member.

Document this clearly in the dialog: "Each ensemble member runs with your current Multiprocessing setting."

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual "sweep and eyeball" for worst case | Automated ensemble with P5/P50/P95 distribution | Phase 5 (this phase) | Engineers see full yield distribution |
| Global SALib dependency for Sobol | `scipy.stats.qmc.Sobol` (built into scipy ≥ 1.7) | scipy 1.7 (2021) | No extra package; Sobol QMC available in env |
| KPI logic tangled in heatmap_panel.py | `core/kpi.compute_scalar_kpis()` extracted in Phase 4 | Phase 4 | Ensemble can call headless KPI computation |

**Deprecated/outdated:**
- SALib package: Was the standard for Sobol analysis before scipy added `scipy.stats.qmc`. Not installed in this environment. Use scipy QMC instead.

---

## Runtime State Inventory

> Phase 5 is not a rename/refactor/migration phase. No runtime state inventory needed.

**None — this is a greenfield feature addition.**

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| numpy | Jitter sampling, histogram | ✓ | 2.4.2 | — |
| scipy.stats.qmc | Sobol sampling (full mode) | ✓ | 1.17.1 | Disable Sobol mode, OAT only |
| PySide6 | Ensemble dialog, QThread | ✓ | 6.10.2 | — |
| pyqtgraph | BarGraphItem, PlotWidget | ✓ | 0.14.0 | — |
| pytest | Tests | ✓ | 9.0.2 | — |
| SALib | Sobol Si estimation (alternative) | ✗ | — | Use scipy.stats.qmc.Sobol instead |
| blu_tracer.pyd | C++ fast path | ✓ | cp312-win_amd64 | D-09 hard crash — mandatory |

[VERIFIED: all availability checks via pip show and python import tests in session]

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:**
- SALib: not installed. Fallback is `scipy.stats.qmc.Sobol`, which is already installed and tested.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | none (bare pytest invocation) |
| Quick run command | `pytest backlight_sim/tests/test_ensemble.py -x -q` |
| Full suite command | `pytest backlight_sim/tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENS-01 | `apply_jitter()` applies position offset sampled from correct distribution | unit | `pytest backlight_sim/tests/test_ensemble.py::test_apply_jitter_gaussian -x` | ❌ Wave 0 |
| ENS-02 | `apply_jitter()` does not mutate base project (deep-copy isolation) | unit | `pytest backlight_sim/tests/test_ensemble.py::test_apply_jitter_does_not_mutate_base -x` | ❌ Wave 0 |
| ENS-03 | Cavity recipe jitter re-invokes `build_cavity()` with jittered args | unit | `pytest backlight_sim/tests/test_ensemble.py::test_cavity_jitter_rebuilds_geometry -x` | ❌ Wave 0 |
| ENS-04 | JSON round-trip preserves `source_position_sigma_mm` and `cavity_recipe` | unit | `pytest backlight_sim/tests/test_ensemble.py::test_json_roundtrip_tolerance_fields -x` | ❌ Wave 0 |
| ENS-05 | Older JSON files load without tolerance fields (backwards compat) | unit | `pytest backlight_sim/tests/test_ensemble.py::test_json_backward_compat_no_tolerance_fields -x` | ❌ Wave 0 |
| ENS-06 | OAT sensitivity returns k+1 entries; baseline is member 0 | unit | `pytest backlight_sim/tests/test_ensemble.py::test_oat_sample_count_and_baseline -x` | ❌ Wave 0 |
| ENS-07 | `compute_oat_sensitivity()` returns zero for zero-sigma params | unit | `pytest backlight_sim/tests/test_ensemble.py::test_oat_sensitivity_zero_sigma -x` | ❌ Wave 0 |
| ENS-08 | Sobol sample count is rounded up to next power of 2 | unit | `pytest backlight_sim/tests/test_ensemble.py::test_sobol_sample_count_power_of_2 -x` | ❌ Wave 0 |
| ENS-09 | Ensemble KPI spread increases with larger sigma (distribution sensitivity test) | integration | `pytest backlight_sim/tests/test_ensemble.py::test_ensemble_spread_increases_with_sigma -x` | ❌ Wave 0 |
| ENS-10 | _EnsembleThread cancel flag halts run mid-ensemble | unit (headless Qt) | `pytest backlight_sim/tests/test_ensemble.py::test_ensemble_thread_cancel -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest backlight_sim/tests/test_ensemble.py -x -q --tb=short`
- **Per wave merge:** `pytest backlight_sim/tests/ -q`
- **Phase gate:** Full suite (currently 240 tests) green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backlight_sim/tests/test_ensemble.py` — covers ENS-01 through ENS-10
- [ ] `backlight_sim/sim/ensemble.py` — new module (stub with raise NotImplementedError for Wave 0 TDD)
- [ ] No new framework required — pytest already installed

---

## Security Domain

`security_enforcement` not explicitly set to `false` in `.planning/config.json`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Clamp tolerance sigma to [0, max_reasonable]; validate N ensemble size [1, 500] |
| V6 Cryptography | no | — |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unreasonably large N (e.g. N=100000) as DoS | DoS | Clamp N to [1, 500] at dialog level; same pattern as uq_batches clamp in Wave 2 |
| Negative sigma / NaN sigma from JSON import | Tampering | `max(0.0, value)` clamp in `_dict_to_src` and `load_project` |
| Ensemble member seed overflow (int32 on Windows) | Tampering | Apply `& 0x7FFFFFFF` mask; established in Phase 4 Wave 2 signed-int32 fix (STATE.md) |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | OAT sensitivity with k+1 runs is adequate for the 3 v1 parameters | Sensitivity Method recommendation | Would need Sobol or Morris for reliable ranking; low risk since v1 scope is limited to 3 params |
| A2 | At N=200, storing N Project clones uses ~10-40 MB — acceptable | Worst-case drill-down recommendation | If scenes are much larger (many solid bodies, many surfaces), memory could exceed 100 MB; mitigate by capping stored variants at top-10 outliers |
| A3 | `scipy.stats.qmc.Sobol` in scipy 1.17.1 produces scrambled Sobol sequences suitable for Saltelli Si estimation | Sobol full mode | If the scipy Sobol implementation has a known bug for certain k values, Saltelli Si may be biased; mitigate by adding a unit test that verifies Si sums to ~1.0 for a known linear model |

---

## Open Questions (RESOLVED)

1. **Does the Geometry Builder dialog (gui/geometry_builder.py) currently write back to project.cavity_recipe?**
   - What we know: `io/geometry_builder.py::build_cavity()` takes explicit kwargs and modifies `project.surfaces`. The GUI wrapper (`gui/geometry_builder.py`) calls it.
   - What's unclear: Whether the GUI dialog stores the kwargs anywhere on the project after calling `build_cavity()`.
   - Recommendation: Read `gui/geometry_builder.py` during planning Wave 0. If it doesn't write a recipe, add a `record_recipe=True` parameter to `build_cavity()` as part of Wave 1.
   - **RESOLVED:** No — `gui/geometry_builder.py` does not currently write back to `project.cavity_recipe`. Plan 04 Task 1 adds `record_recipe=True` to the `build_cavity()` call in the GUI builder, which triggers the `record_recipe` flag added to `io/geometry_builder.py::build_cavity()` in Plan 02 Task 2.

2. **Sensitivity display when multiple KPIs are active (efficiency, uniformity, hotspot all at once)?**
   - What we know: The sensitivity table will have rows = parameters, columns = KPI sensitivity.
   - What's unclear: Which KPI the user wants to optimize is user preference.
   - Recommendation: Default to showing uniformity sensitivity as the primary column; allow KPI selector combo above the table (same pattern as convergence_tab uses a KPI selector combo).
   - **RESOLVED:** Default display column is `uniformity_1_4_min_avg`. A KPI selector combo above the sensitivity table allows switching (same pattern as the histogram KPI selector in the Distribution tab). Implemented in Plan 03 Task 2.

---

## Sources

### Primary (HIGH confidence)

- `backlight_sim/core/sources.py` — PointSource field layout, `flux_tolerance`, `effective_flux` [VERIFIED: read in session]
- `backlight_sim/core/project_model.py` — SimulationSettings, Project layout [VERIFIED: read in session]
- `backlight_sim/core/kpi.py` — `compute_scalar_kpis`, `compute_all_kpi_cis` signatures [VERIFIED: read in session]
- `backlight_sim/core/uq.py` — `CIEstimate`, `batch_mean_ci` [VERIFIED: read in session]
- `backlight_sim/sim/tracer.py` — `run()`, `_run_multiprocess`, `_serialize_project`, `_project_uses_cpp_unsupported_features`, RNG seeding [VERIFIED: read in session]
- `backlight_sim/io/geometry_builder.py` — `build_cavity()` signature (L15-26) [VERIFIED: read in session]
- `backlight_sim/io/project_io.py` — serialization/deserialization patterns, `.get(key, default)` usage [VERIFIED: read in session]
- `backlight_sim/gui/parameter_sweep_dialog.py` — `_SweepThread`, cancel pattern, `step_done` signal [VERIFIED: read in session]
- `backlight_sim/gui/widgets/collapsible_section.py` — `CollapsibleSection` API [VERIFIED: read in session]
- `backlight_sim/gui/main_window.py` — `_variants` dict, `_clone_as_variant`, `_load_variant` [VERIFIED: read in session]
- `.planning/phases/05-geometry-tolerance-monte-carlo/05-CONTEXT.md` — all locked decisions [VERIFIED: read in session]
- `.planning/STATE.md` — Phase 04 decisions including signed-int32 seed mask, flux jitter pre-serialization [VERIFIED: read in session]
- scipy 1.17.1 `scipy.stats.qmc.Sobol` import test [VERIFIED: python import + random() call in session]
- Environment benchmark: 22 ms/run at 2k rays, 110 ms/run at 10k rays [VERIFIED: timed in session]
- Test suite: 240 tests, all passing [VERIFIED: pytest in session]

### Secondary (MEDIUM confidence)

- Saltelli (2002) Sobol pick-freeze estimator formula — standard reference for `scipy.stats.qmc` usage with A/B matrix design
- pyqtgraph 0.14.0 `BarGraphItem.setOpts()` for live histogram update [VERIFIED: hasattr check; API confirmed by pyqtgraph source code pattern]

### Tertiary (LOW confidence)

- None.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified in environment
- Architecture: HIGH — all anchor files read; integration points confirmed against actual code
- Pitfalls: HIGH — derived from reading actual code and established decisions in STATE.md
- Sensitivity methods: MEDIUM — OAT/Sobol math is standard; scipy Sobol QMC verified; Saltelli estimator formula is well-known but not re-derived in this session

**Research date:** 2026-04-19
**Valid until:** 2026-05-19 (stable domain — no fast-moving dependencies)
