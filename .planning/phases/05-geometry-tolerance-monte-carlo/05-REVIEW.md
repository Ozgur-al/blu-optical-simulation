---
phase: 05-geometry-tolerance-monte-carlo
status: issues_found
depth: standard
files_reviewed: 11
reviewed: 2026-04-19
findings:
  critical: 3
  warning: 7
  info: 5
  total: 15
---

# Code Review — Phase 5: Geometry Tolerance Monte Carlo

**Depth:** standard  
**Files reviewed:** 11  
**Status:** issues_found

---

## Critical

### CR-01: OAT single-parameter isolation reuses the same RNG instance across all perturbations

**File:** `backlight_sim/sim/ensemble.py` (`build_oat_sample`)

`build_oat_sample` creates one `rng` from the masked seed, then calls `apply_jitter(p_temp, rng)` in a loop for each parameter. Because `rng` is stateful, the Nth perturbed sample depends on the draw state left by samples 1…N-1. Reproducibility breaks when the set of active parameters changes between runs, and OAT sensitivity indices are incorrect.

**Fix:** Create a fresh RNG per perturbation derived from the base seed:
```python
for j, (param_name, sigma) in enumerate(_active_tolerance_params(project)):
    param_rng = np.random.default_rng((seed & 0x7FFFFFFF) ^ (j * 0x9E3779B9))
    perturbed = apply_jitter(p_temp, param_rng)
```

---

### CR-02: OAT cavity overrides add sigma value directly instead of drawing from it

**File:** `backlight_sim/sim/ensemble.py` (`_jitter_cavity`)

When `overrides` contains `"depth_sigma_mm"`, the code adds the raw sigma value as a fixed offset — not a random draw. For position overrides in `apply_jitter`, sigma is set and then Gaussian-drawn, which is correct. Cavity and position perturbation paths are inconsistent: position gets `N(0, σ)` while cavity gets exactly `+σ` added.

**Fix:** Route all cavity overrides through `_draw()` for consistent behavior, or document that cavity OAT is a deterministic +1σ shift and align the position OAT path to also be deterministic.

---

### CR-03: `build_mc_sample` seed derivation has collision risk after 31-bit masking

**File:** `backlight_sim/sim/ensemble.py` (`build_mc_sample`)

```python
member_seed = (base_seed + i * 6364136223846793005) & 0x7FFFFFFF
```

Multiplying a 64-bit LCG multiplier and masking to 31 bits produces poor distribution in the lower bits. The 31-bit truncation of a 63-bit multiplier is not a quality LCG — many members may share seeds.

**Fix:** Use numpy's recommended child-seed pattern:
```python
base_rng = np.random.default_rng(seed & 0x7FFFFFFF)
child_rngs = base_rng.spawn(N)
for i, rng in enumerate(child_rngs):
    member = apply_jitter(base_project, rng)
```

---

## Warning

### WR-01: `_on_dist_step_done` mixes KPI values if user changes combo mid-run

**File:** `backlight_sim/gui/ensemble_dialog.py` (`_on_dist_step_done`)

`_dist_kpi_values` accumulates values for whichever KPI is selected at each step signal. If the user changes the combo mid-run, the list becomes a mixed-KPI series and the histogram/percentiles show meaningless data.

**Fix:** Rebuild from `_dist_all_kpis` on every step instead of appending:
```python
self._dist_kpi_values = [k.get(selected_key, 0.0) for k in self._dist_all_kpis]
```

---

### WR-02: `_EnsembleThread` silently swallows all exceptions per member with no user feedback

**File:** `backlight_sim/gui/ensemble_dialog.py` (`_EnsembleThread.run`)

A persistent simulation bug will cause all N members to silently fail — the progress bar advances, `sweep_finished` emits, and the dialog shows an empty result with no error message.

**Fix:** Track an `_error_count` and emit a warning after the loop when errors occurred.

---

### WR-03: `_on_sens_kpi_changed` always calls OAT table updater even in Sobol mode

**File:** `backlight_sim/gui/ensemble_dialog.py` (`_on_sens_kpi_changed`)

When the user ran a Sobol sensitivity analysis and then changes the KPI selector, the OAT table updater is called, silently displaying incorrect results.

**Fix:**
```python
def _on_sens_kpi_changed(self) -> None:
    if not self._sens_all_kpis:
        return
    if "Sobol" in self._sens_mode_combo.currentText():
        self._update_sobol_sensitivity_table()
    else:
        self._update_oat_sensitivity_table()
```

---

### WR-04: `_update_worst_case` always uses `argmin` regardless of KPI direction

**File:** `backlight_sim/gui/ensemble_dialog.py` (`_update_worst_case`)

`argmin` is correct for uniformity and efficiency (lower = worse) but wrong for `cv_pct` and `hotspot_peak_avg` (higher = worse). For `cv_pct`, `argmin` gives the *best* member, not the worst.

**Fix:** Define a per-KPI direction map and conditionally use `argmin` or `argmax`.

---

### WR-05: `_on_dist_finished` overwrites `_dist_member_projects` from thread's private attribute

**File:** `backlight_sim/gui/ensemble_dialog.py` (`_on_dist_finished`)

Two parallel lists (`_dist_member_projects` in dialog and `_member_projects` in thread) are maintained independently. Near-cancellation signal timing could cause them to diverge. The finish-time reassignment silently replaces accumulated step data.

**Fix:** Use only one authoritative list — remove either the per-step accumulation or the finish-time reassignment.

---

### WR-06: `SettingsForm` does not expose `source_position_sigma_mm` / `source_position_distribution`

**File:** `backlight_sim/gui/properties_panel.py` (`SettingsForm`)

The project-level position sigma and distribution choice are not editable in the UI. Users cannot configure the primary ensemble tolerance parameter without editing the JSON file directly.

**Fix:** Add a "Position Tolerance" row to `SettingsForm` with a sigma spinbox and distribution combo.

---

### WR-07: `build_sobol_sample` has `scipy.stats.norm` import inside the inner loop

**File:** `backlight_sim/sim/ensemble.py` (`build_sobol_sample`)

`from scipy.stats import norm` is executed up to `N_pow2 × k` times (e.g. 2048 times for N=512, k=4). Python caches imports so this is not a correctness issue, but it is poor practice.

**Fix:** Hoist to function scope alongside the existing `qmc` import.

---

## Info

### IN-01: `_active_tolerance_params` collapses per-source sigmas to a single max value

**File:** `backlight_sim/sim/ensemble.py` (`_active_tolerance_params`)

When sources have different `position_sigma_mm` values, the function returns only the max, used as the OAT perturbation amplitude. The OAT index over-estimates sensitivity for sources with smaller individual sigmas. Document as a known approximation.

---

### IN-02: `compute_sobol_sensitivity` uses `np.var` over A+B pool — slightly biased at small N

**File:** `backlight_sim/sim/ensemble.py` (`compute_sobol_sensitivity`)

Saltelli (2002) total-output-variance estimate from `np.var(concatenate([fa, fb]))` is correct in the limit but slightly biased for small N. The clamping already acknowledges artefacts; note this approximation in the docstring.

---

### IN-03: `_jitter_cavity` does not update `cavity_recipe` with realized jittered values

**File:** `backlight_sim/io/geometry_builder.py` / `backlight_sim/sim/ensemble.py`

After jitter, `project.cavity_recipe` still holds the original nominal values. Jitters do not compose — calling `apply_jitter` twice on the same clone jitters from the original recipe both times. Add a comment documenting this non-composable behavior.

---

### IN-04: `_EnsembleThread.run()` defers ensemble imports unnecessarily

**File:** `backlight_sim/gui/ensemble_dialog.py`

`build_mc_sample`, `build_oat_sample`, `build_sobol_sample` are imported inside `run()` but there is no circular import risk. Move to module-level for clarity.

---

### IN-05: `_check_project_ready` does not warn when all sigma values are zero

**File:** `backlight_sim/gui/ensemble_dialog.py`

Running an ensemble with all-zero sigmas produces N identical copies of the base project (degenerate case). A flat histogram with no explanation may confuse users. Add a warning or early return when no active tolerances are configured.

---

## Summary

The three critical issues all affect statistical correctness: CR-01 (shared RNG across OAT perturbations), CR-02 (inconsistent cavity vs. position perturbation semantics), and CR-03 (weak MC seed derivation after 31-bit masking). These should be fixed before relying on OAT sensitivity indices or ensemble distributions for engineering decisions.

The GUI bugs (WR-01, WR-03, WR-04) affect result interpretation quality. WR-06 is a usability gap that makes the primary ensemble parameter inaccessible via UI.

**Recommended:** Run `/gsd-code-review-fix 5` to auto-apply the tractable fixes (WR-01, WR-03, WR-07, IN-04). Address CR-01 and CR-03 manually — they require algorithm changes.
