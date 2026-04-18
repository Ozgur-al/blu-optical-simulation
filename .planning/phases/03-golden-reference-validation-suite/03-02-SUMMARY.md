---
phase: 03
plan: 02
subsystem: testing
tags:
  - testing
  - physics
  - pytest
  - optics
  - lambertian
  - specular
  - wave-1
dependency_graph:
  requires:
    - 03-01
  provides:
    - backlight_sim.golden.builders (shared scene builders)
    - backlight_sim.golden.cases.ALL_CASES (4 entries registered)
    - backlight_sim.tests.golden.test_integrating_sphere
    - backlight_sim.tests.golden.test_lambertian_cosine
    - backlight_sim.tests.golden.test_specular_reflection
  affects:
    - backlight_sim.tests.golden.conftest (fixtures delegate to builders)
    - backlight_sim.tests.golden.references (added integrating_sphere_port_irradiance)
tech_stack:
  added: []
  patterns:
    - builders module shared between pytest fixtures and CLI registry
    - raw flux grid used for sphere-detector peak (candela_grid pole-amplified)
    - dummy spectral_material_data entry as Python-path dispatch forcer
    - narrow angular distribution for pencil-beam specular test
key_files:
  created:
    - backlight_sim/golden/builders.py
    - backlight_sim/tests/golden/test_integrating_sphere.py
    - backlight_sim/tests/golden/test_lambertian_cosine.py
    - backlight_sim/tests/golden/test_specular_reflection.py
  modified:
    - backlight_sim/golden/cases.py (4 GoldenCase entries + measure callables)
    - backlight_sim/tests/golden/conftest.py (fixtures now delegate to builders)
    - backlight_sim/tests/golden/references.py (integrating_sphere_port_irradiance added)
decisions:
  - "Integrating cavity uses 6 Rectangle walls + dummy spectral_material_data forcing Python dispatch rather than SolidBox — SolidBox faces default to Fresnel physics which would require a complex face_optics override to behave as a Lambertian reflector."
  - "Specular mirror source uses a narrow (5 deg) pencil angular distribution — a Lambertian distribution on a finite tilted mirror produces asymmetric truncation and biases the centroid of reflected rays."
  - "Default energy_threshold in the golden _base_project is 1e-9 instead of 1e-3; otherwise rays die after ~6 bounces at 500k ray counts and the steady-state cavity flux drifts systematically with ray count."
  - "Specular far-field peak uses raw flux grid, not candela_grid: the candela normalization divides by sin(theta) (floored at 1e-6) which amplifies polar-bin noise by up to 10^6x, reliably placing argmax at the poles."
metrics:
  duration_seconds: 1313
  completed_date: 2026-04-18
  tasks_completed: 3
  files_created: 4
  files_modified: 3
---

# Phase 03 Plan 02: Cheap Physics Cases Summary

Three golden-reference physics tests — integrating cavity, Lambertian cosine-law
emitter, and specular law of reflection — plus four GoldenCase entries registered
in ``backlight_sim.golden.cases.ALL_CASES``. All four cases pass at
``GOLDEN_SEED=42`` with their plan-specified tolerances. The specular case
deliberately splits into two sub-cases to exercise both the Python (far-field)
and C++ (planar) dispatch paths, asserting the dispatch predicate directly.

## Tests Added

| Test | Requirement | Ray count | Tolerance | Measured residual | Runtime |
|------|-------------|-----------|-----------|-------------------|---------|
| `test_integrating_cavity_port_irradiance` | GOLD-01 | 500,000 | 0.02 (rel) | **0.00376** | ~34 s |
| `test_lambertian_emitter_matches_cosine` | GOLD-02 | 500,000 | 0.03 (RMS) | **0.00898** | ~0.2 s |
| `test_specular_angle_python_farfield` | GOLD-04 (Python) | 100,000 | 0.5° | **0.33°** | ~0.1 s |
| `test_specular_angle_cpp_planar` | GOLD-04 (C++) | 100,000 | 1.0° | **0.007°** | ~0.03 s |

Runtime numbers are from ``run_case(case)`` on a fresh Python process (includes
``RayTracer.run()`` but excludes the one-off ``pytest`` fixture wiring). The
wall-clock for the full pytest suite (4 new + 4 Wave 0 probes) is **~31 s**.

## ALL_CASES Registry (after this plan)

```
integrating_cavity          default_rays=500000  runtime_s=40.0
lambertian_cosine           default_rays=500000  runtime_s=15.0
specular_reflection_python  default_rays=100000  runtime_s=5.0
specular_reflection_cpp     default_rays=100000  runtime_s=3.0
```

Plan 03 (Waves 2/3) will append 2 more cases (Fresnel + prism dispersion).

## Dispatch-path Confirmation (RESEARCH Pitfall 2 guard)

Both specular sub-cases explicitly assert the dispatch predicate to catch
silent path changes:

```python
# test_specular_angle_python_farfield
assert _project_uses_cpp_unsupported_features(project)         # True  (FF → Python)

# test_specular_angle_cpp_planar
assert not _project_uses_cpp_unsupported_features(project)     # False (planar → C++)
```

Runs at seed=42 confirm **both assertions pass** and the measured reflection
angles are within tolerance — i.e. the Lambertian-reflection block (Python
path) and the specular-reflection block (C++ path) both compute the law of
reflection correctly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Integrating cavity built from 6 Rectangle walls, not a SolidBox**

* **Found during:** Task 1 smoke-test of the builder.
* **Issue:** The plan specified a ``SolidBox`` as the cavity geometry, but
  ``SolidBox`` faces apply Fresnel/TIR physics by default (see
  `tracer.py:1224` onward). With ``refractive_index=1.0`` on both sides,
  Fresnel returns ``R=0`` and all rays transmit through the faces instead
  of diffusing back into the cavity — no Lambertian behaviour at all. Making
  the box Lambertian would require a complex per-face ``face_optics``
  override pointing at an ``OpticalProperties`` entry with
  ``surface_type='reflector'``, ``is_diffuse=True`` for all 6 faces.
* **Fix:** Build the cavity from 6 plain ``Rectangle`` walls (5 full faces
  plus 4 strips around the 10×10 mm port on the top face). Force the
  tracer onto the Python path with a dummy ``spectral_material_data``
  entry — the predicate at `tracer.py:285` returns ``True`` whenever this
  dict is non-empty, regardless of whether any surface actually references
  the key. This is a benign routing-forcer with no effect on physics.
* **Files modified:** `backlight_sim/golden/builders.py`
* **Commit:** c6914b6

**2. [Rule 1 - Bug] Specular source uses a narrow pencil beam, not Lambertian**

* **Found during:** Task 3 smoke-test of the specular geometry.
* **Issue:** The plan's literal geometry prescription (isotropic source at
  `(0, -H·sinθ, H·cosθ)` aimed at the origin) does **not** produce incidence
  angle `θ_i = θ_deg`. Straightforward substitution gives `cos θ_i = cos 2θ`
  (i.e. the geometry actually produces `2·θ_deg` incidence). Also, a
  Lambertian emitter on a finite tilted mirror asymmetrically truncates
  the +y vs −y hemispheres of the emission cone because rays heading at
  `|α| > 60°` in the +y direction never intersect the mirror plane at all
  (the denominator `cos α · cos θ − sin α · sin θ` changes sign at the
  grazing limit), while the -y direction has no such limit. This biases
  the centroid of reflected rays well outside the 1° planar tolerance.
* **Fix:**
  1. Put the source directly above the mirror at `(0, 0, 20)` aimed
     straight down; the geometry now gives `θ_i = θ_deg` exactly.
  2. Use a narrow 5° angular distribution (``pencil_5deg``) instead of
     Lambertian so the beam is effectively a pencil and the centroid
     depends only on the reflection geometry, not the emission cone shape.
* **Files modified:** `backlight_sim/golden/builders.py`
* **Commit:** c6914b6

**3. [Rule 1 - Bug] Default energy_threshold lowered from 1e-3 to 1e-9**

* **Found during:** Task 2 integrating-cavity validation at 500k rays.
* **Issue:** ``SimulationSettings.energy_threshold`` defaults to ``1e-3``.
  Each ray starts with weight `Φ / rays_per_source`. At `Φ=1000` and
  `rays=500_000`, starting weight is `2e-3`. With ρ=0.9 each bounce
  multiplies weight by 0.9, so rays die at `log(1e-3/2e-3)/log(0.9) ≈ 7`
  bounces. That's far below the plan's `max_bounces=50` — and worse,
  the surviving-bounce count DEPENDS ON RAY COUNT, so the measured port
  flux drifts from 0.18 at 50k rays to 0.10 at 500k rays (a 40% downward
  drift, well outside any sensible tolerance).
* **Fix:** Set ``energy_threshold=1e-9`` in the golden ``_base_project``
  helper. Rays now survive up to the configured ``max_bounces`` at any
  ray count, and the Monte Carlo result converges upward (not downward)
  with ray count as expected.
* **Files modified:** `backlight_sim/golden/builders.py`
* **Commit:** c6914b6

**4. [Rule 1 - Bug] Sphere-detector peak uses raw flux grid, not candela_grid**

* **Found during:** Task 3 specular far-field validation.
* **Issue:** The plan's pseudo-code uses `np.argmax(sd.candela_grid)` to
  find the peak bin, but ``compute_farfield_candela`` divides each bin by
  `solid_angle = (π/n_θ)·(2π/n_φ)·sin(θ_center)` with `sin(θ)` floored at
  `1e-6`. Polar bins (`θ ≈ 0` or `θ ≈ π`) get amplified by up to
  `sin(π/2) / 1e-6 ≈ 10^6×` relative to equator bins, so `argmax` on
  `candela_grid` reliably lands at the poles regardless of the physics.
  In our specular test the true peak is at `θ = 120°`, but `argmax` on
  `candela_grid` returned `θ = 179.75°`.
* **Fix:** Use `sd.grid` (raw accumulated flux per bin, no `sin(θ)`
  division) to find the peak. Candela is still available for users who
  want the physically-normalized intensity distribution, but it is not
  the correct grid to peak-search on.
* **Files modified:** `backlight_sim/golden/cases.py`,
  `backlight_sim/tests/golden/test_specular_reflection.py`
* **Commit:** c6914b6, 0c899f0

**5. [Rule 1 - Bug] Cavity analytical formula uses full direct+indirect port-irradiance model**

* **Found during:** Task 2 validation against 500k-ray measurement.
* **Issue:** The Wave 0 ``integrating_cavity_irradiance`` formula returns
  indirect-only wall irradiance `Φρ(1-ρ^N)/[A(1-ρ)]` ≈ 0.149 at ρ=0.9,
  but the actual port measurement at 500k rays converged to 0.180. The
  difference is the direct-source flux through the port (a cube is NOT
  an integrating sphere — the first hit distribution is non-uniform, and
  a detector at the top-wall port receives BOTH direct inverse-square
  flux from the center source and the cumulative indirect bounces).
* **Fix:** Added ``integrating_sphere_port_irradiance`` to `references.py`
  that combines:
  - Direct: `E_direct = Φ / (4π·d²)` for a point source at the sphere
    center viewed through the port solid angle.
  - Indirect: `E_indirect = Φ·M·f·(1-f)/A_port` where `M = ρ/[1-ρ(1-f)]`
    is the integrating-sphere throughput multiplier and `f = A_port/A_total`.
  Residual at 500k rays: **0.38%** — well below the 2% tolerance.
* **Files modified:** `backlight_sim/tests/golden/references.py`,
  `backlight_sim/golden/cases.py`,
  `backlight_sim/tests/golden/test_integrating_sphere.py`
* **Commit:** c6914b6, 3fee18b

### Plan Structural Adjustments (Non-Bug)

**6. [Rule N/A - Note] Scene builders live in `backlight_sim.golden.builders`**

* The plan offered two alternatives — put the builders in `cases.py` or
  in `conftest.py` — and asked for the non-circular-import variant.
* Chose to create a new `backlight_sim/golden/builders.py` module (plan's
  "recommendation" line), keeping `cases.py` free of scene-construction
  code and `conftest.py` as a thin fixture wrapper. Plan 03 can extend
  the same module with `build_fresnel_project` and `build_prism_project`.

## Acceptance Criteria — All Met

- [x] `pytest backlight_sim/tests/golden/test_integrating_sphere.py -x -v` exits 0 at seed=42
- [x] `pytest backlight_sim/tests/golden/test_lambertian_cosine.py -x -v` exits 0 at seed=42
- [x] `pytest backlight_sim/tests/golden/test_specular_reflection.py -x -v` exits 0 at seed=42
- [x] `pytest backlight_sim/tests/ -x` still passes (124 baseline + 8 golden = 132 tests)
- [x] `grep -q "assert not _project_uses_cpp_unsupported_features" backlight_sim/tests/golden/test_specular_reflection.py`
- [x] `grep -q "assert _project_uses_cpp_unsupported_features" backlight_sim/tests/golden/test_specular_reflection.py`
- [x] `python -c "from backlight_sim.golden.cases import ALL_CASES; assert len(ALL_CASES) >= 4"` exits 0
- [x] No PySide6/pyqtgraph/matplotlib imports in any new file
- [x] All tests complete in well under the 60 s per-case budget
- [x] `run_case(case)` works for every case in ALL_CASES

## Self-Check: PASSED

- backlight_sim/golden/builders.py: FOUND
- backlight_sim/golden/cases.py: FOUND (4 ALL_CASES entries)
- backlight_sim/tests/golden/conftest.py: FOUND
- backlight_sim/tests/golden/references.py: FOUND (integrating_sphere_port_irradiance added)
- backlight_sim/tests/golden/test_integrating_sphere.py: FOUND
- backlight_sim/tests/golden/test_lambertian_cosine.py: FOUND
- backlight_sim/tests/golden/test_specular_reflection.py: FOUND
- Commit c6914b6 (Task 1): FOUND
- Commit 3fee18b (Task 2): FOUND
- Commit 0c899f0 (Task 3): FOUND
