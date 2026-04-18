"""Unit tests for backlight_sim.core.uq — batch-means CI math and Student-t table."""

from __future__ import annotations

import math
import subprocess
import sys
import textwrap

import numpy as np
import pytest

from backlight_sim.core.uq import (
    CIEstimate,
    batch_mean_ci,
    kpi_batches,
    per_bin_stderr,
    student_t_critical,
)


# ---------------------------------------------------------------------------
# Student-t table parity & coverage
# ---------------------------------------------------------------------------

def test_student_t_critical_matches_scipy_within_1e3():
    """Student-t critical values from the table match scipy.stats.t.ppf within 1e-3."""
    scipy_stats = pytest.importorskip("scipy.stats")

    cases = [
        (0.95, 4), (0.95, 10), (0.95, 20),  # K in {4,10,20}
        (0.90, 10), (0.99, 10),             # conf in {0.9,0.95,0.99} for K=10
        (0.99, 4),
    ]
    for conf, k in cases:
        dof = k - 1
        expected = float(scipy_stats.t.ppf(1 - (1 - conf) / 2, dof))
        got = student_t_critical(conf, k)
        assert abs(got - expected) < 1e-3, (
            f"t({dof}, {conf}) expected {expected:.4f}, got {got:.4f}"
        )


def test_student_t_table_has_51_entries():
    """Table covers dof in {3..19} × conf in {0.90, 0.95, 0.99} = 51 entries."""
    from backlight_sim.core.uq import _T_TABLE  # type: ignore[attr-defined]

    assert len(_T_TABLE) == 51


def test_student_t_critical_clamps_dof_to_19():
    """For K > 20 (dof > 19) return the dof=19 critical value (asymptotic tail clamp)."""
    t19 = student_t_critical(0.95, 20)
    t_huge = student_t_critical(0.95, 100)
    assert t19 == t_huge  # clamped


def test_student_t_critical_rejects_unsupported_conf():
    with pytest.raises(ValueError):
        student_t_critical(0.80, 10)
    with pytest.raises(ValueError):
        student_t_critical(0.5, 10)


def test_student_t_critical_rejects_small_k():
    with pytest.raises(ValueError):
        student_t_critical(0.95, 3)  # K=3 → dof=2, below floor


# ---------------------------------------------------------------------------
# batch_mean_ci — core formula
# ---------------------------------------------------------------------------

def test_batch_mean_ci_synthetic_k10():
    """K=10 synthetic iid batch means → mean exact, std exact, half_width = t*s/sqrt(K)."""
    rng = np.random.default_rng(42)
    values = rng.normal(loc=100.0, scale=5.0, size=10)
    ci = batch_mean_ci(values, conf_level=0.95)

    assert ci.mean == pytest.approx(float(values.mean()), rel=1e-12)
    assert ci.std == pytest.approx(float(values.std(ddof=1)), rel=1e-12)
    assert ci.n_batches == 10
    assert ci.conf_level == 0.95

    # Expected half-width: t_{9,0.975} * s/sqrt(10), t=2.2622 (table)
    expected_hw = 2.2622 * float(values.std(ddof=1)) / np.sqrt(10)
    assert ci.half_width == pytest.approx(expected_hw, rel=1e-4)


def test_batch_mean_ci_lower_upper_properties():
    """CIEstimate.lower / .upper are symmetric around mean."""
    ci = CIEstimate(mean=10.0, half_width=1.5, std=2.0, n_batches=10, conf_level=0.95)
    assert ci.lower == pytest.approx(8.5)
    assert ci.upper == pytest.approx(11.5)


def test_batch_mean_ci_half_width_shrinks_as_sqrt_n():
    """half_width of per-batch means shrinks by sqrt(2) when per-batch N doubles.

    Simulate: K=10 batches, each batch is a mean of n_per_batch iid N(0,1) samples.
    The per-batch mean has stderr 1/sqrt(n_per_batch); the batch-means CI stderr is
    1/sqrt(K*n_per_batch). Doubling n_per_batch → half_width shrinks by sqrt(2) in
    expectation.
    """
    rng = np.random.default_rng(42)
    K = 10
    # Many repeated experiments, compare mean half_widths
    def mean_half_width(n_per_batch: int) -> float:
        hws = []
        for _ in range(200):
            batches = rng.normal(0.0, 1.0, size=(K, n_per_batch)).mean(axis=1)
            hws.append(batch_mean_ci(batches, 0.95).half_width)
        return float(np.mean(hws))

    hw_1000 = mean_half_width(1000)
    hw_2000 = mean_half_width(2000)
    ratio = hw_1000 / hw_2000
    assert 1.2 < ratio < 1.6, f"expected ratio ≈ sqrt(2)=1.414, got {ratio:.3f}"


def test_batch_mean_ci_requires_min_4_values():
    with pytest.raises(ValueError):
        batch_mean_ci([1.0, 2.0, 3.0], 0.95)


def test_batch_mean_ci_rejects_bad_conf():
    with pytest.raises(ValueError):
        batch_mean_ci([1.0, 2.0, 3.0, 4.0, 5.0], 0.80)


def test_batch_mean_ci_accepts_list_and_array():
    ci_list = batch_mean_ci([1.0, 2.0, 3.0, 4.0, 5.0], 0.95)
    ci_arr = batch_mean_ci(np.array([1.0, 2.0, 3.0, 4.0, 5.0]), 0.95)
    assert ci_list.mean == ci_arr.mean
    assert ci_list.half_width == ci_arr.half_width


# ---------------------------------------------------------------------------
# CIEstimate.format
# ---------------------------------------------------------------------------

def test_ci_estimate_format_aligns_precision():
    """mean=87.324, half_width=1.23 → '87.3 ± 1.2%' (aligned to 2 sig figs of hw)."""
    ci = CIEstimate(mean=87.324, half_width=1.23, std=3.9, n_batches=10, conf_level=0.95)
    s = ci.format(precision=3, unit="%")
    assert "±" in s
    assert s.endswith("%")
    # mean and hw should be formatted to same decimals — 1 decimal here
    assert "87.3" in s
    assert "1.2" in s


def test_ci_estimate_format_legacy_no_ci_when_n_batches_zero():
    """n_batches == 0 → show plain 'mean unit' without ± token (legacy display)."""
    ci = CIEstimate(mean=42.0, half_width=0.0, std=0.0, n_batches=0, conf_level=0.95)
    s = ci.format(precision=3, unit="%")
    assert "±" not in s
    assert "42" in s


def test_ci_estimate_format_no_ci_when_hw_nonfinite():
    ci = CIEstimate(
        mean=42.0, half_width=float("nan"), std=0.0, n_batches=10, conf_level=0.95
    )
    s = ci.format(precision=3, unit="%")
    assert "±" not in s


# ---------------------------------------------------------------------------
# per_bin_stderr
# ---------------------------------------------------------------------------

def test_per_bin_stderr_matches_elementwise_formula():
    """Exact match to np.std(axis=0, ddof=1) / sqrt(K) on Poisson(100) batches."""
    rng = np.random.default_rng(7)
    grid_batches = rng.poisson(lam=100.0, size=(10, 50, 50)).astype(float)
    expected = grid_batches.std(axis=0, ddof=1) / np.sqrt(10)
    got = per_bin_stderr(grid_batches)
    np.testing.assert_allclose(got, expected, rtol=1e-12, atol=1e-12)


def test_per_bin_stderr_poisson_noise_floor_agreement():
    """On uniform high-N case batch stderr ≈ Poisson noise floor sqrt(lam/K) within 20%."""
    rng = np.random.default_rng(11)
    K = 10
    lam = 500.0
    grid_batches = rng.poisson(lam=lam, size=(K, 20, 20)).astype(float)
    batch_se = per_bin_stderr(grid_batches).mean()
    # Mean Poisson stderr per bin across K batches = sqrt(lam) / sqrt(K)
    poisson_floor = np.sqrt(lam) / np.sqrt(K)
    ratio = batch_se / poisson_floor
    assert 0.8 <= ratio <= 1.2, f"batch SE/Poisson floor={ratio:.3f} out of 20% band"


def test_per_bin_stderr_k1_returns_zeros():
    grid_batches = np.random.default_rng(0).random((1, 10, 10))
    se = per_bin_stderr(grid_batches)
    assert se.shape == (10, 10)
    assert np.all(se == 0.0)


def test_per_bin_stderr_rejects_wrong_dims():
    with pytest.raises(ValueError):
        per_bin_stderr(np.zeros((10, 10)))  # 2D not supported


# ---------------------------------------------------------------------------
# kpi_batches
# ---------------------------------------------------------------------------

def test_kpi_batches_mean_matches_axis_reduction():
    """kpi_batches(grid_batches, mean) == grid_batches.mean(axis=(1,2))."""
    rng = np.random.default_rng(3)
    grid_batches = rng.random((10, 20, 20))
    out = kpi_batches(grid_batches, lambda g: float(g.mean()))
    np.testing.assert_allclose(out, grid_batches.mean(axis=(1, 2)), rtol=1e-12)


def test_kpi_batches_returns_k_shape():
    grid_batches = np.zeros((7, 5, 5))
    out = kpi_batches(grid_batches, lambda g: 1.0)
    assert out.shape == (7,)
    np.testing.assert_array_equal(out, np.ones(7))


# ---------------------------------------------------------------------------
# Layering: core/uq.py must not pull in PySide6/pyqtgraph/gui
# ---------------------------------------------------------------------------

def test_core_uq_has_no_gui_imports():
    code = textwrap.dedent(
        """
        import sys, backlight_sim.core.uq  # noqa
        forbidden = {m for m in sys.modules
                     if m.startswith(("PySide6", "pyqtgraph", "backlight_sim.gui"))}
        assert not forbidden, f"core.uq leaked imports: {sorted(forbidden)}"
        """
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
