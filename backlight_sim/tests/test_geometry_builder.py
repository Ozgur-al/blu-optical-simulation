"""Direct-lit geometry builder: core layout logic + dialog smoke tests."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

from backlight_sim.core.materials import Material
from backlight_sim.core.project_model import Project
from backlight_sim.io.geometry_builder import (
    _grid_positions, build_cavity, build_led_grid, build_optical_stack,
)


def test_pitch_grid_is_centred():
    # 120 mm plate, 10 mm takeoff, 30 mm pitch: 4 LEDs fit, leftover split evenly.
    assert _grid_positions(-60, 60, 30, 10) == pytest.approx([-45, -15, 15, 45])
    assert _grid_positions(-60, 60, 25, 10) == pytest.approx([-50, -25, 0, 25, 50])
    assert _grid_positions(-10, 10, 30, 11) == []


def test_led_grid_pitch_mode_symmetric():
    p = Project()
    build_led_grid(p, 100, 60, 30, 30, 10, 10, 1.0, "lambertian")
    xs = np.array(sorted({s.position[0] for s in p.sources}))
    ys = np.array(sorted({s.position[1] for s in p.sources}))
    assert xs.mean() == pytest.approx(0.0)
    assert ys.mean() == pytest.approx(0.0)


def test_cavity_without_walls_builds_plate_only():
    p = Project()
    build_cavity(p, 100, 60, 10, wall_angle_x_deg=5.0, walls=False, record_recipe=True)
    assert [s.name for s in p.surfaces] == ["Floor"]
    assert p.cavity_recipe["walls"] is False


def test_films_default_to_transmissive_material():
    p = Project()
    build_optical_stack(p, 100, 60, 10, diffuser_distance=8.0, film_distances=[5.0],
                        diffuser_material="diff")
    film = next(s for s in p.surfaces if s.name == "Film_1")
    assert film.material_name == "diff"


def test_ensemble_rebuild_keeps_stack_and_moves_output_plane():
    from backlight_sim.core.detectors import DetectorSurface
    from backlight_sim.sim.ensemble import _jitter_cavity

    p = Project()
    p.materials["diff"] = Material("diff", "diffuser", transmittance=0.7)
    build_cavity(p, 100, 60, 10, wall_angle_x_deg=10.0, record_recipe=True)
    build_optical_stack(p, 100, 60, 10, diffuser_distance=8.0, diffuser_material="diff",
                        wall_angle_x_deg=10.0)
    tan = np.tan(np.radians(10.0))
    p.detectors.append(DetectorSurface.axis_aligned(
        "Output Plane", [0, 0, 10.0], (100 + 20 * tan, 60), 2, 1.0, (10, 10)))

    _jitter_cavity(p, None, overrides={"depth_sigma_mm": 2.0}, prescribed_only=True)

    assert "Diffuser" in [s.name for s in p.surfaces]
    det = p.detectors[0]
    assert det.center[2] == pytest.approx(12.0)
    assert det.size[0] == pytest.approx(100 + 24 * tan)


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def dialog(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from backlight_sim.gui.geometry_builder import GeometryBuilderDialog

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    dlg = GeometryBuilderDialog(Project())
    yield dlg
    dlg.deleteLater()


def test_dialog_preview_matches_builder_for_single_led(dialog):
    dialog._use_count.setChecked(True)
    dialog._count_x.setValue(3)
    dialog._count_y.setValue(1)
    dialog._preview_count()
    assert "LED count: 3 " in dialog._count_lbl.text()


def test_dialog_active_area_mode_builds_plate_and_detector(dialog):
    d = dialog
    d._size_mode.setCurrentIndex(1)
    d._aa_w.setValue(100.0)
    d._aa_h.setValue(50.0)
    d._margin_x.setValue(4.0)
    d._margin_y.setValue(3.0)
    assert d._cav_w.value() == pytest.approx(108.0)
    assert d._cav_h.value() == pytest.approx(56.0)
    assert d._use_count.isChecked()

    d._count_x.setValue(4)
    d._count_y.setValue(2)
    d._edge_x.setValue(9.0)
    d._edge_y.setValue(8.0)
    d._walls.setChecked(False)
    d._diff_dist.setValue(6.0)
    d._led_flux.setValue(800.0)
    d._flux_mode.setCurrentIndex(1)  # total flux, split evenly
    d._preview_count()
    assert "OD/pitch" in d._count_lbl.text()

    d._on_accept()
    p = d.built_project()
    assert [s.name for s in p.surfaces] == ["Floor", "Diffuser"]
    assert p.surfaces[0].size == pytest.approx((108.0, 56.0))
    assert len(p.sources) == 8
    assert all(s.flux == pytest.approx(100.0) for s in p.sources)
    xs = sorted({s.position[0] for s in p.sources})
    assert xs[0] == pytest.approx(-54.0 + 9.0)
    assert p.detectors[0].size == pytest.approx((100.0, 50.0))
    # Default emitting surface = whole LED top face (3 x 3 package).
    assert all(src.emitter_size == (3.0, 3.0) for src in p.sources)


def test_dialog_custom_emitting_area(dialog):
    dialog._emit_mode.setCurrentIndex(1)
    dialog._emit_x.setValue(1.2)
    dialog._emit_y.setValue(0.6)
    dialog._on_accept()
    assert {s.emitter_size for s in dialog.built_project().sources} == {(1.2, 0.6)}


def test_dialog_blocks_diffuser_above_detector(dialog):
    dialog._cav_d.setValue(10.0)
    dialog._diff_dist.setValue(12.0)
    dialog._on_accept()
    assert dialog.result() == 0  # stayed open
    assert dialog.built_project().surfaces == []
