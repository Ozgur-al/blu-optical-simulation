# Phase 6: Tracer Cross-Phase Wiring - Research

**Researched:** 2026-03-15
**Domain:** Python simulation engine — tracer dispatch, multiprocessing, spectral material lookup, BSDF interaction
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| GEOM-02 | User can create cylinder solid body primitives | Cylinder/prism dispatch is absent from `_trace_single_source` (MP path lines 1178–1325) — wiring gap confirmed in source |
| GEOM-03 | User can create prism solid body primitives | Same gap as GEOM-02; prism_faces never built inside `_trace_single_source` |
| LGP-01 | User can define an LGP slab as a solid box with independent optical properties per face | `face_optics` dict is set correctly on each Rectangle at SolidBox.get_faces() line 209; tracer never reads it back during Fresnel bounce dispatch (lines 697–770) |
| SPEC-04 | Material reflectance and transmittance can be defined as wavelength-dependent tables | `spectral_material_data` lookup only wired in `_bounce_surfaces` for type=0 Rectangle; solid body Fresnel branches (type 3/4/5) use only scalar `mat.refractive_index` |
| BRDF-01 | User can import tabulated BSDF data and assign it to surfaces | BSDF dispatch executes `continue` at line 1084, silently skipping the `spectral_material_data` lookup that follows it — mutual exclusion with SPEC-04 |
</phase_requirements>

---

## Summary

Phase 6 closes four verified integration gaps discovered in the v1.0 milestone audit. All gaps are in a single file (`backlight_sim/sim/tracer.py`) and involve omissions rather than wrong logic — the needed data structures and helper functions are already present and correct; they simply are not called in all code paths.

**Gap 1 (GEOM-02/GEOM-03 — Cylinder/Prism MP):** `_trace_single_source` (the multiprocessing worker function, lines 1142–1560) only expands `project.solid_bodies` (SolidBox). It never builds `cyl_faces`, `cyl_face_map`, `prism_faces`, or `prism_face_map`. The bounce loop therefore never hits cylinder/prism geometry in MP mode; those objects are invisible. The fix is to copy the expansion and dispatch blocks from `_run_single` into `_trace_single_source`.

**Gap 2 (LGP-01 — face_optics):** SolidBox faces are already created with per-face `optical_properties_name` set in `solid_body.py` line 209, but the tracer Fresnel branch for type=3 hits (lines 697–770) ignores this field. It uses only `box.material_name` as the refractive index source and never consults `box.face_optics`. The fix is to apply the face's `optical_properties_name` (if set and resolves to an `OpticalProperties` object) for surface-level behavior at that face — specifically: if the face_optics entry points to an `OpticalProperties` with surface_type != blank, handle it as a custom surface rather than pure Fresnel. For the LGP use case (bottom reflector), the per-face optics should override Fresnel with reflector/absorber behavior.

**Gap 3 (SPEC-04 — spectral solid body Fresnel):** `_bounce_surfaces` receives `wavelengths` and `spectral_material_data` and applies per-wavelength R/T (lines 1086–1102) for type=0 Rectangle surfaces. The Fresnel branches for type=3/4/5 (lines 688–883) receive no `wavelengths` array and perform no spectral lookup. The fix is to pipe the wavelength array into each Fresnel branch and do a spectral interpolation of n(λ) when `spectral_material_data` provides it, then feed the wavelength-dependent n into `_fresnel_unpolarized`.

**Gap 4 (BRDF-01+SPEC-04 — BSDF skips spectral):** In `_bounce_surfaces`, the BSDF dispatch (lines 1030–1084) ends with `continue`, skipping the spectral material lookup at lines 1086–1102. Surfaces with both `bsdf_profile_name` and a `spectral_material_data` entry get BSDF-only behavior. The fix is to move the spectral R/T interpolation before the BSDF dispatch so wavelength-dependent scaling is applied even when BSDF is active.

**Primary recommendation:** All four gaps are surgical edits to `tracer.py` — add cylinder/prism expansion to `_trace_single_source`, read face `optical_properties_name` in the SolidBox Fresnel branch, thread `wavelengths` into Fresnel branches for spectral R/T, and apply spectral R/T scaling before (not after) BSDF dispatch. No new data structures or helper functions are needed.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | (project existing) | Vectorized ray operations, boolean masking, einsum | Already used throughout tracer; no change |
| pytest | (project existing) | Unit tests for each gap | 102 tests already passing; extend existing file |

### No New Dependencies

This phase adds no new packages. All fixes are purely within `backlight_sim/sim/tracer.py` (and possibly one line in `_bounce_surfaces`). The project's existing stack is sufficient.

---

## Architecture Patterns

### Recommended Project Structure

No new files required. Changes confined to:

```
backlight_sim/
└── sim/
    └── tracer.py      # All 4 gaps are here
backlight_sim/
└── tests/
    └── test_tracer.py  # New integration tests for each gap
```

### Pattern 1: Cylinder/Prism Expansion in MP Worker

**What:** `_trace_single_source` must replicate the cylinder and prism face expansion logic already in `_run_single` (lines 361–393).
**When to use:** At the top of `_trace_single_source`, immediately after the existing SolidBox expansion block (lines 1178–1196).

```python
# After existing solid_faces / solid_face_map setup in _trace_single_source:

# Expand SolidCylinder objects into face-like objects and build lookup
cyl_faces = []
cyl_face_map = {}  # face_name -> (cyl, face_id, cyl_n, geom_eps)
for cyl in getattr(project, "solid_cylinders", []):
    mat = materials.get(cyl.material_name)
    cyl_n = mat.refractive_index if mat is not None else 1.0
    geom_eps = max(_EPSILON, min(cyl.radius, cyl.length / 2.0) * 1e-4)
    for face in cyl.get_faces():
        cyl_faces.append(face)
        face_id = face.name.split("::", 1)[1]
        cyl_face_map[face.name] = (cyl, face_id, cyl_n, geom_eps)
    sb_stats[cyl.name] = {
        fid: {"entering_flux": 0.0, "exiting_flux": 0.0}
        for fid in ("top_cap", "bottom_cap", "side")
    }

# Expand SolidPrism objects into face-like objects and build lookup
prism_faces = []
prism_face_map = {}
for prism in getattr(project, "solid_prisms", []):
    mat = materials.get(prism.material_name)
    prism_n = mat.refractive_index if mat is not None else 1.0
    geom_eps = max(_EPSILON, min(prism.circumscribed_radius, prism.length / 2.0) * 1e-4)
    for face in prism.get_faces():
        prism_faces.append(face)
        face_id = face.name.split("::", 1)[1]
        prism_face_map[face.name] = (prism, face_id, prism_n, geom_eps)
    all_face_ids = ["cap_top", "cap_bottom"] + [f"side_{i}" for i in range(prism.n_sides)]
    sb_stats[prism.name] = {
        fid: {"entering_flux": 0.0, "exiting_flux": 0.0}
        for fid in all_face_ids
    }
```

Then in the bounce loop in `_trace_single_source`, add intersection and dispatch for type=4 and type=5 (copy from `_run_single` lines 596–883, substituting `self.rng` with `rng`).

### Pattern 2: face_optics Consumption in SolidBox Fresnel Branch

**What:** When a SolidBox face has `optical_properties_name` set, the tracer should check if that OpticalProperties entry overrides the Fresnel behavior before applying pure Fresnel R/T.
**When to use:** In the type=3 hit dispatch block (line ~697), after extracting `box, face_id, box_n, geom_eps` from `solid_face_map`.

```python
# In type=3 (SolidBox face hit) dispatch, in both _run_single and _trace_single_source:
box, face_id, box_n, geom_eps = solid_face_map[sface.name]

# Check face_optics override
face_op_name = sface.optical_properties_name   # set by SolidBox.get_faces() line 209
if face_op_name:
    # Look up in self.project.optical_properties (or project.optical_properties in MP)
    face_op = (self.project if hasattr(self, "project") else project).optical_properties.get(face_op_name)
    if face_op is not None and face_op.surface_type in ("reflector", "absorber", "diffuser"):
        # Delegate to standard surface behavior rather than Fresnel
        _apply_surface_optics(face_op, ...)  # inline or call helper
        continue
# else: fall through to Fresnel
```

**Key insight:** The LGP bottom_reflector override (primary use case) uses `optical_properties_name` pointing to a reflector. The tracer should check `surface_type != ""` to decide whether to use non-Fresnel behavior. Pure refractive faces leave `face_optics` empty, so the default path is unchanged.

### Pattern 3: Spectral R/T in Solid Body Fresnel Branches

**What:** When `has_spectral` is True and `spectral_material_data` has an entry for the solid body's material, the scalar `box_n`/`cyl_n`/`prism_n` used in `_fresnel_unpolarized` should be replaced by wavelength-dependent values `n(λ)`.
**When to use:** In each of the three Fresnel branches (type 3, 4, 5) when `wavelengths is not None`.

```python
# Pattern for spectral n(λ) lookup in Fresnel branches:
spec_data = (spectral_material_data or {}).get(body.material_name) if wavelengths is not None else None
if spec_data is not None and "refractive_index" in spec_data:
    spec_wl = np.asarray(spec_data["wavelength_nm"], dtype=float)
    n_lambda = np.interp(wavelengths[hit_idx], spec_wl,
                         np.asarray(spec_data["refractive_index"], dtype=float))
    n2_arr = np.where(entering, n_lambda, 1.0)
else:
    n2_arr = np.where(entering, body_n, 1.0)
```

**Note:** The `spectral_material_data` schema currently stores `reflectance` and `transmittance` per wavelength for surfaces. For refractive bodies, the requirement (SPEC-04) is that R/T are wavelength-dependent. The Fresnel formula already computes R from n1/n2 and angle, so providing n(λ) is the physically correct path. If `spectral_material_data` for solid bodies stores an `"refractive_index"` array, that is the correct column to use.

**Fallback:** If no `refractive_index` spectral column is found but a `reflectance` spectral column exists, the tracer can apply a wavelength-dependent weight scaling on top of the Fresnel R result. This is less physically correct but preserves the intent of SPEC-04.

### Pattern 4: BSDF+Spectral — Move Spectral Scaling Before `continue`

**What:** In `_bounce_surfaces`, the `continue` after BSDF dispatch (line 1084) skips spectral material lookup. Move the spectral R/T scale factor computation before the BSDF block, then apply it inside the BSDF branch.
**When to use:** Lines 1030–1084 in `_bounce_surfaces`.

```python
# Before BSDF dispatch block, compute spectral weight scale factor:
optics_name = getattr(surf, "optical_properties_name", "") or surf.material_name
spec_data = (spectral_material_data or {}).get(optics_name)
spectral_r_scale = None
spectral_t_scale = None
if spec_data is not None and wavelengths is not None:
    ray_wl = wavelengths[hit_idx]
    spec_wl = np.asarray(spec_data["wavelength_nm"], dtype=float)
    spectral_r_scale = np.interp(ray_wl, spec_wl,
                                 np.asarray(spec_data["reflectance"], dtype=float))
    t_data = spec_data.get("transmittance")
    if t_data is not None:
        spectral_t_scale = np.interp(ray_wl, spec_wl,
                                     np.asarray(t_data, dtype=float))

# In BSDF branch, apply spectral weight scaling before direction update:
if spectral_r_scale is not None:
    weights[hit_idx] *= spectral_r_scale   # or t_scale for transmit
```

### Anti-Patterns to Avoid

- **Duplicating bounce loop logic without abstraction:** The type 4/5 dispatch blocks are long. Copy them exactly from `_run_single` into `_trace_single_source`, substituting `self.rng` → `rng`. Do not try to refactor into a shared function — the MP function must be pickleable and cannot hold a reference to a `RayTracer` instance method.
- **Removing the spectral+MP guard:** The existing `has_spectral and settings.use_multiprocessing` guard at line 175 still correctly blocks full spectral simulation in MP mode. Do NOT remove this guard. Gap 3 only addresses the single-thread path.
- **Modifying SolidBox.get_faces():** face_optics are already correctly set in `get_faces()` line 209. The fix belongs entirely in the tracer dispatch, not in solid_body.py.
- **Adding face_optics override for cylinder/prism first pass:** SolidCylinder and SolidPrism also have `face_optics` dicts, but the priority for this phase is SolidBox face_optics (LGP-01). Cylinder/prism face_optics can be deferred — they are not part of GEOM-02/GEOM-03 success criteria.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-wavelength refractive index interpolation | Custom spline/table class | `np.interp(wavelengths, spec_wl, n_data)` | Already used throughout tracer for R/T; consistent, vectorized |
| Cylinder/prism intersection in MP | New intersection functions | `_intersect_rays_cylinder_side`, `_intersect_rays_disc`, `_intersect_prism_cap` already in same file | Functions are module-level and pickleable; no duplication needed |
| Per-face material resolution | New lookup system | `sface.optical_properties_name` already set by `SolidBox.get_faces()` line 209; `project.optical_properties.get(name)` already wired | The data is already there; just read it |
| BSDF+spectral combination model | New material type | Apply spectral weight scale factor before BSDF scatter direction sampling | Spectral R/T is a weight multiplier; BSDF controls scatter direction; these are independent and compose cleanly |

**Key insight:** This entire phase is wiring work, not new feature development. Every capability needed (cylinder/prism Fresnel, spectral interpolation, face optical properties lookup) exists in the single-thread path. The plan tasks are: identify the omission, locate the existing code block, copy/adapt it into the missing location.

---

## Common Pitfalls

### Pitfall 1: Missing `_CYLINDER_FACE_NAMES` import in `_trace_single_source`
**What goes wrong:** When expanding cylinder faces in the MP worker, `sb_stats` initialization uses the string literals `("top_cap", "bottom_cap", "side")`. If a refactor moves these to a constant that is not imported, the MP function fails at pickle time.
**Why it happens:** `_trace_single_source` is a module-level function. It can use module-level constants but cannot reference `self` or instance variables.
**How to avoid:** Use string literals directly in `_trace_single_source` (as done for cylinder face IDs at line 375 in `_run_single`). Do not import `CYLINDER_FACE_NAMES` from `solid_body` unless it is already in the import list.
**Warning signs:** `AttributeError` or `NameError` only when `use_multiprocessing=True`.

### Pitfall 2: `rng` vs `self.rng` in MP worker
**What goes wrong:** The MP worker function uses a local `rng` variable (derived from hash, line 1150). Code copied from `_run_single` uses `self.rng`. Forgetting to substitute the two will raise `NameError: name 'self' is not defined` at runtime in subprocess.
**Why it happens:** `_trace_single_source` is a top-level function, not a method.
**How to avoid:** Text-search every copied block for `self.rng` before committing.
**Warning signs:** `NameError` in subprocess futures that surfaces as a warning string at line 280–283.

### Pitfall 3: face_optics override silently changes Fresnel behavior
**What goes wrong:** If face_optics consumption is implemented too broadly (e.g., always checking for an override even when surface_type is empty or the OpticalProperties has no surface_type), faces that are meant to be pure dielectric interfaces will be treated as diffusers/reflectors.
**Why it happens:** `OpticalProperties` objects may exist for LGP coupling faces without a meaningful `surface_type`.
**How to avoid:** Only activate non-Fresnel behavior when `face_op.surface_type in ("reflector", "absorber", "diffuser")`. If `face_op` is None or surface_type is blank, fall through to Fresnel.
**Warning signs:** LGP slab transmits much less flux than expected; edge coupling efficiency drops to near zero.

### Pitfall 4: Spectral n(λ) data not present in `spectral_material_data`
**What goes wrong:** `spectral_material_data` schema was designed for surface R/T (reflectance, transmittance columns). Solid bodies need refractive_index n(λ). If spectral_material_data for a material has no `refractive_index` column, the code silently falls through to scalar n.
**Why it happens:** SPEC-04 states "reflectance and transmittance can be defined as wavelength-dependent" — the refractive index column is an extension of this design.
**How to avoid:** Check for `"refractive_index"` key explicitly before attempting n(λ) interpolation. Document in a code comment that the schema supports optional `refractive_index` array alongside `reflectance`/`transmittance`. Falling back to scalar n is safe and correct for existing projects.
**Warning signs:** No error, but spectral simulation of solid bodies gives same result as non-spectral.

### Pitfall 5: `sb_stats` merge in `_run_multiprocess` missing cylinder/prism keys
**What goes wrong:** `_run_multiprocess` (line 224–229) only initializes `merged_sb_stats` for `project.solid_bodies`. If cylinder/prism stats are returned in `result["sb_stats"]`, the merge loop at lines 270–274 will skip unknown keys, silently losing those stats.
**Why it happens:** `merged_sb_stats` was built before cylinder/prism were added to the MP worker.
**How to avoid:** Initialize `merged_sb_stats` for `solid_cylinders` and `solid_prisms` as well, using the correct face ID sets.
**Warning signs:** Cylinder/prism KPI stats show zero entering/exiting flux even when simulation is running correctly.

---

## Code Examples

Verified patterns from existing source:

### Existing cylinder expansion in `_run_single` (source of truth)
```python
# backlight_sim/sim/tracer.py lines 361-393 (_run_single):
cyl_faces: list = []
cyl_face_map: dict[str, tuple] = {}
for cyl in getattr(self.project, "solid_cylinders", []):
    mat = materials.get(cyl.material_name)
    cyl_n = mat.refractive_index if mat is not None else 1.0
    geom_eps = max(_EPSILON, min(cyl.radius, cyl.length / 2.0) * 1e-4)
    for face in cyl.get_faces():
        cyl_faces.append(face)
        face_id = face.name.split("::", 1)[1]
        cyl_face_map[face.name] = (cyl, face_id, cyl_n, geom_eps)
    sb_stats[cyl.name] = {
        fid: {"entering_flux": 0.0, "exiting_flux": 0.0}
        for fid in ("top_cap", "bottom_cap", "side")
    }
```

### Existing spectral R/T interpolation in `_bounce_surfaces` (source of truth)
```python
# backlight_sim/sim/tracer.py lines 1086-1102 (_bounce_surfaces):
optics_name = getattr(surf, "optical_properties_name", "") or surf.material_name
spec_data = (spectral_material_data or {}).get(optics_name)
if spec_data is not None and wavelengths is not None:
    ray_wl = wavelengths[hit_idx]
    spec_wl = np.asarray(spec_data["wavelength_nm"], dtype=float)
    r_vals = np.interp(ray_wl, spec_wl,
                       np.asarray(spec_data["reflectance"], dtype=float))
    t_data = spec_data.get("transmittance")
    if t_data is not None:
        t_vals_spec = np.interp(ray_wl, spec_wl,
                                np.asarray(t_data, dtype=float))
    else:
        t_vals_spec = np.full_like(r_vals, mat.transmittance)
```

### Existing face_optics population in SolidBox.get_faces() (source of truth)
```python
# backlight_sim/core/solid_body.py line 209:
rect.optical_properties_name = self.face_optics.get(face_id, "")
```

### Existing BSDF `continue` that blocks spectral lookup (the gap itself)
```python
# backlight_sim/sim/tracer.py line 1084 (_bounce_surfaces):
                continue       # <-- this skips lines 1086–1102 (spectral lookup)

            # Resolve spectral material properties (per-wavelength R/T lookup)
            optics_name = getattr(surf, "optical_properties_name", "") or surf.material_name
            spec_data = (spectral_material_data or {}).get(optics_name)
```

### `_run_multiprocess` sb_stats init (shows current gap for cylinder/prism)
```python
# backlight_sim/sim/tracer.py lines 224-229 (_run_multiprocess):
merged_sb_stats: dict[str, dict[str, dict[str, float]]] = {}
for box in self.project.solid_bodies:             # only SolidBox, not cylinders/prisms
    merged_sb_stats[box.name] = {
        fid: {"entering_flux": 0.0, "exiting_flux": 0.0}
        for fid in FACE_NAMES
    }
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No per-face optical override | face_optics dict populated in SolidBox.get_faces(), NOT consumed by tracer | Phase 1 | LGP bottom reflector has zero physical effect — this phase wires the consumption |
| No spectral in MP | spectral+MP guard falls back to single thread | Phase 2 | Still applies; do not change this guard |
| No cylinder/prism in MP | Cylinder/prism expansion absent from `_trace_single_source` | Phase 4 | Zero flux from cylinders/prisms in MP — this phase adds expansion |
| BSDF skips spectral | `continue` before spectral lookup in `_bounce_surfaces` | Phase 4 | Surfaces with both BSDF and spectral data ignore spectral — this phase inserts scale factor before continue |

**Not deprecated in this phase:**
- The spectral+MP guard remains. This phase does NOT enable spectral+MP; it only fixes cylinder/prism in the existing non-spectral MP path.
- The `_run_single` Fresnel branches remain unchanged except for spectral n(λ) wiring.

---

## Open Questions

1. **What exact schema does `spectral_material_data` use for refractive solid bodies?**
   - What we know: The schema stores `{wavelength_nm, reflectance, transmittance}` for surface materials (confirmed in `_bounce_surfaces` lines 1090–1098). A `refractive_index` column is not present in any existing project files.
   - What's unclear: Should SPEC-04 for solid bodies add a `refractive_index` spectral column to `spectral_material_data`, or should it apply wavelength-dependent absorptance as a weight multiplier on top of Fresnel?
   - Recommendation: Implement the simpler path first — if a material in `spectral_material_data` has a `refractive_index` array, use it for n(λ) in Fresnel. Otherwise, fall back to scalar refractive_index. This is backward-compatible and does not require schema changes. Document the optional column. The planner can add a schema note to `project_io.py` serialization.

2. **Should face_optics override apply in the MP path too?**
   - What we know: Gap 2 (LGP-01) is about the `_run_single` path failing to consume face_optics. The MP path (`_trace_single_source`) also has the same omission.
   - What's unclear: Whether both paths must be fixed simultaneously or if fixing `_run_single` is sufficient for v1.0.
   - Recommendation: Fix both paths in the same task. The code change is identical (same conditional check); duplicating the fix is the safest approach for correctness.

3. **Does the `sb_stats` merge in `_run_multiprocess` need updating for cylinder/prism stats?**
   - What we know: `merged_sb_stats` initialization at lines 224–229 only covers `solid_bodies`. When cylinder/prism stats are added to `_trace_single_source`, the merge loop at lines 270–274 uses `if box_name in merged_sb_stats` and will silently skip unknown names.
   - What's unclear: Whether cylinder/prism KPI stats (entering/exiting flux) are currently displayed anywhere in the GUI that would reveal the omission.
   - Recommendation: Extend `merged_sb_stats` initialization to include solid_cylinders and solid_prisms with their correct face ID sets. This is a one-time fix required for completeness.

---

## Validation Architecture

*nyquist_validation is not set in .planning/config.json — skipping this section.*

---

## Sources

### Primary (HIGH confidence)

- `backlight_sim/sim/tracer.py` — direct code inspection, lines 1142–1560 (`_trace_single_source`), lines 224–297 (`_run_multiprocess`), lines 361–393 (cylinder/prism expansion in `_run_single`), lines 1030–1084 (BSDF dispatch with `continue`)
- `backlight_sim/core/solid_body.py` — line 209 (`rect.optical_properties_name = self.face_optics.get(face_id, "")`)
- `.planning/v1.0-MILESTONE-AUDIT.md` — integration gaps section, confirmed 5 gaps with line-level evidence
- `.planning/REQUIREMENTS.md` — GEOM-02, GEOM-03, LGP-01, SPEC-04, BRDF-01 requirement text
- `.planning/ROADMAP.md` — Phase 6 success criteria

### Secondary (MEDIUM confidence)

- `.planning/STATE.md` `## Decisions` section — confirms Phase 4 decisions: `face_optics` dict convention, cylinder/prism per-hit normal computation patterns, geometry-relative epsilon formula

### Tertiary (LOW confidence)

- None. All findings are directly confirmed from source code inspection.

---

## Metadata

**Confidence breakdown:**
- Gap identification (what is missing): HIGH — confirmed from source code line-by-line inspection
- Fix approach (how to wire): HIGH — existing single-thread path provides the template; changes are copy/adapt operations
- Schema for spectral n(λ): MEDIUM — no existing usage found; design choice required (open question 1)
- face_optics behavioral semantics: HIGH — `surface_type` field in OpticalProperties already defines the override contract

**Research date:** 2026-03-15
**Valid until:** 2026-04-15 (stable domain — pure Python logic, no external library changes)
