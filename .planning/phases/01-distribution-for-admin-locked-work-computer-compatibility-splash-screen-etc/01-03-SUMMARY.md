---
phase: 01-distribution-for-admin-locked-work-computer-compatibility-splash-screen-etc
plan: 03
subsystem: distribution
tags: [update-checker, pyinstaller, dist-assets, urllib, threading]

# Dependency graph
requires:
  - phase: 01-distribution
    plan: 01
    provides: backlight_sim/__version__.py, backlight_sim/config.py, assets/icon.ico
  - phase: 01-distribution
    plan: 02
    provides: app.py with splash screen flow, window.show() anchor point
provides:
  - backlight_sim/update_checker.py (non-blocking GitHub Releases checker)
  - dist_assets/README.txt (user-facing run instructions + SmartScreen bypass)
  - dist_assets/generate_samples.py (sample .blu file generator)
  - BluOpticalSim.spec updated with icon.ico, http/urllib un-excluded, assets bundled
  - build_exe.py updated with copy_dist_assets() post-build step
  - app.py wired with check_for_update_async after window.show()
affects: [04-distribution-plan]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Daemon thread + QTimer.singleShot for safe cross-thread Qt UI updates"
    - "Broad exception catch in network code — return UpdateInfo(error=...), never raise"
    - "update_checker is stdlib-only (urllib.request + threading) — no external deps"

key-files:
  created:
    - backlight_sim/update_checker.py
    - dist_assets/README.txt
    - dist_assets/generate_samples.py
  modified:
    - BluOpticalSim.spec
    - build_exe.py
    - app.py

key-decisions:
  - "Status bar notification (15s) instead of modal dialog — unobtrusive for frequent startup"
  - "5-second timeout on update check — short enough for corporate firewall hangs"
  - "http and urllib un-excluded in PyInstaller spec (update_checker requires them)"
  - "check_for_update_async uses daemon=True thread — auto-killed if app exits before check completes"
  - "Version comparison uses tuple-of-ints fallback — no packaging dependency required"

patterns-established:
  - "Background network calls: threading.Thread(daemon=True) + QTimer.singleShot(0, ...) for Qt callback"
  - "Dist assets: generate_samples.py uses sys.path insert for portability from any working directory"

requirements-completed: [DIST-03, DIST-04, DIST-05]

# Metrics
duration: 3min
completed: 2026-03-15
---

# Phase 01 Plan 03: Update Checker & Distribution Assets Summary

**Non-blocking GitHub Releases update checker (stdlib-only) wired into app startup, PyInstaller spec updated with icon and http/urllib, dist zip now includes README with SmartScreen bypass steps and three sample .blu project files**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-15T22:15:07Z
- **Completed:** 2026-03-15T22:18:14Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- `backlight_sim/update_checker.py` — stdlib-only non-blocking update check; returns `UpdateInfo`, never raises; 5s timeout suitable for corporate proxies
- `app.py` wired: `check_for_update_async` called after `window.show()`, uses `QTimer.singleShot` for thread-safe status bar notification
- PyInstaller build pipeline updated: icon embedded in `.exe`, `http`/`urllib` no longer excluded, `assets/` bundled, `copy_dist_assets()` post-build step added
- `dist_assets/README.txt` covers getting started, system requirements, SmartScreen bypass, sample projects, update notifications, user data location
- `dist_assets/generate_samples.py` generates `Simple_Box_Demo.blu`, `Automotive_Cluster_Demo.blu`, `Edge_Lit_LGP_Demo.blu` from existing presets

## Task Commits

1. **Task 1: Create update checker module** - `8c21687` (feat)
2. **Task 2: Update build pipeline and create distribution assets** - `5597b04` (feat)
3. **Task 3: Wire update checker into app startup** - `1b1a51d` (feat)

**Plan metadata:** (pending — final commit)

## Files Created/Modified

- `backlight_sim/update_checker.py` - UpdateInfo dataclass, check_for_update(), check_for_update_async()
- `BluOpticalSim.spec` - icon enabled, http/urllib un-excluded, assets/ added to datas, hidden_imports for update_checker/config/__version__
- `build_exe.py` - copy_dist_assets() function added, called from main() after build()
- `dist_assets/README.txt` - 101-line user guide with SmartScreen bypass instructions
- `dist_assets/generate_samples.py` - standalone script producing 3 sample .blu files
- `app.py` - check_for_update_async wired after window.show() with thread-safe QTimer callback

## Decisions Made

- Status bar message (15s auto-dismiss) rather than a modal dialog — engineers find popups intrusive on every startup
- 5-second network timeout chosen as balance between responsiveness and proxy hop latency
- `http` and `urllib` modules removed from PyInstaller excludes — they were previously excluded to reduce bundle size but are required by the update checker; the size cost is minimal (stdlib)
- Daemon thread for update check ensures clean app exit even if check is still in flight

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all three tasks completed without blocking issues.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Update checker, build pipeline, and dist assets all complete
- Plan 04 (final distribution checklist / CI) can proceed
- `python build_exe.py --clean --zip` will produce a complete distribution zip with icon, README, and sample projects

---
*Phase: 01-distribution-for-admin-locked-work-computer-compatibility-splash-screen-etc*
*Completed: 2026-03-15*
