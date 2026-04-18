# Phase 3: Golden-Reference Validation Suite — Context

**Added:** 2026-04-18
**Status:** Spec recorded, not planned yet

## Phase Boundary

Build a library of analytical and experimentally-verified test cases that every tracer change must pass before merging. Establish trust in the physics engine before building higher-order features (UQ bars, optimizers, LGP) on top of it.

## Why First in the Post-v1.0 Physics Track

UQ, inverse design, and the LGP engine all consume the tracer's output as ground truth. A silent Fresnel bug or dispersion error propagates into every downstream feature. Golden references catch physics regressions cheaply, now — before wrong physics poisons optimizer objectives and LGP extraction models.

## Scope

- **Known-answer cases:**
  - Integrating-sphere uniformity (analytical cos-weighted flux on inner wall)
  - Lambertian flat emitter vs cosine law (I(θ) = I₀·cos(θ))
  - Fresnel transmittance at glass interface (s/p polarization-averaged) vs analytical Fresnel equations across incidence angles
  - Single-bounce specular mirror angle check (law of reflection)
  - Spectral n(λ) dispersion path for a prism/wedge vs Snell's law at sampled wavelengths — closes the `project_spectral_ri_testing.md` gap (smoke-tested but not verified)
- **Tolerance-based pass/fail:** each case declares expected value + tolerance (e.g. ±1% for MC with 1M rays); suite prints per-case PASS/FAIL + residual + effective ray count.
- **CLI + pytest integration:**
  - `pytest backlight_sim/tests/golden/` runs the suite as part of CI.
  - `python -m backlight_sim.golden --report` emits an HTML/markdown report with plots for documentation.
- **Regression guard:** suite must run in < 5 min on a dev laptop so it can be a pre-merge check.

## Out of Scope

- BRDF / measured-material validation (requires external data; schedule later).
- Experimental/measurement fit (future phase; distinct from analytical golden refs).
- Performance benchmarking (separate concern).

## Depends On

- Phase 1 (distribution) — no direct blocker; Phase 3 can run in parallel with Phase 2 (C++ port).

## Claude's Discretion

- Exact tolerance values per case (must be defensible vs MC std error at stated ray counts).
- Whether to use pytest fixtures or standalone `unittest` style.
- Report HTML template (can reuse `io/report.py` pattern).
