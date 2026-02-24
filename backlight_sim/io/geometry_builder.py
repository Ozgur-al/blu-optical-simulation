"""Cavity geometry builder — pure logic, no GUI."""

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
    floor_material: str = "default_reflector",
    wall_material: str = "default_reflector",
    replace_existing: bool = True,
) -> None:
    """Generate floor + 4 walls and add them to *project.surfaces*.

    wall_angle_deg > 0 → cavity is wider at the top (output side).
    This is the typical concentrating reflector shape for backlight design.

    replace_existing=True clears existing surfaces before building.
    """
    if replace_existing:
        project.surfaces.clear()

    θ = np.radians(wall_angle_deg)
    sinθ, cosθ = float(np.sin(θ)), float(np.cos(θ))
    tanθ = float(np.tan(θ))
    D = float(depth)
    W, H = float(width), float(height)
    half_w, half_h = W / 2.0, H / 2.0

    # Floor — always axis-aligned
    project.surfaces.append(
        Rectangle.axis_aligned("Floor", [0.0, 0.0, 0.0], (W, H), 2, -1.0, floor_material)
    )

    if wall_angle_deg == 0.0:
        # Vertical walls — simple axis-aligned
        project.surfaces += [
            Rectangle.axis_aligned("Wall Right", [ half_w, 0.0, D/2], (H, D), 0,  1.0, wall_material),
            Rectangle.axis_aligned("Wall Left",  [-half_w, 0.0, D/2], (H, D), 0, -1.0, wall_material),
            Rectangle.axis_aligned("Wall Back",  [0.0,  half_h, D/2], (W, D), 1,  1.0, wall_material),
            Rectangle.axis_aligned("Wall Front", [0.0, -half_h, D/2], (W, D), 1, -1.0, wall_material),
        ]
        return

    # Tilted walls — general orientation
    wall_h = D / cosθ           # surface height along the wall
    d_out  = D * tanθ / 2.0    # extra x/y offset of wall centre vs cavity edge

    # Right wall  (outward normal = +x and slightly -z)
    # v_axis (bottom-to-top along wall): (sinθ, 0, cosθ)
    # u_axis: (0, -1, 0)  → cross((0,-1,0),(sinθ,0,cosθ)) = (-cosθ, 0, sinθ) but we need outward for right
    # Instead use u=(0,1,0) flipped: cross((0,1,0),(sinθ,0,cosθ)) = (cosθ,0,-sinθ) = outward right ✓
    project.surfaces.append(Rectangle(
        name="Wall Right",
        center=np.array([half_w + d_out, 0.0, D / 2.0]),
        u_axis=np.array([0.0, 1.0, 0.0]),
        v_axis=np.array([sinθ, 0.0, cosθ]),
        size=(H, wall_h),
        material_name=wall_material,
    ))

    # Left wall  (outward normal = -x and slightly -z)
    # cross((0,-1,0),(-sinθ,0,cosθ)) = (-cosθ,0,-sinθ) … still need to check sign
    # Use u=(0,-1,0), v=(-sinθ,0,cosθ) → cross = (-cosθ,0,-sinθ) → outward left ✓
    project.surfaces.append(Rectangle(
        name="Wall Left",
        center=np.array([-(half_w + d_out), 0.0, D / 2.0]),
        u_axis=np.array([0.0, -1.0, 0.0]),
        v_axis=np.array([-sinθ, 0.0, cosθ]),
        size=(H, wall_h),
        material_name=wall_material,
    ))

    # Back wall  (outward normal = +y and slightly -z)
    # u=(1,0,0), v=(0,sinθ,cosθ) → cross=(0*cosθ-0*sinθ, 0*0-1*cosθ, 1*sinθ-0*0)=(0,-cosθ,sinθ) — wrong sign
    # Try u=(-1,0,0), v=(0,sinθ,cosθ) → cross=(0*cosθ-cosθ*sinθ... let me be explicit:
    # cross((-1,0,0),(0,sinθ,cosθ))=(0*cosθ-0*sinθ, 0*0-(-1)*cosθ, (-1)*sinθ-0*0)=(0,cosθ,-sinθ) = outward back ✓
    project.surfaces.append(Rectangle(
        name="Wall Back",
        center=np.array([0.0, half_h + d_out, D / 2.0]),
        u_axis=np.array([-1.0, 0.0, 0.0]),
        v_axis=np.array([0.0, sinθ, cosθ]),
        size=(W, wall_h),
        material_name=wall_material,
    ))

    # Front wall  (outward normal = -y and slightly -z)
    # u=(1,0,0), v=(0,-sinθ,cosθ) → cross=(0*cosθ-cosθ*(-sinθ), cosθ*0-1*cosθ... explicit:
    # cross((1,0,0),(0,-sinθ,cosθ))=(0*cosθ-0*(-sinθ), 0*0-1*cosθ, 1*(-sinθ)-0*0)=(0,-cosθ,-sinθ) = outward front ✓
    project.surfaces.append(Rectangle(
        name="Wall Front",
        center=np.array([0.0, -(half_h + d_out), D / 2.0]),
        u_axis=np.array([1.0, 0.0, 0.0]),
        v_axis=np.array([0.0, -sinθ, cosθ]),
        size=(W, wall_h),
        material_name=wall_material,
    ))


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
) -> int:
    """Create a uniform LED grid and add PointSources to *project*.

    Returns the number of LEDs created.
    """
    if replace_existing:
        project.sources.clear()

    xs = _grid_positions(-width / 2, width / 2, pitch_x, edge_offset_x)
    ys = _grid_positions(-height / 2, height / 2, pitch_y, edge_offset_y)

    count = 0
    for row, y in enumerate(ys):
        for col, x in enumerate(xs):
            count += 1
            from backlight_sim.core.sources import PointSource
            project.sources.append(PointSource(
                name=f"LED_r{row+1}_c{col+1}",
                position=np.array([x, y, z_offset]),
                flux=led_flux,
                direction=np.array([0.0, 0.0, 1.0]),
                distribution=distribution,
            ))
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
