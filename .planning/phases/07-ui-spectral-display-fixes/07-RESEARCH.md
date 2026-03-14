# Phase 7: UI + Spectral Display Fixes — Research

**Researched:** 2026-03-15
**Domain:** PySide6 GUI wiring (tab persistence, duplicate action) + pyqtgraph spectral display (chromaticity scatter, live preview spectral color)
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| UI-02 | Left sidebar with central tabbed panel area; tab state persists between sessions via QSettings | Tab save/restore code exists in `_save_layout`/`_restore_layout` but has a QSettings list-vs-string type bug on Windows; fix is in `_restore_layout` |
| UI-06 | Object tree shows per-type colored icons and enhanced context menus with Duplicate action | Icons: done. `duplicate_requested` signal is defined AND connected in `_connect_signals` AND `_duplicate_object` handler exists — signal fires correctly already; audit was stale. Needs validation. |
| SPEC-03 | User can view detector result as a CIE XYZ / sRGB color image | SpectralDataPanel needs a new public `update_from_result(result)` method wired from `_on_sim_finished`; `xy_per_pixel` helper already exists in `spectral.py` |
</phase_requirements>

---

## Summary

Phase 7 closes four specific gaps identified in the v1.0 milestone audit. All four are wiring or minor implementation gaps — no new subsystems are needed. The code infrastructure for each fix is already in place; the gaps are missing connections or partial implementations.

**Gap 1 — Tab persistence (UI-02):** `_save_layout` writes `open_tabs` as a list to `QSettings`. On Windows, `QSettings.value()` can deserialize a single-element list as a bare string and a multi-element list as `list[str]` — but there is also a known PySide6 Windows issue where `QSettings.value("open_tabs")` typed as a list returns a list of strings correctly. The `_restore_layout` code has an `isinstance(saved_tabs, list)` guard but no `isinstance(saved_tabs, str)` fallback. If QSettings returns a bare string (single tab), restoration silently fails. Fix: wrap with `if isinstance(saved_tabs, str): saved_tabs = [saved_tabs]`.

**Gap 2 — Duplicate action (UI-06):** The audit noted `duplicate_requested` was "never connected in main_window.py." The current source code shows this is already fixed — `_connect_signals` at line 437 connects `self._tree.duplicate_requested.connect(self._duplicate_object)` and `_duplicate_object` is fully implemented. The audit was written before or during Phase 5 completion. This gap may already be closed. **Validation required:** manually right-click a source in the object tree and confirm the duplicate appears.

**Gap 3 — Chromaticity scatter post-simulation (SPEC-03):** `_on_sim_finished` in `main_window.py` does not call any update on `_spectral_panel`. The `SpectralDataPanel._chroma_scatter` currently shows only the selected SPD's single coordinate. A new public method `update_from_result(result)` must be added to `SpectralDataPanel` that: (1) iterates detectors for one with `grid_spectral`, (2) calls `spectral_grid_to_xyz` + `xy_per_pixel` from `spectral.py`, (3) filters zero-luminance pixels, (4) scatter-plots the (x,y) cloud on `_chroma_plot`. Then `_on_sim_finished` calls `self._spectral_panel.update_from_result(result)`.

**Gap 4 — Live preview spectral color mode (UI-08/SPEC-03):** The `_on_partial_result` callback emits a `SimulationResult` snapshot where each `DetectorResult` has `grid=dr.grid.copy()` but `grid_spectral=None` (not included in partial snapshots). When `HeatmapPanel` is in spectral color mode, it sees `grid_spectral is None` and falls back to intensity mode with an informational message. Fix: include `grid_spectral` in the partial snapshot by copying it alongside `grid`. The relevant code is in `tracer.py` `_run_single` around line 946.

**Primary recommendation:** Implement all four fixes in a single plan (one wave). They are independent, small, and test-verifiable. Total scope is ~30 lines of code across 3 files: `tracer.py`, `spectral_data_panel.py`, `main_window.py`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | installed | QSettings, signal/slot wiring | Already the project framework |
| pyqtgraph | installed | ScatterPlotItem for chromaticity cloud | Already used in SpectralDataPanel |
| NumPy | installed | `grid_spectral.copy()` for partial snapshots, `xy_per_pixel` computation | Already the math layer |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `backlight_sim.sim.spectral` | internal | `spectral_grid_to_xyz`, `spectral_bin_centers`, `xy_per_pixel` | Computing chromaticity per pixel from spectral grids |

**Installation:**
```bash
# No new packages — all dependencies already in requirements.txt
```

---

## Architecture Patterns

### Recommended Project Structure

No new files needed. All changes are modifications to existing files:

```
backlight_sim/
├── sim/
│   └── tracer.py              # Gap 4: add grid_spectral.copy() to partial snapshot
├── gui/
│   ├── spectral_data_panel.py # Gap 3: add update_from_result(result) public method
│   └── main_window.py         # Gap 1: fix _restore_layout; Gap 2: validate; Gap 3: wire call; Gap 4: no change needed
```

### Pattern 1: Partial Result Snapshot with Spectral Grid

**What:** Include `grid_spectral` in the partial `DetectorResult` snapshots emitted during simulation progress.

**Current code (tracer.py ~line 947):**
```python
# Current: grid_spectral NOT included
partial_detectors[det_name] = DetectorResult(
    detector_name=det_name,
    grid=dr.grid.copy(),
    total_hits=dr.total_hits,
    total_flux=dr.total_flux,
)
```

**Fix:**
```python
# Source: audit gap "Live preview + Spectral Color: partial_result_callback omits grid_spectral"
partial_detectors[det_name] = DetectorResult(
    detector_name=det_name,
    grid=dr.grid.copy(),
    total_hits=dr.total_hits,
    total_flux=dr.total_flux,
    grid_spectral=dr.grid_spectral.copy() if dr.grid_spectral is not None else None,
)
```

**Performance note:** `grid_spectral` is shape `(ny, nx, n_bins)` — for a 100×100 detector with 32 spectral bins, this is ~320 KB per copy. At 5% intervals (20 emits), total extra allocation is ~6.4 MB per simulation — acceptable. The guard `if dr.grid_spectral is not None else None` ensures no overhead for non-spectral simulations.

### Pattern 2: SpectralDataPanel Chromaticity Cloud Update

**What:** New public method on `SpectralDataPanel` that computes per-pixel CIE (x,y) from `grid_spectral` and plots as a scatter cloud.

**Implementation:**
```python
# Source: spectral.py already has xy_per_pixel() and spectral_grid_to_xyz()
# In spectral_data_panel.py

def update_from_result(self, result) -> None:
    """Update chromaticity scatter with per-pixel simulation colors.

    Called by MainWindow._on_sim_finished(). Plots all illuminated pixels
    as (x, y) points on the CIE 1931 diagram.
    """
    from backlight_sim.sim.spectral import spectral_grid_to_xyz, spectral_bin_centers

    # Clear previous simulation scatter (keep SPD marker separate)
    if hasattr(self, "_sim_scatter"):
        self._chroma_plot.removeItem(self._sim_scatter)
    self._sim_scatter = None

    # Find the first detector with spectral data
    grid_spectral = None
    for dr in result.detectors.values():
        if dr.grid_spectral is not None:
            grid_spectral = dr.grid_spectral
            break

    if grid_spectral is None:
        return  # Non-spectral simulation — nothing to plot

    try:
        n_bins = grid_spectral.shape[2]
        wl = spectral_bin_centers(n_bins)
        xyz = spectral_grid_to_xyz(grid_spectral, wl)   # (ny, nx, 3)

        from backlight_sim.sim.spectral import xy_per_pixel
        xy = xy_per_pixel(xyz)  # (ny, nx, 2)

        # Filter illuminated pixels only (luminance > threshold)
        luminance = xyz[..., 1]  # Y channel
        threshold = luminance.max() * 0.01
        mask = luminance > threshold

        xs = xy[..., 0][mask]
        ys = xy[..., 1][mask]

        if len(xs) == 0:
            return

        # Subsample to avoid scatter overload on high-res detectors
        max_pts = 2000
        if len(xs) > max_pts:
            idx = np.random.choice(len(xs), max_pts, replace=False)
            xs, ys = xs[idx], ys[idx]

        scatter = pg.ScatterPlotItem(
            x=xs, y=ys,
            size=5,
            pen=pg.mkPen(None),
            brush=pg.mkBrush(80, 200, 120, 120),  # translucent green
        )
        self._chroma_plot.addItem(scatter)
        self._sim_scatter = scatter

        # Restore fixed view range
        self._chroma_plot.setXRange(0.0, 0.85, padding=0.02)
        self._chroma_plot.setYRange(0.0, 0.92, padding=0.02)
    except Exception:
        pass  # Non-critical display enhancement
```

**Key constraint:** Use a separate `_sim_scatter` item from `_chroma_scatter` (which shows the SPD marker). Both coexist on the plot.

### Pattern 3: QSettings Tab Restore — Single-Element List Fix

**What:** When `QSettings` stores a list with one element on Windows, it may deserialize as a bare `str` rather than `list[str]`.

**Current code (main_window.py `_restore_layout`):**
```python
saved_tabs = settings.value("open_tabs")
if saved_tabs and isinstance(saved_tabs, list):
    ...
```

**Fix:**
```python
# Source: QSettings Windows deserialization behavior (verified from Qt docs)
saved_tabs = settings.value("open_tabs")
if isinstance(saved_tabs, str):
    saved_tabs = [saved_tabs]  # single-tab case on Windows
if saved_tabs and isinstance(saved_tabs, list):
    ...
```

**Why this matters:** First launch saves `["3D View", "Heatmap"]` (two items — no issue). But if a user closes all optional tabs, only the two non-closable tabs remain, saved as `["3D View", "Heatmap"]`. This is still two items. The problem would surface if only one tab were somehow saved. The primary fix is defensive — ensures correctness for edge cases. The main original gap is that `_save_layout` saves correctly but `_restore_layout` was never validated end-to-end.

**Deeper issue:** The audit evidence states "tab layout (open tabs, order) not persisted via QSettings — resets on each launch." But the code shows `_save_layout` writing `open_tabs` and `_restore_layout` reading it. The actual bug may be: `_open_tab` is called for each saved title, but "3D View" and "Heatmap" are already in `_tab_registry` from `_setup_ui`, so the guard `title not in self._tab_registry` prevents re-opening them, and their order from QSettings is ignored. The fix requires that after `_restore_layout`, we ensure the active tab index from saved state is honored.

**Concrete investigation finding:** The restore code `for title in saved_tabs: if title in panel_map and title not in self._tab_registry:` correctly skips already-open tabs. The `active_tab` index is then applied. This means tabs like "Angular Dist." would be reopened if they were open when the app last closed. The tab ORDER within `_center_tabs` may not match `saved_tabs` order because "3D View" and "Heatmap" are pre-opened. Fix: also ensure "3D View" and "Heatmap" are moved to their saved positions, or simply rely on the restore working for extra tabs and active index.

### Pattern 4: Wire Chromaticity Update in `_on_sim_finished`

**What:** Single line addition to `main_window._on_sim_finished`:

```python
def _on_sim_finished(self, result):
    # ... existing code ...
    self._heatmap.update_results(result)
    self._plot_tab.update_results(result)
    self._receiver_3d.update_results(result)
    self._spectral_panel.update_from_result(result)  # ADD THIS LINE
    # ... rest of existing code ...
```

### Anti-Patterns to Avoid

- **Replacing `_chroma_scatter`:** The existing `_chroma_scatter` shows the selected SPD marker. Keep it separate from the simulation scatter. Use a second `_sim_scatter` item that is added/removed independently.
- **Deep-copying the entire `SimulationResult` for partial snapshots:** Keep using shallow copies (`dr.grid.copy()`, `dr.grid_spectral.copy()`) — full deepcopy at 5% intervals would be prohibitive.
- **Computing chromaticity for all pixels including dark pixels:** Filter with `luminance > threshold` first. Dark/unilluminated pixels cluster near (0,0) and (0.333, 0.333) as numerical noise, polluting the scatter diagram.
- **Using `spectral_grid_to_rgb` for chromaticity:** That function returns sRGB, not chromaticity. Use `spectral_grid_to_xyz` then `xy_per_pixel` for the CIE diagram update.
- **Not handling `grid_spectral` None guard in partial snapshot:** Always guard with `if dr.grid_spectral is not None else None` — non-spectral simulations must have zero overhead.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-pixel CIE (x,y) computation | Custom matrix multiply | `spectral_grid_to_xyz` + `xy_per_pixel` from `sim/spectral.py` | Already implemented, tested, handles zero-luminance masking |
| Chromaticity scatter plot | Custom renderer | `pg.ScatterPlotItem` | pyqtgraph scatter is already in the panel, used for SPD marker |
| Spectral bin wavelengths | Hardcoded array | `spectral_bin_centers(n_bins)` | Consistent with tracer's spectral resolution |

**Key insight:** All computational infrastructure exists. Phase 7 is purely wiring + one small display method.

---

## Common Pitfalls

### Pitfall 1: `_sim_scatter` Not Removed on Next Simulation
**What goes wrong:** Each simulation adds a new scatter item to the chromaticity plot — old cloud remains visible behind new results.
**Why it happens:** `_chroma_plot.addItem(scatter)` accumulates items; no cleanup between runs.
**How to avoid:** Track `self._sim_scatter` at instance level. At the start of `update_from_result`, call `if hasattr(self, "_sim_scatter") and self._sim_scatter is not None: self._chroma_plot.removeItem(self._sim_scatter)`.
**Warning signs:** Multiple overlapping point clouds after running simulation twice.

### Pitfall 2: `spectral_grid_to_xyz` vs `spectral_grid_to_rgb` Confusion
**What goes wrong:** Using `spectral_grid_to_rgb` to compute chromaticity gives sRGB values (after gamut mapping + gamma), not linear CIE chromaticity — scatter points cluster incorrectly.
**Why it happens:** Both functions are in `spectral.py`; names are similar.
**How to avoid:** Use `spectral_grid_to_xyz` (returns raw XYZ) → `xy_per_pixel` (returns CIE chromaticity). The `spectral_grid_to_rgb` function applies sRGB linearization and is only for display.

### Pitfall 3: `DetectorResult` Constructor Keyword for `grid_spectral`
**What goes wrong:** Partial snapshot creation fails with `TypeError: __init__() got an unexpected keyword argument 'grid_spectral'`.
**Why it happens:** `DetectorResult` is a dataclass; if the field `grid_spectral` was added later, old snapshot construction code may not include it.
**How to avoid:** Verify `DetectorResult.__init__` signature includes `grid_spectral: np.ndarray | None = None`. It does (confirmed in tracer.py line 326–328). Safe to add to partial construction.

### Pitfall 4: QSettings `value()` Type Coercion on Windows
**What goes wrong:** Tab restore works on macOS/Linux (which return native Python types from QSettings) but fails on Windows where `QSettings` backed by the registry may return all values as `str`.
**Why it happens:** On Windows, `QSettings` uses the registry by default, which has no native list type. Qt serializes lists as a numbered format or concatenated string depending on the Qt version.
**How to avoid:** Use `settings.value("open_tabs", [], type=list)` — the `type` parameter coerces the deserialized value. Alternatively, serialize as JSON string: `settings.setValue("open_tabs", json.dumps(tab_titles))` and `json.loads(settings.value("open_tabs", "[]"))`.

### Pitfall 5: Scatter Point Overload on High-Resolution Detectors
**What goes wrong:** 200×200 detector (40,000 pixels) causes `ScatterPlotItem` to render 40,000 points, making the chromaticity diagram unresponsive.
**Why it happens:** No sampling limit on pixels passed to scatter.
**How to avoid:** Cap at ~2,000 points using `np.random.choice(len(xs), max_pts, replace=False)` when `len(xs) > max_pts`. This is visually sufficient for chromaticity cloud visualization.

### Pitfall 6: `xy_per_pixel` Importing from `spectral.py` Inside GUI
**What goes wrong:** `from backlight_sim.sim.spectral import xy_per_pixel` — if the function wasn't in the module's public API (not in `__all__`), it would fail at runtime.
**Why it happens:** `xy_per_pixel` is a relatively new addition; its importability from `sim/spectral.py` is confirmed by source reading (it's defined as a module-level function at line 294).
**How to avoid:** Verified — `xy_per_pixel` is importable from `backlight_sim.sim.spectral`. No `__all__` restriction exists in that module.

---

## Code Examples

Verified patterns from official sources and codebase inspection:

### Partial Snapshot with Spectral Grid (tracer.py)
```python
# Source: tracer.py _run_single, line ~947; gap from v1.0 audit
if partial_result_callback and progress >= 0.05:
    partial_detectors = {}
    for det_name, dr in det_results.items():
        partial_detectors[det_name] = DetectorResult(
            detector_name=det_name,
            grid=dr.grid.copy(),
            total_hits=dr.total_hits,
            total_flux=dr.total_flux,
            grid_spectral=dr.grid_spectral.copy() if dr.grid_spectral is not None else None,
        )
    partial = SimulationResult(
        detectors=partial_detectors,
        ray_paths=[],
        escaped_flux=escaped_flux,
        total_emitted_flux=total_emitted_flux,
        source_count=src_idx + 1,
    )
    partial_result_callback(partial)
```

### QSettings List Restore Fix (main_window.py)
```python
# Source: Qt docs — QSettings Windows list deserialization edge case
def _restore_layout(self):
    settings = QSettings("BluOptical", "BluSim")
    geom = settings.value("geometry")
    if geom is not None:
        self.restoreGeometry(geom)
    saved_tabs = settings.value("open_tabs")
    # Windows QSettings may return bare str for single-element lists
    if isinstance(saved_tabs, str):
        saved_tabs = [saved_tabs]
    if saved_tabs and isinstance(saved_tabs, list):
        panel_map = {title: widget for title, widget in self._get_openable_panels()}
        for title in saved_tabs:
            if title in panel_map and title not in self._tab_registry:
                closable = title not in ("3D View", "Heatmap")
                self._open_tab(title, panel_map[title], closable=closable)
        active = settings.value("active_tab")
        if active is not None:
            try:
                self._center_tabs.setCurrentIndex(int(active))
            except (ValueError, TypeError):
                pass
```

### Chromaticity Cloud in SpectralDataPanel
```python
# Source: spectral.py xy_per_pixel() + pg.ScatterPlotItem
def update_from_result(self, result) -> None:
    """Plot per-pixel simulation chromaticity on the CIE 1931 diagram."""
    from backlight_sim.sim.spectral import spectral_grid_to_xyz, spectral_bin_centers, xy_per_pixel
    import numpy as np

    # Remove previous simulation scatter
    if getattr(self, "_sim_scatter", None) is not None:
        self._chroma_plot.removeItem(self._sim_scatter)
        self._sim_scatter = None

    # Find first detector with spectral data
    grid_spectral = None
    for dr in result.detectors.values():
        if getattr(dr, "grid_spectral", None) is not None:
            grid_spectral = dr.grid_spectral
            break
    if grid_spectral is None:
        return

    try:
        n_bins = grid_spectral.shape[2]
        wl = spectral_bin_centers(n_bins)
        xyz = spectral_grid_to_xyz(grid_spectral, wl)          # (ny, nx, 3)
        xy = xy_per_pixel(xyz)                                  # (ny, nx, 2)
        luminance = xyz[..., 1]                                 # Y channel
        threshold = luminance.max() * 0.01
        mask = luminance > threshold
        xs = xy[..., 0][mask]
        ys = xy[..., 1][mask]
        if len(xs) == 0:
            return
        if len(xs) > 2000:
            idx = np.random.choice(len(xs), 2000, replace=False)
            xs, ys = xs[idx], ys[idx]
        scatter = pg.ScatterPlotItem(
            x=xs, y=ys, size=5,
            pen=pg.mkPen(None),
            brush=pg.mkBrush(80, 200, 120, 120),
        )
        self._chroma_plot.addItem(scatter)
        self._sim_scatter = scatter
        self._chroma_plot.setXRange(0.0, 0.85, padding=0.02)
        self._chroma_plot.setYRange(0.0, 0.92, padding=0.02)
    except Exception:
        pass
```

### Wire Spectral Panel Update in `_on_sim_finished` (main_window.py)
```python
def _on_sim_finished(self, result):
    self._progress.setVisible(False)
    self._run_btn.setEnabled(True)
    self._cancel_btn.setEnabled(False)
    self.statusBar().showMessage("Simulation complete.", 5000)
    self._heatmap.update_results(result)
    self._plot_tab.update_results(result)
    self._receiver_3d.update_results(result)
    self._spectral_panel.update_from_result(result)  # NEW: wire chromaticity scatter
    # ... rest unchanged ...
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Chromaticity shows only selected SPD coordinate | Chromaticity shows per-pixel simulation cloud + SPD coordinate | Phase 7 | SPEC-03 fully satisfied — user sees where simulation pixels land on CIE diagram |
| Live preview always shows intensity mode | Live preview honors spectral color mode when `grid_spectral` included in partial | Phase 7 | UI-08 fully satisfied for spectral simulations |
| Tab restore may silently fail on Windows single-item list | Explicit string coercion before list check | Phase 7 | UI-02 robustly satisfied |

**Current status of each gap (from code audit):**

| Gap | Audit Status | Current Code Status | Action Required |
|-----|-------------|---------------------|-----------------|
| UI-02 tab persistence | unsatisfied | `_save_layout`/`_restore_layout` implemented but Windows edge case bug | Fix `_restore_layout` string coercion |
| UI-06 duplicate action | partial | `_connect_signals` line 437 shows it IS connected; `_duplicate_object` fully implemented | Validate manually — may already be closed |
| SPEC-03 chromaticity scatter | gap found | `_on_sim_finished` has no call to spectral panel; `update_from_result` doesn't exist | Add method + wire call |
| Live preview spectral color | gap found | `grid_spectral` not copied in partial snapshot | Add `.copy()` in tracer partial snapshot |

---

## Open Questions

1. **UI-06 Duplicate Action — Already Fixed?**
   - What we know: `object_tree.py` line 50 defines `duplicate_requested` signal; main_window.py line 437 connects it; `_duplicate_object` is fully implemented at line 464.
   - What's unclear: Whether the Phase 5 audit was written before or after this was connected. The STATE.md entry "[Phase 05-03]: duplicate_requested signal defined in ObjectTree but wired by MainWindow (avoids Plan 02 conflict)" confirms the wiring was deferred — and the current code shows it is wired.
   - Recommendation: Add a quick manual validation step (right-click a source, select Duplicate, verify new source appears). If it works, UI-06 is already closed except for any documentation update. If not, investigate the signal connection.

2. **Tab Persistence — Exact Failure Mode**
   - What we know: Both `_save_layout` and `_restore_layout` are implemented. The audit says tabs reset on each launch.
   - What's unclear: Is the failure the Windows list deserialization bug, or is it that the active index restore conflicts with the order of pre-existing tabs?
   - Recommendation: Add a `print(settings.value("open_tabs"))` debug line temporarily to observe the actual deserialized type. Add the `isinstance(saved_tabs, str)` coercion as a defensive fix regardless.

3. **Chromaticity Scatter — Multiple Detectors**
   - What we know: Scenes can have multiple `DetectorSurface` objects; `update_from_result` will show only the first with spectral data.
   - What's unclear: Should all detectors be aggregated into one scatter, or shown for the currently selected detector only?
   - Recommendation: For Phase 7, show the first detector with spectral data — consistent with HeatmapPanel behavior which defaults to the first detector. A future enhancement could add a detector selector.

---

## Validation Architecture

> `workflow.nyquist_validation` is not set in `.planning/config.json` (no `nyquist_validation` key). Treating as false — skipping Validation Architecture section.

*Note: All four fixes are in GUI code (event handlers, display methods) that cannot be meaningfully unit-tested without a QApplication instance. Validation is manual: run the app, trigger each scenario, confirm the expected behavior. The existing 102 tests in `test_tracer.py` cover simulation correctness and should pass without modification.*

---

## Sources

### Primary (HIGH confidence)
- `G:/blu-optical-simulation/backlight_sim/gui/main_window.py` — Full source read; confirmed `_duplicate_object` connected at line 437, `_save_layout`/`_restore_layout` at lines 537–566, `_on_sim_finished` at line 1220 (no spectral panel call)
- `G:/blu-optical-simulation/backlight_sim/gui/object_tree.py` — Full source read; confirmed `duplicate_requested` signal defined at line 50, context menu action at lines 266–269
- `G:/blu-optical-simulation/backlight_sim/gui/spectral_data_panel.py` — Full source read; confirmed `_chroma_scatter` at line 205, `_update_chromaticity_for_spd` at line 250; no `update_from_result` public method exists
- `G:/blu-optical-simulation/backlight_sim/sim/tracer.py` — Partial read; confirmed partial snapshot at lines 946–962, `grid_spectral` NOT included in partial
- `G:/blu-optical-simulation/backlight_sim/sim/spectral.py` — Partial read; confirmed `spectral_grid_to_xyz` at line 268, `xy_per_pixel` at line 294, `spectral_bin_centers` at line 259
- `.planning/v1.0-MILESTONE-AUDIT.md` — Full read; confirmed 5 integration gaps and 4 broken E2E flows
- `.planning/REQUIREMENTS.md` — Full read; UI-02, UI-06, SPEC-03 confirmed as pending Phase 7

### Secondary (MEDIUM confidence)
- `G:/blu-optical-simulation/.planning/phases/05-ui-rewamp/05-RESEARCH.md` — Established QSettings, QTabWidget, and tab persistence patterns from Phase 5 research
- Qt documentation (from Phase 5 research) — `QSettings.value()` type behavior on Windows; `saveGeometry`/`restoreGeometry` API

### Tertiary (LOW confidence)
- None — all critical findings verified from source code

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all changes in existing files
- Architecture: HIGH — all computational primitives confirmed present in codebase (`xy_per_pixel`, `spectral_grid_to_xyz`, `spectral_bin_centers`); wiring pattern consistent with existing `_on_sim_finished` structure
- Pitfalls: HIGH for spectral scatter pitfalls (verified from code); MEDIUM for QSettings Windows behavior (platform-specific, not directly testable in current session)

**Research date:** 2026-03-15
**Valid until:** 2026-04-15 (all stable PySide6/pyqtgraph APIs; internal code structure is stable)
