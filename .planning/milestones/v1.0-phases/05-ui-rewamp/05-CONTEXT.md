# Phase 5: UI Revamp - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Comprehensive visual and workflow overhaul of the PySide6 desktop application. Modernize the look (dark theme, custom styling, icons) and improve usability (dockable panels, toolbar, undo/redo, streamlined workflows). No new simulation capabilities — purely UI/UX layer changes.

</domain>

<decisions>
## Implementation Decisions

### Visual Theme
- Dark mode only — no light mode toggle
- Sleek engineering tool aesthetic (Blender, Fusion 360, LightTools reference)
- Teal/cyan accent color on dark gray backgrounds — distinctive, matches scientific feel
- Borderless panel separators — use small gaps (2-3px) with slightly different background shade instead of visible borders
- Recessed/inset form inputs — darker than panel background with subtle inner shadow for editable affordance
- Icon + text labels for toolbar buttons and key actions — needs an icon set (Material Icons, Lucide, or similar)
- Custom Qt stylesheet (QSS) applied globally for consistent dark theme across all widgets

### Object Tree (Left Panel)
- Styled tree with per-type colored icons (source, surface, material, detector, solid body)
- Selected item highlighted with teal accent
- Expandable groups with subtle indentation

### Properties Panel (Right Side)
- Collapsible sections for property groups (Position, Orientation, Material, Optical, etc.)
- Section headers with expand/collapse arrows — user controls what's visible
- Reduces scrolling, follows Blender's properties panel pattern

### Layout & Navigation
- Full dockable panel system — panels can be dragged, docked, floated, tabbed, and rearranged
- 3D Viewport is the fixed central widget — always visible
- Heatmap, 3D Receiver, Plots, Angular Dist., Spectral Data all become dockable panels around the viewport
- Object tree and properties panel also dockable (default: tree left, properties right)
- Auto-save/restore layout between sessions using QSettings (window geometry + dock state)
- Top toolbar with icon buttons for common actions (New, Open, Save, Run Sim, Cancel, etc.)

### Workflow Streamlining
- Quick-add toolbar buttons for common objects (LED, Surface, Detector, SolidBox) — one-click add with sensible defaults, immediately selected for editing
- Right-click context menus in object tree — Add/Duplicate/Delete, context-aware (right-clicking 'Sources' group offers 'Add LED')
- No wizard — experienced users don't need hand-holding
- Full undo/redo system (Ctrl+Z / Ctrl+Y) using command stack pattern for all scene changes
- Essential keyboard shortcuts only: Ctrl+S save, Ctrl+Z undo, Ctrl+R run sim, Delete remove object
- Live heatmap preview during simulation — heatmap updates in real-time as rays accumulate

### Results Presentation
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

</decisions>

<specifics>
## Specific Ideas

- Engineering tool references: Blender, Fusion 360, LightTools, ANSYS — dense but organized, professional feel
- Teal/cyan accent is intentionally different from typical CAD blue — more distinctive and scientific
- Borderless panels with spacing gaps for a modern, less cluttered appearance
- Live heatmap preview during simulation — user sees the result forming progressively as rays accumulate

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `MainWindow._setup_ui()` (main_window.py:88): Current 3-pane QSplitter layout — will be replaced with QDockWidget-based layout
- `ObjectTree` (object_tree.py): QTreeWidget with 4 category groups — needs icon decoration and context menu additions
- `PropertiesPanel` (properties_panel.py): QStackedWidget with per-type forms — needs collapsible group refactor
- `HeatmapPanel` (heatmap_panel.py): pyqtgraph ImageItem + KPI grid — needs KPI card redesign and enhanced features
- `SimulationThread` (main_window.py:34): QThread with progress signal — needs to emit partial results for live preview

### Established Patterns
- All GUI panels follow `set_project(project)` pattern for data binding
- Signals/slots used throughout for cross-panel communication
- `_loading` guard + `blockSignals()` pattern in forms to prevent value-leak on selection changes
- `_refresh_timer` debounce (50ms) for coalescing rapid property edits

### Integration Points
- `MainWindow._setup_ui()`: Primary refactor target — QSplitter → QDockWidget layout
- `MainWindow._setup_menu()`: Add toolbar creation alongside menu setup
- `app.py`: Apply global QSS stylesheet before MainWindow creation
- `QSettings`: Qt's built-in persistence for window state and dock geometry
- `SimulationThread.progress` signal: Extend to emit partial DetectorResult for live preview

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-ui-rewamp*
*Context gathered: 2026-03-14*
