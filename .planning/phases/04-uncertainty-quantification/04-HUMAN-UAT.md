---
status: resolved
phase: 04-uncertainty-quantification
source: [04-VERIFICATION.md]
started: 2026-04-18T18:18:26Z
updated: 2026-04-19T00:00:00Z
---

## Current Test

[all items approved by user]

## Tests

### 1. Heatmap KPI label "±" rendering
expected: Running a sim with uq_batches=10 and opening the Heatmap tab shows KPI rows formatted as "value ± half_width unit". When uq_batches=0 or n_batches<4, the "±" token is absent and labels show plain "value unit".
result: passed (user-approved 2026-04-19)

### 2. Confidence-level dropdown recompute
expected: Changing the confidence dropdown (90/95/99 %) in the heatmap panel updates all CI half-widths instantly with NO tracer rerun. All KPI labels and the CSV export refresh to the new conf level.
result: passed (user-approved 2026-04-19)

### 3. Per-bin relative stderr overlay
expected: Selecting the noise-overlay color mode renders sigma_bin / mean_bin on the heatmap. Bins with mean_bin=0 render as NaN. Colorbar label reflects "relative stderr".
result: passed (user-approved 2026-04-19)

### 4. Convergence (UQ) tab
expected: Convergence tab shows cumulative uniformity_1_4_min_avg vs cumulative ray count with a shaded CI band that visibly narrows as rays accumulate.
result: passed (user-approved 2026-04-19)

### 5. Parameter sweep ErrorBarItem + CI columns
expected: 1D parameter sweep with UQ on shows vertical whiskers on the KPI trace; results table has three additional CI columns.
result: passed (user-approved 2026-04-19)

### 6. HTML report CI rendering
expected: HTML report shows KPI rows as "value ± half_width" and an embedded matplotlib errorbar chart.
result: passed (user-approved 2026-04-19)

### 7. Warning banner styling
expected: When SimulationResult.uq_warnings is non-empty, heatmap panel displays a visible warning banner showing all warning strings; hidden when empty.
result: passed (user-approved 2026-04-19)

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
