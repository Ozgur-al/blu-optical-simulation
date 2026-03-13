# Project Research Summary

**Project:** Blu Optical Simulation — Phase 2
**Domain:** Monte Carlo optical simulation — backlight unit (BLU), edge-lit/LGP, spectral, refractive optics
**Researched:** 2026-03-14
**Confidence:** MEDIUM (physics HIGH, integration MEDIUM, library versions MEDIUM)

## Executive Summary

Blu Optical Simulation Phase 2 extends an already-functional direct-lit BLU Monte Carlo tracer into a full optical simulation tool capable of modeling edge-lit LGP panels, spectral color simulation, and physically-accurate refractive optics. The existing layered architecture (core/sim/io/gui with a strict no-PySide6 constraint on the lower layers) is well-suited for this extension and should not be restructured — every Phase 2 feature is an additive extension to defined integration points. The critical path runs through three sequential prerequisites: (1) Snell's law + Fresnel + TIR, (2) solid body box primitive, and (3) LGP scene configuration. Nothing in Phase 2 is possible without these three, and they are independent of spectral or performance work.

The recommended approach is to build in dependency order rather than feature order. Refractive optics (Fresnel/TIR) is a zero-dependency foundation that unlocks LGP physics, solid-body glass, and spectral dispersion. Solid body geometry (decomposed into rectangles at trace time) preserves the existing intersection engine unchanged. Numba JIT acceleration is a pure performance layer that should be deferred until the physics is stable and verified, because the `np.add.at` scatter-add pattern that permeates the accumulator is not Numba-compatible and must be refactored first. PyVista/VTK for 3D rendering should be implemented as an optional overlay with fallback to existing pyqtgraph.opengl — VTK adds ~200 MB to the PyInstaller binary and must never be a hard dependency.

The top risks are: (1) epsilon offset failure for thin LGP geometry causing phantom ray loss, (2) Fresnel normal-side errors producing silently wrong angular distributions, (3) spectral accumulation loop being 40x slower than expected due to a `for b in range(n_bins)` Python loop that must be vectorized before enabling spectral by default, and (4) the multiprocessing path being entirely disconnected from the spectral engine (requires either a guard or a refactor before spectral + MP can coexist). All four are preventable with targeted unit tests written before the affected code is merged.

## Key Findings

### Recommended Stack

The Phase 1 stack (PySide6, pyqtgraph, NumPy, PyOpenGL, pytest) is unchanged. Phase 2 adds six libraries, all optional or conditional imports. The only HIGH-confidence new dependency is Numba (>=0.60) for JIT acceleration of intersection and accumulation inner loops — widely stable, no build toolchain, 10–50x expected speedup, PyInstaller-safe with `--collect-all numba`. The remaining additions are MEDIUM confidence on version numbers (knowledge cutoff August 2025; verify on PyPI before pinning).

Refractive optics (Snell/Fresnel/TIR), temperature-dependent materials, far-field detector, and spectral integration require no new libraries — all are pure NumPy implementations on top of existing primitives. The BRDF feature adds `scipy >=1.11` for 2D irregular-grid interpolation, which is PyInstaller-safe. CAD import adds `ezdxf >=1.3` (pure Python, safe) and `trimesh >=4.0` (pure Python, safe) for DXF and STL/OBJ formats respectively. STEP/IGES import via cadquery/OCC is explicitly deferred to Phase 3 due to the 500 MB OCC dependency and fragile PyInstaller packaging.

**Core technologies (new):**
- **numba >=0.60**: JIT-compile intersection and accumulation inner loops — only viable acceleration without a build toolchain or GPU dependency
- **pyvista >=0.43 + pyvistaqt >=0.11**: CAD-quality solid body 3D rendering — optional overlay; fallback to existing pyqtgraph.opengl if unavailable; adds ~200 MB to binary
- **ezdxf >=1.3**: DXF import for LED layouts and LGP dot patterns — pure Python, PyInstaller-safe
- **trimesh >=4.0**: STL/OBJ mesh import for LGP slab and prism geometry — pure Python, pairs with PyVista
- **scipy >=1.11**: 2D BRDF table interpolation — standard scientific Python, PyInstaller-safe

**Explicitly deferred:**
- cadquery/pythonOCC (STEP/IGES) — 500 MB, fragile packaging
- pyembree (Intel Embree BVH) — overkill until 500+ surface scenes are common
- Optuna (Bayesian optimization) — current Pareto sweep covers 98% of use cases

### Expected Features

The research examined LightTools, Zemax OpticStudio (Non-Sequential), TracePro, ASAP, Raysect, and RayFlare to establish what engineers expect from a BLU simulation tool claiming edge-lit and spectral capability.

**Must have (table stakes) — no LGP simulation without these:**
- LGP slab geometry (rectangular box with independent per-face optical properties) — every edge-lit LCD uses a slab
- TIR (Total Internal Reflection) at LGP faces — the core mechanism of edge-lit propagation; qualitatively wrong without it
- Fresnel transmission at coupling face — controls edge coupling efficiency (key design metric)
- Extraction dot/feature pattern on bottom face — primary LGP design variable; modeled as per-region scatter/transmittance map
- Snell's law refraction + critical angle — mathematical prerequisite for TIR
- Spectral detector output (flux per wavelength bin) — required for color uniformity analysis
- Per-ray wavelength assignment — existing groundwork in `sim/spectral.py` needs to be wired into the main bounce loop

**Should have (competitive differentiators):**
- GGX microfacet BRDF model — covers polished/satin surfaces with a single roughness parameter; more physically accurate than pure Lambertian/specular
- Far-field angular detector with IES export — validates against goniometric measurements; existing SphereDetector just needs solid-angle binning
- Wavelength-dependent refractive index (dispersion) — PMMA and glass have measurable chromatic effects in color uniformity analysis
- Python scripting API stabilization + example notebooks — genuine differentiator vs LightTools' brittle COM API
- Spectral + uniformity co-optimization in parameter sweep — no open-source tool does this simultaneously

**Defer to Phase 3:**
- Full BRDF tabulated import (measured goniophotometer data) — GGX covers 80% of cases; full BRDF is high complexity
- Triangle mesh import + BVH — high complexity; wedge LGP can be approximated with tilted planes
- Wedge LGP (tapered) — requires mesh import or trapezoidal solid
- Temperature-dependent material LUTs — foundation exists (`thermal_derate`); defer full per-surface LUT
- LGP dot pattern inverse design — gradient descent from target uniformity; Phase 3 research problem
- Polarization state tracking — Jones/Mueller matrices; niche within BLU, ~2x memory overhead
- GPU/CUDA — packaging complexity; Numba CPU covers the target 100x speedup goal

**Anti-features — do not build:**
- Full micro-optics simulation of LGP dots — impractical; use stochastic extraction probability map instead
- FDTD/wave optics — category confusion in a ray tracer
- CAD solid modeling / history tree — import from STL/OBJ, not build inside the app
- Bayesian/Optuna optimization — premature; Nelder-Mead via scipy is sufficient if needed

### Architecture Approach

The architecture strategy is strict additive extension: new modules slot into defined integration points without modifying the existing bounce loop, intersection logic, or accumulation code. The key patterns are: (1) solid bodies decompose into rectangles at trace time so the inner loop sees only existing Rectangle types; (2) per-ray state additions (refractive index, wavelength) are parallel numpy arrays of length N, not added to ray objects; (3) optional dependencies (Numba, VTK) are conditional imports with explicit fallback paths; (4) all new Project fields use `.get(key, default)` deserialization to maintain JSON backwards compatibility.

**Major new components:**
1. `sim/fresnel.py` — Snell's law, TIR critical angle, Fresnel R/T coefficients; the zero-dependency foundation for all refractive physics
2. `core/solid_body.py` + `sim/solid_intersect.py` — SolidBody dataclass with `decompose_faces()` method; ray-AABB and ray-cylinder intersection
3. `core/lgp_geometry.py` — LGPSlab, CouplingFace, ExtractionDot data model; the LGP scene configuration layer
4. `sim/tracer_kernels.py` — `@numba.jit` kernels for intersection and accumulation inner loops; conditional import with NumPy fallback
5. `sim/bvh.py` — BVH node + build + traverse; only beneficial at 50+ surfaces; build once before bounce loop
6. `gui/viewport_vtk.py` — pyvistaqt-backed 3D renderer exposing the same public API as existing `viewport_3d.py`; optional overlay
7. `gui/spectral_panel.py` — display spectral simulation results (per-wavelength heatmaps, CIE chromaticity)

**Recommended build sequence:**
```
Fresnel/TIR → Solid bodies → LGP scene → Spectral integration → BVH → Numba → VTK renderer
             (Spectral integration can proceed in parallel with Solid bodies)
```

### Critical Pitfalls

1. **Fresnel normal orientation bug** — the existing tracer already computes `on` (oriented normal, guaranteed to point away from incoming ray) in `_bounce_surfaces`. Any Fresnel implementation must use `on`, not `surf.normal`. Using the raw surface normal produces wrong reflectance values and incorrect TIR threshold. Prevention: write `fresnel_coefficients(cos_theta_i, n1, n2)` that takes the already-oriented angle; unit test at normal incidence (R ≈ 4% for n=1.5), at Brewster's angle, and at the critical angle (R = 1.0 exactly).

2. **TIR epsilon offset failure for thin LGP geometry** — `_EPSILON = 1e-6` is calibrated for mm-scale open cavity. For a 3 mm PMMA plate with grazing TIR bounces, the self-intersection offset may place the ray outside the medium, causing valid TIR reflections to be silently discarded as `t < _EPSILON`. The LGP then appears to have anomalously high loss. Prevention: make `_EPSILON` geometry-relative (`1e-9 × max_scene_dimension`) before starting any LGP work.

3. **Spectral accumulation Python loop** — `tracer.py:_accumulate` has a `for b in range(n_bins)` inner loop over spectral bins that runs once per detector hit per bounce. With 40 bins, this is 40 Python iterations per hit instead of one vectorized operation. A 40-bin spectral run is 40–80x slower than expected. Prevention: replace with a single vectorized `np.add.at` over the spectral dimension before enabling spectral by default. Profile `_accumulate` with `cProfile` on a 10k-ray spectral run to confirm.

4. **Spectral + multiprocessing path mismatch** — `tracer.py:_trace_single_source` (the module-level function used by multiprocessing) was written before spectral and does not sample wavelengths, does not initialize `grid_spectral`, and the merge in `_run_multiprocess` does not accumulate spectral grids. Enabling spectral + MP together silently produces photometric-only results with no error. Prevention: add an explicit guard in `run()` — if `has_spectral`, force single-thread mode until the MP path is updated.

5. **Numba incompatibility with `np.add.at` and `np.random.default_rng`** — both are used throughout the tracer and are not supported in Numba's `nopython` mode. Using `@jit` (not `@njit`) falls back to object mode silently with zero speedup. Prevention: refactor scatter-add to explicit loops (which Numba compiles efficiently) and replace `np.random.default_rng` with seed-passing into JIT functions before attempting to JIT any tracer code. Use `@njit(nopython=True)` to force explicit compilation errors.

## Implications for Roadmap

Based on the dependency graph and pitfall analysis, the natural phase structure has three main phases corresponding to the three dependency chains: (1) refractive physics + LGP, (2) spectral engine completion, and (3) performance + renderer + advanced geometry.

### Phase 1: Refractive Physics and LGP Foundation

**Rationale:** This is the zero-dependency entry point and the highest-value deliverable. Fresnel/TIR depends on nothing. Solid body geometry depends only on Fresnel. LGP depends on both. This phase unblocks the entire Phase 2 product category. Without it, the app cannot claim edge-lit simulation capability.

**Delivers:** First working edge-lit LGP simulation end-to-end — sources at LGP edge, TIR propagation inside PMMA slab, extraction dot scatter, top-surface detector output. Includes edge coupling efficiency KPI.

**Implements from FEATURES.md:** LGP slab geometry, TIR, Fresnel transmission, extraction dot pattern, edge coupling efficiency KPI, Snell's law + critical angle. Unlocks the "table stakes" checklist for BLU simulation.

**Uses from STACK.md:** No new libraries required. Pure NumPy implementation in `sim/fresnel.py` + new `core/solid_body.py` + `core/lgp_geometry.py`.

**Must avoid (PITFALLS.md):** Fix `_EPSILON` before any LGP code (Pitfall 2). Use `on` not `surf.normal` in Fresnel (Pitfall 1). Design `SolidBody` with inside-tracking before implementing solid bodies as independent rectangles (Pitfall 9).

**Research flag:** Needs phase-level research — specifically the `SolidBody` inside-tracking design (medium confidence; no published precedent in this codebase pattern) and the per-face optical property architecture.

### Phase 2: Spectral Engine Completion

**Rationale:** Spectral groundwork exists (`sim/spectral.py` is complete; `_run_single` has `has_spectral` guards; `DetectorResult.grid_spectral` exists). This phase is integration work, not new physics. It can run in parallel with Phase 1 development (no dependency on Fresnel/TIR). But the accumulation loop vectorization and MP guard must be done before spectral is exposed to users or performance benchmarks will be misleading.

**Delivers:** End-to-end spectral simulation — per-ray wavelength assignment, wavelength-dependent material reflectance/transmittance, spectral detector grids, CIE XYZ → sRGB display in heatmap panel, color uniformity KPIs (ΔCCx, ΔCCy).

**Implements from FEATURES.md:** Per-ray wavelength assignment (wire existing groundwork), spectral detector output, CIE XYZ/sRGB display, wavelength-dependent material properties, built-in SPD presets (partially done).

**Uses from STACK.md:** No new libraries for core spectral. When Phase 1 Fresnel is available, add wavelength-dependent `n(λ)` (dispersion) as a second pass.

**Must avoid (PITFALLS.md):** Vectorize `_accumulate` spectral loop before enabling (Pitfall 3). Add MP guard before enabling spectral in multiprocessing mode (Pitfall 7). Enforce `.get(key, default)` for all new `Material` spectral fields (Pitfall 12).

**Research flag:** Standard integration patterns — no research phase needed. Code paths are already mapped in `tracer.py`.

### Phase 3: Performance Acceleration

**Rationale:** Numba JIT is the last step, not the first, because the accumulator refactor required for Numba compatibility (replacing `np.add.at` with loops) must not break the existing correctness-validated physics. BVH is deferred until solid bodies from Phase 1 push surface counts high enough to justify it. The break-even for BVH in Python is ~200 surfaces; without LGP dot meshes, typical scenes stay at 10–20 surfaces.

**Delivers:** 10–50x speedup on intersection and accumulation inner loops via Numba JIT. Optional BVH for scenes with triangle mesh imports. LGP quality preset in `SimulationSettings` (100k+ rays).

**Implements from STACK.md:** `numba >=0.60`, `sim/tracer_kernels.py` with `@njit` kernels, `sim/bvh.py`.

**Must avoid (PITFALLS.md):** Refactor `np.add.at` before JIT (Pitfall 4). Use `@njit` not `@jit` to catch object mode fallback (Pitfall 4). Benchmark before/after to confirm BVH is not a regression for small scenes (Pitfall 5). Disable Numba cache during development, add to `.gitignore` (Pitfall 15).

**Research flag:** Standard patterns — Numba documentation is thorough. The main work is refactoring, not algorithm research.

### Phase 4: BRDF and Advanced Material Models

**Rationale:** GGX microfacet model is independent of all Phase 1–3 work and can be developed in parallel. Tabulated BRDF import (full goniophotometer data) is higher complexity and needs scipy for 2D interpolation. Temperature-dependent material LUTs build on existing `thermal_derate` foundation. Far-field detector (candela distribution + IES export) extends the existing SphereDetector.

**Delivers:** GGX roughness parameter for polished/satin PMMA surfaces; tabulated BRDF import from CSV; far-field angular detector with IES export; temperature-dependent surface properties.

**Uses from STACK.md:** `scipy >=1.11` for 2D BRDF interpolation.

**Must avoid (PITFALLS.md):** Clamp BRDF interpolation to prevent NaN/negative weights at grazing angles (Pitfall 10). Assert no NaN per bounce in debug mode. Apply temperature LUT per-bounce for accuracy, or document the single-lookup approximation clearly (Pitfall 13). Use equal solid-angle bins or display normalization for far-field detector (Pitfall 14).

**Research flag:** BRDF importance sampling needs phase-level research — the CDF inversion pattern from angular distributions can be adapted, but the 2D case (theta_in, theta_out) requires careful treatment.

### Phase 5: VTK Renderer and Mesh Import

**Rationale:** VTK/PyVista is a pure GUI enhancement with significant binary size impact (~200 MB). It requires solid body geometry from Phase 1 to have something worthwhile to render. Triangle mesh import (STL/OBJ via trimesh) is a prerequisite for wedge LGP and complex geometry, and requires BVH from Phase 3 to be performant. Deferred to last because it adds deployment complexity without affecting simulation physics.

**Delivers:** CAD-quality solid body rendering via PyVista (optional, fallback to existing pyqtgraph.opengl). STL/OBJ mesh import for LGP slabs and prism geometry. Wedge LGP (tapered) preset.

**Uses from STACK.md:** `pyvista >=0.43`, `pyvistaqt >=0.11`, `trimesh >=4.0`, `ezdxf >=1.3`.

**Must avoid (PITFALLS.md):** Never import pyvistaqt unconditionally — conditional import only, fallback to pyqtgraph.opengl (Pitfall, Anti-Pattern 5 from ARCHITECTURE.md). Use `BackgroundPlotter` not `pv.Plotter`; defer VTK widget init until after main window shows to avoid Qt event loop conflict (Pitfall 8).

**Research flag:** pyvistaqt PySide6 integration on Windows needs verification against current version before committing. Known event loop interaction risk.

### Phase Ordering Rationale

- Fresnel before solid bodies because glass solids need `refractive_index` behavior at each face
- Solid bodies before LGP because the LGP slab is a solid box with specific optical assignments
- Both before spectral integration because wavelength-dependent `n(λ)` requires Snell's law to be meaningful
- Spectral accumulator vectorization before Numba because Numba cannot JIT the current `np.add.at` pattern
- Solid bodies before BVH because BVH break-even requires 50+ surfaces, only reached once solid faces are in the scene
- VTK last because it is a visual layer with no physics coupling; deferred to avoid binary size cost before core value is delivered

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 1 (solid body architecture):** The `SolidBody` inside-tracking design (per-ray `inside_solid` boolean array + medium-tracking) is a non-trivial extension to the tracer's ray state. Research the exact integration points in `_bounce_surfaces` before coding begins.
- **Phase 4 (BRDF):** Full tabulated BRDF importance sampling in 2D is a domain-specific algorithm. Research the CDF inversion extension from 1D (angular distributions) to 2D before implementation.
- **Phase 5 (pyvistaqt on Windows):** PyVista + PySide6 6.6 integration on Windows 11 has known event loop issues that depend on the exact library versions. Verify before starting.

**Phases with standard patterns (skip research-phase):**
- **Phase 2 (spectral integration):** All code paths are mapped in existing codebase. This is wiring, not research.
- **Phase 3 (Numba JIT):** Numba documentation is comprehensive. The main work is refactoring `np.add.at`, which is clearly specified.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Numba is HIGH; library version numbers for pyvista/ezdxf/trimesh/scipy are MEDIUM (inferred from training data Aug 2025, not live PyPI verification) |
| Features | MEDIUM | LGP physics and table-stakes analysis is HIGH (textbook optics); tool feature comparisons (LightTools/TracePro) are MEDIUM (training knowledge, not verified against current product docs) |
| Architecture | HIGH | Based on direct code analysis of the existing codebase; integration points are specific file/line references |
| Pitfalls | HIGH for physics / MEDIUM for integration | Fresnel orientation bug and epsilon failure are first-principles verified; Numba and VTK integration pitfalls are training-knowledge MEDIUM |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Performance baseline before Numba commitment:** Measure how slow a 1M-ray LGP simulation with TIR is in pure NumPy before committing Numba as Phase 3. If < 30 seconds, Numba may not be worth the refactoring cost in Phase 2 timeframe.
- **BRDF vs GGX user need:** Verify whether target users actually have goniophotometer BRDF data files. If not, GGX with roughness parameter covers 80% of cases and full tabulated BRDF import can be Phase 3.
- **Renderer decision before Phase 5 planning:** Verify pyvistaqt 0.11.x + PySide6 6.6 on Windows 11 before committing. If integration is fragile, keep pyqtgraph.opengl and add solid body wireframe rendering there instead.
- **Spectral MP guard vs full fix:** Decide at Phase 2 start whether to add a single-thread guard (fast, safe) or properly extend `_trace_single_source` to support spectral (correct, more work). The guard is recommended for Phase 2; the full fix for Phase 3.
- **LGP wedge geometry timing:** Validate whether rectangular slab covers 90% of target use cases before committing to mesh import in Phase 5.

## Sources

### Primary (HIGH confidence)
- `G:/blu-optical-simulation/backlight_sim/sim/tracer.py` — RayTracer implementation; specific line references in pitfalls
- `G:/blu-optical-simulation/backlight_sim/sim/spectral.py` — complete spectral utilities confirmed implemented
- `G:/blu-optical-simulation/backlight_sim/core/materials.py` — Material + OpticalProperties dual model; `refractive_index` field confirmed present
- `G:/blu-optical-simulation/backlight_sim/core/geometry.py` — Rectangle u_axis/v_axis pattern
- `G:/blu-optical-simulation/backlight_sim/core/detectors.py` — SphereDetector, grid_spectral confirmed
- `G:/blu-optical-simulation/.planning/PROJECT.md` — Phase 2 requirements and constraints
- Pharr & Humphreys "Physically Based Rendering" — Fresnel equations, BVH construction
- Standard optics: Snell's law, TIR critical angle, Fresnel unpolarized R/T formulas

### Secondary (MEDIUM confidence)
- LightTools (Synopsys) user documentation — LGP simulation workflow, extraction modeling, BRDF import
- Zemax OpticStudio Non-Sequential reference — BSDF, detector types, bulk scatter
- TracePro (Lambda Research) — material properties, Monte Carlo engine description
- Raysect (open source Python) — spectral + physical material architecture
- Training knowledge (Aug 2025 cutoff) — library version numbers, ecosystem status

### Tertiary (LOW confidence)
- Numba 0.60 version number — expected mid-2025; verify on PyPI before pinning
- pyvistaqt 0.11 + PySide6 6.6 compatibility on Windows 11 — needs live verification
- ezdxf >= 1.3 / trimesh >= 4.0 — version numbers inferred; verify against current releases

---
*Research completed: 2026-03-14*
*Ready for roadmap: yes*
