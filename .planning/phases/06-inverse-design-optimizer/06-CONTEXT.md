# Phase 6: Inverse Design / Target-Driven Optimizer — Context

**Added:** 2026-04-18
**Status:** Spec recorded, not planned yet

## Phase Boundary

User declares a target ("uniformity ≥ 85%, minimize LED count") and the app solves for design parameters (LED count/pitch, wall angle, diffuser transmittance, cavity depth, etc.). Moves the app from analysis tool to design tool. Scope ends at numerical optimization — no ML surrogate models, no generative design.

## Why

Parameter sweeps already scan the design space manually. Inverse design closes the loop: formal optimization (CMA-ES or Bayesian) + multi-objective Pareto replaces "sweep then eyeball the best point". Critical that it sits on top of Phase 4 (UQ) — a gradient-free optimizer on a noisy objective will chase noise without proper noise modeling.

## Scope

- **Design variable spec:** UI to mark parameters as "free" (with bounds) vs "fixed". Support:
  - LED count (integer)
  - LED pitch / grid dimensions
  - Cavity depth, width, height
  - Wall angle (X and Y independently)
  - Diffuser transmittance / haze
  - Source flux / current
- **Objective builder:**
  - Weighted sum (scalarized multi-objective).
  - Multi-objective with Pareto front output.
  - Constraints (e.g. "uniformity ≥ 0.85" as hard constraint, "minimize cost" as objective).
- **Optimizer backends:**
  - **Primary:** CMA-ES (gradient-free, proven for MC-noisy objectives). Use `pycma` library.
  - **Secondary:** Bayesian optimization (scikit-optimize or Optuna) for expensive sims where evaluation count must be tiny.
  - Noise model: use Phase 4 UQ's per-evaluation CI as σ for the optimizer's noise estimate.
- **Integer handling:** LED count is integer — use integer-aware CMA-ES variant or round + re-evaluate.
- **Results UI:**
  - Pareto front plot (2D objectives; parallel-coordinates for >2).
  - Best-so-far trace across iterations.
  - Top-N candidate variants saved as project clones (leverages existing variant system).
  - Convergence diagnostics (σ trajectory, stagnation detector).
- **Robust design (optional):** if Phase 5 is available, optimize P5 (worst-case across tolerances) instead of nominal — i.e. minimize tolerance-sensitive failure.

## Out of Scope

- Topology optimization of continuous geometry (future).
- Neural-network surrogates (future — orthogonal to the optimizer itself).
- Real-time optimization during user editing (offline batch only).

## Depends On

- Phase 4 (UQ — optimizer needs noise-aware objective evaluation to avoid chasing MC noise).
- Phase 5 (optional — enables robust-design mode).

## Claude's Discretion

- CMA-ES implementation choice (`pycma` is standard).
- Pareto front visualization (2D scatter vs parallel-coordinates for high-D).
- How to express constraints to CMA-ES (penalty vs feasibility projection).
- Parallel evaluation strategy (CMA-ES population can run in parallel via existing multiprocessing path).
