"""Regression tests for spectral.cct_robertson (Robertson 1968 isotherm method)."""
from __future__ import annotations

import numpy as np
import pytest

from backlight_sim.sim import spectral as sp


def _blackbody_xy(T: float) -> np.ndarray:
    """CIE 1931 xy of a Planckian radiator, integrated with the module's CMFs."""
    lam = np.arange(380.0, 781.0, 1.0)
    lam_m = lam * 1e-9
    h, c, k = 6.62607015e-34, 2.99792458e8, 1.380649e-23
    B = lam_m ** -5 / np.expm1(h * c / (lam_m * k * T))
    X = np.sum(B * np.interp(lam, sp._CIE_LAMBDA, sp._CIE_X))
    Y = np.sum(B * np.interp(lam, sp._CIE_LAMBDA, sp._CIE_Y))
    Z = np.sum(B * np.interp(lam, sp._CIE_LAMBDA, sp._CIE_Z))
    s = X + Y + Z
    return np.array([X / s, Y / s])


@pytest.mark.parametrize("T", [2700.0, 3000.0, 4000.0, 5000.0, 6500.0, 10000.0])
def test_blackbody_cct_recovered(T):
    cct = float(sp.cct_robertson(_blackbody_xy(T)[None, :])[0])
    assert abs(cct - T) / T < 0.02, f"T={T}: got {cct:.1f} K"


def test_cct_monotonic_in_temperature():
    temps = [2000.0, 3000.0, 4500.0, 6500.0, 9000.0, 15000.0]
    xy = np.stack([_blackbody_xy(T) for T in temps])
    cct = sp.cct_robertson(xy)
    assert np.all(np.diff(cct) > 0), cct


def test_d65_cct():
    # D65 white point; reference CCT ~6504 K
    cct = float(sp.cct_robertson(np.array([[0.31271, 0.32902]]))[0])
    assert abs(cct - 6504.0) < 60.0, cct


def test_cct_shape_clamp_and_nan():
    xy = np.array([[[0.31271, 0.32902], [np.nan, np.nan]],
                   [[0.60, 0.38], [0.24, 0.23]]])
    cct = sp.cct_robertson(xy)
    assert cct.shape == (2, 2)
    assert np.isnan(cct[0, 1])
    assert 1000.0 <= cct[1, 0] <= 1700.0      # very warm -> cool end of table
    assert cct[1, 1] == pytest.approx(25000.0)  # very blue -> clamped hot end
