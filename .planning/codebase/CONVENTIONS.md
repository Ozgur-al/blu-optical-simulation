# Coding Conventions

**Analysis Date:** 2026-03-14

## Naming Patterns

**Files:**
- snake_case: `project_io.py`, `geometry_builder.py`, `properties_panel.py`
- Prefixed with module intent: GUI files in `gui/`, core models in `core/`, I/O in `io/`, simulation in `sim/`
- Test files: `test_tracer.py` with `test_` prefix for all test functions

**Functions:**
- snake_case throughout: `sample_isotropic()`, `build_cavity()`, `_intersect_rays_plane()`
- Private/internal functions prefixed with single underscore: `_make_box_scene()`, `_build_basis()`, `_rotation_matrix_xyz()`
- Properties use `@property` decorator: `.normal`, `.effective_flux`, `.dominant_normal_axis`

**Variables:**
- snake_case: `rays_per_source`, `wall_reflectance`, `total_flux`, `rng`
- NumPy arrays: descriptive names `u_axis`, `v_axis`, `normal`, `grid`, `directions`
- Loop variables: single letters acceptable for short loops (`x`, `y`, `z`, `r`, `n`)
- Constants: UPPER_CASE with underscore: `_EPSILON = 1e-6`, `N_SPECTRAL_BINS`

**Types:**
- Classes: PascalCase: `Rectangle`, `Material`, `PointSource`, `RayTracer`, `DetectorSurface`, `MainWindow`
- Type hints: modern Python 3.10+ style with `|` for unions: `Callable[[float], None] | None`, `dict[str, Material]`
- Dataclasses heavily used for core models: `@dataclass` decorator on all core/* classes

## Code Style

**Formatting:**
- No explicit linting/formatting tool configured (no `.eslintrc`, `.prettierrc`, `pyproject.toml`)
- Observed style: consistent spacing, 4-space indentation
- Module docstrings: triple-quoted at top with brief description: `"""Monte Carlo ray tracing engine — general plane intersection."""`

**Linting:**
- No configured linter found
- Style enforced by convention and code review

## Import Organization

**Order:**
1. `from __future__ import annotations` (at top of every module)
2. Standard library: `import json`, `from pathlib import Path`, `import multiprocessing`
3. Third-party: `import numpy as np`, `from PySide6.QtWidgets import ...`
4. Local imports: `from backlight_sim.core.geometry import Rectangle`

**Path Aliases:**
- No aliases configured; always use relative imports from project root: `from backlight_sim.core.geometry import Rectangle`
- GUI modules never import PySide6 in `core/`, `sim/`, or `io/` (architectural constraint)

## Error Handling

**Patterns:**
- Explicit error handling in I/O and parsing: `try/except ValueError` for IES file parsing (`backlight_sim/io/ies_parser.py:31`, `:40`)
- GUI layer catches broad exceptions: `except Exception as exc:` in file open/save (`backlight_sim/gui/main_window.py:281`, `:293`)
- Angular distribution parsing raises `ValueError` with descriptive message: `raise ValueError("Need at least two valid rows.")` (`backlight_sim/gui/angular_distribution_panel.py:194`)
- Fallback behavior on parse error: invalid profiles fall back to lambertian distribution (`backlight_sim/sim/sampling.py:63`, `:75`)
- No custom exception classes defined; standard Python exceptions used

## Logging

**Framework:** None (no logging module usage detected)

**Patterns:**
- No structured logging in place
- Errors presented to user via GUI dialogs in main_window.py
- Progress communicated via callback: `progress_callback=lambda p: calls.append(p)` pattern used for long-running operations (`backlight_sim/tests/test_tracer.py:73`)

## Comments

**When to Comment:**
- Explain "why" not "what"; code should be self-documenting
- Comment non-obvious math: docstrings for sampling functions explain mathematical approach (`backlight_sim/sim/sampling.py:9-12`)
- Comment section breaks with `# -------` lines to group related functions (`backlight_sim/io/project_io.py:17`, `:29`, `:141`)
- Comment legacy behavior or compatibility notes: `"For backward compatibility, Material retains all the old surface_type fields."` (`backlight_sim/core/materials.py:45-47`)

**JSDoc/TSDoc:**
- Python docstrings (not JSDoc): triple-quoted `"""docstring"""` format
- Function docstrings explain inputs, outputs, and behavior:
  ```python
  def sample_lambertian(n: int, normal: np.ndarray, rng: np.random.Generator) -> np.ndarray:
      """Sample n cosine-weighted directions in the hemisphere around normal.

      Uses Malley's method: sample uniform disk, project to hemisphere.
      Returns (n, 3) array of unit vectors.
      """
  ```
- Dataclass docstrings explain the purpose and key fields
- No separate param/return documentation; integrated into body

## Function Design

**Size:** Functions typically 5–50 lines; longer functions in tracer.py handle complex ray-plane intersection

**Parameters:**
- Few parameters per function (≤5); use dataclass objects for related parameters: `Project`, `SimulationSettings` passed as containers
- Type hints required for all public functions: `def run(self, progress_callback: Callable[[float], None] | None = None) -> SimulationResult:`
- Default values common for optional parameters

**Return Values:**
- Single return: `Rectangle`, `SimulationResult`, `Project`
- No implicit `None` returns; functions with side effects return nothing
- Tuple unpacking common: `u, v = _map[(int(normal_axis), float(normal_sign))]` (`backlight_sim/core/geometry.py:64`)

## Module Design

**Exports:**
- Explicit classes and functions exported; module organization reflects API
- `core/` modules export dataclasses: `Rectangle`, `PointSource`, `Material`, `DetectorSurface`, `Project`
- `sim/` modules export functions and the `RayTracer` class
- `io/` modules export builder functions (`build_cavity`, `build_led_grid`) and I/O functions (`save_project`, `load_project`)
- `gui/` modules export QWidget subclasses: `MainWindow`, `PropertiesPanel`, `ViewportWidget`

**Barrel Files:**
- `__init__.py` files exist but minimal: typically empty or with module imports
- Encourage importing from submodules directly: `from backlight_sim.core.geometry import Rectangle`

## Dataclass Usage

**Pattern:**
- Core models use `@dataclass` with field defaults and `__post_init__` for validation
- Example: `Rectangle.__post_init__()` normalizes u_axis/v_axis vectors, `PointSource.__post_init__()` converts position to float array
- Mutable defaults: use `field(default_factory=...)` for lists/dicts: `sources: list[PointSource] = field(default_factory=list)`
- No validators used; __post_init__ ensures arrays are correct dtype and normalized

## Geometry/Math Conventions

**Coordinate System:**
- Z-up convention: `normal: np.ndarray` from cross product `np.cross(u_axis, v_axis)`
- Rectangular geometry uses u_axis/v_axis pair for arbitrary 3D orientation: `backlight_sim/core/geometry.py:17-20`
- World coordinates always in float: `np.asarray(..., dtype=float)`

**Math Operations:**
- NumPy vectorized: ray tracing done with (n, 3) arrays for all rays in one bounce
- Vectorized reflection: `reflect_specular(directions, normal)` operates on (n, 3) arrays (`backlight_sim/sim/sampling.py`)
- CDF inversion for sampling: 2048-point interpolation grid for angular distributions (`backlight_sim/sim/sampling.py:70`)

---

*Convention analysis: 2026-03-14*
