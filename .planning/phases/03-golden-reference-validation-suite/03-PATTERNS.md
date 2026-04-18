# Phase 03: Golden-Reference Validation Suite — Pattern Map

**Mapped:** 2026-04-18
**Files analyzed:** 13 (all new)
**Analogs found:** 13 / 13 (every new file has a concrete analog in the existing repo)

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `backlight_sim/tests/golden/__init__.py` | test package marker | n/a | `backlight_sim/tests/__init__.py` (implicit empty package) | exact |
| `backlight_sim/tests/golden/conftest.py` | test fixture module | test-time shared state | `backlight_sim/tests/test_tracer.py` `_make_box_scene` helper (lines 15-39) | role-match (pytest fixture idiom) |
| `backlight_sim/tests/golden/references.py` | pure math utility | transform (angle → scalar) | `backlight_sim/sim/sampling.py` (pure numpy helpers, no PySide6) | role-match |
| `backlight_sim/tests/golden/test_integrating_sphere.py` | pytest test | request-response (Project → KPI) | `backlight_sim/tests/test_tracer.py::test_basic_simulation_produces_nonzero_heatmap` | exact |
| `backlight_sim/tests/golden/test_lambertian_cosine.py` | pytest test | request-response | `backlight_sim/tests/test_tracer.py` (same pattern as sphere) | exact |
| `backlight_sim/tests/golden/test_fresnel_glass.py` | pytest parametric test | batch (5 angles) | `test_tracer.py::test_effective_flux_current_scaling` + pytest.parametrize idiom | role-match |
| `backlight_sim/tests/golden/test_specular_reflection.py` | pytest test | request-response (dual sub-case) | `test_tracer.py::test_basic_simulation_produces_nonzero_heatmap` | exact |
| `backlight_sim/tests/golden/test_prism_dispersion.py` | pytest parametric test | batch (3 wavelengths) | `test_tracer.py::test_tracer_supports_custom_angular_distribution_name` (mutates Project, then runs) | role-match |
| `backlight_sim/tests/golden/test_cli_report.py` | pytest integration test | CLI spawn + file I/O | `test_tracer.py::test_project_serialization_new_fields` (uses tempfile) | role-match |
| `backlight_sim/golden/__init__.py` | package marker | n/a | `backlight_sim/io/__init__.py` (implicit empty) | exact |
| `backlight_sim/golden/__main__.py` | CLI entry | argparse → dispatch | `build_exe.py::main()` (lines 102-123, argparse + function dispatch) | role-match (only argparse CLI in repo) |
| `backlight_sim/golden/cases.py` | case registry (dataclass + factory) | data model | `backlight_sim/io/presets.py::PRESETS` dict + `preset_simple_box()` factory | exact |
| `backlight_sim/golden/report.py` | HTML/markdown renderer | transform (results → artifact) | `backlight_sim/io/report.py::generate_html_report` | exact |

---

## Pattern Assignments

### `backlight_sim/tests/golden/__init__.py` (package marker)

**Analog:** `backlight_sim/tests/__init__.py`

**Content:** Empty file — pytest auto-discovers test modules; package marker only so `conftest.py` is picked up with `from backlight_sim.tests.golden.references import ...` possible for future sharing.

**Invariants:** Must exist (even if empty) so pytest treats `golden/` as a package; must NOT import anything from `backlight_sim.gui`.

**Verify:** `pytest backlight_sim/tests/golden/ --collect-only`

---

### `backlight_sim/tests/golden/conftest.py` (shared fixtures)

**Analog:** `backlight_sim/tests/test_tracer.py` — `_make_box_scene` helper pattern (lines 15-39)

**Imports to mirror** (same as `test_tracer.py:1-12`):
```python
import numpy as np
import pytest
from dataclasses import dataclass

from backlight_sim.core.geometry import Rectangle
from backlight_sim.core.materials import Material, OpticalProperties
from backlight_sim.core.sources import PointSource
from backlight_sim.core.detectors import DetectorSurface, SphereDetector
from backlight_sim.core.solid_body import SolidBox, SolidPrism
from backlight_sim.core.project_model import Project, SimulationSettings
```

**Scene-builder pattern** (mirror this shape; adapt per case):
```python
# Source: backlight_sim/tests/test_tracer.py:15-39
def _make_box_scene(rays_per_source=5000, wall_reflectance=0.9,
                    wall_type="reflector", source_flux=1000.0) -> Project:
    materials = {
        "wall": Material(name="wall", surface_type=wall_type,
                         reflectance=wall_reflectance, absorption=1.0-wall_reflectance),
    }
    surfaces = [
        Rectangle.axis_aligned("floor", [0, 0, -5], (20, 20), 2, -1.0, "wall"),
        # ... 4 walls ...
    ]
    detectors = [DetectorSurface.axis_aligned("top_detector", [0, 0, 5], (20, 20), 2, 1.0, (50, 50))]
    sources = [PointSource("src1", np.array([0.0, 0.0, 0.0]), flux=source_flux)]
    settings = SimulationSettings(rays_per_source=rays_per_source, max_bounces=50,
                                  energy_threshold=0.001, random_seed=42, record_ray_paths=10)
    return Project(name="test_box", sources=sources, surfaces=surfaces,
                   materials=materials, detectors=detectors, settings=settings)
```

**Fixture pattern to add** (new; imports the GoldenResult dataclass from `backlight_sim.golden.cases`):
```python
from backlight_sim.golden.cases import GoldenResult

GOLDEN_SEED = 42  # single authoritative seed constant

@pytest.fixture
def assert_within_tolerance():
    def _check(result: GoldenResult) -> None:
        assert result.residual < result.tolerance, (
            f"{result.name}: residual={result.residual:.4g} "
            f"exceeds tolerance={result.tolerance:.4g} "
            f"(expected={result.expected:.4g}, measured={result.measured:.4g}, "
            f"rays={result.rays})"
        )
    return _check
```

**Builder fixtures to add** (one per case — mirror `_make_box_scene` shape, adapt geometry):
- `make_integrating_cavity_scene(radius, rho, rays)` — SolidBox + interior Lambertian reflector wrap + patch detector
- `make_lambertian_emitter_scene(rays)` — one PointSource(distribution="lambertian") + one SphereDetector(mode="far_field")
- `make_fresnel_scene(theta_deg, rays, n_glass=1.5)` — SolidBox with glass material, `face_optics={"bottom": "absorber"}` so only one interface counts, two DetectorSurfaces (reflected above, transmitted below)
- `make_specular_mirror_scene(theta_deg, rays, use_farfield=False)` — tilted Rectangle reflector + either planar detector (C++ path) or SphereDetector far-field (Python path)
- `make_prism_scene(wavelength_nm, apex_deg=45.0, theta_in_deg=20.0, rays=500_000)` — SolidPrism(n_sides=3) + PointSource(spd=f"mono_{wavelength_nm}") + project.spectral_material_data populated + SphereDetector far-field

**Invariants:**
- NO PySide6 imports (constraint — `tests/` runs headless; CLAUDE.md rule)
- Every scene must set `settings.random_seed = GOLDEN_SEED`
- Every scene must leave `flux_tolerance = 0.0` (pitfall 6: jitter breaks seed stability)
- Return a fresh `Project` dataclass per call (no mutation of module-level state)

**Verify:** `pytest backlight_sim/tests/golden/conftest.py -q` (should report "no tests ran" cleanly)

---

### `backlight_sim/tests/golden/references.py` (analytical math)

**Analog:** `backlight_sim/sim/sampling.py` — pure-numpy helpers, no side effects, no GUI/tracer imports

**Pattern to copy** (headers, dtype discipline, short functions):
```python
# Source: backlight_sim/sim/sampling.py top
"""Analytical reference formulas for golden tests.

No tracer imports — only numpy + stdlib math.
Each function is derived from textbook optics and referenced in RESEARCH.md.
"""
from __future__ import annotations
import numpy as np
```

**Required functions** (signatures from RESEARCH.md § Code Examples, lines 495-521):
```python
def fresnel_transmittance_unpolarized(theta_i_rad: float, n1: float, n2: float) -> float:
    """Analytical unpolarized T(θ). Verified against tracer.py::_fresnel_unpolarized."""
    cos_i = np.cos(theta_i_rad)
    sin_t_sq = (n1 / n2) ** 2 * (1.0 - cos_i ** 2)
    if sin_t_sq >= 1.0:
        return 0.0
    cos_t = np.sqrt(1.0 - sin_t_sq)
    rs = (n1 * cos_i - n2 * cos_t) / (n1 * cos_i + n2 * cos_t)
    rp = (n2 * cos_i - n1 * cos_t) / (n2 * cos_i + n1 * cos_t)
    return 1.0 - 0.5 * (rs ** 2 + rp ** 2)

def integrating_cavity_irradiance(phi: float, area: float, rho: float, n_bounces: int) -> float:
    """Finite-bounce cavity wall irradiance; matches Pitfall 4 formula."""
    return (phi / area) * rho * (1.0 - rho ** n_bounces) / (1.0 - rho)

def lambert_cosine(i0: float, theta_rad: np.ndarray) -> np.ndarray:
    return i0 * np.cos(theta_rad)

def snell_exit_angle(theta_in_rad: float, n: float, apex_rad: float) -> float:
    """Prism exit angle (symmetric incidence, apex apex_rad, refractive index n)."""
    theta1 = np.arcsin(np.sin(theta_in_rad) / n)
    theta2 = apex_rad - theta1
    if n * np.sin(theta2) > 1.0:
        return float("nan")  # TIR at exit
    return float(np.arcsin(n * np.sin(theta2)))
```

**Verification cross-check against tracer**: `_fresnel_unpolarized` at `backlight_sim/sim/tracer.py:150-189` uses exactly this s/p polarization-averaged formula; the reference function must return the same T = 1 − R for scalar inputs.

**Invariants:**
- NO imports from `backlight_sim.sim` or `backlight_sim.gui` (keep reference math isolated so a bug in the tracer can't silently corrupt the reference)
- Scalar inputs in, scalar outputs (the test body handles numpy broadcasting)
- Unit contract: angles in RADIANS, flux in the same units as the tracer

**Verify:** `python -c "from backlight_sim.tests.golden.references import fresnel_transmittance_unpolarized; print(fresnel_transmittance_unpolarized(0.0, 1.0, 1.5))"` → `0.96`

---

### `backlight_sim/tests/golden/test_integrating_sphere.py` (physics test, GOLD-01)

**Analog:** `backlight_sim/tests/test_tracer.py::test_basic_simulation_produces_nonzero_heatmap` (line 42-48) for the shape; `test_absorber_walls_fewer_hits_than_reflector` (line 58-62) for the parametric idiom.

**Pattern to mirror** (test function body):
```python
# Source pattern: test_tracer.py:42-48
import numpy as np
import pytest
from backlight_sim.sim.tracer import RayTracer
from backlight_sim.golden.cases import GoldenResult
from backlight_sim.tests.golden.references import integrating_cavity_irradiance

def test_integrating_cavity_uniformity(make_integrating_cavity_scene, assert_within_tolerance):
    rho = 0.9
    rays = 500_000
    project = make_integrating_cavity_scene(radius=50.0, rho=rho, rays=rays)
    result = RayTracer(project).run()
    det = result.detectors["patch"]
    # Measured patch-averaged irradiance (flux per unit patch area)
    patch_area = float(np.prod(project.detectors[0].size))
    E_measured = float(det.total_flux) / patch_area
    # Finite-bounce analytical prediction (RESEARCH pitfall 4)
    E_expected = integrating_cavity_irradiance(
        phi=project.sources[0].flux,
        area=4.0 * np.pi * 50.0 ** 2,  # TODO for planner: match cavity wall area (SolidBox != sphere)
        rho=rho,
        n_bounces=project.settings.max_bounces,
    )
    assert_within_tolerance(GoldenResult(
        name="integrating_cavity_E",
        expected=E_expected, measured=E_measured,
        residual=abs(E_measured - E_expected) / E_expected,
        tolerance=0.02, rays=rays, passed=None,
    ))
```

**Invariants:**
- `ρ = 0.9` + finite-bounce formula (pitfall 4 — do NOT compare to infinite-bounce analytical)
- Detector patch far from SolidBox corners (pitfall 5)
- `settings.max_bounces` must be high enough that ρ^N truncation error < tolerance

**Verify:** `pytest backlight_sim/tests/golden/test_integrating_sphere.py -x -v`

---

### `backlight_sim/tests/golden/test_lambertian_cosine.py` (physics test, GOLD-02)

**Analog:** `backlight_sim/tests/test_tracer.py::test_basic_simulation_produces_nonzero_heatmap` (pattern).

**Pattern to mirror** (far-field candela readout — uses `compute_farfield_candela` at tracer.py:2934):
```python
# Adapts tracer.py:2934 post-processing result access pattern
def test_lambertian_emitter_matches_cosine(make_lambertian_emitter_scene,
                                           assert_within_tolerance):
    rays = 500_000
    project = make_lambertian_emitter_scene(rays=rays)
    result = RayTracer(project).run()
    sd_result = result.sphere_detectors["farfield"]
    assert sd_result.candela_grid is not None  # far-field post-processing ran
    # Mean over azimuth bins for each polar bin
    profile = sd_result.candela_grid.mean(axis=1)  # (n_theta,)
    n_theta = profile.shape[0]
    theta_centers = (np.arange(n_theta) + 0.5) * np.pi / n_theta
    # Restrict to θ ∈ [0°, 80°] per RESEARCH §Case 2
    mask = theta_centers <= np.radians(80.0)
    expected = np.cos(theta_centers[mask])
    measured = profile[mask] / profile[mask].max()  # normalize to peak
    residual = float(np.sqrt(np.mean((measured - expected) ** 2)))
    # ... build GoldenResult with tolerance=0.03 ...
```

**Invariants:**
- `SphereDetector(..., mode="far_field")` — forces Python path per `_project_uses_cpp_unsupported_features` (tracer.py:272-274)
- Exclude θ > 80° (grazing blowup; cos→0 denominator)
- Restrict RMS to normalized profile, not absolute candela (source flux scaling noise otherwise)

**Verify:** `pytest backlight_sim/tests/golden/test_lambertian_cosine.py -x -v`

---

### `backlight_sim/tests/golden/test_fresnel_glass.py` (physics test, GOLD-03)

**Analog:** `backlight_sim/tests/test_tracer.py` (test_tracer structure) + `pytest.parametrize` usage already in the file (implicit from `pytest` import).

**Pattern to mirror** (RESEARCH.md § Code Examples lines 525-546 is the intended shape):
```python
import pytest
import numpy as np
from backlight_sim.sim.tracer import RayTracer
from backlight_sim.golden.cases import GoldenResult
from backlight_sim.tests.golden.references import fresnel_transmittance_unpolarized

@pytest.mark.parametrize("theta_deg", [0, 30, 45, 60, 80])
def test_fresnel_transmittance_matches_analytic(theta_deg, make_fresnel_scene,
                                                assert_within_tolerance):
    rays = 200_000
    project = make_fresnel_scene(theta_deg=theta_deg, rays=rays, n_glass=1.5)
    result = RayTracer(project).run()
    T_measured = result.detectors["transmitted"].total_flux / project.sources[0].flux
    T_expected = fresnel_transmittance_unpolarized(np.radians(theta_deg), 1.0, 1.5)
    assert_within_tolerance(GoldenResult(
        name=f"fresnel_T_theta={theta_deg}",
        expected=T_expected, measured=T_measured,
        residual=abs(T_measured - T_expected),
        tolerance=0.02, rays=rays, passed=None,
    ))
```

**Scene-builder must implement** (double-interface mitigation — pitfall 1 — see tracer.py:1242-1305 for Fresnel physics):
```python
# Conceptual sketch for conftest.py builder
def make_fresnel_scene(theta_deg, rays, n_glass=1.5):
    project = Project(name=f"fresnel_{theta_deg}")
    project.materials["glass"] = Material("glass", refractive_index=n_glass)
    project.materials["absorber"] = Material("absorber", surface_type="absorber",
                                             reflectance=0.0, absorption=1.0)
    project.optical_properties["absorber"] = OpticalProperties(...)  # or similar override
    box = SolidBox(name="slab", center=np.array([0,0,0]), dimensions=(50.0, 50.0, 2.0),
                   material_name="glass",
                   face_optics={"bottom": "absorber"})  # kills the exit interface
    project.solid_bodies.append(box)
    # ... transmitted detector below, reflected detector above, source tilted at theta_deg ...
    project.settings.random_seed = GOLDEN_SEED
    project.settings.rays_per_source = rays
    return project
```

**Key tracer contract this test exercises** (tracer.py:1256):
```python
# _fresnel_unpolarized called inside SolidBox hit handler
R_arr = _fresnel_unpolarized(cos_i_arr, n1_arr, n2_arr)
# Stochastic Russian roulette: reflect or transmit
roll = self.rng.random(len(hit_idx))
reflects = roll < R_arr
```

**Invariants:**
- SolidBox presence forces Python path (tracer.py:264)
- Absorber override on far face is MANDATORY (pitfall 1; without it T_measured ≈ T² not T)
- Skip θ = 89° (grazing breaks source geometry)

**Verify:** `pytest backlight_sim/tests/golden/test_fresnel_glass.py -x -v`

---

### `backlight_sim/tests/golden/test_specular_reflection.py` (physics test, GOLD-04, dual path)

**Analog:** `backlight_sim/tests/test_tracer.py::test_basic_simulation_produces_nonzero_heatmap`.

**Pattern to mirror** (two sub-tests — one per code path):
```python
def test_specular_angle_python_farfield(make_specular_mirror_scene, assert_within_tolerance):
    project = make_specular_mirror_scene(theta_deg=30.0, rays=100_000, use_farfield=True)
    result = RayTracer(project).run()
    sd = result.sphere_detectors["farfield"]
    # Find peak bin in candela_grid → convert to (theta, phi)
    peak_idx = np.unravel_index(np.argmax(sd.candela_grid), sd.candela_grid.shape)
    n_theta = sd.candela_grid.shape[0]
    theta_measured = (peak_idx[0] + 0.5) * np.pi / n_theta
    theta_expected = np.radians(30.0)  # law of reflection
    assert_within_tolerance(GoldenResult(
        name="specular_theta_python", expected=theta_expected,
        measured=theta_measured,
        residual=abs(theta_measured - theta_expected) * 180.0 / np.pi,  # in degrees
        tolerance=0.5, rays=100_000, passed=None,
    ))

def test_specular_angle_cpp_planar(make_specular_mirror_scene, assert_within_tolerance):
    project = make_specular_mirror_scene(theta_deg=30.0, rays=100_000, use_farfield=False)
    result = RayTracer(project).run()
    # Centroid of planar detector grid → back-compute hit angle from geometry
    # ...
```

**Invariants:**
- Far-field variant: NO SolidBox + NO spectral — only the `SphereDetector(mode="far_field")` forces Python path (tracer.py:272-274)
- Planar variant: Rectangle detector + plain specular reflector → eligible for C++ path
- Resolution `(360, 180)` to get 0.5°/bin
- Mirror reflectance = 1.0 (avoid absorption confounding)

**Verify:** `pytest backlight_sim/tests/golden/test_specular_reflection.py -x -v`

---

### `backlight_sim/tests/golden/test_prism_dispersion.py` (physics test, GOLD-05 — closes spectral memory flag)

**Analog:** `backlight_sim/tests/test_tracer.py::test_tracer_supports_custom_angular_distribution_name` (line 97-106) for the Project-mutation-then-run pattern.

**Pattern to mirror** (mutate project dict fields; then run):
```python
# Source: test_tracer.py:97-106 — mutation-style test
import pytest
import numpy as np
from backlight_sim.sim.tracer import RayTracer
from backlight_sim.golden.cases import GoldenResult
from backlight_sim.tests.golden.references import snell_exit_angle

@pytest.mark.parametrize("wavelength_nm,n_expected", [
    (450, 1.5252),
    (550, 1.5187),
    (650, 1.5145),
])
def test_prism_exit_angle_matches_snell(wavelength_nm, n_expected,
                                        make_prism_scene, assert_within_tolerance):
    rays = 500_000
    project = make_prism_scene(wavelength_nm=wavelength_nm, apex_deg=45.0,
                                theta_in_deg=20.0, rays=rays)
    # Mandatory sanity: project must actually trigger spectral path
    assert project.sources[0].spd == f"mono_{wavelength_nm}"
    assert "bk7_glass" in project.spectral_material_data  # or whatever key we use
    result = RayTracer(project).run()
    sd = result.sphere_detectors["farfield"]
    peak_idx = np.unravel_index(np.argmax(sd.candela_grid), sd.candela_grid.shape)
    n_theta = sd.candela_grid.shape[0]
    theta_measured = (peak_idx[0] + 0.5) * np.pi / n_theta
    theta_expected = snell_exit_angle(np.radians(20.0), n_expected, np.radians(45.0))
    # ...per-λ tolerance check...

def test_prism_dispersion_is_nonzero(make_prism_scene, assert_within_tolerance):
    """Regression guard: silent fallback to scalar refractive_index would zero this."""
    rays = 500_000
    # Run all 3 wavelengths; measure Δθ(450→650)
    # Per RESEARCH §Case 5 dispersion-signal check:
    # REQUIRE |θ(450) - θ(650)| > 0.1° (pitfall 3)
```

**Spectral path wiring this test MUST exercise** (from tracer.py:1242-1247, also 1384-1389 for cylinder):
```python
# tracer.py:1242-1247 — the code path this test validates
spec_data_sb = (self.project.spectral_material_data or {}).get(box.material_name) if wavelengths is not None else None
if spec_data_sb is not None and "refractive_index" in spec_data_sb:
    spec_wl_sb = np.asarray(spec_data_sb["wavelength_nm"], dtype=float)
    n_lambda_sb = np.interp(wavelengths[hit_idx], spec_wl_sb,
                            np.asarray(spec_data_sb["refractive_index"], dtype=float))
    n2_arr = np.where(entering, n_lambda_sb, exit_n)
```

**Three conditions the scene MUST satisfy** (RESEARCH §Spectral path wiring, else the test silently passes with zero dispersion):
1. `project.sources[0].spd` starts with `"mono_"` — triggers `has_spectral` (tracer.py:631, also line 261 dispatch)
2. `project.spectral_material_data["<material_name>"]` exists and the KEY matches the prism's `material_name` exactly
3. The `spectral_material_data[...]` dict has `"refractive_index"` and `"wavelength_nm"` keys populated

**Invariants:**
- `SolidPrism(n_sides=3)` — equilateral triangle (verified from solid_body.py:115 `_compute_polygon_vertices`)
- Must use far-field sphere detector (direction-based readout — the ONLY way to measure angular dispersion without huge geometry)
- Test MUST assert BOTH per-λ accuracy (<0.25°) AND nonzero inter-λ dispersion (>0.1°) — pitfall 3

**Verify:** `pytest backlight_sim/tests/golden/test_prism_dispersion.py -x -v`
**Memory flag closure:** This file is the explicit closer for `~/.claude/projects/.../memory/project_spectral_ri_testing.md`.

---

### `backlight_sim/tests/golden/test_cli_report.py` (integration test, GOLD-06)

**Analog:** `backlight_sim/tests/test_tracer.py::test_project_serialization_new_fields` (line 171+) — uses `tempfile` + subprocess-style file artifact verification.

**Pattern to mirror** (subprocess + tempfile + existence checks):
```python
# Source structure: test_tracer.py:171-... tempfile pattern
import subprocess
import sys
from pathlib import Path
import tempfile

def test_cli_report_writes_html_and_markdown():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "golden_report"
        result = subprocess.run(
            [sys.executable, "-m", "backlight_sim.golden",
             "--report", "--out", str(out),
             "--rays", "5000"],   # small ray count for CI speed
            capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert (out / "report.html").exists()
        assert (out / "report.md").exists()
        md_text = (out / "report.md").read_text(encoding="utf-8")
        for name in ("integrating_cavity", "lambertian_cosine",
                     "fresnel_glass", "specular_reflection", "prism_dispersion"):
            assert name in md_text, f"case {name} missing from report"
```

**Invariants:**
- Use `sys.executable` (not bare `python`) to survive different dev environments
- Short ray count in the CI path — this test verifies wiring, not physics
- Use `tempfile.TemporaryDirectory()` — mirrors `test_project_serialization_new_fields` pattern

**Verify:** `pytest backlight_sim/tests/golden/test_cli_report.py -x`

---

### `backlight_sim/golden/__init__.py` (package marker)

**Analog:** `backlight_sim/io/__init__.py` (implicit empty).

**Content:** Empty (or one-line docstring). Package marker only so `python -m backlight_sim.golden` and `from backlight_sim.golden.cases import GoldenCase` both work.

**Invariants:** NO PySide6 imports — this package is part of the shipped wheel and must stay headless. NO imports from `backlight_sim.gui`.

**Verify:** `python -c "import backlight_sim.golden"`

---

### `backlight_sim/golden/__main__.py` (CLI entry)

**Analog:** `build_exe.py::main()` (lines 102-123) — the only argparse-based CLI in the repo; same stdlib argparse discipline applies.

**Pattern to mirror** (argparse + function dispatch):
```python
# Source: build_exe.py:102-123
def main():
    parser = argparse.ArgumentParser(description="Build BluOpticalSim executable")
    parser.add_argument("--clean", action="store_true", help="Remove previous build artifacts first")
    parser.add_argument("--zip", action="store_true", help="Zip the dist folder after building")
    args = parser.parse_args()

    if args.clean:
        clean()
    build()
    copy_dist_assets()
    if args.zip:
        make_zip()

if __name__ == "__main__":
    main()
```

**Adapted pattern for `backlight_sim/golden/__main__.py`:**
```python
"""CLI entry: python -m backlight_sim.golden --report [--out DIR] [--rays N] [--cases LIST]."""
from __future__ import annotations
import argparse
import sys
from datetime import datetime
from pathlib import Path

from backlight_sim.golden.cases import ALL_CASES, run_case
from backlight_sim.golden.report import write_html_report, write_markdown_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m backlight_sim.golden",
        description="Run the golden-reference validation suite and emit a report.",
    )
    parser.add_argument("--report", action="store_true",
                        help="Write HTML + markdown summary (default: print to stdout)")
    parser.add_argument("--out", type=Path,
                        default=Path("golden_reports") / datetime.now().strftime("%Y%m%d_%H%M%S"),
                        help="Output directory")
    parser.add_argument("--rays", type=int, default=None,
                        help="Override per-case ray count (for fast probes)")
    parser.add_argument("--cases", type=str, default=None,
                        help="Comma-separated case names (default: all)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    cases = ALL_CASES if args.cases is None else [
        c for c in ALL_CASES if c.name in args.cases.split(",")
    ]
    results = [run_case(c, rays_override=args.rays, verbose=args.verbose) for c in cases]

    if args.report:
        args.out.mkdir(parents=True, exist_ok=True)
        write_html_report(results, args.out / "report.html")
        write_markdown_report(results, args.out / "report.md")
        print(f"Wrote report to {args.out}")

    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
```

**Invariants:**
- Stdlib `argparse` only — no `click`/`typer` (no new deps per RESEARCH §Standard Stack)
- Return nonzero exit code if any case fails (so CI integration works)
- NO PySide6 imports
- Graceful degradation if matplotlib missing (delegate to `report.py`)

**Verify:** `python -m backlight_sim.golden --report --out /tmp/gold_report --rays 5000`

---

### `backlight_sim/golden/cases.py` (case registry — shared between pytest + CLI)

**Analog:** `backlight_sim/io/presets.py` — dataclass/function registry + `PRESETS` dict (lines 15-100).

**Pattern to mirror** (factory functions + dict registry):
```python
# Source: backlight_sim/io/presets.py:15-42 + :96-100
def preset_simple_box() -> Project:
    """Single LED in a 50×50×20 mm reflective box with a detector on top."""
    project = Project(name="Simple Box")
    project.settings = SimulationSettings(rays_per_source=20_000, distance_unit="mm")
    project.materials["white_reflector"] = Material(...)
    build_cavity(project, W, H, D, ...)
    project.detectors.append(DetectorSurface.axis_aligned(...))
    project.sources.append(PointSource("LED_1", np.array([0.0, 0.0, 0.5]), ...))
    return project

PRESETS: dict[str, callable] = {
    "Simple Box (50×50×20 mm)": preset_simple_box,
    "Automotive Cluster (120×60×10 mm)": preset_automotive_cluster,
    ...
}
```

**Adapted pattern for `cases.py`:**
```python
"""Golden-reference case registry — shared source of truth for pytest + CLI."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable
import numpy as np
from backlight_sim.core.project_model import Project


@dataclass
class GoldenResult:
    name: str
    expected: float
    measured: float
    residual: float
    tolerance: float
    rays: int
    passed: bool | None = None      # None until assert step fills it in
    notes: str = ""
    # For report plots
    extra: dict = field(default_factory=dict)


@dataclass
class GoldenCase:
    name: str
    description: str
    build_project: Callable[[int | None], Project]   # rays_override -> Project
    measure: Callable[[Project, "SimulationResult"], GoldenResult]
    default_rays: int
    expected_runtime_s: float        # budget-planning aid; see RESEARCH §Budget


def run_case(case: GoldenCase, rays_override: int | None = None,
             verbose: bool = False) -> GoldenResult:
    from backlight_sim.sim.tracer import RayTracer  # lazy import
    project = case.build_project(rays_override)
    result = RayTracer(project).run()
    gr = case.measure(project, result)
    gr.passed = gr.residual < gr.tolerance
    return gr


ALL_CASES: list[GoldenCase] = [
    # Populated by _register_...() calls:
    # integrating_cavity_case,
    # lambertian_cosine_case,
    # fresnel_glass_case,        (parametrized over 5 angles → 5 entries)
    # specular_reflection_case,  (2 sub-cases: python_farfield, cpp_planar)
    # prism_dispersion_case,     (3 wavelengths → 3 entries)
]
```

**Invariants:**
- `build_project` must be pure (no module-level mutation); returns a fresh `Project` each call — mirrors `preset_simple_box` contract
- `default_rays` and `expected_runtime_s` are set per RESEARCH.md § Budget table — planner can tune
- SAME builder functions should be called from `conftest.py` fixtures (single source of truth)
- NO PySide6, NO pyqtgraph imports

**Verify:** `python -c "from backlight_sim.golden.cases import ALL_CASES; print(len(ALL_CASES))"`

---

### `backlight_sim/golden/report.py` (HTML + markdown renderer)

**Analog:** `backlight_sim/io/report.py::_grid_to_png_base64` (lines 15-35) + `generate_html_report` (lines 38-215) — the repo's HTML+embedded-PNG convention.

**Core pattern to mirror** (matplotlib Agg → BytesIO → base64 → HTML embed):
```python
# Source: backlight_sim/io/report.py:15-35 — EXACTLY this shape
def _grid_to_png_base64(grid: np.ndarray) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return ""                            # graceful degradation

    fig, ax = plt.subplots(figsize=(6, 4))
    im = ax.imshow(grid, origin="lower", cmap="inferno", aspect="auto")
    fig.colorbar(im, ax=ax, label="Flux")
    # ...
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")
```

**HTML structure to mirror** (io/report.py:181-213):
```python
# Source: backlight_sim/io/report.py:181-213
html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Simulation Report — {project.name}</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           max-width: 900px; margin: 2em auto; padding: 0 1em; color: #222; }}
    h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.3em; }}
    h2 {{ color: #1a5276; margin-top: 2em; }}
    table {{ border-collapse: collapse; margin: 0.5em 0 1em; }}
    td, th {{ padding: 4px 12px; border: 1px solid #ccc; text-align: left; }}
    th {{ background: #f0f0f0; }}
    .meta {{ color: #666; font-size: 0.9em; }}
</style>
</head>
<body>
<h1>Simulation Report: {project.name}</h1>
...
</body>
</html>"""
Path(path).write_text(html, encoding="utf-8")
```

**Adapted pattern for `backlight_sim/golden/report.py`:**
```python
"""Golden-suite HTML + markdown report renderer.

Mirrors backlight_sim/io/report.py matplotlib Agg + base64 PNG convention.
Degrades to text-only when matplotlib is absent (same pattern as io/report.py:22).
"""
from __future__ import annotations
import base64
import io
from pathlib import Path
from typing import Iterable
import numpy as np

from backlight_sim.golden.cases import GoldenResult


def _fresnel_plot_base64(results: list[GoldenResult]) -> str:
    """Scatter T_measured vs T_analytical across 5 angles; returns base64 PNG or ''."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return ""
    # ...plot setup...
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def write_html_report(results: Iterable[GoldenResult], path: Path) -> None:
    # Per-case table + embedded Fresnel + prism plots
    # Overall verdict banner (green/red)
    # Reproducibility footer: timestamp, python version, blu_tracer module origin
    import importlib.util, platform, sys
    spec = importlib.util.find_spec("backlight_sim.sim.blu_tracer")
    pyd_origin = spec.origin if spec else "(not found)"
    html = f"""<!DOCTYPE html>..."""  # mirror io/report.py:181-213
    Path(path).write_text(html, encoding="utf-8")


def write_markdown_report(results: Iterable[GoldenResult], path: Path) -> None:
    """Text-only markdown; works without matplotlib."""
    lines: list[str] = ["# Golden-Reference Validation Report", ""]
    lines.append("| Case | Expected | Measured | Residual | Tolerance | Rays | PASS |")
    lines.append("|------|----------|----------|----------|-----------|------|------|")
    for r in results:
        status = "[PASS]" if r.passed else "[FAIL]"
        lines.append(f"| {r.name} | {r.expected:.4g} | {r.measured:.4g} | "
                     f"{r.residual:.4g} | {r.tolerance:.4g} | {r.rays} | {status} |")
    path.write_text("\n".join(lines), encoding="utf-8")
```

**Invariants:**
- `matplotlib.use("Agg")` BEFORE importing `pyplot` (io/report.py:19 — headless-safe; must not require a display)
- Graceful fallback when matplotlib is missing — return `""` from base64 helpers; HTML shows `<em>(matplotlib not available)</em>` placeholder (mirror io/report.py:72)
- Markdown report renders without matplotlib (text tables only)
- `write_html_report` and `write_markdown_report` are side-effect-only (write file; no return value — mirrors `generate_html_report` signature at io/report.py:38)
- Use `Path(...).write_text(..., encoding="utf-8")` (io/report.py:215 convention)
- NO PySide6 imports

**Verify:** `python -c "from backlight_sim.golden.report import write_markdown_report; from backlight_sim.golden.cases import GoldenResult; write_markdown_report([GoldenResult('x',1,1,0,1,100,True)], __import__('pathlib').Path('/tmp/r.md'))"`

---

## Shared Patterns

### Pattern A — Minimal Project construction (all 5 case builders)

**Source:** `backlight_sim/tests/test_tracer.py::_make_box_scene` (lines 15-39) + `backlight_sim/io/presets.py::preset_simple_box` (lines 15-42).

**Apply to:** All 5 scene-builder fixtures in `conftest.py` and all 5 `build_project` callables in `cases.py`.

```python
# Canonical scene-builder skeleton — mirror in every golden case
def make_X_scene(rays, ...) -> Project:
    project = Project(name="...")
    project.settings = SimulationSettings(
        rays_per_source=rays,
        max_bounces=...,
        random_seed=GOLDEN_SEED,    # MANDATORY — no random seed variation
        distance_unit="mm",
    )
    project.materials[...] = Material(...)
    # Geometry: Rectangle.axis_aligned / SolidBox / SolidPrism
    # Detectors: DetectorSurface.axis_aligned / SphereDetector(mode=...)
    # Sources: PointSource(... , spd="mono_XXX" for spectral cases)
    return project
```

---

### Pattern B — Matplotlib Agg + graceful fallback

**Source:** `backlight_sim/io/report.py` lines 15-35 (`_grid_to_png_base64`).

**Apply to:** All plot helpers in `backlight_sim/golden/report.py`.

```python
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    return ""     # or handle skip-plots flag
# ...
buf = io.BytesIO()
fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
plt.close(fig)
buf.seek(0)
return base64.b64encode(buf.read()).decode("ascii")
```

---

### Pattern C — Dispatch-predicate awareness (choose the path deliberately)

**Source:** `backlight_sim/sim/tracer.py::_project_uses_cpp_unsupported_features` (lines 251-287).

**Apply to:** Every scene builder must know whether its project routes to C++ or Python:

| Feature in scene | Forces Python? |
|------------------|:--------------:|
| `SolidBox` / `SolidCylinder` / `SolidPrism` in `project.solid_*` lists | YES |
| `SphereDetector(mode="far_field")` | YES |
| Any source with `spd != "white"` (incl. `mono_*`) | YES |
| Any source with `color_rgb != (1,1,1)` | YES |
| `project.spectral_material_data` populated | YES |
| `project.bsdf_profiles` populated | YES |

**Test authors' contract:** If you want C++ coverage, build a scene that uses NONE of the above. If you want Python coverage, include AT LEAST ONE.

---

### Pattern D — Seed determinism

**Source:** `test_tracer.py::test_deterministic_with_same_seed` (lines 65-68).

**Apply to:** Every golden test MUST reuse `GOLDEN_SEED = 42` (constant in `conftest.py`); any per-case seed variation is opt-in via an env var read in conftest (e.g. `os.environ.get("GOLDEN_SEED")` for seed-stability manual runs per VALIDATION.md § Manual-Only).

---

### Pattern E — Dataclass + factory registry

**Source:** `backlight_sim/io/presets.py::PRESETS` dict + factory functions (lines 15-100).

**Apply to:** `backlight_sim/golden/cases.py::ALL_CASES` list.

```python
# io/presets.py:96-100 — registry shape
PRESETS: dict[str, callable] = {
    "Simple Box (50×50×20 mm)": preset_simple_box,
    ...
}
# Adapt for golden:
ALL_CASES: list[GoldenCase] = [integrating_cavity_case, lambertian_cosine_case, ...]
```

---

## No Analog Found

| File | Reason |
|------|--------|
| *(none)* | All 13 files have direct analogs in the existing codebase. |

The closest stretch is the `SphereDetector(mode="far_field")` post-processing via `compute_farfield_candela` (tracer.py:2934) — the repo has not yet exercised a test against the `candela_grid` output, but the function itself is implemented and callable, so tests can read `result.sphere_detectors[name].candela_grid` directly.

---

## Cross-Cutting Invariants (apply to ALL new files)

1. **No PySide6 imports** under `backlight_sim/tests/golden/` OR `backlight_sim/golden/` — CLAUDE.md rule extends to these new modules (the `golden/` package is part of the shipped wheel; `tests/golden/` runs headless).
2. **No `print()` in library code** (use module-level logging if needed) — only the CLI `__main__.py` and the report renderers emit user-visible output.
3. **Type annotations on all public function signatures** (Python style rule).
4. **`from __future__ import annotations`** at the top of each `.py` file — matches `io/report.py:3`, `core/project_model.py:1`, `io/presets.py:3` convention.
5. **Seeded RNG** — every Project passed to `RayTracer` sets `settings.random_seed = GOLDEN_SEED` (constant 42 from conftest.py).
6. **`flux_tolerance = 0.0`** on every source (pitfall 6; jitter breaks seed stability).
7. **`Path(...).write_text(..., encoding="utf-8")`** for all file writes (io/report.py:215 convention).
8. **Absolute imports** (`from backlight_sim.core.project_model import Project`) — matches `tests/test_tracer.py:6-11`.

---

## Metadata

- **Analog search scope:** `backlight_sim/{core,sim,io,tests}/`, `build_exe.py`
- **Files scanned:** 10 (tests/test_tracer.py, io/report.py, io/presets.py, sim/tracer.py [targeted sections only], core/{detectors,sources,materials,project_model,solid_body}.py, build_exe.py)
- **Pattern extraction date:** 2026-04-18
- **Phase:** 03 — golden-reference-validation-suite

---

## PATTERN MAPPING COMPLETE

All 13 new files mapped to concrete analogs — pytest style from `test_tracer.py`, matplotlib+base64 HTML from `io/report.py`, Project factory from `io/presets.py`, argparse CLI from `build_exe.py`; planner can lift line-ranged excerpts directly into each task.
