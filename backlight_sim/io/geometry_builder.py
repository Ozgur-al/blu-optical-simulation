"""Cavity geometry builder - pure logic, no GUI."""

from __future__ import annotations

import numpy as np

from backlight_sim.core.geometry import Rectangle
from backlight_sim.core.materials import Material, OpticalProperties
from backlight_sim.core.sources import PointSource
from backlight_sim.core.detectors import DetectorSurface
from backlight_sim.core.solid_body import SolidBox
from backlight_sim.core.project_model import Project


def build_cavity(
    project: Project,
    width: float,
    height: float,
    depth: float,
    wall_angle_deg: float = 0.0,
    wall_angle_x_deg: float | None = None,
    wall_angle_y_deg: float | None = None,
    floor_material: str = "default_reflector",
    wall_material: str = "default_reflector",
    replace_existing: bool = True,
    record_recipe: bool = False,
) -> None:
    """Generate floor + 4 walls and add them to *project.surfaces*.

    `wall_angle_x_deg` controls left/right wall tilt.
    `wall_angle_y_deg` controls front/back wall tilt.
    If not provided, each falls back to `wall_angle_deg` for compatibility.
    """
    if replace_existing:
        project.surfaces.clear()

    if wall_angle_x_deg is None:
        wall_angle_x_deg = wall_angle_deg
    if wall_angle_y_deg is None:
        wall_angle_y_deg = wall_angle_deg

    tx = np.radians(float(wall_angle_x_deg))
    ty = np.radians(float(wall_angle_y_deg))
    sin_tx, cos_tx = float(np.sin(tx)), float(np.cos(tx))
    sin_ty, cos_ty = float(np.sin(ty)), float(np.cos(ty))
    tan_tx, tan_ty = float(np.tan(tx)), float(np.tan(ty))

    d = float(depth)
    w, h = float(width), float(height)
    half_w, half_h = w / 2.0, h / 2.0

    project.surfaces.append(
        Rectangle.axis_aligned("Floor", [0.0, 0.0, 0.0], (w, h), 2, -1.0, floor_material)
    )

    if abs(wall_angle_x_deg) < 1e-9 and abs(wall_angle_y_deg) < 1e-9:
        # Left/Right walls: normal ±X, u=Y v=Z → size (extent Y, extent Z) = (h, d)
        # Back/Front walls: normal ±Y, u=Z v=X → size (extent Z, extent X) = (d, w)
        project.surfaces += [
            Rectangle.axis_aligned("Wall Right", [half_w, 0.0, d / 2], (h, d), 0, 1.0, wall_material),
            Rectangle.axis_aligned("Wall Left", [-half_w, 0.0, d / 2], (h, d), 0, -1.0, wall_material),
            Rectangle.axis_aligned("Wall Back", [0.0, half_h, d / 2], (d, w), 1, 1.0, wall_material),
            Rectangle.axis_aligned("Wall Front", [0.0, -half_h, d / 2], (d, w), 1, -1.0, wall_material),
        ]
        if record_recipe:
            project.cavity_recipe = {
                "width": width,
                "height": height,
                "depth": depth,
                "wall_angle_x_deg": float(wall_angle_x_deg),
                "wall_angle_y_deg": float(wall_angle_y_deg),
                "floor_material": floor_material,
                "wall_material": wall_material,
            }
        return

    wall_h_x = d / max(cos_tx, 1e-9)
    wall_h_y = d / max(cos_ty, 1e-9)
    d_out_x = d * tan_tx / 2.0
    d_out_y = d * tan_ty / 2.0

    project.surfaces.append(
        Rectangle(
            name="Wall Right",
            center=np.array([half_w + d_out_x, 0.0, d / 2.0]),
            u_axis=np.array([0.0, 1.0, 0.0]),
            v_axis=np.array([sin_tx, 0.0, cos_tx]),
            size=(h, wall_h_x),
            material_name=wall_material,
        )
    )

    project.surfaces.append(
        Rectangle(
            name="Wall Left",
            center=np.array([-(half_w + d_out_x), 0.0, d / 2.0]),
            u_axis=np.array([0.0, -1.0, 0.0]),
            v_axis=np.array([-sin_tx, 0.0, cos_tx]),
            size=(h, wall_h_x),
            material_name=wall_material,
        )
    )

    project.surfaces.append(
        Rectangle(
            name="Wall Back",
            center=np.array([0.0, half_h + d_out_y, d / 2.0]),
            u_axis=np.array([-1.0, 0.0, 0.0]),
            v_axis=np.array([0.0, sin_ty, cos_ty]),
            size=(w, wall_h_y),
            material_name=wall_material,
        )
    )

    project.surfaces.append(
        Rectangle(
            name="Wall Front",
            center=np.array([0.0, -(half_h + d_out_y), d / 2.0]),
            u_axis=np.array([1.0, 0.0, 0.0]),
            v_axis=np.array([0.0, -sin_ty, cos_ty]),
            size=(w, wall_h_y),
            material_name=wall_material,
        )
    )

    if record_recipe:
        project.cavity_recipe = {
            "width": width,
            "height": height,
            "depth": depth,
            "wall_angle_x_deg": float(wall_angle_x_deg),
            "wall_angle_y_deg": float(wall_angle_y_deg),
            "floor_material": floor_material,
            "wall_material": wall_material,
        }


def build_optical_stack(
    project: Project,
    width: float,
    height: float,
    depth: float,
    diffuser_distance: float = 0.0,
    film_distances: list[float] | None = None,
    diffuser_material: str = "diffuser",
    film_material: str = "default_reflector",
    wall_angle_x_deg: float = 0.0,
    wall_angle_y_deg: float = 0.0,
) -> int:
    """Add diffuser and film placeholder surfaces above the cavity floor.

    diffuser_distance: Z height for the diffuser (0 = skip).
    film_distances: list of Z heights for additional film placeholders.

    Returns the number of surfaces added.
    """
    count = 0
    tan_x = float(np.tan(np.radians(wall_angle_x_deg)))
    tan_y = float(np.tan(np.radians(wall_angle_y_deg)))

    def _size_at_z(z: float) -> tuple[float, float]:
        return (width + 2 * z * tan_x, height + 2 * z * tan_y)

    if diffuser_distance > 0:
        sz = _size_at_z(diffuser_distance)
        project.surfaces.append(
            Rectangle.axis_aligned(
                "Diffuser",
                [0.0, 0.0, diffuser_distance],
                sz, 2, 1.0, diffuser_material,
            )
        )
        count += 1

    if film_distances:
        for i, z in enumerate(film_distances):
            if z <= 0:
                continue
            sz = _size_at_z(z)
            project.surfaces.append(
                Rectangle.axis_aligned(
                    f"Film_{i + 1}",
                    [0.0, 0.0, z],
                    sz, 2, 1.0, film_material,
                )
            )
            count += 1

    return count


def build_led_grid(
    project: Project,
    width: float,
    height: float,
    pitch_x: float,
    pitch_y: float,
    edge_offset_x: float,
    edge_offset_y: float,
    led_flux: float,
    distribution: str,
    z_offset: float = 0.5,
    replace_existing: bool = True,
    count_x: int | None = None,
    count_y: int | None = None,
) -> int:
    """Create a uniform LED grid and add PointSources to *project*.

    If count_x and count_y are given, pitch_x and pitch_y are ignored and
    computed so that that many LEDs fit with the given edge offsets:
    pitch = (span - 2*offset) / max(count - 1, 1).

    Returns the number of LEDs created.
    """
    if replace_existing:
        project.sources.clear()

    if count_x is not None and count_y is not None and count_x >= 1 and count_y >= 1:
        span_x = width - 2.0 * edge_offset_x
        span_y = height - 2.0 * edge_offset_y
        pitch_x = span_x / max(count_x - 1, 1) if span_x > 0 else pitch_x
        pitch_y = span_y / max(count_y - 1, 1) if span_y > 0 else pitch_y

    xs = _grid_positions(-width / 2, width / 2, pitch_x, edge_offset_x)
    ys = _grid_positions(-height / 2, height / 2, pitch_y, edge_offset_y)

    count = 0
    for row, y in enumerate(ys):
        for col, x in enumerate(xs):
            count += 1
            from backlight_sim.core.sources import PointSource

            project.sources.append(
                PointSource(
                    name=f"LED_r{row+1}_c{col+1}",
                    position=np.array([x, y, z_offset]),
                    flux=led_flux,
                    direction=np.array([0.0, 0.0, 1.0]),
                    distribution=distribution,
                )
            )
    return count


def _grid_positions(lo: float, hi: float, pitch: float, edge_offset: float) -> list[float]:
    if pitch <= 0:
        return []
    positions = []
    x = lo + edge_offset
    while x <= hi - edge_offset + 1e-9:
        positions.append(x)
        x += pitch
    return positions


def build_lgp_scene(
    project: Project,
    width: float = 80.0,
    height: float = 50.0,
    thickness: float = 3.0,
    lgp_center_z: float = 0.0,
    coupling_edges: list[str] | None = None,
    led_count: int = 6,
    led_flux: float = 100.0,
    led_distribution: str = "lambertian",
    detector_gap: float = 2.0,
    reflector_gap: float = 1.0,
    material_name: str = "pmma",
    refractive_index: float = 1.49,
) -> SolidBox:
    """Build a complete edge-lit LGP scene and add all objects to *project*.

    Creates:
    - A SolidBox (LGP slab) with the given dimensions
    - LEDs positioned at each coupling edge, evenly spaced
    - A flat detector above the top face
    - A reflector surface below the bottom face

    Parameters
    ----------
    project : Project
        The project to populate.
    width : float
        LGP X extent (mm).
    height : float
        LGP Y extent (mm).
    thickness : float
        LGP Z extent (mm).
    lgp_center_z : float
        Z-center of the slab.
    coupling_edges : list[str] or None
        Face IDs for coupling edges. Defaults to ["left"].
        Valid values from FACE_NAMES: "top", "bottom", "left", "right", "front", "back".
    led_count : int
        Number of LEDs per coupling edge.
    led_flux : float
        Flux per LED.
    led_distribution : str
        Angular distribution for LEDs.
    detector_gap : float
        Gap (mm) between the top face and the detector plane.
    reflector_gap : float
        Gap (mm) between the bottom face and the reflector surface.
    material_name : str
        Material name for the LGP. Creates a PMMA material if not already present.
    refractive_index : float
        Refractive index for the LGP material.

    Returns
    -------
    SolidBox
        The created LGP slab object.
    """
    if coupling_edges is None:
        coupling_edges = ["left"]

    # Create PMMA material if not present
    if material_name not in project.materials:
        project.materials[material_name] = Material(
            name=material_name,
            surface_type="reflector",
            reflectance=0.0,
            absorption=0.01,
            transmittance=0.0,
            refractive_index=refractive_index,
        )

    # Create bottom reflector optical properties if not present
    reflector_op_name = "lgp_bottom_reflector"
    if reflector_op_name not in project.optical_properties:
        project.optical_properties[reflector_op_name] = OpticalProperties(
            name=reflector_op_name,
            surface_type="reflector",
            reflectance=0.95,
            absorption=0.05,
            transmittance=0.0,
            is_diffuse=True,
        )

    # Create the SolidBox
    lgp = SolidBox(
        name="LGP",
        center=np.array([0.0, 0.0, lgp_center_z]),
        dimensions=(width, height, thickness),
        material_name=material_name,
        face_optics={"bottom": reflector_op_name},
        coupling_edges=list(coupling_edges),
    )
    project.solid_bodies.append(lgp)

    # Place LEDs at each coupling edge
    half_w = width / 2.0
    half_h = height / 2.0
    half_t = thickness / 2.0
    led_z = lgp_center_z  # LEDs at mid-thickness of slab

    led_idx = 0
    for edge_id in coupling_edges:
        if edge_id == "left":
            # Evenly spaced along Y at x = -(half_w + 0.5)
            edge_length = height
            spacing = edge_length / (led_count + 1)
            for i in range(led_count):
                led_idx += 1
                y_pos = -half_h + spacing * (i + 1)
                project.sources.append(PointSource(
                    name=f"LED_left_{i+1}",
                    position=np.array([-(half_w + 0.5), y_pos, led_z]),
                    flux=led_flux,
                    direction=np.array([1.0, 0.0, 0.0]),
                    distribution=led_distribution,
                ))
        elif edge_id == "right":
            edge_length = height
            spacing = edge_length / (led_count + 1)
            for i in range(led_count):
                led_idx += 1
                y_pos = -half_h + spacing * (i + 1)
                project.sources.append(PointSource(
                    name=f"LED_right_{i+1}",
                    position=np.array([half_w + 0.5, y_pos, led_z]),
                    flux=led_flux,
                    direction=np.array([-1.0, 0.0, 0.0]),
                    distribution=led_distribution,
                ))
        elif edge_id == "front":
            edge_length = width
            spacing = edge_length / (led_count + 1)
            for i in range(led_count):
                led_idx += 1
                x_pos = -half_w + spacing * (i + 1)
                project.sources.append(PointSource(
                    name=f"LED_front_{i+1}",
                    position=np.array([x_pos, -(half_h + 0.5), led_z]),
                    flux=led_flux,
                    direction=np.array([0.0, 1.0, 0.0]),
                    distribution=led_distribution,
                ))
        elif edge_id == "back":
            edge_length = width
            spacing = edge_length / (led_count + 1)
            for i in range(led_count):
                led_idx += 1
                x_pos = -half_w + spacing * (i + 1)
                project.sources.append(PointSource(
                    name=f"LED_back_{i+1}",
                    position=np.array([x_pos, half_h + 0.5, led_z]),
                    flux=led_flux,
                    direction=np.array([0.0, -1.0, 0.0]),
                    distribution=led_distribution,
                ))

    # Add detector above top face
    det_z = lgp_center_z + half_t + detector_gap
    project.detectors.append(
        DetectorSurface.axis_aligned(
            "top_detector",
            [0.0, 0.0, det_z],
            (width, height),
            2,
            1.0,
            (100, 100),
        )
    )

    # Add reflector surface below bottom face
    # Use a default material and apply the lgp_bottom_reflector optical properties override
    ref_z = lgp_center_z - half_t - reflector_gap
    bottom_rect = Rectangle.axis_aligned(
        "bottom_reflector",
        [0.0, 0.0, ref_z],
        (width * 1.2, height * 1.2),
        2,
        1.0,
        material_name,
    )
    bottom_rect.optical_properties_name = reflector_op_name
    project.surfaces.append(bottom_rect)

    return lgp
