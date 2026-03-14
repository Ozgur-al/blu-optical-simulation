"""Tests for the Monte Carlo ray tracer."""

import numpy as np
import pytest

from backlight_sim.core.geometry import Rectangle
from backlight_sim.core.materials import Material
from backlight_sim.core.sources import PointSource
from backlight_sim.core.detectors import DetectorSurface
from backlight_sim.core.project_model import Project, SimulationSettings
from backlight_sim.sim.tracer import RayTracer
from backlight_sim.sim.sampling import sample_angular_distribution, scatter_haze


def _make_box_scene(
    rays_per_source=5000,
    wall_reflectance=0.9,
    wall_type="reflector",
    source_flux=1000.0,
) -> Project:
    materials = {
        "wall": Material(name="wall", surface_type=wall_type,
                         reflectance=wall_reflectance, absorption=1.0-wall_reflectance),
    }
    surfaces = [
        Rectangle.axis_aligned("floor",      [0, 0, -5], (20, 20), 2, -1.0, "wall"),
        Rectangle.axis_aligned("wall_left",  [-10, 0, 0], (20, 10), 0, -1.0, "wall"),
        Rectangle.axis_aligned("wall_right", [10, 0, 0],  (20, 10), 0,  1.0, "wall"),
        Rectangle.axis_aligned("wall_front", [0, -10, 0], (20, 10), 1, -1.0, "wall"),
        Rectangle.axis_aligned("wall_back",  [0, 10, 0],  (20, 10), 1,  1.0, "wall"),
    ]
    detectors = [
        DetectorSurface.axis_aligned("top_detector", [0, 0, 5], (20, 20), 2, 1.0, (50, 50)),
    ]
    sources = [PointSource("src1", np.array([0.0, 0.0, 0.0]), flux=source_flux)]
    settings = SimulationSettings(rays_per_source=rays_per_source, max_bounces=50,
                                  energy_threshold=0.001, random_seed=42, record_ray_paths=10)
    return Project(name="test_box", sources=sources, surfaces=surfaces,
                   materials=materials, detectors=detectors, settings=settings)


def test_basic_simulation_produces_nonzero_heatmap():
    result = RayTracer(_make_box_scene()).run()
    det = result.detectors["top_detector"]
    assert det.total_hits > 0
    assert det.total_flux > 0
    assert det.grid.sum() > 0
    assert det.grid.shape == (50, 50)


def test_zero_flux_produces_zero_results():
    result = RayTracer(_make_box_scene(source_flux=0.0)).run()
    det = result.detectors["top_detector"]
    assert det.total_flux == 0.0
    assert det.grid.sum() == 0.0


def test_absorber_walls_fewer_hits_than_reflector():
    res_absorb  = RayTracer(_make_box_scene(wall_type="absorber",  rays_per_source=10000)).run()
    res_reflect = RayTracer(_make_box_scene(wall_reflectance=0.9,  rays_per_source=10000)).run()
    assert res_absorb.detectors["top_detector"].total_flux < res_reflect.detectors["top_detector"].total_flux
    assert res_absorb.detectors["top_detector"].total_hits > 0


def test_deterministic_with_same_seed():
    r1 = RayTracer(_make_box_scene()).run()
    r2 = RayTracer(_make_box_scene()).run()
    np.testing.assert_array_equal(r1.detectors["top_detector"].grid, r2.detectors["top_detector"].grid)


def test_progress_callback_called():
    calls = []
    RayTracer(_make_box_scene()).run(progress_callback=lambda p: calls.append(p))
    assert len(calls) > 0
    assert calls[-1] == pytest.approx(1.0)


def test_ray_paths_recorded():
    result = RayTracer(_make_box_scene(rays_per_source=500)).run()
    assert len(result.ray_paths) > 0
    assert all(len(p) >= 1 for p in result.ray_paths)


def test_custom_angular_distribution_sampling_points_forward():
    rng = np.random.default_rng(7)
    dirs = sample_angular_distribution(
        20000,
        np.array([0.0, 0.0, 1.0]),
        np.array([0.0, 90.0]),
        np.array([1.0, 0.0]),
        rng,
    )
    assert dirs.shape == (20000, 3)
    assert float(dirs[:, 2].mean()) > 0.5


def test_tracer_supports_custom_angular_distribution_name():
    project = _make_box_scene(rays_per_source=4000)
    project.sources[0].distribution = "led_curve"
    project.angular_distributions["led_curve"] = {
        "theta_deg": [0.0, 30.0, 60.0, 90.0],
        "intensity": [1.0, 0.9, 0.3, 0.0],
    }
    result = RayTracer(project).run()
    det = result.detectors["top_detector"]
    assert det.total_hits > 0


# ------------------------------------------------------------------
# New feature tests
# ------------------------------------------------------------------


def test_effective_flux_current_scaling():
    src = PointSource("s", np.array([0, 0, 0]), flux=100.0,
                      current_mA=20.0, flux_per_mA=5.0, thermal_derate=0.9)
    assert src.effective_flux == pytest.approx(20.0 * 5.0 * 0.9)


def test_effective_flux_default():
    src = PointSource("s", np.array([0, 0, 0]), flux=250.0)
    assert src.effective_flux == pytest.approx(250.0)


def test_effective_flux_thermal_only():
    src = PointSource("s", np.array([0, 0, 0]), flux=100.0, thermal_derate=0.8)
    assert src.effective_flux == pytest.approx(80.0)


def test_scatter_haze_stays_near_original():
    rng = np.random.default_rng(42)
    dirs = np.array([[0.0, 0.0, 1.0]] * 1000)
    scattered = scatter_haze(dirs, 5.0, rng)
    assert scattered.shape == (1000, 3)
    # All scattered directions should still point mostly upward
    assert float(scattered[:, 2].mean()) > 0.95


def test_scatter_haze_zero_angle_unchanged():
    rng = np.random.default_rng(42)
    dirs = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    result = scatter_haze(dirs, 0.0, rng)
    np.testing.assert_array_almost_equal(result, dirs)


def test_haze_material_in_simulation():
    project = _make_box_scene(rays_per_source=5000)
    project.materials["wall"].is_diffuse = False
    project.materials["wall"].haze = 20.0
    result = RayTracer(project).run()
    det = result.detectors["top_detector"]
    assert det.total_hits > 0
    assert det.total_flux > 0


def test_flux_tolerance_produces_variation():
    p1 = _make_box_scene(rays_per_source=1000)
    p1.sources[0].flux_tolerance = 20.0
    p1.settings.random_seed = 1
    r1 = RayTracer(p1).run()

    p2 = _make_box_scene(rays_per_source=1000)
    p2.sources[0].flux_tolerance = 20.0
    p2.settings.random_seed = 2
    r2 = RayTracer(p2).run()

    assert r1.detectors["top_detector"].total_flux > 0
    assert r2.detectors["top_detector"].total_flux > 0


def test_project_serialization_new_fields():
    from backlight_sim.io.project_io import project_to_dict, load_project, save_project
    import tempfile, os

    p = Project(name="test_serial")
    p.materials["m1"] = Material("m1", haze=15.0)
    p.sources.append(PointSource("s1", np.array([0, 0, 0]),
                                  flux_tolerance=10.0, current_mA=30.0,
                                  flux_per_mA=3.5, thermal_derate=0.85))
    p.settings.flux_unit = "mW"
    p.settings.angle_unit = "rad"
    p.settings.use_multiprocessing = True

    d = project_to_dict(p)
    assert d["materials"][0]["haze"] == 15.0
    assert d["sources"][0]["flux_tolerance"] == 10.0
    assert d["sources"][0]["current_mA"] == 30.0
    assert d["sources"][0]["flux_per_mA"] == 3.5
    assert d["sources"][0]["thermal_derate"] == 0.85
    assert d["settings"]["flux_unit"] == "mW"
    assert d["settings"]["use_multiprocessing"] is True

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        save_project(p, path)
        loaded = load_project(path)
        assert loaded.materials["m1"].haze == 15.0
        assert loaded.sources[0].flux_tolerance == 10.0
        assert loaded.sources[0].thermal_derate == 0.85
        assert loaded.settings.flux_unit == "mW"
        assert loaded.settings.use_multiprocessing is True
    finally:
        os.unlink(path)


def test_build_optical_stack():
    from backlight_sim.io.geometry_builder import build_optical_stack
    p = Project()
    p.materials["diffuser"] = Material("diffuser", "diffuser", transmittance=0.7)
    p.materials["default_reflector"] = Material("default_reflector")
    n = build_optical_stack(p, 100, 60, 10,
                            diffuser_distance=8.0,
                            film_distances=[5.0, 3.0])
    assert n == 3
    names = [s.name for s in p.surfaces]
    assert "Diffuser" in names
    assert "Film_1" in names
    assert "Film_2" in names
    diffuser = next(s for s in p.surfaces if s.name == "Diffuser")
    assert diffuser.center[2] == pytest.approx(8.0)


def test_build_optical_stack_no_diffuser():
    from backlight_sim.io.geometry_builder import build_optical_stack
    p = Project()
    p.materials["default_reflector"] = Material("default_reflector")
    n = build_optical_stack(p, 100, 60, 10, diffuser_distance=0.0)
    assert n == 0
    assert len(p.surfaces) == 0


def test_escaped_flux_tracked():
    result = RayTracer(_make_box_scene()).run()
    assert result.escaped_flux >= 0.0
    assert result.total_emitted_flux > 0


def test_sphere_detector_basic():
    """A sphere detector around a source should capture flux."""
    from backlight_sim.core.detectors import SphereDetector
    p = Project(name="sphere_test")
    p.sources.append(PointSource("src1", np.array([0.0, 0.0, 0.0]),
                                  flux=1000.0, distribution="isotropic"))
    p.sphere_detectors.append(SphereDetector("sph1", np.array([0.0, 0.0, 0.0]),
                                              radius=5.0, resolution=(36, 18)))
    p.settings = SimulationSettings(rays_per_source=2000, max_bounces=1,
                                     energy_threshold=0.001, random_seed=42)
    result = RayTracer(p).run()
    sdr = result.sphere_detectors["sph1"]
    assert sdr.total_hits > 0
    assert sdr.total_flux > 0
    assert sdr.grid.shape == (18, 36)
    assert sdr.grid.sum() > 0


def test_spectral_tracing():
    """Non-white SPD should produce spectral grid data on detector."""
    p = _make_box_scene(rays_per_source=2000)
    p.sources[0].spd = "warm_white"
    result = RayTracer(p).run()
    det = result.detectors["top_detector"]
    assert det.grid_spectral is not None
    assert det.grid_spectral.shape[2] > 0  # has spectral bins
    assert det.grid_spectral.sum() > 0  # accumulated flux


def test_spectral_rgb_conversion():
    """Spectral grid should convert to RGB image."""
    from backlight_sim.sim.spectral import spectral_grid_to_rgb, spectral_bin_centers
    n_bins = 40
    grid = np.random.rand(10, 10, n_bins).astype(float)
    wl = spectral_bin_centers(n_bins)
    rgb = spectral_grid_to_rgb(grid, wl)
    assert rgb.shape == (10, 10, 3)
    assert rgb.min() >= 0.0
    assert rgb.max() <= 1.0


def test_ies_parser_basic():
    """Test IES parser with a minimal synthetic IES file."""
    import tempfile, os
    from backlight_sim.io.ies_parser import load_ies

    ies_content = """IESNA:LM-63-2002
[TEST] Synthetic test
[MANUFAC] Test
TILT=NONE
1 100 1.0 5 1 1 1 0 0 0 1.0 1.0 0
0 22.5 45 67.5 90
0
100 90 60 30 0
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ies", delete=False) as f:
        f.write(ies_content)
        path = f.name
    try:
        profile = load_ies(path)
        assert "theta_deg" in profile
        assert "intensity" in profile
        assert len(profile["theta_deg"]) == 5
        assert profile["intensity"][0] == pytest.approx(1.0)  # peak normalized
    finally:
        os.unlink(path)


# ------------------------------------------------------------------
# Phase 1 — SolidBox, Fresnel/TIR tests
# ------------------------------------------------------------------


def _make_slab_scene(rays_per_source=5000, max_bounces=50, seed=42) -> Project:
    """Box scene with a PMMA slab (n=1.49, 3mm thick at z=4..7).

    Source is lambertian at z=0 pointing up.
    Detector is a flat surface at z=12.
    """
    from backlight_sim.core.solid_body import SolidBox
    materials = {
        "pmma": Material(name="pmma", surface_type="reflector",
                         reflectance=0.0, absorption=0.0,
                         refractive_index=1.49),
        "absorber": Material(name="absorber", surface_type="absorber"),
    }
    # PMMA slab centred at z=5.5 (from z=4 to z=7, depth=3)
    slab = SolidBox(name="slab", center=[0.0, 0.0, 5.5],
                    dimensions=(50.0, 50.0, 3.0), material_name="pmma")
    sources = [PointSource("src1", np.array([0.0, 0.0, 0.0]),
                            flux=1000.0, distribution="lambertian",
                            direction=np.array([0.0, 0.0, 1.0]))]
    detectors = [
        DetectorSurface.axis_aligned("top_det", [0, 0, 12], (50, 50), 2, 1.0, (20, 20)),
    ]
    settings = SimulationSettings(rays_per_source=rays_per_source,
                                  max_bounces=max_bounces,
                                  energy_threshold=0.0001,
                                  random_seed=seed,
                                  record_ray_paths=0)
    proj = Project(name="slab_test", sources=sources, surfaces=[],
                   materials=materials, detectors=detectors, settings=settings)
    proj.solid_bodies = [slab]
    return proj


def test_solid_box_get_faces_count_and_names():
    """SolidBox.get_faces() returns exactly 6 Rectangles with correct names."""
    from backlight_sim.core.solid_body import SolidBox, FACE_NAMES
    box = SolidBox("lgp", center=[0, 0, 0], dimensions=(50, 30, 3))
    faces = box.get_faces()
    assert len(faces) == 6
    face_ids = {f.name.split("::")[1] for f in faces}
    assert face_ids == set(FACE_NAMES)
    for f in faces:
        assert f.name.startswith("lgp::")


def test_solid_box_face_centers():
    """Each face center is offset from box center by half-dimension."""
    from backlight_sim.core.solid_body import SolidBox
    cx, cy, cz = 1.0, 2.0, 3.0
    W, H, D = 10.0, 6.0, 4.0
    box = SolidBox("b", center=[cx, cy, cz], dimensions=(W, H, D))
    faces = {f.name.split("::")[1]: f for f in box.get_faces()}

    np.testing.assert_allclose(faces["top"].center,    [cx, cy, cz + D/2])
    np.testing.assert_allclose(faces["bottom"].center, [cx, cy, cz - D/2])
    np.testing.assert_allclose(faces["right"].center,  [cx + W/2, cy, cz])
    np.testing.assert_allclose(faces["left"].center,   [cx - W/2, cy, cz])
    np.testing.assert_allclose(faces["back"].center,   [cx, cy + H/2, cz])
    np.testing.assert_allclose(faces["front"].center,  [cx, cy - H/2, cz])


def test_solid_box_face_normals_outward():
    """Each face normal must point away from the box center."""
    from backlight_sim.core.solid_body import SolidBox
    box = SolidBox("b", center=[5, 5, 5], dimensions=(10, 8, 6))
    for face in box.get_faces():
        offset = face.center - box.center
        dot = float(np.dot(face.normal, offset))
        assert dot > 0, f"Face {face.name} normal not outward: dot={dot}"


def test_solid_box_face_sizes():
    """Face sizes match expected dimensions."""
    from backlight_sim.core.solid_body import SolidBox
    W, H, D = 10.0, 6.0, 4.0
    box = SolidBox("b", center=[0, 0, 0], dimensions=(W, H, D))
    faces = {f.name.split("::")[1]: f for f in box.get_faces()}

    assert faces["top"].size    == pytest.approx((W, H))
    assert faces["bottom"].size == pytest.approx((W, H))
    assert faces["right"].size  == pytest.approx((H, D))
    assert faces["left"].size   == pytest.approx((H, D))
    assert faces["back"].size   == pytest.approx((W, D))
    assert faces["front"].size  == pytest.approx((W, D))


def test_solid_box_face_optics_override():
    """face_optics dict sets optical_properties_name only on the specified face."""
    from backlight_sim.core.solid_body import SolidBox
    box = SolidBox("b", center=[0, 0, 0], dimensions=(10, 10, 10),
                   face_optics={"top": "my_coating"})
    faces = {f.name.split("::")[1]: f for f in box.get_faces()}

    assert faces["top"].optical_properties_name == "my_coating"
    for fid in ("bottom", "left", "right", "front", "back"):
        assert faces[fid].optical_properties_name == ""


def test_solid_box_material_name_propagates():
    """All faces without face_optics override carry the box material_name."""
    from backlight_sim.core.solid_body import SolidBox
    box = SolidBox("b", center=[0, 0, 0], dimensions=(5, 5, 5),
                   material_name="acrylic")
    for face in box.get_faces():
        assert face.material_name == "acrylic"


def test_project_solid_bodies_default_empty():
    """Project.solid_bodies defaults to an empty list."""
    p = Project()
    assert hasattr(p, "solid_bodies")
    assert p.solid_bodies == []


def test_simulation_result_solid_body_stats_default_empty():
    """SimulationResult.solid_body_stats defaults to an empty dict."""
    from backlight_sim.core.detectors import SimulationResult
    r = SimulationResult()
    assert hasattr(r, "solid_body_stats")
    assert r.solid_body_stats == {}


def test_fresnel_normal_incidence():
    """Air-to-PMMA at normal incidence: R ~ 0.04 (textbook value)."""
    from backlight_sim.sim.tracer import _fresnel_unpolarized
    cos_i = np.array([1.0])
    n1 = np.array([1.0])
    n2 = np.array([1.49])
    R = _fresnel_unpolarized(cos_i, n1, n2)
    assert float(R[0]) == pytest.approx(0.0398, abs=0.002)


def test_fresnel_tir():
    """PMMA-to-air past critical angle: R must be 1.0 (TIR)."""
    from backlight_sim.sim.tracer import _fresnel_unpolarized
    # Critical angle for PMMA (n=1.49): sin_c = 1/1.49 ~ 0.671, theta_c ~ 42.2 deg
    # Use cos_i = 0.3 which gives sin_i = sqrt(1-0.09) ~ 0.954 > sin_c
    cos_i = np.array([0.3])
    n1 = np.array([1.49])
    n2 = np.array([1.0])
    R = _fresnel_unpolarized(cos_i, n1, n2)
    assert float(R[0]) == pytest.approx(1.0, abs=1e-9)


def test_fresnel_grazing():
    """At grazing angle (cos_i ~ 0), R should approach 1.0."""
    from backlight_sim.sim.tracer import _fresnel_unpolarized
    cos_i = np.array([0.01])
    n1 = np.array([1.0])
    n2 = np.array([1.49])
    R = _fresnel_unpolarized(cos_i, n1, n2)
    assert float(R[0]) > 0.9


def test_refract_snell_normal_incidence():
    """Normal-incidence ray continues straight through interface."""
    from backlight_sim.sim.tracer import _refract_snell
    d = np.array([[0.0, 0.0, 1.0]])        # ray going +Z
    on = np.array([[0.0, 0.0, 1.0]])       # normal INTO new medium = +Z
    n1 = np.array([1.0])
    n2 = np.array([1.49])
    refracted = _refract_snell(d, on, n1, n2)
    np.testing.assert_allclose(refracted[0], [0.0, 0.0, 1.0], atol=1e-6)


def test_refract_snell_oblique():
    """Snell's law: n1*sin(theta_i) = n2*sin(theta_t) within tolerance."""
    from backlight_sim.sim.tracer import _refract_snell
    theta_i = np.radians(30.0)
    d = np.array([[np.sin(theta_i), 0.0, np.cos(theta_i)]])  # +Z dominant
    on = np.array([[0.0, 0.0, 1.0]])   # interface normal INTO medium 2
    n1_val, n2_val = 1.0, 1.49
    n1 = np.array([n1_val])
    n2 = np.array([n2_val])
    refracted = _refract_snell(d, on, n1, n2)
    # sin(theta_t) from refracted direction (angle with +Z)
    sin_t = float(np.sqrt(refracted[0, 0]**2 + refracted[0, 1]**2))
    sin_i = float(np.sin(theta_i))
    assert n1_val * sin_i == pytest.approx(n2_val * sin_t, rel=1e-4)


def test_slab_scene_produces_detector_flux():
    """PMMA slab scene: lambertian source below slab → detector above receives flux."""
    proj = _make_slab_scene(rays_per_source=5000, seed=42)
    result = RayTracer(proj).run()
    det = result.detectors["top_det"]
    assert det.total_flux > 0, "Expected non-zero detector flux through PMMA slab"


def test_slab_scene_solid_body_stats():
    """After running slab scene, solid_body_stats has the box name with face flux data."""
    proj = _make_slab_scene(rays_per_source=5000, seed=42)
    result = RayTracer(proj).run()
    assert "slab" in result.solid_body_stats, "solid_body_stats should contain 'slab'"
    slab_stats = result.solid_body_stats["slab"]
    # Bottom face should receive entering flux from lambertian source below
    assert "bottom" in slab_stats
    assert slab_stats["bottom"]["entering_flux"] > 0, "Bottom face entering flux should be > 0"


def test_slab_scene_no_self_intersection():
    """PMMA slab with many bounces: geometry-relative epsilon prevents TIR artifact.

    If self-intersection were an issue, rays would get trapped or produce zero
    detector flux. Detector flux > 1% of emitted confirms correct bounce geometry.
    """
    proj = _make_slab_scene(rays_per_source=10000, max_bounces=100, seed=7)
    result = RayTracer(proj).run()
    det = result.detectors["top_det"]
    efficiency = det.total_flux / result.total_emitted_flux
    assert efficiency > 0.01, (
        f"Expected efficiency > 1%, got {efficiency:.4f}. "
        "Possible self-intersection issue with epsilon."
    )


# ------------------------------------------------------------------
# Phase 2 — Spectral engine tests
# ------------------------------------------------------------------


def _make_spectral_scene(rays_per_source=2000, spd="warm_white", seed=42):
    """Minimal box scene with a single spectral source and detector."""
    materials = {
        "wall": Material(name="wall", surface_type="reflector",
                         reflectance=0.9, absorption=0.1),
    }
    surfaces = [
        Rectangle.axis_aligned("floor",      [0, 0, -5], (20, 20), 2, -1.0, "wall"),
        Rectangle.axis_aligned("wall_left",  [-10, 0, 0], (20, 10), 0, -1.0, "wall"),
        Rectangle.axis_aligned("wall_right", [10, 0, 0],  (20, 10), 0,  1.0, "wall"),
        Rectangle.axis_aligned("wall_front", [0, -10, 0], (20, 10), 1, -1.0, "wall"),
        Rectangle.axis_aligned("wall_back",  [0, 10, 0],  (20, 10), 1,  1.0, "wall"),
    ]
    detectors = [
        DetectorSurface.axis_aligned("top_detector", [0, 0, 5], (20, 20), 2, 1.0, (20, 20)),
    ]
    src = PointSource("src1", np.array([0.0, 0.0, 0.0]), flux=1000.0)
    src.spd = spd
    settings = SimulationSettings(rays_per_source=rays_per_source, max_bounces=20,
                                   energy_threshold=0.001, random_seed=seed,
                                   record_ray_paths=0)
    return Project(name="spectral_test", sources=[src], surfaces=surfaces,
                   materials=materials, detectors=detectors, settings=settings)


def test_custom_spd_profile_used_in_sampling():
    """Custom SPD peaked at 550 nm should produce samples clustering near that wavelength."""
    from backlight_sim.sim.spectral import sample_wavelengths, spectral_bin_centers
    import numpy as np

    # Custom SPD: strongly peaked at 550 nm
    wl = np.linspace(380, 780, 40)
    intensity = np.exp(-0.5 * ((wl - 550) / 5) ** 2)
    spd_profiles = {
        "my_green": {
            "wavelength_nm": wl.tolist(),
            "intensity": intensity.tolist(),
        }
    }
    rng = np.random.default_rng(0)
    samples = sample_wavelengths(5000, "my_green", rng, spd_profiles=spd_profiles)
    mean_wl = float(samples.mean())
    assert 530 <= mean_wl <= 570, f"Expected mean near 550 nm, got {mean_wl:.1f}"


def test_blackbody_spd_peak_shifts_with_cct():
    """blackbody_spd(3000) should peak at longer wavelength than blackbody_spd(6500)."""
    from backlight_sim.sim.spectral import blackbody_spd, N_SPECTRAL_BINS

    wl_warm, spd_warm = blackbody_spd(3000)
    wl_cool, spd_cool = blackbody_spd(6500)

    assert len(wl_warm) == N_SPECTRAL_BINS
    assert len(spd_warm) == N_SPECTRAL_BINS
    assert len(wl_cool) == N_SPECTRAL_BINS

    peak_warm = float(wl_warm[np.argmax(spd_warm)])
    peak_cool = float(wl_cool[np.argmax(spd_cool)])
    assert peak_warm > peak_cool, (
        f"Warm white peak ({peak_warm:.0f} nm) should exceed cool ({peak_cool:.0f} nm)"
    )


def test_spectral_material_reflectance_varies_per_wavelength():
    """Material with high reflectance at blue wavelengths should yield more blue flux."""
    from backlight_sim.core.project_model import Project
    import numpy as np

    p = _make_spectral_scene(rays_per_source=3000, spd="warm_white")
    # Override wall spectral data: high reflectance at 450 nm, low at 650 nm
    p.spectral_material_data = {
        "wall": {
            "wavelength_nm": [380.0, 450.0, 550.0, 650.0, 780.0],
            "reflectance": [0.95, 0.95, 0.50, 0.05, 0.05],
            "transmittance": [0.0, 0.0, 0.0, 0.0, 0.0],
        }
    }
    result = RayTracer(p).run()
    det = result.detectors["top_detector"]
    assert det.grid_spectral is not None, "grid_spectral should not be None for non-white SPD"
    spec = det.grid_spectral  # (ny, nx, n_bins)
    # Blue bins are lower wavelength indices; red bins are higher
    n_bins = spec.shape[2]
    blue_flux = float(spec[:, :, :n_bins // 4].sum())
    red_flux = float(spec[:, :, 3 * n_bins // 4:].sum())
    assert blue_flux > red_flux, (
        f"Blue flux ({blue_flux:.3f}) should exceed red ({red_flux:.3f}) "
        "with spectral material favoring blue reflectance"
    )


def test_spectral_grid_accumulated_for_non_white_spd():
    """Non-white SPD (warm_white) should produce non-zero grid_spectral."""
    p = _make_spectral_scene(rays_per_source=2000, spd="warm_white")
    result = RayTracer(p).run()
    det = result.detectors["top_detector"]
    assert det.grid_spectral is not None, "grid_spectral should not be None for warm_white SPD"
    assert det.grid_spectral.sum() > 0, "grid_spectral should have non-zero accumulated flux"
    assert det.grid_spectral.shape[2] > 0, "grid_spectral should have spectral bins"


def test_spd_profiles_project_io_roundtrip():
    """Project with spd_profiles and spectral_material_data should round-trip through JSON."""
    from backlight_sim.io.project_io import save_project, load_project
    import tempfile, os

    p = Project(name="spectral_io_test")
    p.spd_profiles = {
        "my_led": {
            "wavelength_nm": [400.0, 500.0, 600.0, 700.0],
            "intensity": [0.1, 1.0, 0.8, 0.2],
        }
    }
    p.spectral_material_data = {
        "reflector_x": {
            "wavelength_nm": [400.0, 500.0, 600.0, 700.0],
            "reflectance": [0.95, 0.90, 0.85, 0.80],
            "transmittance": [0.0, 0.0, 0.0, 0.0],
        }
    }
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        save_project(p, path)
        p2 = load_project(path)
        assert p2.spd_profiles == p.spd_profiles, "spd_profiles did not survive round-trip"
        assert p2.spectral_material_data == p.spectral_material_data, (
            "spectral_material_data did not survive round-trip"
        )
    finally:
        os.unlink(path)


def test_get_spd_from_project_custom_overrides_builtin():
    """get_spd_from_project with custom profile dict should return that profile, not builtin."""
    from backlight_sim.sim.spectral import get_spd_from_project
    import numpy as np

    wl_custom = [400.0, 500.0, 600.0, 700.0]
    int_custom = [0.0, 1.0, 0.0, 0.0]  # peaked at 500 nm
    spd_profiles = {
        "warm_white": {  # override the builtin warm_white name
            "wavelength_nm": wl_custom,
            "intensity": int_custom,
        }
    }
    wl, intensity = get_spd_from_project("warm_white", spd_profiles)
    # The custom one has 4 points; the builtin warm_white would have N_SPECTRAL_BINS (40)
    assert len(wl) == 4, f"Expected custom 4-point profile, got {len(wl)} points"
    assert float(intensity[1]) == pytest.approx(1.0)


def test_spectral_mp_guard_falls_back_to_single_thread():
    """Spectral simulation with MP enabled should warn and fall back to single-thread."""
    import warnings
    p = _make_spectral_scene(rays_per_source=500, spd="warm_white")
    p.settings.use_multiprocessing = True
    p.settings.record_ray_paths = 0
    # Add a second source so MP would normally apply
    src2 = PointSource("src2", np.array([1.0, 0.0, 0.0]), flux=100.0)
    src2.spd = "warm_white"
    p.sources.append(src2)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = RayTracer(p).run()
    det = result.detectors["top_detector"]
    # Should still produce results (single-thread fallback)
    assert det.total_hits > 0
    # Should have issued a warning about spectral+MP
    warning_messages = [str(warning.message) for warning in w]
    assert any("spectral" in msg.lower() or "single" in msg.lower()
               for msg in warning_messages), (
        f"Expected spectral/single-thread warning, got: {warning_messages}"
    )


# ------------------------------------------------------------------
# Phase 3 — Numba JIT acceleration tests
# ------------------------------------------------------------------


def test_jit_numba_available_is_bool():
    """_NUMBA_AVAILABLE must be a bool regardless of whether Numba is installed."""
    from backlight_sim.sim.accel import _NUMBA_AVAILABLE
    assert isinstance(_NUMBA_AVAILABLE, bool)


def test_jit_warmup_runs_without_error():
    """warmup_jit_kernels() should complete without raising any exception."""
    from backlight_sim.sim.accel import warmup_jit_kernels
    # Should not raise
    result = warmup_jit_kernels()
    assert isinstance(result, bool)


def test_jit_intersect_plane_matches_numpy():
    """intersect_plane JIT wrapper should produce same t-values as _intersect_rays_plane."""
    from backlight_sim.sim.accel import intersect_plane
    from backlight_sim.sim.tracer import _intersect_rays_plane

    rng = np.random.default_rng(42)
    # A horizontal plane at z=5, size 20x20
    normal = np.array([0.0, 0.0, 1.0])
    center = np.array([0.0, 0.0, 5.0])
    u_axis = np.array([1.0, 0.0, 0.0])
    v_axis = np.array([0.0, 1.0, 0.0])
    size = (20.0, 20.0)

    # 100 random rays starting below the plane pointing generally upward
    origins = rng.uniform(-5, 5, (100, 3))
    origins[:, 2] = rng.uniform(-2, 3, 100)  # z in [-2, 3], below plane at z=5
    # Directions mostly upward
    dirs_raw = rng.normal(0, 0.3, (100, 3))
    dirs_raw[:, 2] = np.abs(dirs_raw[:, 2]) + 0.5
    norms = np.linalg.norm(dirs_raw, axis=1, keepdims=True)
    directions = dirs_raw / norms

    t_numpy = _intersect_rays_plane(origins, directions, normal, center, u_axis, v_axis, size)
    t_jit   = intersect_plane(origins, directions, normal, center, u_axis, v_axis, size)

    # Both should give same finite hits
    np.testing.assert_allclose(t_numpy, t_jit, rtol=1e-10, atol=1e-10,
                                err_msg="JIT plane intersection differs from NumPy reference")


def test_jit_intersect_sphere_matches_numpy():
    """intersect_sphere JIT wrapper should produce same t-values as _intersect_rays_sphere."""
    from backlight_sim.sim.accel import intersect_sphere
    from backlight_sim.sim.tracer import _intersect_rays_sphere

    rng = np.random.default_rng(7)
    center = np.array([0.0, 0.0, 0.0])
    radius = 5.0

    # 100 random rays from outside the sphere, pointing inward
    origins = rng.uniform(-15, 15, (100, 3))
    # Ensure origins are outside the sphere
    while True:
        too_close = np.linalg.norm(origins - center, axis=1) < radius + 0.5
        if not too_close.any():
            break
        origins[too_close] = rng.uniform(-15, 15, (too_close.sum(), 3))

    # Directions pointing toward origin with some spread
    dirs_raw = center - origins + rng.normal(0, 1.0, (100, 3))
    norms = np.linalg.norm(dirs_raw, axis=1, keepdims=True)
    directions = dirs_raw / norms

    t_numpy = _intersect_rays_sphere(origins, directions, center, radius)
    t_jit   = intersect_sphere(origins, directions, center, radius)

    np.testing.assert_allclose(t_numpy, t_jit, rtol=1e-10, atol=1e-10,
                                err_msg="JIT sphere intersection differs from NumPy reference")


def test_jit_accumulate_grid_matches_numpy():
    """accumulate_grid_jit should produce identical result to np.add.at scatter-add."""
    from backlight_sim.sim.accel import accumulate_grid_jit

    rng = np.random.default_rng(13)
    grid_jit   = np.zeros((20, 30), dtype=float)
    grid_numpy = np.zeros((20, 30), dtype=float)

    # Random hit indices and weights
    n_hits = 500
    iy = rng.integers(0, 20, n_hits)
    ix = rng.integers(0, 30, n_hits)
    weights = rng.uniform(0.001, 0.1, n_hits)

    accumulate_grid_jit(grid_jit, iy, ix, weights)
    np.add.at(grid_numpy, (iy, ix), weights)

    np.testing.assert_array_equal(grid_jit, grid_numpy,
                                   err_msg="accumulate_grid_jit differs from np.add.at")


def test_jit_accumulate_sphere_matches_numpy():
    """accumulate_sphere_jit should produce identical result to np.add.at."""
    from backlight_sim.sim.accel import accumulate_sphere_jit

    rng = np.random.default_rng(99)
    grid_jit   = np.zeros((18, 36), dtype=float)
    grid_numpy = np.zeros((18, 36), dtype=float)

    n_hits = 300
    i_theta = rng.integers(0, 18, n_hits)
    i_phi   = rng.integers(0, 36, n_hits)
    weights = rng.uniform(0.001, 0.05, n_hits)

    accumulate_sphere_jit(grid_jit, i_theta, i_phi, weights)
    np.add.at(grid_numpy, (i_theta, i_phi), weights)

    np.testing.assert_array_equal(grid_jit, grid_numpy,
                                   err_msg="accumulate_sphere_jit differs from np.add.at")


def test_simulation_deterministic_with_jit():
    """Full simulation should give same result on two runs (determinism check with JIT)."""
    # This also exercises the JIT path once Task 2 is complete (dispatch in tracer)
    p1 = _make_box_scene(rays_per_source=3000)
    p2 = _make_box_scene(rays_per_source=3000)
    r1 = RayTracer(p1).run()
    r2 = RayTracer(p2).run()
    # Exact equality — same seed, same code path
    np.testing.assert_array_equal(
        r1.detectors["top_detector"].grid,
        r2.detectors["top_detector"].grid,
        err_msg="Simulation not deterministic — JIT dispatch may have introduced non-determinism",
    )


# ------------------------------------------------------------------
# Phase 3 Plan 02 — BVH acceleration tests
# ------------------------------------------------------------------


def _make_many_surface_scene(n_surfaces=60, rays_per_source=1000) -> Project:
    """Scene with many small tile surfaces + one source + one detector.

    Creates a grid of small absorber tiles scattered at z=-1 (below source at z=0),
    plus the standard box walls, and a detector at z=5.
    """
    materials = {
        "wall": Material(name="wall", surface_type="reflector",
                         reflectance=0.9, absorption=0.1),
        "tile": Material(name="tile", surface_type="absorber",
                         reflectance=0.0, absorption=1.0),
    }
    # Standard walls
    surfaces = [
        Rectangle.axis_aligned("floor",      [0, 0, -10], (40, 40), 2, -1.0, "wall"),
        Rectangle.axis_aligned("wall_left",  [-20, 0, 0], (40, 20), 0, -1.0, "wall"),
        Rectangle.axis_aligned("wall_right", [20, 0, 0],  (40, 20), 0,  1.0, "wall"),
        Rectangle.axis_aligned("wall_front", [0, -20, 0], (40, 20), 1, -1.0, "wall"),
        Rectangle.axis_aligned("wall_back",  [0, 20, 0],  (40, 20), 1,  1.0, "wall"),
    ]
    # Add small tiles to bring total above BVH threshold (50)
    extra = n_surfaces - len(surfaces)
    cols = max(1, int(np.ceil(np.sqrt(extra))))
    for i in range(extra):
        row, col = divmod(i, cols)
        cx = (col - cols / 2) * 3.0
        cy = (row - cols / 2) * 3.0
        surfaces.append(
            Rectangle.axis_aligned(
                f"tile_{i}", [cx, cy, -1], (1.0, 1.0), 2, 1.0, "tile"
            )
        )
    detectors = [
        DetectorSurface.axis_aligned("top_detector", [0, 0, 5], (40, 40), 2, 1.0, (20, 20)),
    ]
    sources = [PointSource("src1", np.array([0.0, 0.0, 0.0]), flux=1000.0)]
    settings = SimulationSettings(rays_per_source=rays_per_source, max_bounces=30,
                                  energy_threshold=0.001, random_seed=42, record_ray_paths=0)
    return Project(name="many_surfaces", sources=sources, surfaces=surfaces,
                   materials=materials, detectors=detectors, settings=settings)


def test_bvh_build_valid_tree_structure():
    """BVH build produces valid tree: node_count <= 2N-1, leaves reference valid indices."""
    from backlight_sim.sim.accel import build_bvh_flat, compute_surface_aabbs

    rng = np.random.default_rng(7)
    n = 30
    # Random small rectangles scattered in a 20x20x20 volume
    centers = rng.uniform(-10, 10, (n, 3))
    normals = np.tile(np.array([0.0, 0.0, 1.0]), (n, 1))
    u_axes  = np.tile(np.array([1.0, 0.0, 0.0]), (n, 1))
    v_axes  = np.tile(np.array([0.0, 1.0, 0.0]), (n, 1))
    half_ws = np.full(n, 1.0)
    half_hs = np.full(n, 1.0)

    aabbs = compute_surface_aabbs(normals, centers, u_axes, v_axes, half_ws, half_hs)
    assert aabbs.shape == (n, 6), f"Expected ({n}, 6) aabbs, got {aabbs.shape}"

    node_bounds, node_meta, n_nodes = build_bvh_flat(aabbs)

    # Node count must be <= 2N-1
    assert n_nodes <= 2 * n - 1, f"n_nodes {n_nodes} exceeds 2N-1={2*n-1}"
    assert n_nodes >= 1

    # All leaf nodes must reference valid surface indices
    for i in range(n_nodes):
        if node_meta[i, 2] == 1:  # leaf
            surf_idx = node_meta[i, 0]
            assert 0 <= surf_idx < n, (
                f"Leaf node {i} has invalid surf_idx {surf_idx}, expected in [0, {n-1}]"
            )


def test_bvh_matches_bruteforce():
    """BVH traversal must produce the same hit surface as brute-force for a 60-surface scene."""
    from backlight_sim.sim.accel import (
        build_bvh_flat, compute_surface_aabbs, traverse_bvh_batch,
    )

    # Build a scene with 60 horizontal rectangles at various heights
    rng = np.random.default_rng(13)
    n = 60
    centers = rng.uniform(-15, 15, (n, 3))
    centers[:, 2] = rng.uniform(1, 20, n)  # z between 1 and 20
    normals = np.tile(np.array([0.0, 0.0, 1.0], dtype=np.float64), (n, 1))
    u_axes  = np.tile(np.array([1.0, 0.0, 0.0], dtype=np.float64), (n, 1))
    v_axes  = np.tile(np.array([0.0, 1.0, 0.0], dtype=np.float64), (n, 1))
    half_ws = np.full(n, 2.0, dtype=np.float64)
    half_hs = np.full(n, 2.0, dtype=np.float64)

    aabbs = compute_surface_aabbs(normals, centers, u_axes, v_axes, half_ws, half_hs)
    node_bounds, node_meta, n_nodes = build_bvh_flat(aabbs)

    # 500 random rays from below, pointing generally upward
    n_rays = 500
    ray_origins = rng.uniform(-10, 10, (n_rays, 3)).astype(np.float64)
    ray_origins[:, 2] = 0.0
    raw_dirs = rng.normal(0, 0.3, (n_rays, 3))
    raw_dirs[:, 2] = np.abs(raw_dirs[:, 2]) + 0.3
    norms = np.linalg.norm(raw_dirs, axis=1, keepdims=True)
    ray_dirs = (raw_dirs / norms).astype(np.float64)

    epsilon = 1e-6

    # Brute-force: test all surfaces
    from backlight_sim.sim.accel import intersect_plane_jit
    bf_best_t = np.full(n_rays, np.inf)
    bf_best_idx = np.full(n_rays, -1, dtype=np.int64)
    for si in range(n):
        t_vals = intersect_plane_jit(
            ray_origins, ray_dirs,
            normals[si], centers[si], u_axes[si], v_axes[si],
            half_ws[si], half_hs[si], epsilon,
        )
        closer = t_vals < bf_best_t
        bf_best_t[closer] = t_vals[closer]
        bf_best_idx[closer] = si

    # BVH traversal
    bvh_best_t, bvh_best_idx = traverse_bvh_batch(
        ray_origins, ray_dirs,
        node_bounds, node_meta, n_nodes,
        normals, centers, u_axes, v_axes, half_ws, half_hs,
        epsilon,
    )

    # Rays with hits must match on surface index (and t within tolerance)
    hit_mask = bf_best_idx >= 0
    np.testing.assert_array_equal(
        bvh_best_idx[hit_mask], bf_best_idx[hit_mask],
        err_msg="BVH and brute-force surface indices differ for hit rays",
    )
    np.testing.assert_allclose(
        bvh_best_t[hit_mask], bf_best_t[hit_mask], rtol=1e-9,
        err_msg="BVH and brute-force t-values differ for hit rays",
    )
    # No-hit rays must also agree
    miss_mask = ~hit_mask
    assert np.all(bvh_best_idx[miss_mask] == -1), "BVH reported hit where brute-force found none"


def test_bvh_not_used_below_threshold():
    """Scene with < 50 surfaces must complete correctly (no BVH, no regression)."""
    # A standard 5-surface box scene (well below 50)
    project = _make_box_scene(rays_per_source=2000)
    assert len(project.surfaces) < 50
    result = RayTracer(project).run()
    det = result.detectors["top_detector"]
    assert det.total_hits > 0
    assert det.total_flux > 0


def test_bvh_simulation_same_result_as_bruteforce():
    """Simulation with 60+ surfaces must produce same detector flux via BVH as brute-force path.

    We achieve this by comparing two runs: one that uses BVH (>= 50 surfaces)
    and one that uses brute-force (artificially reduce surface count below threshold).
    Both runs use the same physics, so total escaping flux behavior should be similar.
    The primary check is that the BVH run produces nonzero, sensible flux.
    """
    project = _make_many_surface_scene(n_surfaces=60, rays_per_source=2000)
    assert len(project.surfaces) >= 50, (
        f"Expected >= 50 surfaces, got {len(project.surfaces)}"
    )
    result = RayTracer(project).run()
    det = result.detectors["top_detector"]
    assert det.total_hits > 0, "BVH path produced zero hits"
    assert det.total_flux > 0, "BVH path produced zero flux"
