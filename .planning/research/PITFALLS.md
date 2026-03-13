# Domain Pitfalls

**Domain:** Optical simulation Phase 2 — edge-lit/LGP, spectral engine, refractive optics, Numba, BVH, VTK renderer
**Researched:** 2026-03-14
**Confidence:** HIGH for physics correctness pitfalls (first-principles verified against codebase); MEDIUM for integration pitfalls (training knowledge, not yet verified against live dependency versions)

---

## Critical Pitfalls

Mistakes that cause rewrites or physically incorrect simulation results.

---

### Pitfall 1: Wrong Side of the Fresnel Equation at Each Interface

**What goes wrong:** When implementing Snell's law + Fresnel, the incoming ray direction and the surface normal must be on the same side (both pointing into the medium being exited, or both toward the medium being entered). The existing tracer already has this subtlety — it computes `flip = dot > 0` to orient the normal away from the incoming ray (`on`). If the Fresnel implementation re-derives this orientation independently and gets it backwards, reflection and transmission coefficients will be computed for the wrong polarization at the wrong angle. The bug is silent: the simulation runs, produces energy-conserving results, but the angular distribution of the reflected light is wrong.

**Why it happens:** Fresnel equations take the angle of incidence as the angle between the incoming ray and the surface normal at the point of entry. The normal direction convention in `_bounce_surfaces` already flips the normal based on ray direction. A new Fresnel block that uses `surf.normal` directly (not `on`) will compute `cos_theta_i` incorrectly for rays hitting the back side.

**Specific code hazard:** In `tracer.py:_bounce_surfaces` (line 354), `on` is the oriented normal pointing away from the incoming ray. Any Fresnel implementation must use `on`, not `surf.normal`. The dot product used for Fresnel is `-dot(incoming_dir, on)`, which must be positive (between 0 and 1) after orientation is applied.

**Consequences:** Incorrect Fresnel reflectance values, wrong TIR threshold behavior, energy imbalance over many bounces.

**Prevention:** Write a single helper `fresnel_coefficients(cos_theta_i, n1, n2) -> (Rs, Rp, R, T)` that takes the already-oriented angle (guaranteed positive) and returns energy fractions. Never pass raw dot products. Add a unit test: at normal incidence with n1=1.0, n2=1.5, R should be ~0.04 (4% for glass-air). At the critical angle (for n1=1.5, n2=1.0 it is ~41.8°), R must reach 1.0 exactly.

**Detection:** Unit test `fresnel_coefficients` at: normal incidence, Brewster's angle, critical angle, supercritical angle. Energy conservation test: reflected + transmitted fractions must sum to 1.0 for all inputs.

**Phase:** Refractive optics phase.

---

### Pitfall 2: TIR Rays That "Leak" Through Interfaces (Epsilon Offset Failure)

**What goes wrong:** After TIR reflection, the ray origin is offset by `1e-6 * on` (current code uses `_EPSILON = 1e-6`). For a flat LGP plate (e.g., 3 mm thick acrylic, n=1.49), a ray bouncing at a shallow angle travels a very short distance to the next face. If the offset places the origin fractionally outside the medium boundary instead of inside it, the ray will immediately re-intersect the same surface with t close to `_EPSILON` and be blocked by the `t > _EPSILON` guard — silently dying instead of propagating. The LGP will appear to have anomalously high loss.

**Why it happens:** The `_EPSILON = 1e-6` value was calibrated for mm-scale geometry with no refractive interfaces. For thin-film surfaces (0.1–2 mm thick) with grazing-angle TIR, the distance to next hit can be on the order of microns, comparable to the offset magnitude.

**Specific code hazard:** `_intersect_rays_plane` at line 588: `valid = nonzero & (t > _EPSILON)`. If `_EPSILON` is too large relative to the LGP geometry, valid TIR reflections are discarded.

**Consequences:** LGP propagation loss is wildly over-estimated. Extraction efficiency appears much lower than reality. The bug worsens as scene units change (if a user sets `distance_unit = "m"` instead of `mm`, the physical offset is 1000x larger than needed).

**Prevention:** Make `_EPSILON` proportional to scene scale. A robust pattern is to use `_EPSILON = 1e-9 * max_scene_dimension` or to normalize it based on `project.settings.distance_unit`. Alternatively, use a relative epsilon: `t > max(1e-6, 1e-9 * t_far)`. Add a regression test: flat-plate LGP 100×10×3 mm, edge source, verify >80% of rays propagate more than 5 bounces inside the plate before extraction.

**Detection:** Comparing extracted flux vs injected flux for a simple rectangular LGP: should be ~5–20% extraction per dot, not 60–80%.

**Phase:** Edge-lit/LGP phase — must be fixed before LGP work begins.

---

### Pitfall 3: Spectral Simulation Memory Explosion from Per-Ray Wavelength Storage

**What goes wrong:** The current tracer allocates `grid_spectral = np.zeros((ny, nx, n_spec_bins), dtype=float)` per detector. With the default 40 bins, a 100×100 detector grid uses 40k floats per detector — manageable. But `_accumulate` (line 686) iterates a Python `for b in range(n_bins)` loop over every spectral bin for every bounce. With 10k rays × 40 bins × 50 bounces = 20M iterations through Python. The loop was acceptable for per-hit accumulation; it becomes the dominant performance cost for the spectral path.

**Why it happens:** The spectral accumulation was added as a simple extension to the existing accumulation function. The inner `for b in range(n_bins)` loop at line 686 is the exact anti-pattern that Numba or vectorized numpy should eliminate — but it runs in pure Python right now, and there is no Numba integration yet.

**Specific code hazard:** `tracer.py:_accumulate` lines 682–689. For a 40-bin spectral run, this loop executes once per detector hit, per bounce. The `np.add.at` inside the loop is individually called 40 times per hit batch instead of being vectorized over the spectral dimension.

**Consequences:** A 40-bin spectral simulation runs 40–80x slower than expected (not just 40x slower than photometric, because the loop overhead compounds). Interactive preview at 1k rays may feel acceptable, but high-quality 100k-ray runs become impractical.

**Prevention:** Replace the inner loop with a single vectorized `np.add.at` over the spectral grid. The pattern is:
```python
# Vectorized: (M hits, n_bins) outer product added to (ny, nx, n_bins) grid
for i in range(len(hit_idx)):
    result.grid_spectral[iy[i], ix[i], i_bin[i]] += hit_weights[i]
```
Or better, use `np.add.at` with advanced indexing across the bin dimension. When Numba is integrated, the inner loop compiles away; until then, use the vectorized form.

**Detection:** Profile `_accumulate` with `cProfile` on a 10k-ray spectral run. Time for `_accumulate` should scale with `n_rays`, not `n_rays * n_bins`.

**Phase:** Spectral integration phase — fix the accumulation loop before enabling spectral by default.

---

### Pitfall 4: Numba JIT Fails Silently on Unsupported Numpy Operations

**What goes wrong:** Numba's `@njit` does not support all NumPy operations. Common failures relevant to this codebase:
- `np.add.at` (scatter add with repeated indices) — not supported in nopython mode; must use `for` loop or `np.bincount`
- `np.random.default_rng()` (Generator protocol) — Numba has its own `numba.typed` random, not compatible with `np.random.Generator`
- Dataclass instances — cannot be passed directly into `@njit` functions; must unpack to primitive arrays first
- `np.interp` — supported in recent Numba versions but behavior differs at boundaries

**Why it happens:** Numba documentation covers what IS supported but it's easy to miss what isn't. The codebase uses `np.add.at` extensively (every `_accumulate` call) and `np.random.default_rng` as the global RNG. These are structural, not incidental.

**Specific code hazard:**
- `tracer.py` lines 672, 679, 688: `np.add.at(result.grid, ...)` — not Numba-compatible
- `tracer.py` line 35: `self.rng = np.random.default_rng(...)` — must be replaced with Numba's RNG or passed as seed
- All `@dataclass` inputs to any JITted inner loop must be unpacked

**Consequences:** Numba JIT falls back to "object mode" silently if `@jit` is used (not `@njit`). Object mode gives no speedup. With `@njit`, it raises a compile error the first time the function is called — not at import time. This means the failure is discovered during a simulation run, not during startup.

**Prevention:** Use `@njit(nopython=True)` to force explicit errors. Refactor `np.add.at` to use explicit loops (which Numba compiles efficiently) or restructure accumulation to avoid scatter-adds. Wrap RNG calls to pass seeds as integers into JIT functions and use `numba.cuda.random` or numba's xoroshiro128+ internally. Write a standalone test that JIT-compiles the inner loop in isolation before integrating into the tracer.

**Detection:** Write a `test_numba_kernels.py` that calls each JITted function with synthetic data. If any function is in object mode, assert False. Use `numba.core.registry` inspection or `numba.typed_list` checks.

**Phase:** Numba acceleration phase — do not attempt to JIT existing functions directly; refactor first.

---

### Pitfall 5: BVH Construction Overhead Exceeds Benefit for Small Scenes

**What goes wrong:** BVH (Bounding Volume Hierarchy) spatial acceleration requires construction time O(N log N) and memory O(N) before any rays are traced. For the typical BLU scene (4–12 surfaces + 1 detector), the current O(N_surfaces × N_rays) linear scan is faster than BVH traversal because N_surfaces is tiny. Implementing BVH will slow down all existing scenes while only helping scenes with hundreds of surfaces.

**Why it happens:** BVH is standard advice for "fast ray tracing" but the break-even point is approximately 50–100 surfaces for a compiled language and 200+ surfaces for Python-level traversal due to per-node Python overhead. The typical BLU box scene has 5–6 surfaces.

**Specific code hazard:** The inner bounce loop in `tracer.py` (lines 218–239) iterates `for si, surf in enumerate(surfaces)`. With 6 surfaces, this is 6 numpy calls per bounce, each operating on the full ray batch. A BVH traversal in Python would require dozens of Python function calls per ray per node.

**Consequences:** Introducing BVH without careful benchmarking causes a performance regression for all existing scenes — the common case. The feature looks correct but makes the tool slower for 95% of users.

**Prevention:** Implement BVH only after profiling shows that scene complexity (N_surfaces > 50) is actually a bottleneck. Use a simple flat AABB pre-test per surface as a cheap culling step — this captures 80% of the benefit with no structural change. Measure: for current BLU scenes, does any surface intersection test account for more than 10% of trace time? If not, skip BVH.

**Detection:** Benchmark 6-surface vs 200-surface scene before and after BVH. BVH should show >2x speedup only for the 200-surface case, and should not regress the 6-surface case.

**Phase:** Performance phase — defer until solid body geometry exists (which increases surface count meaningfully).

---

## Moderate Pitfalls

---

### Pitfall 6: LGP Dot Pattern Extraction Physics Incorrect

**What goes wrong:** LGP dot patterns extract light via frustrated TIR — scattering elements on the bottom surface break TIR and redirect light upward. A naive implementation treats dots as diffuser patches (random scattering), ignoring that the angular distribution of extracted light depends on dot geometry. A simple Lambertian scatter from dots will produce a cosine-distributed output from the top surface instead of the nearly-collimated forward peak expected from a real LGP.

**Why it happens:** The existing material model (reflector/absorber/diffuser) maps cleanly to dot patches as "diffusers" with partial transmittance. But real dot extraction has an angular bias toward normal incidence on the top surface that a simple Lambertian model does not capture.

**Prevention:** For initial implementation, use Lambertian scatter at dots and document the approximation clearly in the UI. Add a `dot_extraction_angle_deg` parameter to the LGP material to allow tuning. Full BRDF integration (Phase 2 item) can replace this later. Do not claim physical accuracy for LGP angular output before BRDF is integrated.

**Detection:** Compare simulated top-surface angular distribution against reference data for a known LGP specification. Peak should be within ±10° of normal.

**Phase:** Edge-lit/LGP phase.

---

### Pitfall 7: Spectral Wavelength Assignment Breaks Multiprocessing Path

**What goes wrong:** The current multiprocessing path (`_trace_single_source` at line 386) is a standalone module-level function that was written before spectral support was added. It does not handle `source.spd`, `has_spectral`, or spectral grid initialization. When spectral mode is enabled and multiprocessing is also enabled, the MP path silently falls back to photometric behavior — no error, no warning, just missing spectral data in results.

**Why it happens:** The MP path duplicates the single-thread logic (intentionally, for pickling). It was not updated when spectral was added to `_run_single`. Two code paths = two places to maintain.

**Specific code hazard:** `tracer.py:_trace_single_source` lines 403–409: initializes `det_grids` with only `grid`, `hits`, `flux` — no `grid_spectral`. Lines 418–432 emit rays without sampling wavelengths. The merge in `_run_multiprocess` (lines 83–85) would silently ignore spectral data even if it existed.

**Prevention:** Either: (a) keep a single authoritative inner-loop function that works for both modes and serialize only the required arrays; or (b) add an explicit guard in `run()` — if `has_spectral`, force single-thread mode with a log message. Option (b) is faster to ship and safer.

**Detection:** Test: enable spectral SPD on source, enable multiprocessing, run simulation. Assert `result.detectors[name].grid_spectral is not None` in the test.

**Phase:** Spectral integration phase.

---

### Pitfall 8: VTK/pyvistaqt Rendering Loop Steals the Qt Event Loop

**What goes wrong:** pyvistaqt embeds a VTK `QVTKRenderWindowInteractor` inside a Qt widget. By default, VTK manages its own render timer and interaction callbacks. If `show()` is called on the pyvistaqt plotter in a way that starts VTK's own event loop (e.g., `plotter.show(interactive=True)`), it blocks the Qt event loop and the rest of the PySide6 UI freezes.

**Why it happens:** pyvistaqt is designed for Jupyter or standalone usage. The `BackgroundPlotter` class is specifically designed to embed in existing Qt apps, but it requires careful initialization order: the Qt application must exist before pyvistaqt is imported, and the render window must be created after the parent widget is visible.

**Prevention:** Use `pyvistaqt.BackgroundPlotter` (not `pv.Plotter`). Pass `parent=` the parent widget explicitly. Never call `plotter.show()` without `interactive=False` when embedded. Defer VTK widget initialization to after the main window is shown (`QTimer.singleShot(0, init_vtk)`). Test: verify Qt UI responds to mouse events while the VTK viewport is visible.

**Detection:** After adding VTK, verify that opening File menu, running a simulation, and adjusting properties all work while the 3D viewport is displayed. If any action hangs, VTK has captured the event loop.

**Phase:** VTK renderer phase.

---

### Pitfall 9: Solid Body Ray Intersection Double-Counting Internal Faces

**What goes wrong:** A solid box (6 faces) represented as 6 independent `Rectangle` surfaces has no concept of "inside" vs "outside". When a ray enters the box through one face, the tracer will immediately see the opposite face as a potential hit (t > 0 from the new origin). With the current `_EPSILON` offset, the ray starts just inside the first face. The second face is a legitimate hit. But if any face shares an edge with an adjacent face, there is a seam where a ray can be simultaneously "just past" face A and "just before" face B, leading to missed geometry or double-hits at corners.

**Why it happens:** The current codebase was designed for open-cavity geometry (walls, floor) where no ray is inside a closed volume. Solid bodies close the volume, changing the topology assumptions.

**Prevention:** Implement solids as a `SolidBody` abstraction that owns its 6 faces and tracks a "current medium" state per ray — a boolean `inside_solid[ray_idx]` array. When a ray transitions into the solid, set `inside_solid = True` and use the solid's `refractive_index` for subsequent Fresnel computations. This requires extending `RayTracer` state, not just adding more surfaces. Do not implement solid bodies as 6 independent `Rectangle` entries in `project.surfaces`.

**Detection:** Simple test: unit cube solid, ray entering at z=0 face pointing toward z=1 face. Should produce exactly 2 intersections (entry + exit) with correct refraction angles at each face.

**Phase:** Solid body geometry phase — architecture decision before any coding.

---

### Pitfall 10: BRDF Data Interpolation at Grazing Angles Introduces NaN or Negative Weights

**What goes wrong:** Measured BRDF data (e.g., from `.csv` measurement files) is typically sampled in cos-weighted or hemispherical coordinates. At grazing angles (theta_i → 90°), BRDF values can approach infinity (retroreflective peaks, specular lobes). When a ray hits the surface at 87° and the BRDF lookup requires interpolation between 85° and 90° sample points, poorly-conditioned interpolation can produce negative values or NaN, which propagate into ray weights. Negative weights produce nonsensical heatmaps; NaN weights poison the entire detector grid.

**Why it happens:** BRDF tables have finite angular resolution. Extrapolation beyond the table boundary or linear interpolation near a specular peak are both error-prone.

**Prevention:** Clamp BRDF lookup results to `[0, max_measured_value]` before applying to weights. Use reciprocal sampling (sample outgoing direction first from the BRDF lobe, then compute weight) rather than evaluate-then-weight. Mark any ray whose weight becomes NaN or negative as dead immediately (assert in debug mode, clamp to 0 in release mode).

**Detection:** Add `assert not np.any(np.isnan(weights))` and `assert not np.any(weights < 0)` at the start of each bounce iteration in the tracer (can be debug-only).

**Phase:** BRDF phase.

---

### Pitfall 11: CAD/DXF Import Produces Non-Planar or Overlapping Faces

**What goes wrong:** DXF files from real CAD tools contain: faces with normals pointing inward (wrong winding), coincident faces from different layers, non-planar quadrilaterals (vertices not coplanar), and faces scaled to model units (meters or inches, not mm). Any of these causes silent simulation errors — rays miss surfaces they should hit, or accumulate on the wrong side.

**Why it happens:** DXF is a lossy exchange format. AutoCAD and SolidWorks both have known issues with face winding consistency in exported DXF. Non-planar quads are common in mesh exports.

**Prevention:** After import, run a validation pass: (a) check vertex coplanarity for all quads (max deviation < 1e-4 scene units), (b) check that all face normals point outward (for closed bodies, volume-centroid test), (c) warn on coincident faces within 1e-3 units, (d) detect and prompt for unit scale (meter vs mm heuristic: if all coordinates < 1.0 and bounding box < 0.01, likely in meters). Expose a "repair" dialog that shows problem faces before adding to the scene.

**Detection:** Test with a known-good DXF cube (exported from each supported CAD package). Verify 6 faces with correct outward normals. Verify import fails gracefully on malformed DXF (missing ENTITIES section, empty file, wrong version).

**Phase:** CAD/DXF import phase.

---

## Minor Pitfalls

---

### Pitfall 12: JSON Backwards Compatibility Breaking on New Material Fields

**What goes wrong:** Adding `refractive_index` to `Material` (already done in current code at line 61) or adding `dot_density` to an LGP material subtype will break `load_project` for any `.json` file saved before the field existed — unless the `load_project` function uses `.get(key, default)` for every new field.

**Why it happens:** `project_io.py:load_project` deserializes directly from JSON dict. Any new field that uses direct dict indexing (`d["new_field"]`) instead of `d.get("new_field", default)` raises `KeyError` on old files.

**Prevention:** Enforce the `.get(key, default)` pattern for all deserialization. Add a migration test: save a project, manually remove one new field from the JSON, reload it. Must not raise.

**Phase:** Every phase that adds new data model fields.

---

### Pitfall 13: Temperature-Dependent Properties Not Applied Per-Bounce

**What goes wrong:** Temperature-dependent material properties (e.g., LED flux derating as a function of junction temperature) were partially implemented via `thermal_derate` on `PointSource`. If material reflectance is also made temperature-dependent (phosphor coating reflectance drops at high temperature), but the temperature lookup is done once before the bounce loop, simulation results won't capture steady-state conditions where temperature affects intermediate reflections — not just source output.

**Prevention:** If temperature-dependent surface properties are implemented, apply the lookup per-surface per-bounce, not once at the start. For a first-order approximation, a single pre-computed reflectance at operating temperature is acceptable and should be documented as such.

**Phase:** Temperature-dependent materials phase.

---

### Pitfall 14: Far-Field Detector Solid Angle Binning Produces Non-Uniform Sensitivity

**What goes wrong:** A far-field detector that bins by (theta, phi) in equal angular increments produces bins with very different solid angles — bins near the pole (theta → 0) subtend much less solid angle than bins near the equator (theta → 90°). If the display normalizes by bin count instead of bin solid angle, the polar region appears brighter than it physically is.

**Why it happens:** The existing sphere detector (`_accumulate_sphere`) bins as `i_theta = (theta / pi * n_theta)` — equal angular spacing, not equal solid-angle spacing. This is already present in the current code and will be more visible with a far-field detector that is specifically for angular output analysis.

**Prevention:** Either: (a) bin by equal solid angle (sinusoidal latitude correction: `i_theta = (1 - cos(theta)) / 2 * n_theta`), or (b) normalize the display by bin solid angle (multiply displayed value by `1 / sin(theta)` for equal-angle bins). Document which convention is used in the UI tooltip.

**Phase:** Far-field detector phase.

---

### Pitfall 15: Numba Compilation Cache Mismatch After Code Changes

**What goes wrong:** Numba caches compiled functions in `__pycache__`. If a JIT-compiled function is modified but the cache is not invalidated, the old compiled version continues to execute silently. This is particularly dangerous during development when the function signature changes (e.g., adding a `refractive_index` parameter to a JIT-compiled intersection function).

**Prevention:** During development, use `@njit(cache=False)` and only enable caching for release. Add `NUMBA_CACHE_DIR` to `.gitignore`. In CI, set `NUMBA_DISABLE_JIT=1` to catch fallback to Python mode.

**Phase:** Numba acceleration phase.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Edge-lit / LGP | TIR epsilon offset failure for thin plates | Adjust `_EPSILON` to be geometry-relative before LGP work |
| Edge-lit / LGP | Dot pattern angular output physically wrong | Document Lambertian approximation; defer to BRDF phase |
| Spectral integration | `_accumulate` inner loop = N×slower | Replace `for b in range(n_bins)` with vectorized op first |
| Spectral integration | MP path not updated for spectral | Force single-thread when spectral mode active, or update MP path |
| Refractive optics / TIR | Fresnel uses wrong normal side | Use oriented `on` (not `surf.normal`); unit test at critical angle |
| Refractive optics / TIR | Solid body inside-tracking missing | Design `SolidBody` abstraction before implementing |
| BRDF | Grazing angle interpolation NaN | Clamp weights; assert no NaN/negative per bounce |
| VTK renderer | Event loop conflict with Qt | Use `BackgroundPlotter`; verify UI remains interactive |
| Numba acceleration | `np.add.at` not supported | Refactor scatter-add before JIT; use `@njit` not `@jit` |
| Numba acceleration | Compile cache stale during dev | `cache=False` during development |
| BVH | Regression for small scenes | Benchmark before/after; add AABB pre-test first |
| CAD/DXF import | Incorrect face normals / unit scale | Validation pass + repair dialog before adding to scene |
| Far-field detector | Non-uniform solid angle binning | Use solid-angle-equal bins or normalize display by `sin(theta)` |
| Temperature materials | Applied once vs per-bounce | Clarify and document the approximation |
| All new model fields | JSON backwards compat breaks | Enforce `.get(key, default)` in `load_project`; add migration test |

---

## Sources

All findings derived from:
- Direct code analysis of `backlight_sim/sim/tracer.py`, `sampling.py`, `spectral.py`, `core/materials.py`, `core/geometry.py`, `core/project_model.py` (HIGH confidence — first-principles)
- Domain knowledge of Monte Carlo optical simulation, Fresnel/Snell physics, Numba limitations, and VTK/Qt embedding patterns (MEDIUM confidence for integration pitfalls — training knowledge, not verified against live dependency versions)
- `.planning/PROJECT.md` Phase 2 requirements and constraint list (HIGH confidence)
