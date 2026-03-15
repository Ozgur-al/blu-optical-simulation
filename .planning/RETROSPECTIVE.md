# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Phase 2 Full-Fidelity Simulator

**Shipped:** 2026-03-15
**Phases:** 7 | **Plans:** 19 | **Tests:** 118

### What Was Built
- Refractive physics engine (Snell's law, Fresnel, TIR) with SolidBox for edge-lit LGP simulation
- Per-ray wavelength spectral engine with CIE XYZ colorimetry and color uniformity KPIs
- Numba JIT acceleration (optional), BVH spatial indexing, adaptive sampling with convergence targeting
- Tabulated BSDF import/sampling, far-field angular detector with IES export, cylinder/prism solid bodies
- Professional dark-themed UI with toolbar, undo/redo, collapsible sections, live heatmap preview
- Cross-phase integration wiring: all solid bodies in MP/spectral/BSDF paths; UI gap closure

### What Worked
- TDD approach for physics (RED→GREEN cycle) caught intersection bugs early and provided regression safety
- Phase verification reports (VERIFICATION.md) after each phase caught 5 integration gaps and 4 broken E2E flows before they became user-visible
- Strict layer separation (core/sim/io never import PySide6) made headless testing of physics and I/O fast and reliable
- Gap closure phases (6 and 7) created from audit findings were focused and effective — 8 new tests covered all integration gaps

### What Was Inefficient
- Initial roadmap had 4 phases; UI Revamp (Phase 5) was added mid-milestone, then 2 gap closure phases (6-7) were needed after audit — 7 phases total vs 4 planned
- Phase 5 UI-02 requirement text ("QDockWidgets") didn't match delivered implementation (QSplitter+QTabWidget) — requirement should have been updated when the deviation was approved
- SUMMARY.md frontmatter `requirements-completed` field was inconsistently populated in early plans — required manual backfill during audit
- Some silent `except Exception: pass` handlers accumulated across GUI code — caught only during milestone audit

### Patterns Established
- `face_optics` dict pattern on solid bodies: face-level optical overrides without changing material system
- `getattr(project, "field", [])` guard pattern for backward-compatible expansion of Project dataclass
- Phase verification → audit → gap closure → re-audit cycle for milestone completion
- `CollapsibleSection` widget pattern for all property forms (Identity/Position/Orientation/Dimensions)
- Spectral+MP guard: force single-thread when spectral is active, with user warning

### Key Lessons
1. Cross-phase integration must be tested explicitly — phases that pass individually can have broken E2E flows when combined (Cylinder+MP, BSDF+spectral)
2. Requirement text must be updated when approved deviations change the deliverable — stale requirement text causes audit failures
3. Silent exception handlers mask bugs; always use `warnings.warn()` at minimum
4. BVH optimization only helps homogeneous geometry types — mixing plane/quadratic/polygon intersections requires heterogeneous dispatch, which is a separate feature

### Cost Observations
- Model mix: ~60% sonnet (agents), ~40% opus (orchestration)
- Execution velocity: 19 plans in ~2 calendar days
- Notable: Phase 6 (tracer wiring) took 138 min for plan 1 due to large tracer.py complexity; all other plans averaged <20 min

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 7 | 19 | Phase verification + audit cycle established; gap closure phases added |

### Cumulative Quality

| Milestone | Tests | Requirements | Coverage |
|-----------|-------|-------------|----------|
| v1.0 | 118 | 24/24 | All requirements satisfied, 8 E2E flows verified |

### Top Lessons (Verified Across Milestones)

1. Cross-phase integration testing is essential — individual phase verification is necessary but not sufficient
2. Requirement text must track reality — deviations require immediate requirement updates
