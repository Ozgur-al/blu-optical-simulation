---
phase: 03
plan: 01
subsystem: testing
tags:
  - testing
  - scaffolding
  - pytest
  - optics
  - wave-0
dependency_graph:
  requires: []
  provides:
    - backlight_sim.golden (package)
    - backlight_sim.golden.cases (GoldenResult, GoldenCase, run_case, ALL_CASES)
    - backlight_sim.tests.golden (test package)
    - backlight_sim.tests.golden.references (analytical formulas)
    - backlight_sim.tests.golden.conftest (GOLDEN_SEED, fixtures)
  affects:
    - pytest discovery (new test directory)
tech_stack:
  added: []
  patterns:
    - pytest fixtures (assert_within_tolerance + 5 scene-builder stubs)
    - lazy tracer import inside run_case() to keep CLI import cheap
    - absolute imports only
key_files:
  created:
    - backlight_sim/golden/__init__.py
    - backlight_sim/golden/cases.py
    - backlight_sim/tests/golden/__init__.py
    - backlight_sim/tests/golden/references.py
    - backlight_sim/tests/golden/conftest.py
    - backlight_sim/tests/golden/test_budget_probe.py
  modified: []
decisions:
  - Used `reflectance`/`transmittance` keys in spectral_material_data for Rectangle
    surfaces in the budget probe (per project_model.py:46); SolidBox/Cylinder/Prism
    paths use `refractive_index` — documented for Plans 02/03.
  - Budget probe throughput numbers captured with 100k/50k ray probes — include
    one-shot overhead; Plans 02/03 should amortize over larger scenes.
metrics:
  duration_seconds: 281
  completed_date: 2026-04-18
  tasks_completed: 3
  files_created: 6
---

# Phase 03 Plan 01: Golden-Reference Validation Suite Scaffolding Summary

Created the headless scaffolding for the golden-reference validation suite: a
shipped `backlight_sim/golden/` package with a case registry and a
`backlight_sim/tests/golden/` pytest package with analytical reference formulas,
shared fixtures, and a Wave 0 budget probe that measures C++ vs Python-spectral
throughput so Waves 1-3 can size ray counts with empirical numbers.

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `backlight_sim/golden/__init__.py` | 5 | CLI package marker (shipped in wheel) |
| `backlight_sim/golden/cases.py` | 61 | `GoldenResult`, `GoldenCase`, `run_case()`, `ALL_CASES` registry |
| `backlight_sim/tests/golden/__init__.py` | 1 | pytest package marker |
| `backlight_sim/tests/golden/references.py` | 50 | Analytical formulas (Fresnel, Snell, Lambert, cavity) — no tracer imports |
| `backlight_sim/tests/golden/conftest.py` | 129 | `GOLDEN_SEED = 42`, `assert_within_tolerance`, 5 scene-builder fixture stubs |
| `backlight_sim/tests/golden/test_budget_probe.py` | 113 | Throughput probe + SPD convention smoke tests (4 tests) |

## Budget Probe Measurements (Wave 0 empirical numbers)

Measured on dev laptop (Windows 11, Python 3.12.10, C++ extension as .pyd in site-packages):

| Path | Throughput | Probe size | Actual elapsed |
|------|-----------|-----------|----------------|
| C++ path (spd='white', plain Rectangles) | **~14921 ms / 1M rays** | 100k rays | 1492.1 ms |
| Python path (spd='mono_550', spectral_material_data) | **~17459 ms / 1M rays** | 50k rays | 872.9 ms |

**Important caveat:** These numbers include one-shot overhead (RayTracer init,
ray-path buffer allocation, detector grid initialization). For the larger ray
counts Waves 1-3 will use (200k–500k), throughput will be noticeably better;
use these as an **upper bound** for budget planning, not a typical value.

### Downstream ray-count sizing (per plan contract)

- C++ path budget is ~15 s/1M rays at this probe scale. Plan 02 Specular case at
  100k rays should finish in ~1.5 s per sub-case — well inside the 5-min budget.
- Python spectral path is ~17 s/1M rays. Plan 03 Fresnel (5 × 200k = 1M rays)
  ≈ ~17 s; Prism (3 × 500k = 1.5M rays) ≈ ~26 s. Combined Plans 02+03 well
  under the 300 s phase gate.

## SPD Convention Verification

Confirmed at `backlight_sim/sim/tracer.py:631`
(`has_spectral = any(s.spd != "white" for s in sources)`):

- `spd="mono_450"` → `_project_uses_cpp_unsupported_features` returns **True** →
  routes to Python spectral path. Run completes without AttributeError/KeyError
  when `project.spectral_material_data["<optics_name>"]` is populated with
  `reflectance`/`transmittance` keys.
- `spd="white"` → predicate returns **False** → routes to C++ path (baseline).

**Risk closure:** assumption A3 from 03-RESEARCH.md (`spd="mono_<nm>"` triggers
spectral sampling) is now **verified**, not assumed. Plans 02/03 can rely on
`spd=f"mono_{wavelength_nm}"` as the canonical way to emit monochromatic rays
from a PointSource.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Spectral material data key convention for Rectangle surfaces**

- **Found during:** Task 3 (first run of `test_python_path_throughput`)
- **Issue:** The plan's pseudo-code put `"refractive_index"` inside
  `project.spectral_material_data["wall"]`, but the tracer's plain-Rectangle
  spectral dispatch at tracer.py:1688-1695 expects `"reflectance"` and
  `"transmittance"` keys. Initial run crashed with `KeyError: 'reflectance'`.
- **Fix:** Rewrote the spectral dict in the budget probe to use
  `{"wavelength_nm", "reflectance", "transmittance"}` — the correct key set
  for Rectangle surfaces per `project_model.py:46` comment. SolidBox/Cylinder/
  Prism use a different key set (`"refractive_index"`) — documented inline so
  Plans 02/03 use the right schema per geometry type.
- **Files modified:** `backlight_sim/tests/golden/test_budget_probe.py`
- **Commit:** 95824df

### Plan Interface Discrepancy (documented, non-blocking)

**2. [Rule N/A - Note] Project field name: `solid_bodies` not `solid_boxes`**

- **Found during:** Task 1 read-first review
- **Issue:** 03-01-PLAN.md `<interfaces>` section listed
  `solid_boxes: list[SolidBox]` but the actual Project dataclass uses
  `solid_bodies: list[SolidBox]`. The dispatch predicate
  `_project_uses_cpp_unsupported_features` also references `solid_bodies`.
- **Action:** No code change required — this plan's scene builders do not yet
  touch solid bodies (Plans 02/03 will). Documented so downstream plans use
  the correct field name.

### Research Note

**3. [Rule N/A - Note] RESEARCH.md Fresnel T(60°) table value**

- **Issue:** 03-RESEARCH.md Case 3 table lists T(60°, air→glass n=1.5) ≈ 0.9069,
  but the analytically-correct value is **T ≈ 0.9108** (verified by hand:
  rs² = 0.1766, rp² = 0.0018, R = 0.0892, T = 0.9108).
- **Action:** Our `fresnel_transmittance_unpolarized` implementation returns
  the mathematically correct value. Plans 02/03 should derive expected values
  by calling the reference function, not copying from the RESEARCH table.
- **Confirmed** by comparing to the tracer's own `_fresnel_unpolarized` at
  tracer.py:150 — same formula, same result.

## Acceptance Criteria — All Met

- [x] `python -c "import backlight_sim.golden; import backlight_sim.golden.cases; import backlight_sim.tests.golden"` exits 0
- [x] `GoldenCase`, `GoldenResult`, `ALL_CASES` importable; `isinstance(ALL_CASES, list)` True
- [x] `grep -q "GOLDEN_SEED = 42" backlight_sim/tests/golden/conftest.py`
- [x] `grep -q "def assert_within_tolerance" backlight_sim/tests/golden/conftest.py`
- [x] `grep -q "def fresnel_transmittance_unpolarized" backlight_sim/tests/golden/references.py`
- [x] `grep -q "def integrating_cavity_irradiance" backlight_sim/tests/golden/references.py`
- [x] `grep -q "def snell_exit_angle" backlight_sim/tests/golden/references.py`
- [x] `grep -q "def lambert_cosine" backlight_sim/tests/golden/references.py`
- [x] `fresnel_transmittance_unpolarized(0.0, 1.0, 1.5) == 0.96` (to 4 decimals)
- [x] `pytest backlight_sim/tests/golden/ --collect-only` shows 4 tests
- [x] `pytest backlight_sim/tests/golden/test_budget_probe.py -v -s` — 4 passed; stdout contains `ms / 1M rays` for BOTH C++ and Python paths
- [x] Headlessness: neither `PySide6` nor `pyqtgraph` in `sys.modules` after importing golden packages
- [x] No regressions: `pytest backlight_sim/tests/ --ignore=backlight_sim/tests/golden` — 124 passed (baseline preserved)

## Handoff Notes for Waves 1-3

1. **Insertion point for `ALL_CASES`:** `backlight_sim/golden/cases.py:61` —
   `ALL_CASES: list[GoldenCase] = []`. Plans 02/03 can either
   `ALL_CASES.append(...)` in each case module or replace with a module-level
   list literal.

2. **Scene-builder fixtures already have the right signatures** in
   `conftest.py`. Waves 1-3 only need to replace the stub bodies with real
   geometry — DO NOT change signatures or names.

3. **SPD convention locked:** use `spd=f"mono_{wavelength_nm}"` (e.g.
   `"mono_450"`, `"mono_550"`, `"mono_650"`) to trigger the spectral path.

4. **spectral_material_data key convention (important for Plans 02/03):**
   - Rectangle surfaces: `{"wavelength_nm", "reflectance", "transmittance"}`
   - SolidBox/SolidCylinder/SolidPrism: `{"wavelength_nm", "refractive_index"}`
   - Case 5 (prism dispersion) uses the SolidPrism schema.

5. **Project field name: `solid_bodies`**, not `solid_boxes` (plan interface
   snippet had this wrong).

6. **Budget guidance:** C++ path ~15 ms/1k rays worst case, Python spectral
   ~17 ms/1k rays. A 500k-ray Python spectral case should fit in ~10 s when
   amortized over larger scenes — comfortable for the 300 s phase gate.

## Self-Check: PASSED

- backlight_sim/golden/__init__.py: FOUND
- backlight_sim/golden/cases.py: FOUND
- backlight_sim/tests/golden/__init__.py: FOUND
- backlight_sim/tests/golden/references.py: FOUND
- backlight_sim/tests/golden/conftest.py: FOUND
- backlight_sim/tests/golden/test_budget_probe.py: FOUND
- Commit 71c2b33 (Task 1): FOUND
- Commit 711f193 (Task 2): FOUND
- Commit 95824df (Task 3): FOUND
