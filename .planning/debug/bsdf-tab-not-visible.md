---
status: resolved
trigger: "Investigate why the BSDF panel tab is not visible in the center tab area of the application."
created: 2026-03-15T00:00:00Z
updated: 2026-03-15T00:01:00Z
---

## Current Focus

hypothesis: CONFIRMED — BSDFPanel is added to a hidden QDockWidget, not to a center QTabWidget
test: Grep for all addTab / tabifyDockWidget / _bsdf_ references in main_window.py
expecting: BSDF placed in dock that is hidden by default
next_action: Return diagnosis

## Symptoms

expected: A "BSDF" tab visible in the center tab area of the application
actual: The BSDF tab is absent from the center tab widget
errors: none reported
reproduction: Launch the application and observe the center tab area
started: Plan 04-04 was supposed to add it but tab is missing

## Eliminated

- hypothesis: BSDFPanel class does not exist or is not properly defined
  evidence: backlight_sim/gui/bsdf_panel.py exists; BSDFPanel is a complete QWidget subclass
  timestamp: 2026-03-15T00:01:00Z

- hypothesis: BSDFPanel is not imported in main_window.py
  evidence: Line 28 of main_window.py: `from backlight_sim.gui.bsdf_panel import BSDFPanel` — import is present
  timestamp: 2026-03-15T00:01:00Z

- hypothesis: BSDFPanel is never instantiated
  evidence: Line 135: `self._bsdf_panel = BSDFPanel()` — instantiated and wired to project
  timestamp: 2026-03-15T00:01:00Z

## Evidence

- timestamp: 2026-03-15T00:01:00Z
  checked: main_window.py lines 163–190 (_setup_ui)
  found: There is NO center QTabWidget anywhere. The "center" is a single Viewport3D set via setCentralWidget (line 117). All panels — Heatmap, Far-field, Plots, Angular Dist., Spectral Data, and BSDF — are QDockWidgets tabified in the RightDockWidgetArea via tabifyDockWidget calls (lines 178–183).
  implication: The plan's description of a "center tab widget" does not match the actual architecture; center = viewport only.

- timestamp: 2026-03-15T00:01:00Z
  checked: main_window.py lines 188–191 (_floating_docks)
  found: `self._floating_docks = {self._farfield_dock, self._receiver3d_dock, self._spectral_dock, self._bsdf_dock}` — all four are immediately hidden after being tabified (line 191: `dock.hide()`).
  implication: _bsdf_dock is correctly registered in the tabified right-panel group but is hidden by default. It does not appear in the visible dock tab bar at startup.

- timestamp: 2026-03-15T00:01:00Z
  checked: View > Panels menu (lines 331–335)
  found: _bsdf_dock is listed in the Panels menu, so it CAN be toggled visible, but it starts hidden.
  implication: The tab is accessible to users who know to look in View > Panels, but it is not visible by default.

## Resolution

root_cause: |
  The application has no center QTabWidget. The center widget is permanently the 3D Viewport3D. All analysis panels (Heatmap, Plots, Angular Dist., Spectral Data, BSDF) live as QDockWidgets tabified in the RightDockWidgetArea.

  The BSDF dock (self._bsdf_dock) IS correctly wired into the tabified group at line 183 (`tabifyDockWidget(self._spectral_dock, self._bsdf_dock)`), but it is immediately placed into `self._floating_docks` and hidden (lines 189–192). It is therefore invisible at startup.

  The fix is to remove _bsdf_dock from `self._floating_docks` so it is visible in the dock tab bar by default, just like _heatmap_dock, _plots_dock, and _angdist_dock.

fix: |
  In main_window.py line 189–190, remove self._bsdf_dock from the _floating_docks set:
    Before: self._floating_docks = {self._farfield_dock, self._receiver3d_dock, self._spectral_dock, self._bsdf_dock}
    After:  self._floating_docks = {self._farfield_dock, self._receiver3d_dock, self._spectral_dock}

  Also update _reset_layout (line 444–446) to match: remove self._bsdf_dock from that same set.

verification: After the change, BSDF appears as a visible tab next to Spectral Data in the right dock tab bar.
files_changed:
  - backlight_sim/gui/main_window.py
