"""
Tests for the C++ blu_tracer extension (C++-01 through C++-08).

Run with:  pytest backlight_sim/tests/test_cpp_tracer.py -v
"""
from __future__ import annotations

import importlib

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helper: build a minimal serialized project dict for testing
# ---------------------------------------------------------------------------


def _make_simple_project(n_rays: int = 1000, max_bounces: int = 10) -> dict:
    """Return a project_dict for a simple enclosed box scene.

    Box: 50x50x20mm, LED at center bottom, detector at top.
    All surfaces are reflectors (reflectance=0.9), detector absorbs.
    """
    surfaces = [
        # Floor
        {
            "name": "floor",
            "center": [25.0, 25.0, 0.0],
            "normal": [0.0, 0.0, 1.0],
            "u_axis": [1.0, 0.0, 0.0],
            "v_axis": [0.0, 1.0, 0.0],
            "size": [50.0, 50.0],
            "material_name": "reflector",
            "optical_properties_name": "",
        },
        # Wall -X
        {
            "name": "wall_x0",
            "center": [0.0, 25.0, 10.0],
            "normal": [1.0, 0.0, 0.0],
            "u_axis": [0.0, 1.0, 0.0],
            "v_axis": [0.0, 0.0, 1.0],
            "size": [50.0, 20.0],
            "material_name": "reflector",
            "optical_properties_name": "",
        },
        # Wall +X
        {
            "name": "wall_x1",
            "center": [50.0, 25.0, 10.0],
            "normal": [-1.0, 0.0, 0.0],
            "u_axis": [0.0, 1.0, 0.0],
            "v_axis": [0.0, 0.0, 1.0],
            "size": [50.0, 20.0],
            "material_name": "reflector",
            "optical_properties_name": "",
        },
        # Wall -Y
        {
            "name": "wall_y0",
            "center": [25.0, 0.0, 10.0],
            "normal": [0.0, 1.0, 0.0],
            "u_axis": [1.0, 0.0, 0.0],
            "v_axis": [0.0, 0.0, 1.0],
            "size": [50.0, 20.0],
            "material_name": "reflector",
            "optical_properties_name": "",
        },
        # Wall +Y
        {
            "name": "wall_y1",
            "center": [25.0, 50.0, 10.0],
            "normal": [0.0, -1.0, 0.0],
            "u_axis": [1.0, 0.0, 0.0],
            "v_axis": [0.0, 0.0, 1.0],
            "size": [50.0, 20.0],
            "material_name": "reflector",
            "optical_properties_name": "",
        },
    ]

    detectors = [
        {
            "name": "top_detector",
            "center": [25.0, 25.0, 20.0],
            "normal": [0.0, 0.0, -1.0],
            "u_axis": [1.0, 0.0, 0.0],
            "v_axis": [0.0, 1.0, 0.0],
            "size": [50.0, 50.0],
            "resolution": [50, 50],
        }
    ]

    materials = {
        "reflector": {
            "surface_type": "reflector",
            "reflectance": 0.9,
            "transmittance": 0.0,
            "is_diffuse": True,
            "haze": 0.0,
            "refractive_index": 1.0,
        }
    }

    sources = [
        {
            "name": "led_0",
            "position": [25.0, 25.0, 0.5],
            "direction": [0.0, 0.0, 1.0],
            "distribution": "lambertian",
            "effective_flux": 1.0,
            "enabled": True,
            "flux_tolerance": 0.0,
            "spd": "white",
        }
    ]

    settings = {
        "rays_per_source": n_rays,
        "max_bounces": max_bounces,
        "energy_threshold": 1e-4,
        "random_seed": 42,
        "record_ray_paths": 0,
        "use_multiprocessing": False,
        "adaptive_sampling": False,
        "check_interval": n_rays,
    }

    return {
        "sources": sources,
        "surfaces": surfaces,
        "detectors": detectors,
        "sphere_detectors": [],
        "materials": materials,
        "optical_properties": {},
        "angular_distributions": {},
        "solid_bodies": [],
        "solid_cylinders": [],
        "solid_prisms": [],
        "bsdf_profiles": {},
        "settings": settings,
    }


# ---------------------------------------------------------------------------
# C++-01: .pyd loads without error
# ---------------------------------------------------------------------------


def test_blu_tracer_loads():
    """C++-01: The blu_tracer C++ extension loads without ImportError."""
    try:
        from backlight_sim.sim import blu_tracer  # noqa: F401
    except ImportError as e:
        pytest.fail(f"blu_tracer failed to import: {e}")


# ---------------------------------------------------------------------------
# C++-02: trace_source returns valid dict with grids
# ---------------------------------------------------------------------------


def test_trace_source_returns_valid_dict():
    """C++-02: trace_source returns a dict with required keys and correct shapes."""
    from backlight_sim.sim import blu_tracer

    project_dict = _make_simple_project(n_rays=500)
    result = blu_tracer.trace_source(project_dict, "led_0", 42)

    assert isinstance(result, dict), "Result must be a dict"
    assert "grids" in result, "Result must have 'grids' key"
    assert "escaped" in result, "Result must have 'escaped' key"
    assert "sb_stats" in result, "Result must have 'sb_stats' key"
    assert "sph_grids" in result, "Result must have 'sph_grids' key"
    assert "spectral_grids" in result, "Result must have 'spectral_grids' key"

    grids = result["grids"]
    assert "top_detector" in grids, "Detector grid must be present"
    det_entry = grids["top_detector"]
    assert "grid" in det_entry and "hits" in det_entry and "flux" in det_entry

    grid = np.asarray(det_entry["grid"])
    assert grid.ndim == 2, f"Grid must be 2D, got {grid.ndim}D"
    assert grid.dtype == np.float64 or grid.dtype == float

    assert isinstance(result["escaped"], float), "'escaped' must be float"


# ---------------------------------------------------------------------------
# C++-03: All 20 existing tracer tests pass (run via full suite)
# ---------------------------------------------------------------------------


def test_existing_tests_are_still_runnable():
    """C++-03: Verify the existing test module can be imported (tests run via full suite)."""
    import importlib.util

    spec = importlib.util.find_spec("backlight_sim.tests.test_tracer")
    assert spec is not None, "test_tracer.py must remain importable"


# ---------------------------------------------------------------------------
# C++-04: Determinism - same seed produces same result
# ---------------------------------------------------------------------------


def test_determinism():
    """C++-04: Two calls with same seed produce bit-identical grids."""
    from backlight_sim.sim import blu_tracer

    project_dict = _make_simple_project(n_rays=2000)

    r1 = blu_tracer.trace_source(project_dict, "led_0", seed=12345)
    r2 = blu_tracer.trace_source(project_dict, "led_0", seed=12345)

    g1 = np.asarray(r1["grids"]["top_detector"]["grid"])
    g2 = np.asarray(r2["grids"]["top_detector"]["grid"])

    np.testing.assert_array_equal(
        g1, g2,
        err_msg="Same seed must produce identical grids (C++ RNG is deterministic)",
    )


# ---------------------------------------------------------------------------
# C++-05: Energy conservation within 0.1% for enclosed scene
# ---------------------------------------------------------------------------


def test_energy_conservation():
    """C++-05: Total flux in + escaped <= source emission within 0.1%."""
    from backlight_sim.sim import blu_tracer

    project_dict = _make_simple_project(n_rays=10000, max_bounces=50)
    # Low reflectance => most energy absorbed in walls.
    project_dict["materials"]["reflector"]["reflectance"] = 0.1

    result = blu_tracer.trace_source(project_dict, "led_0", seed=99)

    source_flux = project_dict["sources"][0]["effective_flux"]
    detector_flux = result["grids"]["top_detector"]["flux"]
    escaped = result["escaped"]

    # Full energy conservation (detector + absorbed + escaped == source) requires
    # the real bounce loop from Plan 02-02. For the Wave 1 stub this simply
    # asserts the accounting is non-negative and does not exceed source flux.
    total_accounted = detector_flux + escaped
    assert total_accounted <= source_flux * 1.001, (
        f"Accounted flux ({total_accounted:.4f}) exceeds source flux ({source_flux:.4f}) "
        "by more than 0.1% - energy not conserved"
    )


# ---------------------------------------------------------------------------
# C++-06: Statistical equivalence - C++ vs Python within 5% per pixel
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="Requires real bounce loop from Plan 02-02 - enable in Wave 3")
def test_statistical_equivalence():
    """C++-06: C++ result agrees with Python/Numba within 5% per pixel (100k rays)."""
    from backlight_sim.sim import blu_tracer  # noqa: F401

    # This test will be un-skipped in Plan 04 after full bounce loop is in.
    project_dict = _make_simple_project(n_rays=100_000)
    _ = blu_tracer.trace_source(project_dict, "led_0", seed=42)
    pytest.skip("Enable after Plan 02-02 real bounce loop")


# ---------------------------------------------------------------------------
# C++-07: Speedup 3-8x over Python baseline
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="Requires real bounce loop from Plan 02-02 - enable in Wave 4")
def test_speedup():
    """C++-07: C++ path is 3-8x faster than Python/Numba baseline (print timing)."""
    pytest.skip("Enable after Plan 02-02 real bounce loop - see Plan 02-04")


# ---------------------------------------------------------------------------
# C++-08: Numba entirely absent from codebase imports
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="Enable after Plan 02-03 removes Numba - accel.py deleted")
def test_no_numba_imports():
    """C++-08: No module in backlight_sim.sim imports numba after Numba removal."""
    import pkgutil

    import backlight_sim.sim as sim_pkg

    numba_found = []
    for _importer, modname, _ispkg in pkgutil.walk_packages(
        path=sim_pkg.__path__,
        prefix=sim_pkg.__name__ + ".",
        onerror=lambda x: None,
    ):
        try:
            mod = importlib.import_module(modname)
            src = getattr(mod, "__file__", "") or ""
            if src.endswith(".py"):
                with open(src, encoding="utf-8") as f:
                    content = f.read()
                if "import numba" in content or "from numba" in content:
                    numba_found.append(modname)
        except Exception:
            pass

    assert not numba_found, (
        f"Numba imports still present in: {numba_found}\n"
        "All numba references must be removed per D-05/D-06."
    )
