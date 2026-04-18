"""Export-surface UQ tests (Phase 4 Wave 3).

Covers the CI-column schema on HTML report, KPI CSV, and batch ZIP KPI CSV,
plus an end-to-end smoke test that runs the Simple Box preset through the
full export path.
"""

from __future__ import annotations

import csv
import io
import os
import sys
import zipfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

from backlight_sim.core.detectors import DetectorResult, SimulationResult
from backlight_sim.core.project_model import Project, SimulationSettings


# ---------------------------------------------------------------------------
# Synthetic result builders
# ---------------------------------------------------------------------------


def _uq_result(
    n_batches: int = 10,
    ny: int = 8,
    nx: int = 8,
    rays_per_batch: list[int] | None = None,
    total_emitted_flux: float = 1000.0,
    add_variance: bool = True,
) -> SimulationResult:
    rng = np.random.default_rng(42)
    if add_variance:
        gb = rng.uniform(0.5, 1.5, size=(n_batches, ny, nx))
    else:
        gb = np.ones((n_batches, ny, nx))
    grid = gb.sum(axis=0) / n_batches
    if rays_per_batch is None:
        rays_per_batch = [100] * n_batches
    rpb = np.asarray(rays_per_batch, dtype=float)
    # Flux exactly proportional to rays_per_batch => per-batch eff is constant.
    flux_batches = rpb * (total_emitted_flux * 0.5 / rpb.sum())
    det = DetectorResult(
        detector_name="det0",
        grid=grid,
        total_hits=int(rpb.sum()),
        total_flux=float(flux_batches.sum()),
        grid_batches=gb,
        flux_batches=flux_batches,
        rays_per_batch=list(rays_per_batch),
        n_batches=n_batches,
    )
    return SimulationResult(
        detectors={"det0": det},
        total_emitted_flux=total_emitted_flux,
        escaped_flux=total_emitted_flux * 0.1,
        source_count=1,
    )


def _legacy_result(ny: int = 8, nx: int = 8) -> SimulationResult:
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


def _dummy_project() -> Project:
    return Project(name="test_project", settings=SimulationSettings())


# ---------------------------------------------------------------------------
# HTML report — CI strings and errorbar chart
# ---------------------------------------------------------------------------


def test_report_html_contains_ci_strings(tmp_path):
    from backlight_sim.io.report import generate_html_report

    project = _dummy_project()
    result = _uq_result(n_batches=10, add_variance=True)
    out = tmp_path / "report.html"
    generate_html_report(project, result, out)
    html = out.read_text(encoding="utf-8")
    # At least 3 ± tokens (avg, peak, efficiency rows minimum).
    assert html.count("±") >= 3, (
        f"Expected >= 3 ± tokens in report HTML, got {html.count('±')}"
    )


def test_report_html_legacy_no_ci(tmp_path):
    from backlight_sim.io.report import generate_html_report

    project = _dummy_project()
    result = _legacy_result()
    out = tmp_path / "report_legacy.html"
    generate_html_report(project, result, out)
    html = out.read_text(encoding="utf-8")
    assert "±" not in html, "Legacy report must not contain ± tokens"


def test_report_embeds_errorbar_chart(tmp_path):
    from backlight_sim.io.report import generate_html_report

    project = _dummy_project()
    result = _uq_result(n_batches=10, add_variance=True)
    out = tmp_path / "report_err.html"
    generate_html_report(project, result, out)
    html = out.read_text(encoding="utf-8")
    # Expect at least 2 <img tags: heatmap + errorbar chart.
    img_count = html.count("<img")
    assert img_count >= 2, (
        f"Expected >= 2 <img tags (heatmap + errorbar), got {img_count}"
    )


def test_report_matplotlib_missing_graceful(tmp_path, monkeypatch):
    """Report must still render when matplotlib is unavailable."""
    from backlight_sim.io import report as report_mod

    project = _dummy_project()
    result = _uq_result(n_batches=10, add_variance=True)
    out = tmp_path / "report_no_mpl.html"

    # Block matplotlib imports by clearing the cached module and making
    # future imports raise ImportError.
    for mod_name in list(sys.modules):
        if mod_name == "matplotlib" or mod_name.startswith("matplotlib."):
            monkeypatch.delitem(sys.modules, mod_name, raising=False)

    import builtins
    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "matplotlib" or name.startswith("matplotlib"):
            raise ImportError(f"simulated: no {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    report_mod.generate_html_report(project, result, out)
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert "matplotlib not available" in html or "<h1>" in html


# ---------------------------------------------------------------------------
# Batch export ZIP — CI columns in KPI CSV
# ---------------------------------------------------------------------------


def test_batch_export_csv_has_ci_columns(tmp_path):
    from backlight_sim.io.batch_export import export_batch_zip

    project = _dummy_project()
    result = _uq_result(n_batches=10, add_variance=True)
    out = tmp_path / "batch.zip"
    export_batch_zip(project, result, out)
    assert out.exists()
    with zipfile.ZipFile(out) as zf:
        with zf.open("kpi.csv") as fh:
            content = fh.read().decode("utf-8")
    header_line = content.splitlines()[0].lower()
    for col in ("mean", "half_width", "std", "lower", "upper", "n_batches", "conf_level"):
        assert col in header_line, (
            f"Missing CI column '{col}' in batch zip kpi.csv header: {header_line}"
        )


def test_batch_export_csv_legacy_has_ci_columns(tmp_path):
    """Legacy (UQ-off) batch export must still ship the CI column schema —
    rows have empty CI cells but the columns are present (backwards-compat
    for external consumers)."""
    from backlight_sim.io.batch_export import export_batch_zip

    project = _dummy_project()
    result = _legacy_result()
    out = tmp_path / "batch_legacy.zip"
    export_batch_zip(project, result, out)
    with zipfile.ZipFile(out) as zf:
        with zf.open("kpi.csv") as fh:
            content = fh.read().decode("utf-8")
    header_line = content.splitlines()[0].lower()
    for col in ("mean", "half_width", "n_batches"):
        assert col in header_line


# ---------------------------------------------------------------------------
# compute_all_kpi_cis rays_per_batch-aware scaling (threat T-04.03-05)
# ---------------------------------------------------------------------------


def test_compute_all_kpi_cis_uses_rays_per_batch():
    from backlight_sim.core.kpi import compute_all_kpi_cis

    # Uneven split with flux proportional to rays_per_batch — per-batch
    # efficiency is identical so half_width ~ 0 ONLY when rays_per_batch
    # scaling is used.  A naive total/K scaling would inflate half_width.
    gb = np.ones((10, 5, 5))
    result = SimulationResult(
        detectors={
            "d": DetectorResult(
                detector_name="d",
                grid=gb.sum(axis=0) / 10,
                total_hits=1010,
                total_flux=505.0,
                grid_batches=gb,
                flux_batches=np.asarray([50.5] * 8 + [50.0] * 2),
                rays_per_batch=[101] * 8 + [100] * 2,
                n_batches=10,
            )
        },
        total_emitted_flux=1010.0,
        source_count=1,
    )
    cis = compute_all_kpi_cis(result, conf_level=0.95)
    eff_ci = cis["efficiency_pct"]
    assert eff_ci is not None
    assert eff_ci.half_width < 1e-6, (
        f"Efficiency half_width {eff_ci.half_width} > 0 indicates naive "
        "1010/10 scaling used instead of rays_per_batch-aware scaling."
    )


# ---------------------------------------------------------------------------
# End-to-end smoke test: Simple Box preset → CSV + HTML + batch ZIP
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_end_to_end_uq_smoke(tmp_path, monkeypatch):
    """Run tracer on Simple Box preset with UQ on and verify all three export
    surfaces carry CI evidence."""
    from backlight_sim.io.presets import preset_simple_box
    from backlight_sim.sim.tracer import RayTracer
    from backlight_sim.io.report import generate_html_report
    from backlight_sim.io.batch_export import export_batch_zip
    from backlight_sim.gui.heatmap_panel import HeatmapPanel
    from PySide6.QtWidgets import QApplication, QFileDialog

    app = QApplication.instance() or QApplication([])

    project = preset_simple_box()
    project.settings.rays_per_source = 2000
    project.settings.uq_batches = 10
    project.settings.random_seed = 42

    result = RayTracer(project).run()

    # (a) KPI CSV via HeatmapPanel._export_kpi_csv
    panel = HeatmapPanel()
    panel.set_project(project)
    panel.update_results(result)
    csv_path = tmp_path / "kpi.csv"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName",
        classmethod(lambda cls, *a, **kw: (str(csv_path), "")),
    )
    panel._export_kpi_csv()
    assert csv_path.exists()
    with csv_path.open("r", newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    header = [c.lower() for c in rows[0]]
    assert "half_width" in header
    # At least one row must have a non-empty half_width cell.
    hw_idx = header.index("half_width")
    assert any(row[hw_idx].strip() for row in rows[1:])

    # (b) HTML report
    html_path = tmp_path / "report.html"
    generate_html_report(project, result, html_path)
    html = html_path.read_text(encoding="utf-8")
    assert "±" in html

    # (c) Batch ZIP
    zip_path = tmp_path / "batch.zip"
    export_batch_zip(project, result, zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert "kpi.csv" in names
        with zf.open("kpi.csv") as fh:
            content = fh.read().decode("utf-8")
    assert "half_width" in content.lower()
