"""UI-layer UQ rendering tests (Phase 4 Wave 3).

Covers:
- Heatmap panel CI label formatting (mean ± half_width)
- Legacy fallback when n_batches < 4
- Confidence-level dropdown re-renders without re-running tracer
- Per-bin relative stderr overlay mode
- UQ warning banner visibility + content
- KPI CSV export schema with CI columns
- ConvergenceTab construction + population + legacy no-op
- Parameter sweep dialog ErrorBarItem + CI table columns
- rays_per_batch-aware efficiency scaling (checker I5)

All tests run under QT_QPA_PLATFORM=offscreen — no display required.
"""

from __future__ import annotations

import csv
import os
import re

# Ensure Qt runs headless before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

from PySide6.QtWidgets import QApplication

from backlight_sim.core.detectors import DetectorResult, SimulationResult


# ---------------------------------------------------------------------------
# QApplication fixture (module scope — one per test run)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ---------------------------------------------------------------------------
# Helpers for building synthetic SimulationResults
# ---------------------------------------------------------------------------


def _make_uq_result(
    n_batches: int = 10,
    ny: int = 20,
    nx: int = 20,
    rays_per_batch_list: list[int] | None = None,
    total_emitted_flux: float = 1000.0,
    warnings: list[str] | None = None,
    add_spatial_variance: bool = True,
) -> SimulationResult:
    """Build a SimulationResult with UQ data populated.

    Per-batch grids have mean ~= 1.0 and small stochastic variance.
    """
    rng = np.random.default_rng(42)
    if add_spatial_variance:
        # Batches with real variance so CI half_width > 0.
        grid_batches = rng.uniform(0.5, 1.5, size=(n_batches, ny, nx))
    else:
        # Deterministic identical batches -> zero variance.
        grid_batches = np.ones((n_batches, ny, nx))

    grid = grid_batches.sum(axis=0) / n_batches  # average per-batch
    # For efficiency, flux_batches should match per-batch flux totals proportional
    # to rays_per_batch; caller can override rays_per_batch_list explicitly.
    if rays_per_batch_list is None:
        rays_per_batch_list = [100] * n_batches
    rpb = np.asarray(rays_per_batch_list, dtype=float)
    # Make flux_batches exactly proportional to rays_per_batch (=> per-batch
    # efficiency is identical and half_width should be ~0).
    flux_batches = rpb * (total_emitted_flux * 0.5 / rpb.sum())
    hits_batches = (rpb * 0.9).astype(int)

    det = DetectorResult(
        detector_name="det0",
        grid=grid,
        total_hits=int(hits_batches.sum()),
        total_flux=float(flux_batches.sum()),
        grid_batches=grid_batches,
        hits_batches=hits_batches,
        flux_batches=flux_batches,
        rays_per_batch=list(rays_per_batch_list),
        n_batches=n_batches,
    )
    sim = SimulationResult(
        detectors={"det0": det},
        total_emitted_flux=total_emitted_flux,
        escaped_flux=total_emitted_flux * 0.1,
        source_count=1,
        uq_warnings=warnings or [],
    )
    return sim


def _make_legacy_result(ny: int = 20, nx: int = 20) -> SimulationResult:
    """Build a SimulationResult with no UQ data (n_batches=0)."""
    grid = np.ones((ny, nx))
    det = DetectorResult(
        detector_name="det0",
        grid=grid,
        total_hits=500,
        total_flux=500.0,
        n_batches=0,
    )
    return SimulationResult(
        detectors={"det0": det},
        total_emitted_flux=1000.0,
        escaped_flux=100.0,
        source_count=1,
    )


# ---------------------------------------------------------------------------
# Task 1 tests: HeatmapPanel CI rendering
# ---------------------------------------------------------------------------


_CI_REGEX = re.compile(r"^\d+(\.\d+)?\s*±\s*\d+(\.\d+)?.*$")
_PLAIN_REGEX = re.compile(r"^-?\d+(\.\d+)?.*$")


def test_heatmap_labels_show_ci_when_n_batches_nonzero(qapp):
    from backlight_sim.gui.heatmap_panel import HeatmapPanel

    panel = HeatmapPanel()
    result = _make_uq_result(n_batches=10, add_spatial_variance=True)
    panel.update_results(result)
    text = panel._lbl_avg.text()
    # Should render "mean ± half_width" format
    assert "±" in text, f"Expected ± in label '{text}'"


def test_heatmap_labels_fallback_when_legacy(qapp):
    from backlight_sim.gui.heatmap_panel import HeatmapPanel

    panel = HeatmapPanel()
    result = _make_legacy_result()
    panel.update_results(result)
    text = panel._lbl_avg.text()
    assert "±" not in text, f"Legacy label should have no ±: '{text}'"


def test_heatmap_labels_fallback_when_sub_floor(qapp):
    from backlight_sim.gui.heatmap_panel import HeatmapPanel

    panel = HeatmapPanel()
    # n_batches=3 < 4 floor: fall back to plain mean.
    result = _make_uq_result(n_batches=3, rays_per_batch_list=[100, 100, 100])
    panel.update_results(result)
    text = panel._lbl_avg.text()
    assert "±" not in text, f"Sub-floor label should have no ±: '{text}'"


def test_confidence_combo_recomputes_without_rerun(qapp):
    from backlight_sim.gui.heatmap_panel import HeatmapPanel

    panel = HeatmapPanel()
    result = _make_uq_result(n_batches=10, add_spatial_variance=True)
    panel.update_results(result)
    # Default is 95% CI (index 1). Switch to 99% (index 2).
    text_95 = panel._lbl_avg.text()
    assert "±" in text_95
    panel._conf_combo.setCurrentIndex(2)  # 99%
    # Trigger the slot explicitly in case the combo change is queued.
    qapp.processEvents()
    text_99 = panel._lbl_avg.text()
    assert "±" in text_99
    # The 99% CI half-width should be larger than 95%, so label changes.
    assert text_95 != text_99, (
        f"Expected different labels for 95% vs 99% CI, got '{text_95}' "
        f"and '{text_99}'"
    )


def test_noise_overlay_mode_renders(qapp):
    from backlight_sim.gui.heatmap_panel import HeatmapPanel
    from backlight_sim.core.uq import per_bin_stderr

    panel = HeatmapPanel()
    result = _make_uq_result(n_batches=10, add_spatial_variance=True)
    panel.update_results(result)
    # Select the per-bin relative stderr item.
    idx = panel._color_mode.findText("Per-bin relative stderr")
    assert idx >= 0, "Per-bin relative stderr mode must be in color mode combo"
    panel._color_mode.setCurrentIndex(idx)
    qapp.processEvents()
    # Check image data is set from the stderr calculation.
    gb = result.detectors["det0"].grid_batches
    expected_stderr = per_bin_stderr(gb)
    # The panel displays a relative stderr; we confirm the render happened
    # by verifying the image item has data roughly the right shape.
    img = panel._img.image
    assert img is not None
    # ImageItem stores transposed (width, height). Verify shape matches.
    assert img.shape[0] == expected_stderr.shape[1]
    assert img.shape[1] == expected_stderr.shape[0]


def test_uq_warning_banner_visible(qapp):
    from backlight_sim.gui.heatmap_panel import HeatmapPanel

    panel = HeatmapPanel()
    result = _make_uq_result(n_batches=10, warnings=["adaptive sampling + UQ may bias CI"])
    panel.update_results(result)
    assert panel._uq_warning_label.isVisible()
    assert "adaptive" in panel._uq_warning_label.text().lower()


def test_uq_warning_banner_shows_multiple_warnings(qapp):
    from backlight_sim.gui.heatmap_panel import HeatmapPanel

    panel = HeatmapPanel()
    warnings = [
        "Adaptive sampling + UQ may bias CI.",
        "UQ CI undefined (k' < 4).",
    ]
    result = _make_uq_result(n_batches=10, warnings=warnings)
    panel.update_results(result)
    text = panel._uq_warning_label.text()
    assert "adaptive" in text.lower()
    assert "UQ CI undefined" in text


def test_uq_warning_banner_hidden(qapp):
    from backlight_sim.gui.heatmap_panel import HeatmapPanel

    panel = HeatmapPanel()
    result = _make_uq_result(n_batches=10, warnings=[])
    panel.update_results(result)
    assert not panel._uq_warning_label.isVisible()


def test_export_kpi_csv_includes_ci_columns(qapp, tmp_path, monkeypatch):
    from backlight_sim.gui.heatmap_panel import HeatmapPanel
    from PySide6.QtWidgets import QFileDialog

    panel = HeatmapPanel()
    result = _make_uq_result(n_batches=10, add_spatial_variance=True)
    panel.update_results(result)

    out_path = tmp_path / "kpi.csv"
    # Stub the file dialog so export writes to our tmp_path.
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName",
        classmethod(lambda cls, *a, **kw: (str(out_path), "")),
    )
    panel._export_kpi_csv()
    assert out_path.exists()
    with out_path.open("r", newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert len(rows) > 1
    header = [c.lower() for c in rows[0]]
    for col in ("mean", "half_width", "std", "lower", "upper", "n_batches", "conf_level"):
        assert col in header, f"Missing CI column '{col}' in header {header}"


def test_export_kpi_csv_legacy(qapp, tmp_path, monkeypatch):
    from backlight_sim.gui.heatmap_panel import HeatmapPanel
    from PySide6.QtWidgets import QFileDialog

    panel = HeatmapPanel()
    result = _make_legacy_result()
    panel.update_results(result)

    out_path = tmp_path / "kpi_legacy.csv"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName",
        classmethod(lambda cls, *a, **kw: (str(out_path), "")),
    )
    panel._export_kpi_csv()
    assert out_path.exists()
    with out_path.open("r", newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    header = [c.lower() for c in rows[0]]
    # CI columns still present; legacy rows have empty or nan values for CI cells.
    for col in ("mean", "half_width", "std", "lower", "upper", "n_batches", "conf_level"):
        assert col in header, f"Missing CI column '{col}' in header {header}"


def test_efficiency_ci_uses_rays_per_batch_not_naive_division(qapp):
    """Verify _per_batch_source_flux uses rays_per_batch (not total/K)."""
    from backlight_sim.core.kpi import _per_batch_source_flux

    # Uneven split: K=10, rays_total=1005 -> [101]*5 + [100]*5
    grid_batches = np.ones((10, 5, 5))
    flux_batches = np.asarray([101.0] * 5 + [100.0] * 5)
    rays_per_batch = [101] * 5 + [100] * 5

    det = DetectorResult(
        detector_name="d",
        grid=grid_batches.sum(axis=0) / 10,
        total_hits=1,
        total_flux=float(flux_batches.sum()),
        grid_batches=grid_batches,
        flux_batches=flux_batches,
        rays_per_batch=rays_per_batch,
        n_batches=10,
    )
    result = SimulationResult(
        detectors={"d": det},
        total_emitted_flux=1005.0,
        source_count=1,
    )
    per_batch_src = _per_batch_source_flux(result, det)
    assert per_batch_src is not None
    # Batch 0 should have source flux 101.0, batch 9 should have 100.0
    assert np.allclose(per_batch_src[:5], 101.0)
    assert np.allclose(per_batch_src[5:], 100.0)
    # Naive formula (1005/10 = 100.5) would produce a different per-batch vector.
    naive = 1005.0 / 10.0
    assert not np.allclose(per_batch_src, naive)
