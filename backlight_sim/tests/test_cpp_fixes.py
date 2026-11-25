"""Regression tests for blu_tracer C++ fixes (skipped when the extension is not built).

Covers: relative energy_threshold, unknown-distribution -> isotropic fallback,
diffuser honoring is_diffuse on reflect, unsorted angular profile, haze
hemisphere fold, zero-size detector binning.
"""
from __future__ import annotations

import numpy as np
import pytest

from backlight_sim.sim import blu_tracer

pytestmark = pytest.mark.skipif(blu_tracer is None, reason="blu_tracer extension not built")


def _plane(name, center, normal, u, v, size, material=""):
    return {
        "name": name, "center": list(center), "normal": list(normal),
        "u_axis": list(u), "v_axis": list(v), "size": list(size),
        "material_name": material, "optical_properties_name": "",
    }


def _det(name, center, normal, u, v, size, res=(10, 10)):
    d = _plane(name, center, normal, u, v, size)
    d.pop("material_name"); d.pop("optical_properties_name")
    d["resolution"] = list(res)
    return d


def _mat(surface_type, R=0.0, T=0.0, diffuse=True, haze=0.0):
    return {"surface_type": surface_type, "reflectance": R, "transmittance": T,
            "is_diffuse": diffuse, "haze": haze, "refractive_index": 1.0}


def _project(surfaces, detectors, materials, *, distribution="lambertian",
             direction=(0.0, 0.0, 1.0), position=(0.0, 0.0, 0.0), flux=1.0,
             n_rays=5000, max_bounces=20, threshold=0.0, ang=None):
    return {
        "sources": [{
            "name": "s", "position": list(position), "direction": list(direction),
            "distribution": distribution, "effective_flux": flux, "enabled": True,
            "flux_tolerance": 0.0, "spd": "white",
        }],
        "surfaces": surfaces, "detectors": detectors, "sphere_detectors": [],
        "materials": materials, "optical_properties": {},
        "angular_distributions": ang or {},
        "solid_bodies": [], "solid_cylinders": [], "solid_prisms": [],
        "settings": {"rays_per_source": n_rays, "max_bounces": max_bounces,
                     "energy_threshold": threshold, "random_seed": 1,
                     "record_ray_paths": 0, "use_multiprocessing": False,
                     "adaptive_sampling": False, "check_interval": n_rays},
    }


X, Y, Z = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
NZ = (0.0, 0.0, -1.0)


def test_energy_threshold_is_relative_to_initial_weight():
    # Box with R=0.9 walls; weight/ray = 1/20000 = 5e-5 (< 1e-3 absolute).
    walls = [
        _plane("floor", (0, 0, 0), Z, X, Y, (50, 50), "r"),
        _plane("wx0", (-25, 0, 10), X, Y, Z, (50, 20), "r"),
        _plane("wx1", (25, 0, 10), (-1, 0, 0), Y, Z, (50, 20), "r"),
        _plane("wy0", (0, -25, 10), Y, X, Z, (50, 20), "r"),
        _plane("wy1", (0, 25, 10), (0, -1, 0), X, Z, (50, 20), "r"),
    ]
    det = [_det("top", (0, 0, 20), NZ, X, Y, (50, 50))]
    mats = {"r": _mat("reflector", R=0.9)}
    kw = dict(position=(0, 0, 0.5), n_rays=20000, max_bounces=50)
    lo = blu_tracer.trace_source(_project(walls, det, mats, threshold=1e-12, **kw), "s", 7)
    hi = blu_tracer.trace_source(_project(walls, det, mats, threshold=1e-3, **kw), "s", 7)
    f_lo = lo["grids"]["top"]["flux"]
    f_hi = hi["grids"]["top"]["flux"]
    # Relative 1e-3 needs 0.9**k < 1e-3 -> k >= 66 bounces > max_bounces: no kills.
    assert f_hi == pytest.approx(f_lo, rel=1e-12)


def test_unknown_distribution_falls_back_to_isotropic():
    det = [_det("below", (0, 0, -1), Z, X, Y, (100, 100))]
    res = blu_tracer.trace_source(
        _project([], det, {}, distribution="no_such_profile", n_rays=4000), "s", 3)
    frac = res["grids"]["below"]["flux"]
    # Isotropic sends ~half the rays downward; Lambertian(+z) sends none.
    assert 0.3 < frac < 0.6


def test_diffuser_reflect_honors_specular():
    ang = {"pencil": {"theta_deg": [0.0, 0.5], "intensity": [1.0, 1.0]}}
    surf = [_plane("dif", (0, 0, 10), NZ, X, Y, (100, 100), "d")]
    det = [_det("below", (0, 0, -1), Z, X, Y, (4, 4))]
    mats = {"d": _mat("diffuser", R=1.0, T=0.0, diffuse=False)}
    res = blu_tracer.trace_source(
        _project(surf, det, mats, distribution="pencil", n_rays=3000, ang=ang), "s", 5)
    # Specular return of a 0.5 deg pencil lands within ~0.2 mm of the source.
    assert res["grids"]["below"]["flux"] > 0.99


def test_unsorted_angular_profile():
    ang = {"cone": {"theta_deg": [10.0, 5.0, 0.0], "intensity": [0.0, 1.0, 1.0]}}
    det = [_det("top", (0, 0, 10), NZ, X, Y, (4, 4))]  # 10 deg -> r=1.76 mm
    res = blu_tracer.trace_source(
        _project([], det, {}, distribution="cone", n_rays=3000, ang=ang), "s", 9)
    assert res["grids"]["top"]["flux"] == pytest.approx(1.0, rel=1e-9)


def test_haze_grazing_reflection_stays_above_surface():
    # Grazing pencil (2 deg above a huge R=0.5 hazy mirror): every ray must
    # reflect exactly once -> detector + escaped == 0.5 * flux.
    g = np.radians(2.0)
    ang = {"pencil": {"theta_deg": [0.0, 0.01], "intensity": [1.0, 1.0]}}
    surf = [_plane("m", (0, 0, 0), Z, X, Y, (1e6, 1e6), "m")]
    mats = {"m": _mat("reflector", R=0.5, diffuse=False, haze=20.0)}
    res = blu_tracer.trace_source(
        _project(surf, [], mats, distribution="pencil",
                 direction=(np.cos(g), 0.0, -np.sin(g)), position=(0, 0, 1),
                 n_rays=4000, max_bounces=10, ang=ang), "s", 11)
    assert res["escaped"] == pytest.approx(0.5, rel=1e-9)


def test_zero_size_detector_does_not_crash():
    det = [_det("pt", (0, 0, 5), NZ, X, Y, (0.0, 0.0), res=(4, 4))]
    res = blu_tracer.trace_source(_project([], det, {}, n_rays=1000), "s", 1)
    g = np.asarray(res["grids"]["pt"]["grid"])
    assert g.shape == (4, 4) and np.all(np.isfinite(g))
