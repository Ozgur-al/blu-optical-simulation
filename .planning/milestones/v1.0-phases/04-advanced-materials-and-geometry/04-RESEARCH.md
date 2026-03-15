# Phase 4: Advanced Materials and Geometry - Research

**Researched:** 2026-03-14
**Domain:** Monte Carlo ray tracing — BSDF sampling, analytic solid-body geometry, far-field photometry, PySide6/pyqtgraph GUI
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**BSDF model**
- Full BSDF only — no separate BRDF or BTDF; uploaded table must cover both reflection and transmission
- Isotropic (1D) model: for each incident angle theta_in, a reflected and transmitted intensity profile I(theta_out)
- CSV import format: columns theta_in, theta_out, refl_intensity, trans_intensity; absorption derived as remainder
- BSDF profile assigned to OpticalProperties — overrides all manual reflectance/transmittance/diffuse values when set
- When no BSDF is assigned, manual values apply as before (backward compatible)
- Stored in project as `project.bsdf_profiles = {name: {theta_in, theta_out, refl_intensity, trans_intensity}}`
- Tracer sampling: 2D CDF inversion per incident angle, extending existing sample_angular_distribution() pattern

**Far-field detector**
- Extend existing SphereDetector with a `mode` field: `"near_field"` (default) or `"far_field"` (direction-only accumulation)
- Full sphere coverage: theta 0-180 deg, phi 0-360 deg
- Candela computed as flux / solid_angle_per_bin
- Display: both polar plot and 3D intensity lobe in viewport
- Polar plot: multi-slice C-plane overlay (C0, C90, etc.) with color-coded lines and checkboxes
- 3D lobe: solid color-mapped mesh surface (radius proportional to candela, cool-to-warm colormap)
- Far-field KPIs: peak cd, total lm, beam angle (50% peak), field angle (10% peak), asymmetry
- IES export via existing io/ies_parser.py — add export_ies() function
- CSV export for raw candela data

**Cylinder solid body**
- Analytic ray-cylinder intersection (quadratic for curved surface, plane intersection for end caps)
- Parameterization: center, axis direction vector, radius, length
- Three faces: "top_cap", "bottom_cap", "side" — per-face optical overrides via face_optics dict
- Full Fresnel/TIR refractive physics (same as SolidBox, detected via "::" naming convention)
- 3D viewport: smooth 64-segment mesh rendering

**Prism solid body**
- Regular polygon cross-section: n_sides, circumscribed radius, length, axis direction, center
- Flat side faces: reuse _intersect_rays_plane() for side faces
- End caps: plane intersection with point-in-polygon test for non-rectangular clipping
- Faces: "cap_top", "cap_bottom", "side_0" through "side_{n-1}" — per-face optical overrides
- Full Fresnel/TIR refractive physics (same "::" convention)

**GUI integration**
- Cylinder and prism appear under Surfaces category in object tree, expandable to show faces
- Dedicated BSDF panel (new top-level tab, separate from Angular Distribution panel)
- BSDF panel: profile list, import CSV/delete, 2D heatmap (theta_in x theta_out), click-to-select line plot, separate reflection/transmission views
- BSDF assignment: dropdown on OpticalProperties form; when BSDF profile selected, manual fields greyed out
- Far-field result panel: polar plot with multi-slice overlay + KPI sidebar + export buttons
- Property forms for SolidCylinder and SolidPrism following SolidBoxForm pattern

### Claude's Discretion
- Exact CDF interpolation grid resolution for BSDF sampling
- Cylinder mesh segment count (recommended 64)
- Prism end-cap triangulation approach
- Polar plot color palette for C-plane overlays
- 3D intensity lobe colormap choice and scaling
- Error handling for malformed BSDF CSV files

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BRDF-01 | User can import tabulated BSDF data (goniophotometer CSV) and assign it to surfaces | 2D CDF inversion pattern from existing sample_angular_distribution(); OpticalProperties.bsdf_profile_name field; backward-compatible with existing reflectance/transmittance when no BSDF |
| DET-01 | User can add a far-field angular detector, run simulation, export candela distribution as IES | Extend SphereDetector with mode="far_field"; direction-based accumulation (not position); candela = flux / solid_angle_per_bin; export_ies() added to ies_parser.py |
| GEOM-02 | User can create cylinder solid body primitives | SolidCylinder dataclass with analytic quadratic intersection for curved surface + plane caps; get_faces() yields synthetic face objects; "::" name convention triggers Fresnel/TIR path |
| GEOM-03 | User can create prism solid body primitives | SolidPrism dataclass with n_sides regular polygon; side faces reuse _intersect_rays_plane(); caps use point-in-polygon clipping; same "::" Fresnel/TIR trigger |
</phase_requirements>

---

## Summary

Phase 4 extends the simulation engine and GUI with four distinct capabilities: measured BSDF surface scattering, far-field candela detection, cylinder solid bodies, and prism solid bodies. All four features are self-contained extensions to existing, proven code patterns. No architectural upheaval is needed — each feature plugs into a specific existing extension point.

The codebase already has every foundational primitive this phase needs: 1D CDF sampling (`sample_angular_distribution()`), ray-plane intersection (`_intersect_rays_plane()`), Fresnel/TIR physics (`_fresnel_unpolarized()` + `_refract_snell()`), solid-body face dispatch via `"::"` naming, sphere detector infrastructure (`SphereDetector` + `SphereDetectorResult` + `_intersect_rays_sphere()` + `_accumulate_sphere()`), IES parser, and panel widget patterns (`AngularDistributionPanel`, `SpectralDataPanel`, `SolidBoxForm`). Phase 4 work is almost entirely additive — extend existing classes, add new dataclasses, new sampling functions, new GUI panels.

The largest engineering tasks are: (1) the 2D CDF for BSDF sampling (two-pass per-theta_in table build), (2) the analytic cylinder intersection (quadratic + bounded t), (3) the far-field candela conversion and IES export format, and (4) the cylinder/prism mesh generation for 3D viewport.

**Primary recommendation:** Implement in four independent plans — BSDF engine+panel, far-field detector+panel, SolidCylinder, SolidPrism — each touching a clean layer boundary (core model → I/O → sim → GUI).

---

## Standard Stack

### Core (already in use — no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | >=1.24 | All geometry math, CDF inversion, mesh generation | Entire engine is numpy-vectorized |
| PySide6 | >=6.4 | GUI forms, signal/slot, QStackedWidget | Project standard |
| pyqtgraph | >=0.13 | 2D plots (polar, heatmap, line), pyqtgraph.opengl mesh | Already used for heatmap, angular dist, 3D viewport |
| pyqtgraph.opengl | same | GLMeshItem for cylinder/prism rendering, GLLinePlotItem for lobe wireframe | Already used for SolidBox, sphere wireframe |

### No New Dependencies Required
All functionality can be implemented with the existing stack. Confirm with:
```bash
python -c "import PySide6, pyqtgraph, numpy; print('ok')"
```

---

## Architecture Patterns

### Recommended Structure for New Files

```
backlight_sim/
├── core/
│   └── solid_body.py          # ADD: SolidCylinder, SolidPrism classes
├── sim/
│   └── sampling.py            # ADD: sample_bsdf_reflection(), sample_bsdf_transmission()
├── io/
│   └── ies_parser.py          # ADD: export_ies()
│   └── bsdf_io.py             # NEW: load_bsdf_csv(), validate_bsdf()
├── gui/
│   └── bsdf_panel.py          # NEW: BSDFPanel (mirrors AngularDistributionPanel)
│   └── far_field_panel.py     # NEW: FarFieldPanel (polar plot + KPIs + export)
│   └── properties_panel.py    # EXTEND: SolidCylinderForm, SolidPrismForm, BSDF dropdown on OpticalPropertiesForm
│   └── object_tree.py         # EXTEND: cylinder/prism nodes with face children
│   └── viewport_3d.py         # EXTEND: _draw_solid_cylinder(), _draw_solid_prism()
└── tests/
    └── test_tracer.py         # EXTEND: BSDF sampling, cylinder/prism intersection, far-field accumulation
```

### Pattern 1: Solid Body Extension (SolidCylinder, SolidPrism follow SolidBox)

**What:** New dataclasses in `core/solid_body.py` that expose a `get_faces()` method returning synthetic face objects with `"::"` in their name, triggering the Fresnel/TIR path in the tracer. The tracer code that dispatches on solid bodies is already written — it iterates `project.solid_bodies` (SolidBox) and calls `box.get_faces()`. Cylinders and prisms go into new lists (`project.solid_cylinders`, `project.solid_prisms`) with their own type 4/5 dispatch blocks in the bounce loop.

**When to use:** Any solid refractive body with per-face optical overrides.

**SolidCylinder face synthesis approach:**
```python
# Source: core/solid_body.py (SolidBox pattern, adapted)
# Cylinder faces are synthetic Rectangle-like objects for end caps.
# The curved "side" face is NOT a Rectangle — it requires analytic intersection.
# Strategy: end caps are actual Rectangle (disc approximated as square for
# intersection purposes is WRONG — must use plane intersection + radius check).
# Better: define CylinderFace as a lightweight named namedtuple or dataclass
# with (name, face_type, ...) so tracer dispatch can identify them.
```

Key insight: cylinder and prism faces cannot all use `Rectangle`. Caps can reuse `_intersect_rays_plane()` with a circular (cylinder) or polygon (prism) boundary check replacing the `|u_coord| <= hw, |v_coord| <= hh` box test. The curved cylinder side and flat prism sides each need a custom intersection function.

### Pattern 2: BSDF 2D CDF Inversion

**What:** Extension of existing `sample_angular_distribution()` from 1D to 2D. The existing function builds a CDF over `theta_out` given a fixed `normal` direction. For BSDF we need a per-`theta_in` table of CDFs.

**Data structure:**
```python
# project.bsdf_profiles = {
#     "my_film": {
#         "theta_in":       [0.0, 10.0, 20.0, ..., 80.0],  # M values
#         "theta_out":      [0.0, 5.0, 10.0, ..., 175.0],  # N values
#         "refl_intensity": [[...], [...], ...],             # M x N array
#         "trans_intensity": [[...], [...], ...]             # M x N array
#     }
# }
```

**Sampling algorithm:**
```python
# sim/sampling.py — new function sample_bsdf_reflection/transmission
def sample_bsdf(n, incident_dirs, surface_normal, bsdf_profile, mode, rng):
    # 1. Compute theta_in for each ray: cos_i = dot(-d, normal)
    # 2. For each ray, find nearest theta_in row via np.searchsorted
    # 3. Build per-ray CDF from the matched theta_out row (2048-point interp grid)
    # 4. CDF inversion → sampled theta_out per ray
    # 5. Random phi per ray (0..2pi — isotropic in phi, same as 1D case)
    # 6. Build local basis (tangent, bitangent, normal) per ray → transform to world
    # Vectorized over n rays but with a Python loop over unique theta_in values
    # for CDF construction (M CDFs at most, where M = len(theta_in))
```

CDF grid resolution: 2048 points (same as existing 1D sampler — confirmed HIGH confidence).

### Pattern 3: Far-field Mode in SphereDetector

**What:** Add `mode: str = "near_field"` field to `SphereDetector`. In the tracer, when `mode == "far_field"`, use **ray direction** (not hit point) to bin into the theta/phi grid. This means the sphere radius is irrelevant for binning — it only determines where the ray terminates (pass-through semantics, same as near_field).

**Candela conversion:**
```python
# After simulation, for far-field:
# solid_angle_per_bin = (2*pi / n_phi) * (pi / n_theta) * sin(theta_center)
# candela_grid[i_theta, i_phi] = flux_grid[i_theta, i_phi] / solid_angle_per_bin[i_theta]
# Note: sin(theta) weighting for equal solid-angle binning is needed at display time,
# NOT at accumulation time — accumulate raw flux, convert on read.
```

**IES export format (IESNA LM-63 2002):**
The export_ies() function must produce an LM-63 file. Key sections:
```
IESNA:LM-63-2002
[TEST]
[MANUFAC]
[LUMCAT]
[LUMINAIRE]
[LAMP]
TILT=NONE
1  <lumens_per_lamp>  1.0  <n_vert>  <n_horiz>  1  1  0  0  0  1.0  1.0  0
<vert_angles...>
<horiz_angles: 0 to 350 by step>
<candela_values: one row per C-plane>
```
- C-planes: phi slices (0, step, ..., 360-step)
- Vertical angles: theta values (0..180)
- Candela per row = candela_grid[theta_idx, phi_idx]
- n_lamps=1, lumens_per_lamp = total_flux from simulation

### Pattern 4: Cylinder Intersection (Quadratic)

The analytic ray-cylinder intersection is:
```
ray: P(t) = o + t*d
cylinder axis: passes through center C, direction unit vector A, half-length L/2
curved surface: ||(P - C) - ((P-C).A)*A||^2 = R^2

Substitution: oc = o - C
Components perpendicular to axis:
  a = d - (d.A)*A  (d perp)
  c_perp = oc - (oc.A)*A  (oc perp)
Quadratic: |a|^2 * t^2 + 2*(a.c_perp)*t + |c_perp|^2 - R^2 = 0
→ solve, pick t > epsilon, check |(P-C).A| <= L/2 (within cylinder height)

End caps: plane at C + (L/2)*A (top) and C - (L/2)*A (bottom)
  t_cap = ((cap_center - o).A) / (d.A)
  check ||(hit - cap_center)||^2 <= R^2 (within disc radius)
```

This is vectorized over N rays with numpy. Self-intersection epsilon: use `max(1e-6, min(R, L/2) * 1e-4)` (consistent with SolidBox pattern).

### Pattern 5: Prism Intersection

```
Prism: n_sides polygon cross-section, each side is a flat rectangular face.
Side face i:
  - Normal: outward from polygon centroid
  - Center: at midpoint of side edge, offset by axis_direction * 0
  - Size: (edge_length, L) for the side rectangle
  → reuse _intersect_rays_plane() directly (side faces ARE rectangles)

End caps: regular polygon in the plane perpendicular to axis
  - Intersection: _intersect_rays_plane() for the cap plane (using a bounding square)
  - Then point-in-polygon test to clip: use cross-product winding number or
    check if point is inside convex polygon (all cross products same sign)
  - For regular polygon with n vertices, the convex check is O(n) per ray
  - Can vectorize: build edge normals and signed distances, check all positive
```

### Anti-Patterns to Avoid

- **Using Rectangle for cylinder curved face:** The curved side of a cylinder cannot be represented as a Rectangle. Needs a dedicated `CylinderFace` type or inline quadratic intersection in the tracer.
- **Position-based far-field accumulation:** Far-field must bin by **ray direction**, not hit point. The hit point on the sphere is direction-proportional only when the source is at the sphere center — which is not guaranteed. Always use `directions[hit_idx]` at the moment of sphere intersection.
- **Building one CDF per ray for BSDF:** Expensive. Build one CDF per theta_in bin (at most M = len(theta_in) CDFs), then assign each ray the nearest bin's CDF. Vectorize with groupby or np.searchsorted.
- **Ignoring sin(theta) solid angle at IES export:** IES candela values are per-steradian. An equal-angle bin at theta=5 deg subtends far less solid angle than theta=85 deg. Always divide flux by `solid_angle = delta_theta * delta_phi * sin(theta_center)`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Polar plot (Cartesian-to-polar coord transform) | Custom polar widget | Existing `pg.PlotWidget` with manual x=I*sin(theta), y=I*cos(theta) mapping | Already proven in AngularDistributionPanel — same pattern |
| 3D lobe mesh | Custom mesh builder | Existing `_build_sphere_mesh()` pattern from `receiver_3d.py` (radius → candela) | Identical problem — sphere mesh with per-vertex color |
| IES parser for reading | Custom text parser | Existing `load_ies()` in `io/ies_parser.py` | Already handles all LM-63 variants |
| Ray-plane intersection for prism faces | Custom per-face code | `_intersect_rays_plane()` in tracer.py | Already vectorized, tested, handles arbitrary orientation |
| Fresnel/TIR for cylinder/prism | New physics code | `_fresnel_unpolarized()` + `_refract_snell()` + existing "::" dispatch | Exactly the same physics — just new geometry shape |
| 1D CDF inversion for BSDF theta_out | New interpolation code | Extend `sample_angular_distribution()` pattern directly | Same algorithm, just applied per theta_in row |
| 2D heatmap for BSDF overview | Custom widget | `pyqtgraph.ImageItem` + `ColorBarItem` (same as heatmap_panel.py) | Identical use case |

**Key insight:** This phase is almost entirely reuse. The hard physics are already implemented. The geometry math is already vectorized. The GUI patterns are proven. Engineering effort is in correctly connecting new data shapes to existing algorithms.

---

## Common Pitfalls

### Pitfall 1: BSDF Absorption Not Derived Correctly
**What goes wrong:** Importing a BSDF CSV where `refl_intensity + trans_intensity` does not sum to 1.0 for each (theta_in, theta_out) pair. Treating intensities as probabilities directly causes energy gain.
**Why it happens:** Goniophotometer data is often unnormalized or measures only hemisphere — user may import BRDF-only or BTDF-only data.
**How to avoid:** At import time, validate that for each theta_in row: `sum(refl) + sum(trans) <= total_incident_flux` (within numerical tolerance). Absorption = 1 - (refl_total + trans_total). Reject or warn if either refl or trans is absent (full BSDF required per user decision).
**Warning signs:** Any total_weight > 1 after a BSDF scatter event is a bug.

### Pitfall 2: Cylinder Self-Intersection
**What goes wrong:** After a refraction/reflection at the curved cylinder surface, the ray origin is offset by `_EPSILON` along the wrong normal direction, causing the ray to re-intersect the same surface on the next bounce.
**Why it happens:** The cylinder surface normal at a hit point is `(hit - C_axis) / R` (outward radial), not a global axis. Must compute it per-hit.
**How to avoid:** Per-hit outward normal = `(hit_pt - center - ((hit_pt - center) . axis) * axis) / R`. Use geometry-relative epsilon: `max(1e-6, R * 1e-4)` as done for SolidBox thin slabs.

### Pitfall 3: Far-Field Direction Binning Sign Convention
**What goes wrong:** `_accumulate_sphere` uses hit-point position to derive theta/phi. For far-field, we want the **ray direction** going OUT from the source, not the position on a large sphere. If the sphere is not centered on the luminaire centroid, theta/phi derived from position is wrong.
**Why it happens:** Near-field and far-field modes look identical in code — both operate on the same sphere intersection event.
**How to avoid:** In `_accumulate_sphere` (or a new `_accumulate_sphere_farfield`), use the ray direction vector at time of hit instead of `hit_pt - sd.center`. Specifically: `theta = arccos(clip(directions[hit_idx, 2], -1, 1))`, `phi = arctan2(directions[hit_idx, 1], directions[hit_idx, 0])`.

### Pitfall 4: Prism End-Cap Out-of-Bounds
**What goes wrong:** `_intersect_rays_plane()` uses a bounding box (hw, hh) test. For a regular polygon, the circumscribed circle radius equals the bounding half-width. This means rays hitting corners outside the polygon but inside the bounding box are falsely accepted.
**Why it happens:** Rectangle intersection uses `|u| <= hw AND |v| <= hh` — that's a square, not a polygon.
**How to avoid:** After `_intersect_rays_plane()` reports a hit, apply a secondary polygon-interior test. For a convex regular polygon with N vertices, check that the hit point (u, v) satisfies all N edge half-plane inequalities. Vectorize with numpy: precompute edge normals at SolidPrism construction time.

### Pitfall 5: BSDF Panel Profile List Mismatched with OpticalProperties Dropdown
**What goes wrong:** User deletes a BSDF profile that is referenced by an OpticalProperties. The tracer gets a missing key and falls back to no scattering (silent energy loss).
**Why it happens:** Two panels (BSDF panel and OpticalProperties form) share a reference by string name.
**How to avoid:** On profile deletion, scan all `project.optical_properties` for references and clear them (or show a confirmation dialog), matching the pattern used when deleting angular distributions or materials.

### Pitfall 6: IES Export C-Plane Ordering
**What goes wrong:** IES readers expect horizontal angles (C-planes) in strictly ascending order, starting from 0.0. If the phi grid bins don't align with 0-start, the exported file may fail validation.
**Why it happens:** `_accumulate_sphere` bins phi uniformly but doesn't guarantee 0.0 is the center of the first bin.
**How to avoid:** Compute C-plane angles as `phi_bin_centers = (np.arange(n_phi) + 0.5) * 360 / n_phi`. Alternatively, reconstruct at export time using linspace(0, 360, n_phi, endpoint=False). Standard IES C-plane set: 0, 22.5, 45, ..., 337.5 for 16 planes, or 0, 90, 180, 270 for 4 planes.

---

## Code Examples

Verified patterns from existing codebase:

### SolidBox "::" Face Dispatch (core/solid_body.py line 17 + tracer.py)
```python
# Face naming convention: "{box_name}::{face_id}"
# Tracer identifies solid faces by checking face.name contains "::"
# box, face_id, box_n, geom_eps = solid_face_map[sface.name]
# This is the ONLY modification needed in the tracer for new solid types —
# add solid_cylinders and solid_prisms with the same "::" naming.
```

### CDF Inversion Pattern (sim/sampling.py lines 49-98)
```python
# Existing 1D pattern to extend to 2D for BSDF:
grid = np.linspace(theta_rad[0], theta_rad[-1], 2048)
interp_i = np.interp(grid, theta_rad, intensity, left=0.0, right=0.0)
weights = interp_i * np.sin(grid)
csum = np.cumsum(weights)
cdf = csum / csum[-1]
u = rng.uniform(0.0, 1.0, size=n)
sample_theta = np.interp(u, cdf, grid)
# For BSDF: build one such CDF per theta_in row, store as list of arrays.
# Then for each ray: look up nearest theta_in row, do this inversion.
```

### SphereDetector Accumulation (tracer.py lines 1028-1047)
```python
# Existing near-field: uses hit_pts - sd.center to get direction
d = hit_pts - sd.center  # (M, 3)
# Far-field extension: use ray direction directly
d = directions[hit_idx]  # (M, 3) — ray direction at time of sphere hit
# Rest of binning code is identical
```

### GLMeshItem for Solid Body (viewport_3d.py lines 159-171)
```python
mesh = gl.GLMeshItem(
    vertexes=verts,      # (N_verts, 3) float32
    faces=face_indices,  # (N_faces, 3) int32
    faceColors=colors,   # (N_faces, 4) float32 RGBA
    smooth=False,
    drawEdges=True,
    edgeColor=edge_color,
)
mesh.setGLOptions("translucent")
self._view.addItem(mesh)
```

### Cylinder Mesh Generation (for 64 segments)
```python
# Generate cylinder mesh for viewport — NOT used in tracer (tracer uses analytic)
import numpy as np
def cylinder_mesh(center, axis, radius, length, n_seg=64):
    # Build orthonormal basis perpendicular to axis
    axis = axis / np.linalg.norm(axis)
    if abs(axis[0]) < 0.9:
        ref = np.array([1., 0., 0.])
    else:
        ref = np.array([0., 1., 0.])
    u = np.cross(axis, ref); u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    # Ring vertices at top and bottom caps
    angles = np.linspace(0, 2*np.pi, n_seg, endpoint=False)
    ring = radius * (np.cos(angles)[:, None] * u + np.sin(angles)[:, None] * v)
    top = center + (length/2) * axis + ring      # (n_seg, 3)
    bot = center - (length/2) * axis + ring      # (n_seg, 3)
    # Quads on side surface → 2 triangles each
    # Cap triangles → fan from center
```

### Polar Plot Pattern (gui/angular_distribution_panel.py lines 410-424)
```python
# Existing: theta vs I to (x, y) polar coords
# For far-field C-plane overlay: same approach, one curve per C-plane
x = I * np.sin(np.radians(theta))   # horizontal axis
y = I * np.cos(np.radians(theta))   # vertical axis (0 deg = top)
self._polar_plot.plot(x, y, pen=pen)
# Mirror for second half (theta mirrored):
self._polar_plot.plot(-x, y, pen=pen)
```

### IES Export Format Skeleton (io/ies_parser.py — new export_ies())
```python
def export_ies(path, theta_deg, candela_grid, total_lm, n_lamps=1):
    """Write IESNA LM-63-2002 file from candela_grid (n_theta x n_phi)."""
    n_theta = len(theta_deg)
    n_phi = candela_grid.shape[1]
    phi_deg = np.linspace(0, 360, n_phi, endpoint=False)
    lines = [
        "IESNA:LM-63-2002",
        "[TEST] BLU Optical Simulation Export",
        "[MANUFAC] blu-sim",
        "TILT=NONE",
        f"{n_lamps}  {total_lm:.4f}  1.0  {n_theta}  {n_phi}  1  1  0.0  0.0  0.0  1.0  1.0  0.0",
    ]
    lines.append("  ".join(f"{t:.2f}" for t in theta_deg))
    lines.append("  ".join(f"{p:.2f}" for p in phi_deg))
    for phi_idx in range(n_phi):
        row = candela_grid[:, phi_idx]
        lines.append("  ".join(f"{v:.4f}" for v in row))
    Path(path).write_text("\n".join(lines))
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual reflectance scalar | BSDF 2D table (theta_in x theta_out) | Phase 4 | Measured goniophotometer data replaces scalar approximation |
| Near-field sphere detector | Far-field mode (direction binning) | Phase 4 | Output is angular luminous intensity distribution — standard photometric output |
| No curved geometry | Analytic cylinder + polygon prism | Phase 4 | Light pipes, rod lenses, triangular prisms now representable |

**What is already current in this codebase:**
- Fresnel/TIR physics: fully implemented in Phase 1
- Spectral ray tracing: fully implemented in Phase 2
- SolidBox pattern: proven in Phase 1 — cylinder/prism follow same architecture

---

## Open Questions

1. **Cylinder face representation in the tracer dispatch**
   - What we know: SolidBox faces are Rectangle objects stored in `solid_faces: list[Rectangle]` with `solid_face_map` for lookup. The tracer loops over them using `_intersect_rays_plane()`.
   - What's unclear: Cylinder curved face is NOT a rectangle — cannot use `_intersect_rays_plane()`. End caps are circular discs — also not rectangles (different boundary test).
   - Recommendation: Add a new intersection type (type 4 = cylinder, type 5 = prism) in the bounce loop with dedicated `_intersect_rays_cylinder()` and `_intersect_prism_caps()` functions. Do NOT try to retrofit cylinder faces as Rectangle — it would be wrong for the curved surface and imprecise for caps.

2. **Per-ray theta_in grouping for vectorized BSDF sampling**
   - What we know: The 2D CDF must be per theta_in bin. Each ray hitting a BSDF surface will have a different theta_in.
   - What's unclear: Whether to build all M CDFs upfront (at simulation init) or lazily per scatter event. Upfront is safer for performance.
   - Recommendation: Precompute all M CDFs (M = number of theta_in rows, typically 10-18 for goniophotometer data) as numpy arrays at tracer init time, stored in a dict keyed by bsdf_profile_name. At scatter time, use `np.searchsorted(theta_in_arr, cos_i_per_ray_in_degrees)` to index into the right CDF row.

3. **SphereDetector mode field backward compatibility**
   - What we know: Existing projects have `SphereDetector` objects serialized without a `mode` field.
   - What's unclear: Whether project_io.py load code will break on old files.
   - Recommendation: Add `mode: str = "near_field"` as default in the dataclass. In `project_io.py`, use `.get("mode", "near_field")` when loading — consistent with the project's backward-compatibility pattern already used for other fields.

---

## Validation Architecture

> `workflow.nyquist_validation` is not set in `.planning/config.json` (no key present) — skipping formal test map section.

However, the existing test infrastructure in `backlight_sim/tests/test_tracer.py` uses pytest and runs 20+ tests. All new core engine code (BSDF sampling, cylinder intersection, prism intersection, far-field accumulation) should have tests added to this file following the existing pattern.

**Quick run:** `pytest backlight_sim/tests/test_tracer.py -x`
**Full suite:** `pytest backlight_sim/tests/`

New tests needed (Wave 0 items for planner):
- `test_bsdf_sampling_energy_conservation` — scatter events should not increase ray weight
- `test_cylinder_intersection_basic` — ray through cylinder center returns two t values
- `test_cylinder_no_hit` — parallel ray misses cylinder
- `test_prism_intersection_triangle` — n_sides=3, ray through face hits exit face
- `test_farfield_direction_binning` — far-field result is direction-based not position-based

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection of `backlight_sim/sim/tracer.py` — confirmed intersection dispatch, Fresnel implementation, sphere accumulation, "::" naming convention
- Direct code inspection of `backlight_sim/sim/sampling.py` — confirmed CDF inversion pattern for 1D extension to 2D
- Direct code inspection of `backlight_sim/core/solid_body.py` — confirmed face naming, get_faces() pattern
- Direct code inspection of `backlight_sim/core/detectors.py` — confirmed SphereDetector dataclass, SphereDetectorResult
- Direct code inspection of `backlight_sim/io/ies_parser.py` — confirmed IES LM-63 structure for export reverse-engineering
- Direct code inspection of `backlight_sim/gui/angular_distribution_panel.py` — confirmed polar plot pattern using pg.PlotWidget
- Direct code inspection of `backlight_sim/gui/receiver_3d.py` — confirmed sphere mesh GLMeshItem construction
- Direct code inspection of `backlight_sim/gui/properties_panel.py` lines 1478-1617 — confirmed SolidBoxForm / FaceForm pattern

### Secondary (MEDIUM confidence)
- IESNA LM-63-2002 format structure: cross-verified against `load_ies()` implementation and standard IES photometric file format documentation. The format used in export_ies() skeleton above matches the parsing structure in the existing parser.
- Ray-cylinder analytic intersection: standard computer graphics formulation (quadratic discriminant) — well-known and verified against geometric derivation

### Tertiary (LOW confidence)
- None — all findings are based on direct code inspection of this repository

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, all verified against installed packages in requirements.txt
- Architecture patterns: HIGH — all patterns are directly derived from existing, working code in this repository
- Physics/math algorithms: HIGH — cylinder intersection and BSDF CDF are standard algorithms verified against implementation in the existing tracer
- Pitfalls: HIGH — all pitfalls derived from reading actual code paths that would trigger them
- GUI patterns: HIGH — all derived from existing PySide6/pyqtgraph code in this repository

**Research date:** 2026-03-14
**Valid until:** 2026-04-14 (stable codebase — no external library churn expected)
