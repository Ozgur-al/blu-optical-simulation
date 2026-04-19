# Phase 7: Cost / Thermal / Photometric Joint Design View — Context

**Added:** 2026-04-18
**Status:** Spec recorded, not planned yet

## Phase Boundary

Single "design sheet" view displaying lm/W, $/unit (BOM estimate), ΔT (thermal estimate from LED current + derating), and uniformity/peak luminance side by side. Mostly UI/aggregation on top of existing outputs; adds a lumped-node thermal proxy and a user-editable cost model.

## Why

Mortals optimize one axis; reality is a 3-way tradeoff between cost, thermal, and photometric performance. A single dashboard that shows all three together is a cheaper win than the LGP engine (Phase 8) and pairs naturally with Phase 6 inverse design — the optimizer optimizes what the joint view displays.

## Scope

- **Cost model:**
  - Per-LED unit cost (default from vendor table, user-editable).
  - Cavity material cost (area × $/unit area).
  - Diffuser/film cost (area × $/unit area).
  - Aggregated $/unit with live update as design changes.
- **Thermal proxy (lumped-node):**
  - Inputs: LED current (I), package thermal resistance (R_θJA), board/ambient thermal resistance, ambient temp.
  - P_dissipated = V_f(I) × I × (1 − η_LED).
  - ΔT = P_dissipated × R_total.
  - Feeds back into `PointSource.thermal_derate` — closes the loop on an existing field that's currently user-set by hand.
- **Photometric summary:**
  - Existing KPIs (uniformity, peak, efficiency) displayed with Phase 4 CIs.
  - New: lm/W = total luminous flux / total electrical power (sum of P_elec per LED).
- **Design sheet panel:**
  - New tab in main window; single-pane dashboard with cost / thermal / photometric tiles.
  - Cross-influence indicators (e.g. "↑ current → +5% flux, +8°C ΔT, −3% lm/W").
- **Variant comparison extension:** existing `comparison_dialog` extended to show all three axes side by side across variants.
- **Optimizer objective source:** Phase 6 optimizer reads objectives from the design sheet — "minimize $/unit subject to lm/W ≥ X and ΔT ≤ Y".

## Out of Scope

- Finite-element thermal simulation (stick with lumped-node proxy).
- Full BOM cost including assembly labor (user can edit unit costs to incorporate).
- Time-domain thermal (transient) — steady-state only.

## Depends On

- Phase 4 (UQ — so cost/thermal/photometric all display with CIs).
- Ideally pairs with Phase 6 (optimizer reads objectives from the joint view), but can ship independently.

## Claude's Discretion

- Exact thermal model parameters (use reasonable defaults for common LED packages).
- Cost table schema (CSV vs embedded table editor).
- Whether to expose thermal sensitivity (dΔT/dI) as its own KPI.
