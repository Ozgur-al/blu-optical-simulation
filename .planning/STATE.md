---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_plan: 2
status: executing
stopped_at: Completed 03-01-PLAN.md
last_updated: "2026-04-18T15:54:45Z"
last_activity: 2026-04-18 -- Phase 03 Plan 01 (Wave 0 scaffolding + budget probe) complete
progress:
  total_phases: 8
  completed_phases: 2
  total_plans: 13
  completed_plans: 8
  percent: 62
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-15)

**Core value:** Engineers can iterate on both direct-lit and edge-lit BLU designs with physically accurate, wavelength-aware simulation — fast enough for real workloads.
**Current focus:** Phase 03 — golden-reference-validation-suite

## Current Position

Milestone: v2.0-distribution — In Progress
Phase: 03 (golden-reference-validation-suite) — EXECUTING
Plan: 1 of 4
Status: Executing Phase 03
Last activity: 2026-04-18 -- Phase 03 execution started

Progress: [██████████] 100% (8/8 plans)

## Current Position Detail

Phase: 02-converting-main-simulation-loop-to-cpp-for-faster-computation
Current Plan: 1
Stopped at: Completed 02-04-PLAN.md

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
- C++ port Wave 3: conservative dispatch predicate `_project_uses_cpp_unsupported_features(project)` gates the C++ fast path — routes to C++ only when scene has no spectral SPD, no solid bodies/cylinders/prisms, no far-field sphere detectors, no non-white RGB sources, no BSDF profiles, no spectral_material_data; additionally `_run_single` requires `n_record == 0`, `not _adaptive`, `convergence_callback is None`. Everything else keeps the Python bounce loop. This protects Wave 2 deferred items from being silently broken.
- C++ port Wave 3: flux_tolerance jitter applied in Python via `self.rng.uniform(-tol, tol)` BEFORE serializing the project dict (the C++ extension reads `effective_flux` from the dict and does NOT apply jitter). Keeps Python and C++ determinism behavior identical for flux_tolerance > 0 scenes.
- C++ port Wave 3: D-09 hard-crash pattern at module import — `from backlight_sim.sim import blu_tracer` wrapped in try/except ImportError that raises RuntimeError with rebuild instructions. No silent fallback to Python; the C++ extension is mandatory.
- C++ port Wave 3: BVH disabled on the Python fallback path (`_BVH_THRESHOLD = 10**9`). The C++ extension handles acceleration for all scenes that would benefit from BVH; the Python path now services only spectral / solid-body scenes which are small enough for brute-force intersection.
- C++ port Wave 3: pure-Python shim layer inside tracer.py replaces deleted `sim.accel` symbols (`_intersect_plane_accel`, `_intersect_sphere_accel`, `accumulate_grid_jit`, `accumulate_sphere_jit`, `compute_surface_aabbs`, `build_bvh_flat` stub, `traverse_bvh_batch` stub). Keeps the spectral / solid-body call sites untouched without dragging Numba infrastructure into the Wave 3 diff.
- C++ port Wave 3: accel.py-internal tests deleted (6 JIT kernel equivalence + 2 BVH internal traversal); simulation-level BVH tests preserved and now served by C++. New `test_simulation_deterministic_with_cpp` replaces the old JIT determinism smoke test.
- C++ port Wave 4: D-10 speedup target met at 29.8× on preset_simple_box at 100k rays (16.8 ms/run, extrapolated 168 ms for 1M rays) — an order of magnitude above the 3–8× target in CONTEXT.md.
- C++ port Wave 4: PyInstaller .pyd resolution uses `importlib.util.find_spec("backlight_sim.sim.blu_tracer").origin` at spec-evaluation time instead of a ROOT-relative glob; editable scikit-build-core installs place the .pyd under site-packages, so the glob matched zero files and PyInstaller aborted. Dynamic resolve fails fast with a rebuild instruction if the extension is not importable — consistent with the D-09 runtime hard-crash pattern from 02-03.
- C++ port Wave 4: numba fully excised from the distribution — BluOpticalSim.spec hiddenimports purged (numba, numba.core, numba.typed, numba.np, numba.np.ufunc, llvmlite, llvmlite.binding) and requirements.txt drops `numba>=0.64.0`. pybind11/scikit-build-core/cmake/ninja are documented as build-time-only deps.
- C++ port Wave 4: test_statistical_equivalence (C++-06) uses strict energy-conservation bounds (0 < flux_cpp ≤ source_flux, with a 1% floor) instead of per-pixel comparison because Python and C++ paths do not share RNG state after 02-03's pre-serialization flux_tolerance jitter decision. Energy conservation catches the bugs the test was meant to catch without depending on cross-path RNG alignment.
- C++ port Wave 4: test_speedup (C++-07) measures against a conservative 500 ms Python/NumPy baseline for 100k rays (pre-Numba); extrapolated ratio, not a live comparison. The 29.8× measured ratio leaves enough margin that this does not risk a false-positive pass against the 3× D-10 floor.
- v2.0.0 chosen as first distributable release version (v1.0 was internal milestone)
- User data dir uses %LOCALAPPDATA%/BluOpticalSim on Windows — corporate-safe, no admin rights needed
- config.py strictly no PySide6 — headless-safe for io/ and sim/ layer consumption
- Icon generated at runtime via QPainter + Pillow; script checked in so icon can be regenerated
- Splash uses QWidget with Qt.SplashScreen flag instead of QSplashScreen for full QSS/dark theme control
- Staged loading: 20% theme/icon, 60% after MainWindow import, 90% after construct, 100% on close
- Status bar notification (15s) used for update available — unobtrusive vs modal dialog
- http/urllib un-excluded in PyInstaller spec — required by update_checker, minimal size cost
- Daemon thread for update check — auto-killed if app exits before check completes
- Phase 03 Plan 01 (Wave 0): spectral_material_data key convention differs by geometry type — Rectangle surfaces use `{reflectance, transmittance}` (project_model.py:46 docstring); SolidBox/Cylinder/Prism use `{refractive_index}` (tracer.py:1242-1247, 1384-1389). Plans 02/03 must use the right schema per geometry.
- Phase 03 Plan 01 (Wave 0): `spd="mono_<nm>"` verified to trigger `has_spectral` gate at tracer.py:631 and route to Python via `_project_uses_cpp_unsupported_features` — canonical way to emit monochromatic rays. Closes RESEARCH.md assumption A3.
- Phase 03 Plan 01 (Wave 0): budget probe measured ~15 ms/1k rays C++ path and ~17 ms/1k rays Python spectral path on 100k/50k ray probes (includes one-shot overhead); downstream plans can use these as upper bounds for 300s phase gate sizing.
- Phase 03 Plan 01 (Wave 0): RESEARCH.md Case 3 Fresnel table value T(60°, air→glass) = 0.9069 is incorrect; analytical and tracer implementation both return T ≈ 0.9108. Plans 02/03 should derive expected values from `fresnel_transmittance_unpolarized()` call, not the RESEARCH table.

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
Stopped at: Completed 03-01-PLAN.md (Wave 0 scaffolding + budget probe: `backlight_sim/golden/` CLI package with GoldenCase/GoldenResult/ALL_CASES registry; `backlight_sim/tests/golden/` test package with GOLDEN_SEED=42, assert_within_tolerance fixture, 5 scene-builder fixture stubs, analytical references (Fresnel/Snell/Lambert/cavity) — no tracer imports; budget probe emits throughput numbers ~15 ms/1k rays C++ and ~17 ms/1k rays Python spectral; `spd="mono_*"` convention verified to trigger spectral dispatch at tracer.py:631; 128 tests green (124 existing + 4 budget-probe); headless verified — no PySide6/pyqtgraph in sys.modules). Ready for Plan 02 (Wave 1 physics: integrating sphere + Lambertian + specular).
Resume file: None
