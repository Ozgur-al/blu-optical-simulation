# Phase 1: Distribution & Splash Screen - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the app distributable and runnable on admin-locked work computers (no admin rights, local folder execution), add a polished splash screen with progress feedback, and add app icon/branding. Portable zip distribution format (already exists) is refined with branding, README, and sample files.

</domain>

<decisions>
## Implementation Decisions

### Splash screen
- Logo + progress bar on startup
- Show version number + status text that updates: "Loading modules...", "Initializing GUI...", "Ready"
- Dark background (#1e1e1e) with teal accents (#00bcd4) — match existing app dark theme
- Styled text logo ("Blu Optical Simulation" rendered programmatically) — no separate graphic image file
- Splash disappears when main window is ready

### App icon & branding
- Optics/light theme icon — stylized light rays, lens, or optical simulation motif
- Teal graphic on transparent background — adapts to light/dark OS themes
- Icon set everywhere: window title bar, taskbar, and .exe file
- Icon creation method: Claude's discretion

### Distribution format
- Portable zip (keep current approach): BluOpticalSim.exe + _internal/ folder, extract anywhere, run
- Include README.txt (how to run, requirements, SmartScreen bypass instructions) + sample .blu project file(s)
- Version check on startup: app checks for new versions and notifies user (no auto-install)
- Update check source: Claude's discretion (consider that corporate networks may block GitHub — a simple JSON endpoint may be more reliable)

### Locked PC compatibility
- Target scenario: no admin rights, run from local folder (Desktop, Documents)
- User data (settings, preferences) stored in %LOCALAPPDATA%\BluOpticalSim\
- Ship unsigned — accept SmartScreen warning; README documents how to bypass ("More info" → "Run anyway")
- Bundle all runtime dependencies (VC++ runtime, OpenGL DLLs) — nothing external required
- Corporate proxy/firewall may block update check HTTP requests — must fail gracefully (timeout, no crash, no blocking UI)

### Claude's Discretion
- Icon creation method (SVG→ICO pipeline vs QPainter-rendered vs other)
- Update check implementation (GitHub Releases API vs simple JSON endpoint vs other)
- Exact splash screen font, sizing, and progress bar styling
- How to bundle VC++ redistributable DLLs with PyInstaller
- Sample project file selection (which presets to include)

</decisions>

<specifics>
## Specific Ideas

- Progress bar should show meaningful status text, not just a spinning indicator — users want to know the app is actually loading
- SmartScreen bypass instructions in README are important since this targets corporate users who may be alarmed by the warning
- Update check must be completely non-blocking and proxy-tolerant — corporate firewalls are a known constraint

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `build_exe.py` + `BluOpticalSim.spec`: PyInstaller build pipeline already exists, one-folder mode, icon line commented out ready to enable
- `backlight_sim/gui/theme/__init__.py`: Dark theme palette constants (BG_BASE, ACCENT, TEXT_PRIMARY etc.) — splash should import these
- `io/presets.py`: Built-in preset factories (Simple Box, Automotive Cluster) — can generate sample .blu files for the zip

### Established Patterns
- Dark theme (#1e1e1e bg, #00bcd4 teal accent) used consistently across all GUI panels
- `app.py` entry point: sets up QApplication, applies theme, then imports MainWindow — splash should intercept between theme apply and MainWindow construction
- PyInstaller spec already handles hidden imports (PySide6, pyqtgraph, OpenGL, Numba), data files, and excludes

### Integration Points
- Splash screen inserts between `QApplication()` creation and `MainWindow()` construction in `app.py`
- Icon .ico file referenced in `BluOpticalSim.spec` (line 120, currently commented out) and set via `app.setWindowIcon()` in `app.py`
- User data directory: new code to determine `%LOCALAPPDATA%\BluOpticalSim\` path, used by settings/preferences (currently no centralized config path)
- Version check: new module, called during or after splash, with timeout/proxy handling

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-distribution-for-admin-locked-work-computer-compatibility-splash-screen-etc*
*Context gathered: 2026-03-16*
