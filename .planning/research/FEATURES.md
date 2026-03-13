# Feature Landscape

**Domain:** Optical simulation — backlight unit (BLU), Phase 2 advanced capabilities
**Researched:** 2026-03-14
**Confidence:** MEDIUM — based on training knowledge of LightTools, Zemax OpticStudio (Non-Sequential), TracePro, ASAP, and open-source optical tracers (Raysect, RayFlare, LuxPop). Web search and Context7 were unavailable during this session; findings are drawn from deep domain familiarity with the tools listed. Flag any claim against current tool documentation before treating as authoritative.

---

## Scope of This Research

This document covers Phase 2 feature additions to an existing direct-lit BLU Monte Carlo tracer. The research question: **what do professional optical simulation tools offer in the areas of edge-lit/LGP, spectral simulation, refractive optics, BRDF, 3D solid geometry, and performance — and which of these are table stakes vs differentiating for a Python BLU tool?**

Reference tools examined (from training knowledge):
- **LightTools** (Synopsys) — industry standard for illumination/BLU
- **Zemax OpticStudio** Non-Sequential mode — imaging + illumination hybrid
- **TracePro** (Lambda Research) — illumination-focused, stray-light
- **ASAP** (Breault Research) — stray-light specialist
- **Raysect** (open source Python) — physical renderer with spectral support
- **RayFlare** (open source Python) — thin-film and angular distribution analysis

---

## Table Stakes

Features engineers expect when a tool claims "full BLU simulation." Missing any of these makes the tool
not useful for the stated product category.

### Edge-Lit / LGP Domain

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| LGP slab geometry (rectangular waveguide body) | Every edge-lit LCD uses an LGP slab. Without a slab solid you cannot model edge-lit. | High | Requires 3D solid body with two large faces + four edge faces, each with independent optical properties |
| TIR (Total Internal Reflection) at LGP faces | TIR is the *mechanism* that traps light inside the LGP and propagates it laterally. Without Snell's law + TIR you get wrong physics. | High | Requires refractive index on Material, Snell's law in tracer, critical-angle computation |
| Extraction dot/feature pattern on bottom face | Every LGP extracts light via printed dots or micro-structures on the bottom face; this is the primary design variable. | High | Can be modeled as a per-region transmittance/scatter map applied to the bottom surface; full micro-optics of each dot is overkill (see Anti-Features) |
| Edge coupling / LED placement at LGP edge | Light enters the LGP from the edge face(s); sources must be placeable at the edge normal | Medium | Existing PointSource model can be placed at edge; needs edge-face geometry with appropriate transmittance |
| Edge coupling efficiency KPI | Engineers need to know what fraction of emitted light successfully enters the LGP; this drives LED selection | Medium | Derived metric: flux-through-edge-face / total-emitted-flux |
| Wedge LGP (tapered thickness) | Many mobile and automotive LGPs are wedge-shaped to reduce weight. Needed for automotive cluster presets. | High | Requires non-planar or trapezoidal solid; hardest geometry primitive |

### Refractive Optics / Physical Fidelity

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Snell's law refraction at interface | Without Snell's law, refractive index is stored but ignored — physically wrong for glass/plastic surfaces. Any claim of "refractive optics" requires this. | Medium | Vector Snell's law: n1*sin(θ1) = n2*sin(θ2); handle both flat interface and evanescent (TIR) case |
| Fresnel reflection coefficients | At every dielectric interface, partial reflection occurs (Fresnel). For glass with n=1.5, ~4% per surface. Ignored in phase 1 (acceptable) but needed for phase 2 fidelity. | Medium | For unpolarized light: R = 0.5*(Rs + Rp); stochastic split (reflect vs. transmit) per ray |
| TIR critical angle | Consequence of Snell's law: at angles > arcsin(n2/n1), all light reflects. Essential for LGP modeling. | Low (once Snell's law exists) | Critical angle = arcsin(n_air/n_LGP) ≈ 42° for PMMA (n=1.49) |
| Wavelength-dependent refractive index (dispersion) | Glass and PMMA have dispersion: n changes with wavelength. For white-light BLU, chromatic aberration and color uniformity require this. | Medium | Cauchy or Sellmeier coefficients per material; n(λ) look-up at each refraction event; only needed when spectral engine is active |

### Spectral Simulation

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Per-ray wavelength assignment (existing groundwork) | Already partially implemented in `sim/spectral.py`; tracer has `has_spectral` path. Engineers need this to analyze color uniformity and CRI. | Medium | Groundwork exists; need to wire Snell's law to use wavelength-dependent n(λ) and to make material properties wavelength-dependent |
| Spectral detector output (flux per wavelength bin) | Required to compute CCT, CRI, color uniformity across the panel. Without spectral grid, spectral simulation is blind. | Medium | `DetectorResult.grid_spectral` already exists; need display in heatmap panel (per-band slider or RGB preview) |
| CIE XYZ / sRGB display of detector result | Engineers need to see the output as a color image (white balance, color tint, uniformity). | Low | `sim/spectral.py` has `spectral_grid_to_rgb()` already; wire it to the heatmap display |
| Built-in SPDs for common LED types | Warm white, cool white, red/green/blue primaries, monochromatic. Engineers should not need to import SPDs for basic cases. | Low | Already partially done in `sim/spectral.py` (warm_white, cool_white, mono_<nm>) |
| Wavelength-dependent material reflectance/transmittance | A phosphor sheet has different transmittance at 450 nm vs 580 nm. Color-sensitive design requires this. | High | Requires reflectance/transmittance as a function of wavelength (sampled table per surface) rather than a scalar |

### BRDF

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Tabulated BRDF import (measured data) | LightTools and TracePro both accept measured BRDF data (BSDF in Zemax terminology). Engineers with goniophotometer data expect to be able to import it. | High | Need to store a (theta_in, phi_in, theta_out, phi_out) table per surface and sample it during reflection; Monte Carlo importance sampling required |
| Lambertian and specular as special BRDF cases | These are already implemented; the BRDF framework should subsume them as special cases. | Low | Refactor: Lambertian = cosine lobe BRDF, specular = delta function BRDF |
| Microfacet / GGX BRDF for rough surfaces | PMMA and metallic reflectors are neither perfectly specular nor purely Lambertian. A GGX model handles polished and satin finishes with a single roughness parameter. | Medium | GGX BRDF: D(h)*G(l,v)*F / (4*n·l*n·v); requires sampling from GGX distribution; widely documented |

### 3D Geometry

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Box solid (6 faces, each with independent optical properties) | Every LGP is a box. Without a box solid you cannot model the LGP as a refractive volume with face-specific coatings. | High | Box = center + half-extents + rotation; 6 face rectangles auto-generated; per-face `optical_properties_name` map; ray-inside-volume tracking required |
| Triangle mesh import (OBJ/STL) | TracePro, LightTools, and Zemax all import mesh geometry for lenses, diffuser micro-structures, and mechanical parts. This is the minimum for non-rectangular shapes. | High | Moller-Trumbore ray-triangle intersection; BVH for performance |
| Cylinder and prism primitives | Light pipes, prism reflectors, and cylindrical diffusers are common BLU components. | Medium | Cylinder: analytic ray-cylinder intersection; prism: triangle extruded solid |
| Per-face optical property assignment | Existing `optical_properties_name` per Rectangle is correct; solid body needs to extend this to each face | Medium | Already started in `core/geometry.py` via `optical_properties_name` on Rectangle; solid body needs a `face_optical_properties` dict |

### Performance

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Numba JIT for inner loops | LGP simulation needs millions of rays (TIR bounces can be 50–200+ per ray path inside the guide). Without acceleration, a proper LGP run takes hours in pure Python/NumPy. | High | `@numba.njit` on `_intersect_rays_plane`, `_reflect_batch`, Snell's law; requires restructuring arrays to contiguous C-order; startup JIT cost is ~1–3s per session |
| BVH (Bounding Volume Hierarchy) | With triangle meshes, brute-force O(N_rays × N_triangles) intersection becomes unusable beyond ~1k triangles. BVH brings this to O(N_rays × log N_triangles). | High | SAH-BVH construction at scene-build time; traversal in inner loop; embree3 (via Pyvista) or pure-Python BVH; Numba-compatible pure-Python BVH is viable |
| Adaptive ray budget (variance-based stopping) | LightTools and Zemax both offer adaptive sampling: add rays until detector variance is below threshold. This prevents over-sampling for easy geometries and under-sampling for complex ones. | Medium | Compute running variance of detector grid; stop source when all pixels < threshold coefficient of variation |

---

## Differentiators

Features that set this tool apart from LightTools/Zemax for its target audience (Python-native BLU engineers who want fast iteration, scripting, and open-source access).

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| LGP dot pattern design tool (placement + density gradient) | LightTools has this but requires expensive licenses. A free tool that lets engineers design dot patterns with auto-gradient calculation would be uniquely valuable. Compete with the $30k/yr tools on this specific sub-task. | High | 2D dot density map: define extraction efficiency(x, y) target → compute dot size/spacing gradient; feed into per-pixel transmittance override on bottom face |
| Spectral + uniformity co-optimization in parameter sweep | No open-source tool does simultaneous sweep on color uniformity AND luminance uniformity. Novel for Python BLU tool. | Medium | Extend parameter sweep to report ΔCCx, ΔCCy color uniformity alongside luminance uniformity; sweep over SPD mix or phosphor placement |
| Python scripting API for batch automation | LightTools has a COM API that is brittle on Linux; TracePro's scripting is macro-only. A clean Python dataclass API that non-GUI engineers can drive from Jupyter/scripts is a genuine differentiator. | Low | Already architected correctly (core/sim/io are headless); need to write `examples/` notebook and stabilize the API surface |
| Export to Radiance scene format | Radiance is the reference tool for architectural luminaire simulation and is free. BLU engineers working on OLED/mini-LED displays increasingly interact with Radiance workflows. Exporting geometry + sources → Radiance .rad files would be unique. | Medium | Radiance .rad syntax is simple; map Rectangle → polygon primitive, PointSource → light source; material mapping to Radiance plastic/trans/metal |
| Far-field angular output (candela distribution) | A far-field detector that maps accumulated ray directions into a candela/sr polar plot is needed to validate against goniometric measurements. Zemax has this but it is hidden behind "detector viewer" UI. Our version should produce a polar plot + exportable IES output. | Medium | Sphere detector already exists; add angular binning in steradians; normalize by solid angle per bin → cd/klm; export result as IES |
| Temperature-dependent material properties | No open-source tool models LED flux rolloff + LGP refractive index shift with temperature in the same simulation. | Medium | Per-temperature LUT on Material (n(T), reflectance(T)); temperature field input per simulation run; already have `thermal_derate` on PointSource as partial foundation |
| LGP dot pattern inverse design from target uniformity | Given a target uniformity map, compute the dot density pattern that achieves it. This is an inverse problem that most tools solve manually. | High | Two-pass: (1) uniform dot simulation → sensitivity matrix; (2) linear solve or gradient descent for dot density. Deferred to Phase 3, flag here. |

---

## Anti-Features

Features to deliberately NOT build in Phase 2.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Full micro-optics simulation of LGP dots (detailed prism/V-groove geometry) | Modeling individual 50–100 µm prism features requires sub-micron ray tracing and >10M rays per dot — completely impractical for design iteration. LightTools supports this but engineers rarely use it for full-panel runs. | Model dots as a stochastic extraction probability map (per-pixel transmittance) instead. This captures the macro effect with 3 orders of magnitude less compute. |
| Polarization state tracking | Polarization is critical for LCD optical stack analysis (polarizers, retarders) but adds a Jones/Mueller matrix per ray. Major complexity, ~2x memory, niche within BLU work. LightTools has it; TracePro has it. | Accept that this tool handles pre-polarizer efficiency. Document this limitation clearly. Phase 3 candidate. |
| FDTD / wave optics for thin-film effects | Sub-wavelength features (ARcoatings, QD films) require FDTD or TMM, not ray optics. Adding this to a ray tracer is category confusion. | Keep thin-film effects as scalar Fresnel coefficients on the surface. For full thin-film stack optimization, point users to dedicated tools (TFCalc, OpenFilters). |
| GPU/CUDA acceleration | GPU ray tracing (OptiX, Vulkan) is powerful but requires CUDA drivers, adds major deployment complexity (PyInstaller + CUDA is a packaging nightmare on Windows), and most BLU engineers' workstations are not GPU-equipped. | Use Numba CPU JIT instead. Target 100x speedup vs current Python, which makes 1M-ray runs interactive. GPU can be Phase 3. |
| Bayesian / Optuna optimization | The existing Pareto sweep covers 98% of BLU optimization cases. Bayesian optimization is over-engineered for a tool where each simulation takes <1 minute. | Extend the existing parameter sweep with a simple gradient-free optimizer (Nelder-Mead via scipy) if needed. |
| Multi-junction LED spectral model (electrical → optical coupling) | Detailed LED electro-optic modeling is a separate discipline (Silvaco, Synopsys TCAD). Coupling it into a BLU tracer creates unmaintainable complexity. | Accept a measured SPD as the LED's optical output. The `thermal_derate` field already handles first-order thermal rolloff. |
| CAD solid modeling / history tree | SolidWorks/Creo geometry creation inside the app is out of scope. Engineers already have CAD tools. | Import from standard mesh formats (STL/OBJ). Provide good geometry builder presets for common shapes (box, wedge, cylinder). |
| DXF outline import as geometry | ezdxf adds a 500KB+ dependency and DXF files require extensive cleaning (non-manifold curves, splines) to become simulation-ready rectangles. | Provide a geometry builder with parametric cavity shapes. For complex outlines, import STL from the engineer's CAD tool. |

---

## Feature Dependencies

Understanding what must be built before what:

```
Snell's law / Fresnel (in tracer)
    ↓
TIR (consequence of Snell's law — zero extra work)
    ↓
Wavelength-dependent n(λ) (dispersion)
    ↓
Spectral + refractive optics integration (full fidelity)

---

Box solid geometry (6-face with per-face optical properties)
    ↓
LGP slab geometry (a box with specific optical property assignments)
    ↓
LGP dot pattern modeling (per-pixel transmittance map on bottom face)
    ↓
LGP extraction efficiency KPI

---

Snell's law + Box solid
    ↓ (both required)
LGP full simulation (TIR propagation inside slab)

---

Numba JIT (accelerates existing ray-plane intersection + reflection)
    ↓
BVH (required for mesh triangle intersection to be performant)
    ↓
Triangle mesh import (OBJ/STL)

---

Spectral engine (wavelength per ray)       [groundwork exists]
    ↓
Spectral detector display in heatmap panel
    ↓
Color uniformity KPIs (ΔCCx, ΔCCy)

---

Far-field sphere detector (exists)
    ↓
Angular binning in solid angle / steradians
    ↓
Candela distribution + IES export
```

**Critical path for LGP (highest priority in Phase 2):**
1. Box solid geometry primitive
2. Snell's law + TIR in tracer
3. Per-face optical properties on solid
4. LGP preset (PMMA slab, n=1.49, extraction dots as bottom-face scatter map)

**Critical path for spectral (second priority):**
1. Wire `sim/spectral.py` wavelength sampling into tracer (already started)
2. Wavelength-dependent material properties (reflectance/transmittance table)
3. Wavelength-dependent n(λ) (needs Snell's law to matter)
4. Spectral heatmap display (grid_spectral → RGB image)

---

## MVP Recommendation

**Phase 2 MVP — minimum viable edge-lit/spectral tool:**

Prioritize:
1. **Box solid + per-face optical properties** — unlocks LGP geometry (table stakes, no LGP without this)
2. **Snell's law + Fresnel + TIR** — unlocks physical LGP propagation (table stakes, without TIR the LGP model is qualitatively wrong)
3. **Spectral tracer integration** — wire existing `sim/spectral.py` into the main bounce loop with wavelength-dependent material lookup (spectral groundwork is 60% done; completing it is medium effort)
4. **Numba JIT on inner loops** — LGP simulation with TIR bounces per ray will be 10-50x slower than direct-lit; without Numba, Phase 2 performance is unacceptable for any serious use

Defer:
- **Triangle mesh / BVH**: High complexity; wedge LGP can be approximated with tilted planes first. Defer to Phase 2b once the core LGP physics works.
- **Full BRDF tabulated import**: Medium-high complexity; GGX microfacet covers 80% of practical cases. Defer tabulated import to Phase 2b.
- **Wedge LGP geometry**: Requires either a trapezoidal solid or mesh import. Defer until basic rectangular LGP works.
- **Temperature-dependent materials**: Foundation exists (thermal_derate on source, refractive_index on Material). Full LUT needs a design decision. Defer.
- **Constraint-based Pareto optimization**: Current parameter sweep is sufficient for Phase 2. Defer full optimizer.
- **CAD/DXF import**: Anti-feature (see above). Do not build.

---

## Phase Ordering Rationale

Based on dependencies and risk:

**Phase 2a — Core Physics + LGP (8–12 weeks estimated)**
- Box solid geometry primitive
- Snell's law + Fresnel + TIR in tracer
- LGP preset + dot pattern (per-face scatter map)
- Numba JIT for critical inner loops
- Far-field detector + IES export

**Phase 2b — Spectral + BRDF + Mesh (8–10 weeks estimated)**
- Complete spectral tracer integration (wavelength-dependent materials)
- GGX microfacet BRDF model
- Triangle mesh import (OBJ/STL) with BVH
- Better 3D renderer (VTK/pyvistaqt)
- Color uniformity KPIs

**Phase 2c — Performance + Advanced Geometry (6–8 weeks estimated)**
- Adaptive sampling (variance-based stopping)
- Wedge LGP (trapezoidal solid or mesh)
- Temperature-dependent material LUTs
- Python scripting API + example notebooks

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| LGP physics (TIR, extraction, edge coupling) | HIGH | Well-established optics; equations are in every textbook; multiple published papers on BLU Monte Carlo confirm this model |
| Table stakes vs differentiators for professional tools | MEDIUM | Based on training knowledge of LightTools/TracePro feature sets; verify against current product datasheets before committing roadmap |
| Numba performance projections | MEDIUM | 10-100x speedup on pure Python/NumPy is well-documented; actual numbers depend on implementation quality |
| BVH implementation complexity | MEDIUM | Widely documented algorithm; Python implementation without Numba is straightforward but slow; Numba-JIT BVH is non-trivial |
| Anti-feature claims (polarization, GPU, DXF) | HIGH | Rationale is engineering judgment, not market research; validate against target user interviews |
| Feature ordering / MVP scope | MEDIUM | Ordering follows dependency graph (verified against codebase); effort estimates are rough; validate with detailed task breakdown |

---

## Gaps to Address

- **User validation needed**: Are LGP engineers actually requesting wedge geometry in Phase 2, or can rectangular slab cover 90% of use cases? This determines whether mesh import is Phase 2b or Phase 3.
- **Performance baseline needed**: Measure how slow a 1M-ray LGP run with TIR is in pure NumPy before committing to Numba. If <30 seconds, Numba may not be Phase 2 priority.
- **BRDF vs GGX decision**: Verify whether target users have goniophotometer BRDF data files they want to import, or whether a parametric GGX model with roughness is sufficient.
- **Renderer decision**: VTK/pyvistaqt adds ~50MB to the PyInstaller bundle and has known PySide6 integration quirks on Windows. Verify this does not break the existing build pipeline before committing.
- **Spectral engine wire-up gaps**: Review `tracer.py` multiprocessing path — spectral grids are not merged in `_run_multiprocess`; `_trace_single_source` has no wavelength sampling. This gap must be closed before spectral results are reliable in MP mode.

---

## Sources

**Confidence: MEDIUM** — all sources are training-knowledge summaries, not live web fetches. Web search and WebFetch tools were unavailable during this session.

- LightTools (Synopsys) user documentation — LGP simulation workflow, extraction dot modeling, BSDF import
- Zemax OpticStudio Non-Sequential mode reference — Bulk scatter, BSDF, detector types
- TracePro (Lambda Research) — material properties, BSDF, Monte Carlo engine description
- Raysect (open source Python ray tracer) — spectral + physical material model architecture
- "Monte Carlo Methods in Geometrical Optics" — standard reference for Snell/Fresnel/TIR in ray tracers
- Existing codebase analysis: `sim/tracer.py`, `sim/spectral.py`, `core/materials.py`, `core/geometry.py`, `core/project_model.py`, `PLAN_TASKS.md`, `PROJECT.md`
