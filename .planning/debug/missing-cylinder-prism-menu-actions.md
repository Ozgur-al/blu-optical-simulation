---
status: resolved
trigger: "Add Cylinder and Add Prism menu actions are missing from the scene menu"
created: 2026-03-15T00:00:00Z
updated: 2026-03-15T00:00:00Z
---

## Current Focus

hypothesis: confirmed — menu actions were never added to either the &Add menu or the toolbar
test: read main_window.py _setup_menu and _setup_toolbar in full
expecting: cylinder and prism actions missing from both locations
next_action: report findings

## Symptoms

expected: "Add Cylinder" and "Add Prism" actions present in the scene/Add menu alongside "Add Solid Box"
actual: neither action appears anywhere in the menu bar or toolbar
errors: none (silent omission)
reproduction: launch app, open "&Add" menu — only Point Source / Surface / Detector / Sphere Detector / Material / Optical Properties are present
started: the handlers exist but the triggering UI was never wired up

## Eliminated

- hypothesis: SolidCylinder / SolidPrism classes don't exist
  evidence: backlight_sim/core/solid_body.py lines 219-425 define both classes fully
  timestamp: 2026-03-15

- hypothesis: handler code (_add_object, _on_object_selected, _delete_object) is missing
  evidence: main_window.py lines 772-800 and 825-828 handle "Solid Bodies:cylinder" and "Solid Bodies:prism" groups correctly
  timestamp: 2026-03-15

## Evidence

- timestamp: 2026-03-15
  checked: main_window.py _setup_menu (lines 274-280)
  found: "&Add" menu contains: Point Source, Surface, Detector, Sphere Detector, Material, Optical Properties — NO cylinder or prism entry
  implication: the menu actions were never added

- timestamp: 2026-03-15
  checked: main_window.py _setup_toolbar (lines 364-373)
  found: toolbar quick-add loop contains only: Add LED, Add Surface, Add Detector, Add SolidBox — NO cylinder or prism
  implication: toolbar actions were also never added

- timestamp: 2026-03-15
  checked: plan 04-04-PLAN.md line 284
  found: spec explicitly states "Add 'Add Cylinder' and 'Add Prism' actions to the scene menu (alongside 'Add Solid Box')"
  implication: the implementation skipped the menu-wiring step

## Resolution

root_cause: >
  In backlight_sim/gui/main_window.py, two menu entries were never added.
  The _setup_menu() method at lines 274-280 builds the "&Add" menu but omits
  "Add Cylinder" and "Add Prism". The _setup_toolbar() method at lines 364-373
  builds the toolbar quick-add loop but also omits those two entries.
  All downstream handler code IS present (selection, add, delete all handle
  "Solid Bodies:cylinder" and "Solid Bodies:prism" group strings). Only the
  UI trigger points — the menu actions and toolbar buttons — were never written.

fix: >
  In main_window.py _setup_menu(), add after line 280 (after "Optical Properties"):
    am.addSeparator()
    am.addAction("Solid Box",  lambda: self._add_object("Solid Bodies:box"))
    am.addAction("Cylinder",   lambda: self._add_object("Solid Bodies:cylinder"))
    am.addAction("Prism",      lambda: self._add_object("Solid Bodies:prism"))

  In _setup_toolbar(), extend the quick-add loop to include:
    ("Add Cylinder", "Solid Bodies:cylinder"),
    ("Add Prism",    "Solid Bodies:prism"),

verification: not yet applied — diagnosis only

files_changed: []
