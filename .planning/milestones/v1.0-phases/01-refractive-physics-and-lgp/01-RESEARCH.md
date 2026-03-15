# Phase 1: Refractive Physics and LGP - Research

**Researched:** 2026-03-14
**Domain:** Monte Carlo ray tracing — Fresnel/TIR dielectric physics, solid box primitive, LGP scene building, KPI dashboard extension
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Solid body model**: New dedicated `SolidBox` dataclass that owns 6 Rectangle faces internally. Fields: name, center, dimensions (W,H,D), material_name (bulk material with refractive_index), face_optics (dict mapping face_id to OpticalProperties name). Axis-aligned only for Phase 1.
- **Per-face optical properties**: Faces named top/bottom/left/right/front/back. All faces start with bulk material default optics. User can override any individual face with a different OpticalProperties.
- **Scene tree presentation**: New "Solid Bodies" top-level category. SolidBox appears as collapsible parent with 6 child face nodes. Parent edits box-level; child face edits face OpticalProperties override.
- **Fresnel and TIR physics**: Unpolarized average Fresnel coefficients: `R = 0.5 * (Rs + Rp)`, `T = 1 - R`. No polarization tracking. TIR: when `sin(theta_t) > 1`, `R = 1.0`.
- **Reflect/transmit decision**: Stochastic Russian roulette — roll random number, if `< R` reflect (specular), else refract (Snell's law direction). Ray keeps full weight.
- **Medium tracking**: Each ray carries `current_n` (starts at 1.0). Entry: n1 = current_n, n2 = box.refractive_index, ray.current_n = n2. Exit: n1 = current_n, n2 = 1.0, ray.current_n = 1.0.
- **Refraction scope**: Fresnel/refraction only triggers on SolidBox face hits. Existing Rectangle surfaces keep their current reflect/absorb/diffuse behavior unchanged.
- **LGP scene builder**: New preset "Edge-Lit LGP" in Presets menu. New "LGP" tab in Geometry Builder dialog. Multi-edge coupling support (1-4 edges). Full scene auto-build: LGP slab + LEDs at edge(s) + detector above top face + reflector below bottom face.
- **Built-in materials**: Auto-created PMMA (refractive_index = 1.49, low absorption). Auto-created bottom-face reflector OpticalProperties. Created only if they don't already exist.
- **Edge coupling KPI**: coupling efficiency = flux entering LGP through coupling face(s) / total emitted. Extraction efficiency = flux at detector / flux entering coupling face(s). Only shown when a SolidBox exists. Displayed in Energy Balance section.
- **Flux tracking**: Each SolidBox face accumulates entering/exiting flux via per-face counters. Stored in `SimulationResult.solid_body_stats`.

### Claude's Discretion

- Exact SolidBox 3D rendering approach (GLMeshItem vs face quads)
- Self-intersection epsilon handling at SolidBox faces
- LGP builder dialog layout details
- Default gap distances for auto-placed detector and reflector
- How face_optics defaults are stored (explicit dict vs lazy lookup)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| LGP-01 | User can define an LGP slab as a solid box with independent optical properties per face | SolidBox dataclass with `.get_faces()` → list[Rectangle]; face_optics dict; Project.solid_bodies field; project_io serialization |
| LGP-02 | Tracer computes Snell's law refraction, Fresnel reflection/transmission, and TIR at dielectric interfaces | `_fresnel_unpolarized()` helper; `_refract_snell()` direction calculation; per-ray `current_n` array; new SolidBox branch in `_bounce_surfaces()` |
| LGP-03 | User can see edge coupling efficiency (flux-through-edge / total-emitted) as a KPI after simulation | Per-face flux counters in tracer; `SimulationResult.solid_body_stats`; KPI dashboard extension in `heatmap_panel.py` |
| GEOM-01 | User can create a box solid body with 6 faces, each with independent optical properties | SolidBox dataclass; object_tree "Solid Bodies" category; properties_panel SolidBoxForm + FaceForm; viewport_3d solid box rendering |
</phase_requirements>

## Summary

Phase 1 adds Fresnel/TIR physics and an LGP simulation workflow to an already functional Monte Carlo ray tracer. The core engine (`sim/tracer.py`) is well-structured for extension: it uses a typed bounce loop with per-surface dispatch, and a clean `_resolve_optics()` helper. The existing `Material.refractive_index` field is already defined (default 1.0) but not yet wired to any physics. The existing `OpticalProperties` system, `_intersect_rays_plane()`, and `reflect_specular()` in `sampling.py` are all directly reusable.

The main new physics is a `_bounce_solid_box_face()` branch inside `_bounce_surfaces()`: compute the ray-surface dot product for entry/exit classification, compute Fresnel R/T coefficients (unpolarized average), stochastic Russian roulette to choose reflect or refract, apply Snell's law for the refraction direction, update `current_n` per ray, and offset origin by a geometry-relative epsilon (not the fixed 1e-6, which would cause TIR loss in thin PMMA slabs). This branch runs only for SolidBox faces; existing Rectangle surfaces are untouched.

The data model requires a new `SolidBox` dataclass in `core/`, a `solid_bodies: list[SolidBox]` field on `Project`, and `solid_body_stats: dict` on `SimulationResult`. The GUI requires a new "Solid Bodies" category in the object tree, a `SolidBoxForm`/`FaceForm` in the properties panel, a 6-face solid render in the 3D viewport, an "LGP" tab in the geometry builder dialog, a new preset, and two new KPI rows in the energy balance section of the heatmap panel.

**Primary recommendation:** Implement in this order: (1) SolidBox dataclass + Project field, (2) Fresnel/refraction physics in tracer with geometry-relative epsilon, (3) face flux tracking + SimulationResult.solid_body_stats, (4) project save/load, (5) KPI dashboard rows, (6) GUI (tree + properties + viewport + builder + preset). This order keeps each step testable and prevents cascading breakage.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | Already installed | Ray direction math, Snell's law vectorized ops, batch epsilon offset | All existing tracer math uses numpy; no new dependency |
| PySide6 | Already installed | GUI forms, tree widget, dialogs | Existing GUI layer |
| pyqtgraph.opengl (GLMeshItem) | Already installed | 3D solid box rendering | Already used for Rectangle mesh rendering |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python dataclasses | stdlib | SolidBox data model | Consistent with Rectangle, DetectorSurface, Material patterns |
| json | stdlib | Project serialization | Same pattern as all other save/load |
| pytest | Already installed | New test coverage for TIR/Fresnel | Existing test suite at `backlight_sim/tests/test_tracer.py` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| GLMeshItem for solid box | 12 GLLinePlotItem wireframes (6 faces × 2 triangles) | GLMeshItem is already used for Rectangle meshes — consistent and simpler |
| stochastic Russian roulette | ray splitting (two child rays at each interface) | Splitting doubles ray count geometrically — prohibitive for glass with many bounces; roulette is standard Monte Carlo practice |
| geometry-relative epsilon | fixed 1e-6 | Fixed 1e-6 mm causes self-intersection in thin slabs (e.g., 3 mm PMMA) — must scale to slab thickness |

**Installation:** No new packages required. All dependencies are already in requirements.txt.

## Architecture Patterns

### Recommended Project Structure

New files and where they fit:
```
backlight_sim/
├── core/
│   └── solid_body.py          # NEW: SolidBox dataclass + face-name constants
├── sim/
│   └── tracer.py              # MODIFY: add SolidBox branch + Fresnel helpers + current_n tracking
├── io/
│   ├── project_io.py          # MODIFY: serialize/deserialize SolidBox
│   ├── geometry_builder.py    # MODIFY: add build_lgp_scene()
│   └── presets.py             # MODIFY: add preset_edge_lit_lgp()
├── gui/
│   ├── main_window.py         # MODIFY: wire "Solid Bodies" group, LGP preset menu item
│   ├── object_tree.py         # MODIFY: add "Solid Bodies" to GROUPS, support parent/child tree
│   ├── properties_panel.py    # MODIFY: add SolidBoxForm, FaceForm to QStackedWidget
│   ├── viewport_3d.py         # MODIFY: render SolidBox as GLMeshItem solid
│   ├── heatmap_panel.py       # MODIFY: add coupling/extraction KPI rows in energy balance
│   └── geometry_builder.py    # MODIFY: add LGP tab to GeometryBuilderDialog
```

### Pattern 1: SolidBox Dataclass

`core/solid_body.py` owns `SolidBox` and provides `.get_faces() -> list[Rectangle]`. Each face is a `Rectangle` whose `name` is `"{box_name}::top"` etc., and whose `material_name` and `optical_properties_name` are set from `face_optics` (with fallback to the box bulk material).

```python
# core/solid_body.py
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from backlight_sim.core.geometry import Rectangle

FACE_NAMES = ("top", "bottom", "left", "right", "front", "back")

@dataclass
class SolidBox:
    name: str
    center: np.ndarray        # (3,) world-space center
    dimensions: tuple[float, float, float]  # (W, H, D) — full extents
    material_name: str = "pmma"
    # face_id → OpticalProperties name; absent = use bulk material
    face_optics: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        self.center = np.asarray(self.center, dtype=float)

    def get_faces(self) -> list[Rectangle]:
        """Decompose this box into 6 axis-aligned Rectangle faces."""
        W, H, D = self.dimensions
        cx, cy, cz = self.center
        hw, hh, hd = W / 2.0, H / 2.0, D / 2.0

        face_specs = {
            "top":    (np.array([cx, cy, cz + hd]), (2,  1.0), (W, H)),
            "bottom": (np.array([cx, cy, cz - hd]), (2, -1.0), (W, H)),
            "right":  (np.array([cx + hw, cy, cz]), (0,  1.0), (H, D)),
            "left":   (np.array([cx - hw, cy, cz]), (0, -1.0), (H, D)),
            "back":   (np.array([cx, cy + hh, cz]), (1,  1.0), (D, W)),
            "front":  (np.array([cx, cy - hh, cz]), (1, -1.0), (D, W)),
        }
        faces = []
        for face_id, (center, (axis, sign), size) in face_specs.items():
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
```

**Key detail**: The face Rectangle names use `"::"` as separator so the tracer can split on `"::"` to recover (box_name, face_id) when accumulating face flux.

### Pattern 2: Fresnel Physics in the Tracer

Add two helper functions alongside `_reflect_batch` and `_intersect_rays_plane`:

```python
def _fresnel_unpolarized(cos_theta_i: np.ndarray, n1: np.ndarray, n2: np.ndarray) -> np.ndarray:
    """Compute unpolarized Fresnel reflectance R = 0.5*(Rs + Rp).

    Returns (N,) array of R values in [0, 1]. TIR case returns 1.0.
    cos_theta_i must be positive (angle of incidence, not signed dot product).
    """
    sin_theta_i = np.sqrt(np.maximum(0.0, 1.0 - cos_theta_i**2))
    sin_theta_t_sq = (n1 / n2)**2 * (1.0 - cos_theta_i**2)
    tir = sin_theta_t_sq >= 1.0
    cos_theta_t = np.sqrt(np.maximum(0.0, 1.0 - sin_theta_t_sq))

    rs_num = n1 * cos_theta_i - n2 * cos_theta_t
    rs_den = n1 * cos_theta_i + n2 * cos_theta_t
    rp_num = n2 * cos_theta_i - n1 * cos_theta_t
    rp_den = n2 * cos_theta_i + n1 * cos_theta_t

    # Avoid divide-by-zero
    rs = np.where(np.abs(rs_den) > 1e-12, (rs_num / rs_den)**2, 1.0)
    rp = np.where(np.abs(rp_den) > 1e-12, (rp_num / rp_den)**2, 1.0)

    R = 0.5 * (rs + rp)
    R = np.where(tir, 1.0, R)
    return np.clip(R, 0.0, 1.0)


def _refract_snell(directions: np.ndarray, oriented_normals: np.ndarray,
                   n1: np.ndarray, n2: np.ndarray) -> np.ndarray:
    """Compute refracted ray directions using Snell's law (vectorized).

    oriented_normals points INTO the medium (away from incoming ray).
    Returns (N, 3) refracted directions (unit vectors).
    """
    eta = n1 / n2          # (N,) ratio
    cos_i = np.einsum("ij,ij->i", -directions, oriented_normals)  # (N,) positive
    cos_i = np.clip(cos_i, 0.0, 1.0)
    sin_t_sq = eta**2 * (1.0 - cos_i**2)
    cos_t = np.sqrt(np.maximum(0.0, 1.0 - sin_t_sq))
    # Snell-Descartes vectorized formula
    refracted = (eta[:, None] * directions
                 + (eta * cos_i - cos_t)[:, None] * oriented_normals)
    # Normalize to handle numerical drift
    norms = np.linalg.norm(refracted, axis=1, keepdims=True)
    return refracted / np.maximum(norms, 1e-12)
```

### Pattern 3: Geometry-Relative Epsilon

The existing `_EPSILON = 1e-6` is fine for large cavities (50+ mm) but causes false self-intersection in thin PMMA slabs (~3 mm). The fix: compute epsilon relative to the slab dimension at the hit point.

```python
# In _bounce_solid_box_face():
# After computing hit_pts, offset by epsilon scaled to face thickness:
W, H, D = box.dimensions
min_dim = min(W, H, D)
geom_eps = max(1e-6, min_dim * 1e-4)   # e.g. 3mm slab → eps = 3e-4 mm
origins[hit_idx] = hit_pts + on * geom_eps
```

This matches the STATE.md blocker: "Fix _EPSILON to geometry-relative value before any LGP code (thin-slab TIR loss pitfall)".

### Pattern 4: Per-Ray current_n Tracking

Add `current_n` to the per-source ray state arrays in `_run_single()`:

```python
# After emitting rays:
current_n = np.ones(n, dtype=float)   # all rays start in air (n=1.0)
```

Pass `current_n` into `_bounce_surfaces()` and `_bounce_solid_box_face()`. On entry into a SolidBox face, update: `current_n[hit_idx] = box_n`. On exit, update: `current_n[hit_idx] = 1.0`. Entry vs. exit is determined by the dot product sign between ray direction and the outward face normal (same pattern as the existing `flip` / `on` computation).

### Pattern 5: SolidBody Stats in SimulationResult

```python
# core/detectors.py — add to SimulationResult:
solid_body_stats: dict = field(default_factory=dict)
# Structure: { box_name: { face_id: { "entering_flux": float, "exiting_flux": float } } }
```

During simulation, the tracer maintains a local accumulator dict and writes it to `SimulationResult.solid_body_stats` at the end. The KPI dashboard reads `solid_body_stats` to compute coupling and extraction efficiencies.

### Pattern 6: Object Tree — Parent/Child SolidBox Node

The existing `GROUPS` tuple in `object_tree.py` becomes `("Sources", "Surfaces", "Materials", "Optical Properties", "Detectors", "Sphere Detectors", "Solid Bodies")`. The tree's `refresh()` method builds a collapsible parent for each SolidBox, with 6 fixed child items (top/bottom/left/right/front/back). Selection of the parent emits `("Solid Bodies", box_name)`. Selection of a child emits `("Solid Bodies", f"{box_name}::face_id")`.

### Pattern 7: LGP Builder Function

`io/geometry_builder.py` gains a new function:

```python
def build_lgp_scene(
    project: Project,
    width: float,   # LGP X extent (mm)
    height: float,  # LGP Y extent (mm)
    thickness: float,  # LGP Z extent (mm)
    lgp_center_z: float = 0.0,
    coupling_edges: list[str] = ("left",),  # "left","right","front","back"
    led_count: int = 4,
    led_flux: float = 100.0,
    led_distribution: str = "lambertian",
    detector_gap: float = 2.0,   # above top face
    reflector_gap: float = 1.0,  # below bottom face
    material_name: str = "pmma",
) -> SolidBox:
    """Build a complete edge-lit LGP scene in project.

    Creates: SolidBox LGP, LEDs at coupling edges, detector above top face,
    reflector surface below bottom face.
    Returns the SolidBox object.
    """
```

### Anti-Patterns to Avoid

- **Modifying Rectangle for Fresnel**: Fresnel only applies to SolidBox faces — do not add a `refractive_interface` flag to Rectangle. The locked decision states: "Fresnel/refraction only triggers on SolidBox face hits."
- **Ray splitting at Fresnel interface**: Creates exponentially many child rays. Use Russian roulette.
- **Fixed epsilon for TIR**: The 1e-6 global _EPSILON will cause TIR loss in thin slabs. Must compute geometry-relative epsilon per SolidBox.
- **Global current_n state**: current_n must be per-ray (array), not per-tracer. Nested SolidBox geometries or overlapping volumes would corrupt a global value.
- **Flat face name string "top"**: Use `"{box_name}::top"` as the Rectangle name so the tracer can identify both the box and the face from a single string split.
- **Accumulating flux in multiprocessing path**: The existing `_trace_single_source()` function (used in MP mode) duplicates the bounce loop. It also needs the SolidBox branch and current_n array — failing to add it there will silently produce wrong KPIs in MP mode.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Snell's law refraction direction | Custom vector algebra | Vectorized formula: `η·d + (η·cos_i - cos_t)·n` | This is the standard closed-form Snell-Descartes formula — well-known, numerically stable, one line |
| GLMeshItem for solid box | Custom OpenGL VAO | `gl.GLMeshItem(vertexes=..., faces=..., faceColors=..., smooth=False)` | Already used in `_draw_rect()` in `viewport_3d.py` — same call pattern |
| Face-area intersection test | Custom AABB | Reuse `_intersect_rays_plane()` for each face Rectangle | Already exists, handles general orientations, tested |
| Project serialization | Custom binary format | json.dumps with numpy→list conversion | Same pattern used for all existing objects in project_io.py |

**Key insight:** The entire simulation physics for Fresnel/TIR can be implemented in ~80 lines of numpy — there are no external physics libraries that need to be integrated.

## Common Pitfalls

### Pitfall 1: Fixed Epsilon Causes Spurious TIR
**What goes wrong:** A ray that just reflected or refracted inside a thin slab (e.g., 3 mm PMMA) immediately re-intersects the same face because the 1e-6 offset is smaller than floating-point noise at that scale.
**Why it happens:** `_EPSILON = 1e-6` was designed for 50+ mm cavities. A 3 mm slab has a face-to-face distance where 1e-6 is insufficient.
**How to avoid:** Compute `geom_eps = max(1e-6, min(W, H, D) * 1e-4)` per SolidBox and use it for all SolidBox face offsets. The existing Rectangle surfaces continue using the global `_EPSILON`.
**Warning signs:** An LGP scene produces zero or near-zero detector flux even with many bounces and no absorbing faces.

### Pitfall 2: Wrong Normal Orientation in Fresnel
**What goes wrong:** Using `surf.normal` (always pointing in the fixed direction from cross(u_axis, v_axis)) instead of the oriented normal `on` gives wrong entry/exit classification and wrong cos_theta_i.
**Why it happens:** The existing `_bounce_surfaces()` already computes `on = where(flip, -normal, normal)` — the Fresnel implementation must use `on`, not `surf.normal`.
**How to avoid:** STATE.md already flags this: "Use oriented normal `on` not `surf.normal` in Fresnel impl (normal orientation pitfall)." Compute `cos_theta_i = clip(-dot(d, on), 0, 1)` — the angle must be positive.
**Warning signs:** TIR triggers at angles below the critical angle, or light refracts in the wrong direction.

### Pitfall 3: Missing SolidBox Branch in Multiprocessing Path
**What goes wrong:** `_run_single()` has the new SolidBox physics, but `_trace_single_source()` (used in MP mode) does not. Simulation produces correct results in single-thread mode but wrong (or zero-KPI) results when `use_multiprocessing=True`.
**Why it happens:** The MP function is a standalone top-level function that duplicates the bounce loop. Adding the SolidBox branch to `_run_single()` does not automatically propagate.
**How to avoid:** After implementing in `_run_single()`, immediately replicate the SolidBox handling in `_trace_single_source()`. Add a test that runs the same scene in both modes and compares detector flux within a statistical tolerance.
**Warning signs:** MP mode produces different KPIs than single-thread mode for LGP scenes.

### Pitfall 4: face_optics Defaulting vs. Bulk Material
**What goes wrong:** If `face_optics` is an empty dict and code does `self.face_optics[face_id]` without a `.get()`, all faces fail to look up their optics and the tracer falls through to a None material, treating all faces as absorbers.
**Why it happens:** The locked decision says "user can override any individual face" but all faces default to the bulk material. The tracer's `_resolve_optics()` already handles the None case by falling back to material lookup — SolidBox faces must be built as Rectangle with `optical_properties_name = ""` and `material_name = box.material_name` when no override exists.
**How to avoid:** In `SolidBox.get_faces()`, always set `rect.material_name = self.material_name` and set `rect.optical_properties_name = self.face_optics.get(face_id, "")`. The existing `_resolve_optics()` then handles the fallback chain correctly.
**Warning signs:** All LGP faces act as absorbers — zero flux at detector even with 1 bounce.

### Pitfall 5: KPI Division by Zero
**What goes wrong:** `coupling_efficiency = entering_flux / total_emitted` raises ZeroDivisionError or produces NaN when total_emitted is zero (empty scene, no enabled sources).
**How to avoid:** Guard all KPI computations: `eff = entering_flux / total_emitted if total_emitted > 0 else 0.0`. The existing KPI code in `heatmap_panel.py` already uses this pattern for efficiency.
**Warning signs:** KPI dashboard shows `nan%` or crashes on empty scenes.

### Pitfall 6: SolidBox Faces in Tracer Intersection Loop
**What goes wrong:** Each `SolidBox` must be expanded into its 6 faces before the intersection loop. If SolidBox objects are iterated directly (not expanded), no intersections are computed.
**Why it happens:** `_intersect_rays_plane()` operates on Rectangle attributes. SolidBox is not a Rectangle.
**How to avoid:** In `_run_single()`, before the bounce loop, compute `solid_faces = [face for box in project.solid_bodies for face in box.get_faces()]`. Store alongside a mapping `face_rect → (box, face_id)` for flux accumulation. Include solid_faces in the intersection test loop (type=3 or similar).
**Warning signs:** LGP surface is invisible to rays — all rays escape immediately.

## Code Examples

### Snell's Law Refraction Direction (Vectorized)

The Snell-Descartes vector form avoids computing angles explicitly:
```python
# Source: Pharr, Jakob, Humphreys "Physically Based Rendering" — standard formula
# eta = n1/n2, d = incoming direction, n = oriented normal INTO the medium
# cos_i = -dot(d, n)  [positive when ray hits the front face]
def _refract_snell(directions, oriented_normals, n1_arr, n2_arr):
    eta = n1_arr / n2_arr                                            # (N,)
    cos_i = np.clip(-np.einsum("ij,ij->i", directions, oriented_normals), 0.0, 1.0)
    sin_t_sq = eta**2 * (1.0 - cos_i**2)
    cos_t = np.sqrt(np.maximum(0.0, 1.0 - sin_t_sq))               # 0 for TIR
    refracted = (eta[:, None] * directions
                 + (eta * cos_i - cos_t)[:, None] * oriented_normals)
    norms = np.linalg.norm(refracted, axis=1, keepdims=True)
    return refracted / np.maximum(norms, 1e-12)
```

### Fresnel Reflectance (Unpolarized)

```python
# Source: Born & Wolf "Principles of Optics" — standard Fresnel equations
def _fresnel_unpolarized(cos_i, n1, n2):
    # cos_i: (N,) positive values; n1, n2: (N,) or scalars
    sin_t_sq = (n1 / n2)**2 * (1.0 - cos_i**2)
    tir = sin_t_sq >= 1.0
    cos_t = np.sqrt(np.maximum(0.0, 1.0 - sin_t_sq))
    rs = ((n1 * cos_i - n2 * cos_t) / np.maximum(n1 * cos_i + n2 * cos_t, 1e-12))**2
    rp = ((n2 * cos_i - n1 * cos_t) / np.maximum(n2 * cos_i + n1 * cos_t, 1e-12))**2
    R = np.where(tir, 1.0, 0.5 * (rs + rp))
    return np.clip(R, 0.0, 1.0)
```

### GLMeshItem for Solid Box (6 Faces)

Reuse the existing `_rect_mesh()` helper (already in `viewport_3d.py`) for each face:
```python
# viewport_3d.py — in a new _draw_solid_box() method:
def _draw_solid_box(self, box):
    for face in box.get_faces():
        verts, faces = _rect_mesh(face.center, face.u_axis, face.v_axis, face.size)
        color = (0.4, 0.7, 1.0, 0.25 if self._view_mode == "transparent" else 0.5)
        mesh = gl.GLMeshItem(vertexes=verts, faces=faces,
                              faceColors=np.array([color] * len(faces)),
                              smooth=False, drawEdges=True,
                              edgeColor=(0.4, 0.7, 1.0, 1.0))
        if self._view_mode == "transparent":
            mesh.setGLOptions("translucent")
        self._view.addItem(mesh)
        self._scene_items.append(mesh)
```

### Project Serialization for SolidBox

```python
# io/project_io.py
def _solid_box_to_dict(b: SolidBox) -> dict:
    return {
        "name": b.name,
        "center": _v(b.center),
        "dimensions": list(b.dimensions),
        "material_name": b.material_name,
        "face_optics": b.face_optics,   # already a plain dict[str, str]
    }

def _dict_to_solid_box(d: dict) -> SolidBox:
    return SolidBox(
        name=d["name"],
        center=_a(d["center"]),
        dimensions=tuple(d["dimensions"]),
        material_name=d.get("material_name", "pmma"),
        face_optics=d.get("face_optics", {}),
    )
```

### Edge Coupling KPI Computation

```python
# heatmap_panel.py — in _update_kpis()
stats = result.solid_body_stats  # dict from SimulationResult
if stats and result.total_emitted_flux > 0:
    total_entering = sum(
        face_data.get("entering_flux", 0.0)
        for box_data in stats.values()
        for face_id, face_data in box_data.items()
        if face_id in project_coupling_faces   # set from project.solid_bodies[*].coupling_edges
    )
    coupling_eff = total_entering / result.total_emitted_flux
    detector_flux = result.detectors[main_det_name].total_flux
    extraction_eff = detector_flux / total_entering if total_entering > 0 else 0.0
    overall_eff = coupling_eff * extraction_eff
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Rectangle-only surfaces | SolidBox primitive with 6 Rectangle faces + Fresnel physics | Phase 1 | Enables edge-lit LGP simulation |
| Fixed `_EPSILON = 1e-6` for all surfaces | Geometry-relative epsilon for SolidBox faces | Phase 1 | Prevents TIR loss in thin slabs |
| No medium tracking | Per-ray `current_n` array | Phase 1 | Enables nested dielectric media (future: glass-in-glass) |
| Energy balance (efficiency/absorbed/escaped) | + Coupling efficiency + Extraction efficiency | Phase 1 | LGP-specific KPIs |

**Deprecated/outdated:**
- None — this is additive. No existing behavior changes.

## Open Questions

1. **SolidBox in multiprocessing: serialization of solid_body_stats across process boundaries**
   - What we know: `_trace_single_source()` returns a plain dict. If solid_body_stats is added to that return dict, merging is simple (sum per-face flux across sources).
   - What's unclear: Whether the face-name-as-key scheme (`"box_name::face_id"`) works cleanly when aggregating across multiple sources' per-face dicts.
   - Recommendation: Use nested dict `{box_name: {face_id: float}}` in the return payload, and sum them on the main thread.

2. **LGP builder — which face is the "coupling edge"?**
   - What we know: The locked decision supports multi-edge coupling (1–4 edges). The edge identification maps to face_id strings: "left", "right", "front", "back".
   - What's unclear: Where coupling_edges is stored — in `SolidBox` itself or only in the builder's output metadata.
   - Recommendation: Add `coupling_edges: list[str] = field(default_factory=list)` to `SolidBox` so the KPI dashboard can read it directly without needing external metadata.

3. **Face child node selection in the object tree — signal protocol**
   - What we know: `ObjectTree.object_selected` emits `(group, name)`. For a face child, this would need to be `("Solid Bodies", "MyLGP::top")`.
   - What's unclear: Whether the properties panel dispatcher can split on `"::"` safely (no face_id contains `"::"`).
   - Recommendation: Use `"::"` as separator throughout (face_ids are fixed strings: top/bottom/left/right/front/back). The properties panel checks `if "::" in name: box_name, face_id = name.split("::", 1)`.

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `backlight_sim/sim/tracer.py`, `backlight_sim/core/`, `backlight_sim/io/`, `backlight_sim/gui/` — direct inspection of all integration points
- `backlight_sim/tests/test_tracer.py` — 20 existing tests, pytest framework confirmed
- `.planning/phases/01-refractive-physics-and-lgp/01-CONTEXT.md` — locked user decisions
- `.planning/STATE.md` — known blockers (epsilon, normal orientation)

### Secondary (MEDIUM confidence)
- Physically Based Rendering (Pharr, Jakob, Humphreys): Snell-Descartes vectorized refraction formula — widely cited, independent verification not performed against latest edition
- Born & Wolf "Principles of Optics": Fresnel coefficient equations — textbook standard, HIGH confidence in correctness

### Tertiary (LOW confidence)
- None — all critical claims are verifiable from the codebase or standard optics references

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already present and in use; no new dependencies
- Architecture: HIGH — all integration points verified by direct code inspection; pattern reuse from existing codebase is unambiguous
- Fresnel/Snell physics: HIGH — standard geometric optics equations, not framework-dependent
- Pitfalls: HIGH — two are explicitly flagged in STATE.md; four others are logical consequences of the codebase structure

**Research date:** 2026-03-14
**Valid until:** 2026-06-14 (stable codebase; physics equations don't change)
