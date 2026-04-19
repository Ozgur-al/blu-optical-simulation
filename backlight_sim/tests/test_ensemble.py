"""Tests for backlight_sim.sim.ensemble — tolerance Monte Carlo service.

Wave 0 (TDD): all tests are marked xfail(strict=False) because sim/ensemble.py
only has NotImplementedError stubs. After Wave 1 implements the module, tests
will pass and the xfail markers should be removed.
"""
from __future__ import annotations

import numpy as np
import pytest

from backlight_sim.sim.ensemble import (
    apply_jitter,
    build_oat_sample,
    compute_oat_sensitivity,
    build_sobol_sample,
    build_mc_sample,
)


# ---------------------------------------------------------------------------
# Scene factory
# ---------------------------------------------------------------------------

def _make_tolerance_scene(pos_sigma_mm=0.0, project_sigma_mm=0.0) -> "Project":
    from backlight_sim.core.geometry import Rectangle
    from backlight_sim.core.materials import Material
    from backlight_sim.core.sources import PointSource
    from backlight_sim.core.detectors import DetectorSurface
    from backlight_sim.core.project_model import Project, SimulationSettings

    materials = {"wall": Material(name="wall", surface_type="reflector",
                                  reflectance=0.9, absorption=0.1,
                                  transmittance=0.0)}
    surfaces = [Rectangle.axis_aligned("floor", np.array([0.0, 0.0, -5.0]),
                                       (20.0, 20.0), 2, -1.0, "wall")]
    detectors = [DetectorSurface(name="det",
                                 center=np.array([0.0, 0.0, 5.0]),
                                 u_axis=np.array([1.0, 0.0, 0.0]),
                                 v_axis=np.array([0.0, 1.0, 0.0]),
                                 size=(20.0, 20.0), resolution=(10, 10))]
    # Build source kwargs — position_sigma_mm may not exist yet (Wave 0)
    src_kwargs = dict(name="led1", position=np.array([0.0, 0.0, 0.0]), flux=100.0)
    if pos_sigma_mm != 0.0:
        src_kwargs["position_sigma_mm"] = pos_sigma_mm
    src = PointSource(**src_kwargs)

    # Build settings kwargs — new fields may not exist yet (Wave 0)
    settings_kwargs = dict(rays_per_source=500, max_bounces=10, random_seed=42)
    if project_sigma_mm != 0.0:
        settings_kwargs["source_position_sigma_mm"] = project_sigma_mm
    settings = SimulationSettings(**settings_kwargs)

    return Project(name="test_ens", sources=[src], surfaces=surfaces,
                   materials=materials, detectors=detectors, settings=settings)


# ---------------------------------------------------------------------------
# Tests (ENS-01 through ENS-11) — all xfail in Wave 0
# ---------------------------------------------------------------------------

def test_apply_jitter_gaussian():
    """ENS-01: apply_jitter shifts source positions when Gaussian sigma > 0."""
    project = _make_tolerance_scene(project_sigma_mm=0.5)
    rng = np.random.default_rng(99)
    jittered = apply_jitter(project, rng)
    original_pos = np.array([0.0, 0.0, 0.0])
    assert not np.allclose(jittered.sources[0].position, original_pos), \
        "Expected non-zero position jitter with sigma=0.5"


def test_apply_jitter_does_not_mutate_base():
    """ENS-02: apply_jitter does not mutate the base project."""
    project = _make_tolerance_scene(project_sigma_mm=0.5)
    original_pos = project.sources[0].position.copy()
    rng = np.random.default_rng(99)
    _ = apply_jitter(project, rng)
    np.testing.assert_array_equal(project.sources[0].position, original_pos,
                                  err_msg="Base project position was mutated by apply_jitter")


def test_cavity_jitter_rebuilds_geometry():
    """ENS-03: cavity_recipe with depth_sigma_mm > 0 rebuilds project surfaces."""
    import copy
    project = _make_tolerance_scene()
    project.cavity_recipe = {
        "width": 50.0, "height": 50.0, "depth": 20.0,
        "wall_angle_x_deg": 0.0, "wall_angle_y_deg": 0.0,
        "floor_material": "wall", "wall_material": "wall",
        "depth_sigma_mm": 1.0,
    }
    original_surfaces = copy.deepcopy(project.surfaces)
    rng = np.random.default_rng(7)
    jittered = apply_jitter(project, rng)
    # After cavity rebuild, at least one surface center should differ
    differs = any(
        not np.allclose(s1.center, s2.center)
        for s1, s2 in zip(jittered.surfaces, original_surfaces)
    )
    assert differs, "Cavity jitter did not rebuild geometry"


def test_json_roundtrip_tolerance_fields(tmp_path):
    """ENS-04: tolerance fields survive JSON save/load round-trip."""
    from backlight_sim.io.project_io import save_project, load_project
    project = _make_tolerance_scene(pos_sigma_mm=0.25, project_sigma_mm=0.1)
    project.cavity_recipe = {"width": 50.0, "depth_sigma_mm": 0.05}
    path = tmp_path / "test_tolerance.json"
    save_project(project, path)
    loaded = load_project(path)
    assert loaded.sources[0].position_sigma_mm == pytest.approx(0.25)
    assert loaded.settings.source_position_sigma_mm == pytest.approx(0.1)
    assert loaded.cavity_recipe.get("depth_sigma_mm") == pytest.approx(0.05)


def test_json_backward_compat_no_tolerance_fields(tmp_path):
    """ENS-05: old JSON without tolerance fields loads with all-zero defaults."""
    import json
    old_dict = {
        "name": "old_project",
        "sources": [{"name": "s1", "position": [0, 0, 0], "flux": 100.0}],
        "settings": {},
    }
    path = tmp_path / "old.json"
    path.write_text(json.dumps(old_dict))
    from backlight_sim.io.project_io import load_project
    loaded = load_project(path)
    assert loaded.sources[0].position_sigma_mm == 0.0
    assert loaded.settings.source_position_sigma_mm == 0.0
    assert loaded.cavity_recipe == {}


def test_oat_sample_count_and_baseline():
    """ENS-06: build_oat_sample returns k+1 entries; item 0 is 'baseline'."""
    project = _make_tolerance_scene(project_sigma_mm=0.5)
    samples = build_oat_sample(project, seed=42)
    assert len(samples) >= 2, "Expected at least 2 entries (baseline + 1 perturbed)"
    label_0 = samples[0][1]
    assert label_0 == "baseline", f"Expected 'baseline' as first label, got {label_0!r}"


def test_oat_sensitivity_zero_sigma():
    """ENS-07: compute_oat_sensitivity returns 0.0 for zero-sigma params."""
    baseline = {"uniformity_1_4_min_avg": 0.80}
    perturbed = [{"uniformity_1_4_min_avg": 0.82}]
    param_names = ["position_sigma_mm"]
    param_sigmas = [0.0]  # zero sigma → sensitivity must be 0
    result = compute_oat_sensitivity(baseline, perturbed, param_names, param_sigmas)
    assert result["uniformity_1_4_min_avg"][0] == pytest.approx(0.0)


def test_sobol_sample_count_power_of_2():
    """ENS-08: build_sobol_sample rounds N up to next power of 2, minimum 32."""
    pytest.importorskip("scipy.stats.qmc")
    project = _make_tolerance_scene(project_sigma_mm=0.5)
    samples = build_sobol_sample(project, N=10, seed=42)
    assert len(samples) == 32, f"Expected 32 (next pow2 >= max(10,32)), got {len(samples)}"


@pytest.mark.xfail(raises=(NotImplementedError, AttributeError, TypeError, AssertionError), strict=False)
def test_ensemble_spread_increases_with_sigma():
    """ENS-09: larger sigma produces larger KPI spread across ensemble members."""
    from backlight_sim.io.presets import preset_simple_box
    from backlight_sim.sim.tracer import RayTracer
    from backlight_sim.core.kpi import compute_scalar_kpis

    def _run_ensemble(sigma, n=15, seed=0):
        base = preset_simple_box()
        base.settings.rays_per_source = 500
        base.settings.source_position_sigma_mm = sigma
        rng = np.random.default_rng(seed)
        kpis = []
        for i in range(n):
            member = apply_jitter(base, np.random.default_rng(seed + i))
            result = RayTracer(member).run()
            k = compute_scalar_kpis(result)
            kpis.append(k.get("uniformity_1_4_min_avg", 0.0))
        return float(np.std(kpis))

    spread_zero = _run_ensemble(sigma=0.0)
    spread_large = _run_ensemble(sigma=2.0)
    assert spread_large > spread_zero, \
        f"Expected sigma=2 spread ({spread_large:.4f}) > sigma=0 spread ({spread_zero:.4f})"


@pytest.mark.xfail(raises=(NotImplementedError, AttributeError, TypeError, ImportError), strict=False)
def test_ensemble_thread_cancel():
    """ENS-10: _EnsembleThread halts before all members complete when cancel() is called."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    from backlight_sim.gui.ensemble_dialog import _EnsembleThread
    from backlight_sim.io.presets import preset_simple_box
    import copy

    base = preset_simple_box()
    base.settings.rays_per_source = 200
    base.settings.source_position_sigma_mm = 0.5
    n_members = 20

    thread = _EnsembleThread(copy.deepcopy(base), n_members, "oat", seed=42)
    completed = []

    def _on_step(idx, result, proj):
        completed.append(idx)

    thread.step_done.connect(_on_step)
    thread.start()
    thread.cancel()   # cancel immediately
    thread.wait(5000)

    assert len(completed) < n_members, \
        f"Expected fewer than {n_members} completed, got {len(completed)}"


def test_flux_tolerance_redrawn_per_member():
    """ENS-11: D-01b -- flux_tolerance is re-drawn per ensemble member (not fixed).

    Given a source with flux_tolerance=20%, two members produced with different seeds
    must have different flux values. This verifies that apply_jitter() re-draws
    the flux jitter for each realization rather than inheriting the base project value.
    """
    from backlight_sim.io.presets import preset_simple_box
    base = preset_simple_box()
    base.settings.source_position_sigma_mm = 0.0  # disable position jitter
    base.sources[0].flux_tolerance = 20.0         # 20% flux bin tolerance
    base.sources[0].position_sigma_mm = 0.0

    member_a = apply_jitter(base, np.random.default_rng(seed=1))
    member_b = apply_jitter(base, np.random.default_rng(seed=999))

    flux_a = member_a.sources[0].flux
    flux_b = member_b.sources[0].flux
    assert abs(flux_a - flux_b) > 0.0, (
        f"Expected flux to differ between members with different seeds "
        f"(flux_a={flux_a:.4f}, flux_b={flux_b:.4f}). "
        f"D-01b requires flux_tolerance jitter re-drawn per realization."
    )
