"""JSON project save / load."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from backlight_sim.core.geometry import Rectangle
from backlight_sim.core.materials import Material, default_color_for_surface_type
from backlight_sim.core.sources import PointSource
from backlight_sim.core.detectors import DetectorSurface
from backlight_sim.core.project_model import Project, SimulationSettings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _v(arr) -> list:
    return np.asarray(arr).tolist()


def _a(lst) -> np.ndarray:
    return np.array(lst, dtype=float)


# ---------------------------------------------------------------------------
# Serialise
# ---------------------------------------------------------------------------

def _rect_to_dict(r: Rectangle) -> dict:
    return {
        "name": r.name,
        "center": _v(r.center),
        "u_axis": _v(r.u_axis),
        "v_axis": _v(r.v_axis),
        "size": list(r.size),
        "material_name": r.material_name,
    }


def _det_to_dict(d: DetectorSurface) -> dict:
    return {
        "name": d.name,
        "center": _v(d.center),
        "u_axis": _v(d.u_axis),
        "v_axis": _v(d.v_axis),
        "size": list(d.size),
        "resolution": list(d.resolution),
    }


def _src_to_dict(s: PointSource) -> dict:
    return {
        "name": s.name,
        "position": _v(s.position),
        "flux": s.flux,
        "direction": _v(s.direction),
        "distribution": s.distribution,
        "enabled": s.enabled,
    }


def _mat_to_dict(m: Material) -> dict:
    return {
        "name": m.name,
        "surface_type": m.surface_type,
        "reflectance": m.reflectance,
        "absorption": m.absorption,
        "transmittance": m.transmittance,
        "is_diffuse": m.is_diffuse,
        "color": list(m.color) if m.color is not None else None,
    }


def project_to_dict(project: Project) -> dict:
    s = project.settings
    return {
        "name": project.name,
        "settings": {
            "rays_per_source": s.rays_per_source,
            "max_bounces": s.max_bounces,
            "energy_threshold": s.energy_threshold,
            "random_seed": s.random_seed,
            "record_ray_paths": s.record_ray_paths,
            "distance_unit": s.distance_unit,
        },
        "angular_distributions": project.angular_distributions,
        "materials": [_mat_to_dict(m) for m in project.materials.values()],
        "sources": [_src_to_dict(src) for src in project.sources],
        "surfaces": [_rect_to_dict(r) for r in project.surfaces],
        "detectors": [_det_to_dict(d) for d in project.detectors],
    }


def save_project(project: Project, path: str | Path):
    data = project_to_dict(project)
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Deserialise
# ---------------------------------------------------------------------------

def _dict_to_rect(d: dict) -> Rectangle:
    return Rectangle(
        name=d["name"],
        center=_a(d["center"]),
        u_axis=_a(d["u_axis"]),
        v_axis=_a(d["v_axis"]),
        size=tuple(d["size"]),
        material_name=d.get("material_name", "default_reflector"),
    )


def _dict_to_det(d: dict) -> DetectorSurface:
    return DetectorSurface(
        name=d["name"],
        center=_a(d["center"]),
        u_axis=_a(d["u_axis"]),
        v_axis=_a(d["v_axis"]),
        size=tuple(d["size"]),
        resolution=tuple(d.get("resolution", [100, 100])),
    )


def _dict_to_src(d: dict) -> PointSource:
    return PointSource(
        name=d["name"],
        position=_a(d["position"]),
        flux=d.get("flux", 100.0),
        direction=_a(d.get("direction", [0, 0, 1])),
        distribution=d.get("distribution", "isotropic"),
        enabled=d.get("enabled", True),
    )


def _dict_to_mat(d: dict) -> Material:
    surface_type = d.get("surface_type", "reflector")
    color = d.get("color", None)
    if color is None:
        color = default_color_for_surface_type(surface_type)
    return Material(
        name=d["name"],
        surface_type=surface_type,
        reflectance=d.get("reflectance", 0.9),
        absorption=d.get("absorption", 0.1),
        transmittance=d.get("transmittance", 0.0),
        is_diffuse=d.get("is_diffuse", True),
        color=tuple(color),
    )


def load_project(path: str | Path) -> Project:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    s = data.get("settings", {})
    settings = SimulationSettings(
        rays_per_source=s.get("rays_per_source", 10_000),
        max_bounces=s.get("max_bounces", 50),
        energy_threshold=s.get("energy_threshold", 0.001),
        random_seed=s.get("random_seed", 42),
        record_ray_paths=s.get("record_ray_paths", 200),
        distance_unit=s.get("distance_unit", "mm"),
    )
    materials = {d["name"]: _dict_to_mat(d) for d in data.get("materials", [])}
    distributions = data.get("angular_distributions", {})
    return Project(
        name=data.get("name", "Untitled"),
        settings=settings,
        materials=materials,
        sources=[_dict_to_src(d) for d in data.get("sources", [])],
        surfaces=[_dict_to_rect(d) for d in data.get("surfaces", [])],
        detectors=[_dict_to_det(d) for d in data.get("detectors", [])],
        angular_distributions=distributions,
    )
