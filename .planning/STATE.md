---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-03-15T10:39:15.834Z"
progress:
  total_phases: 7
  completed_phases: 6
  total_plans: 19
  completed_plans: 17
---

---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in-progress
last_updated: "2026-03-15T22:20:00Z"
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 16
  completed_plans: 15
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-14)

**Core value:** Engineers can iterate on both direct-lit and edge-lit BLU designs with physically accurate, wavelength-aware simulation — fast enough for real workloads.
**Current focus:** Phase 5 — UI Revamp

## Current Position

Phase: 7 of 7 (UI + Spectral Display Fixes) — In Progress
Plan: 1 of 1 in current phase — COMPLETE (07-01 SUMMARY created, checkpoint awaiting human verify)
Status: 07-01 complete. Tab persistence fix, chromaticity scatter cloud, live spectral preview, spectral panel wiring.
Last activity: 2026-03-15 — Plan 07-01 complete (tracer.py, spectral_data_panel.py, main_window.py)

Progress: [██████████] 99%

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
| Phase 04 P05 | 20 min | 3 tasks | 6 files |
| Phase 03-performance-acceleration P02 | 20 | 2 tasks | 7 files |
| Phase 05-ui-rewamp P02 | 6 | 2 tasks | 6 files |
| Phase 05-ui-rewamp P03 | 5 | 2 tasks | 4 files |
| Phase 05-ui-rewamp P04 | 18 | 2 tasks | 3 files |
| Phase 07-ui-spectral-display-fixes P01 | 8 | 2 tasks | 3 files |

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
- [Phase 04-04]: FarFieldPanel polar display uses (I*sin(theta), I*cos(theta)) mirrored to negative half — matches goniophotometer convention
- [Phase 04-04]: BSDF delete guard checks all optical_properties for bsdf_profile_name references before allowing delete — prevents dangling references
- [Phase 04-04]: Far-field lobe cleared before each refresh via clear_farfield_lobe() — avoids mesh accumulation across simulation runs
- [Phase 04-04]: Cylinder and prism placed under Solid Bodies (not Surfaces) in object tree — volumetric refractive objects need face-children pattern
- [Phase 05-02]: QUndoStack/QUndoCommand imported from PySide6.QtGui (NOT QtWidgets — Qt6 moved them)
- [Phase 05-02]: Command constructor must NOT perform mutation — QUndoStack.push() calls redo() automatically
- [Phase 05-02]: mergeWith() uses hash((id(obj), attr)) for rapid property edit coalescing (slider drag → single undo step)
- [Phase 05-02]: undo_stack.clear() called in all 5 project-replacement paths (new/open/preset/variant/history)
- [Phase 05-02]: indexChanged signal connected to _mark_dirty() so undo/redo marks project modified
- [Phase 05-03]: CollapsibleSection uses QToolButton with setArrowType for expand/collapse indicator
- [Phase 05-03]: ObjectTree icon cache at class level (_ICONS dict); programmatic QPainter circles avoid image files
- [Phase 05-03]: duplicate_requested signal defined in ObjectTree but wired by MainWindow (avoids Plan 02 conflict)
- [Phase 04-05]: showed_farfield boolean flag controls tab focus: only focus Heatmap when no far-field results shown
- [Phase 04-05]: smooth=False on GLMeshItem for far-field lobe: smooth=True overrides per-face faceColors with vertex-normal interpolation
- [Phase 04-05]: Sphere detector accumulation in _trace_single_source uses inline numpy to avoid passing SphereDetectorResult between processes
- [Phase 04-05]: sph_grids dict returned from _trace_single_source; merged in _run_multiprocess; compute_farfield_candela called after merge
- [Phase 05-04]: Partial result emitted after each source completes (source-granularity) — matches natural progress callback rhythm; progress >= 0.05 guard prevents early empty snapshots
- [Phase 05-04]: grid.copy() for partial snapshots — fast shallow numpy copy; no ray_paths/sphere_detectors/solid_body_stats in partial to minimize cross-thread transfer
- [Phase 05-04]: CollapsibleSection wraps inner QWidget+QGridLayout (not addLayout directly) to preserve existing grid structure
- [Phase 05-04]: _threshold_color() returns CSS color string; applied via label.setStyleSheet() for green/yellow/red threshold feedback
- [Phase 04-05]: pyqtgraph 0.14.0 pg.mkPen() requires integer 0-255 color tuples, not float 0.0-1.0 — float values cause silent polar plot curve rendering failure
- [Phase 07-ui-spectral-display-fixes]: Separate _sim_scatter item from _chroma_scatter so SPD marker and simulation chromaticity cloud coexist independently
- [Phase 07-ui-spectral-display-fixes]: update_from_result uses first detector with grid_spectral (not aggregating all detectors) — consistent with HeatmapPanel default
- [Phase 07-ui-spectral-display-fixes]: isinstance(saved_tabs, str) coercion before list check in _restore_layout — Windows QSettings single-item list edge case

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

Last session: 2026-03-15
Stopped at: Completed 07-01-PLAN.md — Tab persistence, chromaticity scatter, live spectral preview (checkpoint awaiting visual verification)
Resume file: None
