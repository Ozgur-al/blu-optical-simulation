"""SolidBox — axis-aligned rectangular solid for refractive physics (LGP).

A SolidBox expands into 6 axis-aligned Rectangle faces via get_faces().
Each face carries the box material name and optional per-face optical
property override (face_optics dict).  The tracer identifies SolidBox
faces by the "::" separator in the face Rectangle name and applies
Fresnel/TIR physics instead of the regular reflect/absorb/diffuse path.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from backlight_sim.core.geometry import Rectangle

# Canonical face ordering
FACE_NAMES = ("top", "bottom", "left", "right", "front", "back")


@dataclass
class SolidBox:
    """Axis-aligned rectangular solid in 3D space.

    Parameters
    ----------
    name : str
        Unique scene name (used as prefix for face Rectangle names).
    center : array-like, shape (3,)
        World-space center of the box.
    dimensions : tuple[float, float, float]
        (Width along X, Height along Y, Depth along Z) in scene units.
    material_name : str
        Key into Project.materials — must have a ``refractive_index`` set.
    face_optics : dict[str, str]
        Optional per-face optical-properties overrides.
        Keys are face IDs from FACE_NAMES; values are
        optical_properties_name strings in the project.
    coupling_edges : list[str]
        Face IDs that are "coupling" edges (light enters here from LEDs).
        Reserved for future use; the tracer currently treats all faces
        identically with Fresnel physics.
    """

    name: str
    center: np.ndarray
    dimensions: tuple[float, float, float]   # (W, H, D)
    material_name: str = "pmma"
    face_optics: dict[str, str] = field(default_factory=dict)
    coupling_edges: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.center = np.asarray(self.center, dtype=float)

    # ------------------------------------------------------------------
    # Face geometry
    # ------------------------------------------------------------------

    def get_faces(self) -> list[Rectangle]:
        """Return 6 axis-aligned Rectangle faces with outward normals.

        Face layout (Z-up coordinate system):
          top    — center at z + D/2, normal +Z, size (W, H)
          bottom — center at z - D/2, normal -Z, size (W, H)
          right  — center at x + W/2, normal +X, size (H, D)
          left   — center at x - W/2, normal -X, size (H, D)
          back   — center at y + H/2, normal +Y, size (W, D)
          front  — center at y - H/2, normal -Y, size (W, D)

        Notes
        -----
        * Face names follow the pattern ``"{box_name}::{face_id}"``.
        * Faces without a face_optics override get
          ``optical_properties_name=""`` (falls back to material).
        """
        W, H, D = self.dimensions
        cx, cy, cz = self.center
        hw, hh, hd = W / 2.0, H / 2.0, D / 2.0

        # Each entry: (face_center, normal_axis, normal_sign, face_size)
        # normal_axis: 0=X, 1=Y, 2=Z  |  normal_sign: +1 or -1
        face_specs: dict[str, tuple] = {
            "top":    (np.array([cx,       cy,       cz + hd]), 2,  1.0, (W, H)),
            "bottom": (np.array([cx,       cy,       cz - hd]), 2, -1.0, (W, H)),
            "right":  (np.array([cx + hw,  cy,       cz     ]), 0,  1.0, (H, D)),
            "left":   (np.array([cx - hw,  cy,       cz     ]), 0, -1.0, (H, D)),
            "back":   (np.array([cx,       cy + hh,  cz     ]), 1,  1.0, (W, D)),
            "front":  (np.array([cx,       cy - hh,  cz     ]), 1, -1.0, (W, D)),
        }

        faces: list[Rectangle] = []
        for face_id, (center, axis, sign, size) in face_specs.items():
            rect = Rectangle.axis_aligned(
                name=f"{self.name}::{face_id}",
                center=center,
                size=size,
                normal_axis=axis,
                normal_sign=sign,
                material_name=self.material_name,
            )
            rect.optical_properties_name = self.face_optics.get(face_id, "")
            faces.append(rect)

        return faces
