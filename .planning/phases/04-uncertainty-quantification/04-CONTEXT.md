# Phase 4: Uncertainty Quantification — Context

**Added:** 2026-04-18
**Status:** Spec recorded, not planned yet

## Phase Boundary

Every reported KPI (uniformity, peak luminance, efficiency, hotspot ratio, NRMSE, edge-center ratio) ships with a 95% confidence interval derived from Monte Carlo sampling variance. Users distinguish noise-limited results from design-limited results.

## Why

A KPI without an error bar is a liability. Users currently see "uniformity = 87.3%" and trust it; they need "87.3 ± 1.2% @ 95% CI" to decide whether to throw more rays or accept the estimate. Also: prerequisite for Phase 5 (tolerance MC — need to separate ensemble variance from MC variance) and Phase 6 (noise-aware optimizer objective).

## Scope

- **Batch-based variance estimation:** split `rays_per_source` into K batches (default K=10); compute per-batch KPIs and derive stdev → ± CI per KPI. Zero extra tracer cost — same rays, post-processed differently.
- **Confidence level config:** user-selectable 90 / 95 / 99% CI (z-score lookup).
- **KPI dashboard update:** heatmap panel + HTML report + sweep results all display `value ± CI`.
- **Convergence plot:** cumulative KPI vs ray count with shrinking CI band — user sees when more rays stop helping.
- **Grid-level noise map:** per-bin stderr map; toggleable overlay on heatmap so users can see hot-pixels that are just noise.
- **Exports:** CI columns in KPI CSV, error bars on HTML report charts.
- **Sweep integration:** parameter sweep results show CI bands on the KPI trace line so users don't chase noise.

## Out of Scope

- Tolerance-based ensemble variance (Phase 5).
- Bayesian credible intervals (stick with frequentist CI from batches).
- Changes to the tracer itself — this is post-processing only.

## Depends On

- Phase 3 (golden refs validate that the *mean* is correct before we put error bars around it).

## Claude's Discretion

- Exact K (batches) default — must balance CI stability vs per-batch bin sparsity.
- Visual presentation of error bars (shaded band vs whiskers).
- Whether to cache per-batch grids (memory cost) or recompute on demand.

## Decisions (added during planning — 2026-04-18)

- **Adaptive sampling + UQ:** allow both simultaneously; UI shows a warning that CI may be biased when adaptive sampling is active. Do NOT hard-disable either mode.
- **Spectral batch storage:** default ON via `uq_include_spectral: bool = True` toggle in `SimulationSettings`. Users on memory-tight scenes can disable.
- **Sphere detector UQ:** in scope from Phase 4 — all detector types (flat + sphere) get ± CI uniformly; no detector-type carve-out.
