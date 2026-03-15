"""SolidBox, SolidCylinder, SolidPrism — refractive solid body primitives.

SolidBox expands into 6 axis-aligned Rectangle faces via get_faces().
SolidCylinder expands into 3 face-like objects (top_cap, bottom_cap, side).
SolidPrism expands into (2 + n_sides) face-like objects.

Each face carries the body material name and optional per-face optical
property override (face_optics dict).  The tracer identifies solid body
faces by the "::" separator in the face name and applies Fresnel/TIR
physics instead of the regular reflect/absorb/diffuse path.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from backlight_sim.core.geometry import Rectangle

# Canonical face ordering for SolidBox
FACE_NAMES = ("top", "bottom", "left", "right", "front", "back")

# Canonical face ordering for SolidCylinder
CYLINDER_FACE_NAMES = ("top_cap", "bottom_cap", "side")


# ---------------------------------------------------------------------------
# Lightweight face objects for cylinder / prism (not Rectangle)
# ---------------------------------------------------------------------------

@dataclass
class CylinderCap:
    """Disc-shaped end cap of a SolidCylinder."""

    name: str
    center: np.ndarray        # (3,) world center of cap disc
    normal: np.ndarray        # (3,) outward normal (along axis)
    radius: float
    material_name: str = "pmma"
    optical_properties_name: str = ""

    def __post_init__(self):
        self.center = np.asarray(self.center, dtype=float)
        self.normal = np.asarray(self.normal, dtype=float)
        n = np.linalg.norm(self.normal)
        if n > 0:
            self.normal = self.normal / n


@dataclass
class CylinderSide:
    """Curved side surface of a SolidCylinder."""

    name: str
    center: np.ndarray        # (3,) world center of the cylinder
    axis: np.ndarray          # (3,) normalized cylinder axis
    radius: float
    length: float
    material_name: str = "pmma"
    optical_properties_name: str = ""

    def __post_init__(self):
        self.center = np.asarray(self.center, dtype=float)
        self.axis = np.asarray(self.axis, dtype=float)
        n = np.linalg.norm(self.axis)
        if n > 0:
            self.axis = self.axis / n


@dataclass
class PrismCap:
    """Polygonal end cap of a SolidPrism."""

    name: str
    center: np.ndarray         # (3,) world center of cap polygon
    normal: np.ndarray         # (3,) outward normal (along axis)
    # Orthonormal basis vectors in the cap plane (for local coordinate transform)
    u_axis: np.ndarray         # (3,) first in-plane axis
    v_axis: np.ndarray         # (3,) second in-plane axis
    n_sides: int
    circumscribed_radius: float
    # Precomputed for containment test (in local 2D u/v coords):
    vertices_2d: np.ndarray    # (n_sides, 2) polygon vertices
    edge_normals_2d: np.ndarray  # (n_sides, 2) outward edge normals
    material_name: str = "pmma"
    optical_properties_name: str = ""

    def __post_init__(self):
        self.center = np.asarray(self.center, dtype=float)
        self.normal = np.asarray(self.normal, dtype=float)
        self.u_axis = np.asarray(self.u_axis, dtype=float)
        self.v_axis = np.asarray(self.v_axis, dtype=float)
        self.vertices_2d = np.asarray(self.vertices_2d, dtype=float)
        self.edge_normals_2d = np.asarray(self.edge_normals_2d, dtype=float)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _perpendicular_basis(axis: np.ndarray):
    """Return (u, v) orthonormal vectors perpendicular to *axis*."""
    axis = axis / np.linalg.norm(axis)
    ref = np.array([1.0, 0.0, 0.0])
    if abs(np.dot(axis, ref)) > 0.9:
        ref = np.array([0.0, 1.0, 0.0])
    u = np.cross(axis, ref)
    u = u / np.linalg.norm(u)
    v = np.cross(axis, u)
    v = v / np.linalg.norm(v)
    return u, v


def _compute_polygon_vertices(n_sides: int, radius: float) -> np.ndarray:
    """Return (n_sides, 2) vertices of a regular polygon in local u/v plane."""
    angles = np.linspace(0.0, 2.0 * np.pi, n_sides, endpoint=False)
    return radius * np.column_stack([np.cos(angles), np.sin(angles)])


def _compute_edge_normals(vertices_2d: np.ndarray) -> np.ndarray:
    """Return (n_sides, 2) outward edge normals for a CCW convex polygon."""
    n = len(vertices_2d)
    normals = np.zeros((n, 2), dtype=float)
    for i in range(n):
        a = vertices_2d[i]
        b = vertices_2d[(i + 1) % n]
        edge = b - a
        # For a CCW polygon the outward normal is (edge_y, -edge_x)
        normals[i] = np.array([edge[1], -edge[0]])
        ln = np.linalg.norm(normals[i])
        if ln > 0:
            normals[i] /= ln
    return normals


# ---------------------------------------------------------------------------
# SolidBox
# ---------------------------------------------------------------------------

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

    def get_faces(self) -> list[Rectangle]:
        """Return 6 axis-aligned Rectangle faces with outward normals.

        Face layout (Z-up coordinate system):
          top    — center at z + D/2, normal +Z, size (W, H)
          bottom — center at z - D/2, normal -Z, size (W, H)
          right  — center at x + W/2, normal +X, size (H, D)
          left   — center at x - W/2, normal -X, size (H, D)
          back   — center at y + H/2, normal +Y, size (W, D)
          front  — center at y - H/2, normal -Y, size (W, D)
        """
        W, H, D = self.dimensions
        cx, cy, cz = self.center
        hw, hh, hd = W / 2.0, H / 2.0, D / 2.0

        face_specs: dict[str, tuple] = {
            "top":    (np.array([cx,       cy,       cz + hd]), 2,  1.0, (W, H)),
            "bottom": (np.array([cx,       cy,       cz - hd]), 2, -1.0, (W, H)),
            "right":  (np.array([cx + hw,  cy,       cz     ]), 0,  1.0, (H, D)),
            "left":   (np.array([cx - hw,  cy,       cz     ]), 0, -1.0, (H, D)),
            "back":   (np.array([cx,       cy + hh,  cz     ]), 1,  1.0, (D, W)),
            "front":  (np.array([cx,       cy - hh,  cz     ]), 1, -1.0, (D, W)),
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


# ---------------------------------------------------------------------------
# SolidCylinder
# ---------------------------------------------------------------------------

@dataclass
class SolidCylinder:
    """Cylinder solid body for refractive physics.

    Expands into 3 face objects: top_cap (CylinderCap), bottom_cap
    (CylinderCap), and side (CylinderSide).  All use the ``"::"`` naming
    convention so the tracer applies Fresnel/TIR physics.

    Parameters
    ----------
    name : str
        Unique scene name.
    center : array-like, shape (3,)
        World-space center (mid-point of the cylinder axis).
    axis : array-like, shape (3,)
        Direction of the cylinder axis (need not be normalized).
    radius : float
        Radius of the cylinder cross-section.
    length : float
        Total length along the axis.
    material_name : str
        Key into Project.materials.
    face_optics : dict[str, str]
        Per-face optical override.  Keys: "top_cap", "bottom_cap", "side".
    """

    name: str
    center: np.ndarray
    axis: np.ndarray
    radius: float = 5.0
    length: float = 10.0
    material_name: str = "pmma"
    face_optics: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        self.center = np.asarray(self.center, dtype=float)
        self.axis = np.asarray(self.axis, dtype=float)
        n = np.linalg.norm(self.axis)
        if n > 0:
            self.axis = self.axis / n

    def get_faces(self) -> list:
        """Return [top_cap, bottom_cap, side] face objects."""
        half = self.length / 2.0
        top_center = self.center + self.axis * half
        bot_center = self.center - self.axis * half

        top_cap = CylinderCap(
            name=f"{self.name}::top_cap",
            center=top_center,
            normal=self.axis.copy(),
            radius=self.radius,
            material_name=self.material_name,
            optical_properties_name=self.face_optics.get("top_cap", ""),
        )
        bot_cap = CylinderCap(
            name=f"{self.name}::bottom_cap",
            center=bot_center,
            normal=-self.axis.copy(),
            radius=self.radius,
            material_name=self.material_name,
            optical_properties_name=self.face_optics.get("bottom_cap", ""),
        )
        side = CylinderSide(
            name=f"{self.name}::side",
            center=self.center.copy(),
            axis=self.axis.copy(),
            radius=self.radius,
            length=self.length,
            material_name=self.material_name,
            optical_properties_name=self.face_optics.get("side", ""),
        )
        return [top_cap, bot_cap, side]


# ---------------------------------------------------------------------------
# SolidPrism
# ---------------------------------------------------------------------------

@dataclass
class SolidPrism:
    """Regular polygonal prism solid body for refractive physics.

    Expands into (2 + n_sides) face objects: cap_top (PrismCap),
    cap_bottom (PrismCap), and side_0 ... side_{n_sides-1} (Rectangle).

    Parameters
    ----------
    name : str
        Unique scene name.
    center : array-like, shape (3,)
        World-space center (mid-point of the prism axis).
    axis : array-like, shape (3,)
        Direction of the prism axis (need not be normalized).
    n_sides : int
        Number of sides (3 = triangle, 6 = hexagon, etc.). Minimum 3.
    circumscribed_radius : float
        Radius of the circumscribed circle (vertex to center distance).
    length : float
        Total length along the axis.
    material_name : str
        Key into Project.materials.
    face_optics : dict[str, str]
        Per-face optical override.  Keys: "cap_top", "cap_bottom",
        "side_0" ... "side_{n_sides-1}".
    """

    name: str
    center: np.ndarray
    axis: np.ndarray
    n_sides: int = 6
    circumscribed_radius: float = 5.0
    length: float = 10.0
    material_name: str = "pmma"
    face_optics: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        self.center = np.asarray(self.center, dtype=float)
        self.axis = np.asarray(self.axis, dtype=float)
        n = np.linalg.norm(self.axis)
        if n > 0:
            self.axis = self.axis / n
        if self.n_sides < 3:
            self.n_sides = 3

    def get_faces(self) -> list:
        """Return [cap_top, cap_bottom, side_0, ..., side_{n-1}] face objects."""
        half = self.length / 2.0
        u_local, v_local = _perpendicular_basis(self.axis)

        verts_2d = _compute_polygon_vertices(self.n_sides, self.circumscribed_radius)
        edge_normals = _compute_edge_normals(verts_2d)

        top_center = self.center + self.axis * half
        bot_center = self.center - self.axis * half

        cap_top = PrismCap(
            name=f"{self.name}::cap_top",
            center=top_center,
            normal=self.axis.copy(),
            u_axis=u_local.copy(),
            v_axis=v_local.copy(),
            n_sides=self.n_sides,
            circumscribed_radius=self.circumscribed_radius,
            vertices_2d=verts_2d.copy(),
            edge_normals_2d=edge_normals.copy(),
            material_name=self.material_name,
            optical_properties_name=self.face_optics.get("cap_top", ""),
        )
        cap_bottom = PrismCap(
            name=f"{self.name}::cap_bottom",
            center=bot_center,
            normal=-self.axis.copy(),
            u_axis=u_local.copy(),
            v_axis=v_local.copy(),
            n_sides=self.n_sides,
            circumscribed_radius=self.circumscribed_radius,
            vertices_2d=verts_2d.copy(),
            edge_normals_2d=edge_normals.copy(),
            material_name=self.material_name,
            optical_properties_name=self.face_optics.get("cap_bottom", ""),
        )

        faces: list = [cap_top, cap_bottom]

        # Side faces: n_sides flat rectangles
        # Edge length = 2 * R * sin(pi / n_sides)
        edge_len = 2.0 * self.circumscribed_radius * math.sin(math.pi / self.n_sides)
        for i in range(self.n_sides):
            v0_2d = verts_2d[i]
            v1_2d = verts_2d[(i + 1) % self.n_sides]
            mid_2d = (v0_2d + v1_2d) / 2.0

            # 3D face center
            face_center = self.center + mid_2d[0] * u_local + mid_2d[1] * v_local

            # Outward normal in 3D (from edge normals in local plane)
            en = edge_normals[i]
            face_normal_3d = en[0] * u_local + en[1] * v_local
            face_normal_3d = face_normal_3d / np.linalg.norm(face_normal_3d)

            # Edge direction (along edge in local plane, projected to 3D)
            edge_dir_2d = v1_2d - v0_2d
            edge_dir_2d = edge_dir_2d / np.linalg.norm(edge_dir_2d)
            edge_dir_3d = edge_dir_2d[0] * u_local + edge_dir_2d[1] * v_local
            edge_dir_3d = edge_dir_3d / np.linalg.norm(edge_dir_3d)

            # Rectangle axes: u_axis, v_axis such that cross(u_axis, v_axis) = face_normal_3d
            # Strategy: u_axis = edge_dir_3d, then v_axis = cross(face_normal_3d, edge_dir_3d)
            # which guarantees cross(u_axis, v_axis) = face_normal_3d
            face_u_axis = edge_dir_3d
            face_v_axis = np.cross(face_normal_3d, edge_dir_3d)
            face_v_axis = face_v_axis / np.linalg.norm(face_v_axis)

            # size = (edge_len, prism_length) corresponding to (u, v) extents
            rect = Rectangle(
                name=f"{self.name}::side_{i}",
                center=face_center,
                u_axis=face_u_axis,
                v_axis=face_v_axis,
                size=(edge_len, self.length),
                material_name=self.material_name,
            )
            rect.optical_properties_name = self.face_optics.get(f"side_{i}", "")
            faces.append(rect)

        return faces
