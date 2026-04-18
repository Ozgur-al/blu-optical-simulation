---
status: partial
phase: 04-uncertainty-quantification
source: [04-VERIFICATION.md]
started: 2026-04-18T18:18:26Z
updated: 2026-04-18T18:18:26Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Heatmap KPI label "±" rendering
expected: Running a sim with uq_batches=10 and opening the Heatmap tab shows KPI rows formatted as "value ± half_width unit" (e.g., "87.3 ± 1.2 %"). When uq_batches=0 or n_batches<4, the "±" token is absent and labels show plain "value unit".
result: [pending]

### 2. Confidence-level dropdown recompute
expected: Changing the confidence dropdown (90/95/99 %) in the heatmap panel updates all CI half-widths instantly with NO tracer rerun (progress bar does not move). All KPI labels and the CSV export refresh to the new conf level.
result: [pending]

### 3. Per-bin relative stderr overlay
expected: Selecting the noise-overlay color mode renders sigma_bin / mean_bin on the heatmap. Bins with mean_bin=0 render as NaN (transparent / colorbar out-of-range). Colorbar label reflects "relative stderr" (not flux units).
result: [pending]

### 4. Convergence (UQ) tab
expected: Convergence tab shows cumulative uniformity_1_4_min_avg (y) vs cumulative ray count (x). A shaded CI band surrounds the trace and visibly narrows as rays accumulate.
result: [pending]

### 5. Parameter sweep ErrorBarItem + CI columns
expected: Running a 1D parameter sweep with UQ on shows vertical whiskers on the KPI trace line. The results table has three additional columns: half_width, lower, upper (or equivalent CI column triplet). Whiskers align with trace points.
result: [pending]

### 6. HTML report CI rendering
expected: Exporting the HTML report and opening in a browser shows KPI rows as "value ± half_width" strings. A matplotlib errorbar chart for top KPIs is embedded inline (base64 PNG) and renders correctly.
result: [pending]

### 7. Warning banner styling
expected: When SimulationResult.uq_warnings is non-empty (e.g., adaptive+UQ both on, or k'<4 early-exit), the heatmap panel displays a visible warning banner showing all warning strings. Banner is hidden when uq_warnings is empty. Multi-warning case uses a readable separator (newline or bullet).
result: [pending]

## Summary

total: 7
passed: 0
issues: 0
pending: 7
skipped: 0
blocked: 0

## Gaps
