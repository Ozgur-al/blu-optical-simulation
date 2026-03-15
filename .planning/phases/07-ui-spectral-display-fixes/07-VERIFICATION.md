---
phase: 07-ui-spectral-display-fixes
verified: 2026-03-15T11:00:00Z
status: human_needed
score: 4/4 must-haves verified
re_verification: false
human_verification:
  - test: "Tab persistence — open Spectral Data tab, close app, relaunch"
    expected: "Spectral Data tab is still open and active after relaunch"
    why_human: "QSettings restore involves OS-level registry state, cannot simulate session restart in a test"
  - test: "Duplicate action — right-click a Source in the object tree, select Duplicate"
    expected: "A new source (e.g. Source_1) appears in the tree as a deep-copy of the original"
    why_human: "Context menu interaction requires live Qt event loop"
  - test: "Chromaticity scatter — run a spectral simulation, inspect CIE 1931 diagram in Spectral Data tab"
    expected: "A translucent green scatter cloud of per-pixel (x,y) points appears on the diagram after simulation"
    why_human: "Requires visual inspection of pyqtgraph ScatterPlotItem in running app"
  - test: "Live spectral color preview — set heatmap to Spectral Color mode, run a spectral simulation"
    expected: "Heatmap updates with color during simulation progress (not a placeholder message)"
    why_human: "Requires observing incremental heatmap updates during an active simulation run"
---

# Phase 7: UI + Spectral Display Fixes — Verification Report

**Phase Goal:** All UI features work end-to-end (duplicate action, tab persistence) and spectral display paths are complete (chromaticity scatter, live preview color mode)
**Verified:** 2026-03-15T11:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth                                                                              | Status     | Evidence                                                                                              |
| --- | ---------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------- |
| 1   | Tab state persists between sessions via QSettings                                  | ✓ VERIFIED | `_restore_layout` at line 555 coerces `str` to `[str]` before list check; logic is complete          |
| 2   | Right-clicking a scene object and selecting Duplicate creates a copy               | ✓ VERIFIED | `object_tree.py` emits `duplicate_requested`; wired at `main_window.py:437`; `_duplicate_object` handles all 7 group types |
| 3   | After a spectral simulation, chromaticity diagram shows per-pixel (x,y) scatter   | ✓ VERIFIED | `SpectralDataPanel.update_from_result` exists at line 294, substantive (60 lines), wired via `_on_sim_finished:1230` |
| 4   | Live heatmap preview shows spectral color mode during spectral simulations         | ✓ VERIFIED | `tracer.py:954` adds `grid_spectral=dr.grid_spectral.copy()` to partial snapshots; `heatmap_panel.py` consumes `grid_spectral` in Spectral Color mode |

**Score:** 4/4 truths verified (automated checks pass; human visual confirmation outstanding)

### Required Artifacts

| Artifact                                          | Expected                                          | Status     | Details                                                                                 |
| ------------------------------------------------- | ------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------- |
| `backlight_sim/sim/tracer.py`                     | Partial snapshot includes `grid_spectral` copy    | ✓ VERIFIED | Line 954: `grid_spectral=dr.grid_spectral.copy() if dr.grid_spectral is not None else None` |
| `backlight_sim/gui/spectral_data_panel.py`        | Public `update_from_result` method                | ✓ VERIFIED | Method at line 294, 60-line substantive implementation with filtering, subsampling, and scatter plot |
| `backlight_sim/gui/main_window.py`                | Tab restore str coercion + spectral panel wiring  | ✓ VERIFIED | Line 555: `isinstance(saved_tabs, str)` coercion; line 1230: `_spectral_panel.update_from_result(result)` |

### Key Link Verification

| From                                   | To                                      | Via                                              | Status     | Details                                                                               |
| -------------------------------------- | --------------------------------------- | ------------------------------------------------ | ---------- | ------------------------------------------------------------------------------------- |
| `main_window.py`                       | `spectral_data_panel.py`                | `_on_sim_finished` calls `update_from_result`    | ✓ WIRED    | `self._spectral_panel.update_from_result(result)` at line 1230, after `update_results` chain |
| `tracer.py`                            | `heatmap_panel.py`                      | Partial snapshot includes `grid_spectral`        | ✓ WIRED    | `grid_spectral=dr.grid_spectral.copy()` at line 954; `heatmap_panel.py` reads `result.grid_spectral` in `_show_result` |
| `main_window.py`                       | QSettings                               | `_restore_layout` handles str coercion           | ✓ WIRED    | `isinstance(saved_tabs, str)` at line 555 converts bare string to list before list-walk |

### Requirements Coverage

| Requirement | Source Plan   | Description                                                                               | Status      | Evidence                                                                                             |
| ----------- | ------------- | ----------------------------------------------------------------------------------------- | ----------- | ---------------------------------------------------------------------------------------------------- |
| UI-02       | 07-01-PLAN.md | Tab state persists between sessions via QSettings                                         | ✓ SATISFIED | `_restore_layout` Windows str coercion fix at `main_window.py:555`; traceability table maps UI-02 to Phase 7 |
| UI-06       | 07-01-PLAN.md | Object tree enhanced context menus with Duplicate action                                  | ✓ SATISFIED | `object_tree.py:268` emits signal; `main_window.py:437` connects to `_duplicate_object`; all 7 group types handled |
| SPEC-03     | 07-01-PLAN.md | User can view detector result as CIE XYZ / sRGB color image (chromaticity scatter cloud) | ✓ SATISFIED | `SpectralDataPanel.update_from_result` (line 294) + `_on_sim_finished` wiring (line 1230)            |

No orphaned requirements found. All three requirement IDs declared in the plan frontmatter are mapped in REQUIREMENTS.md and covered by verified code.

Note on SPEC-03 traceability: REQUIREMENTS.md maps SPEC-03 to Phase 2 (spectral grid accumulation infrastructure). Phase 7 delivers the display path completion — the chromaticity scatter visualization that makes the requirement end-to-end observable to users. This is a gap-closure extension of SPEC-03, not a conflicting ownership.

### Anti-Patterns Found

None. No TODO/FIXME/PLACEHOLDER comments in any of the three modified files. No stub return patterns. No empty handlers.

### Human Verification Required

All four success criteria require live application verification because they depend on Qt event loop behavior, OS-level QSettings state, or visual pyqtgraph rendering.

#### 1. Tab Persistence (UI-02)

**Test:** Launch the app, open the Spectral Data tab from the Window menu, close the application normally (File > Quit or window X), then relaunch.
**Expected:** The Spectral Data tab is automatically reopened and is the active tab (or the tab that was active at close time is restored).
**Why human:** QSettings restore depends on OS registry state written during a prior session; cannot simulate a full session restart in a unit test.

#### 2. Duplicate Action (UI-06)

**Test:** Right-click a Source (or Surface, Detector, Material) in the object tree and choose "Duplicate [name]" from the context menu.
**Expected:** A new object appears in the tree under the same group, with a name like `Source_1`. The duplicate should be a full deep-copy (same position, flux, and settings as the original). Ctrl+Z should undo the duplication.
**Why human:** Context menu click and tree update require a live Qt event loop; undo behavior requires interactive testing.

#### 3. Chromaticity Scatter Cloud (SPEC-03)

**Test:** Open the Spectral Data tab. Assign a non-white SPD to a source (e.g. `warm_white`). Run a simulation. After completion, inspect the CIE 1931 chromaticity diagram in the Spectral Data tab.
**Expected:** A translucent green scatter cloud of per-pixel (x, y) points appears on the diagram, overlaid on top of the CIE locus. The cloud should be distinct from the single SPD marker point.
**Why human:** Visual inspection of pyqtgraph ScatterPlotItem rendering in a running application.

#### 4. Live Spectral Color Preview

**Test:** Set the heatmap display mode to "Spectral Color". Assign a non-white SPD to a source. Run a simulation (use at least 10 sources or enough rays that progress bar updates are visible during the run).
**Expected:** The heatmap shows a color image that updates at ~5% intervals during the simulation, not a static "no spectral data" message.
**Why human:** Requires observing incremental partial-result updates during an active simulation run; cannot be replicated without the Qt event loop driving partial_result signals.

### Gaps Found During Human Verification (Resolved)

1. **Chromaticity scatter import bug** — `update_from_result()` imported non-existent `spectral_grid_to_xyz`; correct function is `xyz_per_pixel`. ImportError was silently caught by `except Exception: pass`. **Fixed:** `7fe8b28`
2. **Properties panel dropdown too narrow** — Min width 280px caused QComboBox dropdowns to be unclickable at default width. **Fixed:** `7fe8b28` (280→320px + matching splitter size)

All gaps resolved. Phase awaiting final human visual confirmation.

Commits verified:
- `352ed02` — Task 1: tracer.py + spectral_data_panel.py (61 lines added)
- `7bb55f5` — Task 2: main_window.py (3 lines added)
- `7fe8b28` — Fix: chromaticity scatter import bug + properties panel min width

---

_Verified: 2026-03-15T11:00:00Z_
_Verifier: Claude (gsd-verifier)_
