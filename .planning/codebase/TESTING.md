# Testing Patterns

**Analysis Date:** 2026-03-14

## Test Framework

**Runner:**
- pytest 7.0+ (from `requirements.txt`)
- Config: None explicit (no `pytest.ini`, `setup.cfg`, or `pyproject.toml` found)
- Pytest uses default discovery: `test_*.py` files, `test_*()` functions

**Assertion Library:**
- pytest's built-in assertion syntax plus NumPy `np.testing`
- `assert det.total_hits > 0` for simple checks
- `np.testing.assert_array_equal()` for array comparisons
- `pytest.approx()` for floating-point comparisons: `assert src.effective_flux == pytest.approx(20.0 * 5.0 * 0.9)`

**Run Commands:**
```bash
pytest backlight_sim/tests/              # Run all tests
pytest backlight_sim/tests/test_tracer.py::test_function_name  # Run single test
pytest -v                                # Verbose output
pytest --tb=short                        # Short traceback
```

## Test File Organization

**Location:**
- Single test file: `backlight_sim/tests/test_tracer.py`
- Tests are co-located in `tests/` directory (separated from source)
- No test files in individual module directories (e.g., no `core/test_geometry.py`)

**Naming:**
- Test file: `test_tracer.py`
- Test functions: `test_basic_simulation_produces_nonzero_heatmap()`, `test_zero_flux_produces_zero_results()`
- Descriptive names stating what is tested and expected outcome

**Structure:**
```
backlight_sim/
├── tests/
│   ├── __init__.py
│   └── test_tracer.py  (23 tests as of current state)
```

## Test Structure

**Suite Organization:**
```python
def _make_box_scene(
    rays_per_source=5000,
    wall_reflectance=0.9,
    wall_type="reflector",
    source_flux=1000.0,
) -> Project:
    """Fixture factory returning a test Project with a box scene."""
    materials = {
        "wall": Material(name="wall", surface_type=wall_type, ...)
    }
    surfaces = [
        Rectangle.axis_aligned("floor", [0, 0, -5], (20, 20), 2, -1.0, "wall"),
        ...
    ]
    detectors = [
        DetectorSurface.axis_aligned("top_detector", [0, 0, 5], (20, 20), 2, 1.0, (50, 50)),
    ]
    sources = [PointSource("src1", np.array([0.0, 0.0, 0.0]), flux=source_flux)]
    settings = SimulationSettings(rays_per_source=rays_per_source, max_bounces=50, ...)
    return Project(name="test_box", sources=sources, ...)
```

**Patterns:**
- **Setup**: Helper function `_make_box_scene()` creates reusable test project with configurable parameters
- **Assertions**: Each test is a single test function with 3–8 assertions
- **Teardown**: None explicit; uses context managers for file cleanup: `tempfile.NamedTemporaryFile()` with try/finally
- **Data**: Test uses deterministic seed (`random_seed=42`) for reproducibility

## Mocking

**Framework:** None; no unittest.mock or pytest-mock used

**Patterns:**
- No mocking in current tests; simulation engine tested as-is
- Tests use real `RayTracer` with real geometry and materials
- Integration tests: `test_tracer_supports_custom_angular_distribution_name()` tests end-to-end with custom distribution

**What to Mock:**
- Not typically mocked in this codebase; prefer integration testing
- File I/O tested with real `tempfile.NamedTemporaryFile()` context managers (see `test_project_serialization_new_fields()`)

**What NOT to Mock:**
- Core simulation logic: always test with real tracer
- Ray sampling functions: test with real RNG
- Geometry and material behavior: test with actual shapes and properties

## Fixtures and Factories

**Test Data:**
- **Factory function** `_make_box_scene()` with parameters:
  ```python
  def _make_box_scene(
      rays_per_source=5000,
      wall_reflectance=0.9,
      wall_type="reflector",
      source_flux=1000.0,
  ) -> Project:
      # Returns configured Project with box geometry
  ```
- **Inline construction** in specific tests:
  ```python
  src = PointSource("s", np.array([0, 0, 0]), flux=100.0,
                    current_mA=20.0, flux_per_mA=5.0, thermal_derate=0.9)
  ```
- **Temporary files** for I/O tests:
  ```python
  with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
      path = f.name
  try:
      save_project(p, path)
      loaded = load_project(path)
  finally:
      os.unlink(path)
  ```

**Location:**
- `_make_box_scene()` defined at top of `test_tracer.py` (line 15)
- IES test file created inline: `tempfile.NamedTemporaryFile(mode="w", suffix=".ies", delete=False)`

## Coverage

**Requirements:** Not enforced; no coverage threshold or tooling configured

**View Coverage:**
- Not set up; would require `pytest-cov`: `pip install pytest-cov`
- Current practice: rely on test author inspection

## Test Types

**Unit Tests:**
- **Scope**: Test single functions or classes in isolation
- **Approach**:
  - `test_effective_flux_current_scaling()` tests `PointSource.effective_flux` property
  - `test_scatter_haze_zero_angle_unchanged()` tests `scatter_haze()` function with zero angle
  - `test_sphere_detector_basic()` tests `SphereDetector` functionality
- **Example**: `test_effective_flux_thermal_only()` — tests property calculation with specific inputs (`backlight_sim/tests/test_tracer.py:125`)

**Integration Tests:**
- **Scope**: Test tracer with full scene setup
- **Approach**:
  - `test_basic_simulation_produces_nonzero_heatmap()` runs full Monte Carlo with box scene
  - `test_tracer_supports_custom_angular_distribution_name()` tests tracer lookup of custom distribution
  - `test_haze_material_in_simulation()` tests material haze scattering in end-to-end simulation
- **Example**: `test_absorber_walls_fewer_hits_than_reflector()` compares two absorption behaviors (`backlight_sim/tests/test_tracer.py:58`)

**E2E Tests:**
- Not formally separated; integration tests serve as end-to-end verification
- `test_project_serialization_new_fields()` tests save → load cycle with all new fields
- `test_build_optical_stack()` tests geometry builder + project structure + serialization

## Common Patterns

**Async Testing:**
- Not used; all tests are synchronous
- Ray tracing runs in worker thread in GUI, but test layer is synchronous

**Error Testing:**
- Error handling tested via simulation behavior:
  - `test_zero_flux_produces_zero_results()` validates absorber prevents reflection
  - `test_custom_angular_distribution_sampling_points_forward()` validates sampler doesn't produce unphysical directions
- ValueError testing on IES parser:
  ```python
  with tempfile.NamedTemporaryFile(mode="w", suffix=".ies", delete=False) as f:
      f.write(ies_content)  # Synthetic IES file
      path = f.name
  try:
      profile = load_ies(path)
      assert profile["intensity"][0] == pytest.approx(1.0)
  finally:
      os.unlink(path)
  ```

**Property/Array Testing:**
- Direct array assertions: `np.testing.assert_array_equal(r1.detectors["top_detector"].grid, r2.detectors["top_detector"].grid)` for determinism testing
- Shape validation: `assert scattered.shape == (1000, 3)` for sampling functions
- Aggregate checks: `assert float(dirs[:, 2].mean()) > 0.5` for directional bias

**Progress Callback Testing:**
```python
def test_progress_callback_called():
    calls = []
    RayTracer(_make_box_scene()).run(progress_callback=lambda p: calls.append(p))
    assert len(calls) > 0
    assert calls[-1] == pytest.approx(1.0)  # Final progress is 100%
```

## New Test Additions

**Where to add tests:**
- Simulation core changes → `backlight_sim/tests/test_tracer.py`
- New I/O parsers → add test function in same file (or create `test_io.py` if significant)
- GUI changes → test via integration (GUI not directly tested; functionality tested in core)

**Template for new test:**
```python
def test_feature_description():
    """What this test validates."""
    # Arrange: setup scene
    project = _make_box_scene(rays_per_source=1000)
    project.sources[0].some_param = new_value

    # Act: run simulation
    result = RayTracer(project).run()

    # Assert: verify output
    det = result.detectors["top_detector"]
    assert det.total_hits > 0
    assert det.grid.sum() > expected_minimum
```

---

*Testing analysis: 2026-03-14*
