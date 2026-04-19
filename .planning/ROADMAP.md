# Roadmap: Blu Optical Simulation

## Milestones

- ✅ **v1.0 Phase 2 Full-Fidelity Simulator** — Phases 1-7 (shipped 2026-03-15)

## Phases

<details>
<summary>✅ v1.0 Phase 2 Full-Fidelity Simulator (Phases 1-7) — SHIPPED 2026-03-15</summary>

- [x] Phase 1: Refractive Physics and LGP (3/3 plans) — completed 2026-03-14
- [x] Phase 2: Spectral Engine (2/2 plans) — completed 2026-03-14
- [x] Phase 3: Performance Acceleration (2/2 plans) — completed 2026-03-14
- [x] Phase 4: Advanced Materials and Geometry (5/5 plans) — completed 2026-03-14
- [x] Phase 5: UI Revamp (4/4 plans) — completed 2026-03-14
- [x] Phase 6: Tracer Cross-Phase Wiring (2/2 plans) — completed 2026-03-15
- [x] Phase 7: UI + Spectral Display Fixes (1/1 plan) — completed 2026-03-15

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Refractive Physics and LGP | v1.0 | 3/3 | Complete | 2026-03-14 |
| 2. Spectral Engine | v1.0 | 2/2 | Complete | 2026-03-14 |
| 3. Performance Acceleration | v1.0 | 2/2 | Complete | 2026-03-14 |
| 4. Advanced Materials and Geometry | v1.0 | 5/5 | Complete | 2026-03-14 |
| 5. UI Revamp | v1.0 | 4/4 | Complete | 2026-03-14 |
| 6. Tracer Cross-Phase Wiring | v1.0 | 2/2 | Complete | 2026-03-15 |
| 7. UI + Spectral Display Fixes | v1.0 | 1/1 | Complete | 2026-03-15 |
| 02. Converting main simulation loop to C++ | v2.0 | 4/4 | Complete    | 2026-04-18 |
| 03. Golden-reference validation suite | v2.0 | 4/4 | Complete    | 2026-04-18 |
| 04. Uncertainty quantification | v2.0 | 3/3 | Complete    | 2026-04-18 |
| 05. Geometry tolerance Monte Carlo | v2.0 | 0/4 | Planned | — |

### Phase 1: distribution for admin locked work computer compatibility, splash screen etc.

**Goal:** Make the app distributable and runnable on admin-locked work computers with polished branding (splash screen, icon), version check, and bundled distribution assets (README, sample files).
**Requirements**: [DIST-01, DIST-02, DIST-03, DIST-04, DIST-05]
**Depends on:** Phase 0
**Plans:** 3 plans (2/3 complete)

Plans:
- [x] 01-01-PLAN.md — Foundation: version constant, app icon, user data config (complete 2026-03-15)
- [x] 01-02-PLAN.md — Splash screen with progress feedback and icon integration (complete 2026-03-15)
- [ ] 01-03-PLAN.md — Version check, build pipeline updates, distribution assets

### Phase 2: Converting main simulation loop to C++ for faster computation

**Goal:** Rewrite the core Monte Carlo ray tracing engine in C++ (exposed to Python via pybind11) to achieve significant speedup on CPU-bound simulation workloads while keeping the Python/PySide6 front-end unchanged.
**Requirements**: [C++-01, C++-02, C++-03, C++-04, C++-05, C++-06, C++-07, C++-08]
**Depends on:** Phase 1
**Plans:** 4 plans

Plans:
- [x] 02-01-PLAN.md — Build infrastructure: pyproject.toml, CMakeLists.txt, C++ skeleton, .pyd build, test stubs (complete 2026-04-18)
- [x] 02-02-PLAN.md — Core C++ engine: all intersection types, sampling, Fresnel/material dispatch, full bounce loop (complete 2026-04-18)
- [x] 02-03-PLAN.md — Python integration: tracer.py C++ wiring, Numba removal, D-09 hard crash (complete 2026-04-18)
- [x] 02-04-PLAN.md — Distribution: PyInstaller spec, requirements.txt, docs, statistical equivalence + speedup validation (complete 2026-04-18)

### Phase 3: Golden-reference validation suite

**Goal:** Build a library of analytical and experimentally-verified test cases that every tracer change must pass before merging — establish trust in the physics engine before building higher-order features (UQ bars, optimizers, LGP) on top of it.

**Rationale (why first in the post-v1.0 physics track):** UQ, inverse design, and the LGP engine all consume the tracer's output as ground truth. A silent Fresnel bug or dispersion error propagates into every downstream feature. Golden references catch physics regressions cheaply, now.

**Scope:**
- **Known-answer cases:** integrating-sphere uniformity (analytical cos-weighted flux), Lambertian flat emitter vs cosine law, Fresnel transmittance at glass interface (s/p polarization-averaged) vs analytical Fresnel equations, single-bounce specular mirror angle check, spectral n(λ) dispersion path for a prism/wedge vs Snell's law at sampled wavelengths.
- **Tolerance-based pass/fail:** each case declares expected value + tolerance (e.g. ±1% for MC with 1M rays); suite prints per-case PASS/FAIL + residual.
- **CLI + pytest integration:** `pytest backlight_sim/tests/golden/` runs the suite; a `python -m backlight_sim.golden --report` command emits an HTML/markdown report.
- **Closes memory flag:** verifies `project_spectral_ri_testing.md` gap — solid-body spectral n(λ) is smoke-tested, not physically verified.

**Depends on:** Phase 1 (distribution only — no blocker; could run in parallel with Phase 2)
**Plans:** 4 plans

Plans:
- [x] 03-01-PLAN.md — Scaffolding + Wave 0 budget probe (GOLD-00): package layout, references.py, conftest fixtures, GoldenCase/GoldenResult registry, C++ vs Python throughput probe, SPD naming smoke check (complete 2026-04-18)
- [x] 03-02-PLAN.md — Cheap analytical cases (GOLD-01, GOLD-02, GOLD-04): integrating cavity + Lambertian cosine law + specular dual C++/Python sub-cases (complete 2026-04-18)
- [x] 03-03-PLAN.md — Expensive cases + memory-flag closure (GOLD-03, GOLD-05): Fresnel T(θ) at 5 angles with face_optics absorber override; prism dispersion at 3 wavelengths — closes project_spectral_ri_testing.md (complete 2026-04-18)
- [x] 03-04-PLAN.md — CLI report + integration test + CLAUDE.md gate (GOLD-06): python -m backlight_sim.golden --report HTML + markdown; subprocess integration test; documentation (complete 2026-04-18)

### Phase 4: Uncertainty quantification (Monte Carlo noise bars on KPIs)

**Goal:** Every reported KPI (uniformity, peak luminance, efficiency, hotspot ratio, NRMSE) ships with a 95% confidence interval derived from the Monte Carlo sampling variance — so users know when results are noise-limited vs design-limited.

**Rationale:** A KPI without an error bar is a liability. Users currently see "uniformity = 87.3%" and trust it; they need "87.3 ± 1.2% @ 95% CI" to decide whether to throw more rays or accept the estimate.

**Scope:**
- **Batch-based variance:** split the `rays_per_source` into K batches (default K=10); compute per-batch KPIs and derive stdev → ± CI per KPI. Zero extra tracer cost — same rays, post-processed differently.
- **KPI dashboard update:** heatmap panel + report + sweep results all display `value ± CI` with configurable confidence level (90/95/99%).
- **Convergence plot:** cumulative KPI vs ray count with shrinking CI band — user sees when more rays stop helping.
- **Grid-level noise:** per-bin stderr map; expose as toggle in heatmap panel so users can see hot-pixels that are just noise.
- **Report + CSV export:** CI columns in KPI CSV, error bars in HTML report.

**Depends on:** Phase 3 (golden refs validate the mean is correct before we quantify its uncertainty)
**Plans:** 3 plans

Plans:
- [x] 04-01-PLAN.md — Data model + core/uq.py + core/kpi.py lift-and-shift + unit tests (complete 2026-04-18)
- [x] 04-02-PLAN.md — Tracer batch loop (C++ fast path + Python fallback + MP merge) with per-batch seeding (complete 2026-04-18)
- [x] 04-03-PLAN.md — UI CI rendering (heatmap, convergence tab, sweep) + HTML/CSV exports + end-to-end smoke (complete 2026-04-18)

### Phase 5: Geometry tolerance Monte Carlo

**Goal:** Randomize geometry and source parameters within user-specified tolerances and run an ensemble sim — real BLUs fail from tolerance stack-up (LED placement drift, cavity depth variation, wall-angle tolerance), not nominal design. Output: KPI distributions (P5/P50/P95) across the ensemble, plus sensitivity ranking per parameter.

**Rationale:** Nominal design says "uniformity = 88%"; manufacturing reality is a distribution. Engineers need to know which tolerances dominate yield before tightening the wrong spec.

**Scope:**
- **Tolerance spec per parameter:** extend Source, cavity-builder params with optional tolerance fields. UI: tolerance section in SourceForm; collapsible, per-source position sigma override.
- **Ensemble runner:** new EnsembleDialog with _EnsembleThread; samples N realizations from tolerance distributions (gaussian or uniform); OAT default, optional Sobol full mode.
- **Outputs:** KPI distributions (live-streaming histogram + P5/P50/P95 per KPI), worst-case realization drill-down, OAT/Sobol sensitivity index per tolerance parameter.
- **Reuses Phase 4 UQ plumbing:** each member calls compute_scalar_kpis; ensemble variance (from tolerances) distinguishable from MC variance (from ray noise).

**Depends on:** Phase 4
**Plans:** 4 plans

Plans:
- [ ] 05-01-PLAN.md — TDD scaffold: test_ensemble.py (ENS-01..ENS-10 xfail stubs) + sim/ensemble.py stub
- [ ] 05-02-PLAN.md — Core data model + headless ensemble engine: tolerance fields, JSON round-trip, apply_jitter, OAT/Sobol sampling
- [ ] 05-03-PLAN.md — GUI: EnsembleDialog + _EnsembleThread + live histogram + SourceForm tolerance section + main_window wiring
- [ ] 05-04-PLAN.md — Integration gate: remove xfail markers, full suite green, cavity recipe GUI wiring, CLAUDE.md update

### Phase 6: Inverse design / target-driven optimizer

**Goal:** User declares a target ("uniformity ≥ 85%, minimize LED count") and the app solves for design parameters (LED count/pitch, wall angle, diffuser transmittance, cavity depth) — moving the app from analysis tool to design tool.

**Rationale:** Parameter sweeps already scan the design space manually. Inverse design closes the loop — formal optimization (CMA-ES or Bayesian) + multi-objective Pareto replaces manual sweep-then-eyeball.

**Scope:**
- **Design variable spec:** UI to mark parameters as "free" (with bounds) vs "fixed". Support LED count/pitch, cavity dims, wall angles, diffuser transmittance, source flux.
- **Objective builder:** weighted sum OR multi-objective (Pareto front). Support constraints (e.g. "uniformity ≥ 0.85" as hard constraint, "minimize cost" as objective).
- **Optimizer backends:** start with CMA-ES (gradient-free, proven for MC-noisy objectives) and optional Bayesian optimization (scikit-optimize or Optuna) for expensive sims. Use Phase 4 UQ as the noise model for the objective.
- **Results UI:** Pareto front plot, best-so-far trace, top-N candidate variants saved as project clones (leverages existing variant system).
- **Cost-aware:** integer penalty for LED count (discrete variable via integer-aware CMA-ES or rounding).

**Depends on:** Phase 4 (UQ — optimizer needs noise-aware objective evaluation), Phase 5 (optional: robust design = optimize P5 instead of mean).
**Plans:** Not planned yet

### Phase 7: Cost / thermal / photometric joint design view

**Goal:** Single "design sheet" view that displays lm/W, $/unit (BOM estimate), ΔT (thermal estimate from LED current + derating), and uniformity/peak luminance side by side — mortals optimize one axis; reality is a 3-way tradeoff.

**Rationale:** Mostly UI/aggregation on top of existing outputs (cheaper win than LGP engine). Pairs with inverse design: the optimizer optimizes what the joint view displays.

**Scope:**
- **Cost model:** per-LED unit cost + cavity material cost + diffuser/film cost as user-editable table; aggregated $/unit.
- **Thermal proxy:** simple lumped-node estimate from LED current + package Rth + ambient; feeds back into `thermal_derate` (closes the loop on `PointSource.thermal_derate`).
- **Photometric summary:** existing KPIs + lm/W (total luminous flux / total electrical power).
- **Design sheet panel:** new tab in main window; single-pane dashboard with the three axes and their cross-influences highlighted.
- **Variant comparison extension:** existing `comparison_dialog` extended to show all three axes side by side across variants.
- **Optimizer objective source:** Phase 6 optimizer reads objectives from the design sheet.

**Depends on:** Phase 4 (UQ — so cost/thermal/photo all display with CIs); ideally pairs with Phase 6 but can ship independently.
**Plans:** Not planned yet

### Phase 8: Edge-lit LGP design optimizer

**Goal:** Full edge-lit light guide plate (LGP) design workflow — micro-structure (dot pattern, V-groove, prism) layout optimization, TIR modeling, extraction-profile targeting — extending the app beyond direct-lit BLUs into the larger edge-lit market.

**Rationale:** Biggest engine lift on the list (Phase 2+ per CLAUDE.md). Intentionally last so it builds on validated physics (Phase 3), uncertainty-aware KPIs (Phase 4), and the optimizer (Phase 6). Shipping LGP on an unvalidated tracer would compound error across a much larger feature.

**Scope:**
- **LGP geometry primitives:** thin plate with bottom-surface extraction features (dot grid, V-groove, printed-dot density map). Each feature has an extraction probability function.
- **TIR-aware tracer integration:** leverage existing refractive-physics / n(λ) path (verified by Phase 3) to trace rays inside the LGP until extraction or escape.
- **Extraction-profile targeting:** user draws a desired top-surface luminance profile; optimizer (Phase 6 engine) solves for dot-density map or groove-pitch map that achieves it.
- **Side-injection source model:** line sources or LED arrays along an edge, with coupling efficiency into the LGP.
- **New presets:** edge-lit LCD-backlight, keypad-illumination.
- **Validation:** Phase 3 suite extended with LGP analytical cases (total internal reflection critical angle, simple groove extraction cosine-law).

**Depends on:** Phase 3 (golden refs for TIR/Fresnel), Phase 6 (optimizer for extraction-profile targeting).
**Plans:** Not planned yet
