# Phase 8: Edge-Lit LGP Design Optimizer — Context

**Added:** 2026-04-18
**Status:** Spec recorded, not planned yet

## Phase Boundary

Full edge-lit light guide plate (LGP) design workflow — micro-structure (dot pattern, V-groove, prism) layout optimization, TIR-aware tracing, extraction-profile targeting. Extends the app beyond direct-lit BLUs into the larger edge-lit display market.

## Why Last

Biggest engine lift on the list (originally a Phase 2+ item per CLAUDE.md). Intentionally last in this track so it builds on validated physics (Phase 3), uncertainty-aware KPIs (Phase 4), and the optimizer (Phase 6). Shipping LGP on an unvalidated tracer would compound error across a much larger feature — every extraction-profile fit would silently be wrong if Fresnel/TIR is buggy.

## Scope

- **LGP geometry primitives:**
  - Thin plate with bottom-surface extraction features.
  - Feature types: dot grid (variable density map), V-groove (variable pitch/angle map), prism (angle map).
  - Each feature has an extraction probability function derived from geometric optics.
- **TIR-aware tracer integration:**
  - Leverage existing refractive-physics / n(λ) path (verified by Phase 3 golden refs for TIR critical angle).
  - Trace rays inside the LGP until extraction event or edge escape.
  - Track extraction location + direction for top-surface luminance profile.
- **Extraction-profile targeting:**
  - User draws/loads a desired top-surface luminance profile (e.g. uniform, or custom curve).
  - Optimizer (Phase 6 engine) solves for dot-density map or groove-pitch map that achieves it.
  - Closed-form initial guess from Beer-Lambert-like extraction law, refined by MC.
- **Side-injection source model:**
  - Line sources or LED arrays along an edge.
  - Coupling efficiency into the LGP (Fresnel at edge interface).
  - Support multiple-edge injection (e.g. two-sided edge lighting).
- **New presets:**
  - Edge-lit LCD backlight (single-edge + reflector bottom).
  - Keypad illumination (small LGP, one LED).
- **Golden-ref extension (Phase 3 suite grows):**
  - TIR critical angle verification.
  - Simple V-groove extraction cosine-law vs analytical.
  - Uniform dot-density extraction profile vs Beer-Lambert analytical.

## Out of Scope (for this phase, maybe later)

- Full-wave / physical optics for sub-wavelength features (stick with geometric optics).
- BEF (Brightness Enhancement Film) stack optimization on top of LGP — future.
- Full curved / wedged LGP shapes (start with uniform-thickness rectangular).

## Depends On

- Phase 3 (golden refs for TIR, Fresnel at LGP edges, dispersion inside LGP).
- Phase 6 (optimizer engine for extraction-profile targeting).
- Phase 2 (C++ port) strongly recommended — LGP sims have high bounce counts (TIR pinballs inside the plate), Python-loop cost dominates.

## Claude's Discretion

- Exact dot pattern parameterization (uniform grid with density map vs free-placed dots).
- Optimizer search space reduction (e.g. parameterize density map with low-order basis functions rather than per-pixel).
- Whether to implement all three feature types (dot/groove/prism) in one phase or split into sub-plans.
