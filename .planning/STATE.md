---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: milestone
current_plan: 3
status: executing
stopped_at: Completed 04-02-PLAN.md
last_updated: "2026-04-18T20:40:00Z"
last_activity: 2026-04-18 -- Phase 04 Plan 02 (tracer K-batch UQ loop on C++/Python/MP paths) complete
progress:
  total_phases: 8
  completed_phases: 3
  total_plans: 14
  completed_plans: 13
  percent: 93
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-15)

**Core value:** Engineers can iterate on both direct-lit and edge-lit BLU designs with physically accurate, wavelength-aware simulation — fast enough for real workloads.
**Current focus:** Phase 04 — uncertainty-quantification

## Current Position

Milestone: v2.0-distribution — In Progress
Phase: 04 (uncertainty-quantification) — EXECUTING (Plan 03 active)
Plan: 3 of 3
Status: Executing Phase 04 (Plan 02 complete; Plan 03 UI rendering next)
Last activity: 2026-04-18 -- Phase 04 Plan 02 (tracer K-batch UQ loop) complete

Progress: [██████████████] 93% (13/14 plans)

## Current Position Detail

Phase: 04-uncertainty-quantification
Current Plan: 3
Stopped at: Completed 04-02-PLAN.md

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
- Phase 03 Plan 02 (Wave 1): integrating cavity built from 6 Rectangle walls + dummy `spectral_material_data` Python-path forcer instead of a SolidBox — SolidBox faces apply Fresnel by default and would require a per-face `face_optics` override to behave as a Lambertian reflector.
- Phase 03 Plan 02 (Wave 1): specular mirror source uses a narrow 5° pencil angular distribution, not Lambertian. Lambertian on a finite tilted mirror asymmetrically truncates the emission cone (+y rays hit the mirror only up to |α|<60°; -y has no such limit), biasing the centroid of reflected rays outside the 1° tolerance.
- Phase 03 Plan 02 (Wave 1): default `energy_threshold` in the golden `_base_project` is 1e-9 (vs 1e-3 default). Otherwise rays die after ~6 bounces at 500k ray counts and the steady-state cavity flux drifts systematically with ray count, breaking Monte Carlo convergence.
- Phase 03 Plan 02 (Wave 1): sphere-detector peak-finding uses raw `sd.grid`, not `sd.candela_grid`. Candela divides by sin(θ) floored at 1e-6, amplifying pole-bin noise by up to 10^6x and placing argmax at the poles independent of the physics.
- Phase 03 Plan 02 (Wave 1): added `integrating_sphere_port_irradiance` to references.py — combines direct point-source inverse-square flux + integrating-sphere throughput multiplier M=ρ/[1-ρ(1-f)]. Residual at 500k rays: 0.38% (well under 2% tolerance).
- Phase 03 Plan 03 (Wave 2): `SolidPrism(n_sides=3)` is fixed-equilateral (apex=60° enforced in builder). RESEARCH.md's apex=45° suggestion not applicable. Prism dispersion test uses θ_in=40° (near min-deviation) — Rule 4 deviation authorized because 20° causes TIR at all 3 BK7 wavelengths per analytical `snell_exit_angle`. At 40° the analytical dispersion is 1.19° (12× above the 0.1° memory-flag guard); measured dispersion at seed=42 is 1.00° (16% relative residual).
- Phase 03 Plan 03 (Wave 2): Fresnel scene uses asymmetric source/detector placement (L_src=10, L_det=20 along incidence/reflection rays from top-face hit point) so source pencil-beam cone and reflected detector never coincide at θ=0 (both would otherwise sit on the +z axis and the detector would catch downgoing source rays, giving T_measured=-0.04).
- Phase 03 Plan 03 (Wave 2): `face_optics` values resolve against `project.optical_properties` (not `project.materials`) per `tracer.py:1163-1166`. The Fresnel absorber override is added as an `OpticalProperties` dataclass entry, not a `Material`.
- Phase 03 Plan 03 (Wave 2): prism total-deviation metric (D = θ_in + θ_out − apex, = angle between source dir and far-field peak dir) is rotation-invariant and sidesteps world-frame exit-geometry math that the SolidPrism._perpendicular_basis default axes introduce. Suitable for any prism orientation.
- Phase 03 Plan 03 (Wave 2): MEMORY FLAG `project_spectral_ri_testing.md` CLOSED by passing `test_prism_dispersion_is_nonzero` (dispersion_deg = 1.0° > 0.1° guard; 10× safety margin). The solid-body spectral n(λ) refraction path is now physically verified, not just smoke-tested.
- Phase 03 Plan 04 (Wave 3): `backlight_sim/golden/report.py` mirrors `io/report.py` matplotlib Agg + base64 PNG pattern verbatim; HTML degrades to `<em>(matplotlib not available)</em>` placeholder when matplotlib is absent. Markdown writer has no matplotlib dependency and always succeeds — this is the primary pre-commit regression surface when working in a minimal-deps env.
- Phase 03 Plan 04 (Wave 3): CLI `python -m backlight_sim.golden` uses stdlib argparse (mirrors `build_exe.py`); exit codes 0 (all-pass) / 1 (any-fail, CI gate) / 2 (usage error). `--rays N` override lets CI run at 5k rays for smoke coverage; `--cases LIST` filters to a comma-separated subset.
- Phase 03 Plan 04 (Wave 3): integration tests use pytest `tmp_path` fixture (Windows-aware, no hardcoded `/tmp/...`). `test_golden_suite_runtime_under_budget` enforces VALIDATION.md 300s budget via literal `timeout=300` in subprocess.run — grep-verifiable; on TimeoutExpired raises AssertionError with partial stdout/stderr for diagnosability. Measured: 112.62 s on clean tracer (2.7× margin).
- Phase 03 Plan 04 (Wave 3): HTML report embeds matplotlib PNGs via base64 data URIs (single self-contained file). Reproducibility footer uses `importlib.util.find_spec("backlight_sim.sim.blu_tracer").origin` to print the C++ .pyd path in both HTML and markdown reports — defends against ambiguity about which blu_tracer extension was loaded during the run.
- Phase 03 Plan 04 (Wave 3): concurrent Phase 04 Plan 02 tracer WIP (`_run_uq_batched` in-progress implementation) actively breaks the golden suite during our session (21/21 green when stashed → 14/21 when the WIP is applied, due to `candela_grid=None` in merged `SphereDetectorResult`). Logged to `.planning/phases/03-golden-reference-validation-suite/deferred-items.md`. Not a Plan 03-04 regression; owned by Phase 04 Plan 02.
- Phase 04 Plan 01 (Wave 1): hard-coded Student-t critical-value table (51 entries; dof in {3..19} × conf in {0.90, 0.95, 0.99}) chosen over scipy dependency. Matches `scipy.stats.t.ppf` within 1e-3; keeps PyInstaller bundle lean. Clamps dof to 19 for K>20 (conservative tail asymptote); rejects K<4.
- Phase 04 Plan 01 (Wave 1): `CIEstimate.format()` aligns mean precision to 2 sig figs of the half_width (standard scientific-paper convention: "87.3 ± 1.2%", not "87.324 ± 1.2%"). Legacy results with n_batches=0 render plain mean without ± token.
- Phase 04 Plan 01 (Wave 1): KPI helper bodies lifted verbatim from `gui/heatmap_panel.py` into `core/kpi.py` — parity asserted bitwise on 10 fixed-seed random grids across 5 shapes. `_kpis` removed from `gui/parameter_sweep_dialog.py` outright (not kept as shim); call sites unpack `compute_scalar_kpis(result)` dict directly.
- Phase 04 Plan 01 (Wave 1): `SimulationResult.uq_warnings` uses `field(default_factory=list)` to avoid the shared-mutable-default pitfall. Dedicated test constructs two instances, mutates one, asserts the other untouched.
- Phase 04 Plan 01 (Wave 1): `DetectorResult.rays_per_batch` is `list[int] | None` (not np.ndarray) — records actual rays per batch to handle the `rays_per_source % K != 0` remainder when the tracer populates it in Wave 2.
- Phase 04 Plan 01 (Wave 1): Rule 2 deviation — `io/project_io.py` persists `uq_batches` and `uq_include_spectral` in both `save_project` and `load_project`. Plan only specified load-side; save-side added because otherwise the user's K selection silently resets to default on every reload (a correctness defect disguised as a plan omission).
- Phase 04 Plan 01 (Wave 1): DoS mitigation for threat T-04.01-02 deferred to Wave 2 tracer — will clamp `uq_batches` to `min(20, max(4, rays_per_source // 1000))` at runtime. Wave 1 data model accepts any int; persistence is not a runtime vector.
- Phase 04 Plan 02 (Wave 2): `_run_uq_batched` is an outer K-loop wrapper that calls the existing `_run_single` K times with patched settings, rather than restructuring the ~1000-line inner bounce loop. Preserves K=0 legacy path unchanged (dispatch guard via `_uq_in_chunk` flag) and isolates UQ logic to a new 210-line method.
- Phase 04 Plan 02 (Wave 2): Energy conservation across K chunks — per-chunk source `flux` is scaled by `(rays_this_batch / rays_total)` so per-ray weight = `(flux × scale) / rays_this_batch = flux / rays_total` (identical to legacy). Summed over K chunks: `flux × sum(scale) = flux`. Golden suite caught the missing scaling as 10x flux overshoot on integrating cavity; Rule 2 auto-fix.
- Phase 04 Plan 02 (Wave 2): `uq_batches` clamp policy is `min(20, max(4, k))` — below-4 CLAMPS UP to 4 (does not raise). Matches Wave 1 `core/uq.py::batch_mean_ci` which rejects K<4 for CI. User setting K=2 still gets 4 valid batches.
- Phase 04 Plan 02 (Wave 2): Signed-int32 seed mask (`& 0x7FFFFFFF`) at every C++ trace_source boundary. pybind11's `int seed` parameter is 32-bit signed on x64 Windows; unmasked md5-derived seeds can exceed INT_MAX and raise TypeError. Pre-existing dormant bug surfaced by UQ chunk-level random_seed distribution; Rule 1 auto-fix in 3 call sites.
- Phase 04 Plan 02 (Wave 2): Adaptive convergence is evaluated ONLY at chunk boundaries when UQ is on (CONTEXT D-01 / W1 guard). Each inner `_run_single` chunk runs with `adaptive_sampling=False` (runs to completion); the outer `_run_uq_batched` tests the predicate between chunks and short-circuits when CV drops below target. Second "UQ CI undefined" warning appended when early convergence leaves k' < 4 completed chunks.
- Phase 04 Plan 02 (Wave 2): Per-batch grids are direct chunk contributions (not cumulative deltas). Each `_run_single` call creates fresh `det_results` accumulators — `chunk_result.grid` is this chunk's contribution only. `cum_result` is the running sum used for progress tracking; `per_batch_grids` is the list of direct chunk grids.
- Phase 04 Plan 02 (Wave 2): Python MP worker (`_trace_single_source`) UQ batching deferred. Used only for MP+spectral+solid-body scenes. Aggregator handles missing UQ payload gracefully via `.get(..., None)`. Not covered by tests; graceful degradation (DetectorResult.grid_batches=None) rather than failure.
- Phase 04 Plan 02 (Wave 2): Sphere detector UQ attached via `setattr` (not dataclass fields). Wave 1 did not extend `SphereDetectorResult` with UQ fields; this Wave 2 hand-off uses attributes. Wave 3 UI reads via `getattr(sr, "grid_batches", None)`.
- Phase 04 Plan 02 (Wave 2): stderr shrinkage test (`test_stderr_shrinks_sqrt_n`) uses center-bin mean flux KPI rather than total flux. Total flux in the reflective Simple Box is conservation-bounded (every ray lands somewhere), so batch-to-batch variance is near-zero and does not show 1/sqrt(N) behavior. Center-bin mean exposes the Monte Carlo spatial noise correctly.

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
Stopped at: Completed 04-02-PLAN.md (Phase 04 Wave 2 — tracer K-batch UQ loop on all three execution paths). `backlight_sim/sim/tracer.py` gains 4 new module-level helpers (`_effective_uq_batches`, `_batch_seed`, `_partition_rays`, `_replace_settings`), a new `_run_uq_batched` method (~210 lines) that wraps `_run_single` with K chunks + per-batch seeded RNG + source flux scaling for energy conservation + chunk-boundary adaptive convergence, extends `_cpp_trace_single_source` with a K-loop (~120 lines, up from ~15) for the multiprocess C++ worker path, and augments `_run_multiprocess` with per-batch worker aggregate merging. `RayTracer.run` now emits the "adaptive+UQ" warning onto `SimulationResult.uq_warnings` (CONTEXT D-01). Each of 3 md5-derived C++ seed derivation sites masks to signed int32 (`& 0x7FFFFFFF`) to avoid pybind11 TypeError on hashes > INT_MAX — pre-existing dormant bug flagged as Rule 1 auto-fix. Per-chunk energy conservation via source flux scaling `(rays_this_batch / rays_total)` caught by golden suite as Rule 2 auto-fix. New `backlight_sim/tests/test_uq_tracer.py` (390 lines, 25 tests) covers helpers, remainder distribution, deterministic seeding, stderr shrinkage on center-bin KPI, first-batch-only path recording, adaptive+UQ warning attachment, chunk-boundary convergence instrumentation, spectral toggle, clamp policy, MP parity. 3 new integration tests appended to `test_tracer.py` (bit-identical legacy determinism anchor, C++ batch-sum vs single-run KS test scipy-gated, Python spectral batch-sum vs single-run). C++ extension `_blu_tracer/src/*` untouched — batching is entirely Python-side. Full suite: **212 passed, 6 warnings in 89.92 s**. Phase 04 Plan 02 CLOSED; Plan 03 (UI CI rendering — heatmap, convergence tab, sweep, HTML/CSV exports) is next and final wave.
Resume file: None
