# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-14)

**Core value:** Engineers can iterate on both direct-lit and edge-lit BLU designs with physically accurate, wavelength-aware simulation — fast enough for real workloads.
**Current focus:** Phase 1 — Refractive Physics and LGP

## Current Position

Phase: 1 of 4 (Refractive Physics and LGP)
Plan: 0 of 3 in current phase
Status: Ready to plan
Last activity: 2026-03-14 — Roadmap created

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: — min
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: none yet
- Trend: —

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: Fresnel/TIR before solid bodies (glass solids need refractive_index at each face)
- Roadmap: Spectral after Phase 1 (wavelength-dependent n(λ) requires Snell's law to be meaningful)
- Roadmap: Numba deferred to Phase 3 (np.add.at must be refactored before JIT can apply)
- Roadmap: VTK renderer deferred to v2 (removed from v1 scope; binary size cost not justified yet)

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 1: Fix _EPSILON to geometry-relative value before any LGP code (thin-slab TIR loss pitfall)
- Phase 1: Use oriented normal `on` not `surf.normal` in Fresnel impl (normal orientation pitfall)
- Phase 2: Add single-thread guard before enabling spectral + multiprocessing together
- Phase 3: np.add.at scatter-add pattern throughout tracer is not Numba-compatible — must refactor before JIT

## Session Continuity

Last session: 2026-03-14
Stopped at: Roadmap written, STATE.md initialized, REQUIREMENTS.md traceability to be updated
Resume file: None
