---
status: complete
phase: 01-distribution-for-admin-locked-work-computer-compatibility-splash-screen-etc
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md]
started: 2026-03-16T00:00:00Z
updated: 2026-04-17T23:55:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Splash Screen on Startup
expected: Run `python app.py`. A dark frameless splash screen (480x280) appears immediately showing "Blu Optical Simulation" in teal, a subtitle, a slim progress bar that advances through loading stages, a status label ("Loading modules...", "Initializing GUI...", "Ready"), and version "2.0.0" in the corner.
result: pass

### 2. Splash Dismissal and Main Window Load
expected: After the splash progress bar reaches 100%, the splash fades out smoothly (~300ms) and the main window appears fully loaded with all panels (object tree, 3D viewport, properties panel).
result: pass

### 3. App Icon in Title Bar and Taskbar
expected: The main window title bar and Windows taskbar both show the teal optics-motif icon (LED + rays + lens arc) instead of a generic Python/Qt icon.
result: pass
note: "Fixed in-session — added Windows AppUserModelID via ctypes and explicit MainWindow.setWindowIcon() in app.py"

### 4. Update Checker — Graceful Offline Behavior
expected: With no internet or behind a corporate firewall, `python app.py` starts normally without any error, crash, or visible delay. The update check fails silently in the background.
result: pass

### 5. PyInstaller Build with Icon
expected: Running `python build_exe.py` produces `dist/BluOpticalSim/BluOpticalSim.exe` with the teal icon embedded in the executable file. The `dist/BluOpticalSim/` folder also contains a README.txt and sample .blu files.
result: pass

### 6. Sample Project Files
expected: Running `python dist_assets/generate_samples.py` creates three .blu files (Simple_Box_Demo.blu, Automotive_Cluster_Demo.blu, Edge_Lit_LGP_Demo.blu) that can be opened in the app via File > Open.
result: pass

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0

## Gaps

[none — all resolved]

## Resolved

- truth: "The main window title bar and Windows taskbar both show the teal optics-motif icon (LED + rays + lens arc) instead of a generic Python/Qt icon."
  status: resolved
  root_cause: "On Windows, python.exe owns the taskbar grouping unless AppUserModelID is set via ctypes before the first window shows. setWindowIcon alone is insufficient."
  fix: "app.py: added ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('BluOptical.Simulation.2.0') at top of main() on win32; added explicit window.setWindowIcon(app_icon) after MainWindow creation."
  severity: major
  test: 3
