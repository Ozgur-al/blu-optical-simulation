"""Parity tests for core/kpi.py and back-compat / extension tests for
DetectorResult, SimulationResult, SimulationSettings (Phase 4, Wave 1).

The "old" KPI helper bodies are replicated inline here as
``_old_<name>`` so the parity assertions are independent of which module
currently owns the canonical implementation.  After the lift, the copies in
``gui/heatmap_panel.py`` and ``gui/parameter_sweep_dialog.py`` are gone —
these inline copies remain the reference.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import numpy as np
import pytest

from backlight_sim.core.detectors import DetectorResult, SimulationResult
from backlight_sim.core.kpi import (
    compute_scalar_kpis,
    corner_ratio,
    edge_center_ratio,
    uniformity_in_center,
)
from backlight_sim.core.project_model import Project, SimulationSettings


# ---------------------------------------------------------------------------
# Reference (pre-lift) implementations — kept locally so the parity assertion
# does not depend on whichever module currently owns the canonical copy.
# ---------------------------------------------------------------------------

def _old_uniformity_in_center(grid: np.ndarray, fraction: float) -> tuple[float, float]:
    ny, nx = grid.shape
    f_side = float(np.sqrt(fraction))
    cy, cx = ny // 2, nx // 2
    half_y = max(1, int(ny * f_side / 2))
    half_x = max(1, int(nx * f_side / 2))
    roi = grid[cy - half_y: cy + half_y, cx - half_x: cx + half_x]
    if roi.size == 0 or roi.max() == 0:
        return 0.0, 0.0
    avg = float(roi.mean())
    mn = float(roi.min())
    mx = float(roi.max())
    return (mn / avg if avg > 0 else 0.0, mn / mx if mx > 0 else 0.0)


def _old_corner_ratio(grid: np.ndarray, corner_frac: float = 0.1) -> float:
    ny, nx = grid.shape
    ch = max(1, int(ny * corner_frac))
    cw = max(1, int(nx * corner_frac))
    corners = np.concatenate([
        grid[:ch, :cw].ravel(),
        grid[:ch, -cw:].ravel(),
        grid[-ch:, :cw].ravel(),
        grid[-ch:, -cw:].ravel(),
    ])
    full_avg = float(grid.mean())
    corner_avg = float(corners.mean())
    return corner_avg / full_avg if full_avg > 0 else 0.0


def _old_edge_center_ratio(grid: np.ndarray) -> float:
    ny, nx = grid.shape
    cy, cx = ny // 2, nx // 2
    half_y = max(1, int(ny * 0.25))
    half_x = max(1, int(nx * 0.25))
    center = grid[cy - half_y: cy + half_y, cx - half_x: cx + half_x]

    ey = max(1, int(ny * 0.15))
    ex = max(1, int(nx * 0.15))
    edge_mask = np.zeros(grid.shape, dtype=bool)
    edge_mask[:ey, :] = True
    edge_mask[-ey:, :] = True
    edge_mask[:, :ex] = True
    edge_mask[:, -ex:] = True
    edge = grid[edge_mask]

    center_avg = float(center.mean()) if center.size > 0 else 0.0
    edge_avg = float(edge.mean()) if edge.size > 0 else 0.0
    if center_avg == 0:
        return 0.0
    return edge_avg / center_avg


def _old_kpis_tuple(result: SimulationResult) -> tuple[float, float, float]:
    """Reference tuple returned by the old gui/parameter_sweep_dialog::_kpis."""
    if not result.detectors:
        return 0.0, 0.0, 0.0
    grid = next(iter(result.detectors.values())).grid
    avg = float(grid.mean())
    if result.total_emitted_flux > 0:
        det_total = sum(dr.total_flux for dr in result.detectors.values())
        eff = det_total / result.total_emitted_flux * 100.0
    else:
        eff = 0.0
    u14, _ = _old_uniformity_in_center(grid, 0.25)
    hot = float(grid.max()) / avg if avg > 0 else 0.0
    return eff, u14, hot


# ---------------------------------------------------------------------------
# Fixture: random fixed-seed grids of various sizes
# ---------------------------------------------------------------------------

def _fixture_grids() -> list[np.ndarray]:
    rng = np.random.default_rng(12345)
    shapes = [(50, 50), (100, 100), (37, 73), (10, 10), (20, 30)] * 2
    return [rng.random(sh) * 1000.0 for sh in shapes]


# ---------------------------------------------------------------------------
# KPI parity tests
# ---------------------------------------------------------------------------

def test_uniformity_in_center_parity():
    for grid in _fixture_grids():
        for frac in (0.25, 1 / 6, 0.10):
            got = uniformity_in_center(grid, frac)
            expected = _old_uniformity_in_center(grid, frac)
            assert got == expected, (
                f"mismatch on shape={grid.shape} frac={frac}: {got} vs {expected}"
            )


def test_corner_ratio_parity():
    for grid in _fixture_grids():
        for cf in (0.1, 0.2, 0.05):
            got = corner_ratio(grid, cf)
            expected = _old_corner_ratio(grid, cf)
            assert got == expected, (
                f"mismatch on shape={grid.shape} cf={cf}: {got} vs {expected}"
            )


def test_edge_center_ratio_parity():
    for grid in _fixture_grids():
        got = edge_center_ratio(grid)
        expected = _old_edge_center_ratio(grid)
        assert got == expected, f"mismatch on shape={grid.shape}: {got} vs {expected}"


def _make_result(grid: np.ndarray, total_emitted: float = 1000.0) -> SimulationResult:
    det = DetectorResult(
        detector_name="d",
        grid=grid,
        total_hits=int(grid.sum() / max(grid.mean(), 1e-9)),
        total_flux=float(grid.sum()),
    )
    r = SimulationResult(detectors={"d": det})
    r.total_emitted_flux = total_emitted
    r.source_count = 1
    return r


def test_compute_scalar_kpis_keys_and_parity():
    grid = np.random.default_rng(42).random((50, 50)) * 100.0
    result = _make_result(grid, total_emitted=1000.0)

    k = compute_scalar_kpis(result)
    assert set(k) >= {"efficiency_pct", "uniformity_1_4_min_avg", "hotspot_peak_avg"}

    eff_old, u14_old, hot_old = _old_kpis_tuple(result)
    assert k["efficiency_pct"] == pytest.approx(eff_old, rel=0, abs=0)
    assert k["uniformity_1_4_min_avg"] == pytest.approx(u14_old, rel=0, abs=0)
    assert k["hotspot_peak_avg"] == pytest.approx(hot_old, rel=0, abs=0)


def test_compute_scalar_kpis_no_detectors_returns_zeros():
    r = SimulationResult()
    k = compute_scalar_kpis(r)
    assert k["efficiency_pct"] == 0.0
    assert k["uniformity_1_4_min_avg"] == 0.0
    assert k["hotspot_peak_avg"] == 0.0


# ---------------------------------------------------------------------------
# DetectorResult extension / back-compat
# ---------------------------------------------------------------------------

def test_detector_result_legacy_construction_unchanged():
    d = DetectorResult(detector_name="x", grid=np.zeros((10, 10)))
    assert d.total_hits == 0
    assert d.total_flux == 0.0
    assert d.grid_rgb is None
    assert d.grid_spectral is None
    # New fields default to None / 0
    assert d.grid_batches is None
    assert d.hits_batches is None
    assert d.flux_batches is None
    assert d.grid_spectral_batches is None
    assert d.rays_per_batch is None
    assert d.n_batches == 0


def test_detector_result_accepts_uq_kwargs():
    K = 4
    gb = np.zeros((K, 3, 3))
    hb = np.zeros(K, dtype=int)
    fb = np.zeros(K, dtype=float)
    sb = np.zeros((K, 3, 3, 7), dtype=float)
    d = DetectorResult(
        detector_name="x",
        grid=np.zeros((3, 3)),
        grid_batches=gb,
        hits_batches=hb,
        flux_batches=fb,
        grid_spectral_batches=sb,
        rays_per_batch=[100, 100, 100, 100],
        n_batches=K,
    )
    assert d.n_batches == K
    assert d.grid_batches is gb
    assert d.hits_batches is hb
    assert d.flux_batches is fb
    assert d.grid_spectral_batches is sb
    assert d.rays_per_batch == [100, 100, 100, 100]


def test_detector_result_rays_per_batch_field():
    d = DetectorResult("x", np.zeros((3, 3)))
    assert d.rays_per_batch is None
    d2 = DetectorResult(
        "x",
        np.zeros((3, 3)),
        rays_per_batch=[100, 100, 100, 100],
        n_batches=4,
    )
    assert d2.rays_per_batch == [100, 100, 100, 100]


# ---------------------------------------------------------------------------
# SimulationResult.uq_warnings extension
# ---------------------------------------------------------------------------

def test_simulation_result_uq_warnings_default_empty():
    r = SimulationResult()
    assert r.uq_warnings == []


def test_simulation_result_uq_warnings_not_shared_mutable():
    r1 = SimulationResult()
    r2 = SimulationResult()
    r1.uq_warnings.append("test")
    assert r2.uq_warnings == [], (
        "factory default must produce distinct list per instance"
    )


def test_simulation_result_uq_warnings_accepts_kwarg():
    r = SimulationResult(uq_warnings=["adaptive sampling may bias CI"])
    assert r.uq_warnings == ["adaptive sampling may bias CI"]


# ---------------------------------------------------------------------------
# SimulationSettings extension / back-compat
# ---------------------------------------------------------------------------

def test_simulation_settings_uq_defaults():
    s = SimulationSettings()
    assert s.uq_batches == 10
    assert s.uq_include_spectral is True


def test_load_project_without_uq_fields_uses_defaults():
    """Loading a legacy JSON without uq_* keys must not crash."""
    from backlight_sim.io.project_io import load_project, save_project

    legacy_project = Project(name="legacy")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "legacy.json"
        save_project(legacy_project, path)

        # Ensure legacy JSON does NOT contain uq_* keys — simulates an old save.
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("settings", {}).pop("uq_batches", None)
        data["settings"].pop("uq_include_spectral", None)
        path.write_text(json.dumps(data), encoding="utf-8")

        loaded = load_project(path)
        assert loaded.settings.uq_batches == 10
        assert loaded.settings.uq_include_spectral is True


# ---------------------------------------------------------------------------
# Layering: core/kpi.py must not pull in PySide6/pyqtgraph/gui
# ---------------------------------------------------------------------------

def test_core_kpi_has_no_gui_imports():
    code = textwrap.dedent(
        """
        import sys, backlight_sim.core.kpi  # noqa
        forbidden = {m for m in sys.modules
                     if m.startswith(("PySide6", "pyqtgraph", "backlight_sim.gui"))}
        assert not forbidden, f"core.kpi leaked imports: {sorted(forbidden)}"
        """
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------------------
# GUI rewiring checks: duplicate definitions removed
# ---------------------------------------------------------------------------

_HEATMAP_PATH = (
    Path(__file__).resolve().parent.parent / "gui" / "heatmap_panel.py"
)
_SWEEP_PATH = (
    Path(__file__).resolve().parent.parent / "gui" / "parameter_sweep_dialog.py"
)


def test_heatmap_panel_no_longer_defines_kpi_helpers():
    src = _HEATMAP_PATH.read_text(encoding="utf-8")
    # Module-level `def` lines (not indented); tolerate optional trailing parens.
    for name in ("_uniformity_in_center", "_corner_ratio", "_edge_center_ratio"):
        assert f"\ndef {name}(" not in src, (
            f"gui/heatmap_panel.py still defines {name} — should be imported "
            f"from core.kpi instead"
        )


def test_heatmap_panel_imports_from_core_kpi():
    src = _HEATMAP_PATH.read_text(encoding="utf-8")
    assert "from backlight_sim.core.kpi import" in src


def test_parameter_sweep_no_longer_defines_kpis():
    src = _SWEEP_PATH.read_text(encoding="utf-8")
    assert "\ndef _kpis(" not in src


def test_parameter_sweep_imports_from_core_kpi():
    src = _SWEEP_PATH.read_text(encoding="utf-8")
    assert "from backlight_sim.core.kpi import" in src
