# Phase 4: Advanced Materials and Geometry - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can assign measured BSDF data to surfaces, capture far-field candela distributions, and build cylindrical and prism optical elements. This phase rounds out the physical model with tabulated scattering, angular detection, and non-rectangular solid bodies.

</domain>

<decisions>
## Implementation Decisions

### BSDF model
- Full BSDF only — no separate BRDF or BTDF accepted; the uploaded table must cover both reflection and transmission
- Isotropic (1D) model: for each incident angle theta_in, a reflected and transmitted intensity profile I(theta_out)
- CSV import format: columns theta_in, theta_out, refl_intensity, trans_intensity; absorption derived as remainder
- BSDF profile assigned to OpticalProperties — overrides all manual reflectance/transmittance/diffuse values when set
- When no BSDF is assigned, manual values apply as before (backward compatible)
- Stored in project as `project.bsdf_profiles = {name: {theta_in, theta_out, refl_intensity, trans_intensity}}`
- Tracer sampling: 2D CDF inversion per incident angle, extending existing sample_angular_distribution() pattern

### Far-field detector
- Extend existing SphereDetector with a `mode` field: `"near_field"` (default, existing behavior) or `"far_field"` (direction-only accumulation)
- Full sphere coverage: theta 0-180 deg, phi 0-360 deg
- Candela computed as flux / solid_angle_per_bin
- Display: both polar plot and 3D intensity lobe in viewport
- Polar plot: multi-slice C-plane overlay (C0, C90, etc.) with color-coded lines and checkboxes
- 3D lobe: solid color-mapped mesh surface (radius proportional to candela, cool-to-warm colormap)
- Far-field KPIs shown in the polar plot panel: peak cd, total lm, beam angle (50% peak), field angle (10% peak), asymmetry
- IES export via existing io/ies_parser.py — add export_ies() function
- CSV export for raw candela data

### Cylinder solid body
- Analytic ray-cylinder intersection (quadratic equation for curved surface, plane intersection for end caps)
- Parameterization: center, axis direction vector, radius, length — supports any orientation
- Three faces: "top_cap", "bottom_cap", "side" — per-face optical overrides via face_optics dict
- Full Fresnel/TIR refractive physics (same as SolidBox, detected via "::" naming convention)
- 3D viewport: smooth 64-segment mesh rendering, supports wireframe/solid/transparent view modes

### Prism solid body
- Regular polygon cross-section: defined by n_sides, circumscribed radius, length, axis direction, center
- Flat side faces: reuse existing _intersect_rays_plane() for side faces
- End caps: plane intersection with point-in-polygon test for non-rectangular clipping
- Faces: "cap_top", "cap_bottom", "side_0" through "side_{n-1}" — per-face optical overrides
- Full Fresnel/TIR refractive physics (same "::" convention)

### GUI integration
- Cylinder and prism appear under Surfaces category in object tree, expandable to show faces (same pattern as SolidBox)
- Dedicated BSDF panel (new top-level tab, separate from Angular Distribution panel)
- BSDF panel includes: profile list, import CSV/delete buttons, 2D heatmap (theta_in x theta_out) for overview, click-to-select line plot detail per theta_in row, separate reflection/transmission views
- BSDF assignment: dropdown on OpticalProperties form; when a BSDF profile is selected, manual reflectance/transmittance/diffuse fields are greyed out
- Far-field result panel: polar plot with multi-slice overlay + KPI sidebar + export buttons
- Property forms for SolidCylinder and SolidPrism following SolidBoxForm pattern

### Claude's Discretion
- Exact CDF interpolation grid resolution for BSDF sampling
- Cylinder mesh segment count for 3D rendering (recommended 64)
- Prism end-cap triangulation approach
- Polar plot color palette for C-plane overlays
- 3D intensity lobe colormap choice and scaling
- Error handling for malformed BSDF CSV files

</decisions>

<specifics>
## Specific Ideas

- BSDF must be a complete scattering function — partial BRDF or BTDF files are rejected at import
- Cylinder parameterization should feel natural for light pipes and rod lenses (center + axis + radius + length)
- Prism covers common optical elements: triangular prisms (n_sides=3), hexagonal rods (n_sides=6), etc.
- Far-field polar plot should look like standard luminaire photometric datasheets with multi-slice overlays

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SolidBox` (core/solid_body.py): established pattern for solid bodies with get_faces(), face_optics, and "::" naming convention
- `SphereDetector` + `SphereDetectorResult` (core/detectors.py): theta/phi grid accumulation — far-field extends this
- `sample_angular_distribution()` (sim/sampling.py): 1D CDF inversion from I(theta) tables — BSDF sampling extends this to 2D
- `_intersect_rays_plane()` (sim/tracer.py): vectorized ray-plane intersection — reused for prism side faces and end caps
- `_fresnel_unpolarized()` + `_refract_snell()` (sim/tracer.py): Fresnel/TIR physics — reused for cylinder and prism
- `load_ies()` (io/ies_parser.py): IES import parser — export_ies() function added here
- `SolidBoxForm` (gui/properties_panel.py): property editor pattern for solid bodies
- `angular_distribution_panel.py`: pattern for tabulated data management panel (import/export/plot)

### Established Patterns
- Solid body faces identified by "::" separator in Rectangle name → triggers Fresnel/TIR path in tracer
- OpticalProperties priority chain: optical_properties_name → material fallback
- View modes (wireframe/solid/transparent) via pyqtgraph.opengl GLMeshItem
- Object tree: expandable parent items with child face items (SolidBox pattern)

### Integration Points
- `Project` dataclass: new `bsdf_profiles` dict, new `solid_cylinders` and `solid_prisms` lists
- `project_io.py`: serialize/deserialize new solid body types and BSDF profiles
- `tracer.py`: BSDF reflection/transmission sampling, cylinder analytic intersection, far-field accumulation mode
- `object_tree.py`: cylinder and prism tree items with face children
- `properties_panel.py`: SolidCylinderForm, SolidPrismForm, BSDF dropdown on OpticalProperties form
- `viewport_3d.py`: cylinder mesh rendering, prism mesh rendering, 3D intensity lobe overlay

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-advanced-materials-and-geometry*
*Context gathered: 2026-03-14*
