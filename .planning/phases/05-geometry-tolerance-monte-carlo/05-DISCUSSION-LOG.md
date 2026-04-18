# Phase 5: Geometry Tolerance Monte Carlo — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `05-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-04-18
**Phase:** 05-geometry-tolerance-monte-carlo
**Mode:** Augment existing CONTEXT.md (auto-generated spec draft was not a real discussion)
**Areas discussed:** v1 parameter scope, Phase 4 (UQ) dependency handling

**Areas deferred to Claude's discretion** (user unselected):
- Tolerance data model (inline vs unified ToleranceSpec vs sibling dict)
- Sensitivity method (Sobol vs OAT vs Morris)

---

## v1 Parameter Scope

### Q1 — Which manufacturing failure modes belong in v1?

| Option | Description | Selected |
|--------|-------------|----------|
| LED position | Per-source dx/dy/dz jitter; primary manufacturing failure mode | ✓ |
| Cavity wall angle + depth | Tolerance on `build_cavity()` params; re-run builder per realization | ✓ |
| Rectangle pose (generic) | dx/dy/dz + dθ on arbitrary `Rectangle` objects | |
| LED flux + binning | Reuse existing `flux_tolerance`, re-drawn per ensemble member | ✓ |

**User's choice:** LED position, LED flux + binning, Cavity wall angle + depth (generic Rectangle pose deferred)
**Notes:** Covers the three real-world BLU failure modes. Generic Rectangle pose deferred to a v2 of this phase.

### Q2 — LED position tolerance spec model

| Option | Description | Selected |
|--------|-------------|----------|
| Project-level default + per-source override | Single project default σ; individual sources may override | ✓ |
| Per-LED only | Each PointSource has its own sigma fields set individually | |
| Project-level only | One global number applied to every LED | |

**User's choice:** Project-level default + per-source override (recommended)
**Notes:** Matches how engineers actually spec placement tolerance ("our LED placement tolerance is ±0.15 mm"), stays clean on a 16–64 LED grid, allows exceptions for hand-placed LEDs.

### Q3 — Cavity tolerance travel model

| Option | Description | Selected |
|--------|-------------|----------|
| Attach to Project as "build recipe" | Store `build_cavity()` args + tolerances; re-run builder per realization | ✓ |
| Lift to each Rectangle | Jitter each wall's u_axis/v_axis independently | |
| Both, user chooses per param | Recipe-level for cavity, per-Rectangle for diffuser/film planes | |

**User's choice:** Attach to Project as "build recipe" (recommended)
**Notes:** Matches manufacturing reality — a molded cavity with wall-angle drift moves all four walls coherently, not independently.

### Q4 — Tolerance units

| Option | Description | Selected |
|--------|-------------|----------|
| Absolute only | Position ±mm, angle ±deg, depth ±mm; flux keeps existing ±% | ✓ |
| User choice per field | Each tolerance field has an absolute/% dropdown | |

**User's choice:** Absolute only (recommended)
**Notes:** Matches mechanical GD&T convention. Flux keeps ±% since LED bins are intrinsically relative.

---

## Phase 4 (UQ) Dependency Handling

### Q5 — How should Phase 5 handle the Phase 4 prerequisite?

| Option | Description | Selected |
|--------|-------------|----------|
| Block Phase 5 on Phase 4 | Plan and ship Phase 4 first; Phase 5 inherits batch-CI plumbing natively | ✓ |
| Ship Phase 5 without variance separation | Ensemble histogram shows total variance; flag caveat | |
| Stub CI now, wire Phase 4 later | Phase 5 computes per-realization CI via a simple batch split as mini-Phase-4 | |

**User's choice:** Block Phase 5 on Phase 4
**Notes:** Respects declared dependency in ROADMAP.md; cleanest architecture; no technical debt.

### Q6 — Practical meaning of the block

| Option | Description | Selected |
|--------|-------------|----------|
| Plan Phase 4 + execute, then plan Phase 5 | Phase 5 plans land after Phase 4's CI plumbing is real code | |
| Plan both 4 and 5 now, execute in order | Concurrent planning; placeholder Phase 4 API signatures in Phase 5 plans | |
| Capture context only; revisit plan sequencing later | Finish CONTEXT.md; decide plan sequencing when ready | |

**User's choice (free text):** "it is planned btw, let us discuss phase 5 and i will execute planning later"
**Interpretation:** User will sort out planning order outside this command. Phase 5 CONTEXT.md captures the decision; sequencing is their call.

### Q7 — Specific Phase 4 APIs Phase 5 expects

| Option | Description | Selected |
|--------|-------------|----------|
| No specific asks — let Phase 4 design itself | CONTEXT notes dependency without constraining Phase 4 | |
| Phase 5 needs: pure-function KPI extractor | Call out `compute_kpis(result) → dict[str, float]` as Phase 4 prerequisite | |
| Both — pure KPI extractor AND per-realization CI format | Phase 4 must produce (a) pure KPI function and (b) `KpiWithCI { mean, low, high, n_batches }` | ✓ |

**User's choice (free text):** "whats your recommendation"
**Claude's recommendation (accepted in Q8):** Option 3 — lock both. KPI extraction is blocking regardless (ensemble runner calls it N times). A stable `KpiWithCI` struct makes Phase 5 histogram code trivial and future-proofs HTML/CSV exports.

### Q8 — Lock the Phase 4 prerequisites?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, lock both | Write into Phase 5 CONTEXT.md as a hard Phase 4 prerequisite | ✓ |
| Yes, but soft ask | Note as "would benefit from X and Y" — Phase 4 planner can push back | |
| Skip — let Phase 4 design freely | No constraint from Phase 5 | |

**User's choice:** Yes, lock both
**Notes:** Captured as D-07 in CONTEXT.md. If Phase 4 lands without both, Phase 5 planning re-opens.

---

## Claude's Discretion (user deferred)

The following gray areas were intentionally not discussed; the planner / researcher decides during plan-phase:

- **Tolerance data model shape** — inline fields vs unified `ToleranceSpec` dataclass vs sibling `project.tolerances` dict keyed by (object_id, param_name).
- **Sensitivity method** — Sobol first-order vs OAT vs Morris elementary effects. Suggested default: OAT cheap mode + Sobol full mode.
- **Ensemble runner UI container** — new dedicated dialog vs extending `parameter_sweep_dialog`.
- **Worst-case drill-down mechanics** — clone-as-variant vs reconstruct from stored seed.
- **3D viewport tolerance indicator** — ghosted ±σ wireframe vs tree-icon badge vs skip.
- **Live-streaming histogram during run** vs post-run display.
- **Default ensemble size N** and parallelization via `ProcessPoolExecutor`.

## Deferred Ideas

- Correlated tolerances (covariance) — v2 of this phase.
- Temperature-coupled tolerances — depends on Phase 7 thermal model.
- Generic `Rectangle` pose tolerances on arbitrary surfaces — v2 of this phase.
- Robust design optimization (optimize P5 instead of mean) — Phase 6 consumes this.
- Material property tolerances (reflectance, transmittance drift) — not in scope for v1.
