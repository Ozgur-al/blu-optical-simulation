"""Built-in project presets."""

from __future__ import annotations

import numpy as np

from backlight_sim.core.geometry import Rectangle
from backlight_sim.core.materials import Material
from backlight_sim.core.sources import PointSource
from backlight_sim.core.detectors import DetectorSurface
from backlight_sim.core.project_model import Project, SimulationSettings
from backlight_sim.io.geometry_builder import build_cavity, build_lgp_scene


def preset_simple_box() -> Project:
    """Single LED in a 50×50×20 mm reflective box with a detector on top."""
    project = Project(name="Simple Box")
    project.settings = SimulationSettings(rays_per_source=20_000, distance_unit="mm")

    project.materials["white_reflector"] = Material(
        "white_reflector", "reflector", reflectance=0.92, absorption=0.08
    )
    project.materials["absorber"] = Material(
        "absorber", "absorber", reflectance=0.0, absorption=1.0
    )

    W, H, D = 50.0, 50.0, 20.0
    build_cavity(project, W, H, D,
                 wall_angle_deg=0.0,
                 floor_material="white_reflector",
                 wall_material="white_reflector")

    project.detectors.append(
        DetectorSurface.axis_aligned("Output Plane", [0, 0, D], (W, H), 2, 1.0, (100, 100))
    )

    project.sources.append(
        PointSource("LED_1", np.array([0.0, 0.0, 0.5]),
                    flux=100.0, direction=np.array([0, 0, 1]),
                    distribution="lambertian")
    )
    return project


def preset_automotive_cluster() -> Project:
    """Automotive cluster backlight: 120×60×10 mm with a 4×2 LED grid."""
    project = Project(name="Automotive Cluster Direct-Lit")
    project.settings = SimulationSettings(
        rays_per_source=15_000, max_bounces=60, distance_unit="mm"
    )

    project.materials["white_reflector"] = Material(
        "white_reflector", "reflector", reflectance=0.92, absorption=0.08
    )

    W, H, D = 120.0, 60.0, 10.0
    build_cavity(project, W, H, D,
                 wall_angle_deg=10.0,
                 floor_material="white_reflector",
                 wall_material="white_reflector")

    project.detectors.append(
        DetectorSurface.axis_aligned(
            "Output Plane", [0, 0, D],
            (W + 2 * D * np.tan(np.radians(10.0)),
             H + 2 * D * np.tan(np.radians(10.0))),
            2, 1.0, (120, 60)
        )
    )

    # 4 columns × 2 rows, centered in the cavity
    n_col, n_row = 4, 2
    pitch_x, pitch_y = 25.0, 20.0
    for col in range(n_col):
        for row in range(n_row):
            x = (col - (n_col - 1) / 2.0) * pitch_x
            y = (row - (n_row - 1) / 2.0) * pitch_y
            project.sources.append(
                PointSource(f"LED_{col+1}_{row+1}", np.array([x, y, 0.5]),
                            flux=80.0, direction=np.array([0, 0, 1]),
                            distribution="lambertian")
            )
    return project


def preset_edge_lit_lgp() -> Project:
    """Edge-lit LGP: 310×120×2 mm slab with 36 LEDs on the front (bottom-long) edge."""
    project = Project(name="Edge-Lit LGP")
    project.settings.rays_per_source = 10_000
    project.settings.max_bounces = 200  # LGP needs many bounces for TIR propagation
    build_lgp_scene(project, width=310.0, height=120.0, thickness=2.0,
                    coupling_edges=["front"], led_count=36, led_flux=100.0)
    return project


PRESETS: dict[str, callable] = {
    "Simple Box (50×50×20 mm)": preset_simple_box,
    "Automotive Cluster (120×60×10 mm)": preset_automotive_cluster,
    "Edge-Lit LGP (310×120×2 mm)": preset_edge_lit_lgp,
}
