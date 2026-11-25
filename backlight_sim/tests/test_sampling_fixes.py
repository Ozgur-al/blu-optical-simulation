"""Regression tests for sampling.py fixes: BSDF nearest theta_in bin, haze hemisphere."""
from __future__ import annotations

import numpy as np

from backlight_sim.sim.sampling import (
    nearest_theta_in_bin,
    sample_bsdf,
    scatter_haze,
)


def test_nearest_theta_in_bin():
    bins = np.array([0.0, 15.0, 30.0, 45.0])
    th = np.array([-5.0, 0.0, 7.4, 7.6, 29.0, 44.9, 45.0, 80.0])
    np.testing.assert_array_equal(nearest_theta_in_bin(bins, th), [0, 0, 0, 1, 2, 3, 3, 3])
    assert nearest_theta_in_bin(np.array([10.0]), np.array([0.0, 50.0])).tolist() == [0, 0]


def test_sample_bsdf_uses_nearest_theta_in_row():
    # Row 0 (theta_in=0) scatters to ~10 deg; row 1 (theta_in=45) to ~70 deg.
    theta_out = list(np.arange(0.0, 91.0, 1.0))
    row_a = [1.0 if abs(t - 10) <= 1 else 0.0 for t in theta_out]
    row_b = [1.0 if abs(t - 70) <= 1 else 0.0 for t in theta_out]
    profile = {
        "theta_in": [0.0, 45.0],
        "theta_out": theta_out,
        "refl_intensity": [row_a, row_b],
        "trans_intensity": [row_a, row_b],
    }
    normal = np.array([0.0, 0.0, 1.0])
    inc = np.radians(44.0)  # nearest row is 45 deg, floor would pick 0 deg
    d = np.array([np.sin(inc), 0.0, -np.cos(inc)])
    n = 2000
    out = sample_bsdf(n, np.tile(d, (n, 1)), normal, profile, "reflect",
                      np.random.default_rng(0))
    theta = np.degrees(np.arccos(np.clip(out @ normal, -1, 1)))
    assert np.median(theta) > 60.0, np.median(theta)


def test_scatter_haze_folds_into_reflection_hemisphere():
    rng = np.random.default_rng(1)
    normal = np.array([0.0, 0.0, 1.0])
    # Grazing specular reflection: 2 deg above the surface, 20 deg haze cone
    g = np.radians(2.0)
    d = np.tile([np.cos(g), 0.0, np.sin(g)], (5000, 1))
    unfolded = scatter_haze(d, 20.0, np.random.default_rng(1))
    assert (unfolded @ normal <= 0).any()  # sanity: the cone does dip below
    folded = scatter_haze(d, 20.0, rng, surface_normals=normal)
    assert np.all(folded @ normal > 0)
    np.testing.assert_allclose(np.linalg.norm(folded, axis=1), 1.0, atol=1e-12)
    # Per-ray normals form also accepted
    folded2 = scatter_haze(d, 20.0, np.random.default_rng(1),
                           surface_normals=np.tile(normal, (5000, 1)))
    assert np.all(folded2 @ normal > 0)


def test_scatter_haze_without_normals_unchanged_api():
    d = np.tile([0.0, 0.0, 1.0], (100, 1))
    a = scatter_haze(d, 5.0, np.random.default_rng(3))
    b = scatter_haze(d, 5.0, np.random.default_rng(3), surface_normals=None)
    np.testing.assert_array_equal(a, b)
    assert np.all(a[:, 2] >= np.cos(np.radians(5.0)) - 1e-12)
