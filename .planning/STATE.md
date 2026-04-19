---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: milestone
current_plan: 2
status: in_progress
stopped_at: Completed 05-01-PLAN.md
last_updated: "2026-04-19T17:46:11Z"
last_activity: 2026-04-19 -- Phase 05 Plan 01 complete; ensemble.py stub (7 NotImplementedError functions) + test_ensemble.py (11 xfail TDD tests ENS-01..ENS-11); 240 passed 11 xfailed
progress:
  total_phases: 8
  completed_phases: 4
  total_plans: 18
  completed_plans: 15
  percent: 83
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-15)

**Core value:** Engineers can iterate on both direct-lit and edge-lit BLU designs with physically accurate, wavelength-aware simulation — fast enough for real workloads.
**Current focus:** Phase 04 — uncertainty-quantification

## Current Position

Milestone: v2.0-distribution — In Progress
Phase: 04 (uncertainty-quantification) — COMPLETE (all 3 plans shipped)
Plan: 3 of 3 (complete)
Status: Phase 04 closed; ready for Phase 05 (tolerance MC) planning
Last activity: 2026-04-19 -- Phase 04 human UAT approved (7/7 items); UQ settings exposed in UI; golden suite 13/13 green

Progress: [███████████████] 100% (14/14 plans)

## Current Position Detail

Phase: 05-geometry-tolerance-monte-carlo (in progress)
Current Plan: 2 of 4 (plan 01 complete)
Stopped at: Completed 05-01-PLAN.md

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
- Phase 04 Plan 03 (Wave 3): shared `core.kpi.compute_all_kpi_cis(result, conf_level)` aggregator is the single source of CI strings for heatmap_panel, io/report, and io/batch_export. Previously-planned duplicate KPI→CI dispatch across three call sites collapsed to one — eliminates the risk of per-surface CI drift and guarantees consistent column layout across the KPI CSV and the ZIP kpi.csv.
- Phase 04 Plan 03 (Wave 3): `core.kpi._per_batch_source_flux(result, det)` is the single source of truth for per-batch source flux. Consumed by heatmap_panel._compute_all_kpi_batches, parameter_sweep_dialog._per_step_kpi_cis, convergence_tab._per_batch_values_up_to_k, and compute_all_kpi_cis itself. Rays_per_batch-aware scaling guarantees unbiased per-batch efficiency even when `rays_per_source % K != 0` (checker I5 / threat T-04.03-05). Verified by three dedicated tests (test_efficiency_ci_uses_rays_per_batch_not_naive_division, test_sweep_efficiency_uses_rays_per_batch, test_compute_all_kpi_cis_uses_rays_per_batch).
- Phase 04 Plan 03 (Wave 3): MainWindow carries TWO "Convergence" tabs — the existing `self._conv_plot` (live CV%-per-source plot updated during simulation, kept for backward-compat) and the new ConvergenceTab ("Convergence (UQ)" — cumulative-KPI + FillBetweenItem CI band populated after sim). Keeping them separate avoids breaking the live-feedback flow users rely on.
- Phase 04 Plan 03 (Wave 3): confidence-level dropdown in heatmap panel recomputes CI labels from cached per-batch arrays (populated once in update_results) without touching the tracer. Dropdown switch 95%→99% re-renders labels via `batch_mean_ci(cached_vals, conf_level=new)` only — verified by test_confidence_combo_recomputes_without_rerun.
- Phase 04 Plan 03 (Wave 3): Per-bin relative stderr overlay added as 4th item in the existing color-mode combo (rather than a separate widget). Renders `per_bin_stderr(grid_batches) / (grid / n_batches)` with `np.where(mean_bin > 0, ..., 0.0)` to mask division-by-zero at bins where no rays landed. Gracefully shows an informational label when UQ is off.
- Phase 04 Plan 03 (Wave 3): sweep dialog CI column headers chosen as concise `eff ± Δ / u14 ± Δ / hot ± Δ` (3 columns, ~8 chars each). Per-step CI cells show the full CIEstimate.format() string. Per-step CI uses the SAME rays_per_batch-aware scaling as the heatmap/report path — no inline divergence.
- Phase 04 Plan 03 (Wave 3): HTML report embeds the matplotlib errorbar chart via a SECOND `<img src="data:image/png;base64,...">` tag, mirroring the existing heatmap PNG pattern. Graceful matplotlib-missing: `_errorbar_chart_base64` returns `""` inside an `except ImportError` and the caller's `if errorbar_png:` guard produces no `<img>` tag rather than crashing. Tested via monkeypatched `builtins.__import__` blocking `matplotlib*`.
- Phase 04 Plan 03 (Wave 3): CSV schema gained 7 CI columns (`mean,half_width,std,lower,upper,n_batches,conf_level`) AFTER the legacy `metric,value,unit` triple. Position-based parsers of the first three columns still work. Legacy (UQ-off) rows write empty strings for the CI columns — consumers filter on `n_batches == 0` or empty to identify UQ-off entries.
- Phase 04 Plan 03 (Wave 3): headless Qt test pattern adopted — `QT_QPA_PLATFORM=offscreen` set at test module import, single `QApplication.instance() or QApplication([])` fixture at module scope. `isHidden()` used instead of `isVisible()` because the latter returns False until a top-level window is explicitly shown. Applied consistently across test_uq_ui.py and test_uq_exports.py.
- Phase 04 Plan 03 (Wave 3): end-to-end smoke test (`test_end_to_end_uq_smoke`) disables `adaptive_sampling` because the Simple Box preset with `rays_per_source=2000` + K=10 converges at k'=2 (below the 4-batch CI floor). Documented as a user-facing interaction: if you want full K-batch CI fidelity at low ray counts, turn adaptive off.

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

Last session: 2026-04-19
Stopped at: Completed 05-01-PLAN.md (Phase 05 Wave 0 — TDD scaffold: ensemble.py stub + test_ensemble.py 11 xfail tests). New `backlight_sim/gui/convergence_tab.py` (199 lines) introduces `ConvergenceTab(QWidget)` with a pyqtgraph PlotWidget + FillBetweenItem CI band and a KPI selector (uniformity 1/4 / efficiency / hotspot). MainWindow wires it as "Convergence (UQ)" tab next to the Plots tab (distinct from the existing live CV%-per-source "Convergence" tab). `backlight_sim/core/kpi.py` gains `_per_batch_source_flux(result, det)` (single source of truth for rays_per_batch-aware per-batch source flux — closes checker I5 / threat T-04.03-05) and `compute_all_kpi_cis(result, conf_level)` (shared CI aggregator consumed by heatmap_panel, io/report, io/batch_export). `backlight_sim/gui/heatmap_panel.py` gains a confidence-level dropdown (90/95/99%, default 95%) that recomputes CI labels WITHOUT re-running the tracer, a "Per-bin relative stderr" entry in the color-mode combo that renders `sigma_bin / mean_bin` from `grid_batches`, a UQ warnings banner (orange label for all `result.uq_warnings` strings), and a CI-aware KPI CSV exporter with the 10-column schema `metric,value,unit,mean,half_width,std,lower,upper,n_batches,conf_level`. `backlight_sim/gui/parameter_sweep_dialog.py` gains 3 CI columns (`eff ± Δ / u14 ± Δ / hot ± Δ`) on both single and multi-parameter sweep tables, a `pg.ErrorBarItem` overlay on the KPI trace with per-step half-widths, and a `_per_step_kpi_cis` helper using `_per_batch_source_flux` for unbiased efficiency scaling. `backlight_sim/io/report.py` HTML report renders `value ± half_width unit` on KPI rows and embeds a second `<img>` matplotlib errorbar chart (graceful fallback when matplotlib is missing); `backlight_sim/io/batch_export.py` ships the same 10-column CI schema in the ZIP kpi.csv. New `backlight_sim/tests/test_uq_ui.py` (430 lines, 17 headless-Qt tests via `QT_QPA_PLATFORM=offscreen`) covers heatmap labels (CI / legacy / sub-floor), confidence dropdown, noise overlay, warning banner multi-line + hidden state, CSV schema, ConvergenceTab construction/populate/noop, sweep ErrorBarItem + CI columns, rays_per_batch efficiency scaling. New `backlight_sim/tests/test_uq_exports.py` (298 lines, 8 tests) covers HTML CI strings / legacy no-CI / errorbar image / matplotlib-missing graceful; batch zip CI header (UQ-on + legacy); compute_all_kpi_cis rays_per_batch correctness; end-to-end Simple-Box smoke (4k rays, K=10, adaptive disabled) through csv + html + zip. Full suite: **237 passed, 7 warnings in 91.76 s**. Phase 04 CLOSED — every reported KPI ships with a 95% CI end-to-end, rays_per_batch-aware scaling eliminates remainder-distribution bias across all surfaces. Phase 05 (tolerance MC) and Phase 06 (optimizer) can now consume `compute_all_kpi_cis` for noise-aware objectives.
Resume file: None
