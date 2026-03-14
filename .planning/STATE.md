---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in-progress
last_updated: "2026-03-14T09:21:21.844Z"
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 3
  completed_plans: 2
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-14)

**Core value:** Engineers can iterate on both direct-lit and edge-lit BLU designs with physically accurate, wavelength-aware simulation — fast enough for real workloads.
**Current focus:** Phase 1 — Refractive Physics and LGP

## Current Position

Phase: 1 of 4 (Refractive Physics and LGP)
Plan: 2 of 3 in current phase
Status: In progress
Last activity: 2026-03-14 — Plan 01-02 complete (SolidBox I/O + LGP builder + preset + KPI dashboard)

Progress: [██░░░░░░░░] 20%

## Performance Metrics

**Velocity:**
- Total plans completed: 2
- Average duration: 5.5 min
- Total execution time: 0.18 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| Phase 01 | 2 | 11 min | 5.5 min |

**Recent Trend:**
- Last 5 plans: 01-01 (8 min, 39 tests), 01-02 (3 min, 2 tasks, 4 files)
- Trend: accelerating

*Updated after each plan completion*

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

### Pending Todos

None yet.

### Blockers/Concerns

- ~~Phase 1: Fix _EPSILON to geometry-relative value before any LGP code (thin-slab TIR loss pitfall)~~ RESOLVED in 01-01
- ~~Phase 1: Use oriented normal `on` not `surf.normal` in Fresnel impl (normal orientation pitfall)~~ RESOLVED in 01-01
- Phase 2: Add single-thread guard before enabling spectral + multiprocessing together
- Phase 3: np.add.at scatter-add pattern throughout tracer is not Numba-compatible — must refactor before JIT

## Session Continuity

Last session: 2026-03-14
Stopped at: Completed 01-02-PLAN.md (SolidBox I/O + LGP builder + preset + KPI dashboard)
Resume file: None
