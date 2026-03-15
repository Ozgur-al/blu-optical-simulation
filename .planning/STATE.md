---
gsd_state_version: 1.0
milestone: v2.0-distribution
milestone_name: "Distribution & Splash Screen"
status: in_progress
last_updated: "2026-03-15T22:08:00Z"
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 4
  completed_plans: 1
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-15)

**Core value:** Engineers can iterate on both direct-lit and edge-lit BLU designs with physically accurate, wavelength-aware simulation — fast enough for real workloads.
**Current focus:** Phase 01 — Distribution for admin-locked work computer compatibility, splash screen, branding.

## Current Position

Milestone: v2.0-distribution — In Progress
Phase: 01-distribution-for-admin-locked-work-computer-compatibility-splash-screen-etc — Plan 1 of 4 complete
Status: Plan 01-01 (Foundation Artifacts) complete. Plans 02-04 pending.
Last activity: 2026-03-15 — Plan 01-01 executed: __version__.py, config.py, icon.ico

Progress: [##--------] 25% (1/4 plans)

## Current Position Detail

Phase: 01-distribution-for-admin-locked-work-computer-compatibility-splash-screen-etc
Current Plan: 2 of 4
Stopped at: Completed 01-01-PLAN.md

## Accumulated Context

### Decisions

- v2.0.0 chosen as first distributable release version (v1.0 was internal milestone)
- User data dir uses %LOCALAPPDATA%/BluOpticalSim on Windows — corporate-safe, no admin rights needed
- config.py strictly no PySide6 — headless-safe for io/ and sim/ layer consumption
- Icon generated at runtime via QPainter + Pillow; script checked in so icon can be regenerated

### Roadmap Evolution

- v1.0 shipped with 7 phases (originally 4 planned + Phase 5 UI Revamp + Phases 6-7 gap closure)
- VTK renderer deferred to v2 (pyqtgraph.opengl sufficient)
- Spectral+MP guard forces single-thread (future work to lift)
- Phase 01 added: distribution for admin locked work computer compatibility, splash screen etc.

### Pending Todos

None.

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-03-15
Stopped at: Completed 01-01-PLAN.md (foundation artifacts)
Resume file: None
