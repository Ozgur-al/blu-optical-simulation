# Phase 3: Golden-Reference Validation Suite — Research

**Researched:** 2026-04-18
**Domain:** Monte Carlo ray tracer physics verification (Fresnel, Snell, Lambert, dispersion)
**Confidence:** HIGH (analytical references are textbook physics; codebase paths are directly inspected)

---

## Summary

The tracer ships two ray-tracing paths: a C++ extension (`backlight_sim.sim.blu_tracer`) that owns the fast non-spectral, plane-surfaces-only scenes, and a Python fallback (`sim/tracer.py::_run_single`) that owns the interesting physics — Fresnel/TIR on solid bodies, spectral n(λ), BSDF, far-field sphere detectors. Phase 3 must validate BOTH paths, because dispatch is scene-dependent via `_project_uses_cpp_unsupported_features()` — any scene with a `SolidBox`/`SolidCylinder`/`SolidPrism` or a non-"white" SPD is automatically routed to Python.

Five analytical known-answer cases cover the five physics blocks currently claimed to work: integrating-sphere uniformity (tests the multi-bounce bookkeeping and the Lambertian surface-reflection path), Lambertian emitter cosine law (tests `sample_lambertian`), Fresnel T(θ) at a glass interface (tests `_fresnel_unpolarized` + `_refract_snell` on SolidBox), law-of-reflection (tests the specular C++ + Python reflection paths), and prism dispersion (tests the spectral n(λ) path that closes the `project_spectral_ri_testing` memory flag).

**Primary recommendation:** One pytest module per case under `backlight_sim/tests/golden/`, each building its own minimal `Project` via a shared fixture helper, seeded with `SimulationSettings.random_seed`. A thin `backlight_sim/golden/` package provides the CLI (`python -m backlight_sim.golden --report`) that re-imports the same case classes and renders an HTML report via the existing `io/report.py` matplotlib-embedded pattern. Total suite budget ≤ 5 min at 200k–500k rays/case (5 cases × ~60 s each at current C++ speed of ~168 ms/1M rays on a cold scene, but the Python spectral path is ~30× slower so prism and Fresnel-via-SolidBox cases are the budget drivers).

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Scope is fixed to five cases:** integrating-sphere uniformity, Lambertian cosine-law emitter, Fresnel transmittance at glass, single-bounce specular mirror, spectral n(λ) dispersion prism.
- **Tolerance-based PASS/FAIL:** each case declares expected value + tolerance; suite prints per-case PASS/FAIL + residual + effective ray count.
- **Dual entry points:** `pytest backlight_sim/tests/golden/` for CI; `python -m backlight_sim.golden --report` for HTML/markdown report.
- **Regression budget:** suite must run in < 5 min on a dev laptop.
- **Must close:** `project_spectral_ri_testing.md` memory flag — solid-body spectral n(λ) path must be physically verified, not just smoke-tested.

### Claude's Discretion

- Exact tolerance values per case (must be defensible vs MC stderr at stated ray counts).
- pytest fixtures vs standalone unittest style — **recommendation: pytest fixtures** (project already uses pytest throughout `backlight_sim/tests/`).
- Report HTML template — **recommendation: reuse `io/report.py`'s matplotlib→base64 PNG pattern**.

### Deferred Ideas (OUT OF SCOPE)

- BRDF / measured-material validation (requires external datasets).
- Experimental/measurement fit.
- Performance benchmarking (separate concern; C++-07 already covers speedup validation).
- TIR critical-angle case (scheduled for Phase 8's LGP extension per ROADMAP.md).
- Adding new physics — suite only verifies existing implementation.

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GOLD-01 | Integrating-sphere uniformity vs analytical cos-weighted flux | §Case 1 — diffuse-reflector sphere approximation; Python path (solid-body or large rect tessellation) |
| GOLD-02 | Lambertian flat emitter vs I(θ) = I₀·cos(θ) | §Case 2 — far-field sphere detector or per-bin angular binning; Python path (far-field forces Python) |
| GOLD-03 | Fresnel T(θ) at glass (s/p-avg) across incidence angles | §Case 3 — SolidBox with `refractive_index=1.5`; Python path |
| GOLD-04 | Single-bounce specular reflection angle | §Case 4 — tilted specular reflector + sphere detector; C++ path eligible |
| GOLD-05 | Spectral n(λ) dispersion vs Snell at sampled λ | §Case 5 — SolidPrism + `spectral_material_data`; Python path; **closes memory flag** |
| GOLD-06 | Tolerance-based PASS/FAIL reporting | §Tolerance Design — per-case 3σ bound derived from MC stderr |
| GOLD-07 | pytest integration + `python -m backlight_sim.golden --report` CLI | §Suite Architecture, §CLI Report |
| GOLD-08 | Suite runs < 5 min on dev laptop | §Sampling Rate budget: ~200k rays × 5 cases |

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Scene construction per case | `core/` + `io/presets`-style helper | — | Tests must build a `Project` headlessly; no GUI imports. |
| Tracing execution | `sim/tracer.py::RayTracer.run()` | `sim/blu_tracer` (C++) | Tests call the public `RayTracer(project).run()` entry point — dispatch decision is the tracer's, not the test's. |
| Analytical reference math | new `tests/golden/references.py` | — | Pure Python + numpy; keep reference math isolated from tracer code. |
| PASS/FAIL assertion | pytest test body | shared fixture `assert_within_tolerance(...)` | Standard pytest pattern; mirrors `test_tracer.py` style. |
| HTML report | new `backlight_sim/golden/` pkg + `io/report.py` pattern | matplotlib (already dep of `io/report.py`) | Reuse the base64-embedded PNG pattern; headless-safe (matplotlib.use("Agg")). |
| CLI entry | `backlight_sim/golden/__main__.py` | stdlib `argparse` | Mirror simplicity of existing code; no new dep. |

---

## Standard Stack

### Core (already in repo)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | already in requirements.txt | Test runner | [VERIFIED: backlight_sim/tests/test_tracer.py] — entire test suite uses pytest |
| numpy | already in requirements.txt | Reference math + MC post-processing | [VERIFIED: core requirement] |
| matplotlib | already indirect via `io/report.py` | Report plots (residual vs angle/λ) | [VERIFIED: io/report.py:18] — `matplotlib.use("Agg")` headless pattern already in use |
| argparse | stdlib | CLI arg parsing for `--report` | [VERIFIED: stdlib] — repo has no typer/click usage; match existing stdlib discipline |

### No new dependencies required.

Rationale: keeping the suite dep-free is defensible (a) because matplotlib is already an optional dep pulled by `io/report.py`, (b) because click/typer would push new packages into the PyInstaller bundle for a single CLI entry that argparse handles in ~15 LOC.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| argparse | typer/click | Nicer UX, but new dep; 1 CLI command doesn't justify it. |
| pytest fixtures | unittest | Repo uses pytest already; consistency wins. |
| One file per case | Single mega-test file | 5 cases warrants 5 files — keeps per-case math + scene build colocated. |

---

## Runtime State Inventory

This is a new test suite; no rename/refactor. **Not applicable — all 5 categories confirmed empty:**

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — greenfield tests | — |
| Live service config | None — pytest local | — |
| OS-registered state | None | — |
| Secrets/env vars | None | — |
| Build artifacts | None — pure Python test module | — |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | All | [CITED: STATE.md — `blu_tracer.cp312-win_amd64.pyd`] | 3.12 | — |
| pytest | All cases | [VERIFIED: backlight_sim/tests/] | whatever requirements.txt pins | — |
| numpy | Reference math | [VERIFIED] | — | — |
| matplotlib | Report plots | [VERIFIED: io/report.py] | — | Suite still passes without it; report falls back to text-only (same pattern as `_grid_to_png_base64` returning "") |
| `backlight_sim.sim.blu_tracer` (.pyd) | Specular case (C++ path) | [VERIFIED: STATE.md — build complete] | cp312-win_amd64 | HARD CRASH per D-09 (intentional); prerequisite for any test |

**No blocking dependencies.**

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | none currently — tests auto-discovered from `backlight_sim/tests/` |
| Quick run command | `pytest backlight_sim/tests/golden/ -x` |
| Full suite command | `pytest backlight_sim/tests/ -x` |
| Golden-only | `pytest backlight_sim/tests/golden/ -v --tb=short` |
| Report command | `python -m backlight_sim.golden --report [--out DIR] [--rays N]` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| GOLD-01 | Integrating-sphere uniformity flat within tolerance | physics | `pytest backlight_sim/tests/golden/test_integrating_sphere.py -x` | ❌ Wave 0 |
| GOLD-02 | Lambertian emitter angular intensity = I₀·cos(θ) | physics | `pytest backlight_sim/tests/golden/test_lambertian_cosine.py -x` | ❌ Wave 0 |
| GOLD-03 | Fresnel T(θ) matches analytic (0°/30°/45°/60°/80°) | physics | `pytest backlight_sim/tests/golden/test_fresnel_glass.py -x` | ❌ Wave 0 |
| GOLD-04 | θ_out = θ_in specular, residual < tolerance | physics | `pytest backlight_sim/tests/golden/test_specular_reflection.py -x` | ❌ Wave 0 |
| GOLD-05 | Prism exit angle matches Snell at 450/550/650 nm | physics | `pytest backlight_sim/tests/golden/test_prism_dispersion.py -x` | ❌ Wave 0 |
| GOLD-06 | Report CLI writes HTML + markdown to disk | integration | `pytest backlight_sim/tests/golden/test_cli_report.py -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest backlight_sim/tests/golden/ -x` — expected ~3–5 min.
- **Per wave merge:** `pytest backlight_sim/tests/ -x` — full suite, includes golden + 124 existing tests.
- **Phase gate:** Golden suite green across 3 consecutive seeds before `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] `backlight_sim/tests/golden/__init__.py` — test package marker
- [ ] `backlight_sim/tests/golden/conftest.py` — shared `assert_within_tolerance` + minimal-project builder fixtures
- [ ] `backlight_sim/tests/golden/references.py` — analytical formulas (no tracer imports)
- [ ] `backlight_sim/tests/golden/test_integrating_sphere.py`
- [ ] `backlight_sim/tests/golden/test_lambertian_cosine.py`
- [ ] `backlight_sim/tests/golden/test_fresnel_glass.py`
- [ ] `backlight_sim/tests/golden/test_specular_reflection.py`
- [ ] `backlight_sim/tests/golden/test_prism_dispersion.py`
- [ ] `backlight_sim/tests/golden/test_cli_report.py`
- [ ] `backlight_sim/golden/__init__.py` — CLI package
- [ ] `backlight_sim/golden/__main__.py` — `python -m backlight_sim.golden` entry
- [ ] `backlight_sim/golden/cases.py` — case registry (shared between pytest + CLI)
- [ ] `backlight_sim/golden/report.py` — HTML/markdown renderer

---

## Analytical Reference Formulas

### Case 1 — Integrating-sphere uniformity

**Geometry:** A closed sphere (approximated, see pitfall below) of radius R, interior coated with a diffuse Lambertian reflector of reflectance ρ. One isotropic point source of total flux Φ at center.

**Physics:** After infinite multiple diffuse bounces inside a perfectly integrating sphere, the interior irradiance E on the wall is uniform (independent of position) and equals

> **E = Φ · ρ / [ A · (1 − ρ) ]**   (standard integrating-sphere equation; A = 4πR²)

Equivalently the *per-bounce-1 direct* component is E₀ = Φ / A, and the integrating factor (geometric series for diffuse reflectance) is ρ/(1−ρ). For ρ = 0.95, R = 50 mm: A = 31415.9 mm², E ≈ Φ · 0.95 / (31415.9 · 0.05) = Φ · 6.048×10⁻⁴ mm⁻². Normalize Φ = 1000 → E ≈ 0.6048 lm/mm².

**What to measure from MC:** Cover the inner wall with Lambertian-reflector surfaces and place a *small* detector patch on the wall (say 10×10 mm) with coarse binning (e.g. 5×5). The average bin value divided by the patch area gives E_measured. Compute spatial CV across the detector bins as the uniformity metric.

**Tolerance plan:** The analytical answer holds only asymptotically (ρ → 1, infinite bounces). With ρ = 0.95 and `max_bounces = 50`, the geometric tail remainder is ρ^50 ≈ 0.0769 → systematic 8% undercount. Either (a) set ρ = 0.85 to converge faster (tail 0.85^50 ≈ 3×10⁻⁴), OR (b) compute the expected finite-bounce truncation analytically:
> **E(N) = (Φ/A) · ρ · (1 − ρ^N) / (1 − ρ)**
and compare to that. **Recommendation: (b)** — it keeps ρ = 0.9 (closer to the "real sphere" intuition) and makes the tolerance tight. Target tolerance: **±2% at 500k rays** (asymptotic MC stderr on patch average ≈ 1/√N_hits).

### Case 2 — Lambertian flat emitter cosine law

**Geometry:** One `PointSource` with `distribution = "lambertian"` and `direction = (0,0,1)` placed at origin in free space (no surfaces). A far-field sphere detector (`SphereDetector(mode="far_field")`) centered on source, radius irrelevant for far-field (bins by ray direction, not hit position).

**Physics:** A Lambertian emitter has angular intensity
> **I(θ) = I₀ · cos(θ)**   for θ ∈ [0, π/2], zero otherwise; θ measured from the emitter normal.

After normalization for solid-angle-per-bin (the `candela_grid` post-processing in `compute_farfield_candela` at tracer.py:2934), the candela value per bin should equal (Φ/π)·cos(θ_bin).

**What to measure:** For each polar-angle bin i, compute mean candela over all azimuth bins φ: `candela_profile[i] = np.mean(candela_grid[i, :])`. Compare against `I0 * cos(theta_i)` where `I0 = total_flux / π`.

**Tolerance plan:** For `n_theta = 36` polar bins, at 1M rays the expected rays per bin > 25000 at the equator dropping to ~0 near θ=90° (where cos(θ)→0 — use θ_max = 80° to exclude the grazing blowup). Target tolerance: **±3% RMS deviation normalized to peak, θ ∈ [0°, 80°], at 500k rays.**

### Case 3 — Fresnel transmittance at a glass interface

**Geometry:** `SolidBox` with material `glass` (refractive_index = 1.5), large enough that single-interface physics dominates. Source above the top face pointing downward at incidence angle θ (aim via source `direction` vector rotated about an in-plane axis). Place an absorbing detector *below* the box to measure transmitted flux and an absorbing detector *above* the box near the source to measure reflected flux.

**Physics:** Unpolarized Fresnel reflectance:
> **r_s = [n₁·cosθ_i − n₂·cosθ_t] / [n₁·cosθ_i + n₂·cosθ_t]**
> **r_p = [n₂·cosθ_i − n₁·cosθ_t] / [n₂·cosθ_i + n₁·cosθ_t]**
> **R(θ) = ½ · (r_s² + r_p²)**,   **T(θ) = 1 − R(θ)**

With Snell: n₁·sin θ_i = n₂·sin θ_t. For n₁ = 1.0 (air), n₂ = 1.5:
- θ = 0°: R = ((1−1.5)/(1+1.5))² = 0.04 → T = 0.96
- θ = 30°: R ≈ 0.0426 → T ≈ 0.9574
- θ = 45°: R ≈ 0.0505 → T ≈ 0.9495
- θ = 60°: R ≈ 0.0931 → T ≈ 0.9069
- θ = 80°: R ≈ 0.3893 → T ≈ 0.6107

This matches the tracer's `_fresnel_unpolarized` (tracer.py:150) and the C++ mirror `fresnel_unpolarized` (material.cpp:9) — both implement the Fresnel formula on unpolarized light as Rs²+Rp² / 2.

**What to measure:** T_measured = detector_below.total_flux / source.flux. Parametrize over the 5 incidence angles above. Need ONE SolidBox test scene per angle (can loop within one test function).

**Caveat:** The box has *two* interfaces (top + bottom) — transmitted ray also hits the bottom face with the same θ_t on the air side. Account for the double interface: T_total = T(θ_i) · T(θ_t). Either (a) subtract analytically, or (b) use a very thin box with an internal absorber just inside, or (c) orient the box so the exiting face is an absorbing Rectangle (face_optics override) to kill the second interface. **Recommendation: (c)** — use SolidBox + an `optical_properties_name` override on the bottom face set to absorber, so the ray dies after one Fresnel interaction.

**Tolerance plan:** ±2% absolute on T at each angle (well inside MC stderr at 200k rays per angle: σ ≈ √(T(1−T)/N) → at T=0.96, σ = √(0.04·0.96/200k) ≈ 4.4×10⁻⁴ → 3σ ≈ 0.13%). Angles θ ∈ {0°, 30°, 45°, 60°, 80°}. **Skip 89° grazing** — source geometry breaks (beam barely enters the face) and MC stderr on T explodes because T→0. Document the exclusion.

### Case 4 — Single-bounce specular reflection

**Geometry:** One tilted specular-reflector `Rectangle` (is_diffuse=False, reflectance=1.0 to eliminate absorption). Source above at angle θ_i toward the mirror. A `SphereDetector(mode="far_field")` placed ABOVE the mirror captures the reflected direction (far-field binning = direction-based, independent of detector placement).

**Physics:** θ_r = θ_i (law of reflection); reflected ray direction = d − 2(d·n̂)n̂ where n̂ is the mirror normal pointing toward the source.

**What to measure:** Find the peak bin in `candela_grid` after far-field binning. Convert bin indices back to (θ, φ) angles. Compare peak θ to analytical reflection θ_r.

**Path dispatch caveat:** Far-field sphere detectors force the Python path per `_project_uses_cpp_unsupported_features` (tracer.py:273). To test the **C++ specular path** as well, run a second sub-case using a planar detector placed where the reflected beam should hit, and verify the centroid of the hit grid matches the analytical reflected-ray intercept point. Both paths must pass.

**Tolerance plan:** Angular residual < 1° at 100k rays for far-field bin pixel size (180°/36 = 5° per polar bin — need finer `resolution = (360, 180)` → 0.5° pixels). Tolerance: **|θ_measured − θ_expected| < 0.5° at 100k rays** with 0.5° bin resolution.

**Geom-eps bias:** Tracer offsets ray origin by `geom_eps` (≈1e-6, configurable per solid body) along the oriented normal after a bounce (tracer.py:1303, `origins[rfl_i] = hit_pts[reflects] + on_b * geom_eps`). On a 10-mm scale this is a 1e-7 relative position shift with negligible angular bias (arctan(1e-6/10) ≈ 6e-6 rad ≈ 3e-4 degree) — confirmed to be well below the 0.5° tolerance.

### Case 5 — Prism dispersion (spectral n(λ))

**Geometry:** `SolidPrism(n_sides=3, circumscribed_radius=R, length=L)` — equilateral triangular prism with 60° apex. Material has `spectral_material_data[material_name] = {"wavelength_nm": [...], "refractive_index": [...]}`. Use a BK7-like dispersion table: n(450 nm) ≈ 1.5252, n(550 nm) ≈ 1.5187, n(650 nm) ≈ 1.5145.

The source must have `spd != "white"` (otherwise no wavelengths are sampled — confirmed at tracer.py:975 `if has_spectral:` gate) — set `spd = "mono_450"`, `mono_550`, `mono_650` for three separate sub-cases, each producing monochromatic rays at that wavelength. Each sub-case uses a directional beam striking one prism face at a known θ_i (say 30°).

**Physics:** At each interface, Snell's law: n₁ sinθ_i = n₂ sinθ_t. For an equilateral prism with apex 60° and minimum-deviation geometry, the total deviation δ = 2θ_i − 60° where θ_i is the symmetric internal half-angle satisfying sinθ_ext = n·sin(30°) = n/2. Predicted exit angles (relative to normal of exit face) for θ_ext_in = 30°:
- λ = 450 nm, n=1.5252: first refraction θ₁ = arcsin(sin30°/1.5252) = 19.15°; second face internal angle = 60°−19.15° = 40.85°; exit angle θ_out = arcsin(1.5252·sin(40.85°)) = 85.07° (close to grazing — sensitive to geometry; pick a smaller θ_in or a smaller prism apex to stay away from grazing).

**Recommendation:** Use apex = 45° (right-angle prism) and θ_in ≈ 20°. Run three monochromatic sub-cases at 450/550/650 nm; place a far-field sphere detector on the exit side; the peak angular bin should match Snell prediction for that λ.

**What to measure:** peak bin in `candela_grid` → (θ, φ) → compare to analytical exit angle per wavelength. Test the **difference** θ(450) − θ(650) (the angular dispersion) — if the spectral n(λ) path is broken, all three wavelengths land in the same bin and the dispersion is zero. This is the key check that closes the memory flag — a smoke test couldn't detect this.

**Tolerance plan:** For BK7-like glass at θ_in = 20° and 45° apex, predicted angular spread θ(450) − θ(650) ≈ 0.4° (small but larger than bin resolution at 0.25°/bin). Run at 500k rays/wavelength (3 × 500k = 1.5M rays, Python path, ~3-4 min alone — this case dominates the suite budget). Tolerance: **|δλ_measured − δλ_expected| < 0.25° per wavelength, and dispersion Δθ(450→650) measured > 0 with relative error ≤ 25%.**

**Physics verification priority:** For this case, the PASS criterion must reject zero dispersion explicitly — a bug that silently uses `refractive_index` (the scalar fallback) instead of `spectral_material_data` would produce zero dispersion and still pass an ambiguous tolerance check. The test MUST assert both `|θ_measured − θ_analytical| < tol` AND `|θ(450) − θ(650)| > 0.1°`.

---

## Tolerance Design (how to choose defensibly)

For a KPI estimated from N independent ray samples, the MC standard error is σ_KPI ≈ σ_sample / √N_effective. Tolerances should sit at 3σ (99.7% CI) of this noise floor. For a fraction-type KPI like Fresnel T: σ = √(T(1−T)/N). For an angular bin: σ_angle ≈ bin_width / √(rays_per_bin · 12) (variance of uniform distribution within a bin).

**Published tolerances** (see per-case sections for derivation):

| Case | KPI | Rays | MC 3σ stderr | Chosen tolerance | Safety margin |
|------|-----|------|--------------|------------------|---------------|
| Sphere | E (patch-averaged) | 500k | ~1.3% | ±2% | 1.5× |
| Lambertian | RMS deviation from cos(θ) | 500k | ~1.5% | ±3% | 2× |
| Fresnel T | T per angle | 200k × 5 | ~0.15%–0.3% | ±2% | 6–13× |
| Specular | θ_out | 100k | ~0.1° | 0.5° | 5× |
| Prism | exit θ per λ | 500k × 3 | ~0.1° | 0.25° | 2.5× |

Each case's test body computes residual = |measured − expected|, emits `{expected, measured, residual, tolerance, rays, pass}` dict, pytest asserts residual < tolerance, CLI report collects the same dicts for the summary table.

---

## Suite Architecture

### File layout

```
backlight_sim/
├── tests/
│   └── golden/
│       ├── __init__.py
│       ├── conftest.py               # assert_within_tolerance fixture, RNG seed, budget helper
│       ├── references.py             # pure analytical math (no tracer import)
│       ├── test_integrating_sphere.py
│       ├── test_lambertian_cosine.py
│       ├── test_fresnel_glass.py
│       ├── test_specular_reflection.py
│       ├── test_prism_dispersion.py
│       └── test_cli_report.py        # integration test for the CLI entry
└── golden/                           # CLI + report package (shared with tests)
    ├── __init__.py
    ├── __main__.py                   # `python -m backlight_sim.golden`
    ├── cases.py                      # GoldenCase dataclass registry; one entry per case
    └── report.py                     # HTML + markdown renderers
```

### Shared test fixture pattern (conftest.py)

```python
# Pseudocode — mirrors test_tracer.py::_make_box_scene style
@dataclass
class GoldenResult:
    name: str
    expected: float
    measured: float
    residual: float
    tolerance: float
    rays: int
    passed: bool
    notes: str = ""

@pytest.fixture
def assert_within_tolerance():
    def _check(result: GoldenResult):
        assert result.residual < result.tolerance, (
            f"{result.name}: residual={result.residual:.4g} "
            f"exceeds tolerance={result.tolerance:.4g} "
            f"(expected={result.expected:.4g}, measured={result.measured:.4g}, rays={result.rays})"
        )
    return _check
```

Each test_*.py file: builds a Project locally, runs RayTracer, computes measured KPI, produces a GoldenResult, calls the fixture. The GoldenCase objects from `backlight_sim/golden/cases.py` wrap the same logic so CLI can re-run without pytest.

### RNG determinism

Every case sets `SimulationSettings.random_seed = <fixed>` (e.g. 42). Verified this is honored end-to-end — `RayTracer.run()` passes the seed into `_trace_single_source` (Python) and `_cpp_trace_single_source` (C++) alike. Do NOT let pytest randomize seeds; use a constant. For stability-across-seeds checking, write a `tests/golden/test_seed_stability.py` that runs each case with seeds {1, 42, 100} and checks all three PASS — this is NOT a perf-budget case (can be skipped if budget tight).

### Budget allocation (target < 5 min total)

Measured reference: C++ path ~168 ms per 1M rays on simple_box (STATE.md); Python spectral/solid-body path is currently the drop-in fallback (the pre-C++ Python path). Assume Python path ≈ 30× slower (≈ 5 s/1M rays for solid-body scenes of 10–20 surfaces; conservative).

| Case | Path | Rays | Estimated time | Notes |
|------|------|------|----------------|-------|
| Specular (C++) | C++ | 100k | ~2 s | Uses Rectangle specular reflector — C++ eligible |
| Specular (Python far-field sub-case) | Python | 100k | ~5 s | Far-field sphere forces Python |
| Lambertian cosine | Python | 500k | ~15 s | Far-field sphere |
| Fresnel × 5 angles | Python | 5 × 200k = 1M | ~30 s | SolidBox forces Python |
| Integrating sphere | Python | 500k | ~40 s | SolidBox approximation forces Python; many bounces |
| Prism × 3 λ | Python | 3 × 500k = 1.5M | ~60 s | Spectral forces Python |
| **Total** | — | ~3.2M rays | **~2.5 min** | Fits inside 5-min budget with margin |

All estimates are heuristic; Wave 0 must include a budget-probe task that actually measures these and tunes N downward if any case overshoots.

---

## CLI + Report (`python -m backlight_sim.golden`)

### Why `backlight_sim/golden/` (not `backlight_sim/tests/golden/`)

The CONTEXT spec says `python -m backlight_sim.golden --report`. This requires `backlight_sim/golden/__main__.py` — the test directory cannot host the `__main__` because tests are not a shipped module and excluding `tests/` from PyInstaller is the current convention. The pytest files in `tests/golden/` import the case definitions from `backlight_sim.golden.cases` — single source of truth.

### CLI surface

```
python -m backlight_sim.golden --report [--out DIR] [--rays N] [--cases CASE1,CASE2]
  --report       Write HTML + markdown summary (otherwise print to stdout)
  --out DIR      Output directory (default: ./golden_reports/YYYYMMDD_HHMMSS/)
  --rays N       Override the per-case default ray count (for faster/slower runs)
  --cases LIST   Comma-separated case names to run (default: all)
  -v             Verbose per-case progress
```

Use stdlib `argparse` (already the project's implicit standard — no click/typer references in the repo).

### Report structure (reuses io/report.py pattern)

Per `io/report.py:15-35`, the repo's convention is `matplotlib.use("Agg")` → figure → BytesIO → base64 → embed in HTML. Reuse this verbatim for:
- **Per-case summary table:** name, expected, measured, residual, tolerance, rays, PASS/FAIL (colored).
- **Fresnel panel:** plot T_measured vs T_analytical across 5 angles (scatter + analytic curve).
- **Prism panel:** plot θ_exit vs λ (three markers + analytic curve).
- **Overall verdict:** green if all cases PASS, red if any FAIL; run timestamp, Python version, `blu_tracer` module origin (via `importlib.util.find_spec`) — the last one is critical for reproducibility since the .pyd is external to the wheel.

### Markdown output

Produced alongside HTML; uses same GoldenResult dicts. Purpose: include in PR descriptions / CI logs without rendering HTML. Simple table format.

---

## Integration with Existing Project Model

### Reused helpers

- `Rectangle.axis_aligned(...)` — trivial walls for cases 1, 4.
- `SolidBox(name, center, size, material_name, geom_eps=...)` — case 3 (Fresnel glass slab).
- `SolidPrism(...)` — case 5. Note `n_sides = 3` gives triangular cross-section; apex = 60° (equilateral). For a non-equilateral custom-angle prism, must pick `n_sides` carefully — recommend sticking with n_sides=3 and documenting the 60° apex as fixed.
- `SphereDetector(..., mode="far_field")` — cases 2, 4 (sub-case), 5.
- `SphereDetector(..., mode="near_field")` — case 1 patch-style detector (OR an interior `DetectorSurface` — both work).

### New helpers (build into conftest.py)

- `_make_single_interface_glass_scene(angle_deg, rays, n_glass=1.5)` — case 3.
- `_make_specular_mirror_scene(angle_deg, rays)` — case 4.
- `_make_prism_scene(wavelength_nm, apex_deg, theta_in_deg, rays)` — case 5.
- `_make_integrating_sphere_scene(radius, rho, rays)` — case 1.
- `_make_lambertian_emitter_scene(rays)` — case 2.

### Dispatch predicate (which code path runs)

Confirmed from `_project_uses_cpp_unsupported_features()` at tracer.py:251:

| Case | Has solid body? | Has non-white SPD? | Has far-field sphere det? | Path |
|------|:---:|:---:|:---:|:---:|
| 1 Sphere (SolidBox sphere approx) | ✓ | ✗ | ✗ | **Python** |
| 1 Sphere (Rectangle tessellation alt) | ✗ | ✗ | ✗ | C++ |
| 2 Lambertian | ✗ | ✗ | ✓ | **Python** |
| 3 Fresnel | ✓ (SolidBox glass) | ✗ | ✗ | **Python** |
| 4 Specular (planar det) | ✗ | ✗ | ✗ | **C++** |
| 4 Specular (far-field sub-case) | ✗ | ✗ | ✓ | **Python** |
| 5 Prism | ✓ (SolidPrism) | ✓ (mono_*) | ✓ optional | **Python** |

**4 of 5 primary cases exercise the Python physics path.** Only Case 4 primary exercises C++ specular. This is appropriate — the analytical physics the suite is validating (Fresnel, Snell, dispersion) lives exclusively in the Python path (confirmed: C++ material.cpp has `fresnel_unpolarized` + `refract_snell` implementations but the dispatch in `apply_material` never calls them for the current C++ surface set — only reflector/absorber/diffuser on plain Rectangles).

### Spectral path wiring (Case 5 deep-dive)

The spectral refraction path `tracer.py:1242-1247`:
```python
spec_data_sb = (self.project.spectral_material_data or {}).get(box.material_name) if wavelengths is not None else None
if spec_data_sb is not None and "refractive_index" in spec_data_sb:
    spec_wl_sb = np.asarray(spec_data_sb["wavelength_nm"], dtype=float)
    n_lambda_sb = np.interp(wavelengths[hit_idx], spec_wl_sb, np.asarray(spec_data_sb["refractive_index"], dtype=float))
    n2_arr = np.where(entering, n_lambda_sb, exit_n)
else:
    n2_arr = np.where(entering, box_n, exit_n)
```

This path only activates when:
1. `wavelengths is not None` — requires `has_spectral = any(s.spd != "white")` at tracer.py:631
2. `spec_data_sb is not None` — requires `project.spectral_material_data[material_name]` populated
3. `"refractive_index" in spec_data_sb` — dict must have the key

**Equivalent SolidPrism path confirmed at tracer.py:1384-1389** — same logic applies to `SolidPrism`. SolidCylinder has matching code at tracer.py:1384 block.

**Memory-flag closure requires:** The Case 5 test must construct a Project meeting all three conditions and confirm a measurable dispersion. If any of these three conditions silently fails (e.g. SPD falls back to "white", or `spectral_material_data` key mismatches material_name), Δθ across wavelengths collapses to zero — which is exactly the regression this test must catch.

---

## Common Pitfalls

### Pitfall 1: Double-counting interfaces on a SolidBox
**What goes wrong:** A glass SolidBox has 6 faces; a ray entering the top refracts in, then hits the bottom and refracts out (or reflects via TIR). Measured transmittance = T(θ_i) · T(θ_t), not T(θ_i).
**Why it happens:** SolidBox is a closed body; there's no "half-space glass" primitive.
**How to avoid:** Set `optical_properties_name` on the far face to an absorbing coating (as discussed in Case 3). Confirmed the face_optics override path at tracer.py:1163 handles this before Fresnel dispatch.
**Warning signs:** Measured T = 0.92 for θ=0° (expected T=0.96 for single interface) → double-interface.

### Pitfall 2: Far-field sphere detector forces Python path — silent routing
**What goes wrong:** Testing "the C++ specular path" with a far-field detector silently routes to Python because of the `mode == "far_field"` dispatch at tracer.py:273.
**Why it happens:** Far-field binning uses direction-at-hit which C++ doesn't emit.
**How to avoid:** For C++ path coverage, use a planar `DetectorSurface` and compute the hit centroid analytically; for Python path coverage (Case 4 primary), use far-field binning for direct angular readout.
**Warning signs:** Test passes unexpectedly fast for what should be a C++-eligible scene.

### Pitfall 3: Spectral test passes with zero dispersion
**What goes wrong:** If `spectral_material_data` dict key doesn't match `box.material_name` exactly, the `.get()` returns None, the else-branch uses `box_n` (scalar), and all wavelengths refract identically → Δθ = 0. Test that only checks `|θ_measured − θ_analytical| < 0.5°` can still pass because 0° is within 0.5° of ALL expected angles if they're all within 1° of each other.
**Why it happens:** Silent dict-lookup fallback; tolerance band wide enough to mask the bug.
**How to avoid:** Case 5 asserts BOTH `|θ(λ) − θ_analytical(λ)| < tol` AND `θ(λ_blue) − θ(λ_red) > 0.1°` (signal-of-dispersion check).
**Warning signs:** θ(450) ≈ θ(650) within bin resolution — dispersion is zero; scalar n is being used.

### Pitfall 4: Integrating sphere approximation with finite max_bounces
**What goes wrong:** Analytical E = Φρ/[A(1−ρ)] assumes infinite bounces; at max_bounces=50 and ρ=0.95, truncation error is ~8%.
**Why it happens:** Geometric series ρ^(N+1)/(1−ρ) tail is not negligible at high reflectance.
**How to avoid:** Use the finite-bounce formula E(N) = (Φ/A)·ρ·(1−ρ^N)/(1−ρ); OR use ρ=0.85 (tail ≈ 3×10⁻⁴ at N=50).
**Warning signs:** Systematic bias in measured E scaling with ρ — not random MC noise.

### Pitfall 5: Sphere geometry from SolidBox faces is not a sphere
**What goes wrong:** A SolidBox is 6 planar faces; a real integrating sphere is curved. Uniformity on a cube's interior is *not* perfectly flat (corners see more solid angle than faces).
**Why it happens:** The engine has no sphere-body primitive; we must approximate.
**How to avoid:** Either (a) use a SolidBox and measure uniformity on an inner Lambertian-diffuser patch far from corners, comparing to the finite-bounce cubic integrating box formula (different geometric factor — derive numerically via direct MC); OR (b) build a tessellated near-sphere from many Rectangles. **Recommendation (a)** — SolidBox + analytical "integrating-cavity" formula where E = Φρ/[A_total·(1−ρ)] still holds for any convex closed Lambertian cavity (standard result — the shape only affects the transient/direct component, not the steady-state after many bounces). Document that the suite validates "integrating cavity" not strictly "integrating sphere".

### Pitfall 6: Source flux_tolerance jitter violates determinism across seeds
**What goes wrong:** `flux_tolerance > 0` adds per-source flux jitter (Plan 02-03 decision: applied in Python before C++ serialization). Tests that leave it at 0 are fine; tests that set it blow up seed-stability testing.
**How to avoid:** Leave `flux_tolerance = 0.0` for all golden cases — they're verifying MEAN physics, not manufacturing variance (that's Phase 5's domain).

### Pitfall 7: Matplotlib missing in minimal CI
**What goes wrong:** `io/report.py` gracefully degrades when matplotlib is missing (returns empty string at `_grid_to_png_base64`). The golden CLI `--report` must do the same OR declare matplotlib required.
**How to avoid:** Follow the existing `try: import matplotlib except ImportError: skip_plots=True` pattern; write text-only markdown unconditionally; HTML with embedded plots conditionally.

---

## Code Examples

### Shared analytical references (references.py)

```python
# Source: Fresnel equations — Born & Wolf, Principles of Optics, §1.5.2
# Verified against tracer.py::_fresnel_unpolarized and material.cpp::fresnel_unpolarized
import numpy as np

def fresnel_transmittance_unpolarized(theta_i_rad: float, n1: float, n2: float) -> float:
    """Analytical unpolarized T(θ) at a flat interface. Returns scalar in [0,1]."""
    cos_i = np.cos(theta_i_rad)
    sin_t_sq = (n1 / n2) ** 2 * (1 - cos_i ** 2)
    if sin_t_sq >= 1.0:
        return 0.0  # TIR
    cos_t = np.sqrt(1 - sin_t_sq)
    rs = (n1 * cos_i - n2 * cos_t) / (n1 * cos_i + n2 * cos_t)
    rp = (n2 * cos_i - n1 * cos_t) / (n2 * cos_i + n1 * cos_t)
    R = 0.5 * (rs ** 2 + rp ** 2)
    return 1.0 - R

def integrating_cavity_irradiance(phi: float, area: float, rho: float, n_bounces: int) -> float:
    """Finite-bounce integrating-cavity wall irradiance (any closed Lambertian cavity)."""
    return (phi / area) * rho * (1 - rho ** n_bounces) / (1 - rho)

def lambert_cosine(i0: float, theta_rad: np.ndarray) -> np.ndarray:
    return i0 * np.cos(theta_rad)

def snell_exit_angle(theta_in_rad: float, n: float, apex_rad: float) -> float:
    """Prism exit angle (symmetric incidence, prism apex, refractive index n)."""
    theta1 = np.arcsin(np.sin(theta_in_rad) / n)    # first face refraction
    theta2 = apex_rad - theta1                       # geometry inside prism
    if n * np.sin(theta2) > 1.0:
        return np.nan                                # TIR at exit face
    return np.arcsin(n * np.sin(theta2))
```

### Minimal Fresnel test shape (test_fresnel_glass.py)

```python
# Source: pattern mirrors backlight_sim/tests/test_tracer.py
import pytest
import numpy as np
from backlight_sim.tests.golden.references import fresnel_transmittance_unpolarized

@pytest.mark.parametrize("theta_deg", [0, 30, 45, 60, 80])
def test_fresnel_transmittance_matches_analytic(theta_deg, assert_within_tolerance, make_fresnel_scene):
    project = make_fresnel_scene(theta_deg=theta_deg, rays=200_000, n_glass=1.5)
    result = RayTracer(project).run()
    T_measured = result.detectors["transmitted"].total_flux / project.sources[0].flux
    T_expected = fresnel_transmittance_unpolarized(np.radians(theta_deg), 1.0, 1.5)
    assert_within_tolerance(GoldenResult(
        name=f"fresnel_T_theta={theta_deg}",
        expected=T_expected,
        measured=T_measured,
        residual=abs(T_measured - T_expected),
        tolerance=0.02,
        rays=200_000,
        passed=None,  # filled in by fixture
    ))
```

---

## State of the Art

Not applicable — the physics is textbook (Fresnel equations 1823, Snell's law 1621). No ecosystem evolution affects this phase.

---

## Project Constraints (from CLAUDE.md)

- `core/`, `sim/`, `io/` must never import PySide6 — confirmed applies: `backlight_sim/golden/` package must stay headless (the report uses matplotlib with Agg backend like `io/report.py` already does).
- Tests live under `backlight_sim/tests/` — new module at `backlight_sim/tests/golden/` matches.
- Run `pytest backlight_sim/tests/` before committing simulation/core changes — explicit in CLAUDE.md; golden suite becomes part of this standard check.
- Project JSON format uses `.get(key, default)` — not applicable here (no new JSON fields introduced).
- Session changes appended to `CODEX.md` with session ID, title, files touched, validation notes.
- No new packaging complexity — no new heavy deps; PyInstaller spec unaffected.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Python path runtime ≈ 30× C++ (≈ 5 s per 1M rays on a 10–20 surface scene) | Budget table | If 60×, prism case alone takes 2 min → squeezes 5-min budget; mitigation = reduce prism rays from 500k to 200k at cost of tighter tolerance. |
| A2 | `io/report.py` matplotlib Agg pattern is still the repo convention (not replaced by pyqtgraph headless) | CLI/Report section | Low — file still present in repo; confirmed on read. |
| A3 | `spd = "mono_450"` naming convention is valid for wavelength-specific sources | Case 5 | Medium — must verify in `backlight_sim/sim/spectral.py::get_spd_from_project`; if the naming is different, adapt to whatever key triggers monochromatic sampling. Wave 0 task: confirm SPD naming. |
| A4 | Integrating-cavity formula E = Φρ/[A(1−ρ)] generalizes to any convex Lambertian cavity including a cube | Case 1 pitfall 5 | Low — this is a standard result (any closed Lambertian cavity converges to uniform after infinite bounces); the transient (few-bounce) behavior differs but steady-state doesn't. |
| A5 | `_project_uses_cpp_unsupported_features` predicate is stable and won't silently add new unsupported features during Phase 3 | Dispatch table | Low — predicate is explicit enumeration, not catch-all; any additions would be a Phase 3 concern if they land first. |
| A6 | BK7 dispersion values at 450/550/650 nm are acceptable reference values | Case 5 | Low — can substitute any spectral data in `spectral_material_data`; choice of glass is arbitrary. Wave 0 may want to use a Cauchy-equation synthetic n(λ) for more predictable analytical derivation. |
| A7 | `SolidPrism(n_sides=3)` yields an equilateral triangular cross-section with 60° apex | Case 5 | Low — confirmed from solid_body.py:115 `_compute_polygon_vertices` using evenly-spaced angles; n_sides=3 → 60° apex. |

---

## Open Questions

1. **SolidCylinder/SolidPrism refraction spectral path: tested by Case 5?**
   - What we know: SolidPrism with spectral_material_data exercises the tracer.py:1384 block (matching SolidBox:1242). Case 5 as designed covers SolidPrism.
   - What's unclear: should we also add a SolidCylinder sub-case? Memory flag says "solid body spectral n(λ) path" which the prism covers for the prism-branch, but not the cylinder-branch.
   - Recommendation: Defer cylinder to Phase 8 (LGP uses cylinders); document in CODEX that Case 5 covers prism-branch only.

2. **Should Case 4 test both C++ AND Python specular, or just one?**
   - What we know: C++ reflect_specular (material.cpp:74) and Python `_reflect_batch` (tracer.py) should produce identical physics.
   - What's unclear: is duplicate coverage worth the ~30% budget hit?
   - Recommendation: Test both as a low-cost sub-case split (each 100k rays, ~7 s total) — explicit dual-path coverage is what motivates this phase.

3. **CI integration scope:** Does the project have CI beyond `pytest`? (No `.github/workflows/` observed in the tree earlier.)
   - What we know: STATE.md says 124 tests green, implies pre-commit discipline via the command in CLAUDE.md.
   - What's unclear: Is there a separate CI layer to wire the `--report` command into?
   - Recommendation: Wave 0 checks for CI config and scopes the wiring decision accordingly; if none, the pytest integration alone fulfills the requirement.

---

## Security Domain

Not applicable — no ASVS category fires. The suite is:
- No network I/O (V9 network security inapplicable).
- No user input beyond CLI args handled by argparse (V5 input validation: argparse's built-in type checking is sufficient).
- No secrets handling (V2/V6 inapplicable).
- No crypto (V6 inapplicable).
- No authentication or session (V3/V4 inapplicable).

The only relevant discipline: CLI argument parsing must not accept arbitrary filesystem paths without validation — stdlib argparse with default output directory under `./golden_reports/` + explicit `--out` accepting a Path avoids directory-traversal concerns. No CVE-class risk for a local test tool.

---

## Sources

### Primary (HIGH confidence)
- `backlight_sim/sim/tracer.py` — `_fresnel_unpolarized` (line 150), `_refract_snell` (192), `_project_uses_cpp_unsupported_features` (251), spectral SolidBox path (1242–1305), SolidCylinder/Prism paths (1384+).
- `backlight_sim/sim/_blu_tracer/src/material.cpp` — `fresnel_unpolarized` (line 9), `refract_snell` (26), `apply_material` (51) — confirms C++ Fresnel/Snell implementations match Python.
- `backlight_sim/sim/sampling.py` — `sample_lambertian` via Malley's method (line 21), `sample_isotropic` (8).
- `backlight_sim/core/detectors.py` — `SphereDetector(mode="far_field")` definition (line 73), `compute_farfield_candela` at tracer.py:2934.
- `backlight_sim/core/solid_body.py` — SolidBox/Cylinder/Prism definitions + `get_faces()` expansion.
- `backlight_sim/core/project_model.py` — `spectral_material_data` field at line 46.
- `backlight_sim/tests/test_tracer.py` — existing pytest pattern to mirror (`_make_box_scene`, parametrization style, 20 tests).
- `backlight_sim/io/report.py` — HTML+base64-PNG report pattern to reuse.
- `.planning/STATE.md` — confirms Python 3.12 target, .pyd artifact naming, 124-test baseline, D-09 hard-crash on missing extension.
- `.planning/phases/03-golden-reference-validation-suite/03-CONTEXT.md` — phase scope, locked decisions.
- `~/.claude/projects/G--blu-optical-simulation/memory/project_spectral_ri_testing.md` — memory flag text.

### Secondary (MEDIUM confidence)
- Training knowledge: Fresnel equations, Snell's law, Lambert's cosine law, integrating-sphere equation — textbook physics, independent-source-agreed; not verified from web but verifiable against any optics textbook.
- BK7 dispersion values at 450/550/650 nm — training knowledge; Wave 0 task recommends verifying against RefractiveIndex.info or replacing with synthetic Cauchy-equation values.

### Tertiary (LOW confidence)
- Timing estimate for Python path (≈ 5 s per 1M rays): extrapolated from C++ speedup ratio in STATE.md Wave 4 decision (29.8×). Wave 0 should measure empirically.

---

## Metadata

**Confidence breakdown:**
- Analytical reference formulas: HIGH — all derivations are textbook optics, cross-checked against tracer source.
- Dispatch/path map: HIGH — directly read from `_project_uses_cpp_unsupported_features` source.
- Tolerance values: MEDIUM — based on MC stderr theory, but practical performance will fine-tune; Wave 0 must re-measure.
- Runtime budget: MEDIUM — 30× Python/C++ ratio assumed, not measured for solid-body-heavy scenes.
- Report structure: HIGH — reuses existing proven `io/report.py` pattern.

**Research date:** 2026-04-18
**Valid until:** 2026-05-18 (30 days — the only volatile input is the Python-path ray budget, which an early Wave 0 measurement will nail down).

---

## RESEARCH COMPLETE

5 analytical cases, 4-of-5 routed through the Python physics path, under a 5-min budget — suite ready for planning; Case 5 explicitly closes the spectral-n(λ) memory flag by asserting nonzero prism dispersion on top of per-wavelength Snell-angle accuracy.
