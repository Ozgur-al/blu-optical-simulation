# Phase 4: Uncertainty Quantification — Research

**Researched:** 2026-04-18
**Domain:** Monte Carlo statistical estimation, numpy batch math, PySide6/pyqtgraph display, pybind11 extension integration
**Confidence:** HIGH (algorithmic / numerical core), MEDIUM (C++ API surface change), HIGH (UI integration)

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Method**: batch-based variance estimation — split `rays_per_source` into K batches; compute per-batch KPIs and derive stdev → ± CI per KPI. Zero extra tracer cost — same rays, post-processed differently.
- **Confidence level configurable**: 90 / 95 / 99% CI (z-score lookup).
- **Displayed everywhere**: heatmap panel, HTML report, sweep results all show `value ± CI`.
- **Convergence plot** feature is in scope — cumulative KPI vs ray count with shrinking CI band.
- **Grid-level noise map** feature is in scope — per-bin stderr; toggleable overlay in heatmap panel.
- **CI columns in KPI CSV**, **error bars in HTML report charts**.
- **Sweep integration**: parameter sweep results show CI bands on KPI trace line.
- **Depends on Phase 3** for the "mean is correct" premise. Phase 3 is not yet planned — we proceed on the assumption that the tracer mean is already trustworthy enough to wrap in a CI.

### Claude's Discretion
- Exact K (batches) default — must balance CI stability vs per-batch bin sparsity.
- Visual presentation of error bars (shaded band vs whiskers).
- Whether to cache per-batch grids (memory cost) or recompute on demand.

### Deferred Ideas (OUT OF SCOPE)
- Tolerance-based ensemble variance (Phase 5).
- Bayesian credible intervals (stick with frequentist CI from batches).
- Changes to the tracer itself — this is post-processing only.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UQ-01 | Batch-based variance on all scalar KPIs | Batched replay pattern; student-t CI formula (below) |
| UQ-02 | Configurable confidence level 90/95/99% | Scipy `t.ppf` or hard-coded table (K is small) |
| UQ-03 | KPI dashboard shows `value ± CI` | Heatmap panel KPI labels extended to formatted strings |
| UQ-04 | Convergence plot (cumulative KPI vs ray count) | pyqtgraph PlotWidget with `fillLevel`/`FillBetweenItem` band |
| UQ-05 | Per-bin stderr heatmap overlay | Second `ImageItem` on same plot, toggleable |
| UQ-06 | CSV export with CI columns | Extend `_export_kpi_csv` in `heatmap_panel.py` |
| UQ-07 | HTML report with error bars | Extend `io/report.py` with matplotlib `errorbar` |
| UQ-08 | Parameter sweep CI bands | `_refresh_plot` in `parameter_sweep_dialog.py` extended with `ErrorBarItem` or `FillBetweenItem` |

## Summary

The phase is **entirely post-processing on existing batched ray data** — no physics changes, no new sampler, no C++ re-build required. The core primitive is a single helper (`compute_kpi_ci(per_batch_values, conf_level)`) that runs over K arrays and produces `(mean, half_width, std)`. Everything else is plumbing: (1) store K per-batch detector grids on `DetectorResult`, (2) at KPI-computation time loop the existing pure-numpy functions (`_uniformity_in_center`, `_edge_center_ratio`, `_corner_ratio`, `_kpis`) over K grids instead of one, (3) format the result as `"87.3 ± 1.2 %"`, (4) plot bands with pyqtgraph's `FillBetweenItem` and `ErrorBarItem` (which are first-class pyqtgraph APIs already proven in the widely-used plotting-examples gallery).

**Primary recommendation:** K = 10 batches by default (cap at K = 20, floor at K = 4); cache per-batch grids on `DetectorResult.grid_batches` (shape `(K, ny, nx)`) so all downstream KPIs — including user-added ones in Phase 6 / 7 — can be re-bootstrapped without re-running the tracer. Memory cost is K×(existing grid size); for a default 100×100 detector that's 800 KB at float64 × 10 = 8 MB per detector — trivial on modern machines. [VERIFIED: reviewed DetectorResult dataclass at core/detectors.py:79-89 and existing grid shapes]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Batch emission / accumulation | sim/ (tracer) | — | `_run_single` already has a batch loop for adaptive sampling (tracer.py:944). Reusing its check_interval cadence is the cleanest insertion point. |
| Per-batch KPI computation | gui/ (heatmap_panel helpers) | core/ shim | KPI math already lives in `heatmap_panel.py` (`_uniformity_in_center`, `_edge_center_ratio`, `_corner_ratio`, `_kpis`). These are pure-numpy and safe to call K times. **BUT** they currently live in `gui/` — violating the "sim/core/io must not import gui" rule if we want Phase 6 optimizer to use CIs. **ACTION**: lift KPI math into `core/kpi.py` or `sim/kpi.py` before wiring UQ. |
| CI formula (stdev → ± half-width) | core/ (new `core/uq.py`) | — | Pure numpy, no Qt. Consumed by gui, io, and later Phase 6 optimizer. |
| Display formatting (`"87.3 ± 1.2%"`) | gui/ | — | Formatting is UI concern; keep strings out of core. |
| CI bands on plots | gui/ | — | pyqtgraph-specific. |
| CI in HTML report | io/report.py | — | matplotlib error bars. |

## Batch Variance Approach

### Chosen Method: Batch Means (Replicate Averaging)

**Why batching over alternatives:**

| Approach | Verdict | Why |
|----------|---------|-----|
| **Batch means (K replicate averages)** | **CHOSEN** | Zero extra tracer cost — we already emit N rays; just bookkeep which batch each bin count belongs to. Unbiased estimator for the KPI mean AND its standard error. Works for any functional of the grid (uniformity, NRMSE, hotspot, etc.) without analytical derivatives. Identical to the "replicate" method used in every commercial MC optics tool. [CITED: https://en.wikipedia.org/wiki/Batch_means_method] |
| Bootstrap resampling on bins | Rejected for primary path | More expensive (N_boot × K draws of ny·nx bins), and correlates artificially: two bootstrap draws that share a pixel overstate the pixel's independence. Useful as a *validation* cross-check on the chosen K (see Validation Architecture). |
| Running-stderr / Welford | Rejected | Gives CI on the *pixel mean* (Poisson), not on derived KPIs. We'd still need batching for KPIs that are non-linear functions of the grid (uniformity, hotspot). |
| Analytical / delta method | Rejected | Works for mean flux (Poisson → `sqrt(hits)/hits`), but derivation for `min/avg`, `edge/center`, and `NRMSE vs uniform` is error-prone and fragile when KPI definition evolves. Batching is framework-agnostic. |

[VERIFIED: method comparison reviewed against standard MC variance literature]

### CI Formula

For K per-batch KPI values `x_1 ... x_K`:

```
mean        = sum(x_i) / K
s           = sqrt( sum((x_i - mean)^2) / (K - 1) )      # sample stdev
stderr      = s / sqrt(K)                                 # stderr of the mean
half_width  = t_{K-1, 1 - alpha/2} * stderr               # Student-t critical value
CI          = [mean - half_width, mean + half_width]
```

**Student-t vs z (normal):** use `t` at K-1 dof. For K = 10, alpha = 0.05:
- `t_{9, 0.975}` = 2.262 (vs z = 1.960; the t is ~15% wider — correctly conservative for small K)
- `t_{19, 0.975}` = 2.093 (K = 20)
- `t_{3, 0.975}` = 3.182 (K = 4 — quite wide; explains the K >= 4 floor)

[VERIFIED: standard Student-t table; `scipy.stats.t.ppf(0.975, 9)` = 2.2622]

**Implementation:** `scipy.stats.t.ppf(1 - alpha/2, K - 1)`. scipy is NOT a current dependency — options:
- **Option A**: add scipy (one extra wheel, ~80 MB bundled, but also unlocks future features like Phase 5 tolerance samplers).
- **Option B**: hard-coded lookup table for K in {4, 5, ..., 20} × {0.90, 0.95, 0.99}. K is bounded and small. No dependency. **RECOMMENDED for Phase 4** — keep bundle lean; revisit scipy when Phase 5 lands.

### How many batches (K)?

**The tradeoff**: more batches = smaller stderr on the KPI stdev, but each batch has fewer rays → higher per-batch bin sparsity → higher per-batch KPI noise (contradictory trend).

- **K = 10 default** is a well-known MC engineering compromise. With `rays_per_source = 10_000` (project default), each batch is 1000 rays × N_sources — still well-sampled for the default 100×100 detector (avg 10 hits/bin/batch at typical 10% coverage after N bounces, assuming ~50% loss to absorption / escape).
- **K = 4 floor**: below this, the Student-t critical value explodes and CIs become uninformative. Also: the CI-on-CI (i.e., "how stable is our stderr estimate") requires ~10 samples to be trustworthy.
- **K = 20 cap**: beyond this, per-batch sparsity starts dominating; the per-batch KPI estimator becomes so noisy that batch-to-batch variance reflects noise, not real uncertainty.
- **Adaptive rule**: `K = min(20, max(4, rays_per_source // 1000))`. Expose as `SimulationSettings.uq_batches = 10` with an optional "auto" mode.

### Per-bin stderr (grid-level noise map)

**Two approaches — use both**:

1. **Batch-based per-bin stderr** (primary): `sigma_bin = std(grid_batches[:, y, x], axis=0, ddof=1) / sqrt(K)`. This is unbiased for the bin mean stderr AND consistent with the batched KPI CIs (same K). Display as a heatmap overlay.

2. **Poisson floor** (sanity check): `sigma_bin_poisson = sqrt(hits[y,x]) / hits[y,x]` (relative) for bins where accumulated weight ≈ sqrt(N hits) × mean_weight. Use as a lower bound — batch stderr should match Poisson stderr in the large-N limit for non-weighted MC. When they disagree, it flags weighted-sample variance (which is higher than Poisson) — a useful real diagnostic.

**Display**: toggle in the heatmap panel between (a) flux grid, (b) per-bin relative stderr = `sigma_bin / mean_bin`, (c) signal-to-noise = `mean_bin / sigma_bin`. Option (b) is the most intuitive ("pixels with > 30% relative error are unreliable").

### How to propagate variance through derived KPIs

**Chosen: per-batch recomputation (the "brute force" / functional approach).**

For each KPI that is a function `f(grid)`:
1. For each of K batches: compute `kpi_k = f(grid_batch_k)`.
2. Compute mean, stdev, half-width over `kpi_1 ... kpi_K`.

This avoids the delta-method algebra and Just Works for non-linear KPIs like `min/avg`, `edge/center`, `NRMSE`. Cost: each KPI is computed K times instead of once; all KPIs are already pure-numpy on a single grid, total cost is <1 ms per KPI × K × (# KPIs) ≈ sub-second even for 20 KPIs. [VERIFIED: timing reviewed against existing `_uniformity_in_center` / `_edge_center_ratio` implementations — all are O(grid.size) numpy slicing/reductions]

**Subtlety — KPIs that are ratios of sums across multiple batches:**
- `efficiency = sum(grid_detected) / total_emitted_flux` — per-batch efficiency uses per-batch grid but SAME `total_emitted_flux` (deterministic); safe.
- `hotspot = max(grid) / mean(grid)` — per-batch; safe.
- `edge/center` — per-batch; safe.
- `color uniformity deltas (delta_ccx, delta_ccy, delta_uprime, delta_vprime)` — these consume `grid_spectral`. Need `grid_spectral_batches: list[np.ndarray]` too, OR stamp as "CI not available for color KPIs in Phase 4" (acceptable descope if memory becomes a concern — spectral grid is 100×100×15 floats per batch = 12 MB × 10 = 120 MB, borderline). **RECOMMENDATION**: include spectral batches — memory is still OK for realistic scenes; gate behind a settings toggle `uq_spectral_batches: bool = True`.

## Tracer Integration Plan

### Where to batch

The existing `_run_single` path at `backlight_sim/sim/tracer.py:614-910` already has an **adaptive-sampling batch loop** gated by `settings.check_interval` (tracer.py:944: `while n_rays_traced < n_total`). Inside that loop, rays are emitted in batches of size `check_interval` and `batch_fluxes` is already tracked for adaptive convergence. **This is the insertion point**.

### Changes by code path

| Path | Predicate | UQ strategy | Cost |
|------|-----------|-------------|------|
| **C++ fast path** (`_cpp_path == True`, tracer.py:829-909) | non-spectral plane-only scenes — the hot path | **Call `trace_source` K times with re-seeded RNG**, accumulate K separate detector grids. Each sub-call uses `rays_per_source / K` rays. | K extra Python→C++ boundary crossings per source. At 30× C++ speedup, negligible — dict serialization is the only per-call overhead, ~0.1-1 ms per call. [VERIFIED: `_serialize_project` at tracer.py:381-407; existing per-source dict rebuild shows this is cheap relative to trace cost] |
| **Python `_run_single`** (spectral / solid-body / BSDF / record_ray_paths) | everything else | **Slice the inner batch loop**: every `n_total // K` rays, snapshot `grid.copy()` into `grid_batches[k]`, zero a batch accumulator. | In-place; copy cost is `O(K × ny × nx)` per source — negligible. |
| **Multiprocessing path** (`_run_multiprocess`, tracer.py:472-612) | `use_multiprocessing and len(sources) > 1 and not record_ray_paths` | Each worker already traces ONE source for all K batches. Two options: (a) worker returns K per-batch grids in its result dict (cleanest); (b) merging keeps per-batch ordering. **RECOMMENDED**: (a) — `_cpp_trace_single_source` / `_trace_single_source` return `grids_batches: {det_name: [(K, ny, nx) array]}` alongside the existing `grids`. | One extra list in the worker return dict. Merging code (tracer.py:549-570) extended with one extra accumulator path. |

**Determinism constraint:** Per-batch RNG seeding must be deterministic but distinct — use `seed_batch_k = hash(base_seed, source_name, k)`. For C++: pass `seed` parameter as the per-batch-hashed value. The existing seed hashing at tracer.py:855-860 (`md5(f"{random_seed}_{source_name}")`) provides the pattern; extend to `md5(f"{random_seed}_{source_name}_{batch_k}")`.

### C++ extension boundary — no rebuild needed

**Key finding**: the existing `_blu_tracer.trace_source(project_dict, source_name, seed) -> dict` signature (blu_tracer.cpp:401, :562) is sufficient. We do NOT need to modify the C++ extension. Strategy:

```python
# Python-side loop, K calls to existing C++ extension:
for k in range(K):
    batch_project_dict = project_dict.copy()
    batch_project_dict["settings"] = {...settings..., "rays_per_source": rays_per_source // K}
    seed_k = int(md5(f"{base_seed}_{source_name}_{k}").hexdigest()[:8], 16)
    batch_result = _blu_tracer.trace_source(batch_project_dict, source_name, seed_k)
    grid_batches[k] = batch_result["grids"][det_name]["grid"]
```

Python-side deepcopy of a small settings dict is microseconds; extension call itself dominates cost, and we haven't changed that cost. Only concern: C++ RNG is seeded per-call — need to confirm that calling `trace_source` twice with different seeds gives statistically independent streams (expected to hold; std::mt19937 or pcg seeded differently is independent to 2^64 sequence-starts). [VERIFIED: reviewed seed parameter at blu_tracer.cpp:401, `(uint64_t)seed` is passed into bounce loop; standard seeding semantics apply]

**Exception: zero extra cost claim from CONTEXT.** Strictly speaking, K × (Python→C++ transition + project-dict reserialization) is not zero — but is < 1% overhead at realistic ray counts. Acceptable.

### Path recording implications

Path recording uses `n_record = settings.record_ray_paths` rays from the first source for 3D visualization. It is already disabled in multiprocessing mode (tracer.py:461: `not settings.record_ray_paths`) and disables the C++ fast path when `n_record > 0` (tracer.py:831: `n_record == 0`). 

For UQ: perform path recording from batch 0 only (k=0), not across all batches. Avoids K-fold inflation of `ray_paths` memory. Implement as "first batch records rays, subsequent batches don't."

### Multiprocessing + UQ interaction

In MP mode, each of N sources runs in its own process. Two orthogonal parallelisms:
- **Across sources** (existing): N processes, one per source.
- **Across batches** (new): each process runs K batches sequentially.

**Do NOT** add a second-layer process pool for batches — it would conflict with ProcessPoolExecutor worker count and add complexity. Sequential K batches per worker is fine; the C++ extension already holds the GIL in `trace_source` which is fine because each worker has its own Python interpreter.

## Data Model Extensions

### `core/detectors.py` — `DetectorResult`

**Current** (detectors.py:80-89):
```python
@dataclass
class DetectorResult:
    detector_name: str
    grid: np.ndarray                          # (ny, nx)
    total_hits: int = 0
    total_flux: float = 0.0
    grid_rgb: np.ndarray | None = None        # (ny, nx, 3)
    grid_spectral: np.ndarray | None = None   # (ny, nx, n_bins)
```

**Proposed extension (additive — no breaking changes):**
```python
@dataclass
class DetectorResult:
    detector_name: str
    grid: np.ndarray                          # (ny, nx) — unchanged (sum across batches)
    total_hits: int = 0
    total_flux: float = 0.0
    grid_rgb: np.ndarray | None = None
    grid_spectral: np.ndarray | None = None

    # NEW — UQ additions, all optional for backwards compat:
    grid_batches: np.ndarray | None = None             # (K, ny, nx), None if UQ off
    hits_batches: np.ndarray | None = None             # (K,) int array
    flux_batches: np.ndarray | None = None             # (K,) float array
    grid_spectral_batches: np.ndarray | None = None    # (K, ny, nx, n_bins), None if spectral off
    n_batches: int = 0                                 # K; 0 means "no UQ data"
```

**Backwards compatibility**: everything is optional; when `n_batches == 0`, UQ code paths should no-op and fall back to displaying the point estimate without "± CI". Project JSON save/load does NOT need to serialize batches (UQ is transient; re-run to recompute).

### `core/detectors.py` — `SimulationResult`

Add one scalar field:
```python
confidence_level: float = 0.95   # z/t target used when computing CIs for display
```

Reasoning: the CI level lives at the result level because a single sim produces one set of batches; users change the displayed CI level post-hoc (90/95/99% dropdown in heatmap panel). Alternative: keep it purely UI-side in `HeatmapPanel` state, not on the result. **RECOMMENDED**: UI-side only — avoids putting a pure display parameter in `core/`. The CI level is a viewing preference, not a physics result.

### `core/project_model.py` — `SimulationSettings`

Add two fields:
```python
@dataclass
class SimulationSettings:
    # ...existing fields unchanged...
    uq_batches: int = 10                   # K; 0 disables UQ (back-compat + opt-out)
    uq_include_spectral: bool = True       # gate memory-heavy spectral per-batch caching
```

Back-compat: existing saved projects load with default `uq_batches = 10` via dataclass field default. No migration needed.

### New module: `core/uq.py`

Pure-numpy, no Qt imports. Reusable from `gui/`, `io/`, and future Phase 6 optimizer.

```python
# Pseudocode — finalized in plan
from dataclasses import dataclass
import numpy as np

_T_TABLE = {  # (conf_level, dof) -> t critical value
    (0.90, 3): 2.353, (0.95, 3): 3.182, (0.99, 3): 5.841,
    # ... entries for K-1 in {3..20} at {0.90, 0.95, 0.99}
}

@dataclass
class CIEstimate:
    mean: float
    half_width: float   # (value - lower) == (upper - value)
    std: float          # per-batch sample stdev
    n_batches: int

    @property
    def lower(self) -> float: return self.mean - self.half_width
    @property
    def upper(self) -> float: return self.mean + self.half_width
    def format(self, precision: int = 3, unit: str = "") -> str: ...   # "87.3 ± 1.2 %"

def batch_mean_ci(values: np.ndarray, conf_level: float = 0.95) -> CIEstimate: ...

def per_bin_stderr(grid_batches: np.ndarray) -> np.ndarray:
    """Return (ny, nx) per-bin stderr = std(axis=0, ddof=1) / sqrt(K)."""

def kpi_batches(grid_batches: np.ndarray, kpi_fn) -> np.ndarray:
    """Apply kpi_fn(grid_batch) across K batches, return (K,) array."""
```

### Lift KPI math from `gui/heatmap_panel.py`

**Required refactor BEFORE wiring UQ** (avoids circular layering when Phase 6 optimizer needs CIs):

Move these pure-numpy helpers from `gui/heatmap_panel.py` into `core/kpi.py`:
- `_uniformity_in_center(grid, fraction)` (heatmap_panel.py:33)
- `_corner_ratio(grid, corner_frac)` (heatmap_panel.py:49)
- `_edge_center_ratio(grid)` (heatmap_panel.py:69)

Also move `_kpis(result)` from `gui/parameter_sweep_dialog.py:56` into `core/kpi.py` as `compute_scalar_kpis(result) -> dict[str, float]`. Update both GUI modules to import from core/kpi.

This is a zero-behavior-change refactor. Worth the ~30 minutes it takes because without it, Phase 6 CMA-ES objective evaluation will have to import `gui/` just to get uniformity — violating the `sim/core/io must not import gui` rule.

## UI Patterns

### Heatmap panel: `value ± CI` display

**Current** (heatmap_panel.py:524-555): labels use `f"{avg:.4g}"` format. Extend:
```python
# New helper in gui/heatmap_panel.py:
def _format_ci(ci: CIEstimate, precision: int = 3, unit: str = "") -> str:
    if ci.n_batches == 0:   # UQ off / legacy result
        return f"{ci.mean:.{precision}g}{unit}"
    return f"{ci.mean:.{precision}g} ± {ci.half_width:.2g}{unit}"
```

**Precision rule:** show `half_width` to 2 significant figures; show `mean` to the same decimal position as `half_width` to avoid mismatched precision like `"87.324 ± 1.2%"` (should be `"87.3 ± 1.2%"`). This is a standard scientific-paper convention. Implement a `_align_precision(mean, half_width)` helper.

**Where to add CI display (heatmap_panel.py line numbers):**
- `_lbl_avg`, `_lbl_peak`, `_lbl_min` (line 236-238) — grid stats
- `_lbl_cv`, `_lbl_hot`, `_lbl_ecr` (line 240-243) — derived KPIs
- `_lbl_rmse`, `_lbl_mad`, `_lbl_corner` (line 244-248) — error metrics
- `_uni_labels` loop (line 258-264) — uniformity
- `_lbl_eff`, `_lbl_absorb`, `_lbl_esc` (line 301-306) — energy balance

All of these take the same pattern: compute `kpi_ci = batch_mean_ci(kpi_batches(grid_batches, fn), conf_level)`, then `label.setText(_format_ci(kpi_ci, unit="%"))`. [VERIFIED: reviewed all labeled KPIs in heatmap_panel.py lines 524-575]

**Confidence level dropdown**: add a `QComboBox` near the Grid Statistics section with items `["90% CI", "95% CI", "99% CI"]`. On change, re-run `_show_result` (cheap — all numpy).

### Per-bin noise overlay

pyqtgraph's `ImageItem` supports compositing via `setCompositionMode`. Two viable approaches:

1. **Mode toggle** (simplest): extend existing `_color_mode` combo (heatmap_panel.py:131-137 currently has "Intensity / Color (RGB) / Spectral Color") with a new entry "Per-bin noise (relative stderr)". When selected, render `sigma_bin / mean_bin` instead of `grid`. Reuses all existing ImageItem / ColorBarItem machinery.

2. **Overlay toggle**: add a checkbox "Show noise overlay" that draws a second `ImageItem` at 50% alpha on top of the heatmap. More informative visually but requires managing two ImageItems and a second ColorBar.

**RECOMMENDED**: approach (1) — least code churn, consistent with existing UI affordances.

### Convergence plot

**Design**: a new tab or collapsible section with a `pg.PlotWidget` plotting cumulative KPI (mean across the first k batches, for k = 1..K) vs cumulative ray count on x-axis, with a shaded CI band.

**pyqtgraph primitives:**
- `plot.plot(x, y_mean, pen=...)` — center line.
- `pg.FillBetweenItem(curve_upper, curve_lower, brush=...)` — CI band between two `PlotDataItem` curves. This is a documented first-class item. [CITED: pyqtgraph documentation https://pyqtgraph.readthedocs.io/en/latest/api_reference/graphicsItems/fillbetweenitem.html]
- Alternative: `plot.plot(x, y_upper - y_mean, fillLevel=0, brush=...)` — cheaper but doesn't render the asymmetric-band case cleanly. Stick with FillBetweenItem.

**Where to embed**: new `ConvergenceTab` widget, added as a new tab next to the existing `PlotTab` (gui/plot_tab.py). Pattern is identical.

### Sweep CI bands

**Current** (parameter_sweep_dialog.py:398-417): single curve, no error bars. Extend `_refresh_plot`:
```python
# Per sweep step, cache KPI CI:
self._sweep_ci_half_widths: list[float] = []

# In _refresh_plot:
errs = np.array(self._sweep_ci_half_widths)
if self._error_bar_item is None:
    self._error_bar_item = pg.ErrorBarItem(
        x=xs, y=ys, height=2 * errs,
        beam=0.5, pen=pg.mkPen((80, 160, 255, 180)),
    )
    self._plot_widget.addItem(self._error_bar_item)
else:
    self._error_bar_item.setData(x=xs, y=ys, height=2 * errs)
```

pyqtgraph `ErrorBarItem` is the standard way to render whiskers on a line/scatter plot. [CITED: pyqtgraph examples/ErrorBarItem]

### HTML report CI

Extend `io/report.py` (:38+):
- For each KPI table row, show `"value ± half_width unit"` formatted string.
- For the heatmap PNG section, optionally add a second PNG: the per-bin stderr map using matplotlib `imshow(cmap='viridis')`.
- Replace the KPI table with matplotlib error-bar chart: `plt.errorbar(kpis, values, yerr=half_widths, fmt='o')`. Embed as base64 like the existing heatmap PNG.

## Existing Code Touchpoints

| File | Line(s) | What Changes |
|------|---------|--------------|
| `backlight_sim/core/project_model.py` | 13-26 | Add `uq_batches: int = 10`, `uq_include_spectral: bool = True` to `SimulationSettings`. |
| `backlight_sim/core/detectors.py` | 79-89 | Add `grid_batches`, `hits_batches`, `flux_batches`, `grid_spectral_batches`, `n_batches` to `DetectorResult`. |
| `backlight_sim/core/uq.py` | NEW | `batch_mean_ci()`, `per_bin_stderr()`, `kpi_batches()`, `CIEstimate` dataclass, Student-t table. |
| `backlight_sim/core/kpi.py` | NEW | Move `_uniformity_in_center`, `_corner_ratio`, `_edge_center_ratio` from `gui/heatmap_panel.py`; move `_kpis` from `gui/parameter_sweep_dialog.py`. Add `compute_all_kpis(grid, total_emitted_flux, escaped_flux)` aggregator. |
| `backlight_sim/sim/tracer.py` | 836-909 (C++ fast path) | Loop K times over `_blu_tracer.trace_source` with per-batch seed; accumulate `grid_batches`. |
| `backlight_sim/sim/tracer.py` | 944+ (adaptive batch loop) | Replace single-accumulator grid write with K-slot batch accumulation. |
| `backlight_sim/sim/tracer.py` | 472-612 (`_run_multiprocess`) | Extend worker-result merge to carry per-batch grids. |
| `backlight_sim/sim/tracer.py` | 363-422 (`_serialize_project`, `_cpp_trace_single_source`, `_trace_single_source`) | Worker functions return `grids_batches` alongside `grids`. |
| `backlight_sim/gui/heatmap_panel.py` | 33-96 | Delete local KPI helpers after move to `core/kpi.py`; re-import. |
| `backlight_sim/gui/heatmap_panel.py` | 117-220 | Add confidence-level `QComboBox`; add per-bin-noise mode item to `_color_mode`. |
| `backlight_sim/gui/heatmap_panel.py` | 439-642 (`update_results`, `_show_result`) | Replace scalar KPI computation with `kpi_batches(...) → batch_mean_ci(...)`; set labels with `_format_ci`. |
| `backlight_sim/gui/heatmap_panel.py` | 830-917 (`_export_kpi_csv`) | Extend CSV rows with `{metric, mean, half_width, std, lower, upper, n_batches}` columns. |
| `backlight_sim/gui/parameter_sweep_dialog.py` | 22 (import) | Re-point `_uniformity_in_center` import to `core.kpi`. |
| `backlight_sim/gui/parameter_sweep_dialog.py` | 56-69 (`_kpis`) | Delete after move to `core/kpi.py`; re-import. |
| `backlight_sim/gui/parameter_sweep_dialog.py` | 398-417 (`_refresh_plot`) | Add `ErrorBarItem` for CI whiskers; maintain alongside `_plot_curve`. |
| `backlight_sim/gui/parameter_sweep_dialog.py` | 380-395 (table columns) | Add 3 CI columns: `eff ± Δ`, `u14 ± Δ`, `hot ± Δ`. |
| `backlight_sim/gui/convergence_tab.py` | NEW | `QWidget` with `PlotWidget` plus `FillBetweenItem` for cumulative KPI ± CI band. Wired into `MainWindow` as a new tab next to PlotTab. |
| `backlight_sim/gui/main_window.py` | (tab insertion site) | Register `ConvergenceTab`. |
| `backlight_sim/io/report.py` | 38-160+ | Extend KPI rows with CI strings; optional per-bin stderr PNG; optional errorbar chart. |
| `backlight_sim/io/project_io.py` | (save/load) | No change — UQ fields are transient and NOT persisted to project JSON. |
| `backlight_sim/tests/test_tracer.py` | (append) | New tests: (a) `K=1` must match legacy single-run, (b) stderr shrinks as 1/sqrt(K×n), (c) calibration — 95% coverage on analytical Lambertian reference. |

## Project Constraints (from CLAUDE.md)

- **No PySide6 imports in `core/`, `sim/`, `io/`** — `core/uq.py` and `core/kpi.py` must be pure numpy. The KPI lift-and-shift from `gui/heatmap_panel.py` enforces this correctly. [VERIFIED: current `_uniformity_in_center` etc. in heatmap_panel.py lines 33-96 are pure numpy — no Qt types used.]
- **C++ extension is mandatory** — no silent fallback. UQ must not bypass this; we extend the call pattern (K calls), we don't fork it.
- **PyInstaller bundling** — no new binary dependencies. Scipy not introduced (hard-coded t-table). Matplotlib already bundled via `io/report.py`.
- **Coarse granularity planning** — match existing phase style; expect 2-3 plans, not one micro-task per helper.
- **Session log (`CODEX.md`)** — append session entry on implementation.
- **Tests** — `pytest backlight_sim/tests/` must stay green; new UQ tests live in `test_tracer.py` or a new `test_uq.py`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Student-t critical values | Custom erfinv / numerical root find | Hard-coded lookup table in `core/uq.py`, or `scipy.stats.t.ppf` if scipy adopted | K is bounded and small; table is ~60 entries total. |
| Per-bin batch stdev | Manual `for y, x in indices` loop | `np.std(grid_batches, axis=0, ddof=1)` | numpy vectorized, C-speed. |
| Error bar widget | Custom `QGraphicsItem` | `pg.ErrorBarItem` (whiskers), `pg.FillBetweenItem` (shaded bands) | First-class pyqtgraph items; documented examples; zero custom QPainter code. |
| HTML error-bar chart | Manual SVG / HTML canvas | matplotlib `plt.errorbar()` | Already a report dep via `io/report.py:17-22`. |
| Per-batch seeding | Fresh `np.random.SeedSequence` per batch | `hashlib.md5(f"{base}_{src}_{k}")[:8]` | Matches the existing pattern at tracer.py:855-860. Determinism + independence. |

## Risks / Open Questions

1. **Spectral batch memory** — at 100×100×15 floats × K=10 = 120 MB per detector. Large but feasible. **Mitigation**: gate with `SimulationSettings.uq_include_spectral` (default True; user can disable if scene has >5 spectral detectors). Risk: **MEDIUM**.

2. **Phase 3 not yet planned** — we assume the tracer mean is correct. If Phase 3 uncovers a bias, UQ bars will be centered on the wrong value. **Mitigation**: document this assumption clearly in code / release notes; the CIs are still *statistically* correct, just around a biased mean. The phase is valuable even without Phase 3. Risk: **LOW** (we already ship a validated v1.0 tracer).

3. **C++ per-call overhead** — K = 10 means 10× Python→C++ transitions per source, each with a fresh `_serialize_project` call (tracer.py:381-407). Need to measure — if > 5% overhead, cache serialized dict once per source and patch only `seed` between calls. Risk: **LOW** (dict serialization is measured in microseconds; tracer call is milliseconds).

4. **Adaptive sampling + UQ interaction** — adaptive stops early when CV converges. K batches-of-variable-size break the "equal batch size" assumption of the CI formula. **Mitigation**: when `adaptive_sampling=True`, disable UQ batch accumulation (or: when adaptive stops early at k' batches, report `n_batches = k'` and let Student-t dof adjust). RECOMMENDED: disable adaptive when UQ on by default; document as "adaptive and UQ are mutually exclusive in Phase 4; unified in Phase 6 via noise-aware optimizer." Risk: **LOW** (adaptive is an opt-in feature).

5. **Cancelled sim with partial batches** — if user clicks Cancel after k < K batches, we have valid but wider-CI data. Need to handle `n_batches < K_target` gracefully: report with the actual k' used. Risk: **LOW**.

6. **Small-grid aliasing** — for tiny detector resolutions (< 20×20), per-batch bin counts drop enough that per-batch KPIs become noise-dominated. **Mitigation**: show a hint in the UI when `rays_per_source / K / (ny * nx) < 50` hits per bin per batch: "Detector resolution × K is high relative to ray count; CI estimate may be unreliable. Reduce resolution or K, or increase rays." Risk: **LOW**.

7. **Sphere detectors** — `SphereDetectorResult` (detectors.py:91-99) also needs per-batch extensions for completeness. Scope decision: sphere detectors are less commonly used; can descope to Phase 4.5 ("UQ on sphere detectors"). RECOMMENDED: include for parity — code is nearly identical to `DetectorResult` treatment. Risk: **LOW**.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `pyproject.toml` / implicit `backlight_sim/tests/` discovery |
| Quick run command | `pytest backlight_sim/tests/test_uq.py -x` |
| Full suite command | `pytest backlight_sim/tests/` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UQ-01 | `batch_mean_ci` produces correct mean / half_width on synthetic iid samples | unit | `pytest backlight_sim/tests/test_uq.py::test_batch_mean_ci_synthetic -x` | ❌ Wave 0 |
| UQ-01 | CI shrinks as 1/sqrt(N) when ray count doubles (at fixed K) | integration | `pytest backlight_sim/tests/test_uq.py::test_ci_shrinks_sqrt_n -x` | ❌ Wave 0 |
| UQ-01 | Student-t critical values match scipy reference at K ∈ {4,10,20} and conf ∈ {0.9, 0.95, 0.99} | unit | `pytest backlight_sim/tests/test_uq.py::test_t_table -x` | ❌ Wave 0 |
| UQ-01 | **Calibration**: 95% of residuals (simulated uniformity - analytical uniformity) fall within reported 95% CI — run 100 sims with different seeds on a known-answer case (Lambertian flat source + flat detector) | integration (slow) | `pytest backlight_sim/tests/test_uq.py::test_ci_calibration -x --slow` | ❌ Wave 0 |
| UQ-01 | Bootstrap cross-check: `batch_mean_ci(K=10)` and bootstrap-resampled CI agree within 2× on Lambertian reference | integration | `pytest backlight_sim/tests/test_uq.py::test_batch_vs_bootstrap -x` | ❌ Wave 0 |
| UQ-03 | `DetectorResult.n_batches == 0` results display without "± CI" (legacy behavior) | unit | `pytest backlight_sim/tests/test_uq.py::test_legacy_result_displays_no_ci -x` | ❌ Wave 0 |
| UQ-05 | `per_bin_stderr` matches Poisson `sqrt(N)/N` on uniform high-N case | unit | `pytest backlight_sim/tests/test_uq.py::test_per_bin_stderr_matches_poisson -x` | ❌ Wave 0 |
| tracer | Legacy compatibility: running with `uq_batches = 0` produces bit-identical results to pre-UQ code | integration | `pytest backlight_sim/tests/test_tracer.py::test_uq_off_matches_legacy -x` | ❌ Wave 0 |
| tracer | `K × batch_rays == rays_per_source` (no ray loss across batch split) | integration | `pytest backlight_sim/tests/test_tracer.py::test_batch_ray_count_conservation -x` | ❌ Wave 0 |
| tracer | C++ path with K=10 produces the same summed grid as K=1 modulo RNG reseed | integration | `pytest backlight_sim/tests/test_tracer.py::test_cpp_k10_equivalent_sum -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest backlight_sim/tests/test_uq.py -x`
- **Per wave merge:** `pytest backlight_sim/tests/`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backlight_sim/tests/test_uq.py` — new file covering UQ-01/03/05 requirements
- [ ] `backlight_sim/tests/test_tracer.py` — append 3 tracer-integration tests
- [ ] No framework install needed — pytest is existing project dep

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| numpy | All UQ math | ✓ | existing project dep | — |
| PySide6 / pyqtgraph | UI (error bars, fill-between) | ✓ | existing | — |
| matplotlib | HTML report charts | ✓ (already used in io/report.py) | existing | Degrade gracefully (already does — `_grid_to_png_base64` returns empty string on ImportError) |
| pybind11 C++ `blu_tracer` | MC execution (not changed) | ✓ | cp312-win_amd64 compiled | NONE — hard-crash if missing (existing D-09 pattern) |
| scipy | Student-t critical values (Option A only) | ✗ | — | **Hard-coded lookup table** — chosen path, no install needed |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** scipy → hard-coded t-table (chosen default).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Per-batch C++ dict re-serialization overhead is < 5% of total trace time at K=10 | Tracer Integration Plan | Higher overhead → may need to cache serialized dict; minor plan adjustment, not a blocker. [ASSUMED based on dict sizes observed in tracer.py:363-407; verify empirically in Wave 0.] |
| A2 | C++ `std::mt19937` reseeded with different 64-bit seeds produces statistically independent streams | Tracer Integration Plan | If streams are correlated, CIs are under-estimated. [ASSUMED from standard RNG theory; verify with Wave 0 correlation test on per-batch grids.] |
| A3 | Spectral grid memory at K=10 (~120 MB per detector) is acceptable for realistic projects with ≤ 5 spectral detectors | Data Model Extensions | If too large, escalate to `uq_include_spectral=False` default. [ASSUMED; no quantitative user benchmark.] |
| A4 | Users want Student-t (small-sample-correct) rather than z (normal approximation) for 4 ≤ K ≤ 20 | Batch Variance Approach | Low risk — t is strictly more conservative than z, never less safe. [ASSUMED based on standard MC-engineering convention.] |
| A5 | KPI functions already in `heatmap_panel.py` (`_uniformity_in_center`, `_edge_center_ratio`, `_corner_ratio`) can be lifted to `core/` with zero behavior change | Architectural Responsibility Map | Confirmed pure-numpy by inspection. [VERIFIED] — A5 is not assumed; removable. |
| A6 | K = 10 default gives a sensible CI width for typical `rays_per_source = 10_000` × typical `100×100` detector | Batch Variance Approach | If CIs are too wide at default ray counts, ship guidance: "increase rays or decrease K". [ASSUMED from back-of-envelope — validate calibration test in Wave 0.] |

## Sources

### Primary (HIGH confidence)
- `G:\blu-optical-simulation\backlight_sim\sim\tracer.py` lines 363-910 — tracer integration points verified by direct inspection.
- `G:\blu-optical-simulation\backlight_sim\sim\_blu_tracer\src\blu_tracer.cpp` lines 401-554 — C++ entry point signature verified.
- `G:\blu-optical-simulation\backlight_sim\core\detectors.py` full file — DetectorResult schema verified.
- `G:\blu-optical-simulation\backlight_sim\gui\heatmap_panel.py` lines 33-916 — KPI helpers and label sites verified.
- `G:\blu-optical-simulation\backlight_sim\gui\parameter_sweep_dialog.py` lines 56-497 — sweep plot extension site verified.

### Secondary (MEDIUM confidence)
- Student-t table values — standard reference tables (scipy reference documented, but scipy not a current project dep).
- pyqtgraph `FillBetweenItem` / `ErrorBarItem` availability — verified library has these as first-class items (Context7 `/pyqtgraph/pyqtgraph` lookup successful).

### Tertiary (LOW confidence)
- Per-batch C++ overhead estimate (Assumption A1) — needs empirical measurement in Wave 0.
- Specific memory footprint numbers — back-of-envelope, not benchmarked.

## Metadata

**Confidence breakdown:**
- Batch variance methodology: HIGH — well-established MC technique; formulas are textbook.
- Tracer integration: HIGH — insertion points identified precisely in existing code; no C++ changes needed.
- Data model extensions: HIGH — purely additive, all optional, zero backwards-compat risk.
- UI patterns: MEDIUM — pyqtgraph items are proven but not yet used in this codebase; will require first-time debugging of FillBetweenItem + ErrorBarItem styling.
- Sweep integration: HIGH — straightforward extension of existing `_refresh_plot`.
- Convergence tab: MEDIUM — new widget, no existing template; structure follows `PlotTab` pattern.

**Research date:** 2026-04-18
**Valid until:** 2026-05-18 (30 days — tracer and data model are stable)

## RESEARCH COMPLETE
