---
phase: 05-ui-rewamp
verified: 2026-03-15T00:00:00Z
status: gaps_found
score: 5/8 must-haves verified
re_verification: false
gaps:
  - truth: "All panels are dockable QDockWidgets that can be dragged, floated, and rearranged, with layout persisting between sessions via QSettings"
    status: failed
    reason: "Implementation deviated from QDockWidget to QSplitter+QTabWidget. Panels cannot be dragged, floated, or rearranged freely — they open as tabs via a Window menu. Only window geometry (not tab layout) is saved to QSettings. Requirement UI-02 explicitly required 'dockable QDockWidgets that can be dragged, floated, tabbed, and rearranged'. This is a known user-approved deviation documented in 05-01-SUMMARY.md, but the requirement text itself was never updated."
    artifacts:
      - path: "backlight_sim/gui/main_window.py"
        issue: "setCentralWidget(main_splitter) with QSplitter+QTabWidget — no QDockWidget usage, no addDockWidget calls"
    missing:
      - "Either implement QDockWidget layout as originally specified in UI-02, OR update REQUIREMENTS.md UI-02 text to match the delivered QSplitter+QTabWidget implementation so requirement and code agree"
  - truth: "Right-clicking an object in the tree offers Duplicate in addition to Delete"
    status: failed
    reason: "duplicate_requested Signal is defined on ObjectTree and emitted by the Duplicate context menu item, but the signal is never connected in MainWindow._connect_signals(). No _duplicate_object method exists in main_window.py. The Duplicate menu option appears but does nothing when clicked."
    artifacts:
      - path: "backlight_sim/gui/object_tree.py"
        issue: "duplicate_requested Signal defined (line 50) and emitted in context menu, but signal is unwired"
      - path: "backlight_sim/gui/main_window.py"
        issue: "No duplicate_requested.connect() call and no _duplicate_object() method"
    missing:
      - "Add self._tree.duplicate_requested.connect(self._duplicate_object) to MainWindow._connect_signals()"
      - "Implement _duplicate_object(group, name) method in MainWindow that deep-copies the named object and pushes an Add*Command to _undo_stack"
  - truth: "Panel layout and window geometry persist between application sessions via QSettings"
    status: partial
    reason: "Window geometry (size, position) is saved and restored via QSettings saveGeometry/restoreGeometry. However, tab arrangement (which panels are open, their order) is not persisted — tabs reset to the default 3D View + Heatmap + BSDF on each launch. The QTabWidget has no state persistence."
    artifacts:
      - path: "backlight_sim/gui/main_window.py"
        issue: "_save_layout saves only saveGeometry() — tab layout is not saved. _restore_layout restores only geometry — tab state is not restored."
    missing:
      - "Save open tab titles/order to QSettings in _save_layout()"
      - "Restore open tabs in _restore_layout() by calling _open_tab for each saved tab name"
human_verification:
  - test: "Visual dark theme appearance"
    expected: "All widgets have dark backgrounds (#1e1e1e base, #252525 panels), teal (#00bcd4) accent on selection and buttons, visible spinbox up/down arrows, and pyqtgraph plots with dark backgrounds"
    why_human: "CSS rendering and visual correctness cannot be verified programmatically"
  - test: "Collapsible sections in properties panel"
    expected: "Clicking section headers (Position, Orientation, Emission, etc.) collapses and expands the section with arrow indicator changing from down to right"
    why_human: "Widget interaction requires runtime UI testing"
  - test: "Live heatmap preview during simulation"
    expected: "Running a multi-source simulation (not MP mode) shows the heatmap updating progressively as rays accumulate, not just showing the final result"
    why_human: "Requires running the simulation and observing real-time behavior"
  - test: "Colormap selector live switching"
    expected: "Changing the colormap dropdown in the Heatmap panel updates the heatmap colors and colorbar immediately without requiring a new simulation"
    why_human: "Requires runtime heatmap interaction"
  - test: "Crosshair cursor tracking"
    expected: "Moving the mouse over the heatmap image shows a crosshair following the cursor, and the Cursor label updates to show pixel coordinates and flux value"
    why_human: "Requires interactive mouse testing"
---

# Phase 05: UI Revamp Verification Report

**Phase Goal:** Application has a professional dark-themed interface with dockable panels, toolbar, undo/redo, collapsible properties, enhanced heatmap with live simulation preview — matching the look and workflow of engineering tools like Blender and Fusion 360

**Verified:** 2026-03-15

**Status:** gaps_found

**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

The must-haves are derived from the six ROADMAP.md Success Criteria plus key_links from PLAN frontmatter across all four plans.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Application launches with dark theme and teal accent across all widgets | VERIFIED | `backlight_sim/gui/theme/__init__.py` exports `apply_dark_theme` and palette constants; `dark.qss` is 719 lines covering all widget types; `app.py` calls `apply_dark_theme(app)` before `MainWindow`; `viewport_3d.py` line 19 calls `setBackgroundColor(30, 30, 30, 255)` |
| 2 | All panels are dockable QDockWidgets that can be dragged, floated, and rearranged, with layout persisting via QSettings | FAILED | Implementation uses `QSplitter + QTabWidget` — no `addDockWidget` calls found in `main_window.py`. Panels open as tabs via Window menu but cannot be floated or freely rearranged. Only geometry is saved to QSettings, not tab layout. Documented user-approved deviation in 05-01-SUMMARY.md. |
| 3 | Toolbar provides quick access to common actions and one-click object creation | VERIFIED | `_setup_toolbar()` creates `QToolBar("Main")` with `objectName="main_toolbar"`, adds New/Open/Save, Undo/Redo, Run/Cancel, and 6 quick-add buttons (Add LED, Add Surface, Add Detector, Add SolidBox, Add Cylinder, Add Prism) |
| 4 | Scene mutations (add/delete) can be undone/redone via Ctrl+Z / Ctrl+Y | VERIFIED | `QUndoStack` created at line 97; `createUndoAction`/`createRedoAction` wired to Edit menu; all `_add_object` and `_delete_object` paths push typed commands; `_undo_stack.clear()` called at all 5 project-replacement paths |
| 5 | Properties panel uses collapsible sections with expand/collapse arrows | VERIFIED | `CollapsibleSection` widget at `backlight_sim/gui/widgets/collapsible_section.py` (95 lines, `QToolButton` with `setArrowType`); imported and used in `properties_panel.py` across `show_source`, `show_surface`, `show_detector`, `show_material`, `show_solid_box`, `show_settings` |
| 6 | Object tree shows per-type colored icons (source=yellow, surface=blue, etc.) | VERIFIED | `_make_icon(color_hex)` creates `QPixmap` + `QPainter` circle icons; `_GROUP_ICON_COLOR` dict maps all 7 group types; class-level `_ICONS` cache; icons set on tree items in `refresh()` |
| 7 | Right-clicking an object offers Duplicate in addition to Delete | FAILED | `duplicate_requested = Signal(str, str)` defined at `object_tree.py` line 50 and emitted in context menu, but `main_window.py` contains no `duplicate_requested.connect()` call and no `_duplicate_object()` method — signal is unwired, Duplicate item does nothing |
| 8 | Heatmap updates live during simulation with selectable colormaps and KPI threshold coloring | VERIFIED | `_colormap_combo` exists at `heatmap_panel.py` line 135; `_crosshair_v` at line 165; `_cursor_lbl` at line 188; `CollapsibleSection` wraps all 4 KPI sections; `_threshold_color()` helper at line 97; `partial_result_callback` in `RayTracer.run()` at `tracer.py` line 163; `SimulationThread.partial_result` Signal at `main_window.py` line 51; `_on_partial_result()` handler at line 1071 |

**Score:** 5/8 truths verified (2 failed, 1 partial folded into UI-02 gap)

---

## Required Artifacts

| Artifact | Provides | Status | Details |
|----------|----------|--------|---------|
| `backlight_sim/gui/theme/__init__.py` | `apply_dark_theme(app)` + palette constants | VERIFIED | Exports `apply_dark_theme`, `BG_BASE`, `BG_PANEL`, `BG_INPUT`, `ACCENT`, `TEXT_PRIMARY`; uses `pg.setConfigOption` (singular, correct) |
| `backlight_sim/gui/theme/dark.qss` | Global QSS stylesheet | VERIFIED | 719 lines; covers `QDockWidget`, `QDoubleSpinBox`, `#00bcd4` accent color present; `QTreeWidget::item:selected` teal highlight defined |
| `app.py` | Theme application before MainWindow | VERIFIED | Imports `apply_dark_theme`; calls it before `MainWindow()` construction |
| `backlight_sim/gui/main_window.py` | QToolBar, QSettings save/restore | VERIFIED | `QToolBar` at line 374; `QSettings` save/restore via `_save_layout`/`_restore_layout`; PARTIAL on docking — uses QSplitter, not QDockWidget |
| `backlight_sim/gui/commands/__init__.py` | Module init | VERIFIED | Exists |
| `backlight_sim/gui/commands/base.py` | `ProjectCommand` base class | VERIFIED | `ProjectCommand(QUndoCommand)` with `description`, `project`, `refresh_fn` |
| `backlight_sim/gui/commands/source_commands.py` | `AddSourceCommand`, `DeleteSourceCommand`, `SetSourcePropertyCommand` | VERIFIED | All three present with correct `redo()`/`undo()`; `mergeWith()` implemented |
| `backlight_sim/gui/commands/surface_commands.py` | `AddSurfaceCommand`, `DeleteSurfaceCommand`, `SetSurfacePropertyCommand` | VERIFIED | All three present |
| `backlight_sim/gui/commands/scene_commands.py` | `SetPropertyCommand`, `AddDetectorCommand`, `DeleteDetectorCommand` etc. | VERIFIED | All exported classes present with `redo()`/`undo()` |
| `backlight_sim/gui/widgets/collapsible_section.py` | `CollapsibleSection` widget | VERIFIED | 95 lines; `addWidget`, `addLayout`, `contentLayout`, `setCollapsed`, `isCollapsed` methods all present |
| `backlight_sim/gui/properties_panel.py` | PropertiesPanel with collapsible sections | VERIFIED | Imports `CollapsibleSection`; uses it in 6+ `show_*` methods |
| `backlight_sim/gui/object_tree.py` | ObjectTree with colored icons + context menus | VERIFIED (partial) | `QIcon` + `QPainter` icons present; `duplicate_requested` Signal defined; context menu "Duplicate" action emits signal — but signal unconnected in MainWindow |
| `backlight_sim/gui/heatmap_panel.py` | Colormap selector, crosshair, collapsible KPI cards | VERIFIED | `_colormap_combo`, `_crosshair_v`, `_cursor_lbl`, `CollapsibleSection` for 4 KPI sections, `_threshold_color()` helper all present |
| `backlight_sim/sim/tracer.py` | `partial_result_callback` parameter in `run()` | VERIFIED | Parameter at line 163; passed to `_run_single()` at line 183; guard prevents passing to MP path at line 199 |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app.py` | `backlight_sim/gui/theme/__init__.py` | `apply_dark_theme(app)` call | WIRED | Line 22 in app.py: `apply_dark_theme(app)` before MainWindow construction |
| `backlight_sim/gui/main_window.py` | `QSettings` | `saveGeometry`/`restoreGeometry` | PARTIAL | Geometry saved/restored; dock/tab state NOT saved — `saveState` not called |
| `backlight_sim/gui/main_window.py` | `QDockWidget` | `addDockWidget` | NOT WIRED | No `addDockWidget` calls in codebase — QSplitter+QTabWidget used instead |
| `backlight_sim/gui/main_window.py` | `QUndoStack` | `createUndoAction`/`createRedoAction` | WIRED | Lines 294–296; Ctrl+Z and Ctrl+Y shortcuts attached |
| `backlight_sim/gui/main_window.py` | `backlight_sim/gui/commands/` | `_undo_stack.push(command)` | WIRED | All `_add_object` and `_delete_object` paths verified to push typed commands |
| `backlight_sim/gui/properties_panel.py` | `backlight_sim/gui/widgets/collapsible_section.py` | `import CollapsibleSection` + usage | WIRED | Import at line 34; used in `show_source`, `show_surface`, `show_detector`, `show_material`, `show_solid_box`, `show_settings` |
| `backlight_sim/gui/object_tree.py` | `QIcon` | `setIcon` on tree items | WIRED | `_make_icon()` + `_ICONS` cache; `setIcon(0, ...)` called on child items in `refresh()` |
| `backlight_sim/gui/object_tree.py` (duplicate_requested) | `backlight_sim/gui/main_window.py` | `duplicate_requested.connect(_duplicate_object)` | NOT WIRED | Signal defined, emitted in context menu, but not connected in `_connect_signals()` |
| `backlight_sim/gui/main_window.py` | `backlight_sim/gui/heatmap_panel.py` | `SimulationThread.partial_result` signal connected to `heatmap.update_results` | WIRED | Line 1056: `self._sim_thread.partial_result.connect(self._on_partial_result)`; handler at line 1071 calls `self._heatmap.update_results(result)` |
| `backlight_sim/sim/tracer.py` | `backlight_sim/gui/main_window.py` | `partial_result_callback` called during simulation | WIRED | Tracer calls callback at line 962; SimulationThread passes `self.partial_result.emit` as the callback at line 62 |
| `backlight_sim/gui/heatmap_panel.py` | `pyqtgraph.colormap` | `pg.colormap.get(name)` | WIRED | `_apply_colormap()` at line 386 calls `pg.colormap.get(name)` |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| UI-01 | 05-01 | Dark theme with teal/cyan accent across all widgets | SATISFIED | `theme/__init__.py` + `dark.qss` (719 lines) applied in `app.py`; GLViewWidget dark BG set |
| UI-02 | 05-01 | All panels dockable QDockWidgets with QSettings layout persistence | NOT SATISFIED | QSplitter+QTabWidget used instead; panels cannot be floated/dragged; only window geometry saved, not panel layout. User-approved deviation but requirement text unchanged. |
| UI-03 | 05-01 | Top toolbar with icon+text buttons for common actions and quick-add | SATISFIED | `QToolBar("Main")` with New/Open/Save/Undo/Redo/Run/Cancel + 6 quick-add buttons |
| UI-04 | 05-02 | Full undo/redo system via QUndoStack for all scene mutations | SATISFIED | `QUndoStack` wired; all add/delete operations push typed commands; Edit menu with Ctrl+Z/Ctrl+Y; stack cleared on all 5 project-replacement paths |
| UI-05 | 05-03 | Properties panel uses collapsible sections | SATISFIED | `CollapsibleSection` widget (95 lines); imported and used across 6+ property forms |
| UI-06 | 05-03 | Object tree shows per-type colored icons and Duplicate action | PARTIAL | Icons: satisfied. Duplicate context menu: appears but signal is unwired in MainWindow — no `_duplicate_object` handler exists. |
| UI-07 | 05-04 | Heatmap: selectable colormaps, crosshair, KPI cards with color-coded thresholds | SATISFIED | All three features present and substantive: `_colormap_combo`, `_crosshair_v`/`_cursor_lbl`, CollapsibleSection KPI sections with `_threshold_color()` |
| UI-08 | 05-04 | Live heatmap preview at 5% intervals, auto-focus heatmap after simulation | SATISFIED | `partial_result_callback` in tracer; SimulationThread emits `partial_result`; `_on_partial_result` updates heatmap; `_on_sim_finished` focuses Heatmap tab via `_open_tab` |

**Orphaned requirements:** None — all UI-01 through UI-08 are claimed by a plan in this phase.

---

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `object_tree.py` line 51–52 | Comment: "NOTE: duplicate_requested must be connected in MainWindow" — signal never connected | BLOCKER | Duplicate context menu item appears but is a no-op; user confusion |
| `main_window.py` _save_layout | Only saves `saveGeometry()` — tab panel state not persisted | WARNING | Panel arrangement resets on every launch; claimed layout persistence is incomplete |

---

## Human Verification Required

### 1. Dark Theme Visual Appearance

**Test:** Launch `python app.py` and inspect the UI without loading any project.
**Expected:** All widgets have dark backgrounds matching `#1e1e1e` base / `#252525` panels; toolbar and status bar are dark; teal (`#00bcd4`) accent visible on focused inputs and selected tree items; spinbox up/down arrows are visible (not dark-on-dark).
**Why human:** CSS rendering and color correctness cannot be verified programmatically.

### 2. Collapsible Section Interaction

**Test:** Load a preset, click a source in the scene tree, observe the Properties panel. Click the "Emission" section header.
**Expected:** The Emission section collapses (fields hidden, arrow changes from down to right). Clicking again expands it.
**Why human:** Widget interaction and visual state change requires runtime testing.

### 3. Live Heatmap Preview

**Test:** Load the Simple Box preset. Set rays to 100k. Ensure multiprocessing is OFF. Run the simulation.
**Expected:** The Heatmap panel shows a progressively building heatmap as rays accumulate — not just the final image appearing all at once.
**Why human:** Requires observing real-time animation during a multi-second simulation run.

### 4. Colormap Selector

**Test:** After a simulation completes, open the Heatmap tab. Change the colormap dropdown from "inferno" to "viridis".
**Expected:** The heatmap image and colorbar both update immediately to the viridis color scale.
**Why human:** Requires runtime interaction with a loaded simulation result.

### 5. Crosshair Cursor

**Test:** Move the mouse over the heatmap image (with results displayed).
**Expected:** A crosshair follows the cursor, and the label below the plot updates to show "Cursor: (x, y) = flux_value".
**Why human:** Mouse event tracking requires interactive testing.

---

## Gaps Summary

Two gaps block full goal achievement:

**Gap 1 — UI-02: QDockWidget vs QSplitter+QTabWidget**

The PLAN specified QDockWidgets (drag, float, rearrange, QSettings window state). The implementation delivered QSplitter+QTabWidget with a Window menu to open panels as tabs. Panels are closable and reorderable within the tab bar but cannot be floated or freely rearranged across the window. This was a user-approved deviation at the 05-01 checkpoint, but the REQUIREMENTS.md UI-02 text was never updated to match the delivered architecture. This gap is a requirement-code mismatch — either the code needs updating to match the requirement, or the requirement text needs updating to ratify the delivered design.

**Gap 2 — UI-06: Duplicate action is unwired**

The ObjectTree emits `duplicate_requested(group, name)` from the context menu, but MainWindow has no `duplicate_requested.connect()` call and no `_duplicate_object()` method. The Plan 03 SUMMARY notes this as intentional ("leave wiring to Plan 02") but Plan 02's SUMMARY does not mention wiring it, and the grep confirms it was never wired. The Duplicate menu item appears in the context menu but does nothing when clicked.

**Gap 3 — UI-02 subset: Tab layout not persisted**

Only window geometry (size, position) is saved. Which tabs are open, their order, and the splitter positions are not saved. On each launch the app opens with the fixed default tabs (3D View, Heatmap, BSDF). This is within the same UI-02 gap but a distinct missing behavior.

---

_Verified: 2026-03-15_
_Verifier: Claude (gsd-verifier)_
