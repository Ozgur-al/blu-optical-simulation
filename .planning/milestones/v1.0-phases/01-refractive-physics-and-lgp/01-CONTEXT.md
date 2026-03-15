# Phase 1: Refractive Physics and LGP - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Engineers can simulate an edge-lit LGP panel with physically accurate TIR propagation and read edge coupling efficiency from the KPI dashboard. This phase adds Snell's law refraction, Fresnel/TIR physics, a solid box primitive with per-face optical properties, and LGP-specific scene building and KPIs.

Requirements covered: LGP-01, LGP-02, LGP-03, GEOM-01.

</domain>

<decisions>
## Implementation Decisions

### Solid body model
- New dedicated `SolidBox` dataclass that owns 6 Rectangle faces internally
- The user sees and edits one object; the tracer decomposes it into faces via `.get_faces() -> list[Rectangle]`
- Fields: name, center, dimensions (W,H,D), material_name (bulk material with refractive_index), face_optics (dict mapping face_id to OpticalProperties name)
- Axis-aligned only for Phase 1 (center + dimensions, no rotation matrix)
- Rotation support deferred to a future phase

### Per-face optical properties
- Faces are named: top, bottom, left, right, front, back
- All faces start with the bulk material's default optics
- User can override any individual face with a different OpticalProperties in the properties panel
- Existing OpticalProperties system is reused (already wired into the tracer)

### Scene tree presentation
- New "Solid Bodies" top-level category in the object tree
- SolidBox appears as a collapsible parent node with 6 child face nodes
- Selecting the parent edits box-level properties (dimensions, position, bulk material)
- Selecting a child face edits that face's OpticalProperties override
- In 3D viewport, rendered as a semi-transparent solid

### Fresnel and TIR physics
- Unpolarized average Fresnel coefficients: R = 0.5 * (Rs + Rp), T = 1 - R
- No polarization tracking per ray
- TIR: when sin(theta_t) > 1, R = 1.0 (total internal reflection)

### Reflect/transmit decision at Fresnel interface
- Stochastic Russian roulette: roll random number, if < R reflect (specular), else refract (Snell's law direction)
- Ray keeps full weight (energy-conserving, no ray splitting)

### Medium tracking
- Each ray carries a `current_n` value (starts at 1.0 for air)
- When entering a SolidBox face (dot product with outward normal < 0): n1 = current_n, n2 = box material refractive_index, ray.current_n = n2
- When exiting a SolidBox face (dot product > 0): n1 = current_n, n2 = 1.0, ray.current_n = 1.0

### Refraction scope
- Fresnel/refraction only triggers on SolidBox face hits
- Existing Rectangle surfaces keep their current reflect/absorb/diffuse behavior unchanged
- No refraction on legacy surfaces even if material has refractive_index > 1

### LGP scene builder
- New preset "Edge-Lit LGP" in the Presets menu (alongside Simple Box and Automotive Cluster)
- New "LGP" tab in the Geometry Builder dialog
- Builder parameters: LGP width, height, thickness, material (default PMMA), coupling edge(s), LED count, LED pitch (auto)
- Multi-edge coupling support: user can select 1-4 edges (Left, Right, Front, Back) for LED placement — covers single-edge, L-shaped, and U-shaped configurations
- Full scene auto-build: creates LGP slab + LEDs at coupling edge(s) + detector above top face + reflector below bottom face
- All objects editable after creation

### Built-in materials
- Auto-created PMMA material: refractive_index = 1.49, low absorption
- Auto-created reflector OpticalProperties for the bottom face
- Materials are created only if they don't already exist in the project

### Edge coupling KPI
- Edge coupling efficiency = flux entering LGP through coupling face(s) / total emitted flux
- Extraction efficiency = flux at detector / flux entering coupling face(s)
- Both metrics displayed in the Energy Balance section of the KPI dashboard
- Only shown when a SolidBox exists in the scene

### Flux tracking at SolidBox faces
- Each SolidBox face accumulates entering/exiting flux during simulation via per-face counters
- Post-simulation: coupling face flux feeds the coupling KPI, detector flux feeds the extraction KPI
- Results stored in `SimulationResult.solid_body_stats`

### Claude's Discretion
- Exact SolidBox 3D rendering approach (GLMeshItem vs face quads)
- Self-intersection epsilon handling at SolidBox faces
- LGP builder dialog layout details
- Default gap distances for auto-placed detector and reflector
- How face_optics defaults are stored (explicit dict vs lazy lookup)

</decisions>

<specifics>
## Specific Ideas

- SolidBox face naming follows physical convention: top/bottom/left/right/front/back
- LGP builder should support multi-edge LED placement for L-shaped and U-shaped backlight configurations
- Full scene auto-build means one-click to a runnable edge-lit simulation
- KPI dashboard shows coupling, extraction, and overall efficiency (coupling x extraction) together

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Material.refractive_index` field already exists (default 1.0) — just needs to be wired to physics
- `OpticalProperties` dataclass + per-surface override via `optical_properties_name` on Rectangle — reuse for per-face optics
- `_intersect_rays_plane()` in tracer.py — reuse for SolidBox face intersection (each face is a Rectangle)
- `build_cavity()` and `build_led_grid()` in io/geometry_builder.py — pattern for the LGP builder
- `preset_simple_box()` and `preset_automotive_cluster()` in io/presets.py — pattern for the LGP preset
- `reflect_specular()` in sim/sampling.py — reuse for Fresnel reflection direction

### Established Patterns
- Tracer resolves optics via `_resolve_optics(surf)` — checks OpticalProperties first, falls back to Material
- Object tree uses QTreeWidget with top-level categories (Sources, Surfaces, Materials, Detectors) — add "Solid Bodies"
- Properties panel uses QStackedWidget with per-type forms — add SolidBoxForm and FaceForm
- Project model uses flat lists/dicts of dataclasses — add `solid_bodies: list[SolidBox]`
- JSON save/load in project_io.py handles numpy arrays as plain lists — extend for SolidBox

### Integration Points
- `RayTracer._bounce_surfaces()` — needs new branch for SolidBox face hits (Fresnel/refraction)
- `Project` dataclass — add `solid_bodies` field
- `SimulationResult` — add `solid_body_stats` for per-face flux data
- `heatmap_panel.py` KPI dashboard — add LGP metrics row in energy balance section
- `object_tree.py` — add Solid Bodies category
- `properties_panel.py` — add SolidBox and face editing forms
- `viewport_3d.py` — render SolidBox as solid geometry
- `project_io.py` — serialize/deserialize SolidBox

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-refractive-physics-and-lgp*
*Context gathered: 2026-03-14*
