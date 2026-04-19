---
phase: 03-golden-reference-validation-suite
verified: 2026-04-18T00:00:00Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
caveats:
  - kind: concurrent_phase_interaction
    description: |
      Phase 04 Plan 02 WIP (unstaged changes to backlight_sim/sim/tracer.py
      and backlight_sim/tests/test_uq_tracer.py) introduces a batched UQ
      tracer path that currently strips candela_grid from merged sphere
      detector results, breaking golden tests WHEN APPLIED. This is out-of-scope
      for Phase 03 and is flagged in Plan 03-04 SUMMARY + deferred-items.md.
      With Phase 04 WIP stashed, Plan 03-04 SUMMARY reports 21/21 golden tests
      green and full suite 183 passed. Phase 04 plan 02 is responsible for
      reconciliation (specifically calling compute_farfield_candela on merged
      batches at tracer.py:~2934).
human_verification:
  - test: "HTML report visual sanity"
    expected: "Fresnel T(θ) analytical curve + 5 red measured points plot correctly; prism dispersion plot shows 3 Snell-expected blue markers + 3 red measured markers"
    why_human: "Matplotlib PNG rendering is environment-dependent; automated test only checks files exist and contain table rows"
  - test: "Seed stability across {1, 42, 100}"
    expected: "All golden tests PASS at each seed"
    why_human: "Optional reproducibility verification, not strictly required for every CI run"
---

# Phase 03: Golden-Reference Validation Suite — Verification Report

**Phase Goal:** Build a library of analytical and experimentally-verified test cases that every tracer change must pass before merging — establish trust in the physics engine before building higher-order features (UQ bars, optimizers, LGP) on top of it.

**Verified:** 2026-04-18
**Status:** PASSED
**Re-verification:** No — initial verification.

## Goal Achievement

### Observable Truths (Goal-Backward)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | All 5 analytical cases exist and pass at seed=42 | ✓ VERIFIED | 6 test files present; SUMMARY measurements cite residuals orders of magnitude below tolerance |
| 2 | Memory flag `project_spectral_ri_testing.md` is closed by a regression-guard test | ✓ VERIFIED | `test_prism_dispersion.py:209` literal `assert dispersion_deg > 0.1`; Δθ measured = 1.0000° (10× margin) |
| 3 | CLI `python -m backlight_sim.golden --report` produces HTML + markdown | ✓ VERIFIED | `__main__.py:30–114`; `report.py:144` (markdown) + `report.py:192` (HTML); smoke run in Plan 03-04 SUMMARY returned both artifacts |
| 4 | Runtime budget < 300 s enforced | ✓ VERIFIED | `test_cli_report.py:133` literal `timeout=300`; measured 36.30 s + 112.62 s (both 2.7×–8.3× margin) |
| 5 | Package hygiene: no GUI imports in shipped `backlight_sim/golden/` | ✓ VERIFIED | `grep PySide6\|pyqtgraph` returns only docstring comments (no imports); `references.py` has no `backlight_sim.sim` imports |
| 6 | CLAUDE.md documents the suite as a pre-merge gate | ✓ VERIFIED | `CLAUDE.md:78–81, 322–324` all present |
| 7 | All 7 GOLD-0x requirements covered by at least one test | ✓ VERIFIED | See Requirements Coverage below |

**Score:** 7/7 truths verified.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backlight_sim/golden/__init__.py` | Package marker, headless | ✓ VERIFIED | 5 lines; docstring notes "no PySide6, no pyqtgraph eager imports" |
| `backlight_sim/golden/cases.py` | ALL_CASES registry, GoldenCase/GoldenResult, run_case | ✓ VERIFIED | 495 lines; 13 cases registered |
| `backlight_sim/golden/builders.py` | Scene builders for all 5 cases | ✓ VERIFIED | 600 lines; exports `PRISM_APEX_DEG=60.0`, `PRISM_THETA_IN_DEG=40.0`, `GOLDEN_SEED=42` |
| `backlight_sim/golden/report.py` | HTML + markdown renderers with matplotlib Agg fallback | ✓ VERIFIED | 283 lines; `matplotlib.use("Agg")` at line 39; `except ImportError` at line 42 |
| `backlight_sim/golden/__main__.py` | argparse CLI with --report/--out/--rays/--cases | ✓ VERIFIED | 114 lines; exit code 0/1/2 semantics |
| `backlight_sim/tests/golden/conftest.py` | 5 scene-builder fixtures + assert_within_tolerance | ✓ VERIFIED | 95 lines; GOLDEN_SEED re-exported from builders |
| `backlight_sim/tests/golden/references.py` | Pure analytical math, no tracer imports | ✓ VERIFIED | 88 lines; only `numpy` + `math` imports |
| `backlight_sim/tests/golden/test_integrating_sphere.py` | GOLD-01 | ✓ VERIFIED | 62 lines, seed=42, ρ=0.9, 500k rays, ±2% rel |
| `backlight_sim/tests/golden/test_lambertian_cosine.py` | GOLD-02 | ✓ VERIFIED | 61 lines, 500k rays, RMS tol 0.03 |
| `backlight_sim/tests/golden/test_fresnel_glass.py` | GOLD-03 (5 angles) | ✓ VERIFIED | 123 lines, parametrized {0, 30, 45, 60, 80}, 200k rays, ±0.02 abs |
| `backlight_sim/tests/golden/test_specular_reflection.py` | GOLD-04 (Python + C++ sub-cases) | ✓ VERIFIED | 143 lines; both `_project_uses_cpp_unsupported_features` assertions present (lines 48, 105) |
| `backlight_sim/tests/golden/test_prism_dispersion.py` | GOLD-05 with dispersion guard | ✓ VERIFIED | 242 lines; `assert dispersion_deg > 0.1` at line 209; all 3 Pitfall-3 guards at lines 125–140 |
| `backlight_sim/tests/golden/test_cli_report.py` | GOLD-06 (4 integration tests) | ✓ VERIFIED | 146 lines; `timeout=300` at line 133; `test_golden_suite_runtime_under_budget` at line 111 |
| `CLAUDE.md` update | Documents `python -m backlight_sim.golden`, pre-merge gate, memory-flag closure | ✓ VERIFIED | lines 78–81 (Commands) + 322–324 (Conventions) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `__main__.py` | `cases.ALL_CASES` | Import at line 22 | ✓ WIRED | `run_case(case, rays_override=args.rays)` invoked per case |
| `__main__.py` | `report.write_html_report` / `write_markdown_report` | Import at line 23, invoke lines 106–107 | ✓ WIRED | Both writers called under `--report` flag |
| `cases.py` | `builders.build_*_project` | Lazy imports inside each `_build_*` closure | ✓ WIRED | 5 builders (cavity, lambertian, specular, fresnel, prism) all reachable |
| `conftest.py` | `builders` | `from backlight_sim.golden import builders as _builders` line 18 | ✓ WIRED | 5 scene-builder fixtures all forward to builders |
| `test_prism_dispersion.py` | `builders.PRISM_APEX_DEG/PRISM_THETA_IN_DEG` | Import line 33–36 + cross-module invariant asserts lines 52–60 | ✓ WIRED | Loud fail if builder constants drift |
| `cases.py::_measure_prism` | `references.snell_exit_angle` | Import inside function | ✓ WIRED | Deviation metric = θ_in + θ_out − apex, rotation-invariant |
| `report.py::_fresnel_plot_base64` | `references.fresnel_transmittance_unpolarized` | Lazy import inside function with try/except | ✓ WIRED | Graceful fallback if test package unavailable |
| `CLI exit code` | `passed == len(results)` | `__main__.py:110` | ✓ WIRED | Returns `0 if passed == len(results) else 1` — CI-gate semantics |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `test_prism_dispersion.py::test_prism_dispersion_is_nonzero` | `dispersion_deg` | `abs(dev(450) − dev(650))` from two live tracer runs at 500k rays | Yes — Plan 03-03 SUMMARY reports 1.0000° measured | ✓ FLOWING |
| `test_fresnel_glass.py` | `T_measured` | `1.0 − reflected_flux / source_flux` from planar detector in live tracer run | Yes — 5 residuals 0.000045–0.000746, all well under 0.02 | ✓ FLOWING |
| `test_specular_reflection.py` | `theta_peak` (Python), `residual_deg` (C++) | argmax of sphere_detectors["farfield"].grid / centroid of detectors["planar"].grid | Yes — Python 0.33° vs 0.5° tol; C++ 0.007° vs 1° tol | ✓ FLOWING |
| `test_integrating_sphere.py` | `E_measured` | `det.total_flux / patch_area` from live 500k-ray run | Yes — residual 0.00376 vs 0.02 tol | ✓ FLOWING |
| `test_lambertian_cosine.py` | `rms` | RMS of (candela_profile_norm − cos(θ)) after masking θ > 80° | Yes — residual 0.00898 vs 0.03 tol | ✓ FLOWING |
| `report.py::write_html_report` | `fresnel_png`, `prism_png` base64 strings | Live matplotlib render of measured points vs analytical curve | Yes — smoke-verified in Plan 03-04 SUMMARY (opened in browser) | ✓ FLOWING |

### Behavioral Spot-Checks

Skipped live test execution per verification_context instructions — the Phase 04 WIP in `backlight_sim/sim/tracer.py` is intentionally dirty in the working tree and the user asked for committed-state verification. Plan 03-04 SUMMARY cites the authoritative measurements taken with Phase 04 WIP stashed: `pytest backlight_sim/tests/golden/ -x -q` → 21 passed in 112.62 s; `pytest backlight_sim/tests/ -x` → 183 passed.

Code-inspection spot-checks performed:

| Behavior | Check | Result | Status |
|----------|-------|--------|--------|
| ALL_CASES is populated | `cases.py` has 13 `ALL_CASES.append(...)` / for-loop appends | 4 + 5 + 3 + 1 = 13 | ✓ PASS |
| GOLDEN_SEED = 42 is the single source | `builders.py:41` + `conftest.py:21` re-export | Single constant, single definition | ✓ PASS |
| `flux_tolerance = 0.0` on every golden source | `grep flux_tolerance backlight_sim/golden/builders.py` | 5 matches (one per builder) at lines 163, 217, 309, 446, 588 | ✓ PASS |
| Pitfall-3 preconditions on prism | Three explicit `assert project.sources[0].spd.startswith("mono_")` + `spd == f"mono_{nm}"` + `"bk7" in spectral_material_data` + `"refractive_index" in spectral_material_data["bk7"]` | All 4 guards at test_prism_dispersion.py:125–140 | ✓ PASS |
| Memory-flag literal guard is grep-able | `grep -qE "assert.*dispersion_deg.*>\s*0\.1"` | Line 209 matches | ✓ PASS |
| Runtime budget literal is grep-able | `grep -q "timeout=300"` | Line 133 matches | ✓ PASS |
| CLI exit code CI semantics | `return 0 if passed == len(results) else 1` in `__main__.py:110` | Literal match | ✓ PASS |
| No GUI imports in shipped package | `grep PySide6\|pyqtgraph backlight_sim/golden/*.py` returns only docstring notes | Zero actual imports | ✓ PASS |

### Requirements Coverage

Derived from VALIDATION.md Requirement→Observable Map.

| Requirement | Source Plan | Observable | Status | Evidence |
|-------------|-------------|------------|--------|----------|
| GOLD-00 | 03-01 | Scaffolding: golden package + test package + references + conftest | ✓ SATISFIED | All files present; Wave 0 SUMMARY confirms 4 budget-probe tests pass |
| GOLD-01 | 03-02 | Integrating-cavity port irradiance | ✓ SATISFIED | `test_integrating_sphere.py`; residual 0.00376 vs 0.02 tol (Plan 03-02 SUMMARY) |
| GOLD-02 | 03-02 | Lambertian I(θ) ≈ I₀·cos(θ) | ✓ SATISFIED | `test_lambertian_cosine.py`; residual 0.00898 vs 0.03 tol (Plan 03-02 SUMMARY) |
| GOLD-03 | 03-03 | Fresnel T(θ) at 5 angles n=1.5 | ✓ SATISFIED | `test_fresnel_glass.py`; max residual 0.000746 vs 0.02 tol across all 5 angles (Plan 03-03 SUMMARY) |
| GOLD-04 | 03-02 | Law of reflection, dual Python+C++ sub-cases | ✓ SATISFIED | `test_specular_reflection.py`; 0.33°/0.007° residuals vs 0.5°/1.0° tolerances; both dispatch-predicate asserts present |
| GOLD-05 | 03-03 | Prism dispersion at 3λ AND Δθ > 0.1° guard | ✓ SATISFIED | `test_prism_dispersion.py`; per-λ max residual 0.2341° vs 0.25° tol; dispersion measured 1.0000° > 0.1° guard (10× margin) — memory flag closed |
| GOLD-06 | 03-04 | CLI produces HTML + markdown with all cases | ✓ SATISFIED | `test_cli_report.py` (4 integration tests); `__main__.py` + `report.py`; Plan 03-04 SUMMARY confirms smoke run produced both artifacts |

No orphaned requirements.

### Anti-Patterns Found

None blocking. Inspection summary:

| File | Finding | Severity | Impact |
|------|---------|----------|--------|
| `backlight_sim/golden/*.py` | No TODO/FIXME/placeholder strings | ℹ️ Info | Clean |
| `backlight_sim/tests/golden/*.py` | No empty handlers or stubs | ℹ️ Info | Clean |
| All files | Every assertion has a descriptive failure message | ℹ️ Info | Clean — diagnosability is high |
| `cases.py` measure callables | Several use lazy imports (`from ... import` inside function body) | ℹ️ Info | Intentional — keeps CLI cold-start cheap and decouples shipped package from test package |

### Memory-Flag Closure (GOLD-05)

**Flag:** `~/.claude/projects/G--blu-optical-simulation/memory/project_spectral_ri_testing.md`
**Description:** "Solid body spectral n(λ) refraction path is implemented but only smoke-tested, not verified for physical correctness"

**Closure evidence:**

1. **Regression-guard test exists** at `backlight_sim/tests/golden/test_prism_dispersion.py::test_prism_dispersion_is_nonzero` with literal assertion:
   ```python
   # Line 207–218
   dispersion_deg = abs(deviations_deg[450] - deviations_deg[650])
   assert dispersion_deg > 0.1, ...
   ```

2. **Per-λ Snell tests exist** at `test_prism_exit_angle_matches_snell` parametrized over {450, 550, 650} nm — residuals 0.0354°, 0.2341°, 0.2297° all < 0.25° tolerance (Plan 03-03 SUMMARY).

3. **Pitfall-3 dispatch guards present** (lines 125–140): verify `spd.startswith("mono_")`, `spd == f"mono_{wavelength_nm}"`, `"bk7" in spectral_material_data`, `"refractive_index" in spectral_material_data["bk7"]`. Without these, a silent scalar-n fallback could pass the per-λ tolerances while dispersion → 0.

4. **Measured dispersion** = 1.0000° vs analytical 1.1942° — 10× safety margin above the 0.1° guard, and within ±25% relative tolerance vs analytical.

5. **CLAUDE.md documents the closure** at line 323: "Phase 03 closes the `project_spectral_ri_testing.md` memory flag: `backlight_sim/tests/golden/test_prism_dispersion.py::test_prism_dispersion_is_nonzero` is the regression guard..."

**Verdict:** Memory flag can be marked resolved. The solid-body spectral n(λ) path is now physically verified (not just smoke-tested) at three wavelengths in the correct monotonic order (n₄₅₀ > n₅₅₀ > n₆₅₀ ⟹ D₄₅₀ > D₅₅₀ > D₆₅₀).

### Human Verification Recommended (Non-Blocking)

1. **HTML report visual sanity** — Run `python -m backlight_sim.golden --report --out ./gold_full` and open `report.html` in a browser. Confirm Fresnel analytical curve and measured points render, prism dispersion shows 3 expected+3 measured markers across 450–650 nm.
2. **Seed-stability** (optional) — `for s in 1 42 100; do GOLDEN_SEED=$s pytest backlight_sim/tests/golden/ -x; done`.

Both flagged in VALIDATION.md Manual-Only Verifications; Plan 03-04 SUMMARY reports the visual check was performed in-session ("Opened in a browser: ... all 13 table rows colored green").

### Gaps Summary

None. All 7 observable truths verified; all 14 required artifacts exist, are substantive, wired, and have data flowing; all 7 GOLD-0x requirements satisfied.

### Caveat: Phase 04 Concurrent Work (Informational)

`git status` shows `backlight_sim/sim/tracer.py` and `backlight_sim/tests/test_uq_tracer.py` as unstaged — this is Phase 04 Plan 02 WIP by a concurrent session. With these changes applied, `compute_farfield_candela` is not called on merged UQ batches, which breaks 3 golden tests (`test_lambertian_cosine`, both `test_specular_*`) and the CLI integration tests that depend on them.

**This does not invalidate Phase 03.** Plan 03-04 SUMMARY explicitly documents the interaction and confirms:
- Phase 03 files (builders, report, `__main__`, tests, CLAUDE.md) do not modify `tracer.py`.
- With Phase 04 WIP stashed, golden suite is 21/21 green and full suite is 183 passed — this is the authoritative Phase-3-committed state.
- Reconciliation is Phase 04 Plan 02's deliverable, tracked in `deferred-items.md`.

---

## VERIFICATION PASSED

**Phase 03 achieved its goal.** The golden-reference validation suite exists as a library of 5 analytical physics cases (13 GoldenCase registrations) with tolerance-based PASS/FAIL, CLI integration as a CI gate with sub-5-minute runtime budget enforcement, and closes the long-standing `project_spectral_ri_testing.md` memory flag with a `dispersion > 0.1°` regression guard at 10× safety margin. CLAUDE.md documents the suite as a pre-merge gate. The package is headless (no PySide6/pyqtgraph) and ships with the wheel.

---

_Verified: 2026-04-18_
_Verifier: Claude (gsd-verifier)_
