# Phase 2: Spectral Engine - Research

**Researched:** 2026-03-14
**Domain:** Wavelength-aware Monte Carlo ray tracing + CIE colorimetry + PySide6 GUI
**Confidence:** HIGH — all findings grounded in direct codebase inspection and established colorimetry standards

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Spectral Material Definition**
- Wavelength-dependent properties defined as tables of (wavelength_nm, value) pairs — same pattern as angular distributions
- Both reflectance and transmittance are wavelength-dependent; absorption derived as 1 - R - T
- Spectral tables are optional: materials without spectral data fall back to their scalar reflectance/transmittance values for all wavelengths (backward-compatible)
- GUI: dedicated spectral tab (not inline in properties panel) for managing material spectral properties

**Source SPD Management**
- Custom SPD profiles via CSV import + table editor, same pattern as angular distributions
- Combined "Spectral Data" tab manages both source SPDs and material spectral tables in two sub-sections
- Include a blackbody (Planckian) SPD generator: user inputs a CCT (e.g. 3000K, 6500K) and the app generates the spectral curve
- SPD profiles stored inside the project JSON file (alongside angular distributions) — self-contained projects
- Built-in SPDs remain: white, warm_white, cool_white, mono_<nm>

**Color Result Visualization**
- True-color image from CIE XYZ integration: each pixel's spectral bins are integrated through CIE 1931 color matching functions to produce sRGB — shows what the backlight actually looks like
- Instant toggle between intensity/color views after simulation — no re-run required (spectral grid always accumulated when any source has non-white SPD)
- CIE 1931 chromaticity diagram widget alongside the color heatmap — shows distribution of pixel chromaticity coordinates as scatter points on the gamut outline
- Click-to-inspect per-pixel spectrum: clicking a pixel shows its spectral power distribution as a line plot (wavelength vs flux)

**Color Uniformity KPIs**
- Three metric families: delta-CCx/CCy (CIE 1931), delta-u'v' (CIE 1976 perceptually uniform), and CCT (correlated color temperature average + range)
- CRI not included in this phase
- Computed over both full detector AND center fractions (1/4, 1/6, 1/10) — matches existing intensity uniformity pattern
- Displayed in a separate collapsible "Color Uniformity" section in the KPI dashboard, below intensity metrics
- Color KPIs included in CSV export and HTML report exports

### Claude's Discretion
- Chromaticity diagram widget library choice and layout within the spectral tab
- Per-pixel spectrum plot widget placement (popup, side panel, or tooltip)
- Spectral bin count and interpolation method for material property lookup
- Multiprocessing path update for spectral accumulation (architecture choice)
- CCT computation method (Robertson's, Ohno's, or McCamy's approximation)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SPEC-01 | Each ray carries a sampled wavelength and material interactions are wavelength-dependent | `sample_wavelengths()` exists; `_bounce_surfaces()` must interpolate per-wavelength R/T tables; custom SPD storage in Project needed |
| SPEC-02 | Detector accumulates flux per wavelength bin into a spectral grid | `grid_spectral` field already on `DetectorResult`; `_accumulate()` already bins by wavelength in single-thread path; MP merge path missing spectral grids |
| SPEC-03 | User can view detector result as a CIE XYZ / sRGB color image | `spectral_grid_to_rgb()` exists; heatmap panel has "Spectral Color" mode wired; chromaticity diagram and click-to-inspect need new widgets |
| SPEC-04 | Material reflectance and transmittance can be defined as wavelength-dependent tables | No spectral table storage in `Material`/`OpticalProperties` or `Project`; needs new `Project.spectral_material_data` dict + tracer lookup |
| SPEC-05 | User can see color uniformity KPIs (delta-CCx, delta-CCy) after spectral simulation | No chromaticity computation exists yet; need `xyz_per_pixel()` → `xy_per_pixel()` → delta-CCx/CCy/u'v'/CCT; KPI panel section + CSV/HTML export |
</phase_requirements>

---

## Summary

Phase 2 adds wavelength-aware simulation on top of a codebase that already has substantial spectral scaffolding in place. The core spectral pipeline — CIE observer data, built-in SPDs (white/warm/cool/mono), `sample_wavelengths()`, `spectral_bin_centers()`, `spectral_grid_to_rgb()`, `DetectorResult.grid_spectral`, and the heatmap panel "Spectral Color" toggle — exists and works in the single-thread path. Phase 2 closes the remaining gaps: (1) custom/project-stored SPD lookup so user-defined SPDs are actually used by the tracer, (2) wavelength-dependent material property interpolation so surfaces interact differently at 450 nm vs 600 nm, (3) spectral grid merge in the multiprocessing path, (4) the "Spectral Data" combined tab for managing SPDs and material spectral tables, and (5) CIE colorimetry KPIs (delta-CCx/CCy, delta-u'v', CCT) in the KPI dashboard.

The implementation falls naturally into two plans. Plan 02-01 is entirely simulation-engine and data-model work: wire custom SPD lookup into `sample_wavelengths`, add `Project.spd_profiles` + `Project.spectral_material_data` dicts, implement per-wavelength material property interpolation in `_bounce_surfaces`, and fix the MP merge path to carry spectral grids. Plan 02-02 is GUI and colorimetry work: the combined "Spectral Data" tab (mirroring the Angular Distribution panel), chromaticity diagram + click-to-inspect widgets, `spectral_to_chromaticity()` / CCT helpers in `sim/spectral.py`, and the Color Uniformity KPI section in `heatmap_panel.py`.

**Primary recommendation:** Tackle data-model + tracer plumbing (02-01) first — it has no GUI dependencies and produces testable outputs. The GUI work (02-02) consumes the stable spectral API.

---

## Standard Stack

### Core (already in requirements.txt — no new installs needed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | (existing) | Array math for spectral bins, CIE integration, interpolation | Used throughout codebase |
| PySide6 | (existing) | GUI widgets, tab panels, signals | Project's GUI framework |
| pyqtgraph | (existing) | 2D plot widget for spectrum plot and chromaticity diagram | Already used for heatmap + angular distribution plots |

### Supporting (no new packages — implement in pure numpy)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| scipy (optional) | — | `scipy.interpolate.interp1d` for spectral table lookup | Only if numpy `np.interp` proves insufficient; prefer np.interp for minimal deps |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pure numpy CIE integration | colour-science (pip) | colour-science has authoritative data but adds ~20 MB dependency; pure numpy with inline CIE tables (already in spectral.py) is sufficient and keeps install simple |
| Robertson's CCT | McCamy's approximation | McCamy is a closed-form polynomial (~1% error for 2000–12500 K); Robertson requires table lookup but is more accurate across the full range; either works |
| pyqtgraph scatter plot (chromaticity) | matplotlib embedded | pyqtgraph is already used everywhere; no matplotlib dep needed; gamut outline from CIE spectral locus can be drawn as a PlotCurveItem |

**Installation:** No new packages required. All spectral math is numpy; GUI uses existing PySide6 + pyqtgraph.

---

## Architecture Patterns

### Recommended Project Structure (changes only)

```
backlight_sim/
├── core/
│   └── project_model.py          # add: spd_profiles dict, spectral_material_data dict
├── sim/
│   └── spectral.py               # add: get_spd_from_project(), blackbody_spd(),
│                                 #      xyz_per_pixel(), xy_per_pixel(), uv_per_pixel(),
│                                 #      cct_robertson(), compute_color_kpis()
├── io/
│   └── project_io.py             # add: serialize/deserialize spd_profiles + spectral_material_data
└── gui/
    ├── spectral_data_panel.py    # NEW: combined SPD + material spectral table tab
    ├── heatmap_panel.py          # extend: Color Uniformity KPI section, click-to-inspect
    └── main_window.py            # add: spectral_data_panel tab, pass spd_profiles to tracer
```

### Pattern 1: Custom SPD Lookup in Tracer (SPEC-01 gap)

**What:** `sample_wavelengths()` currently only knows built-in SPD names ("white", "warm_white", etc.). When a source's `spd` field references a custom profile (user-imported CSV), the tracer falls back to flat white. The fix is to pass the project's `spd_profiles` dict into the tracer and resolve custom SPDs before sampling.

**Current code path:**
```python
# sim/spectral.py  — get_spd() is only built-ins
def get_spd(name: str) -> tuple[np.ndarray, np.ndarray]:
    if name in BUILTIN_SPDS: ...
    if name.startswith("mono_"): ...
    return _spd_flat()   # <-- custom names silently fall back

# sim/tracer.py  — _run_single() line 340
wavelengths = sample_wavelengths(n, source.spd, self.rng)
# ↑ no project spd_profiles passed in
```

**Fix pattern:**
```python
# sim/spectral.py
def get_spd_from_project(name: str, spd_profiles: dict) -> tuple[np.ndarray, np.ndarray]:
    """Resolve SPD from project profiles first, then built-ins, then flat fallback."""
    if name in spd_profiles:
        profile = spd_profiles[name]
        lam = np.asarray(profile["wavelength_nm"], dtype=float)
        intensity = np.asarray(profile["intensity"], dtype=float)
        return lam, intensity
    return get_spd(name)   # existing built-in lookup

# sim/tracer.py — pass spd_profiles to sample_wavelengths
spd_profiles = getattr(self.project, "spd_profiles", {})
wavelengths = sample_wavelengths(n, source.spd, self.rng,
                                  spd_profiles=spd_profiles)
```

### Pattern 2: Wavelength-Dependent Material Interpolation (SPEC-04)

**What:** `_bounce_surfaces()` uses scalar `mat.reflectance` for all rays. With spectral material tables, reflectance varies per wavelength. The pattern is per-ray lookup via `np.interp` into the material's spectral table.

**Data model for spectral_material_data:**
```python
# Project.spectral_material_data format (matches angular_distributions pattern):
# { mat_name: { "wavelength_nm": [...], "reflectance": [...], "transmittance": [...] } }
```

**Interpolation in `_bounce_surfaces()`:**
```python
# For rays hitting a surface with spectral data, at wavelengths `ray_wl` (N,):
spec = project.spectral_material_data.get(mat.name)
if spec is not None and ray_wl is not None:
    wl_table = np.asarray(spec["wavelength_nm"])
    r_table  = np.asarray(spec["reflectance"])
    t_table  = np.asarray(spec.get("transmittance", np.zeros_like(r_table)))
    r_vals = np.interp(ray_wl, wl_table, r_table)   # per-ray reflectance
    t_vals = np.interp(ray_wl, wl_table, t_table)   # per-ray transmittance
else:
    r_vals = np.full(len(hit_idx), mat.reflectance)
    t_vals = np.full(len(hit_idx), mat.transmittance)
weights[hit_idx] *= r_vals   # replace scalar multiply
```

Wavelengths must be threaded through `_bounce_surfaces()` as an argument: `wavelengths[hit_idx]`.

### Pattern 3: Multiprocessing Spectral Grid Merge (SPEC-02 gap)

**What:** `_run_multiprocess()` creates `DetectorResult` without `grid_spectral` (line 163) and merges only `result["grids"]` which has no spectral key. The spectral path is fully absent from the MP code.

**Fix:** `_run_multiprocess()` must:
1. Detect `has_spectral` the same way `_run_single()` does
2. Init `grid_spectral` on each `DetectorResult`
3. Return `grid_spectral` from `_trace_single_source()` in the dict
4. Merge `grid_spectral` in the accumulator loop

```python
# _run_multiprocess() init
has_spectral = any(s.spd != "white" for s in sources)
n_spec_bins = N_SPECTRAL_BINS if has_spectral else 0
for det in detectors:
    grid = np.zeros(...)
    grid_spectral = np.zeros((det.resolution[1], det.resolution[0], n_spec_bins)) if has_spectral else None
    det_results[det.name] = DetectorResult(..., grid_spectral=grid_spectral)

# merge loop
for det_name, grid_data in result["grids"].items():
    ...
    if has_spectral and "grid_spectral" in grid_data and grid_data["grid_spectral"] is not None:
        det_results[det_name].grid_spectral += grid_data["grid_spectral"]
```

**Known blocker (from STATE.md):** "Phase 2: Add single-thread guard before enabling spectral + multiprocessing together." The guard is `if has_spectral and settings.use_multiprocessing: warn/disable MP`. Implement the guard in `run()` before routing to `_run_multiprocess`.

### Pattern 4: CIE Colorimetry KPIs (SPEC-05)

**What:** Per-pixel XYZ → xy (CIE 1931) → u'v' (CIE 1976) → CCT. All computed in pure numpy from `grid_spectral`.

**Helper functions to add to `sim/spectral.py`:**

```python
def xyz_per_pixel(spectral_grid: np.ndarray, wavelengths: np.ndarray) -> np.ndarray:
    """Return (ny, nx, 3) XYZ image from spectral grid."""
    # Already implemented via: spectral_grid @ xyz_weights
    # xyz_weights computed as in spectral_grid_to_rgb()
    ...

def xy_per_pixel(xyz: np.ndarray) -> np.ndarray:
    """CIE 1931 (x, y) chromaticity. Returns (ny, nx, 2). Safe for zero-sum pixels."""
    s = xyz.sum(axis=-1, keepdims=True)
    s = np.where(s > 0, s, 1.0)
    return xyz[..., :2] / s   # x = X/(X+Y+Z), y = Y/(X+Y+Z)

def uv_per_pixel(xyz: np.ndarray) -> np.ndarray:
    """CIE 1976 u'v' chromaticity. Returns (ny, nx, 2)."""
    X, Y, Z = xyz[..., 0], xyz[..., 1], xyz[..., 2]
    denom = X + 15*Y + 3*Z
    denom = np.where(denom > 0, denom, 1.0)
    u_prime = 4*X / denom
    v_prime = 9*Y / denom
    return np.stack([u_prime, v_prime], axis=-1)

def cct_robertson(xy: np.ndarray) -> np.ndarray:
    """Robertson (1968) CCT from (x, y) chromaticity. Returns scalar array (same shape minus last dim)."""
    # Robertson isotherms table (31 entries from 1000 K to ∞)
    # Returns CCT per pixel in Kelvin
    ...
```

**delta-CCx/CCy computation:**
```python
# delta_cc = max(xy) - min(xy) across detector pixels, per channel
xy_full = xy_per_pixel(xyz_img)
delta_ccx = float(xy_full[..., 0].max() - xy_full[..., 0].min())
delta_ccy = float(xy_full[..., 1].max() - xy_full[..., 1].min())
```

**Center fraction delta-CC (matches existing uniformity pattern):**
```python
def _color_uniformity_in_center(xy_grid: np.ndarray, fraction: float):
    """Returns delta-CCx, delta-CCy in the central fraction area."""
    ny, nx = xy_grid.shape[:2]
    f_side = float(np.sqrt(fraction))
    cy, cx = ny // 2, nx // 2
    half_y = max(1, int(ny * f_side / 2))
    half_x = max(1, int(nx * f_side / 2))
    roi = xy_grid[cy-half_y:cy+half_y, cx-half_x:cx+half_x]
    return float(roi[...,0].max()-roi[...,0].min()), float(roi[...,1].max()-roi[...,1].min())
```

### Pattern 5: Chromaticity Diagram Widget (SPEC-03)

**What:** Use `pyqtgraph.PlotWidget` (already imported everywhere). Draw the CIE 1931 spectral locus from the precomputed `_CIE_LAMBDA`/`_CIE_X`/`_CIE_Y` data as a PlotCurveItem, then overlay per-pixel chromaticity as a ScatterPlotItem.

**Spectral locus xy coordinates (from existing `_CIE_LAMBDA`, `_CIE_X`, `_CIE_Y`, `_CIE_Z`):**
```python
from backlight_sim.sim.spectral import _CIE_X, _CIE_Y, _CIE_Z
s = _CIE_X + _CIE_Y + _CIE_Z
# Avoid div-by-zero at 780 nm end
s = np.where(s > 0, s, 1.0)
locus_x = _CIE_X / s
locus_y = _CIE_Y / s
# Close the locus (line of purples)
locus_x = np.append(locus_x, locus_x[0])
locus_y = np.append(locus_y, locus_y[0])
```

**Widget placement (Claude's discretion):** Recommend a `QSplitter` in the Spectral Data tab — left side: SPD/material table editor, right side: chromaticity diagram. The per-pixel spectrum popup triggered by clicking the heatmap image via `pyqtgraph.ImageItem.mouseClickEvent` is a clean approach that does not require a dedicated side panel.

### Pattern 6: Blackbody SPD Generator (Planckian)

**What:** Given CCT in Kelvin, compute spectral radiance `B(λ, T) ∝ λ^(-5) / (exp(hc/λkT) − 1)` and normalize.

```python
def blackbody_spd(cct_K: float, n_bins: int = N_SPECTRAL_BINS) -> tuple[np.ndarray, np.ndarray]:
    """Planckian SPD at color temperature cct_K (Kelvin). Normalized to peak = 1."""
    lam = np.linspace(LAMBDA_MIN, LAMBDA_MAX, n_bins) * 1e-9  # m
    h = 6.626e-34; c = 2.998e8; k = 1.381e-23
    exponent = (h * c) / (lam * k * cct_K)
    spd = lam**(-5) / (np.exp(exponent) - 1.0)
    lam_nm = lam * 1e9
    return lam_nm, spd / spd.max()
```

This is pure physics — no library needed.

### Pattern 7: Project Data Model Extension (SPEC-01, SPEC-04)

**Two new dict fields on `Project`:**
```python
@dataclass
class Project:
    ...
    # SPD profiles: { name: {"wavelength_nm": [...], "intensity": [...]} }
    spd_profiles: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    # Material spectral data: { mat_name: {"wavelength_nm": [...], "reflectance": [...], "transmittance": [...]} }
    spectral_material_data: dict[str, dict[str, list[float]]] = field(default_factory=dict)
```

**JSON serialization** follows the exact same pattern as `angular_distributions` — already a plain dict of lists, so `json.dumps` handles it directly. Load with `.get("spd_profiles", {})` for backwards compatibility.

### Anti-Patterns to Avoid

- **Wavelength threading via global state:** Don't store `wavelengths` as an instance variable on `RayTracer`. Thread it explicitly through `_bounce_surfaces()` as a parameter; only the `has_spectral` sources trigger allocation.
- **Re-running spectral integration on display mode change:** The heatmap already handles this correctly — `grid_spectral` is stored in `DetectorResult` and `spectral_grid_to_rgb()` is called only on display. Don't re-simulate.
- **Spectral binning using wavelength as dict key:** Keep the flat numpy array approach (`i_bin = clip(((wl - LAMBDA_MIN) / bin_width).astype(int), ...)`) — it vectorizes correctly. Never convert to Python dict per wavelength.
- **Material spectral tables with float dict keys in JSON:** Store as `{"wavelength_nm": [380, 390, ...], "reflectance": [0.9, 0.88, ...]}` parallel lists, not `{"380": 0.9, "390": 0.88}`.
- **Enabling MP + spectral without the guard:** The STATE.md explicitly flags this as a known concern. The guard must be in `run()` before routing to `_run_multiprocess`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CIE observer data | Custom CMF tables from scratch | Existing `_CIE_X/Y/Z` arrays in `sim/spectral.py` | Already validated 10 nm data at 380–780 nm |
| sRGB conversion | Custom matrix | Existing `spectral_grid_to_rgb()` in `sim/spectral.py` | Already has D65 matrix + gamma correction |
| Spectral locus coordinates | External data file | Compute from existing `_CIE_X/Y/Z` inline | Avoids additional data assets |
| Plot widget | Matplotlib embed | `pyqtgraph.PlotWidget` | Already used in `angular_distribution_panel.py` for same use case |
| CDF inversion for SPD sampling | Custom RNG loop | `np.interp(rng.uniform(n), cdf, lam)` | Already used in `sample_wavelengths()` — same pattern |

**Key insight:** The spectral math layer is mostly written. Phase 2 completes it; it does not replace it.

---

## Common Pitfalls

### Pitfall 1: Wavelengths not passed into `_bounce_surfaces`
**What goes wrong:** Wavelength-dependent material lookup silently uses scalar fallback for all rays because `wavelengths[hit_idx]` was never threaded into the bounce function.
**Why it happens:** `_bounce_surfaces()` currently takes no wavelengths argument; adding spectral material support requires changing its signature.
**How to avoid:** Update the method signature to accept `wavelengths: np.ndarray | None = None` and plumb it through the call site in `_run_single()`.
**Warning signs:** Tests pass but per-wavelength reflectance has no effect on output — check that modifying a material's spectral table changes `grid_spectral` distribution.

### Pitfall 2: Multiprocessing spectral merge missing
**What goes wrong:** Running with `use_multiprocessing=True` and a non-white SPD produces a zero `grid_spectral` (all None) because `_run_multiprocess()` never initializes or merges spectral data.
**Why it happens:** The MP code predates the spectral feature; STATE.md explicitly calls this out as a known concern.
**How to avoid:** Add the single-thread guard AND implement the full MP spectral merge. The guard (disable MP when spectral is active) is the safe option for 02-01; full MP spectral support is an enhancement within that plan.
**Warning signs:** `result.detectors[name].grid_spectral is None` after MP run with non-white SPD.

### Pitfall 3: Custom SPD names resolve to flat white
**What goes wrong:** User imports a custom LED SPD CSV, assigns it to a source, runs simulation — all wavelengths are uniform because `get_spd()` falls back to `_spd_flat()`.
**Why it happens:** `sample_wavelengths()` takes `spd_name: str` but has no access to `project.spd_profiles`. The lookup chain only covers built-in names.
**How to avoid:** Add `spd_profiles` parameter to `sample_wavelengths()` and resolve custom names before built-in lookup.
**Warning signs:** Spectral color image looks identical regardless of SPD selection.

### Pitfall 4: spectral_material_data lookup when mat resolves through OpticalProperties
**What goes wrong:** Phase 1 introduced `OpticalProperties` as a separate object from `Material`. A surface may have `optical_properties_name` set — its optical behavior comes from `OpticalProperties`, but `spectral_material_data` keys on `mat_name`. The per-ray reflectance lookup silently ignores the spectral table.
**Why it happens:** `_resolve_optics()` in tracer returns the `OpticalProperties` object, not the `Material`. The spectral table dict keys must match what `_resolve_optics()` returns.
**How to avoid:** Key `spectral_material_data` by `OpticalProperties` name for surfaces with an explicit `optical_properties_name`, and by `Material` name for the legacy path. Or key by surface's resolved optics name. Clarify this convention in the data model.
**Warning signs:** Assigning a spectral table to a surface material has no effect when that surface has an explicit `optical_properties_name`.

### Pitfall 5: Chromaticity diagram pixel-flooding with high-resolution detectors
**What goes wrong:** A 100×100 detector produces 10,000 scatter points on the chromaticity diagram — too slow/dense to be useful.
**Why it happens:** Naive approach passes all (ny×nx) xy pairs to `ScatterPlotItem`.
**How to avoid:** Downsample or subsample: use `grid[::4, ::4]` for display, or compute a 2D histogram of chromaticity space and display as a density image rather than individual points.
**Warning signs:** UI freezes or becomes unresponsive when switching to Color mode for large detector grids.

### Pitfall 6: Robertson CCT table edge cases
**What goes wrong:** Robertson's method fails for chromaticity coordinates outside the 1000–25000 K range (very saturated colors, pure monochromatic pixels).
**Why it happens:** Robertson isotherms don't extrapolate gracefully.
**How to avoid:** Clamp CCT output to [1000, 25000] K range, and return `float("nan")` or 0 for pixels with near-zero luminance (Y < threshold).
**Warning signs:** CCT display shows extreme values (0 K or 1e6 K) for unlit detector pixels.

---

## Code Examples

### Vectorized XYZ Integration (from existing `spectral_grid_to_rgb`, extracted pattern)
```python
# Source: backlight_sim/sim/spectral.py — spectral_grid_to_rgb()
# Build CIE XYZ weight matrix once (n_bins, 3) from inline CMF arrays
xyz_weights = np.zeros((n_bins, 3), dtype=float)
for i, wl in enumerate(wavelengths):
    x = np.interp(wl, _CIE_LAMBDA, _CIE_X)
    y = np.interp(wl, _CIE_LAMBDA, _CIE_Y)
    z = np.interp(wl, _CIE_LAMBDA, _CIE_Z)
    xyz_weights[i] = [x, y, z]
# Integrate: (ny, nx, 3) = (ny, nx, n_bins) @ (n_bins, 3)
xyz_img = spectral_grid @ xyz_weights
```

### Spectral Bin Accumulation (existing in `_accumulate`)
```python
# Source: backlight_sim/sim/tracer.py — _accumulate()
n_bins = len(spec_centers)
bin_width = (LAMBDA_MAX - LAMBDA_MIN) / max(n_bins - 1, 1)
i_bin = np.clip(((wavelengths - LAMBDA_MIN) / bin_width).astype(int), 0, n_bins - 1)
for b in range(n_bins):
    bmask = i_bin == b
    if bmask.any():
        np.add.at(result.grid_spectral[:, :, b], (iy[bmask], ix[bmask]), hit_weights[bmask])
```

### SPD CDF Inversion (existing in `sample_wavelengths`)
```python
# Source: backlight_sim/sim/spectral.py — sample_wavelengths()
cdf = np.cumsum(intensity)
cdf = cdf / cdf[-1]
u = rng.uniform(size=n)
wavelengths = np.interp(u, cdf, lam)
```

### Angular Distribution Panel Pattern (template for Spectral Data Panel)
- Selector `QComboBox` + Import/Export/Delete buttons
- `QTableWidget` with (wavelength_nm, value) columns
- `pyqtgraph.PlotWidget` live preview updated on table edit
- `Signal distributions_changed` to notify `MainWindow` on edits
- `_loading_table: bool` guard + `blockSignals()` on selector changes
- See: `backlight_sim/gui/angular_distribution_panel.py`

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Scalar material R/T per bounce | Per-wavelength R/T interpolation | Phase 2 | SPEC-01 and SPEC-04 fulfilled |
| `get_spd()` built-ins only | `get_spd_from_project()` checks project SPD dict first | Phase 2 | Custom user SPDs work |
| MP merge: grid only | MP merge: grid + grid_spectral | Phase 2 | Spectral data survives multiprocessing |
| Single "Spectral Color" display mode (wired but no supporting data structures) | Full SPD/material spectral editor + color KPI dashboard | Phase 2 | SPEC-02, SPEC-03, SPEC-05 fulfilled |

**Not deprecated:** The existing `grid_spectral` field on `DetectorResult`, `spectral_grid_to_rgb()`, and the heatmap "Spectral Color" combo item are all kept and used as-is.

---

## Open Questions

1. **Spectral material data keying by OpticalProperties vs Material name**
   - What we know: `_resolve_optics()` returns `OpticalProperties` when a surface has `optical_properties_name` set; `Material` otherwise. Spectral tables need a matching key.
   - What's unclear: Should `spectral_material_data` key by `OpticalProperties` name or `Material` name? Does a user expect to set spectral data on the "material" or on the "optical properties"?
   - Recommendation: Key by whatever name `_resolve_optics()` returns (i.e., the effective optics object name). Add a helper `_get_spectral_optics_name(surf)` that mirrors `_resolve_optics()`. Document this in the Spectral Data panel UI.

2. **Chromaticity diagram density rendering for large detectors**
   - What we know: 100×100 detector = 10k points; pyqtgraph ScatterPlotItem handles this but may lag on slower machines.
   - What's unclear: Performance threshold; whether downsampling (every Nth pixel) or 2D histogram binning is more appropriate.
   - Recommendation: Start with subsampling (`xy[::4, ::4]` → max ~625 points) with a note in the widget. If users request higher fidelity, switch to 2D histogram binned image.

3. **CCT method selection (Claude's discretion)**
   - What we know: Robertson's method (1968) uses a 31-entry isotherm table and handles 1000–25000 K accurately; McCamy's is a cubic polynomial valid for 2856–6500 K (narrower range).
   - Recommendation: Implement Robertson's — it covers the full visible LED range (warm white ~2700 K to cool white ~6500 K and beyond) and the table is compact (31 rows, easily inlined).

---

## Validation Architecture

*(Skipped — `workflow.nyquist_validation` not set in config.json)*

However, the existing test suite in `backlight_sim/tests/test_tracer.py` (20 tests, pytest) should be extended. Recommended test additions for Phase 2:

- `test_spectral_grid_accumulated_for_non_white_spd()` — verifies `grid_spectral` is non-None and non-zero when source has `spd="warm_white"`
- `test_custom_spd_profile_used_in_sampling()` — verifies distribution of sampled wavelengths matches a project-stored SPD
- `test_spectral_material_reflectance_varies_per_wavelength()` — verifies that flux in green bins differs from red bins when material has a wavelength-dependent R table
- `test_mp_spectral_grid_merge_equals_single_thread()` — verifies MP result matches single-thread result for spectral grids
- `test_xy_per_pixel_sums_to_one()` — verifies x + y ≤ 1 for all lit pixels
- `test_cct_robertson_range()` — verifies CCT for warm_white ~2700–3300 K, cool_white ~5500–7000 K

Run with: `pytest backlight_sim/tests/ -x`

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `backlight_sim/sim/spectral.py`, `backlight_sim/sim/tracer.py`, `backlight_sim/core/detectors.py`, `backlight_sim/core/sources.py`, `backlight_sim/core/project_model.py`, `backlight_sim/gui/heatmap_panel.py`, `backlight_sim/gui/angular_distribution_panel.py`, `backlight_sim/io/project_io.py`
- `.planning/phases/02-spectral-engine/02-CONTEXT.md` — locked user decisions
- `.planning/STATE.md` — "Phase 2: Add single-thread guard before enabling spectral + multiprocessing together" known concern
- CIE 1931 standard colorimetry: XYZ → xy → u'v' formulas are definitional (ISO 11664-1, ISO 11664-3)

### Secondary (MEDIUM confidence)
- Robertson (1968) CCT algorithm: widely reproduced in colorimetry textbooks and implementations; table and formula are stable and standard
- Planckian radiator formula: h=6.626e-34, c=2.998e8, k=1.381e-23 constants are CODATA-standard; formula `B(λ,T) ∝ λ^-5 / (exp(hc/λkT) - 1)` is definitional

### Tertiary (LOW confidence)
- None — all findings verified against codebase or physical constants

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all existing dependencies confirmed by requirements.txt and import inspection
- Architecture: HIGH — patterns derived directly from existing working code in same repo (angular_distribution_panel, spectral.py, tracer.py)
- Pitfalls: HIGH — gaps identified by direct gap analysis of existing code paths vs. requirements; MP gap confirmed in STATE.md

**Research date:** 2026-03-14
**Valid until:** 2026-06-14 (stable domain — CIE colorimetry and project architecture are not fast-moving)
