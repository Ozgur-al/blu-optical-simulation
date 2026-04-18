"""JSON project save / load."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from backlight_sim.core.geometry import Rectangle
from backlight_sim.core.materials import Material, OpticalProperties, default_color_for_surface_type
from backlight_sim.core.sources import PointSource
from backlight_sim.core.detectors import DetectorSurface, SphereDetector
from backlight_sim.core.project_model import Project, SimulationSettings
from backlight_sim.core.solid_body import SolidBox, SolidCylinder, SolidPrism


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
    d = {
        "name": r.name,
        "center": _v(r.center),
        "u_axis": _v(r.u_axis),
        "v_axis": _v(r.v_axis),
        "size": list(r.size),
        "material_name": r.material_name,
    }
    if r.optical_properties_name:
        d["optical_properties_name"] = r.optical_properties_name
    return d


def _det_to_dict(d: DetectorSurface) -> dict:
    return {
        "name": d.name,
        "center": _v(d.center),
        "u_axis": _v(d.u_axis),
        "v_axis": _v(d.v_axis),
        "size": list(d.size),
        "resolution": list(d.resolution),
    }


def _sph_det_to_dict(d: SphereDetector) -> dict:
    return {
        "name": d.name,
        "center": _v(d.center),
        "radius": d.radius,
        "resolution": list(d.resolution),
        "mode": d.mode,
    }


def _src_to_dict(s: PointSource) -> dict:
    return {
        "name": s.name,
        "position": _v(s.position),
        "flux": s.flux,
        "direction": _v(s.direction),
        "distribution": s.distribution,
        "enabled": s.enabled,
        "flux_tolerance": s.flux_tolerance,
        "current_mA": s.current_mA,
        "flux_per_mA": s.flux_per_mA,
        "thermal_derate": s.thermal_derate,
        "color_rgb": list(s.color_rgb),
        "spd": s.spd,
    }


def _mat_to_dict(m: Material) -> dict:
    return {
        "name": m.name,
        "surface_type": m.surface_type,
        "reflectance": m.reflectance,
        "absorption": m.absorption,
        "transmittance": m.transmittance,
        "is_diffuse": m.is_diffuse,
        "haze": m.haze,
        "refractive_index": m.refractive_index,
        "bsdf_profile_name": getattr(m, "bsdf_profile_name", ""),
        "color": list(m.color) if m.color is not None else None,
    }


def _op_to_dict(op: OpticalProperties) -> dict:
    return {
        "name": op.name,
        "surface_type": op.surface_type,
        "reflectance": op.reflectance,
        "absorption": op.absorption,
        "transmittance": op.transmittance,
        "is_diffuse": op.is_diffuse,
        "haze": op.haze,
        "bsdf_profile_name": op.bsdf_profile_name,
        "color": list(op.color) if op.color is not None else None,
    }


def _solid_cylinder_to_dict(c: SolidCylinder) -> dict:
    return {
        "name": c.name,
        "center": _v(c.center),
        "axis": _v(c.axis),
        "radius": c.radius,
        "length": c.length,
        "material_name": c.material_name,
        "face_optics": c.face_optics,
    }


def _solid_prism_to_dict(p: SolidPrism) -> dict:
    return {
        "name": p.name,
        "center": _v(p.center),
        "axis": _v(p.axis),
        "n_sides": p.n_sides,
        "circumscribed_radius": p.circumscribed_radius,
        "length": p.length,
        "material_name": p.material_name,
        "face_optics": p.face_optics,
    }


def _dict_to_solid_cylinder(d: dict) -> SolidCylinder:
    return SolidCylinder(
        name=d["name"],
        center=_a(d["center"]),
        axis=_a(d["axis"]),
        radius=d.get("radius", 5.0),
        length=d.get("length", 10.0),
        material_name=d.get("material_name", "pmma"),
        face_optics=d.get("face_optics", {}),
    )


def _dict_to_solid_prism(d: dict) -> SolidPrism:
    return SolidPrism(
        name=d["name"],
        center=_a(d["center"]),
        axis=_a(d["axis"]),
        n_sides=d.get("n_sides", 6),
        circumscribed_radius=d.get("circumscribed_radius", 5.0),
        length=d.get("length", 10.0),
        material_name=d.get("material_name", "pmma"),
        face_optics=d.get("face_optics", {}),
    )


def _solid_box_to_dict(b: SolidBox) -> dict:
    return {
        "name": b.name,
        "center": _v(b.center),
        "dimensions": list(b.dimensions),
        "material_name": b.material_name,
        "face_optics": b.face_optics,
        "coupling_edges": b.coupling_edges,
    }


def _dict_to_solid_box(d: dict) -> SolidBox:
    return SolidBox(
        name=d["name"],
        center=_a(d["center"]),
        dimensions=tuple(d["dimensions"]),
        material_name=d.get("material_name", "pmma"),
        face_optics=d.get("face_optics", {}),
        coupling_edges=d.get("coupling_edges", []),
    )


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
            "flux_unit": s.flux_unit,
            "angle_unit": s.angle_unit,
            "use_multiprocessing": s.use_multiprocessing,
            "adaptive_sampling": s.adaptive_sampling,
            "convergence_cv_target": s.convergence_cv_target,
            "check_interval": s.check_interval,
            "uq_batches": s.uq_batches,
            "uq_include_spectral": s.uq_include_spectral,
        },
        "angular_distributions": project.angular_distributions,
        "spd_profiles": project.spd_profiles,
        "spectral_material_data": project.spectral_material_data,
        "materials": [_mat_to_dict(m) for m in project.materials.values()],
        "optical_properties": [_op_to_dict(op) for op in project.optical_properties.values()],
        "sources": [_src_to_dict(src) for src in project.sources],
        "surfaces": [_rect_to_dict(r) for r in project.surfaces],
        "detectors": [_det_to_dict(d) for d in project.detectors],
        "sphere_detectors": [_sph_det_to_dict(d) for d in project.sphere_detectors],
        "solid_bodies": [_solid_box_to_dict(b) for b in project.solid_bodies],
        "solid_cylinders": [_solid_cylinder_to_dict(c) for c in getattr(project, "solid_cylinders", [])],
        "solid_prisms": [_solid_prism_to_dict(p) for p in getattr(project, "solid_prisms", [])],
        "bsdf_profiles": getattr(project, "bsdf_profiles", {}),
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
        optical_properties_name=d.get("optical_properties_name", ""),
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
        flux_tolerance=d.get("flux_tolerance", 0.0),
        current_mA=d.get("current_mA", 0.0),
        flux_per_mA=d.get("flux_per_mA", 0.0),
        thermal_derate=d.get("thermal_derate", 1.0),
        color_rgb=tuple(d.get("color_rgb", [1.0, 1.0, 1.0])),
        spd=d.get("spd", "white"),
    )


def _dict_to_sph_det(d: dict) -> SphereDetector:
    return SphereDetector(
        name=d["name"],
        center=_a(d["center"]),
        radius=d.get("radius", 10.0),
        resolution=tuple(d.get("resolution", [72, 36])),
        mode=d.get("mode", "near_field"),
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
        haze=d.get("haze", 0.0),
        refractive_index=d.get("refractive_index", 1.0),
        bsdf_profile_name=d.get("bsdf_profile_name", ""),
        color=tuple(color),
    )


def _dict_to_op(d: dict) -> OpticalProperties:
    surface_type = d.get("surface_type", "reflector")
    color = d.get("color", None)
    if color is None:
        color = default_color_for_surface_type(surface_type)
    return OpticalProperties(
        name=d["name"],
        surface_type=surface_type,
        reflectance=d.get("reflectance", 0.9),
        absorption=d.get("absorption", 0.1),
        transmittance=d.get("transmittance", 0.0),
        is_diffuse=d.get("is_diffuse", True),
        haze=d.get("haze", 0.0),
        bsdf_profile_name=d.get("bsdf_profile_name", ""),
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
        flux_unit=s.get("flux_unit", "lm"),
        angle_unit=s.get("angle_unit", "deg"),
        use_multiprocessing=s.get("use_multiprocessing", False),
        adaptive_sampling=s.get("adaptive_sampling", True),
        convergence_cv_target=s.get("convergence_cv_target", 2.0),
        check_interval=s.get("check_interval", 1000),
        uq_batches=s.get("uq_batches", 10),
        uq_include_spectral=s.get("uq_include_spectral", True),
    )
    materials = {d["name"]: _dict_to_mat(d) for d in data.get("materials", [])}
    opt_props = {d["name"]: _dict_to_op(d) for d in data.get("optical_properties", [])}
    distributions = data.get("angular_distributions", {})
    spd_profiles = data.get("spd_profiles", {})
    spectral_material_data = data.get("spectral_material_data", {})
    solid_bodies = [_dict_to_solid_box(d) for d in data.get("solid_bodies", [])]
    solid_cylinders = [_dict_to_solid_cylinder(d) for d in data.get("solid_cylinders", [])]
    solid_prisms = [_dict_to_solid_prism(d) for d in data.get("solid_prisms", [])]
    bsdf_profiles = data.get("bsdf_profiles", {})
    return Project(
        name=data.get("name", "Untitled"),
        settings=settings,
        materials=materials,
        optical_properties=opt_props,
        sources=[_dict_to_src(d) for d in data.get("sources", [])],
        surfaces=[_dict_to_rect(d) for d in data.get("surfaces", [])],
        detectors=[_dict_to_det(d) for d in data.get("detectors", [])],
        sphere_detectors=[_dict_to_sph_det(d) for d in data.get("sphere_detectors", [])],
        angular_distributions=distributions,
        spd_profiles=spd_profiles,
        spectral_material_data=spectral_material_data,
        solid_bodies=solid_bodies,
        solid_cylinders=solid_cylinders,
        solid_prisms=solid_prisms,
        bsdf_profiles=bsdf_profiles,
    )
