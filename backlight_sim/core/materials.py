from __future__ import annotations

from dataclasses import dataclass


def default_color_for_surface_type(surface_type: str) -> tuple[float, float, float]:
    if surface_type == "absorber":
        return (0.9, 0.2, 0.2)
    if surface_type == "diffuser":
        return (0.2, 0.85, 0.2)
    return (0.55, 0.65, 1.0)


@dataclass
class Material:
    """Optical surface material properties.

    surface_type controls behavior:
      - "reflector": reflects rays (diffuse or specular), absorbs remainder
      - "absorber": absorbs all incoming light
      - "diffuser": transmits a fraction through (scattered), reflects remainder
    """

    name: str
    surface_type: str = "reflector"  # "reflector", "absorber", "diffuser"
    reflectance: float = 0.9
    absorption: float = 0.1
    transmittance: float = 0.0  # fraction passing through (for diffusers)
    is_diffuse: bool = True  # True = Lambertian, False = specular
    color: tuple[float, float, float] | None = None

    def __post_init__(self):
        if self.color is None:
            self.color = default_color_for_surface_type(self.surface_type)
        if len(self.color) != 3:
            self.color = default_color_for_surface_type(self.surface_type)
        self.color = tuple(max(0.0, min(1.0, float(c))) for c in self.color)
