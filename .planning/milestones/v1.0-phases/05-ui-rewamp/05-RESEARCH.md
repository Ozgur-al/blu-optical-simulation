# Phase 5: UI Revamp - Research

**Researched:** 2026-03-14
**Domain:** PySide6 desktop application UI overhaul — dark theme, dockable panels, toolbar, undo/redo, live simulation preview
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Visual Theme:**
- Dark mode only — no light mode toggle
- Sleek engineering tool aesthetic (Blender, Fusion 360, LightTools reference)
- Teal/cyan accent color on dark gray backgrounds — distinctive, matches scientific feel
- Borderless panel separators — use small gaps (2-3px) with slightly different background shade instead of visible borders
- Recessed/inset form inputs — darker than panel background with subtle inner shadow for editable affordance
- Icon + text labels for toolbar buttons and key actions — needs an icon set (Material Icons, Lucide, or similar)
- Custom Qt stylesheet (QSS) applied globally for consistent dark theme across all widgets

**Object Tree (Left Panel):**
- Styled tree with per-type colored icons (source, surface, material, detector, solid body)
- Selected item highlighted with teal accent
- Expandable groups with subtle indentation

**Properties Panel (Right Side):**
- Collapsible sections for property groups (Position, Orientation, Material, Optical, etc.)
- Section headers with expand/collapse arrows — user controls what's visible
- Reduces scrolling, follows Blender's properties panel pattern

**Layout & Navigation:**
- Full dockable panel system — panels can be dragged, docked, floated, tabbed, and rearranged
- 3D Viewport is the fixed central widget — always visible
- Heatmap, 3D Receiver, Plots, Angular Dist., Spectral Data all become dockable panels around the viewport
- Object tree and properties panel also dockable (default: tree left, properties right)
- Auto-save/restore layout between sessions using QSettings (window geometry + dock state)
- Top toolbar with icon buttons for common actions (New, Open, Save, Run Sim, Cancel, etc.)

**Workflow Streamlining:**
- Quick-add toolbar buttons for common objects (LED, Surface, Detector, SolidBox) — one-click add with sensible defaults, immediately selected for editing
- Right-click context menus in object tree — Add/Duplicate/Delete, context-aware (right-clicking 'Sources' group offers 'Add LED')
- No wizard — experienced users don't need hand-holding
- Full undo/redo system (Ctrl+Z / Ctrl+Y) using command stack pattern for all scene changes
- Essential keyboard shortcuts only: Ctrl+S save, Ctrl+Z undo, Ctrl+R run sim, Delete remove object
- Live heatmap preview during simulation — heatmap updates in real-time as rays accumulate

**Results Presentation:**
- After simulation completes, automatically focus/show the heatmap dock panel with KPIs visible alongside
- KPI dashboard redesigned as hierarchical collapsible cards: 'Uniformity', 'Energy Balance', 'Error Metrics', 'Design Score' — each card shows 3-5 related KPIs with color-coded thresholds (green/yellow/red)
- Enhanced heatmap: selectable color maps (viridis, plasma, inferno, etc.), smooth interpolation option, crosshair cursor with live pixel values, restyled colorbar for dark theme
- ROI overlay restyled to match dark theme

### Claude's Discretion
- Exact dark theme color palette (background shades, text colors, hover/focus states)
- Icon set choice and specific icon assignments
- Default dock panel positions and sizes
- Typography choices (font family, sizes)
- Comparison view approach — whether to upgrade ComparisonDialog to a dockable panel with delta overlay, or simply restyle the existing dialog
- Animation/transition details for collapsible sections and dock operations
- How to structure the undo/redo command stack internally
- Plot styling for the analysis tab in the dark theme
- Spectral data panel restyling details

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

## Summary

Phase 5 is a pure UI/UX overhaul of the existing PySide6 desktop application. The simulation engine and data model are untouched — all changes live in `backlight_sim/gui/`, `app.py`, and a new `backlight_sim/gui/theme/` module. The dominant work is: (1) a global dark QSS stylesheet, (2) converting the existing `QSplitter + QTabWidget` layout to a `QDockWidget`-based dockable panel system with `QSettings` persistence, (3) adding a `QToolBar` above the central widget, (4) a `QUndoStack` command pattern for all scene mutations, (5) a collapsible-section refactor of `PropertiesPanel`, and (6) wiring the `SimulationThread` to emit a partial `DetectorResult` signal so `HeatmapPanel` can update live.

The existing codebase already imports `QDockWidget` (used for the Log panel) and has one QThread (`SimulationThread`) with a progress signal — both provide proven extension points. The `progress_callback` lambda pattern in `_run_single` is already in place; the live preview extension adds a second callback that emits partial grid snapshots. The `QUndoStack/QUndoCommand` pair lives in `PySide6.QtGui` (not QtWidgets — a common import mistake). `pyqtgraph` plot widgets need explicit `setBackground('#1e1e1e')` calls and `GLViewWidget.setBackgroundColor(r,g,b,a)` for the OpenGL viewport — QSS does not reach inside these widgets.

**Primary recommendation:** Hand-write a custom QSS file rather than using `qt-material` — it gives precise control over the teal accent palette, avoids a new dependency, and avoids the known pyqtgraph/PySide6 >6.7.2 dark-mode compatibility issue with external stylesheet libraries.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | already in requirements.txt | All widgets, QDockWidget, QToolBar, QUndoStack, QSettings | Already the project framework |
| pyqtgraph | already in requirements.txt | Plot/heatmap background theming, colormap selection | Already used for all plots |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PySide6.QtGui.QUndoStack | (bundled) | Undo/redo command stack | All scene mutations |
| PySide6.QtGui.QUndoCommand | (bundled) | Individual undoable commands | One subclass per action type |
| PySide6.QtCore.QSettings | (bundled) | Persist dock layout + geometry | closeEvent save, showEvent restore |
| PySide6.QtWidgets.QToolBar | (bundled) | Icon+text toolbar above viewport | Main window toolbar |
| PySide6.QtWidgets.QDockWidget | (bundled) | Dockable panels | All side panels |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-written QSS | qt-material 2.17 | qt-material provides dark_teal.xml out-of-box but adds a dependency and has known pyqtgraph dark-mode conflicts with PySide6 >6.7.2; hand-written QSS avoids both issues |
| Hand-written QSS | qdarktheme / PyQtDarkTheme | Similar tradeoffs; last major update 2023; maintenance uncertain |
| QUndoStack | Custom history list | Qt's undo framework auto-wires menu actions (createUndoAction/createRedoAction), handles command merging, and is the established Qt pattern |
| QDockWidget panels | QSplitter tabs (current) | QSplitter doesn't support float/detach; QTabWidget doesn't support side-by-side placement |

**Installation:**
```bash
# No new packages required — all needed classes are in PySide6 (already installed)
```

---

## Architecture Patterns

### Recommended Project Structure
```
backlight_sim/
├── gui/
│   ├── theme/
│   │   ├── __init__.py          # apply_dark_theme(app), PALETTE constants
│   │   └── dark.qss             # Global QSS stylesheet
│   ├── commands/
│   │   ├── __init__.py          # UndoStack singleton accessor
│   │   ├── base.py              # ProjectCommand base (holds project ref)
│   │   ├── source_commands.py   # AddSource, DeleteSource, SetSourceProperty
│   │   ├── surface_commands.py  # AddSurface, DeleteSurface, SetSurfaceProperty
│   │   └── scene_commands.py    # BatchAdd, SetSimSettings
│   ├── widgets/
│   │   └── collapsible_section.py  # CollapsibleSection widget (header + content)
│   ├── main_window.py           # QDockWidget layout, toolbar, QSettings save/restore
│   ├── object_tree.py           # Icon decoration + context menus
│   ├── properties_panel.py      # Collapsible section refactor
│   └── heatmap_panel.py         # Colormap selector, live preview slot
```

### Pattern 1: QDockWidget Panel System

**What:** Replace the QSplitter + QTabWidget center layout with `Viewport3D` as the fixed central widget and all side panels as QDockWidgets.

**When to use:** Any panel that users may want to resize, float, or reorganize.

**Example:**
```python
# Source: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QDockWidget.html
# In MainWindow._setup_ui():

self._viewport = Viewport3D()
self.setCentralWidget(self._viewport)  # always visible, never dockable

# Create dockable panels
self._tree_dock = QDockWidget("Scene")
self._tree_dock.setObjectName("scene_dock")  # REQUIRED for saveState/restoreState
self._tree_dock.setWidget(self._tree)
self._tree_dock.setAllowedAreas(
    Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
)
self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._tree_dock)

self._props_dock = QDockWidget("Properties")
self._props_dock.setObjectName("properties_dock")
self._props_dock.setWidget(self._properties)
self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._props_dock)

self._heatmap_dock = QDockWidget("Heatmap")
self._heatmap_dock.setObjectName("heatmap_dock")
self._heatmap_dock.setWidget(self._heatmap)
self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._heatmap_dock)
```

**Critical requirement:** Every `QDockWidget` MUST have a unique `objectName` set before `saveState()` is called — Qt uses these names as keys when serializing layout. If `objectName` is empty, `restoreState()` silently ignores that dock.

### Pattern 2: QSettings Layout Persistence

**What:** Save and restore full dock geometry on close/open.

**Example:**
```python
# Source: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QMainWindow.html

def _save_layout(self):
    settings = QSettings("BluOptical", "BluSim")
    settings.setValue("geometry", self.saveGeometry())
    settings.setValue("windowState", self.saveState())

def _restore_layout(self):
    settings = QSettings("BluOptical", "BluSim")
    geom = settings.value("geometry")
    state = settings.value("windowState")
    if geom:
        self.restoreGeometry(geom)
    if state:
        self.restoreState(state)

def closeEvent(self, event):
    self._save_layout()
    # ... existing close logic
    super().closeEvent(event)
```

Call `_restore_layout()` at the end of `__init__` after all docks are created.

### Pattern 3: QUndoStack Command Pattern

**What:** Every scene mutation becomes a `QUndoCommand` subclass pushed onto a shared stack.

**Key import:** `from PySide6.QtGui import QUndoStack, QUndoCommand` (NOT `QtWidgets`).

**Example:**
```python
# Source: https://doc.qt.io/qtforpython-6/PySide6/QtGui/QUndoStack.html

class AddSourceCommand(QUndoCommand):
    def __init__(self, project, source, refresh_fn):
        super().__init__(f"Add {source.name}")
        self._project = project
        self._source = source
        self._refresh = refresh_fn

    def redo(self):
        self._project.sources.append(self._source)
        self._refresh()

    def undo(self):
        self._project.sources = [s for s in self._project.sources
                                  if s.name != self._source.name]
        self._refresh()


class SetPropertyCommand(QUndoCommand):
    def __init__(self, target_obj, attr, old_val, new_val, refresh_fn):
        super().__init__(f"Set {attr}")
        self._obj = target_obj
        self._attr = attr
        self._old = old_val
        self._new = new_val
        self._refresh = refresh_fn

    def redo(self):
        setattr(self._obj, self._attr, self._new)
        self._refresh()

    def undo(self):
        setattr(self._obj, self._attr, self._old)
        self._refresh()

    def id(self):
        return hash((id(self._obj), self._attr))  # enables mergeWith compression

    def mergeWith(self, other):
        if other.id() != self.id():
            return False
        self._new = other._new  # collapse rapid edits into single undo step
        return True
```

Wire into MainWindow:
```python
self._undo_stack = QUndoStack(self)
undo_action = self._undo_stack.createUndoAction(self, "Undo")
undo_action.setShortcut(QKeySequence.StandardKey.Undo)
redo_action = self._undo_stack.createRedoAction(self, "Redo")
redo_action.setShortcut(QKeySequence("Ctrl+Y"))
edit_menu.addAction(undo_action)
edit_menu.addAction(redo_action)
```

`push()` automatically calls `redo()` on the new command — do not call `redo()` manually before pushing.

### Pattern 4: Global Dark QSS Stylesheet

**What:** Single `.qss` file loaded at app startup, applied to `QApplication`.

**Example (app.py):**
```python
# Apply before MainWindow creation
from backlight_sim.gui.theme import apply_dark_theme
app = QApplication(sys.argv)
apply_dark_theme(app)
window = MainWindow()
```

**Example (theme/__init__.py):**
```python
import os
from PySide6.QtWidgets import QApplication

def apply_dark_theme(app: QApplication):
    qss_path = os.path.join(os.path.dirname(__file__), "dark.qss")
    with open(qss_path, "r") as f:
        app.setStyleSheet(f.read())
```

**Recommended palette constants (in theme/__init__.py):**
```python
BG_BASE      = "#1e1e1e"   # main window background
BG_PANEL     = "#252525"   # dock panel background
BG_INPUT     = "#181818"   # recessed input fields
BG_HOVER     = "#2d2d2d"   # hover state
ACCENT       = "#00bcd4"   # teal/cyan (Material Design Cyan 500)
ACCENT_HOVER = "#26c6da"   # lighter teal for hover
TEXT_PRIMARY = "#e0e0e0"
TEXT_MUTED   = "#888888"
BORDER_GAP   = 2           # px gap between panels (not a visible border)
```

**Key QSS coverage needed:**
- `QMainWindow`, `QDockWidget`, `QDockWidget::title`
- `QTreeWidget`, `QTreeWidget::item:selected`
- `QScrollArea`, `QScrollBar`
- `QGroupBox` (for collapsible section headers)
- `QLineEdit`, `QDoubleSpinBox`, `QSpinBox`, `QComboBox` (recessed input style)
- `QPushButton` (normal and accent variants)
- `QStatusBar`, `QMenuBar`, `QMenu`
- `QToolBar`, `QToolButton`
- `QTabBar`, `QTabWidget` (for any remaining tab uses)
- `QSplitter::handle`

**pyqtgraph widgets CANNOT be styled via QSS** — they have their own rendering pipeline. Style them programmatically:
```python
# PlotWidget backgrounds
plot_widget.setBackground('#1e1e1e')
plot_widget.getAxis('bottom').setPen(pg.mkPen('#888888'))
plot_widget.getAxis('left').setPen(pg.mkPen('#888888'))

# GLViewWidget (3D viewport)
self._viewport.setBackgroundColor(30, 30, 30, 255)  # r,g,b,a as ints
```

### Pattern 5: QToolBar with Icon + Text

**What:** Top toolbar with icon buttons for the most common actions.

**Example:**
```python
# Source: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QToolBar.html
toolbar = QToolBar("Main")
toolbar.setObjectName("main_toolbar")  # required for saveState
toolbar.setIconSize(QSize(20, 20))
toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

# Reuse existing menu actions (avoids duplicating signal wiring):
toolbar.addAction(self._new_action)
toolbar.addAction(self._open_action)
toolbar.addAction(self._save_action)
toolbar.addSeparator()
toolbar.addAction(self._run_action)
toolbar.addAction(self._cancel_action)
```

**Icon strategy:** Use `QIcon.fromTheme()` for standard OS icons with a bundled SVG fallback. For a consistent cross-platform look, bundle a small set of SVG icons in `backlight_sim/gui/theme/icons/`. Material Design Icons (MDI) provides free SVGs under Apache 2.0 — source the specific icons needed (no full library install required).

### Pattern 6: Collapsible Section Widget

**What:** A reusable header + expandable content widget for PropertiesPanel sections.

**Implementation approach:** Custom widget — hand-roll it. It is simple (~50 lines) and existing libraries add dependencies without significant benefit.

```python
# backlight_sim/gui/widgets/collapsible_section.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QToolButton, QFrame
from PySide6.QtCore import Qt

class CollapsibleSection(QWidget):
    def __init__(self, title: str, parent=None, collapsed: bool = False):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._toggle = QToolButton()
        self._toggle.setText(title)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(not collapsed)
        self._toggle.setArrowType(Qt.ArrowType.DownArrow if not collapsed else Qt.ArrowType.RightArrow)
        self._toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._toggle.toggled.connect(self._on_toggle)
        layout.addWidget(self._toggle)

        self._content = QFrame()
        self._content.setVisible(not collapsed)
        self._content_layout = QVBoxLayout(self._content)
        layout.addWidget(self._content)

    def _on_toggle(self, checked: bool):
        self._content.setVisible(checked)
        self._toggle.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )

    def addWidget(self, widget):
        self._content_layout.addWidget(widget)

    def addLayout(self, layout):
        self._content_layout.addLayout(layout)
```

### Pattern 7: Live Heatmap Preview

**What:** Extend `SimulationThread` to emit partial `DetectorResult` snapshots at regular intervals during the bounce loop.

**Approach:** Add a `partial_result` signal to `SimulationThread`. The tracer's `_run_single` already accepts `progress_callback` — add a second callback `partial_result_callback` that fires every N% progress. The callback snapshots the current in-progress detector grids and emits them.

**Example signal addition to SimulationThread:**
```python
class SimulationThread(QThread):
    progress       = Signal(float)
    convergence    = Signal(int, int, float)
    partial_result = Signal(object)   # SimulationResult snapshot (deep copy)
    finished_sim   = Signal(object)

    def run(self):
        result = self.tracer.run(
            progress_callback=self.progress.emit,
            convergence_callback=self.convergence.emit,
            partial_result_callback=self.partial_result.emit,
        )
        self.finished_sim.emit(result)
```

In `MainWindow._run_simulation()`:
```python
self._sim_thread.partial_result.connect(self._on_partial_result)

def _on_partial_result(self, result):
    self._heatmap.update_results(result)
```

**Tracer change:** In `_run_single`, track a `last_emit_progress` float; when `progress` crosses a 5% threshold, emit a lightweight snapshot via the callback. Use `copy.copy` (shallow) for the grid arrays — full `deepcopy` is too expensive at 5% intervals.

**Frequency:** Emit at 5% intervals (every ~5% of total bounce-ray budget). This gives ~20 preview updates without measurable performance impact.

### Pattern 8: Enhanced Heatmap Colormap Selector

**What:** `QComboBox` in the HeatmapPanel toolbar to switch between colormaps.

```python
# Source: https://pyqtgraph.readthedocs.io/en/latest/api_reference/colormap.html
COLORMAPS = ['viridis', 'plasma', 'inferno', 'magma', 'CET-L1', 'CET-D1']

self._colormap_combo = QComboBox()
self._colormap_combo.addItems(COLORMAPS)
self._colormap_combo.currentTextChanged.connect(self._apply_colormap)

def _apply_colormap(self, name: str):
    cm = pg.colormap.get(name)
    self._img_item.setColorMap(cm)
    self._colorbar.setColorMap(cm)
```

**Note:** `pg.colormap.get('viridis')` works without matplotlib installed — pyqtgraph bundles its own perceptually-uniform maps including viridis/plasma/inferno/magma. [HIGH confidence — verified from official pyqtgraph docs]

### Anti-Patterns to Avoid

- **Not setting `objectName` on docks:** `saveState/restoreState` silently fails — layouts do not persist between sessions.
- **Applying global QSS before pyqtgraph widgets exist:** Some pg widgets read palette at construction. Apply QSS first (in `app.py`), then construct `MainWindow`. Also call `pg.setConfigOption('background', '#1e1e1e')` and `pg.setConfigOption('foreground', '#e0e0e0')` before any widget construction.
- **Using `pg.setConfigOptions` for background:** The correct call is `pg.setConfigOption` (singular). Using the plural form is a silently-ignored typo.
- **Calling `setBackgroundColor` on GLViewWidget with string colors:** `GLViewWidget.setBackgroundColor('k')` does not work reliably. Use `setBackgroundColor(30, 30, 30, 255)` (int RGBA).
- **Importing QUndoStack from QtWidgets:** It moved to `PySide6.QtGui` in Qt6. `from PySide6.QtWidgets import QUndoStack` will raise `ImportError`.
- **Wrapping `addAction` in a lambda for toolbar:** When an `addAction(icon, text)` call is used directly on the toolbar (not re-using an existing QAction), the toolbar creates a new action not linked to menu actions. Reuse the QAction objects from menu setup to avoid duplicating signal wiring.
- **Calling `redo()` before `push()`:** `QUndoStack.push(cmd)` automatically calls `cmd.redo()`. Calling it manually first means the action executes twice.
- **Deep copying grids on every partial result emit:** Use shallow copy of the numpy array (`grid.copy()` — a new array but not full project copy) for live preview snapshots. Full `deepcopy` of `SimulationResult` is prohibitive at 5% intervals.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Undo/redo stack | Custom deque of lambdas | `QUndoStack + QUndoCommand` | Auto-creates menu actions, handles merge/compression, is the established Qt pattern with 0 extra dependencies |
| Layout persistence | Manual JSON of dock positions | `QMainWindow.saveState() / restoreState() + QSettings` | Handles float/tabbed/nested dock states; custom solutions miss edge cases |
| Colormap rendering | Custom color interpolation | `pg.colormap.get()` | pyqtgraph bundles viridis/plasma/inferno/magma natively |
| Collapsible section | 3rd-party package | Hand-rolled `CollapsibleSection` (~50 lines) | Simple enough to own; avoids dependency for 50 lines of code |
| Dark theme library | `qt-material`, `qdarktheme` | Hand-written `dark.qss` | Single file, full palette control, no pyqtgraph compatibility issues |

**Key insight:** Qt already provides the undo/redo framework and layout persistence — using them is both less work and more correct than custom implementations.

---

## Common Pitfalls

### Pitfall 1: QSS Does Not Style pyqtgraph Widgets
**What goes wrong:** Dark QSS is applied globally but plot backgrounds stay white/light. The `QStatusBar` looks dark, the menus look dark, but all plots remain bright.
**Why it happens:** pyqtgraph widgets render via their own OpenGL/QPainter pipeline. Qt stylesheets have no effect on them.
**How to avoid:** After `apply_dark_theme(app)`, call `pg.setConfigOption('background', '#1e1e1e')` and `pg.setConfigOption('foreground', '#e0e0e0')` BEFORE constructing any pyqtgraph widget. For the `GLViewWidget` (3D viewport), additionally call `viewport.setBackgroundColor(30, 30, 30, 255)` inside `Viewport3D.__init__`.
**Warning signs:** White plot backgrounds after applying QSS.

### Pitfall 2: Missing objectName Breaks Layout Persistence
**What goes wrong:** Users rearrange panels, restart the app, and panels snap back to defaults.
**Why it happens:** `QMainWindow.saveState()` uses `objectName` as the key for each dock and toolbar. An empty name causes silent skip.
**How to avoid:** Call `dock.setObjectName("unique_name")` for every `QDockWidget` and every `QToolBar` before `addDockWidget` / `addToolBar`. Names must be unique within the window.
**Warning signs:** `restoreState()` returns `True` but layout doesn't restore.

### Pitfall 3: QUndoStack Import Location (Qt6 vs Qt5)
**What goes wrong:** `from PySide6.QtWidgets import QUndoStack, QUndoCommand` raises `ImportError`.
**Why it happens:** In Qt6, `QUndoStack` and `QUndoCommand` moved from `QtWidgets` to `QtGui`.
**How to avoid:** Always use `from PySide6.QtGui import QUndoStack, QUndoCommand`.
**Warning signs:** `ImportError: cannot import name 'QUndoStack' from 'PySide6.QtWidgets'`.

### Pitfall 4: Undo Commands Holding Stale Project References
**What goes wrong:** Undoing "Add Source" after a "New Project" crashes or silently corrupts the new project.
**Why it happens:** Commands hold a direct reference to the `Project` object. When `_new_project()` replaces `self._project`, old commands still point to the old instance.
**How to avoid:** Clear the undo stack whenever the project is replaced (`self._undo_stack.clear()`). Call this in `_new_project()`, `_open_project()`, `_load_preset()`, and `_load_variant()`.
**Warning signs:** Ctrl+Z after opening a new project modifies an orphaned project object.

### Pitfall 5: Live Preview Emit Frequency Too High
**What goes wrong:** HeatmapPanel updates 1000 times during a simulation, causing UI jank and actually slowing the simulation due to GIL contention from Qt signal delivery.
**Why it happens:** Emitting on every source-batch completion in a scene with many sources.
**How to avoid:** Emit partial results at 5% progress intervals (throttled by `last_emit_progress` float in `_run_single`). The `QTimer` debounce pattern already in `MainWindow` can also be applied on the receive side.
**Warning signs:** Simulation runs slower with live preview enabled; UI freezes briefly on each update.

### Pitfall 6: Dock Tab vs Side-by-Side Layout on Restore
**What goes wrong:** User has heatmap and properties side-by-side; after restart they appear as tabs.
**Why it happens:** Default `restoreState()` is correct, but if dock widgets are created after `restoreState()` is called, they appear in default positions.
**How to avoid:** Create ALL dock widgets before calling `_restore_layout()`. The order is: create widgets → create docks → set default positions → call `restoreState()` last.
**Warning signs:** Non-deterministic dock positions after restart.

### Pitfall 7: QSS QDoubleSpinBox Arrow Buttons
**What goes wrong:** Dark QSS makes spinbox arrow buttons invisible (dark arrows on dark background).
**Why it happens:** Platform-default spinbox arrows are rendered in a color that disappears against dark backgrounds.
**How to avoid:** Include explicit QSS rules for `QDoubleSpinBox::up-button`, `QDoubleSpinBox::down-button`, `QDoubleSpinBox::up-arrow`, `QDoubleSpinBox::down-arrow` using border-image or color overrides.
**Warning signs:** Users cannot click up/down on number inputs.

---

## Code Examples

### Global pyqtgraph Dark Config (app.py, before any widget)
```python
# Source: pyqtgraph official docs
import pyqtgraph as pg
pg.setConfigOption('background', '#1e1e1e')
pg.setConfigOption('foreground', '#e0e0e0')
pg.setConfigOption('antialias', True)
```

### Saving/Restoring Layout
```python
# Source: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QMainWindow.html
from PySide6.QtCore import QSettings

def _save_layout(self):
    s = QSettings("BluOptical", "BluSim")
    s.setValue("geometry", self.saveGeometry())
    s.setValue("windowState", self.saveState())

def _restore_layout(self):
    s = QSettings("BluOptical", "BluSim")
    if (g := s.value("geometry")):
        self.restoreGeometry(g)
    if (w := s.value("windowState")):
        self.restoreState(w)
```

### Colormap Integration
```python
# Source: https://pyqtgraph.readthedocs.io/en/latest/api_reference/colormap.html
import pyqtgraph as pg

cm = pg.colormap.get('viridis')
self._img_item.setColorMap(cm)
# ColorBarItem update:
self._colorbar.setColorMap(cm)
```

### QDockWidget with objectName
```python
# Source: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QDockWidget.html
from PySide6.QtWidgets import QDockWidget
from PySide6.QtCore import Qt

dock = QDockWidget("Heatmap")
dock.setObjectName("heatmap_dock")   # mandatory for saveState
dock.setWidget(self._heatmap)
dock.setFeatures(
    QDockWidget.DockWidgetFeature.DockWidgetMovable |
    QDockWidget.DockWidgetFeature.DockWidgetFloatable |
    QDockWidget.DockWidgetFeature.DockWidgetClosable
)
self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
```

### KPI Color-Coded Threshold Labels
```python
# Pattern for green/yellow/red threshold coloring in KPI cards
def _threshold_style(value: float, green: float, yellow: float) -> str:
    """Returns QSS color string for value vs thresholds (higher is better)."""
    if value >= green:
        return "color: #4caf50;"   # green
    elif value >= yellow:
        return "color: #ff9800;"   # orange
    else:
        return "color: #f44336;"   # red

label.setStyleSheet(_threshold_style(uniformity, 0.80, 0.60))
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| QSplitter + QTabWidget for panels | QDockWidget system | Phase 5 | Panels become user-rearrangeable, floatable, persistable |
| No persistent layout | QSettings saveState/restoreState | Phase 5 | Layout survives app restart |
| _add_object / _delete_object directly | QUndoCommand push to stack | Phase 5 | Ctrl+Z/Y works for all scene changes |
| progress_callback only | progress_callback + partial_result_callback | Phase 5 | Heatmap updates live during simulation |
| System-default Qt style | Custom dark.qss + pg.setConfigOption | Phase 5 | Engineering tool aesthetic throughout |
| Flat KPI grid in HeatmapPanel | Collapsible KPI cards with color thresholds | Phase 5 | Cleaner results view |

---

## Open Questions

1. **Undo scope for batch operations (geometry builder, presets)**
   - What we know: Geometry Builder and preset loading replace large portions of the project in one step.
   - What's unclear: Should each geometry builder output be one undo step (single macro command) or undoable at granular field level?
   - Recommendation: Use `QUndoStack.beginMacro/endMacro` to wrap geometry builder output as a single named undo step (e.g., "Build Cavity"). This is one undoable step that restores the previous full scene.

2. **Icon source and bundling**
   - What we know: Material Design Icons (MDI) is Apache 2.0, has SVGs for all needed actions (new_file, folder_open, save, play_arrow, cancel, add, delete, etc.). No full library install is needed — individual SVG files can be copied into `gui/theme/icons/`.
   - What's unclear: Exact icon naming/selection.
   - Recommendation: Bundle 15-20 individual SVG files directly in `gui/theme/icons/`. Use `QIcon(os.path.join(ICONS_DIR, "play_arrow.svg"))` pattern.

3. **Performance of live preview with multiprocessing enabled**
   - What we know: When `use_multiprocessing` is `True`, `_run_multiprocess` is used, which runs per-source in subprocesses. Partial result callbacks cannot cross process boundaries.
   - What's unclear: Whether live preview should be disabled when MP is enabled, or if an inter-process progress mechanism should be built.
   - Recommendation: Disable live preview (skip `partial_result` emits) when `use_multiprocessing` is True. The existing MP guard pattern in the tracer makes this a one-line check. Document the limitation in the status bar ("Live preview disabled in multiprocessing mode").

---

## Sources

### Primary (HIGH confidence)
- https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QMainWindow.html — saveState/restoreState API, addDockWidget, setCentralWidget
- https://doc.qt.io/qtforpython-6/PySide6/QtGui/QUndoStack.html — push, undo, redo, createUndoAction, createRedoAction API
- https://doc.qt.io/qtforpython-6/PySide6/QtGui/QUndoCommand.html — redo/undo interface, mergeWith, id()
- https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QDockWidget.html — dock creation, objectName requirement
- https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QToolBar.html — setToolButtonStyle, setIconSize, addAction
- https://pyqtgraph.readthedocs.io/en/latest/api_reference/colormap.html — pg.colormap.get(), available maps, ImageItem.setColorMap()
- https://doc.qt.io/qtforpython-6/examples/example_widgets_mainwindows_dockwidgets.html — dock widget creation pattern

### Secondary (MEDIUM confidence)
- https://pypi.org/project/qt-material/ — version 2.17 (April 2025), PySide6 support confirmed, dark_teal.xml theme available; not used but evaluated
- https://github.com/pyqtgraph/pyqtgraph/issues/2175 — GLViewWidget.setBackgroundColor(r,g,b,a) int-tuple form required for dark backgrounds
- https://github.com/pyqtgraph/pyqtgraph/issues/3143 — dark/light mode compatibility issue with PySide6 >6.7.2 when using external stylesheet libraries

### Tertiary (LOW confidence)
- WebSearch results on collapsible section widgets — pattern is straightforward enough to hand-roll; external library evaluations (qt-collapsible-section-pyside6, collapsiblepane) reviewed but not adopted

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in use; no new dependencies needed
- Architecture: HIGH — verified from official Qt for Python docs; QDockWidget/QUndoStack/QSettings APIs are stable Qt6 APIs
- Pitfalls: HIGH (QSS/pyqtgraph split, objectName requirement) — verified from official sources and GitHub issues; MEDIUM (performance of live preview) — based on general threading knowledge

**Research date:** 2026-03-14
**Valid until:** 2026-04-14 (stable APIs — Qt6 APIs are stable; pyqtgraph colormap API is stable)
