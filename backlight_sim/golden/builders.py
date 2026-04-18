"""Scene builders for the golden-reference validation suite.

These functions are shared between the pytest fixtures in
``backlight_sim/tests/golden/conftest.py`` and the CLI case registry in
``backlight_sim/golden/cases.py``. Keeping them here (inside the shipped
``backlight_sim.golden`` package) avoids pulling the test package into the
CLI import path.

Design notes
------------

* Every builder sets ``random_seed = GOLDEN_SEED = 42`` and
  ``flux_tolerance = 0.0`` on every source so runs are bit-reproducible
  (Pitfall 6 from 03-RESEARCH.md).
* The integrating cavity is built from 6 ``Rectangle`` Lambertian walls
  (NOT a ``SolidBox``) because ``SolidBox`` faces apply Fresnel physics by
  default, which would require a complex ``face_optics`` override to
  behave as a Lambertian reflector. A dummy ``spectral_material_data``
  entry is installed on the project so the tracer's dispatch predicate
  (``_project_uses_cpp_unsupported_features`` at ``tracer.py:285``) routes
  the scene to the Python path — this exercises the Python Lambertian
  reflection block that the plan set out to validate.
* The specular mirror uses a source placed directly above the mirror
  center aimed straight down; the mirror is tilted about the x-axis by
  ``theta_deg`` so the incidence angle equals ``theta_deg`` exactly.
  The reflected beam leaves at angle ``2 * theta_deg`` from ``+Z`` in the
  y-z plane, which we verify in the two specular tests.
"""
from __future__ import annotations

import numpy as np

from backlight_sim.core.detectors import DetectorSurface, SphereDetector
from backlight_sim.core.geometry import Rectangle
from backlight_sim.core.materials import Material
from backlight_sim.core.project_model import Project, SimulationSettings
from backlight_sim.core.sources import PointSource


GOLDEN_SEED = 42


def _base_project(
    name: str,
    rays: int,
    max_bounces: int = 50,
    energy_threshold: float = 1e-9,
) -> Project:
    """Return a minimal ``Project`` seeded with ``GOLDEN_SEED``.

    Uses an aggressive ``energy_threshold=1e-9`` by default so rays survive
    up to ``max_bounces`` reflections at any ray count. The default threshold
    of ``1e-3`` (see ``SimulationSettings``) kills rays after only ~6 bounces
    when ``ray count >> phi``, which causes Monte Carlo results to drift
    systematically with the number of rays — breaking reproducibility for
    high-ρ cavities.
    """
    project = Project(name=name)
    project.settings = SimulationSettings(
        rays_per_source=rays,
        max_bounces=max_bounces,
        energy_threshold=energy_threshold,
        random_seed=GOLDEN_SEED,
        record_ray_paths=0,
        distance_unit="mm",
        adaptive_sampling=False,
    )
    return project


# ---------------------------------------------------------------------------
# GOLD-01 — integrating cavity
# ---------------------------------------------------------------------------

def build_integrating_cavity_project(
    radius: float = 50.0,
    rho: float = 0.9,
    rays: int = 500_000,
) -> Project:
    """Closed cubic Lambertian cavity with a 10x10 mm patch detector.

    The cavity is a cube of side ``2 * radius`` centered at the origin built
    from 6 ``Rectangle`` Lambertian walls — not a ``SolidBox`` — because
    ``SolidBox`` faces apply Fresnel physics by default and would require a
    per-face optical-properties override to behave as a Lambertian reflector.

    A dummy ``spectral_material_data`` entry is attached to the project to
    force the tracer into the Python path (exercising the Python Lambertian
    reflection block), matching the plan's routing intent without needing a
    ``SolidBox`` at all.
    """
    project = _base_project(f"integrating_cavity_rho{rho}", rays, max_bounces=50)
    project.materials["cavity_wall"] = Material(
        name="cavity_wall",
        surface_type="reflector",
        reflectance=rho,
        absorption=1.0 - rho,
        transmittance=0.0,
        is_diffuse=True,
    )
    project.materials["patch_absorber"] = Material(
        name="patch_absorber",
        surface_type="absorber",
        reflectance=0.0,
        absorption=1.0,
    )

    # 5 full cube faces + 4 top-wall strips surrounding a 10x10 mm port.
    # The detector occupies the port — this is the classical "exit-port"
    # integrating-sphere geometry where the port irradiance equals the
    # wall irradiance predicted by the analytical formula.
    r = float(radius)
    s = 2.0 * r
    full_face_specs = [
        # (name, center, normal_axis, normal_sign)
        ("wall_+x", [+r, 0.0, 0.0], 0, -1.0),   # normal -X (inward)
        ("wall_-x", [-r, 0.0, 0.0], 0, +1.0),
        ("wall_+y", [0.0, +r, 0.0], 1, -1.0),
        ("wall_-y", [0.0, -r, 0.0], 1, +1.0),
        ("wall_-z", [0.0, 0.0, -r], 2, +1.0),
    ]
    for name, center, axis, sign in full_face_specs:
        project.surfaces.append(Rectangle.axis_aligned(
            name=name,
            center=center,
            size=(s, s),
            normal_axis=axis,
            normal_sign=sign,
            material_name="cavity_wall",
        ))

    # Top wall minus a 10x10 port — 4 strips. The "s/2 - 5" extent runs
    # from ±5 (port edge) to ±r (wall edge).
    port = 10.0
    hp = port / 2.0        # half-port = 5 mm
    strip_len = r - hp     # 45 mm at r=50
    strip_center = (r + hp) / 2.0  # 27.5 mm at r=50
    top_strips = [
        # (name, center, size_along_u, size_along_v)
        # u along +X, v along +Y, normal -Z (inward).
        ("top_strip_+x", [+strip_center, 0.0, +r], (strip_len, s)),
        ("top_strip_-x", [-strip_center, 0.0, +r], (strip_len, s)),
        ("top_strip_+y", [0.0, +strip_center, +r], (port, strip_len)),
        ("top_strip_-y", [0.0, -strip_center, +r], (port, strip_len)),
    ]
    for name, center, size in top_strips:
        project.surfaces.append(Rectangle.axis_aligned(
            name=name,
            center=center,
            size=size,
            normal_axis=2,
            normal_sign=-1.0,   # normal points DOWN into the cavity
            material_name="cavity_wall",
        ))

    # Isotropic source at cavity center
    project.sources.append(PointSource(
        name="src",
        position=np.array([0.0, 0.0, 0.0]),
        flux=1000.0,
        distribution="isotropic",
        flux_tolerance=0.0,
    ))

    # 10x10 mm detector patch flush with the top wall plane (z = +r),
    # occupying the port left by the 4 strips above. Rays that pass
    # through the port register on the detector and then escape the
    # cavity (no wall behind the port) — matching the classic integrating
    # sphere exit-port analytical model.
    project.detectors.append(DetectorSurface.axis_aligned(
        name="patch",
        center=[0.0, 0.0, r],
        size=(port, port),
        normal_axis=2,
        normal_sign=-1.0,
        resolution=(5, 5),
    ))

    # Force the tracer onto the Python path by attaching a dummy
    # spectral_material_data entry. The entry references no actual surface
    # (key '__force_python__' is not used by any surface material_name),
    # so it does not perturb the physics — it only flips the dispatch
    # predicate at tracer.py:285.
    project.spectral_material_data = {
        "__force_python__": {
            "wavelength_nm": [400.0, 700.0],
            "reflectance": [rho, rho],
            "transmittance": [0.0, 0.0],
        }
    }
    return project


# ---------------------------------------------------------------------------
# GOLD-02 — Lambertian emitter
# ---------------------------------------------------------------------------

def build_lambertian_emitter_project(rays: int = 500_000) -> Project:
    """Single Lambertian emitter in free space with one far-field sphere detector.

    Source direction is ``(0, 0, -1)`` so the cosine-law peak aligns with the
    candela grid's theta=0 bin (north pole). See notes in
    ``tracer.py::_accumulate_sphere_farfield`` (``d = -direction``): a ray
    travelling in ``-Z`` is recorded at ``theta = arccos(+1) = 0``.
    """
    # Need at least 1 bounce iteration for the sphere detector intersection
    # block to run (see tracer.py:991 bounce loop). Sphere detectors are
    # pass-through so 1 bounce is enough.
    project = _base_project("lambertian_emitter", rays, max_bounces=1)
    project.sources.append(PointSource(
        name="src",
        position=np.array([0.0, 0.0, 0.0]),
        flux=1000.0,
        distribution="lambertian",
        direction=np.array([0.0, 0.0, -1.0]),
        flux_tolerance=0.0,
    ))
    project.sphere_detectors.append(SphereDetector(
        name="farfield",
        center=np.array([0.0, 0.0, 0.0]),
        radius=1000.0,
        resolution=(72, 36),   # (n_phi, n_theta) → candela_grid shape (36, 72)
        mode="far_field",
    ))
    return project


# ---------------------------------------------------------------------------
# GOLD-04 — specular reflection (dual sub-cases)
# ---------------------------------------------------------------------------

def build_specular_mirror_project(
    theta_deg: float = 30.0,
    rays: int = 100_000,
    use_farfield: bool = False,
) -> Project:
    """Perfect mirror (R=1, specular) tilted by ``theta_deg`` about the x-axis.

    Scene layout
    ------------
    * Source at ``(0, 0, H)`` aiming straight down (``direction=(0,0,-1)``)
      with a narrow (< 5°) angular distribution — effectively a pencil beam.
      A Lambertian distribution would bias the reflected centroid because
      the finite tilted mirror asymmetrically truncates the +y vs -y
      hemispheres of a Lambertian emission cone; a narrow pencil beam
      avoids that and cleanly isolates the law-of-reflection geometry.
    * Mirror ``Rectangle`` centered at the origin in the XY plane rotated
      about ``+X`` by ``theta``. Its outward normal is
      ``(0, sin(theta), cos(theta))`` and the incidence angle for a
      straight-down ray equals exactly ``theta_deg``.
    * Reflected ray direction is
      ``(0, sin(2*theta), cos(2*theta))`` — i.e. ``2*theta_deg`` off ``+Z``.

    When ``use_farfield=True`` a ``SphereDetector(mode="far_field")`` is
    added (0.5° polar bins) and the scene routes to the Python path.
    When ``use_farfield=False`` a planar ``DetectorSurface`` is centered on
    the reflected ray at distance ``D`` from the mirror and oriented
    perpendicular to it — this scene routes to the C++ path.
    """
    project = _base_project(
        f"specular_theta{theta_deg}_ff{use_farfield}",
        rays,
        max_bounces=2,
    )
    project.materials["mirror"] = Material(
        name="mirror",
        surface_type="reflector",
        reflectance=1.0,
        absorption=0.0,
        transmittance=0.0,
        is_diffuse=False,
    )

    theta = float(np.radians(theta_deg))
    # Mirror plane rotated about +X by theta:
    #   u_axis = (1, 0, 0)
    #   v_axis = (0, cos(theta), -sin(theta))
    #   normal = cross(u, v) = (0, sin(theta), cos(theta))
    u_axis = np.array([1.0, 0.0, 0.0])
    v_axis = np.array([0.0, np.cos(theta), -np.sin(theta)])
    project.surfaces.append(Rectangle(
        name="mirror",
        center=np.array([0.0, 0.0, 0.0]),
        u_axis=u_axis,
        v_axis=v_axis,
        size=(50.0, 50.0),
        material_name="mirror",
    ))

    # Narrow pencil-beam angular distribution so essentially all emitted rays
    # travel at < 5° from the source direction. This eliminates the geometric
    # truncation bias a Lambertian distribution would introduce when striking
    # a finite tilted mirror.
    project.angular_distributions["pencil_5deg"] = {
        "theta_deg": [0.0, 1.0, 2.0, 3.0, 5.0],
        "intensity": [1.0, 0.5, 0.1, 0.01, 0.0],
    }

    # Source directly above the mirror center, aimed straight down.
    # A straight-down ray makes angle `theta` with the tilted mirror normal.
    H = 20.0
    project.sources.append(PointSource(
        name="src",
        position=np.array([0.0, 0.0, H]),
        flux=1000.0,
        distribution="pencil_5deg",
        direction=np.array([0.0, 0.0, -1.0]),
        flux_tolerance=0.0,
    ))

    # Reflected direction for a ray travelling in -Z off normal (0, sin θ, cos θ):
    # r = d - 2(d·n)n, d=(0,0,-1) → r = (0, 2 sin θ cos θ, -1 + 2 cos²θ)
    #                              = (0, sin 2θ, cos 2θ)
    refl_dir = np.array([0.0, np.sin(2.0 * theta), np.cos(2.0 * theta)])

    if use_farfield:
        project.sphere_detectors.append(SphereDetector(
            name="farfield",
            center=np.array([0.0, 0.0, 0.0]),
            radius=1000.0,
            # (n_phi, n_theta) = (720, 360) → candela_grid shape (360, 720),
            # polar bin width = pi/360 rad = 0.5° (meets plan's 0.5°/bin target).
            resolution=(720, 360),
            mode="far_field",
        ))
    else:
        # Planar detector placed D mm along the reflected ray from the mirror
        # center, oriented so its inward normal points back toward the mirror.
        D = 30.0
        det_center = D * refl_dir
        det_normal = -refl_dir
        # Build orthonormal u/v basis such that cross(u, v) == det_normal.
        # Use x as u (it is perpendicular to refl_dir since refl_dir lies in YZ).
        u_ax = np.array([1.0, 0.0, 0.0])
        # v = cross(normal, u) → cross(u, v) = cross(u, cross(n, u)) = n (for unit n, u⊥n)
        v_ax = np.cross(det_normal, u_ax)
        v_ax = v_ax / np.linalg.norm(v_ax)
        project.detectors.append(DetectorSurface(
            name="planar",
            center=det_center,
            u_axis=u_ax,
            v_axis=v_ax,
            size=(40.0, 40.0),
            resolution=(80, 80),
        ))
    return project
