"""Cavity geometry builder - pure logic, no GUI."""

from __future__ import annotations

import numpy as np

from backlight_sim.core.geometry import Rectangle
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
