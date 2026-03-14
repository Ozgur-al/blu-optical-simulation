---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in-progress
last_updated: "2026-03-14T19:58:00Z"
progress:
  total_phases: 5
  completed_phases: 3
  total_plans: 15
  completed_plans: 10
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-14)

**Core value:** Engineers can iterate on both direct-lit and edge-lit BLU designs with physically accurate, wavelength-aware simulation — fast enough for real workloads.
**Current focus:** Phase 4 — Advanced Materials and Geometry

## Current Position

Phase: 4 of 5 (Advanced Materials and Geometry) — IN PROGRESS
Plan: 3 of 4 in current phase — COMPLETE
Status: Phase 4 Plan 03 SUMMARY created. Cylinder/prism solid bodies complete: SolidCylinder, SolidPrism, analytic intersection, Fresnel/TIR dispatch, I/O round-trip, 3D viewport rendering.
Last activity: 2026-03-14 — Plan 04-03 SUMMARY created (solid_body.py, tracer.py intersection, project_io.py, viewport_3d.py mesh rendering)

Progress: [████████░░] 77%

## Performance Metrics

**Velocity:**
- Total plans completed: 5
- Average duration: 9.8 min
- Total execution time: 0.82 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| Phase 01 | 3 | 19 min | 6.3 min |
| Phase 02 | 2 | 36 min | 18 min |
| Phase 03 | 1 (so far) | 3.6 min | 3.6 min |

**Recent Trend:**
- Last 5 plans: 01-03 (8 min, 2 tasks, 5 files), 02-01 (12 min, 1 task TDD, 5 files), 02-02 (24 min, 3 tasks, 5 files), 03-01 (3.6 min, 2 tasks TDD, 6 files)
- Trend: stable

*Updated after each plan completion*
| Phase 01 P01 | 8 min | 39 tests | 3 files |
| Phase 01 P02 | 3 min | 2 tasks | 4 files |
| Phase 01 P03 | 8 min | 2 tasks | 5 files |
| Phase 02 P01 | 12 min | 1 task TDD | 5 files |
| Phase 02 P02 | 24 min | 3 tasks | 5 files |
| Phase 03 P01 | 3.6 min | 2 tasks TDD | 6 files |
| Phase 04 P01 | 5 min | 2 tasks TDD | 5 files |
| Phase 04 P02 | 5 | 2 tasks | 5 files |
| Phase 04 P03 | 5 min | 3 tasks | 6 files |
| Phase 03-performance-acceleration P02 | 20 | 2 tasks | 7 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: Fresnel/TIR before solid bodies (glass solids need refractive_index at each face)
- Roadmap: Spectral after Phase 1 (wavelength-dependent n(λ) requires Snell's law to be meaningful)
- Roadmap: Numba deferred to Phase 3 (np.add.at must be refactored before JIT can apply)
- Roadmap: VTK renderer deferred to v2 (removed from v1 scope; binary size cost not justified yet)
- [Phase 01]: Use on_into convention for Fresnel/Snell physics: oriented normal pointing INTO new medium for _refract_snell, flipped to on_back for reflection formula
- [Phase 01]: SolidBox faces identified by '::' separator in Rectangle name — no new type needed, preserves surface API
- [Phase 01]: Geometry-relative epsilon max(1e-6, min(dimensions)*1e-4) prevents TIR self-intersection in thin slabs
- [Phase 01]: bottom_reflector uses optical_properties_name override instead of separate Material — keeps pmma for refractive index and lgp_bottom_reflector OpticalProperties for surface behavior
- [Phase 01]: LGP KPI rows hidden (not removed) when no solid bodies present — avoids layout reflow in heatmap panel
- [Phase 01]: GUI: 3-level tree item detection uses grandparent.text(0) check for Solid Bodies face nodes — avoids metadata storage
- [Phase 01]: GUI: GeometryBuilderDialog converted to QTabWidget (Direct-Lit/LGP) for clean workflow separation
- [Phase 02-01]: Spectral grid allocation triggered by has_spectral (any source spd != 'white'), not by presence of spectral_material_data
- [Phase 02-01]: blackbody_spd exponent clamped to [0, 700] to prevent float overflow at short wavelengths
- [Phase 02-01]: get_spd_from_project follows same check-custom-first pattern as angular_distributions lookup
- [Phase 02-01]: MP+spectral guard uses stacklevel=2 so warning points to user call site
- [Phase 02-spectral-engine]: Robertson 1968 31-entry isotherm table inlined for CCT estimation; clamped to [1000, 25000] K
- [Phase 02-spectral-engine]: Color Uniformity KPI section hidden by default; shown when grid_spectral is not None
- [Phase 02-spectral-engine]: compute_color_kpis uses luminance-weighted mean CCT (by Y channel)
- [Phase 02-02]: Spectral locus filters CIE sum < 1e-3 of peak — removes 780nm region collapse to (0,0) artifact
- [Phase 02-02]: Fixed CIE 1931 view range [0,0.85]x[0,0.92] enforced both at init and after scatter update — pyqtgraph auto-range must not override diagram
- [Phase 02-02]: Spectral Color mode uses _displayed flag + orange status QLabel — user sees explicit feedback when grid_spectral is None instead of silent intensity fallback
- [Phase 03-01]: No-op njit fallback handles both @njit and @njit(cache=True) calling conventions via len(args)==1 check
- [Phase 03-01]: accumulate_*_jit uses @njit(cache=True) without fastmath to preserve exact scatter-add semantics
- [Phase 03-01]: Wrapper functions (intersect_plane/intersect_sphere) handle tuple→scalar conversion so JIT kernels receive primitive types only
- [Phase 03-01]: warmup_jit_kernels() returns bool; JIT label uses addWidget (left-aligned) not addPermanentWidget
- [Phase 04]: Far-field accumulation negates ray direction (outgoing from luminaire = -ray_dir)
- [Phase 04]: Beam/field angle uses 2*half_angle convention for standard cone angle measurement
- [Phase 04]: compute_farfield_candela floors sin(theta) at 1e-6 to prevent division-by-zero at poles
- [Phase 03-02]: BVH activation threshold = 50 total plane surfaces; traverse_bvh_batch is JIT but build_bvh_flat is pure NumPy
- [Phase 03-02]: Adaptive sampling disabled in MP mode with warning; convergence metric = 1.96*std/sqrt(n)/mean * 100
- [Phase 03-02]: Cylinder/prism intersection loops belong inside bounce loop body (20-space indent); bug fixed from prior session
- [Phase 04-01]: BSDF CSV requires both refl_intensity and trans_intensity columns — partial BSDF rejected with ValueError
- [Phase 04-01]: Energy conservation check uses raw row sums with 1e-3 tolerance (not solid-angle integrals) — practical import-time check
- [Phase 04-01]: precompute_bsdf_cdfs called once at tracer init, keyed by profile name — avoids per-bounce CDF construction
- [Phase 04-01]: BSDF dispatch bypasses ALL scalar optical behavior (reflectance, transmittance, is_diffuse, haze) when bsdf_profile_name is set
- [Phase 04-01]: Stochastic reflect/transmit split: p_refl = refl_total / (refl_total + trans_total) per theta_in bin
- [Phase 04-03]: CylinderSide per-hit radial normal computed at intersection point as (hit - center - proj*axis)/radius — required for correct Fresnel on curved surface
- [Phase 04-03]: PrismCap polygon containment uses precomputed 2D edge normals in local u/v coords — avoids 3D cross-product per edge per ray in hot path
- [Phase 04-03]: Prism side faces are standard Rectangle objects — reuses _intersect_plane_accel without a new intersection function
- [Phase 04-03]: Geometry-relative epsilon max(1e-6, min(radius, length/2)*1e-4) for cylinder/prism prevents TIR self-intersection on thin shapes

### Roadmap Evolution

- Phase 5 added: ui rewamp

### Pending Todos

None yet.

### Blockers/Concerns

- ~~Phase 1: Fix _EPSILON to geometry-relative value before any LGP code (thin-slab TIR loss pitfall)~~ RESOLVED in 01-01
- ~~Phase 1: Use oriented normal `on` not `surf.normal` in Fresnel impl (normal orientation pitfall)~~ RESOLVED in 01-01
- ~~Phase 2: Add single-thread guard before enabling spectral + multiprocessing together~~ RESOLVED in 02-01
- ~~Phase 3: np.add.at scatter-add pattern throughout tracer is not Numba-compatible — must refactor before JIT~~ RESOLVED in 03-01

## Session Continuity

Last session: 2026-03-14
Stopped at: Completed 04-03-PLAN.md SUMMARY (cylinder/prism solid bodies: analytic intersection, Fresnel/TIR dispatch, I/O round-trip, viewport mesh rendering)
Resume file: None
