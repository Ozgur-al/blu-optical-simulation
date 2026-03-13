# Technology Stack — Phase 2 Additions

**Project:** Blu Optical Simulation — Phase 2
**Researched:** 2026-03-14
**Research Mode:** Ecosystem / Stack dimension
**Confidence note:** External web tools (WebSearch, WebFetch, Brave Search) were unavailable during this session. All findings come from training data (knowledge cutoff August 2025) cross-referenced against locally available codebase files. Confidence levels are assigned conservatively; HIGH means the claim was stable and well-documented as of the cutoff.

---

## Context: What Already Exists

The Phase 1 stack is locked in and working:
- PySide6 >=6.6 — GUI framework
- pyqtgraph >=0.13 — 2D heatmaps + 3D OpenGL viewport (pyqtgraph.opengl)
- NumPy >=1.24 — vectorized ray math
- PyOpenGL >=3.1 — OpenGL for pyqtgraph 3D
- pytest >=7.0 — testing
- concurrent.futures.ProcessPoolExecutor — multiprocessing

Phase 2 does NOT replace any of those. It adds new capabilities on top.

---

## New Capabilities Required by Phase 2

| Capability | Current State | Gap |
|---|---|---|
| JIT acceleration | Pure NumPy loops | Need per-ray inner loops to run at near-C speed |
| BVH / spatial acceleration | O(rays × surfaces) brute force | Need sublinear surface query |
| Solid body geometry | Rectangle only | Box, cylinder, prism with per-face materials |
| 3D renderer upgrade | pyqtgraph.opengl wireframe | CAD-quality solid rendering of solid bodies |
| CAD/DXF import | No geometry import | Read STEP/IGES/DXF for LGP dot patterns and prism shapes |
| Edge-lit / LGP physics | No TIR, no refractive index | Snell's law, Fresnel, total internal reflection |
| BRDF data | Simple Lambertian / specular | Measured BRDF lookup tables |
| Spectral tracing integration | SPD + CIE utilities in `sim/spectral.py`, not wired into tracer per-ray | Per-ray wavelength in bounce loop |
| Temperature-dependent materials | Not implemented | Material properties as function of temperature |
| Far-field / angular detector | Flat planar detector only | Solid-angle bins, goniometric output |

---

## Recommended New Stack Components

### 1. JIT Acceleration — Numba

**Recommendation:** `numba >=0.60`
**Confidence:** HIGH (stable library, widely used in scientific Python as of Aug 2025)

**Why Numba over alternatives:**

The ray-tracing inner loops — intersection tests, reflection calculations, energy accumulation — are pure NumPy array math over fixed-size arrays. Numba JIT compiles these loops to LLVM machine code with zero-copy NumPy access via the `@njit` decorator. No C extension or Cython required; no new build toolchain.

Alternatives considered:
- **Cython** — requires separate `.pyx` files, C compiler, complicates PyInstaller build. Rejected.
- **CuPy / CUDA** — GPU dependency; not all target machines have discrete GPUs; driver complexity. Rejected per PROJECT.md decision.
- **PyPy** — incompatible with PySide6 and NumPy's CPython C extensions. Rejected.
- **Taichi** — younger, less stable, much larger install footprint (~1 GB). Rejected.

**How to apply it to this codebase:**

The key constraint is that `sim/` must stay headless. Numba satisfies this — it has no GUI dependencies. The integration strategy:

1. Create `sim/accel.py` containing `@njit`-decorated versions of the hottest functions:
   - `_intersect_rays_plane_nb(origins, directions, center, normal, u_axis, v_axis, half_w, half_h)` — returns `(t_array, hit_mask)`
   - `_reflect_specular_nb(directions, normal)` — vectorized specular
   - `_accumulate_grid_nb(grid, u_coords, v_coords, weights, hw, hh)` — grid bin accumulation
2. Keep pure-NumPy fallback paths for environments where Numba is unavailable (e.g., frozen PyInstaller build without LLVM).
3. Gate via `try: import numba; HAS_NUMBA = True except ImportError: HAS_NUMBA = False` at module top.

**PyInstaller packaging concern (MEDIUM confidence):** Numba bundles LLVM and requires `numba` + `llvmlite` to be included in the spec file. As of Numba 0.59, `--collect-all numba` and `--collect-all llvmlite` in PyInstaller spec are the documented approach. The frozen binary will be ~80 MB larger. This is acceptable for the Windows desktop target.

**Expected speedup:** 10–50x for intersection loops based on published Numba benchmarks for similar NumPy-heavy simulation code. Confidence: MEDIUM (depends on loop structure; vectorized NumPy already partially amortizes overhead).

```bash
pip install numba>=0.60
```

---

### 2. Spatial Acceleration — Pure NumPy BVH

**Recommendation:** Implement a flat AABB BVH in `sim/bvh.py` using NumPy — no external library.
**Confidence:** HIGH (the approach is well-established; no specific library needed)

**Why no external BVH library:**

Phase 2 has at most ~50–200 surfaces. A brute-force O(n) test over 50 planes with vectorized NumPy is fast when n is small. The benefit of BVH only becomes compelling at 500+ surfaces (e.g., complex LGP dot patterns). Even then, a two-level flat BVH built at simulation start and traversed with Numba is sufficient.

External options surveyed:
- **trimesh BVH** — trimesh is a mesh-processing library with built-in ray queries. Viable but adds a 30 MB dependency for one feature. Rejected for now; reconsidered if geometry import is added.
- **embree (Intel)** — industry-best ray-intersection hardware SIMD library. Python bindings via `pyembree` or `rtree`. MEDIUM confidence on PyInstaller compatibility. Use as Phase 3 option if performance demands it.
- **scipy KD-tree / cKDTree** — designed for point queries, not ray-plane queries. Not directly applicable.

**Recommended approach:**
1. Build axis-aligned bounding boxes for all surfaces at simulation start.
2. Test ray against AABB first; only compute full plane intersection if AABB hit.
3. Implement in `sim/bvh.py` as NumPy arrays (Nx6 for [x_min, x_max, y_min, y_max, z_min, z_max]), with optional Numba JIT for the AABB test loop.

This keeps the stack minimal and PyInstaller-compatible while providing 5–10x speedup for scenes with many non-overlapping surfaces.

---

### 3. 3D Renderer Upgrade — PyVista / pyvistaqt

**Recommendation:** `pyvista >=0.43` + `pyvistaqt >=0.11`
**Confidence:** MEDIUM (library versions inferred from Aug 2025 training data; verify before pinning)

**Why PyVista over alternatives:**

pyqtgraph.opengl renders primitives (lines, meshes) well for wireframes but has no solid body rendering pipeline, no per-face material support, and no lighting model suitable for showing refractive LGP geometry. PyVista wraps VTK with a high-level Python API and provides a Qt-embeddable render window via `pyvistaqt.QtInteractor`.

Alternatives considered:
- **VTK directly** (`vtk>=9.x`) — PyVista IS VTK under the hood; using raw VTK would mean re-implementing everything PyVista provides. Rejected.
- **Open3D** — excellent for point clouds and meshes but weak on scientific visualization (heatmaps, structured grids, transfer functions). No PySide6 widget. Rejected.
- **Vispy** — lower-level GPU canvas, requires more custom shaders. Good for raw performance but poor for solid body visualization out-of-the-box. Rejected.
- **Mayavi** — the traditional scientific 3D library; heavy dependency on Qt4/wx traits; poor PySide6 integration. Rejected.
- **PyQtGraph's GLViewWidget (current)** — keep for wireframe previews; migrate to PyVista for solid body CAD rendering only. Hybrid approach viable.

**PySide6 integration pattern (pyvistaqt):**
```python
from pyvistaqt import QtInteractor
plotter = QtInteractor(self)  # embeds as a QWidget
self.layout().addWidget(plotter)
plotter.add_mesh(mesh, color="lightblue", opacity=0.5)
```

**PyInstaller packaging concern (MEDIUM confidence):** VTK is a large C++ library (~200 MB). PyInstaller support for pyvistaqt requires `--collect-all pyvista` and `--collect-all vtkmodules`. Recommend making PyVista an optional import with fallback to existing pyqtgraph.opengl renderer — the existing 3D viewport remains usable for users who cannot run the larger binary.

**Strategy:** Add PyVista as a new `gui/viewport_3d_vtk.py` panel that activates when pyvista is importable. The existing `viewport_3d.py` remains the default. MainWindow detects availability at startup.

```bash
pip install pyvista>=0.43 pyvistaqt>=0.11
```

---

### 4. CAD / DXF Import

**Recommendation:** `ezdxf >=1.3` for DXF; `cadquery >=2.4` or `trimesh >=4.x` for STEP/IGES.
**Confidence:** MEDIUM for ezdxf (stable, widely used); LOW for STEP import (cadquery/OCC is complex to package)

**DXF (ezdxf) — use this first:**

LGP dot patterns, extractor patterns, and LED layouts are commonly available as DXF files. `ezdxf` parses DXF natively in pure Python with no external C dependencies. It is PyInstaller-friendly.

Use cases in this app:
- Import LED array positions from DXF
- Import LGP dot pattern as 2D point cloud → convert to absorber/diffuser patches
- Import prism geometry contours

```bash
pip install ezdxf>=1.3
```

**STEP/IGES (complex — defer to Phase 3):**

`cadquery` wraps OpenCASCADE (OCC), a ~500 MB C++ kernel. PyInstaller bundling is fragile; no official support. An alternative is `pythonOCC-core` directly. Recommendation: defer STEP import to Phase 3. For Phase 2, focus on DXF + mesh formats (STL/OBJ via trimesh).

**Mesh formats (STL/OBJ) — trimesh:**

`trimesh >=4.x` is pure Python for loading, slimmer than cadquery, and well-tested. Useful for importing LGP slab geometry, prism arrays, or diffuser microstructure meshes. Pairs naturally with PyVista (pyvista can render trimesh objects directly).

```bash
pip install trimesh>=4.0
```

**Confidence:** MEDIUM for trimesh version; HIGH for the approach.

---

### 5. Refractive Optics (TIR / Fresnel) — Pure NumPy in `sim/`

**Recommendation:** No new library. Implement Snell's law and Fresnel equations as NumPy functions in `sim/optics.py`.
**Confidence:** HIGH (standard physics equations; no library needed)

The equations are closed-form and fully vectorizable:

```python
# Snell's law — refracted direction
# n1 * sin(theta_i) = n2 * sin(theta_t)
# Vectorized form using component decomposition:
cos_i = -np.dot(d, n)   # angle of incidence
sin2_t = (n1/n2)**2 * (1 - cos_i**2)
# TIR: sin2_t > 1.0 → reflect, not refract
tir_mask = sin2_t >= 1.0
cos_t = np.sqrt(1 - sin2_t[~tir_mask])
d_refract = (n1/n2)*d + (n1/n2*cos_i - cos_t)*n

# Fresnel reflectance (unpolarized)
rs = ((n1*cos_i - n2*cos_t) / (n1*cos_i + n2*cos_t))**2
rp = ((n2*cos_i - n1*cos_t) / (n2*cos_i + n1*cos_t))**2
R = 0.5 * (rs + rp)
```

This keeps `sim/` headless and testable. The refractive index `n` is added to the `Material` dataclass (already present as `refractive_index` field in `OpticalProperties` per `ARCHITECTURE.md`).

For LGP glass (PMMA): n=1.49 at 550 nm; add wavelength-dependent Cauchy coefficients to `Material` for spectral accuracy.

---

### 6. BRDF Support — Pure NumPy + scipy (optional)

**Recommendation:** Represent measured BRDF as sampled tables in `Project.brdf_data` dict; use CDF inversion (same pattern as angular distributions). Add `scipy >=1.11` for interpolation of irregular BRDF grids.
**Confidence:** MEDIUM (scipy is the standard choice; version inferred)

**Why scipy here:**

The existing CDF inversion in `sim/sampling.py` works for 1D angular distributions. A full BRDF is a 4D function (theta_i, phi_i, theta_r, phi_r). For practical use in BLU simulation, a simplified isotropic BRDF (theta_i, theta_r) is sufficient — this is still 2D and can be handled with `scipy.interpolate.RegularGridInterpolator` or `scipy.interpolate.RectBivariateSpline`.

Standard BRDF file formats:
- **MERL binary format** (100 materials, 33MB each) — parse with NumPy struct.unpack; too large for typical BLU use
- **CSV tabulated BRDF** — simplest; same approach as angular distributions. Recommend this as primary format.

```bash
pip install scipy>=1.11
```

`scipy` is PyInstaller-safe with `--collect-all scipy`.

---

### 7. Spectral Integration into Tracer — No New Library

**Recommendation:** No new library. `sim/spectral.py` already has all primitives. The work is integration, not new dependencies.
**Confidence:** HIGH

The existing `sim/spectral.py` provides:
- `sample_wavelengths(n, spd_name, rng)` — per-ray wavelength sampling
- `spectral_bin_centers(n_bins)` — bin center lookup
- `spectral_grid_to_rgb(grid, wavelengths)` — final XYZ→sRGB conversion
- CIE 1931 observer tables

The `SimulationResult` and `DetectorResult` already have `grid_spectral` and `grid_rgb` fields based on the codebase structure. The task is wiring wavelength-dependent reflectance/transmittance lookup into the bounce loop.

For wavelength-dependent material properties (e.g., PMMA absorption spectrum), store as `{wavelength_nm: [float], value: [float]}` lists in `Material`, consistent with the angular distribution pattern.

---

### 8. Temperature-Dependent Materials — No New Library

**Recommendation:** No new library. Represent temperature curves as sampled tables in `Material`, interpolated with NumPy at simulation time.
**Confidence:** HIGH

Simple design: add `thermal_reflectance_curve: dict | None` to `Material` — `{"temp_C": [25, 50, 75], "reflectance": [0.95, 0.93, 0.90]}`. At simulation time, interpolate with `np.interp(operating_temp, curve["temp_C"], curve["reflectance"])`. Same pattern as angular distributions.

---

### 9. Far-Field / Angular Detector — No New Library

**Recommendation:** No new library. Extend `SphereDetector` (already partially implemented) to accumulate solid-angle bins.
**Confidence:** HIGH

A far-field detector is a sphere detector where each bin covers a solid angle dΩ = sin(θ) dθ dφ. The existing `SphereDetector` infrastructure in `core/detectors.py` only needs:
1. Solid-angle normalization on readout
2. Polar plot visualization (matplotlib polar axes or pyqtgraph PolarPlot)
3. Export as a goniophotometry CSV (theta, phi, intensity)

No new library required. matplotlib is already used in `io/report.py`.

---

### 10. Solid Body Geometry (Box, Cylinder, Prism)

**Recommendation:** Implement in `core/solids.py` as first-class dataclasses; no external library for geometry representation.
**Confidence:** HIGH (the design fits naturally into the existing u_axis/v_axis pattern)

**Box:** Decompose into 6 `Rectangle` faces at construction time. The existing intersection engine already handles rectangles — no new intersection code needed for boxes. Provide a `SolidBox` dataclass that owns 6 `Rectangle` instances with independent material assignments.

**Cylinder:** Requires new `CylinderSurface` with parametric intersection (`t` solved from quadratic). Add to `_intersect_rays_cylinder()` in tracer.

**Prism (triangular LGP cross-section):** Decompose into planar faces (3 rectangular faces + 2 triangular end caps). Triangle intersection is a special case of plane intersection with a triangular boundary.

For mesh-based geometry from CAD import (trimesh), wrap mesh as a set of triangular face planes in a `MeshBody` container.

---

## Complete Phase 2 Stack

### Core Framework (unchanged)

| Technology | Version | Purpose | Status |
|---|---|---|---|
| PySide6 | >=6.6 | GUI framework | Existing |
| pyqtgraph | >=0.13 | 2D heatmaps, analysis plots | Existing |
| PyOpenGL | >=3.1 | pyqtgraph 3D backend | Existing |
| NumPy | >=1.24 | Vectorized ray math | Existing |
| pytest | >=7.0 | Testing | Existing |

### New in Phase 2

| Technology | Version | Purpose | Why | Confidence |
|---|---|---|---|---|
| numba | >=0.60 | JIT-accelerate ray intersection and accumulation inner loops | 10–50x speedup; pure Python API; no build toolchain | HIGH |
| llvmlite | >=0.43 | Numba dependency (LLVM backend) | Auto-installed with numba | HIGH |
| pyvista | >=0.43 | 3D solid body rendering (VTK wrapper) | CAD-quality solid/transparent rendering; per-face material coloring; industry-standard for scientific 3D viz | MEDIUM |
| pyvistaqt | >=0.11 | Embed PyVista renderer in PySide6 widget | Official Qt integration from PyVista team | MEDIUM |
| ezdxf | >=1.3 | DXF import for LED layouts and LGP patterns | Pure Python, PyInstaller-safe, actively maintained | MEDIUM |
| trimesh | >=4.0 | STL/OBJ mesh import; geometry processing | Lightweight, no C++ dependencies, pairs with PyVista | MEDIUM |
| scipy | >=1.11 | 2D BRDF interpolation; irregular grid resampling | Standard scientific Python; already implied by pyqtgraph; PyInstaller-safe | MEDIUM |

### Optional / Phase 3

| Technology | Purpose | Why Deferred |
|---|---|---|
| pyembree | Fast ray-triangle BVH via Intel Embree | Only beneficial at 500+ triangular surfaces; overkill for Phase 2 |
| cadquery / pythonOCC | STEP/IGES CAD import | OCC packaging complexity; 500 MB install; defer to Phase 3 |
| optuna | Bayesian parameter optimization | Premature; Pareto sweep sufficient per PROJECT.md |

---

## Alternatives Not Recommended

| Category | Alternative | Why Rejected |
|---|---|---|
| JIT | Cython | Requires C compiler, separate .pyx files, complicates PyInstaller build |
| JIT | CuPy / CUDA | GPU dependency; target machines may not have discrete GPU; driver fragility |
| JIT | Taichi | Large install (~1 GB), younger ecosystem, less stable API |
| 3D renderer | Mayavi | Poor PySide6 integration; legacy Qt4/wxWidgets architecture |
| 3D renderer | Open3D | Weak scientific viz (no heatmaps/transfer functions); no PySide6 widget |
| 3D renderer | Vispy | Low-level GPU canvas; requires custom shaders for solid body rendering |
| CAD import | cadquery | 500 MB OCC dependency; fragile PyInstaller; defer to Phase 3 |
| BRDF | MERL binary | Individual files are 33 MB; too large for typical BLU workflow |
| Spatial accel | scipy KD-tree | Designed for point queries, not ray-plane queries |

---

## Installation

```bash
# Core Phase 2 additions (all new)
pip install numba>=0.60 pyvista>=0.43 pyvistaqt>=0.11 ezdxf>=1.3 trimesh>=4.0 scipy>=1.11

# Existing requirements (unchanged)
pip install PySide6>=6.6 pyqtgraph>=0.13 numpy>=1.24 PyOpenGL>=3.1 pytest>=7.0
```

Updated `requirements.txt`:
```
PySide6>=6.6
pyqtgraph>=0.13
numpy>=1.24
PyOpenGL>=3.1
pytest>=7.0
numba>=0.60
pyvista>=0.43
pyvistaqt>=0.11
ezdxf>=1.3
trimesh>=4.0
scipy>=1.11
```

---

## PyInstaller Packaging Implications

| Library | Packaging Notes | Spec File Additions Needed |
|---|---|---|
| numba | Bundles LLVM; adds ~80 MB to binary | `--collect-all numba --collect-all llvmlite` |
| pyvista | Bundles VTK modules; adds ~200 MB | `--collect-all pyvista --collect-all vtkmodules` |
| pyvistaqt | Small; depends on pyvista | `--collect-all pyvistaqt` |
| ezdxf | Pure Python; no special handling | None |
| trimesh | Pure Python; no special handling | None |
| scipy | C extensions; well-tested with PyInstaller | `--collect-all scipy` |

**Recommendation:** Make PyVista (and therefore pyvistaqt) optional imports. The binary grows by ~280 MB if bundled. Offer a "lite" build target in `build_exe.py` that excludes PyVista and falls back to pyqtgraph.opengl for 3D. This matches the project's stated preference to "prefer pure-Python or well-maintained packages; avoid heavy frameworks that complicate PyInstaller builds."

---

## Confidence Assessment

| Area | Confidence | Reason |
|---|---|---|
| Numba for JIT | HIGH | Stable library, straightforward NumPy integration, widely documented |
| NumPy BVH implementation | HIGH | Implementation approach, no external library needed |
| PyVista/pyvistaqt integration | MEDIUM | API stable as of Aug 2025; version numbers inferred from training data, not verified against current PyPI |
| ezdxf | MEDIUM | Actively maintained; version inferred from training data |
| trimesh | MEDIUM | Actively maintained; version inferred from training data |
| scipy version | MEDIUM | Implied by broader scientific Python ecosystem; version inferred |
| Refractive optics (pure NumPy) | HIGH | Standard physics equations; no library needed; well-documented math |
| Spectral integration | HIGH | All needed primitives already in `sim/spectral.py`; no new library |
| Temperature materials | HIGH | Same pattern as existing angular distributions; no new library |
| Far-field detector | HIGH | Extends existing SphereDetector; no new library |
| STEP/IGES import viability | LOW | OCC packaging is notoriously complex; cadquery dependency chain uncertain |

---

## Sources

- Training knowledge (knowledge cutoff August 2025) — all claims
- LOCAL: `G:/blu-optical-simulation/backlight_sim/sim/spectral.py` — spectral utilities already implemented
- LOCAL: `G:/blu-optical-simulation/.planning/codebase/ARCHITECTURE.md` — existing OpticalProperties, SphereDetector, refractive_index field already present
- LOCAL: `G:/blu-optical-simulation/.planning/codebase/CONCERNS.md` — performance bottlenecks and PyInstaller risk analysis
- LOCAL: `G:/blu-optical-simulation/.planning/PROJECT.md` — Phase 2 requirements, key decisions, constraints
- LOCAL: `G:/blu-optical-simulation/requirements.txt` — current locked versions

**Verification needed before implementation:**
- Confirm current Numba version on PyPI (was 0.59.x as of late 2024; 0.60 expected mid-2025)
- Confirm pyvistaqt 0.11.x is latest stable and PySide6 6.6 compatibility
- Check ezdxf latest release (was 1.2.x in 2024)
- Verify trimesh 4.x is stable release (was in active development through 2024)
