---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-03-15T22:34:57.384Z"
progress:
  total_phases: 1
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
---

---
gsd_state_version: 1.0
milestone: v2.0-distribution
milestone_name: "Distribution & Splash Screen"
status: in_progress
last_updated: "2026-03-15T22:12:35Z"
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 4
  completed_plans: 3
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-15)

**Core value:** Engineers can iterate on both direct-lit and edge-lit BLU designs with physically accurate, wavelength-aware simulation — fast enough for real workloads.
**Current focus:** Phase 01 — Distribution for admin-locked work computer compatibility, splash screen, branding.

## Current Position

Milestone: v2.0-distribution — In Progress
Phase: 01-distribution-for-admin-locked-work-computer-compatibility-splash-screen-etc — Plan 3 of 4 complete
Status: Plan 01-03 (Update Checker & Dist Assets) complete. Plan 04 pending.
Last activity: 2026-03-15 — Plan 01-03 executed: update_checker.py, dist_assets/, BluOpticalSim.spec, build_exe.py, app.py updated

Progress: [######----] 75% (3/4 plans)

## Current Position Detail

Phase: 01-distribution-for-admin-locked-work-computer-compatibility-splash-screen-etc
Current Plan: 4 of 4
Stopped at: Completed 01-03-PLAN.md

## Accumulated Context

### Decisions

- v2.0.0 chosen as first distributable release version (v1.0 was internal milestone)
- User data dir uses %LOCALAPPDATA%/BluOpticalSim on Windows — corporate-safe, no admin rights needed
- config.py strictly no PySide6 — headless-safe for io/ and sim/ layer consumption
- Icon generated at runtime via QPainter + Pillow; script checked in so icon can be regenerated
- Splash uses QWidget with Qt.SplashScreen flag instead of QSplashScreen for full QSS/dark theme control
- Staged loading: 20% theme/icon, 60% after MainWindow import, 90% after construct, 100% on close
- Status bar notification (15s) used for update available — unobtrusive vs modal dialog
- http/urllib un-excluded in PyInstaller spec — required by update_checker, minimal size cost
- Daemon thread for update check — auto-killed if app exits before check completes

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
Stopped at: Completed 01-03-PLAN.md (update checker, dist assets, build pipeline)
Resume file: None
