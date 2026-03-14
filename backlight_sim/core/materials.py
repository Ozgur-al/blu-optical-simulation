from __future__ import annotations

from dataclasses import dataclass


def default_color_for_surface_type(surface_type: str) -> tuple[float, float, float]:
    if surface_type == "absorber":
        return (0.9, 0.2, 0.2)
    if surface_type == "diffuser":
        return (0.2, 0.85, 0.2)
    return (0.55, 0.65, 1.0)


@dataclass
class OpticalProperties:
    """Per-surface optical behavior (coating/finish).

    surface_type controls behavior:
      - "reflector": reflects rays (diffuse or specular), absorbs remainder
      - "absorber": absorbs all incoming light
      - "diffuser": transmits a fraction through (scattered), reflects remainder

    When bsdf_profile_name is non-empty, it references a key in
    project.bsdf_profiles, and the scalar reflectance/transmittance fields
    are bypassed — the BSDF table drives scattering instead.
    """

    name: str
    surface_type: str = "reflector"
    reflectance: float = 0.9
    absorption: float = 0.1
    transmittance: float = 0.0
    is_diffuse: bool = True
    haze: float = 0.0
    color: tuple[float, float, float] | None = None
    bsdf_profile_name: str = ""  # key into Project.bsdf_profiles; "" = disabled

    def __post_init__(self):
        if self.color is None:
            self.color = default_color_for_surface_type(self.surface_type)
        if len(self.color) != 3:
            self.color = default_color_for_surface_type(self.surface_type)
        self.color = tuple(max(0.0, min(1.0, float(c))) for c in self.color)


@dataclass
class Material:
    """Material definition — bulk optical properties.

    For backward compatibility, Material retains all the old surface_type fields.
    New code should use OpticalProperties for per-surface coatings and
    Material primarily for refractive_index.

    The tracer resolves optical behavior via:
      1. If the surface has an optical_properties_name → use that OpticalProperties
      2. Else fall back to the Material referenced by material_name (legacy behavior)
    """

    name: str
    surface_type: str = "reflector"  # "reflector", "absorber", "diffuser"
    reflectance: float = 0.9
    absorption: float = 0.1
    transmittance: float = 0.0  # fraction passing through (for diffusers)
    is_diffuse: bool = True  # True = Lambertian, False = specular
    haze: float = 0.0  # forward-scatter half-angle in degrees (0 = no haze)
    refractive_index: float = 1.0  # index of refraction (for future TIR/Fresnel)
    bsdf_profile_name: str = ""  # key into Project.bsdf_profiles; "" = disabled
    color: tuple[float, float, float] | None = None

    def __post_init__(self):
        if self.color is None:
            self.color = default_color_for_surface_type(self.surface_type)
        if len(self.color) != 3:
            self.color = default_color_for_surface_type(self.surface_type)
        self.color = tuple(max(0.0, min(1.0, float(c))) for c in self.color)

    def to_optical_properties(self) -> OpticalProperties:
        """Convert legacy Material fields to an OpticalProperties instance."""
        return OpticalProperties(
            name=self.name,
            surface_type=self.surface_type,
            reflectance=self.reflectance,
            absorption=self.absorption,
            transmittance=self.transmittance,
            is_diffuse=self.is_diffuse,
            haze=self.haze,
            color=self.color,
        )
