---
phase: 03
slug: golden-reference-validation-suite
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-18
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `03-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing `backlight_sim/tests/` discovery — no config file) |
| **Config file** | none currently — add `backlight_sim/tests/golden/conftest.py` in Wave 0 |
| **Quick run command** | `pytest backlight_sim/tests/golden/ -x` |
| **Full suite command** | `pytest backlight_sim/tests/ -x` |
| **Golden-only (verbose)** | `pytest backlight_sim/tests/golden/ -v --tb=short` |
| **Report command** | `python -m backlight_sim.golden --report [--out DIR] [--rays N]` |
| **Estimated golden runtime** | ~150 s (budget ceiling: 300 s) |

---

## Sampling Rate

- **After every task commit:** Run `pytest backlight_sim/tests/golden/ -x` (expected ~3–5 min when all cases land).
- **After every plan wave:** Run `pytest backlight_sim/tests/ -x` — full suite (golden + 124 existing).
- **Before `/gsd-verify-work`:** Golden suite green across 3 consecutive seeds {1, 42, 100}.
- **Max feedback latency:** 300 seconds (hard budget; Wave 0 budget-probe tunes down if overshoot).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 0 | GOLD-00 | — | N/A | infra | `pytest backlight_sim/tests/golden/ --collect-only` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 0 | GOLD-00 | — | N/A | infra | `python -c "import backlight_sim.golden; import backlight_sim.golden.cases"` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 0 | GOLD-00 | — | N/A | infra | `pytest backlight_sim/tests/golden/conftest.py -q` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | GOLD-01 | — | N/A | physics | `pytest backlight_sim/tests/golden/test_integrating_sphere.py -x` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 1 | GOLD-02 | — | N/A | physics | `pytest backlight_sim/tests/golden/test_lambertian_cosine.py -x` | ❌ W0 | ⬜ pending |
| 03-02-03 | 02 | 1 | GOLD-04 | — | N/A | physics | `pytest backlight_sim/tests/golden/test_specular_reflection.py -x` | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 2 | GOLD-03 | — | N/A | physics | `pytest backlight_sim/tests/golden/test_fresnel_glass.py -x` | ❌ W0 | ⬜ pending |
| 03-03-02 | 03 | 2 | GOLD-05 | — | N/A | physics | `pytest backlight_sim/tests/golden/test_prism_dispersion.py -x` | ❌ W0 | ⬜ pending |
| 03-04-01 | 04 | 3 | GOLD-06 | — | N/A | integration | `pytest backlight_sim/tests/golden/test_cli_report.py -x` | ❌ W0 | ⬜ pending |
| 03-04-02 | 04 | 3 | GOLD-06 | — | N/A | smoke | `python -m backlight_sim.golden --report --out /tmp/gold_report` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs are indicative — final IDs assigned by `gsd-planner`; VALIDATION rows updated post-plan.*

---

## Requirement → Observable Map

Derived from RESEARCH.md § Validation Architecture; each row defines the quantity measured and the PASS criterion.

| Req ID | Observable | Sampling Strategy | PASS Criterion |
|--------|-----------|-------------------|----------------|
| GOLD-01 | Inner-wall irradiance E on integrating cavity (SolidBox, ρ=0.9, finite-bounce-corrected) | 500k rays, 5×5 detector patch far from corners, 50 max bounces | `|E_measured − E_finite(N,ρ)| / E_finite < 0.02` |
| GOLD-02 | Angular intensity I(θ) of Lambertian emitter vs I₀·cos(θ) | 500k rays, SphereDetector far_field, 36 polar × 72 azimuth bins, θ∈[0°,80°] | `RMS(I_measured/I_peak − cos(θ))` < 0.03 |
| GOLD-03 | Fresnel T(θ) at air→glass (n=1.5) single interface | 200k rays/angle × {0°, 30°, 45°, 60°, 80°}; SolidBox with absorbing far-face override | `|T_measured(θ) − T_analytical(θ)| < 0.02` for every angle |
| GOLD-04 | Specular reflection law θ_out = θ_in (two sub-cases: C++ planar detector + Python far-field sphere) | 100k rays, far-field resolution (360,180) → 0.5° bins | `|θ_peak − θ_i| < 0.5°` on BOTH sub-cases |
| GOLD-05 | Prism exit angle vs Snell's law at λ∈{450,550,650} nm (closes `project_spectral_ri_testing` memory flag) | 500k rays/λ, SolidPrism apex=45° θ_in=20°, far-field sphere | BOTH (a) `|θ(λ) − θ_analytical(λ)| < 0.25°` for each λ AND (b) `θ(450) − θ(650) > 0.1°` (dispersion-detection guard) |
| GOLD-06 | CLI report produces HTML + markdown artifacts with all cases present | 1 invocation, default ray counts | `out/report.html` and `out/report.md` exist; both contain all 5 case names; exit code 0 |

---

## Wave 0 Requirements

- [ ] `backlight_sim/tests/golden/__init__.py` — test package marker
- [ ] `backlight_sim/tests/golden/conftest.py` — shared `assert_within_tolerance` fixture + minimal-project builders + seed constant
- [ ] `backlight_sim/tests/golden/references.py` — pure analytical math (Fresnel, cavity, Lambert, Snell/prism) — no tracer imports
- [ ] `backlight_sim/golden/__init__.py` — CLI package marker
- [ ] `backlight_sim/golden/cases.py` — `GoldenCase` dataclass + case registry (shared between pytest + CLI)
- [ ] Budget-probe task: actually measure per-case runtime and tune ray counts if any case > 90 s
- [ ] SPD convention verification: confirm `spd = "mono_450" | "mono_550" | "mono_650"` triggers monochromatic wavelength sampling (tracer.py:631 `has_spectral` gate) — low-risk smoke check

*If existing infra already covers any of these: noted in PATTERNS.md by `gsd-pattern-mapper`.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual sanity of HTML report (plots render, colors correct) | GOLD-06 | Matplotlib PNG rendering is environment-dependent; automated test only checks files exist | Run `python -m backlight_sim.golden --report --out ./tmp/golden` and open `tmp/golden/report.html` in a browser. Check Fresnel T vs θ curve and prism θ_exit vs λ markers are visible and near-analytical. |
| Seed-stability across {1, 42, 100} | GOLD-01..GOLD-05 | Optional reproducibility check, not strictly required for CI every run | `for s in 1 42 100; do GOLDEN_SEED=$s pytest backlight_sim/tests/golden/ -x; done` — all three PASS |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (Wave 0 = Plan 01)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (init package, conftest, references.py, CLI cases registry)
- [ ] No watch-mode flags (`pytest -x` only; no `--loop` / watchdog plugins)
- [ ] Feedback latency ≤ 300 s for golden suite
- [ ] `nyquist_compliant: true` set in frontmatter after Wave 0 completes

**Approval:** pending
