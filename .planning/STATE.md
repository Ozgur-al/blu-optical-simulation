---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_plan: 3
status: executing
stopped_at: Completed 02-02-PLAN.md
last_updated: "2026-04-18T14:35:00Z"
last_activity: 2026-04-18 -- Phase 02 Plan 02 complete (C++ bounce loop + real physics)
progress:
  total_phases: 8
  completed_phases: 1
  total_plans: 8
  completed_plans: 5
  percent: 63
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-15)

**Core value:** Engineers can iterate on both direct-lit and edge-lit BLU designs with physically accurate, wavelength-aware simulation — fast enough for real workloads.
**Current focus:** Phase 02 — converting-main-simulation-loop-to-cpp-for-faster-computation

## Current Position

Milestone: v2.0-distribution — In Progress
Phase: 02 (converting-main-simulation-loop-to-cpp-for-faster-computation) — EXECUTING
Plan: 3 of 4
Status: Executing Phase 02
Last activity: 2026-04-18 -- Phase 02 Plan 02 complete (C++ bounce loop + real physics)

Progress: [######----] 63% (5/8 plans)

## Current Position Detail

Phase: 02-converting-main-simulation-loop-to-cpp-for-faster-computation
Current Plan: 3
Stopped at: Completed 02-02-PLAN.md

## Accumulated Context

### Decisions

- C++ port Wave 1: scikit-build-core `wheel.install-dir` unset (not '/') — CMakeLists `DESTINATION backlight_sim/sim` alone installs the .pyd correctly; setting wheel.install-dir to match source path causes doubled-path (backlight_sim/sim/backlight_sim/sim/blu_tracer.pyd) due to scikit-build-core concatenation bug
- C++ port Wave 1: pybind11 entry point `trace_source(project_dict, source_name, seed)` deserializes Python dict at the boundary — keeps Project/RayTracer class API unchanged while C++ handles per-source trace
- C++ port Wave 1: all intersect/sampling/material bodies stubbed (INF or no-op) so Wave 2 planners can work against frozen header signatures
- C++ port Wave 2: detector hits TERMINATE the ray (alive=false) — matches tracer.py::_bounce_detectors semantics; pass-through (as plan text suggested) would double-count flux on multi-detector scenes
- C++ port Wave 2: rays still alive after `max_bounces` have their residual weight added to `escaped_flux` so energy conservation holds strictly (detector + escaped + absorbed = source) with absorbed = source - accounted
- C++ port Wave 2: parse_material defensive with per-field `.contains()` fallbacks (surface_type=absorber, reflectance=0, is_diffuse=true, haze=0) — older project JSONs may omit optional fields; strict pybind cast would raise KeyError
- C++ port Wave 2: BVH stays as no-op stubs (BVH_THRESHOLD=9999 → brute-force always). Full BVH port deferred to a future cleanup phase per CONTEXT.md D-07
- C++ port Wave 2: solid-body / cylinder-body / prism-body Fresnel dispatch deferred to Wave 3 — requires porting `core/solid_body.py::get_faces()` expansion; no Wave 2 test exercises this surface type
- v2.0.0 chosen as first distributable release version (v1.0 was internal milestone)
- User data dir uses %LOCALAPPDATA%/BluOpticalSim on Windows — corporate-safe, no admin rights needed
- config.py strictly no PySide6 — headless-safe for io/ and sim/ layer consumption
- Icon generated at runtime via QPainter + Pillow; script checked in so icon can be regenerated
- Splash uses QWidget with Qt.SplashScreen flag instead of QSplashScreen for full QSS/dark theme control
- Staged loading: 20% theme/icon, 60% after MainWindow import, 90% after construct, 100% on close
- Status bar notification (15s) used for update available — unobtrusive vs modal dialog
- http/urllib un-excluded in PyInstaller spec — required by update_checker, minimal size cost
- Daemon thread for update check — auto-killed if app exits before check completes

### Roadmap Evolution

- v1.0 shipped with 7 phases (originally 4 planned + Phase 5 UI Revamp + Phases 6-7 gap closure)
- VTK renderer deferred to v2 (pyqtgraph.opengl sufficient)
- Spectral+MP guard lifted (quick task 260417-1gw — spectral now runs in MP mode)
- Phase 01 added: distribution for admin locked work computer compatibility, splash screen etc.
- Phase 02 added: converting main simulation loop to C++ for faster computation
- Phase 03 added (2026-04-18): golden-reference validation suite — analytical known-answer physics tests (integrating sphere, Lambertian, Fresnel, Snell/dispersion); validates tracer before downstream phases build on it. Closes `project_spectral_ri_testing.md` gap.
- Phase 04 added (2026-04-18): uncertainty quantification — batch-based MC variance → 95% CI on every KPI; convergence plots; grid-level stderr.
- Phase 05 added (2026-04-18): geometry tolerance Monte Carlo — ensemble sims over parameter tolerances; P5/P50/P95 KPI distributions; sensitivity ranking.
- Phase 06 added (2026-04-18): inverse design optimizer — CMA-ES / Bayesian optimizer over design variables with Pareto multi-objective; optional robust-design mode using Phase 5.
- Phase 07 added (2026-04-18): cost/thermal/photometric joint view — design sheet with $/unit, ΔT, lm/W side by side; closes the loop on `PointSource.thermal_derate` via lumped-node thermal model.
- Phase 08 added (2026-04-18): edge-lit LGP design optimizer — TIR-aware tracing inside light guide plates, extraction-profile targeting via Phase 6 optimizer; biggest engine lift, intentionally last.

### Pending Todos

None.

### Blockers/Concerns

None.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260417-1gw | Fix v1.0 tech debts: BatchForm undo, Spectral+MP guard lifted, BVH cylinder/prism, live heatmap in MP | 2026-04-17 | 60509dc | [260417-1gw-v10-tech-debt](.planning/quick/260417-1gw-v10-tech-debt/) |

## Session Continuity

Last session: 2026-04-18
Stopped at: Completed 02-02-PLAN.md (C++ Monte Carlo engine — real intersection/sampling/material/bounce-loop physics; 5 C++ tests passing, 124 Python tests still green)
Resume file: None
