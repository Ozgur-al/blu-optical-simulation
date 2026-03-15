---
phase: 05-ui-rewamp
plan: 03
subsystem: ui
tags: [PySide6, QTreeWidget, CollapsibleSection, properties-panel, icons, context-menu]

# Dependency graph
requires:
  - phase: 05-ui-rewamp plan 01
    provides: QSS dark theme, tab-based center panel layout, updated ObjectTree structure

provides:
  - CollapsibleSection reusable widget in backlight_sim/gui/widgets/
  - PropertiesPanel forms with collapsible property groups (Identity, Position, Emission, etc.)
  - ObjectTree with per-type colored circle icons (yellow/blue/gray/purple/green/teal/orange)
  - ObjectTree duplicate_requested signal and Duplicate context menu action
  - More descriptive group-level "Add" context menu labels

affects:
  - 05-ui-rewamp plan 02 (MainWindow must wire duplicate_requested)
  - Future form additions must use CollapsibleSection for new property groups

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CollapsibleSection: QToolButton header with arrow indicator + collapsible QFrame content"
    - "Programmatic QIcon creation using QPainter on QPixmap (no image files)"
    - "Class-level _ICONS cache built once per ObjectTree class, shared across instances"
    - "QScrollArea wrapper in each form to handle collapse/expand without layout reflow"

key-files:
  created:
    - backlight_sim/gui/widgets/__init__.py
    - backlight_sim/gui/widgets/collapsible_section.py
  modified:
    - backlight_sim/gui/properties_panel.py
    - backlight_sim/gui/object_tree.py

key-decisions:
  - "CollapsibleSection uses QToolButton (not QPushButton) for built-in arrow indicator support via setArrowType"
  - "Each form wrapped in QScrollArea so expand/collapse doesn't fight fixed-size layout"
  - "Thermal/Binning section collapsed by default in SourceForm — advanced fields users rarely touch per-source"
  - "duplicate_requested signal defined in ObjectTree but intentionally left unwired — MainWindow wires it (avoids file conflict with Plan 02)"
  - "Icon cache at class level (_ICONS dict) — QPainter icons expensive to recreate per item, build once"
  - "Context lambda captures group/name via default arg (g=group, n=name) to avoid Python closure capture-by-reference bug"

patterns-established:
  - "Property form pattern: outer QVBoxLayout > QScrollArea > content QWidget > QVBoxLayout with CollapsibleSection widgets"
  - "Each CollapsibleSection gets a QFormLayout added via section.addLayout()"
  - "_loading guard and QSignalBlocker patterns unchanged — only layout structure changed"

requirements-completed: [UI-05, UI-06]

# Metrics
duration: 5min
completed: 2026-03-14
---

# Phase 05 Plan 03: Collapsible Properties Panel and Colored Object Tree Icons Summary

**CollapsibleSection widget with expand/collapse arrows added to all main property forms; ObjectTree enhanced with QPainter-based per-type colored icons and Duplicate context menu action**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-14T21:38:44Z
- **Completed:** 2026-03-14T21:43:35Z
- **Tasks:** 2
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- Created `backlight_sim/gui/widgets/collapsible_section.py` — reusable QToolButton+QFrame collapsible section widget with arrow indicator
- Refactored 6 property forms (SourceForm, SurfaceForm, DetectorForm, MaterialForm, SolidBoxForm, SettingsForm) to use CollapsibleSection groups instead of flat QFormLayouts
- Enhanced ObjectTree with programmatically-generated colored circle icons per object type (no external image files)
- Added `duplicate_requested = Signal(str, str)` to ObjectTree and "Duplicate" context menu action
- Replaced generic "Add {group[:-1]}" context menu labels with descriptive per-group labels ("Add Point Source", "Add Detector Surface", etc.)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create CollapsibleSection widget and refactor PropertiesPanel** - `d31c748` (feat)
2. **Task 2: Enhance ObjectTree with colored icons and improved context menus** - `45cc28c` (feat)

## Files Created/Modified

- `backlight_sim/gui/widgets/__init__.py` - Package init exporting CollapsibleSection
- `backlight_sim/gui/widgets/collapsible_section.py` - CollapsibleSection widget (addWidget/addLayout/contentLayout/setCollapsed/isCollapsed)
- `backlight_sim/gui/properties_panel.py` - SourceForm, SurfaceForm, DetectorForm, MaterialForm, SolidBoxForm, SettingsForm now use CollapsibleSection
- `backlight_sim/gui/object_tree.py` - Per-type icons, duplicate_requested signal, enhanced context menus

## Decisions Made

- Used QToolButton (not QPushButton) for section headers — built-in setArrowType() gives DownArrow/RightArrow without custom painting
- Each form wrapped in QScrollArea so collapsed/expanded sections don't cause layout overflow
- Thermal/Binning section in SourceForm defaults to collapsed — these fields (current_mA, flux_per_mA, thermal_derate) are advanced and rarely need per-source adjustment
- Convergence and Advanced sections in SettingsForm default to collapsed — Ray Tracing is the main workflow
- Icon cache at class level (`_ICONS`) — avoids recreating QPainter icons for each tree item on every refresh
- Lambda closures in context menu use default argument capture (`g=group, n=name`) to avoid Python late-binding bug

## Deviations from Plan

None - plan executed exactly as written. The "REVISED APPROACH" in Task 2 (use duplicate_requested signal, leave wiring to MainWindow) was already the final plan decision — followed as specified.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CollapsibleSection is ready for use in any future property forms
- duplicate_requested signal must be wired in MainWindow (`self._tree.duplicate_requested.connect(self._duplicate_object)`) — this is Plan 02's responsibility
- All existing property editing, selection, multi-select functionality preserved and verified

---
*Phase: 05-ui-rewamp*
*Completed: 2026-03-14*
