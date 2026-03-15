# Phase 2: Spectral Engine - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Engineers can run wavelength-aware simulations and see the detector result as a color image with color uniformity KPIs. Each ray carries a wavelength sampled from the source SPD, material reflectance/transmittance vary with wavelength, and the detector accumulates spectral flux for CIE XYZ color rendering.

Requirements: SPEC-01 through SPEC-05.

</domain>

<decisions>
## Implementation Decisions

### Spectral Material Definition
- Wavelength-dependent properties defined as tables of (wavelength_nm, value) pairs — same pattern as angular distributions
- Both reflectance and transmittance are wavelength-dependent; absorption derived as 1 - R - T
- Spectral tables are optional: materials without spectral data fall back to their scalar reflectance/transmittance values for all wavelengths (backward-compatible)
- GUI: dedicated spectral tab (not inline in properties panel) for managing material spectral properties

### Source SPD Management
- Custom SPD profiles via CSV import + table editor, same pattern as angular distributions
- Combined "Spectral Data" tab manages both source SPDs and material spectral tables in two sub-sections
- Include a blackbody (Planckian) SPD generator: user inputs a CCT (e.g. 3000K, 6500K) and the app generates the spectral curve
- SPD profiles stored inside the project JSON file (alongside angular distributions) — self-contained projects
- Built-in SPDs remain: white, warm_white, cool_white, mono_<nm>

### Color Result Visualization
- True-color image from CIE XYZ integration: each pixel's spectral bins are integrated through CIE 1931 color matching functions to produce sRGB — shows what the backlight actually looks like
- Instant toggle between intensity/color views after simulation — no re-run required (spectral grid always accumulated when any source has non-white SPD)
- CIE 1931 chromaticity diagram widget alongside the color heatmap — shows distribution of pixel chromaticity coordinates as scatter points on the gamut outline
- Click-to-inspect per-pixel spectrum: clicking a pixel shows its spectral power distribution as a line plot (wavelength vs flux)

### Color Uniformity KPIs
- Three metric families: delta-CCx/CCy (CIE 1931), delta-u'v' (CIE 1976 perceptually uniform), and CCT (correlated color temperature average + range)
- CRI not included in this phase (compute-heavy, lower priority)
- Computed over both full detector AND center fractions (1/4, 1/6, 1/10) — matches existing intensity uniformity pattern
- Displayed in a separate collapsible "Color Uniformity" section in the KPI dashboard, below intensity metrics
- Color KPIs included in CSV export and HTML report exports

### Claude's Discretion
- Chromaticity diagram widget library choice and layout within the spectral tab
- Per-pixel spectrum plot widget placement (popup, side panel, or tooltip)
- Spectral bin count and interpolation method for material property lookup
- Multiprocessing path update for spectral accumulation (architecture choice)
- CCT computation method (Robertson's, Ohno's, or McCamy's approximation)

</decisions>

<specifics>
## Specific Ideas

- The combined spectral tab should feel like the existing Angular Distribution tab — table editing, import/export, normalization, plot preview
- Blackbody generator is a common LED engineering workflow: type CCT, get SPD
- Click-to-inspect spectrum helps diagnose color non-uniformity root causes (e.g. which wavelengths are missing in a corner)
- Color uniformity is an industry-standard BLU metric — delta-CCx/CCy appears on every backlight spec sheet

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `sim/spectral.py`: CIE 1931 observer data, built-in SPDs (white/warm/cool/mono), `sample_wavelengths()`, `spectral_grid_to_rgb()`, `spectral_bin_centers()` — core spectral pipeline exists
- `core/sources.py`: `PointSource.spd` field already wired (default "white")
- `core/detectors.py`: `DetectorResult.grid_spectral` (ny,nx,n_bins) and `grid_rgb` fields already defined
- `gui/angular_distribution_panel.py`: table editor + import/export + plot pattern — reusable for SPD and material spectral table editing
- `gui/heatmap_panel.py`: "Spectral Color" display mode combo already exists with `spectral_grid_to_rgb()` integration
- `gui/properties_panel.py`: SPD combo selector on SourceForm (white/warm_white/cool_white/mono + editable)

### Established Patterns
- Angular distributions: `{name: {theta_deg: [...], intensity: [...]}}` stored in project JSON — same pattern for SPDs and material spectral tables
- `_accumulate()` in tracer.py: already bins wavelengths into spectral grid channels
- Heatmap KPI dashboard: collapsible QGroupBox sections with label grids — color KPIs follow same pattern
- Export: `io/report.py` HTML report + heatmap_panel CSV/PNG export — extend with color metrics

### Integration Points
- `sim/tracer.py`: wavelength-dependent material lookup needed in `_bounce_surfaces()` — currently uses scalar `mat.reflectance`/`mat.transmittance`
- `sim/tracer.py` `_trace_single_source()`: multiprocessing path lacks spectral accumulation — needs spectral grid merge
- `gui/main_window.py`: new "Spectral Data" tab needs to be added alongside existing tabs
- `core/project_model.py`: `Project` needs a new dict field for spectral material data and custom SPDs
- `io/project_io.py`: serialization for spectral material tables and custom SPDs

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-spectral-engine*
*Context gathered: 2026-03-14*
