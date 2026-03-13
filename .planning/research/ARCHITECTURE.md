# Architecture Patterns

**Domain:** Python Monte Carlo optical simulation — Phase 2 extensions
**Researched:** 2026-03-14
**Confidence:** HIGH (based on direct code analysis of existing codebase)

---

## Recommended Architecture

The existing layered architecture is sound and should be preserved. Phase 2 extends it by
adding new components at each layer, not restructuring existing ones. The strategy is
**additive extension** — every new feature plugs into defined integration points without
breaking existing paths.

```
app.py
  └── gui/main_window.py (MainWindow + SimulationThread)
        ├── gui/viewport_vtk.py          [NEW] VTK renderer, replaces viewport_3d.py
        ├── gui/viewport_3d.py           [EXISTING, keep as fallback]
        ├── gui/lgp_builder.py           [NEW] Edge-lit LGP scene wizard
        ├── gui/spectral_panel.py        [NEW] Spectral result display tab
        └── ... (all existing GUI panels unchanged)
              │
              ▼
  core/ (dataclasses — no physics, no GUI)
    ├── geometry.py          Rectangle [EXISTING]
    ├── solid_body.py        [NEW] SolidBody — axis-aligned box/cylinder/prism
    ├── lgp_geometry.py      [NEW] LGPSlab, CouplingFace, ExtractionDot
    ├── materials.py         Material + OpticalProperties [EXISTING, add brdf_name]
    ├── sources.py           PointSource [EXISTING, unchanged]
    ├── detectors.py         DetectorSurface + SphereDetector [EXISTING]
    └── project_model.py     Project [EXISTING, new fields added with .get defaults]
              │
              ▼
  sim/ (engine — numpy + optional numba)
    ├── tracer.py            RayTracer [EXISTING — extend bounce loop]
    ├── tracer_kernels.py    [NEW] @numba.jit kernels for hot paths
    ├── sampling.py          [EXISTING — add refraction/Fresnel sampling]
    ├── fresnel.py           [NEW] Snell's law + TIR + Fresnel R/T coefficients
    ├── solid_intersect.py   [NEW] Ray–box, ray–cylinder, ray–prism intersection
    ├── bvh.py               [NEW] BVH node + build + traverse
    └── spectral.py          [EXISTING, already complete]
              │
              ▼
  io/ (file I/O + scene construction)
    ├── project_io.py        [EXISTING — add serialization for new dataclasses]
    ├── geometry_builder.py  [EXISTING — add edge-lit LGP builder]
    ├── brdf_loader.py       [NEW] Load measured BRDF tables from CSV/BSDF XML
    ├── dxf_importer.py      [NEW] Parse DXF outlines → Rectangle list
    └── ... (all existing I/O unchanged)
```

---

## Component Boundaries

| Component | Responsibility | Communicates With | New for Phase 2 |
|-----------|---------------|-------------------|-----------------|
| `core/solid_body.py` | Data model for 3D solids (box/cylinder/prism), face list generation | `sim/solid_intersect.py`, `io/project_io.py`, `gui/` | YES |
| `core/lgp_geometry.py` | LGP slab dimensions, coupling face positions, dot extraction pattern | `sim/tracer.py`, `io/geometry_builder.py` | YES |
| `sim/fresnel.py` | Snell's law refraction, TIR critical angle check, Fresnel R/T coefficients | `sim/tracer.py` only | YES |
| `sim/solid_intersect.py` | Ray–AABB (axis-aligned bounding box), ray–cylinder, ray–prism intersection | `sim/tracer.py`, `sim/bvh.py` | YES |
| `sim/bvh.py` | Build BVH over surface+solid list; traverse to find closest hit | `sim/tracer.py` | YES |
| `sim/tracer_kernels.py` | `@numba.jit` versions of inner loops (intersection, accumulation) | `sim/tracer.py` (conditional import) | YES |
| `io/brdf_loader.py` | Load measured BRDF/BSDF tables; store as Dict in Project | `core/materials.py`, `io/project_io.py` | YES |
| `gui/viewport_vtk.py` | VTK/pyvistaqt 3D scene rendering; replaces pyqtgraph.opengl for solid bodies | `core/`, GUI panels | YES |
| `gui/lgp_builder.py` | Dialog to configure edge-lit LGP scene (slab dims, coupling, dots) | `io/geometry_builder.py`, `MainWindow` | YES |
| `gui/spectral_panel.py` | Display spectral simulation results (per-wavelength heatmaps, CIE chromaticity) | `sim/spectral.py`, `core/detectors.py` | YES |

---

## Data Flow

### Refractive Optics (TIR / Snell's Law) Flow

```
Surface hit detected (existing bounce loop)
  └── _resolve_optics(surf) returns mat with refractive_index
        ├── if mat.refractive_index == 1.0 → existing reflect/transmit behavior (unchanged)
        └── if mat.refractive_index != 1.0 → call fresnel.compute(ray_dir, normal, n1, n2)
              ├── fresnel.compute returns: (refracted_dir | None, R_coefficient, T_coefficient)
              ├── if TIR (refracted_dir is None) → specular reflect 100%
              └── if partial → stochastic split: roll < R → reflect, else → refract
                    └── refracted ray continues with new direction (Snell's law vector form)
```

**Key insight:** `n1` (medium of origin) must be tracked per-ray. Each ray needs a
`current_n` scalar that starts at 1.0 (air) and updates when entering/exiting a refractive
body. This is the only per-ray state addition needed.

### 3D Solid Body Flow

```
SolidBody defined in core/ (e.g. box: center + half-extents + per-face materials)
  └── SolidBody.decompose_faces() → list[Rectangle]  (6 faces for box)
        └── Faces are added to the intersection candidates list at tracer startup
              └── Hit detection via _intersect_rays_plane (EXISTING, no change needed)
                    └── Face material resolved via face.optical_properties_name
```

**Key insight:** Solid bodies decompose into their constituent rectangles at scene-load
time. The inner bounce loop sees only rectangles. This preserves all existing intersection
and material logic without modification, and makes Numba JIT on the inner loop simpler.

### Edge-Lit LGP Flow

```
LGPSlab geometry defined in core/lgp_geometry.py:
  - slab: large flat box (width × height × thickness), high refractive_index (~1.49 PMMA)
  - coupling face: one edge face = LED injection window
  - extraction dots: small circular patches on bottom face with lower reflectance

Propagation sequence:
  1. LEDs at slab edge emit horizontally (not upward)
  2. Rays couple into slab through coupling face (Fresnel transmission)
  3. Rays propagate inside slab — TIR keeps them trapped (critical angle ~42° for PMMA)
  4. Extraction dots interrupt TIR → rays scatter upward toward diffuser/detector
  5. Bottom reflector plate below slab redirects downward-scattered light back up

Critical physics additions required:
  - Fresnel transmission at coupling face (partial coupling loss)
  - TIR at top/bottom faces (total internal reflection when angle < critical)
  - Dot extraction (local absorption reduction + diffuse scatter upward)
  - Volume absorption in slab material (Beer-Lambert: weight *= exp(-mu * path_length))
```

### Spectral Integration Flow

```
PointSource.spd field (already exists in tracer.py as of current codebase)
  └── sample_wavelengths(n, spd_name, rng) → wavelengths: (n,) array  [EXISTING]
        └── wavelengths tracked per-ray through bounce loop  [EXISTING in _run_single]
              └── DetectorResult.grid_spectral accumulates per-wavelength flux  [EXISTING]
                    └── spectral_grid_to_rgb() converts to display image  [EXISTING]

Missing integration points:
  - Wavelength-dependent material properties: reflectance(λ), n(λ), absorption(λ)
    → Material needs optional spectral_reflectance dict: {wavelength_nm: reflectance}
    → Tracer interpolates reflectance at each ray's wavelength at bounce time
  - Multiprocessing path needs spectral support (currently stripped in _trace_single_source)
```

### Numba JIT Acceleration Flow

```
sim/tracer_kernels.py:
  @numba.jit(nopython=True)
  def intersect_all_planes_numba(origins, directions, normals, centers, u_axes, v_axes, sizes)
      → (best_t, best_obj)   # fully vectorized, no Python loop over surfaces

Tracer detects Numba availability at startup:
  try:
      from backlight_sim.sim import tracer_kernels as _kernels
      _NUMBA_AVAILABLE = True
  except ImportError:
      _NUMBA_AVAILABLE = False

Bounce loop uses kernel if available:
  if _NUMBA_AVAILABLE and not project.settings.force_numpy:
      best_t, best_obj = _kernels.intersect_all_planes_numba(...)
  else:
      # existing per-surface Python loop (unchanged fallback)
```

**Key insight:** Numba JIT should be applied to the inner intersection loop first —
it is the hottest path (called `N_rays × N_bounces × N_surfaces` times). The refraction
and accumulation code can be Numba-JIT'd in a follow-on pass.

### BVH Acceleration Flow

```
bvh.py:
  BVHNode: aabb_min, aabb_max, left, right, surface_indices (leaf)
  build_bvh(surfaces) → BVHNode (root)
  traverse_bvh(node, origins, directions) → (best_t, best_obj)

Replaces the O(N_rays × N_surfaces) flat intersection loop
with O(N_rays × log(N_surfaces)) tree traversal.

Integration point: tracer._run_single() builds BVH once before bounce loop if
  settings.use_bvh is True (default False until validated).
```

### VTK Renderer Integration Flow

```
gui/viewport_vtk.py (VTKWidget):
  Wraps pyvistaqt.BackgroundPlotter or QtInteractor
  Replaces gui/viewport_3d.py (pyqtgraph.opengl GLViewWidget)

MainWindow._setup_viewport():
  if VTK_AVAILABLE:
      self._viewport = VTKWidget(...)
  else:
      self._viewport = Viewport3D(...)   # existing fallback

Both viewport classes expose identical public API:
  .refresh_scene(project)
  .set_view_mode(mode)
  .set_camera_preset(preset)
  .highlight_object(name)
  .show_ray_paths(paths)

MainWindow only calls this interface — it never touches VTK or pyqtgraph directly.
```

---

## Patterns to Follow

### Pattern 1: Additive Field Extension for Project

**What:** Add new fields to `Project` and `SimulationSettings` with `.get(key, default)`
in serialization so old JSON files still load.

**When:** Every time a new feature needs persistent project state.

**Example:**
```python
# core/project_model.py
@dataclass
class Project:
    # ... existing fields ...
    solid_bodies: list[SolidBody] = field(default_factory=list)     # new
    lgp_slabs: list[LGPSlab] = field(default_factory=list)          # new
    brdf_tables: dict[str, BRDFTable] = field(default_factory=dict) # new

# io/project_io.py (load side)
solid_bodies_data = data.get("solid_bodies", [])   # safe fallback
```

### Pattern 2: Conditional Import for Optional Acceleration

**What:** Wrap Numba imports in try/except so the app runs without Numba installed.

**When:** Any optional high-performance dependency (Numba, VTK, pyvistaqt).

**Example:**
```python
# sim/tracer.py
try:
    from backlight_sim.sim import tracer_kernels as _kernels
    _NUMBA_AVAILABLE = True
except (ImportError, Exception):
    _NUMBA_AVAILABLE = False
```

### Pattern 3: Solid Body Face Decomposition

**What:** Solid bodies explode into rectangles at trace time, not at scene-definition time.
The tracer calls `solid.decompose_faces()` once before the bounce loop.

**When:** Adding box, cylinder (approximate as N-gon prism), or prism geometry.

**Example:**
```python
# sim/tracer.py, before bounce loop:
all_surfaces = list(project.surfaces)  # existing rectangles
for solid in project.solid_bodies:
    all_surfaces.extend(solid.decompose_faces())
# bounce loop uses all_surfaces — unchanged intersection code
```

### Pattern 4: Per-Ray State as Parallel Array

**What:** Additional per-ray state (current refractive index, wavelength) is stored as
a parallel numpy array of length N, not added to ray objects.

**When:** Any new physical quantity that varies per-ray.

**Example:**
```python
# sim/tracer.py, after ray emission:
current_n = np.ones(n, dtype=float)   # refractive index of current medium
# at refraction event:
current_n[refracted_rays] = mat.refractive_index
current_n[exited_rays] = 1.0          # back to air
```

### Pattern 5: Dual Viewport with Shared Interface

**What:** VTK and pyqtgraph viewports implement identical method signatures.
MainWindow calls the interface, never the concrete type.

**When:** Introducing an optional higher-quality renderer without forcing the dependency.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Tight-Coupling Spectral to Non-Spectral Path

**What:** Allocating `wavelengths`, `grid_spectral`, and `grid_rgb` arrays even when the
simulation is non-spectral (all sources have `spd = "white"`, `color_rgb = (1,1,1)`).

**Why bad:** Non-spectral simulations carry 40x memory overhead per detector grid;
breaks performance for typical direct-lit use cases.

**Instead:** The `has_spectral` / `has_color` conditional already exists in `_run_single`.
Keep it. Add analogous guards in `_trace_single_source` (multiprocessing path, which
currently strips spectral entirely).

### Anti-Pattern 2: Fresnel as a Material Surface Type

**What:** Adding `"refractive"` as a fourth `surface_type` string, parallel to
`"reflector"` / `"absorber"` / `"diffuser"`.

**Why bad:** Refractive behavior is not an alternative to reflection — it co-exists
with it (partial reflection at every interface). Treating it as a separate type breaks
the resolution hierarchy and forces a code branch in every material lookup.

**Instead:** Refractive behavior is triggered by `material.refractive_index != 1.0`.
Existing `surface_type` controls whether the surface reflects or transmits in the
non-refractive case; for refractive materials, Fresnel equations replace that
stochastic split.

### Anti-Pattern 3: LGP as a New Tracer Mode

**What:** Adding an `lgp_mode` flag to `SimulationSettings` that switches to an entirely
separate LGP-specific tracer.

**Why bad:** A parallel tracer duplicates the entire bounce loop, intersection logic,
path recording, multiprocessing, and cancellation infrastructure. Maintenance burden
doubles. The physics difference (TIR + Fresnel) can be expressed as material properties.

**Instead:** LGP is a scene configuration. The LGP slab is a solid body with
`refractive_index = 1.49`. TIR and Fresnel are handled by `sim/fresnel.py` called from
the existing `_bounce_surfaces` method. The existing tracer runs both direct-lit and
edge-lit scenes.

### Anti-Pattern 4: BVH Built Inside the Bounce Loop

**What:** Rebuilding the BVH on every bounce iteration.

**Why bad:** BVH construction is O(N log N) and dominates performance for small ray counts.
Scene geometry does not change during simulation.

**Instead:** Build BVH once before the bounce loop starts (after flattening all solid
faces into the surface list). Rebuild only when the project changes.

### Anti-Pattern 5: VTK as a Hard Dependency

**What:** Importing pyvistaqt unconditionally at module level in `gui/main_window.py`.

**Why bad:** VTK + pyvistaqt is a ~200MB dependency. PyInstaller builds become large;
users without VTK cannot launch the app at all.

**Instead:** Conditional import in `gui/viewport_vtk.py`, with graceful fallback to
existing `viewport_3d.py` if VTK is unavailable. `requirements.txt` lists pyvistaqt as
optional.

---

## Build Order (Phase Dependencies)

The five major feature areas have dependencies that constrain their build order:

```
1. Fresnel / TIR (sim/fresnel.py)
   └── Required by: LGP (TIR is what makes light guide propagation work)
   └── Required by: Solid body refraction (glass, lens bodies)
   └── No dependencies on other Phase 2 work

2. Spectral wavelength tracking in tracer (integrate sim/spectral.py into _bounce_surfaces)
   └── sim/spectral.py already complete — this is integration work only
   └── Requires: per-ray state extension (wavelengths array)
   └── No dependencies on Fresnel, BVH, or Numba

3. Solid body geometry (core/solid_body.py + sim/solid_intersect.py)
   └── Self-contained new geometry primitives
   └── Fresnel needed for refractive solid bodies (glass bodies) — do after Fresnel
   └── No dependency on spectral or Numba

4. LGP simulation (core/lgp_geometry.py + io/geometry_builder additions)
   └── Requires: Fresnel (TIR physics)
   └── Requires: Solid body (LGP slab is a box solid)
   └── Recommended: built after Fresnel + Solid body are stable

5. BVH + Numba (sim/bvh.py + sim/tracer_kernels.py)
   └── Pure performance optimization — zero new features, zero API change
   └── Should be done last: validates against existing test suite
   └── Requires: stable surface list (including solid body faces)

6. VTK renderer (gui/viewport_vtk.py)
   └── Pure GUI replacement — no sim layer changes
   └── Requires: solid body geometry in core/ (needs something to render)
   └── Can be done in parallel with BVH/Numba

Recommended sequence:
  Fresnel → Solid bodies → LGP → Spectral integration → BVH → Numba → VTK
  (Spectral integration and Solid bodies can be done in parallel)
```

### Dependency Matrix

| Feature | Depends On | Enables |
|---------|-----------|---------|
| Fresnel / TIR | Nothing | LGP, refractive solids |
| Spectral wavelength-dependent materials | Spectral.py (done) | Accurate color simulation |
| Solid body geometry | Fresnel (for glass) | LGP slab, mechanical obstacles, VTK |
| LGP simulation | Fresnel + Solid body | Edge-lit product category |
| BVH acceleration | Stable geometry (solid bodies done) | 10–100x speed for large scenes |
| Numba JIT | Stable intersection logic | 5–20x speed for small-medium scenes |
| VTK renderer | Solid body (something to render) | Better visualization |

---

## Integration Points in Existing Code

These are the exact locations where new code hooks in:

| Existing File | Hook Location | What to Add |
|---------------|--------------|-------------|
| `sim/tracer.py::_run_single()` | Before bounce loop | Flatten `solid_bodies` → faces; optionally build BVH |
| `sim/tracer.py::_bounce_surfaces()` | After `mat = self._resolve_optics(surf)` | If `mat.refractive_index != 1.0`, call `fresnel.compute()` |
| `sim/tracer.py::_run_single()` | Ray emission block | Add `current_n = np.ones(n)` parallel array |
| `sim/tracer.py::_run_single()` | `wavelengths` already sampled | Pass to `fresnel.compute()` for wavelength-dependent n |
| `sim/tracer.py::_trace_single_source()` | Detector accumulation | Add spectral accumulation (currently stripped) |
| `core/project_model.py::Project` | Field list | Add `solid_bodies`, `lgp_slabs`, `brdf_tables` |
| `core/materials.py::Material` | Fields | Add `brdf_name: str = ""`, `spectral_n: dict = field(default_factory=dict)` |
| `io/project_io.py::load_project()` | Deserialization | Handle new fields with `.get(key, default)` |
| `gui/main_window.py::_setup_viewport()` | Viewport construction | Try VTK, fallback to pyqtgraph |

---

## Scalability Considerations

| Concern | Current (Phase 1) | Phase 2 Impact | Mitigation |
|---------|------------------|----------------|------------|
| Intersection cost | O(N_rays × N_surfs) per bounce | Solid bodies add faces; LGP slab adds 6 | BVH reduces to O(N_rays × log N_surfs) |
| Memory per ray | weights (n,) float64 | Add wavelengths (n,) float64, current_n (n,) float64 | Only allocate when has_spectral=True |
| Multiprocessing spectral | Not supported (stripped) | Spectral grids not merged across processes | Extend `_trace_single_source` to return spectral data |
| VTK startup time | pyqtgraph: ~0.5s | VTK: ~1–2s | Lazy import; initialize viewport after main window shows |
| Numba JIT compile | N/A | First run: 1–5s JIT compile | Cache compiled functions (Numba's default behavior) |
| LGP ray count | 10k rays typical | LGP needs 100k+ for smooth extraction patterns | Add LGP quality preset in SimulationSettings |

---

## Sources

All analysis is based on direct code inspection of the existing codebase (HIGH confidence):

- `backlight_sim/sim/tracer.py` — full RayTracer implementation, bounce loop structure
- `backlight_sim/sim/spectral.py` — complete spectral utilities (CIE, SPD, wavelength sampling)
- `backlight_sim/sim/sampling.py` — ray direction sampling (Lambertian, angular CDF, haze)
- `backlight_sim/core/materials.py` — Material + OpticalProperties dual model
- `backlight_sim/core/geometry.py` — Rectangle with u_axis/v_axis pattern
- `backlight_sim/core/detectors.py` — DetectorSurface + SphereDetector + result types
- `backlight_sim/core/project_model.py` — Project container + SimulationSettings
- `backlight_sim/io/geometry_builder.py` — cavity / LED grid / optical stack builders
- `.planning/PROJECT.md` — Phase 2 requirements and constraints
- `.planning/codebase/ARCHITECTURE.md` — existing architecture analysis

Fresnel equations and BVH recommendations are from established Monte Carlo rendering
literature (Pharr & Humphreys "Physically Based Rendering"; Shirley "Ray Tracing in One
Weekend" series) — HIGH confidence for the physics, MEDIUM confidence for specific Python
implementation details without web verification.
