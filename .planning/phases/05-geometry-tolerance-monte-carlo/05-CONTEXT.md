# Phase 5: Geometry Tolerance Monte Carlo — Context

**Added:** 2026-04-18
**Discussed:** 2026-04-18
**Status:** Ready for planning (planning can start; execution blocks on Phase 4)

## Phase Boundary

Randomize geometry and source parameters within user-specified tolerances and run an ensemble sim. Output: KPI distributions (P5/P50/P95) across the ensemble, plus sensitivity ranking per parameter. Scope ends at ensemble analysis — no automated tolerance-tightening loop (that's for Phase 6 inverse design).

## Why

Real BLUs fail from tolerance stack-up (LED placement drift, cavity depth variation, wall-angle tolerance, LED flux binning), not nominal design. Engineers currently see "uniformity = 88%" and commit to a spec, only to find the factory yield is 60% once tolerances hit. Engineers need to know *which* tolerances dominate yield before tightening the wrong spec.

## Scope

- **Tolerance spec per parameter:** extend `PointSource`, `Rectangle`, `DetectorSurface`, and cavity-builder params with optional tolerance fields. Existing `flux_tolerance` on sources stays; new fields added for position (dx/dy/dz), orientation (dθ), and geometry dimensions.
- **Distribution choice:** gaussian (default) or uniform per tolerance.
- **UI:** tolerance columns/fields in property forms; visual indicator on objects that have tolerances.
- **Ensemble runner:** new dialog analogous to `parameter_sweep_dialog` but samples N realizations from tolerance distributions instead of gridding. Runs in background QThread with progress + cancel.
- **Outputs:**
  - KPI distribution histograms + P5/P50/P95 per KPI.
  - Worst-case realization drill-down (click a histogram bin → load that realization as a variant).
  - Sensitivity index per tolerance (Sobol first-order, or simple one-at-a-time for cheap mode).
- **Reuses Phase 4 UQ plumbing:** each ensemble member inherits MC-variance error bars; ensemble variance (from tolerances) must be distinguishable from MC variance (from ray noise) in reports.

## Out of Scope

- Robust design optimization (that's Phase 6 consuming this as an objective).
- Correlated tolerances (covariance between parameters) — start with independent.
- Temperature-dependent tolerances (would need thermal model from Phase 7).
- Generic `Rectangle` pose tolerances (floor, walls-as-Rectangles, diffuser plane) — deferred to a v2 of this phase; v1 reaches wall-angle drift via the cavity build-recipe path instead.

## Depends On

- **Phase 4 (UQ) — HARD BLOCKER for execution.** Planning of Phase 5 may proceed in parallel; execution must wait until Phase 4's CI plumbing is real code. See D-07 below for the prerequisites Phase 4 must deliver.

## Implementation Decisions

### v1 Toleranced Parameter Scope (D-01)

Phase 5 v1 simulates **three** manufacturing failure modes:

- **D-01a: LED position drift** — per-`PointSource` dx/dy/dz jitter. Every LED in a grid draws its own independent offset per ensemble member.
- **D-01b: LED flux / binning drift** — re-use existing `PointSource.flux_tolerance` (±%). Current behavior applies jitter once at tracer run; under the ensemble sampler, jitter is re-drawn per realization. No new field on `PointSource` for flux.
- **D-01c: Cavity wall-angle + depth drift** — tolerances attached to the cavity **build recipe** (see D-03), not to the resulting wall `Rectangle` objects.

**Deferred to a later phase** (noted in "Out of Scope" above): generic `Rectangle` pose tolerances on arbitrary surfaces, detector pose tolerance, diffuser-plane pose tolerance, material property tolerances (reflectance, transmittance).

### LED Position Tolerance Specification (D-02)

- **Project-level default + per-source override.**
- `SimulationSettings` (or equivalent) gets a default `source_position_sigma_mm` field (scalar — isotropic 3D σ) applied to every enabled `PointSource`.
- Individual `PointSource` objects may override via optional per-source sigma fields.
- UI surfaces the default as a single number in a project/settings panel; per-source override lives under a new collapsible tolerance subsection in `SourceForm`.
- Rationale: engineers spec "our LED placement tolerance is ±0.15 mm" once for the PCB, but occasionally need to mark a hand-placed LED tighter.

### Cavity Tolerance Via Build Recipe (D-03)

- `Project` must persist the **original `build_cavity()` arguments** (length_x, length_y, depth, wall_angle_x, wall_angle_y, etc.) alongside their tolerances, not just the resulting `Rectangle` surfaces.
- Each ensemble realization re-invokes `io/geometry_builder.build_cavity(**jittered_args)` and replaces the cavity Rectangles in a cloned project.
- Mirrors manufacturing reality: a molded cavity whose wall angle drifts moves *all four walls* coherently, not independently.
- Required sub-decision for planning: how to round-trip the build recipe through project JSON save/load without breaking the existing backwards-compat `.get(key, default)` pattern.

### Tolerance Units (D-04)

- **Absolute units everywhere** for geometry: position tolerances in mm, angle tolerances in degrees, depth tolerances in mm.
- **Exception:** `flux_tolerance` keeps its existing ±% unit — LED bins are intrinsically relative and the field is already shipped.
- No per-field unit toggle. Matches mechanical GD&T conventions and keeps JSON schema narrow.

### Distribution Shape Per Tolerance (D-05)

- Gaussian (default) or uniform, **per-tolerance-field** (locked from existing CONTEXT).
- Gaussian uses the user's value as σ (not 3σ or FWHM) — document this in the tolerance-field tooltip to prevent misinterpretation.

### Phase 4 Dependency Handling (D-06)

- **Execution of Phase 5 is hard-blocked on Phase 4 execution** (see D-07).
- Phase 5 **planning** may proceed in parallel; plans can reference Phase 4's planned API by name, and the plan-checker gate confirms the API surface before execution begins.
- No stub CI in Phase 5. Ensemble variance vs MC variance separation relies entirely on Phase 4's batch-CI output.

### Phase 4 Prerequisites Locked For Phase 5 (D-07)

Phase 4 **MUST** deliver both of the following before Phase 5 execution starts. This is non-negotiable from Phase 5's perspective:

1. **Pure KPI extractor:** a single function `compute_kpis(result: SimulationResult, project: Project) -> dict[str, float]` (or dataclass equivalent) that returns every shipping KPI — uniformity (at each center fraction), peak luminance, efficiency, hotspot ratio, NRMSE, edge-center ratio, design score. No Qt/GUI imports. Currently this logic is tangled in `gui/heatmap_panel.py` (`_uniformity_in_center`, `_corner_ratio`, `_edge_center_ratio`, inline efficiency compute at L600–618, `_update_score` at L694).
2. **`KpiWithCI` data struct:** a stable dataclass carrying `{mean, low, high, n_batches, confidence_level}` per KPI. Used uniformly by the heatmap panel, HTML report, CSV export, sweep dialog, and — in Phase 5 — the ensemble histogram and the per-realization drill-down.

If Phase 4 lands without both, Phase 5 planning re-opens.

### Claude's Discretion

Left to the planner + researcher to decide when plans are written:

- **Tolerance data model shape** — inline fields on each dataclass vs a unified `ToleranceSpec` dataclass vs a sibling `project.tolerances` dict keyed by (object_id, param_name). All three are viable; researcher weighs JSON schema backwards compat and UI implications.
- **Sensitivity method** — Sobol first-order vs one-at-a-time (OAT) vs Morris elementary effects. Trade-off is sample-count budget vs interaction-effect visibility. Suggested default: OAT for "cheap mode" checkbox, Sobol for full runs; planner decides final shape.
- **Ensemble runner UI container** — new dedicated dialog vs extending `parameter_sweep_dialog`. Scout flagged the sweep dialog (497 L) as a reference, not a great container; likely a new dialog, but planner decides.
- **Worst-case drill-down mechanics** — save full Project clone as a variant on click vs reconstruct from stored (seed, member_idx) on demand. Memory vs compute trade-off at N=200.
- **Visual indicator on toleranced objects** — ghosted ±σ wireframe in 3D viewport vs tree-icon badge vs skip in v1. Researcher to propose, planner to pick.
- **Live-streaming histogram during ensemble run** vs post-run display. Probably streaming for UX at large N; planner to confirm.
- **Default ensemble size N** and whether to parallelize ensemble members through the existing `ProcessPoolExecutor` path.

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & Phase Specs
- `.planning/ROADMAP.md` §"Phase 5" — authoritative scope statement.
- `.planning/phases/04-uncertainty-quantification/04-CONTEXT.md` — Phase 4 context; Phase 5 inherits CI plumbing from here. D-07 above locks the Phase 4 API Phase 5 expects.
- `.planning/PROJECT.md` — project principles, core/sim/io headless constraint, backwards-compat JSON `.get(key, default)` pattern.

### Codebase Anchors (read before designing)
- `backlight_sim/core/sources.py` L7–42 — `PointSource`; existing `flux_tolerance` at L17; `effective_flux` property at L26–31. Template for new tolerance fields.
- `backlight_sim/core/project_model.py` L12–51 — `Project` + `SimulationSettings`; where project-level default `source_position_sigma_mm` and the cavity build-recipe fields attach.
- `backlight_sim/io/geometry_builder.py` — `build_cavity()` entry point. Must remain re-invocable per ensemble member with jittered args; no hidden state.
- `backlight_sim/io/project_io.py` — JSON save/load; any new tolerance / build-recipe fields must round-trip and defend backwards compat with `.get()`.
- `backlight_sim/gui/parameter_sweep_dialog.py` (497 L) — `_SweepThread` / `_MultiSweepThread` QThread pattern, progress bar, cancel flag. Template for the ensemble QThread.
- `backlight_sim/gui/properties_panel.py` (1805 L) — `CollapsibleSection` pattern on per-type forms (`SourceForm` L269–527; Thermal/Binning section L345 is the nearest analog for a new tolerance subsection).
- `backlight_sim/gui/heatmap_panel.py` (949 L) — current (tangled) location of KPI computation. Phase 4's compute_kpis extraction reshapes this; Phase 5 consumes the result.
- `backlight_sim/sim/tracer.py` (2981 L) — `RayTracer.run()` L434–470, `_run_multiprocess` L472–523, RNG seeding at L428 (`np.random.default_rng(project.settings.random_seed)`). Ensemble path likely wraps this loop.

### Prior-Phase Decisions That Apply
- **Phase 02 D-09 (hard-crash pattern)** — `blu_tracer` C++ extension is mandatory; no silent Python fallback. Ensemble members on plane-only scenes get the C++ fast path for free.
- **Phase 02 Wave 3** — flux_tolerance jitter applied in Python **before** serializing the project dict to C++. Same pre-serialization pattern extends to geometry-tolerance jitter in Phase 5.
- **Phase 02 dispatch predicate** (`_project_uses_cpp_unsupported_features`) — ensemble members honor this; spectral / solid-body realizations stay on the Python tracer path.

## Existing Code Insights

### Reusable Assets
- `_SweepThread` / `_MultiSweepThread` QThread + progress + cancel pattern (`parameter_sweep_dialog.py`) — direct template for the ensemble runner thread.
- `CollapsibleSection` per-form idiom in `properties_panel.py` — drop-in container for new tolerance subsections.
- `PointSource.flux_tolerance` field + `effective_flux` property — already defends the jitter semantics; Phase 5 reuses, does not refactor.
- `ProcessPoolExecutor` loop in `_run_multiprocess` — natural insertion point for ensemble-member parallelism.

### Established Patterns
- **Headless core/sim/io** — tolerance sampling logic lives in `sim/` (or a new `sim/ensemble.py`), never imports PySide6. GUI only orchestrates.
- **JSON backwards-compat** — every new field uses `.get(key, default)` on load; older projects load without tolerances.
- **Pre-serialization jitter** — for the C++ fast path, jitter is applied to the Python project dict before it crosses the pybind11 boundary. Phase 5 follows this.
- **KPI compute tangle** — today's biggest friction; Phase 4 untangles it, Phase 5 benefits.

### Integration Points
- `Project` JSON schema — new fields: project-level tolerance defaults, per-source position sigma override, cavity build recipe + tolerances.
- `MainWindow` menu — new "Tolerance Ensemble…" entry next to "Parameter Sweep…".
- `heatmap_panel.py` / `plot_tab.py` — new histogram + P5/P50/P95 summary view; may get its own tab.
- `io/report.py` (HTML) + `batch_export.py` (ZIP) — ensemble results extend existing exports.
- 3D viewport (`gui/viewport_3d.py`) — optional visual indicator (Claude's discretion).

## Specific Ideas

- Ensemble histogram should render CI bands per bin (from Phase 4 `KpiWithCI`) so the user sees noise vs tolerance spread at a glance.
- Worst-case drill-down UX: click a low-uniformity bin → "Load this realization as a variant" button. Mirrors the existing variant-cloning idiom.
- Sensitivity table should rank tolerances by normalized first-order index, with a column that flags "you can relax this" (low index) vs "you must tighten this" (high index).

## Deferred Ideas

- **Correlated tolerances** — covariance matrix across parameters. Deferred; v1 is independent only.
- **Temperature-coupled tolerances** — depends on Phase 7 thermal model.
- **Generic Rectangle pose tolerances** (arbitrary floor/wall/diffuser Rectangles) — deferred to a v2 of this phase. V1 hits the important case (cavity) via the build-recipe route.
- **Tolerance data model refactor** — if v1 ships with inline fields and later needs a unified `ToleranceSpec`, that's a follow-up refactor phase.
- **Robust design optimization** (optimize P5 uniformity instead of mean) — Phase 6 consumes this.

---

*Phase: 05-geometry-tolerance-monte-carlo*
*Context discussed: 2026-04-18*
