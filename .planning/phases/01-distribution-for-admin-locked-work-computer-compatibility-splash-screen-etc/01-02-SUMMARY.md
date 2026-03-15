---
phase: 01-distribution-for-admin-locked-work-computer-compatibility-splash-screen-etc
plan: 02
subsystem: ui
tags: [pyside6, splash-screen, app-icon, dark-theme, startup]

# Dependency graph
requires:
  - phase: 01-distribution-for-admin-locked-work-computer-compatibility-splash-screen-etc
    plan: 01
    provides: "__version__.py with version string, assets/icon.ico, config.py, theme module"
provides:
  - "SplashScreen widget (backlight_sim/gui/splash.py) with progress bar, status text, and fade_out animation"
  - "Updated app.py with staged loading: icon set, splash shown, MainWindow deferred"
affects:
  - "01-03 (update checker wired into startup after splash)"
  - "01-04 (distribution packaging references icon and updated app.py)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deferred heavy imports inside main() after splash.show() + processEvents()"
    - "QPropertyAnimation fade_out pattern for splash dismissal"
    - "PyInstaller frozen-mode path detection via sys._MEIPASS for assets"

key-files:
  created:
    - backlight_sim/gui/splash.py
  modified:
    - app.py

key-decisions:
  - "Splash uses QWidget with FramelessWindowHint + SplashScreen flags rather than QSplashScreen for full styling control"
  - "Staged loading: 20% after theme apply, 60% after MainWindow import, 90% after construct, 100% on close"
  - "fade_out() uses QPropertyAnimation on windowOpacity for smooth 300ms dismiss"
  - "Theme applied before splash creation so QSS dark styling takes effect on SplashScreen"

patterns-established:
  - "Icon path: sys._MEIPASS for frozen, os.path.dirname(__file__) for dev — guards sys.frozen attribute"
  - "app.processEvents() after each splash update to force repaint before heavy work"

requirements-completed: [DIST-01, DIST-02]

# Metrics
duration: 2min
completed: 2026-03-15
---

# Phase 01 Plan 02: Splash Screen and App Icon Summary

**Frameless dark splash screen (480x280, teal logo, slim progress bar) shown before MainWindow loads, with app icon set from assets/icon.ico in both dev and PyInstaller frozen modes.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-15T22:10:35Z
- **Completed:** 2026-03-15T22:12:35Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created `backlight_sim/gui/splash.py` with `SplashScreen` — frameless QWidget with teal app name (24pt bold), subtitle, 7px progress bar with dark track, status label, and version in corner
- Updated `app.py` to show splash immediately, defer `MainWindow` import, update progress/status through loading stages, and close splash after main window is shown
- Set application icon from `assets/icon.ico` with PyInstaller `sys._MEIPASS` frozen-mode support

## Task Commits

Each task was committed atomically:

1. **Task 1: Create splash screen widget** - `8829281` (feat)
2. **Task 2: Integrate splash screen and icon into app.py** - `603cd95` (feat)

## Files Created/Modified
- `backlight_sim/gui/splash.py` - SplashScreen widget: frameless dark QWidget with progress, status, fade_out API
- `app.py` - Entry point with staged loading, icon setup, splash lifecycle

## Decisions Made
- Used `QWidget` with `Qt.SplashScreen` flag instead of `QSplashScreen` — gives full QSS control for dark theme styling
- `fade_out()` stores animation reference on `self._fade_anim` to prevent GC mid-animation
- Kept `pg.setConfigOption` calls in `main()` before `apply_dark_theme` (apply_dark_theme also sets them — benign double-set)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Verification command ran against a venv missing pyqtgraph (from `blu-thermal-simulation` venv being active). Installed pyqtgraph in the active env to complete verification. Actual runtime environment for the app will have all dependencies from requirements.txt.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Splash screen is live; ready for Plan 03 (update checker) which wires into the startup sequence after splash
- `app.py` staged loading has natural insertion point: between "Loading modules..." and "Initializing GUI..." for the update check

---
*Phase: 01-distribution-for-admin-locked-work-computer-compatibility-splash-screen-etc*
*Completed: 2026-03-15*

## Self-Check: PASSED

- backlight_sim/gui/splash.py: FOUND
- app.py: FOUND
- Commit 8829281: FOUND
- Commit 603cd95: FOUND
