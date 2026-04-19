"""Monte Carlo ray tracing engine — general plane intersection."""

from __future__ import annotations

import hashlib
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace as _dataclasses_replace
from typing import Callable

import numpy as np

from backlight_sim.core.project_model import Project
from backlight_sim.core.geometry import Rectangle
from backlight_sim.core.detectors import (
    DetectorSurface, DetectorResult, SimulationResult,
    SphereDetector, SphereDetectorResult,
)
from backlight_sim.core.solid_body import FACE_NAMES, SolidCylinder, SolidPrism, CylinderCap, CylinderSide, PrismCap
from backlight_sim.sim.sampling import (
    sample_isotropic,
    sample_lambertian,
    sample_angular_distribution,
    sample_diffuse_reflection,
    reflect_specular,
    scatter_haze,
    sample_bsdf,
    precompute_bsdf_cdfs,
)
from backlight_sim.sim import blu_tracer as _blu_tracer
from backlight_sim.sim.spectral import (
    sample_wavelengths, spectral_bin_centers, N_SPECTRAL_BINS, LAMBDA_MIN, LAMBDA_MAX,
    get_spd_from_project,
)


_EPSILON = 1e-6

# BVH disabled on the Python fallback path — C++ extension handles the fast
# non-spectral path; the Python path (spectral / solid bodies) falls back to
# brute-force intersection. Setting the threshold above any realistic surface
# count ensures the BVH branch never activates (Plan 02-03, Step 5).
_BVH_THRESHOLD = 10**9

# Maximum nesting depth for per-ray refractive index stack
_N_STACK_MAX = 8


# ---------------------------------------------------------------------------
# Phase 4 UQ helpers
# ---------------------------------------------------------------------------
# Effective K window for batch-means CI:
#   floor=4  -> below this Student-t critical values diverge (test_uq.py in
#              core/uq.py rejects K<4 for CI computation).
#   cap=20   -> above this per-batch sparsity dominates batch-to-batch variance
#              (noise, not uncertainty).  Wave 1 threat T-04.01-02 (DoS via
#              very large uq_batches) is mitigated here at runtime.


def _effective_uq_batches(settings) -> int:
    """Return effective ``K`` honoring the [4, 20] dof window when UQ is on.

    Returns 0 when UQ is disabled (uq_batches <= 0 in SimulationSettings).
    """
    k_req = int(getattr(settings, "uq_batches", 0))
    if k_req <= 0:
        return 0
    return min(20, max(4, k_req))


def _batch_seed(base_seed: int, source_name: str, batch_k: int) -> int:
    """Deterministic per-batch seed from ``(base_seed, source_name, batch_k)``.

    md5 of the composite string -> 64-bit integer.  Matches the source-level
    seed derivation pattern so determinism is preserved across UQ batches.
    """
    h = hashlib.md5(f"{base_seed}_{source_name}_{batch_k}".encode("utf-8")).hexdigest()
    return int(h[:16], 16) & 0xFFFFFFFFFFFFFFFF  # 64-bit mask


def _partition_rays(rays_total: int, K: int) -> list[int]:
    """Split ``rays_total`` into ``K`` batches; remainder -> first batches.

    ``sum(result) == rays_total``.  Consumed for rays_per_batch bookkeeping
    and for the actual per-batch rays_per_source value passed to the tracer.
    """
    if K <= 0:
        return [int(rays_total)]
    base = int(rays_total) // K
    rem = int(rays_total) - base * K
    return [base + (1 if k < rem else 0) for k in range(K)]


def _replace_settings(settings, **overrides):
    """Return a dataclass-copy of ``settings`` with selected attributes overridden.

    Used by the UQ batched runner to patch rays_per_source / random_seed /
    record_ray_paths / adaptive_sampling per chunk without mutating the
    user-provided settings dataclass.
    """
    return _dataclasses_replace(settings, **overrides)


# ---------------------------------------------------------------------------
# Pure-Python shims for removed backlight_sim.sim.accel symbols
# ---------------------------------------------------------------------------
# The C++ extension handles the hot non-spectral path. For the Python spectral /
# solid-body fallback path, we keep using the existing per-bounce numpy
# intersection helpers defined later in this module (_intersect_rays_plane,
# _intersect_rays_sphere). These shims alias those helpers so the rest of the
# tracer code keeps its original call sites without touching every line.
# BVH is disabled via _BVH_THRESHOLD above, so build_bvh_flat / traverse_bvh_batch
# are no-op stubs preserved only for signature compatibility.


def _intersect_plane_accel(origins, directions, normal, center, u_axis, v_axis, size):
    """Shim: delegate to the pure-numpy _intersect_rays_plane defined below."""
    return _intersect_rays_plane(origins, directions, normal, center, u_axis, v_axis, size)


def _intersect_sphere_accel(origins, directions, center, radius):
    """Shim: delegate to the pure-numpy _intersect_rays_sphere defined below."""
    return _intersect_rays_sphere(origins, directions, center, radius)


def accumulate_grid_jit(grid, iy, ix, weights):
    """Shim: scatter-add replacement for numba accumulate_grid_jit."""
    np.add.at(grid, (iy, ix), weights)


def accumulate_sphere_jit(grid, i_theta, i_phi, weights):
    """Shim: scatter-add replacement for numba accumulate_sphere_jit."""
    np.add.at(grid, (i_theta, i_phi), weights)


def compute_surface_aabbs(normals, centers, u_axes, v_axes, half_ws, half_hs):
    """Shim: vectorized AABB computation (was in accel.py, no numba needed)."""
    n = centers.shape[0]
    hw = half_ws[:, None]
    hh = half_hs[:, None]
    corners = np.stack([
        centers + hw * u_axes + hh * v_axes,
        centers + hw * u_axes - hh * v_axes,
        centers - hw * u_axes + hh * v_axes,
        centers - hw * u_axes - hh * v_axes,
    ], axis=1)
    aabbs = np.empty((n, 6), dtype=np.float64)
    aabbs[:, 0] = corners[:, :, 0].min(axis=1)
    aabbs[:, 1] = corners[:, :, 0].max(axis=1)
    aabbs[:, 2] = corners[:, :, 1].min(axis=1)
    aabbs[:, 3] = corners[:, :, 1].max(axis=1)
    aabbs[:, 4] = corners[:, :, 2].min(axis=1)
    aabbs[:, 5] = corners[:, :, 2].max(axis=1)
    return aabbs


def build_bvh_flat(surface_aabbs):
    """Stub: BVH disabled on Python path (see _BVH_THRESHOLD). Returns empty tree."""
    empty_bounds = np.zeros((1, 6), dtype=np.float64)
    empty_meta = np.zeros((1, 3), dtype=np.int32)
    return empty_bounds, empty_meta, 0


def traverse_bvh_batch(origins, directions, bvh_bounds, bvh_meta, n_nodes,
                       surf_normals, surf_centers, surf_u, surf_v,
                       surf_hw, surf_hh, epsilon):
    """Stub: BVH disabled on Python path. All rays report no-hit (brute-force is
    used instead because _BVH_THRESHOLD is set above any realistic count)."""
    n_rays = origins.shape[0]
    best_t = np.full(n_rays, np.inf, dtype=np.float64)
    best_idx = np.full(n_rays, -1, dtype=np.int64)
    return best_t, best_idx


def _n_stack_update(n_depth, n_stack, ri, entering_mask, n1_vals):
    """Push/pop per-ray refractive index stack on solid body refraction.

    Call after ``current_n[ri] = n2_r`` for refracted rays only.
    *entering_mask* is a boolean array (len == len(ri)) indicating which
    refracted rays are entering (True) vs exiting (False) the solid.
    """
    push = ri[entering_mask]
    if len(push):
        d = n_depth[push]
        n_stack[push, np.minimum(d, _N_STACK_MAX - 1)] = n1_vals[entering_mask]
        n_depth[push] = np.minimum(d + 1, _N_STACK_MAX)
    pop = ri[~entering_mask]
    if len(pop):
        n_depth[pop] = np.maximum(n_depth[pop] - 1, 0)


# ------------------------------------------------------------------
# Fresnel / Snell physics helpers
# ------------------------------------------------------------------

def _fresnel_unpolarized(
    cos_theta_i: np.ndarray,
    n1: np.ndarray,
    n2: np.ndarray,
) -> np.ndarray:
    """Vectorized unpolarized Fresnel reflectance.

    Parameters
    ----------
    cos_theta_i : (N,) array
        Cosine of the angle of incidence (always positive, i.e. the dot
        product of the incoming direction with the *inward* normal).
    n1 : (N,) array
        Refractive index of the medium the ray is coming FROM.
    n2 : (N,) array
        Refractive index of the medium the ray is entering.

    Returns
    -------
    R : (N,) array
        Reflectance in [0, 1].  Returns 1.0 for TIR cases.
    """
    cos_i = np.clip(cos_theta_i, 0.0, 1.0)
    ratio = n1 / n2                             # eta = n1/n2
    sin_t_sq = ratio * ratio * (1.0 - cos_i * cos_i)

    tir_mask = sin_t_sq >= 1.0
    cos_t = np.sqrt(np.maximum(0.0, 1.0 - sin_t_sq))

    denom_s = n1 * cos_i + n2 * cos_t
    denom_p = n2 * cos_i + n1 * cos_t
    # Guard against zero denominators (should only hit at exact TIR boundary)
    denom_s = np.maximum(denom_s, 1e-12)
    denom_p = np.maximum(denom_p, 1e-12)

    Rs = ((n1 * cos_i - n2 * cos_t) / denom_s) ** 2
    Rp = ((n2 * cos_i - n1 * cos_t) / denom_p) ** 2
    R = 0.5 * (Rs + Rp)

    return np.where(tir_mask, 1.0, R)


def _refract_snell(
    directions: np.ndarray,
    oriented_normals: np.ndarray,
    n1: np.ndarray,
    n2: np.ndarray,
) -> np.ndarray:
    """Vectorized Snell's law refraction.

    Parameters
    ----------
    directions : (N, 3) array
        Incoming ray directions (unit vectors).
    oriented_normals : (N, 3) array
        Surface normals pointing INTO the new medium (unit vectors pointing
        in the direction the refracted ray will travel through).
    n1 : (N,) array
        Refractive index of the incoming medium.
    n2 : (N,) array
        Refractive index of the new medium.

    Returns
    -------
    refracted : (N, 3) array
        Refracted unit direction vectors.

    Notes
    -----
    Uses the standard formula: r = eta*d + (eta*cos_i - cos_t)*n_hat
    where n_hat points TOWARD the incoming ray (i.e. INTO the old medium).
    We receive ``oriented_normals`` pointing INTO the new medium, so we
    internally negate it to get n_hat pointing toward the source.
    cos_i = dot(-d, n_hat) = dot(-d, -on) = dot(d, on)
    """
    eta = (n1 / n2)[:, None]                   # (N, 1)
    # n_hat points TOWARD incoming ray (into old medium) = -oriented_normals
    # cos_i = dot(-d, n_hat) = dot(-d, -on) = dot(d, on)
    cos_i = np.clip(
        np.einsum("ij,ij->i", directions, oriented_normals),
        0.0, 1.0,
    )[:, None]                                  # (N, 1)
    # n_hat = -oriented_normals
    n_hat = -oriented_normals                  # (N, 3)

    sin_t_sq = eta * eta * (1.0 - cos_i * cos_i)
    cos_t = np.sqrt(np.maximum(0.0, 1.0 - sin_t_sq))   # (N, 1)

    # Standard refraction formula: r = eta*d + (eta*cos_i - cos_t)*n_hat
    refracted = eta * directions + (eta * cos_i - cos_t) * n_hat

    # Normalize (numerical safety)
    norms = np.linalg.norm(refracted, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return refracted / norms


# ---------------------------------------------------------------------------
# C++ extension dispatch helpers (Plan 02-03)
# ---------------------------------------------------------------------------

def _project_uses_cpp_unsupported_features(project) -> bool:
    """Return True if the project uses any feature that the C++ extension
    does not yet handle. Those scenes must stay on the Python path.

    Unsupported by C++ (Wave 2 scope): spectral sources, solid bodies /
    cylinders / prisms, far-field sphere detectors, non-white source colors,
    BSDF profiles, spectral material data. Keep this predicate conservative —
    anything outside the C++ feature set routes to Python.
    """
    # Spectral SPDs on any enabled source
    if any(s.spd != "white" for s in project.sources if s.enabled):
        return True
    # Solid bodies (box / cylinder / prism) — C++ has no Fresnel/TIR dispatch yet
    if getattr(project, "solid_bodies", None):
        return True
    if getattr(project, "solid_cylinders", None):
        return True
    if getattr(project, "solid_prisms", None):
        return True
    # Far-field sphere detectors need candela_grid post-processing that depends
    # on direction-at-hit, which the C++ accumulator doesn't emit.
    for sd in getattr(project, "sphere_detectors", []) or []:
        if getattr(sd, "mode", "near_field") == "far_field":
            return True
    # Non-white source colors (RGB accumulation)
    for s in project.sources:
        if not s.enabled:
            continue
        color = getattr(s, "color_rgb", (1.0, 1.0, 1.0))
        if tuple(color) != (1.0, 1.0, 1.0):
            return True
    # BSDF profiles or spectral material data
    if getattr(project, "bsdf_profiles", None):
        return True
    if getattr(project, "spectral_material_data", None):
        return True
    return False


def _cpp_extension_available() -> bool:
    """Return True when the compiled C++ tracer module is loaded."""
    return _blu_tracer is not None


def _missing_cpp_extension_error() -> RuntimeError:
    """Return a consistent error for direct C++-path calls without the module."""
    return RuntimeError(
        "blu_tracer C++ extension is not available. "
        "Run the Python tracing path or rebuild/install the extension with:\n"
        "  pip install --no-build-isolation -e backlight_sim/sim/_blu_tracer/\n"
        "(requires MSVC 2022 Build Tools and CMake — see CLAUDE.md)"
    )


def _serialize_project(project) -> dict:
    """Serialize a Project dataclass to a plain dict for the C++ extension.

    The C++ trace_source() deserializes this dict — keep the key names and
    value types aligned with blu_tracer.cpp::trace_source deserialization.
    Only the fields that the C++ extension reads are serialized. Features
    unsupported by C++ (solid bodies, BSDF, spectral) are filtered out upstream
    by _project_uses_cpp_unsupported_features().
    """
    def arr3(v):
        return [float(x) for x in v]

    surfaces_list = []
    for s in project.surfaces:
        surfaces_list.append({
            "name": s.name,
            "center": arr3(s.center),
            "normal": arr3(s.normal),
            "u_axis": arr3(s.u_axis),
            "v_axis": arr3(s.v_axis),
            "size": [float(s.size[0]), float(s.size[1])],
            "material_name": str(s.material_name or ""),
            "optical_properties_name": str(
                getattr(s, "optical_properties_name", "") or ""
            ),
        })

    detectors_list = []
    for d in project.detectors:
        detectors_list.append({
            "name": d.name,
            "center": arr3(d.center),
            "normal": arr3(d.normal),
            "u_axis": arr3(d.u_axis),
            "v_axis": arr3(d.v_axis),
            "size": [float(d.size[0]), float(d.size[1])],
            "resolution": [int(d.resolution[0]), int(d.resolution[1])],
        })

    sphere_det_list = []
    for sd in getattr(project, "sphere_detectors", []) or []:
        sphere_det_list.append({
            "name": sd.name,
            "center": arr3(sd.center),
            "radius": float(sd.radius),
            "resolution": [int(sd.resolution[0]), int(sd.resolution[1])],
            "mode": str(getattr(sd, "mode", "near_field")),
        })

    materials_dict = {}
    for name, mat in project.materials.items():
        materials_dict[name] = {
            "surface_type": str(mat.surface_type),
            "reflectance": float(mat.reflectance),
            "transmittance": float(mat.transmittance),
            "is_diffuse": bool(mat.is_diffuse),
            "haze": float(mat.haze),
            "refractive_index": float(getattr(mat, "refractive_index", 1.0)),
        }

    optical_props_dict = {}
    for name, op in (getattr(project, "optical_properties", {}) or {}).items():
        optical_props_dict[name] = {
            "surface_type": str(op.surface_type),
            "reflectance": float(op.reflectance),
            "transmittance": float(op.transmittance),
            "is_diffuse": bool(op.is_diffuse),
            "haze": float(op.haze),
            "refractive_index": float(getattr(op, "refractive_index", 1.0)),
        }

    ang_dist_dict = {}
    for name, profile in (project.angular_distributions or {}).items():
        ang_dist_dict[name] = {
            "theta_deg": [float(x) for x in profile.get("theta_deg", [])],
            "intensity": [float(x) for x in profile.get("intensity", [])],
        }

    sources_list = []
    for s in project.sources:
        sources_list.append({
            "name": s.name,
            "position": arr3(s.position),
            "direction": arr3(s.direction),
            "distribution": str(s.distribution),
            "effective_flux": float(s.effective_flux),
            "enabled": bool(s.enabled),
            "flux_tolerance": float(s.flux_tolerance),
            "spd": str(getattr(s, "spd", "white") or "white"),
        })

    settings = project.settings
    settings_dict = {
        "rays_per_source": int(settings.rays_per_source),
        "max_bounces": int(settings.max_bounces),
        "energy_threshold": float(settings.energy_threshold),
        "random_seed": int(settings.random_seed),
        "record_ray_paths": int(settings.record_ray_paths),
        "use_multiprocessing": bool(settings.use_multiprocessing),
        "adaptive_sampling": bool(getattr(settings, "adaptive_sampling", False)),
        "check_interval": int(
            getattr(settings, "check_interval", settings.rays_per_source)
        ),
    }

    return {
        "sources": sources_list,
        "surfaces": surfaces_list,
        "detectors": detectors_list,
        "sphere_detectors": sphere_det_list,
        "materials": materials_dict,
        "optical_properties": optical_props_dict,
        "angular_distributions": ang_dist_dict,
        "solid_bodies": [],
        "solid_cylinders": [],
        "solid_prisms": [],
        "settings": settings_dict,
    }


def _cpp_trace_single_source(project, source_name: str, base_seed: int) -> dict:
    """Top-level function for multiprocessing: trace one source via C++ extension.

    Mirrors _trace_single_source but delegates to _blu_tracer.trace_source().
    Returns the same dict shape as _trace_single_source.

    Phase 4 UQ (Wave 2): when ``settings.uq_batches > 0``, this function issues
    K sequential calls to the existing C++ ``trace_source`` with per-batch
    seeded RNG and a sliced rays_per_source.  Per-batch grids/hits/flux are
    stacked into the return dict under ``grids_batches`` / ``hits_batches`` /
    ``flux_batches`` / ``rays_per_batch``.  The underlying C++ extension is
    NOT rebuilt — batching is Python-side only.
    """
    if not _cpp_extension_available():
        raise _missing_cpp_extension_error()

    settings = project.settings
    K = _effective_uq_batches(settings)
    project_dict = _serialize_project(project)

    if K == 0:
        # Legacy fast path — single call, no UQ bookkeeping.
        seed_hash = int(
            hashlib.md5(f"{base_seed}_{source_name}".encode()).hexdigest()[:8],
            16,
        ) & 0x7FFFFFFF
        result_dict = _blu_tracer.trace_source(project_dict, source_name, int(seed_hash))
        result_dict["grids_batches"] = None
        result_dict["hits_batches"] = None
        result_dict["flux_batches"] = None
        result_dict["rays_per_batch"] = None
        result_dict["n_batches"] = 0
        return result_dict

    # UQ path: K sequential calls, per-batch seed + sliced rays_per_source.
    rays_total = int(settings.rays_per_source)
    chunk_sizes = _partition_rays(rays_total, K)

    # Per-detector accumulators
    grids_agg: dict[str, dict] = {}
    sph_grids_agg: dict[str, dict] = {}
    sb_stats_agg: dict = {}
    escaped_agg = 0.0
    grids_batches: dict[str, list[np.ndarray]] = {}
    hits_batches: dict[str, list[int]] = {}
    flux_batches: dict[str, list[float]] = {}
    sph_grids_batches: dict[str, list[np.ndarray]] = {}
    sph_hits_batches: dict[str, list[int]] = {}
    sph_flux_batches: dict[str, list[float]] = {}
    actual_rays_per_batch: list[int] = []

    for k in range(K):
        rays_this_batch = chunk_sizes[k]
        if rays_this_batch <= 0:
            continue
        # Shallow-copy dict and patch rays_per_source + scale source flux so
        # each chunk contributes effective_flux * (rays_this_batch / rays_total)
        # to the detector.  Summed over K chunks: effective_flux (unchanged).
        batch_project_dict = dict(project_dict)
        batch_project_dict["settings"] = dict(project_dict["settings"])
        batch_project_dict["settings"]["rays_per_source"] = int(rays_this_batch)
        # Deep-copy sources list so we can patch effective_flux per-batch
        scale = rays_this_batch / max(rays_total, 1)
        batch_project_dict["sources"] = [dict(s) for s in project_dict["sources"]]
        for src_item in batch_project_dict["sources"]:
            src_item["effective_flux"] = float(src_item["effective_flux"]) * scale
        seed_k = _batch_seed(base_seed, source_name, k) & 0x7FFFFFFF
        batch_res = _blu_tracer.trace_source(batch_project_dict, source_name, int(seed_k))

        # Merge aggregates + stack per-batch
        for det_name, grid_data in batch_res.get("grids", {}).items():
            g = np.asarray(grid_data["grid"])
            if det_name not in grids_agg:
                grids_agg[det_name] = {
                    "grid": g.copy(),
                    "hits": int(grid_data["hits"]),
                    "flux": float(grid_data["flux"]),
                }
            else:
                grids_agg[det_name]["grid"] += g
                grids_agg[det_name]["hits"] += int(grid_data["hits"])
                grids_agg[det_name]["flux"] += float(grid_data["flux"])
            grids_batches.setdefault(det_name, []).append(g.copy())
            hits_batches.setdefault(det_name, []).append(int(grid_data["hits"]))
            flux_batches.setdefault(det_name, []).append(float(grid_data["flux"]))
        for sph_name, sph_data in batch_res.get("sph_grids", {}).items():
            g = np.asarray(sph_data["grid"])
            if sph_name not in sph_grids_agg:
                sph_grids_agg[sph_name] = {
                    "grid": g.copy(),
                    "hits": int(sph_data["hits"]),
                    "flux": float(sph_data["flux"]),
                }
            else:
                sph_grids_agg[sph_name]["grid"] += g
                sph_grids_agg[sph_name]["hits"] += int(sph_data["hits"])
                sph_grids_agg[sph_name]["flux"] += float(sph_data["flux"])
            sph_grids_batches.setdefault(sph_name, []).append(g.copy())
            sph_hits_batches.setdefault(sph_name, []).append(int(sph_data["hits"]))
            sph_flux_batches.setdefault(sph_name, []).append(float(sph_data["flux"]))
        escaped_agg += float(batch_res.get("escaped", 0.0))
        for bn, face_map in batch_res.get("sb_stats", {}).items():
            dst = sb_stats_agg.setdefault(bn, {})
            for fid, fstats in face_map.items():
                cur = dst.setdefault(fid, {"entering_flux": 0.0, "exiting_flux": 0.0})
                cur["entering_flux"] += float(fstats.get("entering_flux", 0.0))
                cur["exiting_flux"] += float(fstats.get("exiting_flux", 0.0))
        actual_rays_per_batch.append(int(rays_this_batch))

    # Stack per-batch lists into numpy arrays for downstream consumption
    grids_batches_stacked = {
        name: {"grid": np.stack(grids, axis=0)}
        for name, grids in grids_batches.items()
    }
    return {
        "grids": grids_agg,
        "spectral_grids": {},
        "escaped": escaped_agg,
        "sb_stats": sb_stats_agg,
        "sph_grids": sph_grids_agg,
        # Phase 4 UQ payload
        "grids_batches": grids_batches_stacked,
        "hits_batches": {k: np.asarray(v, dtype=int) for k, v in hits_batches.items()},
        "flux_batches": {k: np.asarray(v, dtype=float) for k, v in flux_batches.items()},
        "sph_grids_batches": {
            name: {"grid": np.stack(grids, axis=0)}
            for name, grids in sph_grids_batches.items()
        },
        "sph_hits_batches": {k: np.asarray(v, dtype=int) for k, v in sph_hits_batches.items()},
        "sph_flux_batches": {k: np.asarray(v, dtype=float) for k, v in sph_flux_batches.items()},
        "rays_per_batch": actual_rays_per_batch,
        "n_batches": len(actual_rays_per_batch),
    }


class RayTracer:
    def __init__(self, project: Project):
        self.project = project
        self.rng = np.random.default_rng(project.settings.random_seed)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(
        self,
        progress_callback: Callable[[float], None] | None = None,
        convergence_callback: Callable[[int, int, float], None] | None = None,
        partial_result_callback: Callable | None = None,
    ) -> SimulationResult:
        self._cancelled = False
        settings = self.project.settings

        # Use multiprocessing if enabled and there are multiple sources
        sources = [s for s in self.project.sources if s.enabled]

        has_spectral = any(s.spd != "white" for s in sources)
        n_spec_bins = N_SPECTRAL_BINS if has_spectral else 0

        # Adaptive + MP guard: adaptive per-source convergence checking cannot be
        # coordinated across processes.  Disable adaptive sampling in MP mode.
        _adaptive = settings.adaptive_sampling
        if _adaptive and settings.use_multiprocessing:
            import warnings
            warnings.warn(
                "Adaptive sampling disabled in multiprocessing mode.",
                stacklevel=2,
            )
            _adaptive = False

        # Phase 4 UQ — adaptive+UQ warning (CONTEXT D-01): both allowed
        # simultaneously with a caveat appended to result.uq_warnings.
        pending_uq_warnings: list[str] = []
        if _adaptive and _effective_uq_batches(settings) > 0:
            pending_uq_warnings.append(
                "Adaptive sampling and UQ are both enabled. CIs may be biased "
                "because adaptive sampling terminates early based on "
                "convergence; Student-t coverage assumes a fixed K. "
                "Convergence is evaluated at chunk boundaries to minimize "
                "bias. Disable adaptive_sampling for strict CI coverage "
                "guarantees."
            )

        if (settings.use_multiprocessing and len(sources) > 1
                and not settings.record_ray_paths):
            result = self._run_multiprocess(
                sources, progress_callback,
                has_spectral=has_spectral, n_spec_bins=n_spec_bins,
                partial_result_callback=partial_result_callback,
            )
        else:
            result = self._run_single(
                sources, progress_callback, convergence_callback,
                _adaptive=_adaptive,
                partial_result_callback=partial_result_callback,
            )

        # Merge pending warnings onto the result (de-duplicated, ordered)
        for w in pending_uq_warnings:
            if w not in result.uq_warnings:
                result.uq_warnings.append(w)
        return result

    def _run_multiprocess(self, sources, progress_callback,
                          has_spectral=False, n_spec_bins=0,
                          partial_result_callback=None):
        """Run each source in a separate process and merge results."""
        settings = self.project.settings
        detectors = self.project.detectors
        sphere_dets = self.project.sphere_detectors

        det_results: dict[str, DetectorResult] = {}
        for det in detectors:
            grid = np.zeros((det.resolution[1], det.resolution[0]), dtype=float)
            grid_spectral = (
                np.zeros((det.resolution[1], det.resolution[0], n_spec_bins), dtype=float)
                if has_spectral and n_spec_bins > 0 else None
            )
            det_results[det.name] = DetectorResult(
                detector_name=det.name, grid=grid, grid_spectral=grid_spectral
            )

        # Initialize merged sphere detector results
        sph_results: dict[str, SphereDetectorResult] = {}
        for sd in sphere_dets:
            n_phi, n_theta = sd.resolution
            grid = np.zeros((n_theta, n_phi), dtype=float)
            sph_results[sd.name] = SphereDetectorResult(detector_name=sd.name, grid=grid)

        # Initialize merged solid_body_stats
        merged_sb_stats: dict[str, dict[str, dict[str, float]]] = {}
        for box in self.project.solid_bodies:
            merged_sb_stats[box.name] = {
                fid: {"entering_flux": 0.0, "exiting_flux": 0.0}
                for fid in FACE_NAMES
            }
        for cyl in getattr(self.project, "solid_cylinders", []):
            merged_sb_stats[cyl.name] = {
                fid: {"entering_flux": 0.0, "exiting_flux": 0.0}
                for fid in ("top_cap", "bottom_cap", "side")
            }
        for prism in getattr(self.project, "solid_prisms", []):
            all_face_ids = ["cap_top", "cap_bottom"] + [f"side_{i}" for i in range(prism.n_sides)]
            merged_sb_stats[prism.name] = {
                fid: {"entering_flux": 0.0, "exiting_flux": 0.0}
                for fid in all_face_ids
            }

        total_emitted_flux = sum(s.effective_flux for s in sources)

        n_workers = min(len(sources), max(1, multiprocessing.cpu_count() - 1))
        completed = 0
        total = len(sources)
        escaped_total = 0.0

        # Phase 4 UQ — per-batch aggregators for MP mode (uq_batches > 0).
        # Each worker returns per-batch grids/hits/flux for its single source;
        # we sum across workers along the batch axis since all workers use
        # the same K and rays_per_batch.
        uq_K = _effective_uq_batches(settings)
        uq_grids_agg: dict[str, np.ndarray] = {}  # det_name -> (K, ny, nx) accumulator
        uq_hits_agg: dict[str, np.ndarray] = {}  # det_name -> (K,) accumulator
        uq_flux_agg: dict[str, np.ndarray] = {}  # det_name -> (K,) accumulator
        uq_sph_grids_agg: dict[str, np.ndarray] = {}
        uq_sph_hits_agg: dict[str, np.ndarray] = {}
        uq_sph_flux_agg: dict[str, np.ndarray] = {}
        uq_rays_per_batch: list[int] | None = None

        # Route to C++ fast path when the project uses only C++-supported features;
        # otherwise keep the Python spectral / solid-body worker (per 02-CONTEXT.md
        # deferred items).
        _cpp_eligible = (
            _cpp_extension_available()
            and not _project_uses_cpp_unsupported_features(self.project)
        )
        _worker = _cpp_trace_single_source if _cpp_eligible else _trace_single_source

        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            futures = []
            for src in sources:
                f = pool.submit(
                    _worker,
                    self.project, src.name, settings.random_seed,
                )
                futures.append(f)

            errors = []
            for future in futures:
                try:
                    result = future.result()
                except Exception as exc:
                    errors.append(str(exc))
                    completed += 1
                    if progress_callback:
                        progress_callback(completed / total)
                    continue
                # Merge detector grids
                for det_name, grid_data in result["grids"].items():
                    det_results[det_name].grid += grid_data["grid"]
                    det_results[det_name].total_hits += grid_data["hits"]
                    det_results[det_name].total_flux += grid_data["flux"]
                escaped_total += result["escaped"]
                # Merge spectral grids (new: from _trace_single_source spectral path)
                for det_name, sg in result.get("spectral_grids", {}).items():
                    if det_name in det_results and det_results[det_name].grid_spectral is not None:
                        det_results[det_name].grid_spectral += sg
                # Merge sphere detector grids
                for sph_name, sph_data in result.get("sph_grids", {}).items():
                    if sph_name in sph_results:
                        sph_results[sph_name].grid += sph_data["grid"]
                        sph_results[sph_name].total_hits += sph_data["hits"]
                        sph_results[sph_name].total_flux += sph_data["flux"]
                # Merge solid_body_stats
                for box_name, face_map in result.get("sb_stats", {}).items():
                    if box_name in merged_sb_stats:
                        for fid, flux_data in face_map.items():
                            merged_sb_stats[box_name][fid]["entering_flux"] += flux_data["entering_flux"]
                            merged_sb_stats[box_name][fid]["exiting_flux"] += flux_data["exiting_flux"]
                # Phase 4 UQ: merge per-batch data from worker (when K>0)
                if uq_K > 0:
                    wb_grids = result.get("grids_batches") or {}
                    for det_name, gbatch in wb_grids.items():
                        arr = np.asarray(gbatch["grid"])  # (K, ny, nx)
                        if det_name in uq_grids_agg:
                            uq_grids_agg[det_name] += arr
                        else:
                            uq_grids_agg[det_name] = arr.copy()
                    wb_hits = result.get("hits_batches") or {}
                    for det_name, hb in wb_hits.items():
                        arr = np.asarray(hb, dtype=int)
                        if det_name in uq_hits_agg:
                            uq_hits_agg[det_name] += arr
                        else:
                            uq_hits_agg[det_name] = arr.copy()
                    wb_flux = result.get("flux_batches") or {}
                    for det_name, fb in wb_flux.items():
                        arr = np.asarray(fb, dtype=float)
                        if det_name in uq_flux_agg:
                            uq_flux_agg[det_name] += arr
                        else:
                            uq_flux_agg[det_name] = arr.copy()
                    wb_sph_grids = result.get("sph_grids_batches") or {}
                    for name, gb in wb_sph_grids.items():
                        arr = np.asarray(gb["grid"])
                        if name in uq_sph_grids_agg:
                            uq_sph_grids_agg[name] += arr
                        else:
                            uq_sph_grids_agg[name] = arr.copy()
                    wb_sph_hits = result.get("sph_hits_batches") or {}
                    for name, hb in wb_sph_hits.items():
                        arr = np.asarray(hb, dtype=int)
                        if name in uq_sph_hits_agg:
                            uq_sph_hits_agg[name] += arr
                        else:
                            uq_sph_hits_agg[name] = arr.copy()
                    wb_sph_flux = result.get("sph_flux_batches") or {}
                    for name, fb in wb_sph_flux.items():
                        arr = np.asarray(fb, dtype=float)
                        if name in uq_sph_flux_agg:
                            uq_sph_flux_agg[name] += arr
                        else:
                            uq_sph_flux_agg[name] = arr.copy()
                    if uq_rays_per_batch is None:
                        rpb = result.get("rays_per_batch")
                        if rpb is not None:
                            uq_rays_per_batch = list(rpb)
                completed += 1
                if progress_callback:
                    progress_callback(completed / total)
                # Emit partial result after each source completes (live preview in MP mode)
                if partial_result_callback is not None:
                    partial_detectors = {}
                    for det_name, dr in det_results.items():
                        partial_detectors[det_name] = DetectorResult(
                            detector_name=det_name,
                            grid=dr.grid.copy(),
                            total_hits=dr.total_hits,
                            total_flux=dr.total_flux,
                            grid_spectral=dr.grid_spectral.copy() if dr.grid_spectral is not None else None,
                        )
                    partial_result_callback(SimulationResult(
                        detectors=partial_detectors,
                        sphere_detectors={},
                        total_emitted_flux=total_emitted_flux,
                        escaped_flux=escaped_total,
                        source_count=completed,
                        solid_body_stats={},
                    ))

            if errors:
                import warnings
                warnings.warn(
                    f"{len(errors)} source(s) failed in multiprocessing: {errors[0]}"
                )

        # Compute far-field candela distributions for far_field sphere detectors
        for sd in sphere_dets:
            if sd.mode == "far_field":
                compute_farfield_candela(sd, sph_results[sd.name])

        # Phase 4 UQ: populate DetectorResult batch fields from MP aggregates
        if uq_K > 0:
            for det_name, dr in det_results.items():
                if det_name in uq_grids_agg:
                    dr.grid_batches = uq_grids_agg[det_name]
                    dr.hits_batches = uq_hits_agg.get(
                        det_name, np.zeros(uq_K, dtype=int)
                    )
                    dr.flux_batches = uq_flux_agg.get(
                        det_name, np.zeros(uq_K, dtype=float)
                    )
                    dr.rays_per_batch = (
                        list(uq_rays_per_batch) if uq_rays_per_batch is not None
                        else _partition_rays(int(settings.rays_per_source), uq_K)
                    )
                    dr.n_batches = int(dr.grid_batches.shape[0])
            for name, sr in sph_results.items():
                if name in uq_sph_grids_agg:
                    setattr(sr, "grid_batches", uq_sph_grids_agg[name])
                    setattr(sr, "hits_batches", uq_sph_hits_agg.get(
                        name, np.zeros(uq_K, dtype=int)))
                    setattr(sr, "flux_batches", uq_sph_flux_agg.get(
                        name, np.zeros(uq_K, dtype=float)))
                    setattr(sr, "rays_per_batch", (
                        list(uq_rays_per_batch) if uq_rays_per_batch is not None
                        else _partition_rays(int(settings.rays_per_source), uq_K)
                    ))
                    setattr(sr, "n_batches", int(uq_sph_grids_agg[name].shape[0]))

        return SimulationResult(
            detectors=det_results,
            sphere_detectors=sph_results,
            total_emitted_flux=total_emitted_flux,
            escaped_flux=escaped_total,
            source_count=len(sources),
            solid_body_stats=merged_sb_stats,
        )

    def _run_single(self, sources, progress_callback, convergence_callback=None,
                    _adaptive=None, partial_result_callback=None,
                    _uq_in_chunk: bool = False):
        """Single-thread trace path.

        Phase 4 UQ integration (Wave 2)
        --------------------------------
        When ``settings.uq_batches > 0`` and we are *not* already re-entered
        as a UQ chunk (``_uq_in_chunk=False``), dispatches to
        :meth:`_run_uq_batched` which slices rays_per_source into K chunks,
        calls this method once per chunk with ``_uq_in_chunk=True`` and
        stacks per-batch detector grids onto the final result.  Each inner
        call has ``adaptive_sampling=False`` in its patched settings so
        convergence is evaluated only at chunk boundaries (CONTEXT D-01).

        When ``settings.uq_batches == 0`` the legacy code path below is
        executed unchanged — bit-identical determinism anchor verified by
        ``test_uq_off_matches_legacy``.
        """
        settings = self.project.settings
        # Phase 4 UQ dispatch — top-level entry only (recursion guarded by
        # _uq_in_chunk flag).
        if not _uq_in_chunk and _effective_uq_batches(settings) > 0:
            return self._run_uq_batched(
                sources, progress_callback, convergence_callback,
                _adaptive=_adaptive,
                partial_result_callback=partial_result_callback,
            )
        # _adaptive defaults to settings.adaptive_sampling unless overridden by caller
        if _adaptive is None:
            _adaptive = settings.adaptive_sampling
        surfaces = self.project.surfaces
        detectors = self.project.detectors
        sphere_dets = self.project.sphere_detectors
        materials = self.project.materials
        distributions = self.project.angular_distributions
        n_record = settings.record_ray_paths

        # Check if any source has color (non-white)
        has_color = any(s.color_rgb != (1.0, 1.0, 1.0) for s in sources)

        # Check if any source has non-white SPD
        has_spectral = any(s.spd != "white" for s in sources)
        n_spec_bins = N_SPECTRAL_BINS if has_spectral else 0
        spec_centers = spectral_bin_centers(n_spec_bins) if has_spectral else None

        # Initialise detector grids
        det_results: dict[str, DetectorResult] = {}
        for det in detectors:
            grid = np.zeros((det.resolution[1], det.resolution[0]), dtype=float)
            grid_rgb = np.zeros((det.resolution[1], det.resolution[0], 3), dtype=float) if has_color else None
            grid_spectral = np.zeros((det.resolution[1], det.resolution[0], n_spec_bins), dtype=float) if has_spectral else None
            det_results[det.name] = DetectorResult(
                detector_name=det.name, grid=grid, grid_rgb=grid_rgb,
                grid_spectral=grid_spectral
            )

        # Initialise sphere detector grids
        sph_results: dict[str, SphereDetectorResult] = {}
        for sd in sphere_dets:
            n_phi, n_theta = sd.resolution
            grid = np.zeros((n_theta, n_phi), dtype=float)
            sph_results[sd.name] = SphereDetectorResult(
                detector_name=sd.name, grid=grid
            )

        # Expand SolidBox objects into face Rectangles and build lookup
        solid_faces: list[Rectangle] = []
        # Maps face rect name -> (box, face_id, box_n)
        solid_face_map: dict[str, tuple] = {}
        for box in self.project.solid_bodies:
            mat = materials.get(box.material_name)
            box_n = mat.refractive_index if mat is not None else 1.0
            geom_eps = max(_EPSILON, min(box.dimensions) * 1e-4)
            for face in box.get_faces():
                solid_faces.append(face)
                face_id = face.name.split("::", 1)[1]
                solid_face_map[face.name] = (box, face_id, box_n, geom_eps)

        # Initialize solid_body_stats accumulator
        sb_stats: dict[str, dict[str, dict[str, float]]] = {}
        for box in self.project.solid_bodies:
            sb_stats[box.name] = {
                fid: {"entering_flux": 0.0, "exiting_flux": 0.0}
                for fid in FACE_NAMES
            }

        # Expand SolidCylinder objects into face-like objects and build lookup
        # cylinder face map: face_name -> (cyl, face_id, cyl_n, geom_eps)
        cyl_faces: list = []
        cyl_face_map: dict[str, tuple] = {}
        for cyl in getattr(self.project, "solid_cylinders", []):
            mat = materials.get(cyl.material_name)
            cyl_n = mat.refractive_index if mat is not None else 1.0
            geom_eps = max(_EPSILON, min(cyl.radius, cyl.length / 2.0) * 1e-4)
            for face in cyl.get_faces():
                cyl_faces.append(face)
                face_id = face.name.split("::", 1)[1]
                cyl_face_map[face.name] = (cyl, face_id, cyl_n, geom_eps)
            sb_stats[cyl.name] = {
                fid: {"entering_flux": 0.0, "exiting_flux": 0.0}
                for fid in ("top_cap", "bottom_cap", "side")
            }

        # Expand SolidPrism objects into face-like objects and build lookup
        prism_faces: list = []
        prism_face_map: dict[str, tuple] = {}
        for prism in getattr(self.project, "solid_prisms", []):
            mat = materials.get(prism.material_name)
            prism_n = mat.refractive_index if mat is not None else 1.0
            geom_eps = max(_EPSILON, min(prism.circumscribed_radius, prism.length / 2.0) * 1e-4)
            for face in prism.get_faces():
                prism_faces.append(face)
                face_id = face.name.split("::", 1)[1]
                prism_face_map[face.name] = (prism, face_id, prism_n, geom_eps)
            all_face_ids = ["cap_top", "cap_bottom"] + [f"side_{i}" for i in range(prism.n_sides)]
            sb_stats[prism.name] = {
                fid: {"entering_flux": 0.0, "exiting_flux": 0.0}
                for fid in all_face_ids
            }

        total_emitted_flux = sum(s.effective_flux for s in sources)

        if not sources or (not surfaces and not detectors and not sphere_dets
                           and not solid_faces and not cyl_faces and not prism_faces):
            return SimulationResult(
                detectors=det_results,
                sphere_detectors=sph_results,
                total_emitted_flux=total_emitted_flux,
                source_count=len(sources),
                solid_body_stats=sb_stats,
            )

        # ---- BVH setup for plane surfaces (activated when total geometry count >= threshold) ----
        # BVH activation threshold: use BVH when total geometry count
        # (planes + cyl + prism faces) >= _BVH_THRESHOLD
        n_all_planes = len(surfaces) + len(solid_faces)
        n_total_geom = n_all_planes + len(cyl_faces) + len(prism_faces)
        use_bvh = n_total_geom >= _BVH_THRESHOLD
        bvh_bounds = bvh_meta = bvh_n_nodes = None
        bvh_normals = bvh_centers = bvh_u = bvh_v = bvh_hw = bvh_hh = None
        n_surf_planes = len(surfaces)  # boundary index: idx < n_surf_planes -> surface, else solid face
        # Pre-computed AABBs for cyl/prism faces (used for broad-phase slab test)
        cyl_aabbs: np.ndarray | None = None
        prism_aabbs: np.ndarray | None = None

        if use_bvh and n_all_planes > 0:
            # Build flat arrays for all plane objects (surfaces + solid_faces)
            all_plane_normals = np.empty((n_all_planes, 3), dtype=np.float64)
            all_plane_centers = np.empty((n_all_planes, 3), dtype=np.float64)
            all_plane_u       = np.empty((n_all_planes, 3), dtype=np.float64)
            all_plane_v       = np.empty((n_all_planes, 3), dtype=np.float64)
            all_plane_hw      = np.empty(n_all_planes, dtype=np.float64)
            all_plane_hh      = np.empty(n_all_planes, dtype=np.float64)
            for i, surf in enumerate(surfaces):
                all_plane_normals[i] = surf.normal
                all_plane_centers[i] = surf.center
                all_plane_u[i]       = surf.u_axis
                all_plane_v[i]       = surf.v_axis
                all_plane_hw[i]      = surf.size[0] / 2.0
                all_plane_hh[i]      = surf.size[1] / 2.0
            for i, sface in enumerate(solid_faces):
                j = n_surf_planes + i
                all_plane_normals[j] = sface.normal
                all_plane_centers[j] = sface.center
                all_plane_u[j]       = sface.u_axis
                all_plane_v[j]       = sface.v_axis
                all_plane_hw[j]      = sface.size[0] / 2.0
                all_plane_hh[j]      = sface.size[1] / 2.0
            aabbs = compute_surface_aabbs(
                all_plane_normals, all_plane_centers,
                all_plane_u, all_plane_v, all_plane_hw, all_plane_hh,
            )
            bvh_bounds, bvh_meta, bvh_n_nodes = build_bvh_flat(aabbs)
            bvh_normals = all_plane_normals
            bvh_centers = all_plane_centers
            bvh_u       = all_plane_u
            bvh_v       = all_plane_v
            bvh_hw      = all_plane_hw
            bvh_hh      = all_plane_hh

        # Pre-compute conservative AABBs for cylinder/prism faces (for broad-phase slab test)
        if use_bvh and cyl_faces:
            cyl_aabb_list = []
            for cface in cyl_faces:
                c = np.asarray(cface.center, dtype=np.float64)
                if isinstance(cface, CylinderCap):
                    r = float(cface.radius)
                    cyl_aabb_list.append([c[0]-r, c[0]+r, c[1]-r, c[1]+r, c[2]-r, c[2]+r])
                else:  # CylinderSide
                    r = float(cface.radius)
                    hl = float(cface.length) / 2.0
                    extent = r + hl  # conservative sphere-bound
                    cyl_aabb_list.append([c[0]-extent, c[0]+extent,
                                          c[1]-extent, c[1]+extent,
                                          c[2]-extent, c[2]+extent])
            cyl_aabbs = np.array(cyl_aabb_list, dtype=np.float64)

        if use_bvh and prism_faces:
            prism_aabb_list = []
            for pface in prism_faces:
                c = np.asarray(pface.center, dtype=np.float64)
                if hasattr(pface, 'vertices') and pface.vertices is not None:
                    verts = np.asarray(pface.vertices, dtype=np.float64)
                    lo = verts.min(axis=0)
                    hi = verts.max(axis=0)
                    prism_aabb_list.append([lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]])
                elif hasattr(pface, 'circumscribed_radius'):
                    r = float(pface.circumscribed_radius)
                    prism_aabb_list.append([c[0]-r, c[0]+r, c[1]-r, c[1]+r, c[2]-r, c[2]+r])
                else:
                    # Rectangle side face — use u/v/size for tight AABB
                    hw_pf = pface.size[0] / 2.0
                    hh_pf = pface.size[1] / 2.0
                    corners = np.array([
                        c + hw_pf * pface.u_axis + hh_pf * pface.v_axis,
                        c + hw_pf * pface.u_axis - hh_pf * pface.v_axis,
                        c - hw_pf * pface.u_axis + hh_pf * pface.v_axis,
                        c - hw_pf * pface.u_axis - hh_pf * pface.v_axis,
                    ])
                    lo = corners.min(axis=0); hi = corners.max(axis=0)
                    prism_aabb_list.append([lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]])
            prism_aabbs = np.array(prism_aabb_list, dtype=np.float64)

        # Pre-compute BSDF CDFs for all profiles in the project
        bsdf_cdf_cache: dict[str, dict] = {}
        for bsdf_name, bsdf_profile in (self.project.bsdf_profiles or {}).items():
            bsdf_cdf_cache[bsdf_name] = precompute_bsdf_cdfs(bsdf_profile)

        total_rays = len(sources) * settings.rays_per_source
        rays_processed = 0
        all_paths: list[list[np.ndarray]] = []
        escaped_flux = 0.0

        # ---- C++ fast-path eligibility (Plan 02-03, D-02/D-03) ----
        # Route non-spectral scenes without solid bodies / BSDF / far-field /
        # record_ray_paths / adaptive convergence to the C++ extension. Scenes
        # with features outside the C++ Wave 2 scope keep the Python bounce
        # loop below. convergence_callback, adaptive, and record_ray_paths all
        # need Python loop hooks, so they force the Python path.
        _cpp_path = (
            _cpp_extension_available()
            and not _project_uses_cpp_unsupported_features(self.project)
            and n_record == 0
            and not _adaptive
            and convergence_callback is None
        )

        for src_idx, source in enumerate(sources):
            if self._cancelled:
                break

            # --- C++ fast path (non-spectral, plane-surfaces-only scenes) ---
            if _cpp_path:
                import hashlib
                eff_flux_src = source.effective_flux
                if source.flux_tolerance > 0:
                    tol = source.flux_tolerance / 100.0
                    eff_flux_src *= (1.0 + self.rng.uniform(-tol, tol))
                project_dict = _serialize_project(self.project)
                # Patch the serialized source effective_flux with the jittered value
                # so the C++ extension uses the exact same per-source flux Python
                # would have used.
                for src_item in project_dict["sources"]:
                    if src_item["name"] == source.name:
                        src_item["effective_flux"] = float(eff_flux_src)
                        break
                # Mask to signed int32 range — C++ extension takes `int seed`
                # and large unsigned md5 hashes would raise TypeError otherwise.
                seed_hash = int(
                    hashlib.md5(
                        f"{settings.random_seed}_{source.name}".encode()
                    ).hexdigest()[:8],
                    16,
                ) & 0x7FFFFFFF
                result_dict = _blu_tracer.trace_source(
                    project_dict, source.name, int(seed_hash)
                )
                # Merge C++ result into Python accumulators
                for det_name, grid_data in result_dict.get("grids", {}).items():
                    if det_name in det_results:
                        det_results[det_name].grid += np.asarray(grid_data["grid"])
                        det_results[det_name].total_hits += int(grid_data["hits"])
                        det_results[det_name].total_flux += float(grid_data["flux"])
                escaped_flux += float(result_dict.get("escaped", 0.0))
                for sph_name, sph_data in result_dict.get("sph_grids", {}).items():
                    if sph_name in sph_results:
                        sph_results[sph_name].grid += np.asarray(sph_data["grid"])
                        sph_results[sph_name].total_hits += int(sph_data["hits"])
                        sph_results[sph_name].total_flux += float(sph_data["flux"])
                for body_name, face_map in result_dict.get("sb_stats", {}).items():
                    if body_name in sb_stats:
                        for fid, flux_data in face_map.items():
                            if fid in sb_stats[body_name]:
                                sb_stats[body_name][fid]["entering_flux"] += float(
                                    flux_data.get("entering_flux", 0.0)
                                )
                                sb_stats[body_name][fid]["exiting_flux"] += float(
                                    flux_data.get("exiting_flux", 0.0)
                                )
                rays_processed += settings.rays_per_source
                if progress_callback:
                    progress = rays_processed / total_rays
                    progress_callback(progress)
                    if partial_result_callback is not None and progress >= 0.05:
                        partial_detectors = {}
                        for det_name, dr in det_results.items():
                            partial_detectors[det_name] = DetectorResult(
                                detector_name=det_name,
                                grid=dr.grid.copy(),
                                total_hits=dr.total_hits,
                                total_flux=dr.total_flux,
                                grid_spectral=dr.grid_spectral.copy()
                                if dr.grid_spectral is not None else None,
                            )
                        partial = SimulationResult(
                            detectors=partial_detectors,
                            ray_paths=[],
                            escaped_flux=escaped_flux,
                            total_emitted_flux=total_emitted_flux,
                            source_count=src_idx + 1,
                        )
                        partial_result_callback(partial)
                continue
            # --- end C++ fast path ---

            n_total = settings.rays_per_source
            eff_flux = source.effective_flux
            if source.flux_tolerance > 0:
                tol = source.flux_tolerance / 100.0
                eff_flux *= (1.0 + self.rng.uniform(-tol, tol))

            # ---- path recording setup ----
            # Distribute recorded rays evenly across all sources
            if n_record > 0:
                per_src = max(1, n_record // len(sources))
                # Give remainder to earlier sources
                extra = 1 if src_idx < (n_record % len(sources)) else 0
                n_rec = min(per_src + extra, n_total)
            else:
                n_rec = 0
            record = n_rec > 0
            paths: list[list[np.ndarray]] = [
                [source.position.copy()] for _ in range(n_rec)
            ]

            # ---- Adaptive batch loop ----
            # When _adaptive is True: emit batches of check_interval rays and stop
            # early when detector CV% converges below convergence_cv_target.
            # When False: emit all n_total rays as one batch (original behavior).
            check_interval = max(1, settings.check_interval) if _adaptive else n_total
            n_rays_traced = 0
            paths_recorded = False  # path recording happens only in first batch
            # Per-batch mean flux accumulator for convergence estimation
            # Snapshot cumulative flux BEFORE this source so we track per-source delta
            _flux_before_source = sum(dr.total_flux for dr in det_results.values())
            batch_fluxes: list[float] = []

            while n_rays_traced < n_total and not self._cancelled:
                n = min(check_interval, n_total - n_rays_traced)  # batch size
                batch_n_rec = n_rec if (not paths_recorded and record) else 0

                # ---- emit batch of rays ----
                if source.distribution == "lambertian":
                    directions = sample_lambertian(n, source.direction, self.rng)
                elif source.distribution == "isotropic":
                    directions = sample_isotropic(n, self.rng)
                else:
                    profile = distributions.get(source.distribution)
                    if profile and "theta_deg" in profile and "intensity" in profile:
                        directions = sample_angular_distribution(
                            n,
                            source.direction,
                            np.asarray(profile["theta_deg"], dtype=float),
                            np.asarray(profile["intensity"], dtype=float),
                            self.rng,
                        )
                    else:
                        directions = sample_isotropic(n, self.rng)

                origins = np.tile(source.position, (n, 1)).copy()
                weights = np.full(n, eff_flux / n_total)
                alive = np.ones(n, dtype=bool)
                # Per-ray refractive index tracking (starts in air, n=1.0)
                current_n = np.ones(n, dtype=float)
                n_stack = np.ones((n, _N_STACK_MAX), dtype=float)
                n_depth = np.zeros(n, dtype=int)

                # Sample wavelengths per ray (use custom project SPD profiles if available)
                if has_spectral:
                    wavelengths = sample_wavelengths(
                        n, source.spd, self.rng,
                        spd_profiles=self.project.spd_profiles or None,
                    )
                else:
                    wavelengths = None

                # For path recording: only first batch uses paths list
                if batch_n_rec > 0 and not paths_recorded:
                    active_paths = paths
                else:
                    active_paths = []
                n_rec_active = batch_n_rec

                # ---- bounce loop ----
                for _bounce in range(settings.max_bounces):
                    if self._cancelled:
                        break
                    if not alive.any():
                        break

                    active_idx = np.where(alive)[0]
                    active_origins = origins[active_idx]
                    active_dirs = directions[active_idx]
                    n_active = len(active_idx)

                    best_t = np.full(n_active, np.inf)
                    best_type = np.full(n_active, -1, dtype=int)
                    best_obj = np.full(n_active, -1, dtype=int)

                    if use_bvh:
                        # BVH path: single traversal covers all surfaces + solid_faces
                        bvh_t, bvh_idx = traverse_bvh_batch(
                            np.ascontiguousarray(active_origins, dtype=np.float64),
                            np.ascontiguousarray(active_dirs,   dtype=np.float64),
                            bvh_bounds, bvh_meta, bvh_n_nodes,
                            bvh_normals, bvh_centers, bvh_u, bvh_v, bvh_hw, bvh_hh,
                            _EPSILON,
                        )
                        hit_mask = bvh_idx >= 0
                        for ri in np.where(hit_mask)[0]:
                            idx = int(bvh_idx[ri])
                            t_val = float(bvh_t[ri])
                            if t_val < best_t[ri]:
                                best_t[ri] = t_val
                                if idx < n_surf_planes:
                                    best_type[ri] = 0
                                    best_obj[ri] = idx
                                else:
                                    best_type[ri] = 3
                                    best_obj[ri] = idx - n_surf_planes
                    else:
                        # Brute-force path (< _BVH_THRESHOLD surfaces)
                        for si, surf in enumerate(surfaces):
                            t = _intersect_plane_accel(active_origins, active_dirs, surf.normal, surf.center,
                                                       surf.u_axis, surf.v_axis, surf.size)
                            closer = t < best_t
                            best_t[closer] = t[closer]
                            best_type[closer] = 0
                            best_obj[closer] = si

                        # SolidBox face intersections (type 3)
                        for sfi, sface in enumerate(solid_faces):
                            t = _intersect_plane_accel(active_origins, active_dirs,
                                                       sface.normal, sface.center,
                                                       sface.u_axis, sface.v_axis, sface.size)
                            closer = t < best_t
                            best_t[closer] = t[closer]
                            best_type[closer] = 3
                            best_obj[closer] = sfi

                    # SolidCylinder face intersections (type 4) — AABB pre-filter when BVH active
                    cyl_candidates = (
                        _aabb_ray_candidates(active_origins, active_dirs, cyl_aabbs)
                        if use_bvh and cyl_aabbs is not None
                        else range(len(cyl_faces))
                    )
                    for cfi in cyl_candidates:
                        cface = cyl_faces[cfi]
                        if isinstance(cface, CylinderCap):
                            t = _intersect_rays_disc(
                                active_origins, active_dirs,
                                cface.center, cface.normal, cface.radius,
                            )
                        else:  # CylinderSide
                            t = _intersect_rays_cylinder_side(
                                active_origins, active_dirs,
                                cface.center, cface.axis, cface.radius, cface.length / 2.0,
                            )
                        closer = t < best_t
                        best_t[closer] = t[closer]
                        best_type[closer] = 4
                        best_obj[closer] = cfi

                    # SolidPrism face intersections (type 5) — AABB pre-filter when BVH active
                    prism_candidates = (
                        _aabb_ray_candidates(active_origins, active_dirs, prism_aabbs)
                        if use_bvh and prism_aabbs is not None
                        else range(len(prism_faces))
                    )
                    for pfi in prism_candidates:
                        pface = prism_faces[pfi]
                        if isinstance(pface, PrismCap):
                            t = _intersect_prism_cap(active_origins, active_dirs, pface)
                        else:  # Rectangle side face
                            t = _intersect_plane_accel(
                                active_origins, active_dirs,
                                pface.normal, pface.center,
                                pface.u_axis, pface.v_axis, pface.size,
                            )
                        closer = t < best_t
                        best_t[closer] = t[closer]
                        best_type[closer] = 5
                        best_obj[closer] = pfi

                    # Detectors and sphere detectors are always tested separately (few, different logic)
                    for di, det in enumerate(detectors):
                        t = _intersect_plane_accel(active_origins, active_dirs, det.normal, det.center,
                                                   det.u_axis, det.v_axis, det.size)
                        closer = t < best_t
                        best_t[closer] = t[closer]
                        best_type[closer] = 1
                        best_obj[closer] = di

                    for sdi, sd in enumerate(sphere_dets):
                        t = _intersect_sphere_accel(active_origins, active_dirs, sd.center, sd.radius)
                        closer = t < best_t
                        best_t[closer] = t[closer]
                        best_type[closer] = 2
                        best_obj[closer] = sdi

                    # Rays that escape
                    missed = best_t == np.inf
                    if missed.any():
                        escaped_flux += float(weights[active_idx[missed]].sum())
                    alive[active_idx[missed]] = False

                    # Detector hits — pass-through: accumulate flux then continue
                    for di, det in enumerate(detectors):
                        mask = (best_type == 1) & (best_obj == di)
                        if not mask.any():
                            continue
                        hit_idx = active_idx[mask]
                        hit_pts = origins[hit_idx] + best_t[mask, None] * directions[hit_idx]
                        hit_wl = wavelengths[hit_idx] if wavelengths is not None else None
                        _accumulate(det, det_results[det.name], hit_pts, weights[hit_idx],
                                    source.color_rgb if has_color else None,
                                    hit_wl, spec_centers)
                        if n_rec_active > 0:
                            for local_i, global_i in enumerate(hit_idx):
                                if global_i < n_rec_active:
                                    active_paths[global_i].append(hit_pts[local_i].copy())
                        # Advance ray past the detector plane
                        origins[hit_idx] = hit_pts + directions[hit_idx] * _EPSILON

                    # Sphere detector hits — pass-through: accumulate flux then continue
                    for sdi, sd in enumerate(sphere_dets):
                        mask = (best_type == 2) & (best_obj == sdi)
                        if not mask.any():
                            continue
                        hit_idx = active_idx[mask]
                        hit_pts = origins[hit_idx] + best_t[mask, None] * directions[hit_idx]
                        if sd.mode == "far_field":
                            _accumulate_sphere_farfield(sd, sph_results[sd.name],
                                                        directions[hit_idx], weights[hit_idx])
                        else:
                            _accumulate_sphere(sd, sph_results[sd.name], hit_pts, weights[hit_idx])
                        if n_rec_active > 0:
                            for local_i, global_i in enumerate(hit_idx):
                                if global_i < n_rec_active:
                                    active_paths[global_i].append(hit_pts[local_i].copy())
                        # Advance ray past the sphere surface
                        origins[hit_idx] = hit_pts + directions[hit_idx] * _EPSILON

                    # SolidBox face hits — Fresnel/TIR physics
                    for sfi, sface in enumerate(solid_faces):
                        mask = (best_type == 3) & (best_obj == sfi)
                        if not mask.any():
                            continue
                        hit_idx = active_idx[mask]
                        t_vals = best_t[mask]
                        hit_pts = origins[hit_idx] + t_vals[:, None] * directions[hit_idx]
                        face_normal = sface.normal   # (3,) static

                        box, face_id, box_n, geom_eps = solid_face_map[sface.name]

                        # --- face_optics override: per-face optical property (e.g., LGP bottom reflector) ---
                        face_op_name = getattr(sface, "optical_properties_name", "")
                        if face_op_name:
                            face_op = self.project.optical_properties.get(face_op_name)
                            if face_op is not None and face_op.surface_type in ("reflector", "absorber", "diffuser"):
                                _dot_dn = np.einsum("ij,j->i", directions[hit_idx], face_normal)
                                _flip = _dot_dn > 0
                                _on = np.where(_flip[:, None], -face_normal, face_normal)

                                # Record waypoints
                                if n_rec_active > 0:
                                    for local_i, global_i in enumerate(hit_idx):
                                        if global_i < n_rec_active:
                                            active_paths[global_i].append(hit_pts[local_i].copy())

                                # Flux accounting
                                _entering = _dot_dn < 0
                                for local_i, global_i in enumerate(hit_idx):
                                    w = float(weights[global_i])
                                    if _entering[local_i]:
                                        sb_stats[box.name][face_id]["entering_flux"] += w
                                    else:
                                        sb_stats[box.name][face_id]["exiting_flux"] += w

                                if face_op.surface_type == "absorber":
                                    alive[hit_idx] = False
                                    continue
                                elif face_op.surface_type == "reflector":
                                    weights[hit_idx] *= face_op.reflectance
                                    new_dirs = _reflect_batch(directions[hit_idx], _on,
                                                              face_op.is_diffuse, self.rng)
                                    if face_op.haze > 0 and not face_op.is_diffuse:
                                        new_dirs = scatter_haze(new_dirs, face_op.haze, self.rng)
                                    origins[hit_idx] = hit_pts + _on * geom_eps
                                    directions[hit_idx] = new_dirs
                                    continue
                                elif face_op.surface_type == "diffuser":
                                    n_rays_fo = len(hit_idx)
                                    roll_fo = self.rng.uniform(size=n_rays_fo)
                                    transmits_fo = roll_fo < face_op.transmittance
                                    if transmits_fo.any():
                                        ti_fo = hit_idx[transmits_fo]
                                        through_n_fo = -_on[transmits_fo]
                                        origins[ti_fo] = hit_pts[transmits_fo] + through_n_fo * geom_eps
                                        # Per-ray Lambertian to handle mixed-side hits correctly
                                        _n_tr_fo = int(transmits_fo.sum())
                                        _new_d_fo = np.empty((_n_tr_fo, 3))
                                        for _j in range(_n_tr_fo):
                                            _new_d_fo[_j] = sample_lambertian(1, through_n_fo[_j], self.rng)[0]
                                        directions[ti_fo] = _new_d_fo
                                    reflects_fo = ~transmits_fo
                                    if reflects_fo.any():
                                        ri_fo = hit_idx[reflects_fo]
                                        weights[ri_fo] *= face_op.reflectance
                                        refl_on_fo = _on[reflects_fo]
                                        new_d_fo = _reflect_batch(directions[ri_fo], refl_on_fo,
                                                                   face_op.is_diffuse, self.rng)
                                        origins[ri_fo] = hit_pts[reflects_fo] + refl_on_fo * geom_eps
                                        directions[ri_fo] = new_d_fo
                                    continue
                        # --- end face_optics override --- fall through to standard Fresnel below

                        # Determine entering vs exiting.
                        # face_normal is the outward normal (points out of the box).
                        # dot(d, face_normal) < 0 → ray goes against outward normal → entering.
                        dot_dn = np.einsum("ij,j->i", directions[hit_idx], face_normal)
                        entering = dot_dn < 0   # ray going against face normal = entering

                        # on_into: normal pointing INTO the new medium.
                        # Entering: new medium is box interior → on_into = -face_normal
                        # Exiting: new medium is air → on_into = +face_normal
                        on_into = np.where(entering[:, None], -face_normal, face_normal)

                        # on_back: normal pointing TOWARD incoming ray (into old medium = -on_into).
                        # Used for origin offset after reflection (to push back into old medium).
                        on_back = -on_into   # points back toward incoming medium

                        n1_arr = current_n[hit_idx].copy()
                        exit_n = n_stack[hit_idx, np.maximum(n_depth[hit_idx] - 1, 0)]
                        # Spectral n(lambda) for SolidBox material
                        spec_data_sb = (self.project.spectral_material_data or {}).get(box.material_name) if wavelengths is not None else None
                        if spec_data_sb is not None and "refractive_index" in spec_data_sb:
                            spec_wl_sb = np.asarray(spec_data_sb["wavelength_nm"], dtype=float)
                            n_lambda_sb = np.interp(wavelengths[hit_idx], spec_wl_sb,
                                                    np.asarray(spec_data_sb["refractive_index"], dtype=float))
                            n2_arr = np.where(entering, n_lambda_sb, exit_n)
                        else:
                            n2_arr = np.where(entering, box_n, exit_n)

                        # cos_i = dot(d, on_into) because _fresnel_unpolarized convention:
                        # cos_theta_i is the cosine between ray and normal pointing into new medium,
                        # which equals dot(d, on_into) for a properly oriented ray.
                        cos_i_arr = np.clip(np.einsum("ij,ij->i", directions[hit_idx], on_into), 0.0, 1.0)

                        R_arr = _fresnel_unpolarized(cos_i_arr, n1_arr, n2_arr)

                        # Stochastic Russian roulette: reflect or transmit
                        roll = self.rng.random(len(hit_idx))
                        reflects = roll < R_arr
                        refracts = ~reflects

                        if n_rec_active > 0:
                            for local_i, global_i in enumerate(hit_idx):
                                if global_i < n_rec_active:
                                    active_paths[global_i].append(hit_pts[local_i].copy())

                        # Flux accounting
                        for local_i, global_i in enumerate(hit_idx):
                            fid = face_id
                            w = float(weights[global_i])
                            if entering[local_i]:
                                sb_stats[box.name][fid]["entering_flux"] += w
                            else:
                                sb_stats[box.name][fid]["exiting_flux"] += w

                        # --- Refracted rays ---
                        if refracts.any():
                            ri = hit_idx[refracts]
                            on_r = on_into[refracts]
                            n1_r = n1_arr[refracts]
                            n2_r = n2_arr[refracts]
                            new_dirs = _refract_snell(directions[ri], on_r, n1_r, n2_r)
                            current_n[ri] = n2_r
                            _n_stack_update(n_depth, n_stack, ri, entering[refracts], n1_r)
                            # Offset origin into new medium (along on_into direction)
                            origins[ri] = hit_pts[refracts] + on_r * geom_eps
                            directions[ri] = new_dirs

                        # --- Reflected rays ---
                        if reflects.any():
                            rfl_i = hit_idx[reflects]
                            on_b = on_back[reflects]   # points toward incoming ray (old medium)
                            # Specular reflection: d' = d - 2*(d·n_hat)*n_hat
                            # where n_hat points TOWARD incoming ray = on_back
                            d_rfl = directions[rfl_i]
                            dot_vals = np.einsum("ij,ij->i", d_rfl, on_b)[:, None]
                            new_dirs = d_rfl - 2.0 * dot_vals * on_b
                            norms = np.linalg.norm(new_dirs, axis=1, keepdims=True)
                            new_dirs = new_dirs / np.maximum(norms, 1e-12)
                            # current_n stays the same for reflected rays
                            # Offset back into the old medium (along on_back direction)
                            origins[rfl_i] = hit_pts[reflects] + on_b * geom_eps
                            directions[rfl_i] = new_dirs

                    # SolidCylinder face hits (type 4) -- Fresnel/TIR physics
                    for cfi, cface in enumerate(cyl_faces):
                        mask = (best_type == 4) & (best_obj == cfi)
                        if not mask.any():
                            continue
                        hit_idx = active_idx[mask]
                        t_vals = best_t[mask]
                        hit_pts = origins[hit_idx] + t_vals[:, None] * directions[hit_idx]
                        cyl, face_id, cyl_n, geom_eps = cyl_face_map[cface.name]
                        if isinstance(cface, CylinderSide):
                            cyl_axis = cface.axis
                            diff = hit_pts - cyl.center
                            proj = np.einsum("ij,j->i", diff, cyl_axis)
                            radial = diff - proj[:, None] * cyl_axis
                            r_norms = np.linalg.norm(radial, axis=1, keepdims=True)
                            face_normals = radial / np.maximum(r_norms, 1e-12)
                            dot_dn = np.einsum("ij,ij->i", directions[hit_idx], face_normals)
                            entering = dot_dn < 0
                            on_into = np.where(entering[:, None], -face_normals, face_normals)
                        else:
                            face_normal = cface.normal
                            dot_dn = np.einsum("ij,j->i", directions[hit_idx], face_normal)
                            entering = dot_dn < 0
                            on_into = np.where(entering[:, None], -face_normal, face_normal)
                        on_back = -on_into
                        # --- face_optics override: per-face optical property ---
                        _fo_name = getattr(cface, "optical_properties_name", "")
                        if _fo_name:
                            _fo = self.project.optical_properties.get(_fo_name)
                            if _fo is not None and _fo.surface_type in ("reflector", "absorber", "diffuser"):
                                if n_rec_active > 0:
                                    for local_i, global_i in enumerate(hit_idx):
                                        if global_i < n_rec_active:
                                            active_paths[global_i].append(hit_pts[local_i].copy())
                                for local_i, global_i in enumerate(hit_idx):
                                    w = float(weights[global_i])
                                    if entering[local_i]:
                                        sb_stats[cyl.name][face_id]["entering_flux"] += w
                                    else:
                                        sb_stats[cyl.name][face_id]["exiting_flux"] += w
                                if _fo.surface_type == "absorber":
                                    alive[hit_idx] = False
                                    continue
                                elif _fo.surface_type == "reflector":
                                    weights[hit_idx] *= _fo.reflectance
                                    new_dirs = _reflect_batch(directions[hit_idx], on_back,
                                                              _fo.is_diffuse, self.rng)
                                    if _fo.haze > 0 and not _fo.is_diffuse:
                                        new_dirs = scatter_haze(new_dirs, _fo.haze, self.rng)
                                    origins[hit_idx] = hit_pts + on_back * geom_eps
                                    directions[hit_idx] = new_dirs
                                    continue
                                elif _fo.surface_type == "diffuser":
                                    _n_fo = len(hit_idx)
                                    _roll_fo = self.rng.uniform(size=_n_fo)
                                    _transmits = _roll_fo < _fo.transmittance
                                    if _transmits.any():
                                        _ti = hit_idx[_transmits]
                                        _through_n = on_into[_transmits]
                                        origins[_ti] = hit_pts[_transmits] + _through_n * geom_eps
                                        _n_tr = int(_transmits.sum())
                                        _new_d = np.empty((_n_tr, 3))
                                        for _j in range(_n_tr):
                                            _new_d[_j] = sample_lambertian(1, _through_n[_j], self.rng)[0]
                                        directions[_ti] = _new_d
                                    _reflects = ~_transmits
                                    if _reflects.any():
                                        _ri = hit_idx[_reflects]
                                        weights[_ri] *= _fo.reflectance
                                        _refl_on = on_back[_reflects]
                                        _new_d_r = _reflect_batch(directions[_ri], _refl_on,
                                                                   _fo.is_diffuse, self.rng)
                                        origins[_ri] = hit_pts[_reflects] + _refl_on * geom_eps
                                        directions[_ri] = _new_d_r
                                    continue
                        n1_arr = current_n[hit_idx].copy()
                        exit_n = n_stack[hit_idx, np.maximum(n_depth[hit_idx] - 1, 0)]
                        # Spectral n(lambda) for SolidCylinder material
                        spec_data_cyl = (self.project.spectral_material_data or {}).get(cyl.material_name) if wavelengths is not None else None
                        if spec_data_cyl is not None and "refractive_index" in spec_data_cyl:
                            spec_wl_cyl = np.asarray(spec_data_cyl["wavelength_nm"], dtype=float)
                            n_lambda_cyl = np.interp(wavelengths[hit_idx], spec_wl_cyl,
                                                     np.asarray(spec_data_cyl["refractive_index"], dtype=float))
                            n2_arr = np.where(entering, n_lambda_cyl, exit_n)
                        else:
                            n2_arr = np.where(entering, cyl_n, exit_n)
                        cos_i_arr = np.clip(np.einsum("ij,ij->i", directions[hit_idx], on_into), 0.0, 1.0)
                        R_arr = _fresnel_unpolarized(cos_i_arr, n1_arr, n2_arr)
                        roll = self.rng.random(len(hit_idx))
                        reflects = roll < R_arr
                        refracts = ~reflects
                        if n_rec_active > 0:
                            for local_i, global_i in enumerate(hit_idx):
                                if global_i < n_rec_active:
                                    active_paths[global_i].append(hit_pts[local_i].copy())
                        for local_i, global_i in enumerate(hit_idx):
                            w = float(weights[global_i])
                            if entering[local_i]:
                                sb_stats[cyl.name][face_id]["entering_flux"] += w
                            else:
                                sb_stats[cyl.name][face_id]["exiting_flux"] += w
                        if refracts.any():
                            ri = hit_idx[refracts]
                            on_r = on_into[refracts]
                            n1_r = n1_arr[refracts]
                            n2_r = n2_arr[refracts]
                            new_dirs = _refract_snell(directions[ri], on_r, n1_r, n2_r)
                            current_n[ri] = n2_r
                            _n_stack_update(n_depth, n_stack, ri, entering[refracts], n1_r)
                            origins[ri] = hit_pts[refracts] + on_r * geom_eps
                            directions[ri] = new_dirs
                        if reflects.any():
                            rfl_i = hit_idx[reflects]
                            on_b = on_back[reflects]
                            d_rfl = directions[rfl_i]
                            dot_vals = np.einsum("ij,ij->i", d_rfl, on_b)[:, None]
                            new_dirs = d_rfl - 2.0 * dot_vals * on_b
                            norms_r = np.linalg.norm(new_dirs, axis=1, keepdims=True)
                            new_dirs = new_dirs / np.maximum(norms_r, 1e-12)
                            origins[rfl_i] = hit_pts[reflects] + on_b * geom_eps
                            directions[rfl_i] = new_dirs

                    # SolidPrism face hits (type 5) -- Fresnel/TIR physics
                    for pfi, pface in enumerate(prism_faces):
                        mask = (best_type == 5) & (best_obj == pfi)
                        if not mask.any():
                            continue
                        hit_idx = active_idx[mask]
                        t_vals = best_t[mask]
                        hit_pts = origins[hit_idx] + t_vals[:, None] * directions[hit_idx]
                        prism, face_id, prism_n, geom_eps = prism_face_map[pface.name]
                        face_normal = pface.normal
                        dot_dn = np.einsum("ij,j->i", directions[hit_idx], face_normal)
                        entering = dot_dn < 0
                        on_into = np.where(entering[:, None], -face_normal, face_normal)
                        on_back = -on_into
                        # --- face_optics override: per-face optical property ---
                        _fo_name = getattr(pface, "optical_properties_name", "")
                        if _fo_name:
                            _fo = self.project.optical_properties.get(_fo_name)
                            if _fo is not None and _fo.surface_type in ("reflector", "absorber", "diffuser"):
                                if n_rec_active > 0:
                                    for local_i, global_i in enumerate(hit_idx):
                                        if global_i < n_rec_active:
                                            active_paths[global_i].append(hit_pts[local_i].copy())
                                for local_i, global_i in enumerate(hit_idx):
                                    w = float(weights[global_i])
                                    if entering[local_i]:
                                        sb_stats[prism.name][face_id]["entering_flux"] += w
                                    else:
                                        sb_stats[prism.name][face_id]["exiting_flux"] += w
                                if _fo.surface_type == "absorber":
                                    alive[hit_idx] = False
                                    continue
                                elif _fo.surface_type == "reflector":
                                    weights[hit_idx] *= _fo.reflectance
                                    new_dirs = _reflect_batch(directions[hit_idx], on_back,
                                                              _fo.is_diffuse, self.rng)
                                    if _fo.haze > 0 and not _fo.is_diffuse:
                                        new_dirs = scatter_haze(new_dirs, _fo.haze, self.rng)
                                    origins[hit_idx] = hit_pts + on_back * geom_eps
                                    directions[hit_idx] = new_dirs
                                    continue
                                elif _fo.surface_type == "diffuser":
                                    _n_fo = len(hit_idx)
                                    _roll_fo = self.rng.uniform(size=_n_fo)
                                    _transmits = _roll_fo < _fo.transmittance
                                    if _transmits.any():
                                        _ti = hit_idx[_transmits]
                                        _through_n = on_into[_transmits]
                                        origins[_ti] = hit_pts[_transmits] + _through_n * geom_eps
                                        _n_tr = int(_transmits.sum())
                                        _new_d = np.empty((_n_tr, 3))
                                        for _j in range(_n_tr):
                                            _new_d[_j] = sample_lambertian(1, _through_n[_j], self.rng)[0]
                                        directions[_ti] = _new_d
                                    _reflects = ~_transmits
                                    if _reflects.any():
                                        _ri = hit_idx[_reflects]
                                        weights[_ri] *= _fo.reflectance
                                        _refl_on = on_back[_reflects]
                                        _new_d_r = _reflect_batch(directions[_ri], _refl_on,
                                                                   _fo.is_diffuse, self.rng)
                                        origins[_ri] = hit_pts[_reflects] + _refl_on * geom_eps
                                        directions[_ri] = _new_d_r
                                    continue
                        n1_arr = current_n[hit_idx].copy()
                        exit_n = n_stack[hit_idx, np.maximum(n_depth[hit_idx] - 1, 0)]
                        # Spectral n(lambda) for SolidPrism material
                        spec_data_prism = (self.project.spectral_material_data or {}).get(prism.material_name) if wavelengths is not None else None
                        if spec_data_prism is not None and "refractive_index" in spec_data_prism:
                            spec_wl_prism = np.asarray(spec_data_prism["wavelength_nm"], dtype=float)
                            n_lambda_prism = np.interp(wavelengths[hit_idx], spec_wl_prism,
                                                       np.asarray(spec_data_prism["refractive_index"], dtype=float))
                            n2_arr = np.where(entering, n_lambda_prism, exit_n)
                        else:
                            n2_arr = np.where(entering, prism_n, exit_n)
                        cos_i_arr = np.clip(np.einsum("ij,ij->i", directions[hit_idx], on_into), 0.0, 1.0)
                        R_arr = _fresnel_unpolarized(cos_i_arr, n1_arr, n2_arr)
                        roll = self.rng.random(len(hit_idx))
                        reflects = roll < R_arr
                        refracts = ~reflects
                        if n_rec_active > 0:
                            for local_i, global_i in enumerate(hit_idx):
                                if global_i < n_rec_active:
                                    active_paths[global_i].append(hit_pts[local_i].copy())
                        for local_i, global_i in enumerate(hit_idx):
                            w = float(weights[global_i])
                            if entering[local_i]:
                                sb_stats[prism.name][face_id]["entering_flux"] += w
                            else:
                                sb_stats[prism.name][face_id]["exiting_flux"] += w
                        if refracts.any():
                            ri = hit_idx[refracts]
                            on_r = on_into[refracts]
                            n1_r = n1_arr[refracts]
                            n2_r = n2_arr[refracts]
                            new_dirs = _refract_snell(directions[ri], on_r, n1_r, n2_r)
                            current_n[ri] = n2_r
                            _n_stack_update(n_depth, n_stack, ri, entering[refracts], n1_r)
                            origins[ri] = hit_pts[refracts] + on_r * geom_eps
                            directions[ri] = new_dirs
                        if reflects.any():
                            rfl_i = hit_idx[reflects]
                            on_b = on_back[reflects]
                            d_rfl = directions[rfl_i]
                            dot_vals = np.einsum("ij,ij->i", d_rfl, on_b)[:, None]
                            new_dirs = d_rfl - 2.0 * dot_vals * on_b
                            norms_r = np.linalg.norm(new_dirs, axis=1, keepdims=True)
                            new_dirs = new_dirs / np.maximum(norms_r, 1e-12)
                            origins[rfl_i] = hit_pts[reflects] + on_b * geom_eps
                            directions[rfl_i] = new_dirs

                    # Surface hits
                    surf_hit_mask = (best_type == 0) & ~missed
                    if surf_hit_mask.any():
                        self._bounce_surfaces(
                            surf_hit_mask, active_idx, best_t, best_obj,
                            origins, directions, weights, alive, surfaces, materials,
                            active_paths, n_rec_active,
                            wavelengths=wavelengths,
                            spectral_material_data=self.project.spectral_material_data or None,
                            bsdf_cdf_cache=bsdf_cdf_cache,
                        )

                    alive[weights < settings.energy_threshold] = False

                # end bounce loop
                pass

                # ---- Post-batch: path collection, convergence check ----
                if batch_n_rec > 0 and not paths_recorded:
                    # First batch: extend all_paths with the recorded paths
                    # (active_paths IS paths, so no copy needed)
                    paths_recorded = True

                n_rays_traced += n
                # Track per-source flux delta (not cumulative across sources)
                batch_fluxes.append(sum(dr.total_flux for dr in det_results.values()) - _flux_before_source)

                # Convergence check (requires >= 2 batches and adaptive mode)
                if _adaptive:
                    if len(batch_fluxes) >= 2:
                        mean_f = float(sum(batch_fluxes) / len(batch_fluxes))
                        var_f = max(0.0, sum((f - mean_f) ** 2 for f in batch_fluxes) / len(batch_fluxes))
                        std_f = float(var_f ** 0.5)
                        n_b = len(batch_fluxes)
                        ci = 1.96 * std_f / max(float(n_b ** 0.5), 1e-12)
                        cv_pct = ci / max(abs(mean_f), 1e-12) * 100.0
                        if convergence_callback is not None:
                            convergence_callback(src_idx, n_rays_traced, cv_pct)
                        if cv_pct <= settings.convergence_cv_target:
                            # Converged — stop early
                            break
                    else:
                        # First batch only — report 100% CV (not yet converged)
                        cv_pct = 100.0
                        if convergence_callback is not None:
                            convergence_callback(src_idx, n_rays_traced, cv_pct)

                # end while (adaptive batch loop)

                # n is the last batch_size; use n_total for progress
                n = n_total  # restore for progress tracking

            # Collect paths for this source
            if record:
                all_paths.extend(paths)

            rays_processed += n_total
            if progress_callback:
                progress = rays_processed / total_rays
                progress_callback(progress)
                # Emit partial result snapshot at source completion points (~5% intervals)
                if partial_result_callback and progress >= 0.05:
                    partial_detectors = {}
                    for det_name, dr in det_results.items():
                        partial_detectors[det_name] = DetectorResult(
                            detector_name=det_name,
                            grid=dr.grid.copy(),
                            total_hits=dr.total_hits,
                            total_flux=dr.total_flux,
                            grid_spectral=dr.grid_spectral.copy() if dr.grid_spectral is not None else None,
                        )
                    partial = SimulationResult(
                        detectors=partial_detectors,
                        ray_paths=[],
                        escaped_flux=escaped_flux,
                        total_emitted_flux=total_emitted_flux,
                        source_count=src_idx + 1,
                    )
                    partial_result_callback(partial)

        # Compute far-field candela distributions for far_field sphere detectors
        for sd in sphere_dets:
            if sd.mode == "far_field":
                compute_farfield_candela(sd, sph_results[sd.name])

        return SimulationResult(
            detectors=det_results,
            sphere_detectors=sph_results,
            ray_paths=all_paths,
            total_emitted_flux=total_emitted_flux,
            escaped_flux=escaped_flux,
            source_count=len(sources),
            solid_body_stats=sb_stats,
        )

    # ------------------------------------------------------------------

    def _run_uq_batched(
        self, sources, progress_callback, convergence_callback=None,
        _adaptive=None, partial_result_callback=None,
    ) -> SimulationResult:
        """Execute the single-thread trace K times with per-batch seeded RNG.

        Phase 4 UQ (Wave 2) — outer K-loop wrapper.  Each chunk runs the full
        single-source bounce loop with an adjusted ``rays_per_source`` (from
        :func:`_partition_rays`) and a deterministic per-batch seed derived
        from ``(random_seed, "__aggregate__", k)``.  Per-batch snapshots of
        the detector grids / hits / flux / spectral grids are accumulated and
        stacked onto the final :class:`DetectorResult`.

        Adaptive sampling convergence is evaluated only at chunk boundaries
        (CONTEXT D-01 / W1): each inner ``_run_single`` call runs to
        completion for its chunk (``_adaptive=False``) and the predicate is
        tested between chunks.  If the predicate reports "converged" at
        ``k'<K``, the outer loop short-circuits and ``n_batches=k'`` is
        reported on the result.
        """
        original_settings = self.project.settings
        K_requested = _effective_uq_batches(original_settings)
        rays_total = int(original_settings.rays_per_source)
        chunk_sizes = _partition_rays(rays_total, K_requested)
        base_seed = int(original_settings.random_seed)
        record_ray_paths_total = int(original_settings.record_ray_paths)
        include_spectral = bool(getattr(original_settings, "uq_include_spectral", True))

        uq_adaptive_enabled = bool(
            _adaptive if _adaptive is not None
            else original_settings.adaptive_sampling
        )

        # Per-batch accumulators keyed by detector name
        per_batch_grids: dict[str, list[np.ndarray]] = {}
        per_batch_hits: dict[str, list[int]] = {}
        per_batch_flux: dict[str, list[float]] = {}
        per_batch_spectral: dict[str, list[np.ndarray]] = {}
        per_batch_sph_grids: dict[str, list[np.ndarray]] = {}
        per_batch_sph_hits: dict[str, list[int]] = {}
        per_batch_sph_flux: dict[str, list[float]] = {}
        rays_per_batch_list: list[int] = []

        cum_result: SimulationResult | None = None
        last_grid_totals: dict[str, np.ndarray] = {}
        last_grid_spectral_totals: dict[str, np.ndarray | None] = {}
        last_hits_totals: dict[str, int] = {}
        last_flux_totals: dict[str, float] = {}
        last_sph_grid_totals: dict[str, np.ndarray] = {}
        last_sph_hits_totals: dict[str, int] = {}
        last_sph_flux_totals: dict[str, float] = {}

        n_batches_effective = 0
        batch_total_fluxes: list[float] = []

        for k in range(K_requested):
            if self._cancelled:
                break
            rays_this_batch = int(chunk_sizes[k])
            if rays_this_batch <= 0:
                continue

            chunk_settings_backup = self.project.settings
            patched = _replace_settings(
                original_settings,
                rays_per_source=rays_this_batch,
                random_seed=_batch_seed(base_seed, "__aggregate__", k) & 0x7FFFFFFF,
                record_ray_paths=record_ray_paths_total if k == 0 else 0,
                adaptive_sampling=False,  # chunk-boundary eval only
            )
            self.project.settings = patched
            self.rng = np.random.default_rng(patched.random_seed)

            # Scale each source's `flux` by (rays_this_batch / rays_total) so
            # that per-ray weight (= eff_flux / rays_per_source) accumulates
            # to the correct per-source total across all K chunks.
            # Weight-per-ray in chunk = (flux * scale) / rays_this_batch;
            #   chunk sum                 = flux * scale;
            #   sum over K chunks         = flux * (sum scale) = flux.
            scale = rays_this_batch / max(rays_total, 1)
            original_fluxes = [src.flux for src in sources]
            for src in sources:
                src.flux = src.flux * scale

            try:
                chunk_result = self._run_single(
                    sources, progress_callback, convergence_callback,
                    _adaptive=False,
                    partial_result_callback=None,
                    _uq_in_chunk=True,
                )
            finally:
                self.project.settings = chunk_settings_backup
                # Restore original source flux values
                for src, orig in zip(sources, original_fluxes):
                    src.flux = orig

            if cum_result is None:
                cum_result = SimulationResult(
                    detectors={
                        name: DetectorResult(
                            detector_name=name,
                            grid=dr.grid.copy(),
                            total_hits=dr.total_hits,
                            total_flux=dr.total_flux,
                            grid_rgb=dr.grid_rgb.copy() if dr.grid_rgb is not None else None,
                            grid_spectral=dr.grid_spectral.copy() if dr.grid_spectral is not None else None,
                        )
                        for name, dr in chunk_result.detectors.items()
                    },
                    sphere_detectors={
                        name: SphereDetectorResult(
                            detector_name=name,
                            grid=sr.grid.copy(),
                            total_hits=sr.total_hits,
                            total_flux=sr.total_flux,
                            candela_grid=(
                                sr.candela_grid.copy()
                                if sr.candela_grid is not None else None
                            ),
                        )
                        for name, sr in chunk_result.sphere_detectors.items()
                    },
                    ray_paths=list(chunk_result.ray_paths),
                    total_emitted_flux=chunk_result.total_emitted_flux,
                    escaped_flux=chunk_result.escaped_flux,
                    source_count=chunk_result.source_count,
                    solid_body_stats={
                        bn: {fid: dict(fstats) for fid, fstats in face_map.items()}
                        for bn, face_map in chunk_result.solid_body_stats.items()
                    },
                )
                for name, dr in chunk_result.detectors.items():
                    per_batch_grids.setdefault(name, []).append(dr.grid.copy())
                    per_batch_hits.setdefault(name, []).append(int(dr.total_hits))
                    per_batch_flux.setdefault(name, []).append(float(dr.total_flux))
                    if include_spectral and dr.grid_spectral is not None:
                        per_batch_spectral.setdefault(name, []).append(dr.grid_spectral.copy())
                    last_grid_totals[name] = dr.grid.copy()
                    last_grid_spectral_totals[name] = (
                        dr.grid_spectral.copy() if dr.grid_spectral is not None else None
                    )
                    last_hits_totals[name] = int(dr.total_hits)
                    last_flux_totals[name] = float(dr.total_flux)
                for name, sr in chunk_result.sphere_detectors.items():
                    per_batch_sph_grids.setdefault(name, []).append(sr.grid.copy())
                    per_batch_sph_hits.setdefault(name, []).append(int(sr.total_hits))
                    per_batch_sph_flux.setdefault(name, []).append(float(sr.total_flux))
                    last_sph_grid_totals[name] = sr.grid.copy()
                    last_sph_hits_totals[name] = int(sr.total_hits)
                    last_sph_flux_totals[name] = float(sr.total_flux)
            else:
                # chunk_result holds only THIS chunk's contribution (not cumulative).
                # Per-batch = chunk_result directly; cum_result is the running sum.
                for name, dr in chunk_result.detectors.items():
                    cur = cum_result.detectors[name]
                    per_batch_grids[name].append(dr.grid.copy())
                    per_batch_hits[name].append(int(dr.total_hits))
                    per_batch_flux[name].append(float(dr.total_flux))
                    if include_spectral and dr.grid_spectral is not None:
                        per_batch_spectral.setdefault(name, []).append(dr.grid_spectral.copy())
                    cur.grid = cur.grid + dr.grid
                    cur.total_hits = int(cur.total_hits) + int(dr.total_hits)
                    cur.total_flux = float(cur.total_flux) + float(dr.total_flux)
                    if dr.grid_spectral is not None:
                        if cur.grid_spectral is not None:
                            cur.grid_spectral = cur.grid_spectral + dr.grid_spectral
                        else:
                            cur.grid_spectral = dr.grid_spectral.copy()
                for name, sr in chunk_result.sphere_detectors.items():
                    cur_s = cum_result.sphere_detectors[name]
                    per_batch_sph_grids[name].append(sr.grid.copy())
                    per_batch_sph_hits[name].append(int(sr.total_hits))
                    per_batch_sph_flux[name].append(float(sr.total_flux))
                    cur_s.grid = cur_s.grid + sr.grid
                    cur_s.total_hits = int(cur_s.total_hits) + int(sr.total_hits)
                    cur_s.total_flux = float(cur_s.total_flux) + float(sr.total_flux)
                    if sr.candela_grid is not None:
                        # candela is computed on grid totals, not summed; take latest chunk's
                        cur_s.candela_grid = sr.candela_grid.copy()
                cum_result.escaped_flux = cum_result.escaped_flux + chunk_result.escaped_flux
                for bn, face_map in chunk_result.solid_body_stats.items():
                    dst = cum_result.solid_body_stats.setdefault(bn, {})
                    for fid, fstats in face_map.items():
                        cur_f = dst.setdefault(
                            fid, {"entering_flux": 0.0, "exiting_flux": 0.0}
                        )
                        cur_f["entering_flux"] += float(fstats.get("entering_flux", 0.0))
                        cur_f["exiting_flux"] += float(fstats.get("exiting_flux", 0.0))
                cum_result.source_count = chunk_result.source_count

            rays_per_batch_list.append(rays_this_batch)
            n_batches_effective += 1

            # Chunk-boundary: notify convergence_callback and evaluate adaptive
            total_flux_now = sum(dr.total_flux for dr in cum_result.detectors.values())
            batch_total_fluxes.append(total_flux_now)

            # Compute cv_pct for both callback and early-exit check
            if len(batch_total_fluxes) >= 2:
                diffs = [
                    batch_total_fluxes[i] - batch_total_fluxes[i - 1]
                    for i in range(1, len(batch_total_fluxes))
                ]
                mean_diff = sum(diffs) / len(diffs) if diffs else 0.0
                var_diff = (
                    sum((d - mean_diff) ** 2 for d in diffs) / len(diffs)
                    if diffs else 0.0
                )
                std_diff = float(var_diff ** 0.5)
                ci = 1.96 * std_diff / max(float(len(diffs) ** 0.5), 1e-12)
                cv_pct = ci / max(abs(mean_diff), 1e-12) * 100.0
            else:
                cv_pct = 100.0

            if convergence_callback is not None and uq_adaptive_enabled:
                # Only emit convergence callbacks when adaptive mode is enabled,
                # to mirror legacy _run_single behavior (no callbacks on
                # non-adaptive runs — see test_adaptive_sampling_disabled_traces_full).
                convergence_callback(0, sum(chunk_sizes[:k + 1]), cv_pct)

            if (
                uq_adaptive_enabled
                and len(batch_total_fluxes) >= 2
                and cv_pct <= original_settings.convergence_cv_target
                and (k + 1) < K_requested
            ):
                break

        if cum_result is None:
            return SimulationResult(total_emitted_flux=0.0, source_count=len(sources))

        for name, dr in cum_result.detectors.items():
            grids = per_batch_grids.get(name, [])
            if grids:
                dr.grid_batches = np.stack(grids, axis=0)
                dr.hits_batches = np.asarray(per_batch_hits[name], dtype=int)
                dr.flux_batches = np.asarray(per_batch_flux[name], dtype=float)
                dr.rays_per_batch = list(rays_per_batch_list)
                dr.n_batches = int(dr.grid_batches.shape[0])
                specs = per_batch_spectral.get(name, [])
                if include_spectral and specs:
                    dr.grid_spectral_batches = np.stack(specs, axis=0)
                else:
                    dr.grid_spectral_batches = None
        for name, sr in cum_result.sphere_detectors.items():
            sph_grids = per_batch_sph_grids.get(name, [])
            if sph_grids:
                # Sphere UQ: attach via attributes (Wave 3 UI picks them up).
                setattr(sr, "grid_batches", np.stack(sph_grids, axis=0))
                setattr(sr, "hits_batches", np.asarray(per_batch_sph_hits[name], dtype=int))
                setattr(sr, "flux_batches", np.asarray(per_batch_sph_flux[name], dtype=float))
                setattr(sr, "rays_per_batch", list(rays_per_batch_list))
                setattr(sr, "n_batches", int(len(sph_grids)))

        if 0 < n_batches_effective < 4:
            cum_result.uq_warnings.append(
                f"UQ CI undefined: only {n_batches_effective} batches completed "
                "before adaptive convergence; need >=4 for Student-t. Skip CI "
                "computation for affected detectors."
            )

        if partial_result_callback is not None:
            try:
                partial_result_callback(cum_result)
            except Exception:
                pass

        return cum_result

    def _resolve_optics(self, surf):
        """Resolve optical behavior for a surface.

        Returns a Material or OpticalProperties-like object with surface_type,
        reflectance, transmittance, is_diffuse, haze fields.
        """
        # Check if surface has explicit optical properties
        if surf.optical_properties_name:
            op = self.project.optical_properties.get(surf.optical_properties_name)
            if op is not None:
                return op
        # Fall back to material
        return self.project.materials.get(surf.material_name)

    def _bounce_surfaces(
        self, surf_hit, active_idx, best_t, best_obj,
        origins, directions, weights, alive,
        surfaces, materials, paths, n_rec,
        wavelengths: np.ndarray | None = None,
        spectral_material_data: dict | None = None,
        bsdf_cdf_cache: dict | None = None,
    ):
        for si, surf in enumerate(surfaces):
            mask = surf_hit & (best_obj == si)
            if not mask.any():
                continue

            hit_idx = active_idx[mask]
            t_vals = best_t[mask]
            hit_pts = origins[hit_idx] + t_vals[:, None] * directions[hit_idx]
            normal = surf.normal

            mat = self._resolve_optics(surf)

            # Record waypoints
            if n_rec > 0:
                for local_i, global_i in enumerate(hit_idx):
                    if global_i < n_rec:
                        paths[global_i].append(hit_pts[local_i].copy())

            if mat is None or mat.surface_type == "absorber":
                alive[hit_idx] = False
                continue

            dot = np.einsum("ij,j->i", directions[hit_idx], normal)
            flip = dot > 0
            # oriented normal pointing away from the incoming ray
            on = np.where(flip[:, None], -normal, normal)

            # --- Spectral R/T lookup (BEFORE BSDF dispatch so both paths can use it) ---
            optics_name = getattr(surf, "optical_properties_name", "") or surf.material_name
            spec_data = (spectral_material_data or {}).get(optics_name)
            if spec_data is not None and wavelengths is not None:
                ray_wl = wavelengths[hit_idx]
                spec_wl = np.asarray(spec_data["wavelength_nm"], dtype=float)
                r_vals = np.interp(ray_wl, spec_wl,
                                   np.asarray(spec_data["reflectance"], dtype=float))
                t_data = spec_data.get("transmittance")
                if t_data is not None:
                    t_vals_spec = np.interp(ray_wl, spec_wl,
                                            np.asarray(t_data, dtype=float))
                else:
                    t_vals_spec = np.full_like(r_vals, mat.transmittance)
            else:
                r_vals = None
                t_vals_spec = None

            # --- BSDF dispatch: overrides scalar R/T/diffuse behavior, respects spectral R ---
            bsdf_name = getattr(mat, "bsdf_profile_name", "")
            if bsdf_name and (bsdf_cdf_cache or {}).get(bsdf_name) is not None:
                bsdf_profile = (self.project.bsdf_profiles or {}).get(bsdf_name, {})
                cdfs = (bsdf_cdf_cache or {}).get(bsdf_name)
                n_hit = len(hit_idx)
                # Determine R/T probability from BSDF profile angular distribution
                # refl_total / trans_total give relative probabilities per theta_in bin
                theta_in_vals = cdfs["theta_in"]
                refl_total = cdfs["refl_total"]   # (M,) — sin-weighted integrals
                trans_total = cdfs["trans_total"]  # (M,)
                cos_i = np.clip(np.einsum("ij,ij->i", -directions[hit_idx], on), 0.0, 1.0)
                theta_i_deg = np.degrees(np.arccos(cos_i))
                bin_idx = np.clip(
                    np.searchsorted(theta_in_vals, theta_i_deg, side="right") - 1,
                    0, len(theta_in_vals) - 1
                )
                r_total_per_ray = refl_total[bin_idx]
                t_total_per_ray = trans_total[bin_idx]
                rt_sum = r_total_per_ray + t_total_per_ray
                # Stochastic decision: reflect or transmit
                roll = self.rng.random(n_hit)
                # Probability of reflection: r_total / (r_total + t_total) if any scatter
                p_refl = np.where(rt_sum > 0, r_total_per_ray / np.maximum(rt_sum, 1e-12), 1.0)
                reflects_bsdf = roll < p_refl
                transmits_bsdf = ~reflects_bsdf
                if reflects_bsdf.any():
                    ri = hit_idx[reflects_bsdf]
                    inc = directions[ri]
                    on_r = on[reflects_bsdf]
                    flip_r = flip[reflects_bsdf]
                    new_dirs = np.empty_like(inc)
                    for side_val, side_n in [(False, normal), (True, -normal)]:
                        sm = flip_r == side_val
                        if not sm.any():
                            continue
                        new_dirs[sm] = sample_bsdf(
                            int(sm.sum()), inc[sm], side_n, bsdf_profile, "reflect",
                            self.rng, cdfs=cdfs,
                        )
                    origins[ri] = hit_pts[reflects_bsdf] + on_r * _EPSILON
                    directions[ri] = new_dirs
                if transmits_bsdf.any():
                    ti = hit_idx[transmits_bsdf]
                    inc = directions[ti]
                    on_t = on[transmits_bsdf]
                    flip_t = flip[transmits_bsdf]
                    new_dirs = np.empty_like(inc)
                    for side_val, side_n in [(False, normal), (True, -normal)]:
                        sm = flip_t == side_val
                        if not sm.any():
                            continue
                        new_dirs[sm] = sample_bsdf(
                            int(sm.sum()), inc[sm], side_n, bsdf_profile, "transmit",
                            self.rng, cdfs=cdfs,
                        )
                    through_n = -on_t
                    origins[ti] = hit_pts[transmits_bsdf] + through_n * _EPSILON
                    directions[ti] = new_dirs
                continue
            # r_vals and t_vals_spec are now available for reflector/diffuser branches below

            if mat.surface_type == "reflector":
                if r_vals is not None:
                    weights[hit_idx] *= r_vals
                else:
                    weights[hit_idx] *= mat.reflectance
                new_dirs = _reflect_batch(directions[hit_idx], on, mat.is_diffuse, self.rng)
                if mat.haze > 0 and not mat.is_diffuse:
                    new_dirs = scatter_haze(new_dirs, mat.haze, self.rng)
                origins[hit_idx] = hit_pts + on * _EPSILON
                directions[hit_idx] = new_dirs

            elif mat.surface_type == "diffuser":
                n_rays = len(hit_idx)
                roll = self.rng.uniform(size=n_rays)
                # Use per-ray transmittance if available, else scalar
                t_thresh = t_vals_spec if t_vals_spec is not None else mat.transmittance
                transmits = roll < t_thresh

                if transmits.any():
                    ti = hit_idx[transmits]
                    through_n = -on[transmits]
                    flip_t = flip[transmits]
                    new_dirs = np.empty((int(transmits.sum()), 3))
                    for side_val, side_n in [(False, -normal), (True, normal)]:
                        sm = flip_t == side_val
                        if not sm.any():
                            continue
                        new_dirs[sm] = sample_lambertian(int(sm.sum()), side_n, self.rng)
                    origins[ti] = hit_pts[transmits] + through_n * _EPSILON
                    directions[ti] = new_dirs

                reflects = ~transmits
                if reflects.any():
                    ri = hit_idx[reflects]
                    if r_vals is not None:
                        weights[ri] *= r_vals[reflects]
                    else:
                        weights[ri] *= mat.reflectance
                    refl_on = on[reflects]
                    new_dirs = _reflect_batch(directions[ri], refl_on, mat.is_diffuse, self.rng)
                    origins[ri] = hit_pts[reflects] + refl_on * _EPSILON
                    directions[ri] = new_dirs


def _trace_single_source(project, source_name, base_seed):
    """Top-level function for multiprocessing: trace one source.

    Returns a dict with detector grid data, escaped flux, and solid_body_stats.
    """
    import hashlib
    # Derive a unique seed per source
    seed_hash = int(hashlib.md5(f"{base_seed}_{source_name}".encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed_hash)

    source = next(s for s in project.sources if s.name == source_name and s.enabled)
    settings = project.settings
    surfaces = project.surfaces
    detectors = project.detectors
    sphere_dets = project.sphere_detectors
    materials = project.materials
    distributions = project.angular_distributions

    det_grids = {}
    for det in detectors:
        det_grids[det.name] = {
            "grid": np.zeros((det.resolution[1], det.resolution[0]), dtype=float),
            "hits": 0,
            "flux": 0.0,
        }

    # Initialize sphere detector grids for this source
    sph_grids: dict[str, dict] = {}
    for sd in sphere_dets:
        n_phi, n_theta = sd.resolution
        sph_grids[sd.name] = {
            "grid": np.zeros((n_theta, n_phi), dtype=float),
            "hits": 0,
            "flux": 0.0,
        }

    # Expand SolidBox objects into face Rectangles
    solid_faces = []
    solid_face_map = {}  # face_rect_name -> (box, face_id, box_n, geom_eps)
    for box in project.solid_bodies:
        mat = materials.get(box.material_name)
        box_n = mat.refractive_index if mat is not None else 1.0
        geom_eps = max(_EPSILON, min(box.dimensions) * 1e-4)
        for face in box.get_faces():
            solid_faces.append(face)
            face_id = face.name.split("::", 1)[1]
            solid_face_map[face.name] = (box, face_id, box_n, geom_eps)

    # Initialize solid_body_stats accumulator
    sb_stats = {}
    for box in project.solid_bodies:
        sb_stats[box.name] = {
            fid: {"entering_flux": 0.0, "exiting_flux": 0.0}
            for fid in FACE_NAMES
        }

    # Expand SolidCylinder objects into face-like objects and build lookup
    cyl_faces = []
    cyl_face_map = {}
    for cyl in getattr(project, "solid_cylinders", []):
        mat = materials.get(cyl.material_name)
        cyl_n = mat.refractive_index if mat is not None else 1.0
        geom_eps = max(_EPSILON, min(cyl.radius, cyl.length / 2.0) * 1e-4)
        for face in cyl.get_faces():
            cyl_faces.append(face)
            face_id = face.name.split("::", 1)[1]
            cyl_face_map[face.name] = (cyl, face_id, cyl_n, geom_eps)
        sb_stats[cyl.name] = {
            fid: {"entering_flux": 0.0, "exiting_flux": 0.0}
            for fid in ("top_cap", "bottom_cap", "side")
        }

    # Expand SolidPrism objects into face-like objects and build lookup
    prism_faces = []
    prism_face_map = {}
    for prism in getattr(project, "solid_prisms", []):
        mat = materials.get(prism.material_name)
        prism_n = mat.refractive_index if mat is not None else 1.0
        geom_eps = max(_EPSILON, min(prism.circumscribed_radius, prism.length / 2.0) * 1e-4)
        for face in prism.get_faces():
            prism_faces.append(face)
            face_id = face.name.split("::", 1)[1]
            prism_face_map[face.name] = (prism, face_id, prism_n, geom_eps)
        all_face_ids = ["cap_top", "cap_bottom"] + [f"side_{i}" for i in range(prism.n_sides)]
        sb_stats[prism.name] = {
            fid: {"entering_flux": 0.0, "exiting_flux": 0.0}
            for fid in all_face_ids
        }

    n = settings.rays_per_source
    eff_flux = source.effective_flux
    if source.flux_tolerance > 0:
        tol = source.flux_tolerance / 100.0
        eff_flux *= (1.0 + rng.uniform(-tol, tol))

    # Emit rays
    if source.distribution == "lambertian":
        directions = sample_lambertian(n, source.direction, rng)
    elif source.distribution == "isotropic":
        directions = sample_isotropic(n, rng)
    else:
        profile = distributions.get(source.distribution)
        if profile and "theta_deg" in profile and "intensity" in profile:
            directions = sample_angular_distribution(
                n, source.direction,
                np.asarray(profile["theta_deg"], dtype=float),
                np.asarray(profile["intensity"], dtype=float),
                rng,
            )
        else:
            directions = sample_isotropic(n, rng)

    origins = np.tile(source.position, (n, 1)).copy()
    weights = np.full(n, eff_flux / n)
    alive = np.ones(n, dtype=bool)
    current_n = np.ones(n, dtype=float)
    n_stack = np.ones((n, _N_STACK_MAX), dtype=float)
    n_depth = np.zeros(n, dtype=int)
    escaped_flux = 0.0

    # Sample wavelengths per ray if this source has a non-white SPD (spectral mode)
    has_spectral_mp = source.spd != "white"
    n_spec_bins_mp = N_SPECTRAL_BINS if has_spectral_mp else 0
    if has_spectral_mp:
        wavelengths_mp = sample_wavelengths(
            n, source.spd, rng,
            spd_profiles=getattr(project, "spd_profiles", None) or None,
        )
    else:
        wavelengths_mp = None

    # Add spectral_grid slot to each detector grid dict (None when not spectral)
    for det in detectors:
        det_grids[det.name]["spectral_grid"] = (
            np.zeros((det.resolution[1], det.resolution[0], n_spec_bins_mp), dtype=float)
            if has_spectral_mp else None
        )

    # Pre-compute BSDF CDFs for all profiles in the project
    bsdf_cdf_cache_mp: dict[str, dict] = {}
    for bsdf_nm, bsdf_prof in (getattr(project, "bsdf_profiles", {}) or {}).items():
        bsdf_cdf_cache_mp[bsdf_nm] = precompute_bsdf_cdfs(bsdf_prof)

    # BVH setup for MP path
    # BVH activation threshold: total geometry (planes + cyl + prism faces) >= _BVH_THRESHOLD
    n_all_planes_mp = len(surfaces) + len(solid_faces)
    n_total_geom_mp = n_all_planes_mp + len(cyl_faces) + len(prism_faces)
    use_bvh_mp = n_total_geom_mp >= _BVH_THRESHOLD
    bvh_bounds_mp = bvh_meta_mp = bvh_n_nodes_mp = None
    bvh_normals_mp = bvh_centers_mp = bvh_u_mp = bvh_v_mp = bvh_hw_mp = bvh_hh_mp = None
    n_surf_planes_mp = len(surfaces)
    cyl_aabbs_mp: np.ndarray | None = None
    prism_aabbs_mp: np.ndarray | None = None

    if use_bvh_mp and n_all_planes_mp > 0:
        all_plane_normals_mp = np.empty((n_all_planes_mp, 3), dtype=np.float64)
        all_plane_centers_mp = np.empty((n_all_planes_mp, 3), dtype=np.float64)
        all_plane_u_mp       = np.empty((n_all_planes_mp, 3), dtype=np.float64)
        all_plane_v_mp       = np.empty((n_all_planes_mp, 3), dtype=np.float64)
        all_plane_hw_mp      = np.empty(n_all_planes_mp, dtype=np.float64)
        all_plane_hh_mp      = np.empty(n_all_planes_mp, dtype=np.float64)
        for i, surf in enumerate(surfaces):
            all_plane_normals_mp[i] = surf.normal
            all_plane_centers_mp[i] = surf.center
            all_plane_u_mp[i]       = surf.u_axis
            all_plane_v_mp[i]       = surf.v_axis
            all_plane_hw_mp[i]      = surf.size[0] / 2.0
            all_plane_hh_mp[i]      = surf.size[1] / 2.0
        for i, sface in enumerate(solid_faces):
            j = n_surf_planes_mp + i
            all_plane_normals_mp[j] = sface.normal
            all_plane_centers_mp[j] = sface.center
            all_plane_u_mp[j]       = sface.u_axis
            all_plane_v_mp[j]       = sface.v_axis
            all_plane_hw_mp[j]      = sface.size[0] / 2.0
            all_plane_hh_mp[j]      = sface.size[1] / 2.0
        aabbs_mp = compute_surface_aabbs(
            all_plane_normals_mp, all_plane_centers_mp,
            all_plane_u_mp, all_plane_v_mp, all_plane_hw_mp, all_plane_hh_mp,
        )
        bvh_bounds_mp, bvh_meta_mp, bvh_n_nodes_mp = build_bvh_flat(aabbs_mp)
        bvh_normals_mp = all_plane_normals_mp
        bvh_centers_mp = all_plane_centers_mp
        bvh_u_mp       = all_plane_u_mp
        bvh_v_mp       = all_plane_v_mp
        bvh_hw_mp      = all_plane_hw_mp
        bvh_hh_mp      = all_plane_hh_mp

    # Pre-compute conservative AABBs for cylinder/prism faces (MP path broad-phase)
    if use_bvh_mp and cyl_faces:
        cyl_aabb_list_mp = []
        for cface in cyl_faces:
            c = np.asarray(cface.center, dtype=np.float64)
            if isinstance(cface, CylinderCap):
                r = float(cface.radius)
                cyl_aabb_list_mp.append([c[0]-r, c[0]+r, c[1]-r, c[1]+r, c[2]-r, c[2]+r])
            else:
                r = float(cface.radius)
                hl = float(cface.length) / 2.0
                extent = r + hl
                cyl_aabb_list_mp.append([c[0]-extent, c[0]+extent,
                                         c[1]-extent, c[1]+extent,
                                         c[2]-extent, c[2]+extent])
        cyl_aabbs_mp = np.array(cyl_aabb_list_mp, dtype=np.float64)

    if use_bvh_mp and prism_faces:
        prism_aabb_list_mp = []
        for pface in prism_faces:
            c = np.asarray(pface.center, dtype=np.float64)
            if hasattr(pface, 'vertices') and pface.vertices is not None:
                verts = np.asarray(pface.vertices, dtype=np.float64)
                lo = verts.min(axis=0); hi = verts.max(axis=0)
                prism_aabb_list_mp.append([lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]])
            elif hasattr(pface, 'circumscribed_radius'):
                r = float(pface.circumscribed_radius)
                prism_aabb_list_mp.append([c[0]-r, c[0]+r, c[1]-r, c[1]+r, c[2]-r, c[2]+r])
            else:
                hw_pf = pface.size[0] / 2.0
                hh_pf = pface.size[1] / 2.0
                corners = np.array([
                    c + hw_pf * pface.u_axis + hh_pf * pface.v_axis,
                    c + hw_pf * pface.u_axis - hh_pf * pface.v_axis,
                    c - hw_pf * pface.u_axis + hh_pf * pface.v_axis,
                    c - hw_pf * pface.u_axis - hh_pf * pface.v_axis,
                ])
                lo = corners.min(axis=0); hi = corners.max(axis=0)
                prism_aabb_list_mp.append([lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]])
        prism_aabbs_mp = np.array(prism_aabb_list_mp, dtype=np.float64)

    for _bounce in range(settings.max_bounces):
        if not alive.any():
            break

        active_idx = np.where(alive)[0]
        active_origins = origins[active_idx]
        active_dirs = directions[active_idx]
        n_active = len(active_idx)

        best_t = np.full(n_active, np.inf)
        best_type = np.full(n_active, -1, dtype=int)
        best_obj = np.full(n_active, -1, dtype=int)

        if use_bvh_mp:
            bvh_t_mp, bvh_idx_mp = traverse_bvh_batch(
                np.ascontiguousarray(active_origins, dtype=np.float64),
                np.ascontiguousarray(active_dirs,   dtype=np.float64),
                bvh_bounds_mp, bvh_meta_mp, bvh_n_nodes_mp,
                bvh_normals_mp, bvh_centers_mp, bvh_u_mp, bvh_v_mp, bvh_hw_mp, bvh_hh_mp,
                _EPSILON,
            )
            hit_mask_mp = bvh_idx_mp >= 0
            for ri in np.where(hit_mask_mp)[0]:
                idx = int(bvh_idx_mp[ri])
                t_val = float(bvh_t_mp[ri])
                if t_val < best_t[ri]:
                    best_t[ri] = t_val
                    if idx < n_surf_planes_mp:
                        best_type[ri] = 0
                        best_obj[ri] = idx
                    else:
                        best_type[ri] = 3
                        best_obj[ri] = idx - n_surf_planes_mp
        else:
            for si, surf in enumerate(surfaces):
                t = _intersect_plane_accel(active_origins, active_dirs, surf.normal, surf.center,
                                           surf.u_axis, surf.v_axis, surf.size)
                closer = t < best_t
                best_t[closer] = t[closer]
                best_type[closer] = 0
                best_obj[closer] = si

            # SolidBox face intersections (type 3)
            for sfi, sface in enumerate(solid_faces):
                t = _intersect_plane_accel(active_origins, active_dirs,
                                           sface.normal, sface.center,
                                           sface.u_axis, sface.v_axis, sface.size)
                closer = t < best_t
                best_t[closer] = t[closer]
                best_type[closer] = 3
                best_obj[closer] = sfi

        # SolidCylinder face intersections (type 4) — AABB pre-filter when BVH active
        cyl_candidates_mp = (
            _aabb_ray_candidates(active_origins, active_dirs, cyl_aabbs_mp)
            if use_bvh_mp and cyl_aabbs_mp is not None
            else range(len(cyl_faces))
        )
        for cfi in cyl_candidates_mp:
            cface = cyl_faces[cfi]
            if isinstance(cface, CylinderCap):
                t = _intersect_rays_disc(
                    active_origins, active_dirs,
                    cface.center, cface.normal, cface.radius,
                )
            else:  # CylinderSide
                t = _intersect_rays_cylinder_side(
                    active_origins, active_dirs,
                    cface.center, cface.axis, cface.radius, cface.length / 2.0,
                )
            closer = t < best_t
            best_t[closer] = t[closer]
            best_type[closer] = 4
            best_obj[closer] = cfi

        # SolidPrism face intersections (type 5) — AABB pre-filter when BVH active
        prism_candidates_mp = (
            _aabb_ray_candidates(active_origins, active_dirs, prism_aabbs_mp)
            if use_bvh_mp and prism_aabbs_mp is not None
            else range(len(prism_faces))
        )
        for pfi in prism_candidates_mp:
            pface = prism_faces[pfi]
            if isinstance(pface, PrismCap):
                t = _intersect_prism_cap(active_origins, active_dirs, pface)
            else:  # Rectangle side face
                t = _intersect_plane_accel(
                    active_origins, active_dirs,
                    pface.normal, pface.center,
                    pface.u_axis, pface.v_axis, pface.size,
                )
            closer = t < best_t
            best_t[closer] = t[closer]
            best_type[closer] = 5
            best_obj[closer] = pfi

        # Detectors always tested separately
        for di, det in enumerate(detectors):
            t = _intersect_plane_accel(active_origins, active_dirs, det.normal, det.center,
                                       det.u_axis, det.v_axis, det.size)
            closer = t < best_t
            best_t[closer] = t[closer]
            best_type[closer] = 1
            best_obj[closer] = di

        # Sphere detectors tested separately (type 2)
        for sdi, sd in enumerate(sphere_dets):
            t = _intersect_sphere_accel(active_origins, active_dirs, sd.center, sd.radius)
            closer = t < best_t
            best_t[closer] = t[closer]
            best_type[closer] = 2
            best_obj[closer] = sdi

        missed = best_t == np.inf
        if missed.any():
            escaped_flux += float(weights[active_idx[missed]].sum())
        alive[active_idx[missed]] = False

        for di, det in enumerate(detectors):
            mask = (best_type == 1) & (best_obj == di)
            if not mask.any():
                continue
            hit_idx = active_idx[mask]
            hit_pts = origins[hit_idx] + best_t[mask, None] * directions[hit_idx]
            # Inline accumulation
            local = hit_pts - det.center
            u = local @ det.u_axis
            v = local @ det.v_axis
            hw, hh = det.size[0] / 2.0, det.size[1] / 2.0
            nx, ny = det.resolution
            ix = np.clip(((u + hw) / det.size[0] * nx).astype(int), 0, nx - 1)
            iy = np.clip(((v + hh) / det.size[1] * ny).astype(int), 0, ny - 1)
            hw_arr = weights[hit_idx]
            accumulate_grid_jit(det_grids[det.name]["grid"], iy, ix, hw_arr)
            det_grids[det.name]["hits"] += len(hw_arr)
            det_grids[det.name]["flux"] += float(hw_arr.sum())
            # Spectral grid accumulation for MP path
            sg = det_grids[det.name].get("spectral_grid")
            if sg is not None and wavelengths_mp is not None:
                bin_idx = np.clip(
                    ((wavelengths_mp[hit_idx] - LAMBDA_MIN) / (LAMBDA_MAX - LAMBDA_MIN)
                     * n_spec_bins_mp).astype(int),
                    0, n_spec_bins_mp - 1,
                )
                np.add.at(sg, (iy, ix, bin_idx), hw_arr)
            # Pass-through: advance ray past the detector plane
            origins[hit_idx] = hit_pts + directions[hit_idx] * _EPSILON

        # Sphere detector hits — pass-through (accumulate flux then continue)
        for sdi, sd in enumerate(sphere_dets):
            mask = (best_type == 2) & (best_obj == sdi)
            if not mask.any():
                continue
            hit_idx = active_idx[mask]
            hit_pts = origins[hit_idx] + best_t[mask, None] * directions[hit_idx]
            if sd.mode == "far_field":
                # Inline far-field accumulation using outgoing direction
                d_out = -directions[hit_idx]
                r_norm = np.linalg.norm(d_out, axis=1, keepdims=True)
                r_norm = np.maximum(r_norm, 1e-12)
                d_norm = d_out / r_norm
                theta = np.arccos(np.clip(d_norm[:, 2], -1.0, 1.0))
                phi = np.arctan2(d_norm[:, 1], d_norm[:, 0])
                phi = np.where(phi < 0, phi + 2.0 * np.pi, phi)
                n_phi_sd, n_theta_sd = sd.resolution
                i_theta = np.clip((theta / np.pi * n_theta_sd).astype(int), 0, n_theta_sd - 1)
                i_phi = np.clip((phi / (2.0 * np.pi) * n_phi_sd).astype(int), 0, n_phi_sd - 1)
                accumulate_sphere_jit(sph_grids[sd.name]["grid"], i_theta, i_phi, weights[hit_idx])
            else:
                # Near-field: accumulate by position
                d_pos = hit_pts - sd.center
                r_pos = np.linalg.norm(d_pos, axis=1, keepdims=True)
                r_pos = np.maximum(r_pos, 1e-12)
                d_norm_pos = d_pos / r_pos
                theta_pos = np.arccos(np.clip(d_norm_pos[:, 2], -1.0, 1.0))
                phi_pos = np.arctan2(d_norm_pos[:, 1], d_norm_pos[:, 0])
                phi_pos = np.where(phi_pos < 0, phi_pos + 2.0 * np.pi, phi_pos)
                n_phi_sd, n_theta_sd = sd.resolution
                i_theta = np.clip((theta_pos / np.pi * n_theta_sd).astype(int), 0, n_theta_sd - 1)
                i_phi = np.clip((phi_pos / (2.0 * np.pi) * n_phi_sd).astype(int), 0, n_phi_sd - 1)
                accumulate_sphere_jit(sph_grids[sd.name]["grid"], i_theta, i_phi, weights[hit_idx])
            sph_grids[sd.name]["hits"] += len(hit_idx)
            sph_grids[sd.name]["flux"] += float(weights[hit_idx].sum())
            # Pass-through: advance ray past the sphere
            origins[hit_idx] = hit_pts + directions[hit_idx] * _EPSILON

        # SolidBox face hits — Fresnel/TIR physics
        for sfi, sface in enumerate(solid_faces):
            mask = (best_type == 3) & (best_obj == sfi)
            if not mask.any():
                continue
            hit_idx = active_idx[mask]
            t_vals = best_t[mask]
            hit_pts = origins[hit_idx] + t_vals[:, None] * directions[hit_idx]
            face_normal = sface.normal

            box, face_id, box_n, geom_eps = solid_face_map[sface.name]

            # --- face_optics override in MP path ---
            face_op_name_mp = getattr(sface, "optical_properties_name", "")
            if face_op_name_mp:
                face_op_mp = project.optical_properties.get(face_op_name_mp)
                if face_op_mp is not None and face_op_mp.surface_type in ("reflector", "absorber", "diffuser"):
                    _dot_dn_mp = np.einsum("ij,j->i", directions[hit_idx], face_normal)
                    _flip_mp = _dot_dn_mp > 0
                    _on_mp = np.where(_flip_mp[:, None], -face_normal, face_normal)
                    _entering_mp = _dot_dn_mp < 0
                    for local_i, global_i in enumerate(hit_idx):
                        w = float(weights[global_i])
                        if _entering_mp[local_i]:
                            sb_stats[box.name][face_id]["entering_flux"] += w
                        else:
                            sb_stats[box.name][face_id]["exiting_flux"] += w
                    if face_op_mp.surface_type == "absorber":
                        alive[hit_idx] = False
                        continue
                    elif face_op_mp.surface_type == "reflector":
                        weights[hit_idx] *= face_op_mp.reflectance
                        new_dirs_mp = _reflect_batch(directions[hit_idx], _on_mp,
                                                     face_op_mp.is_diffuse, rng)
                        if face_op_mp.haze > 0 and not face_op_mp.is_diffuse:
                            new_dirs_mp = scatter_haze(new_dirs_mp, face_op_mp.haze, rng)
                        origins[hit_idx] = hit_pts + _on_mp * geom_eps
                        directions[hit_idx] = new_dirs_mp
                        continue
                    elif face_op_mp.surface_type == "diffuser":
                        n_rays_fo_mp = len(hit_idx)
                        roll_fo_mp = rng.uniform(size=n_rays_fo_mp)
                        transmits_fo_mp = roll_fo_mp < face_op_mp.transmittance
                        if transmits_fo_mp.any():
                            ti_fo_mp = hit_idx[transmits_fo_mp]
                            through_n_fo_mp = -_on_mp[transmits_fo_mp]
                            origins[ti_fo_mp] = hit_pts[transmits_fo_mp] + through_n_fo_mp * geom_eps
                            # Per-ray Lambertian to handle mixed-side hits correctly
                            _n_tr_mp = int(transmits_fo_mp.sum())
                            _new_d_mp = np.empty((_n_tr_mp, 3))
                            for _j in range(_n_tr_mp):
                                _new_d_mp[_j] = sample_lambertian(1, through_n_fo_mp[_j], rng)[0]
                            directions[ti_fo_mp] = _new_d_mp
                        reflects_fo_mp = ~transmits_fo_mp
                        if reflects_fo_mp.any():
                            ri_fo_mp = hit_idx[reflects_fo_mp]
                            weights[ri_fo_mp] *= face_op_mp.reflectance
                            refl_on_fo_mp = _on_mp[reflects_fo_mp]
                            new_d_fo_mp = _reflect_batch(directions[ri_fo_mp], refl_on_fo_mp,
                                                          face_op_mp.is_diffuse, rng)
                            origins[ri_fo_mp] = hit_pts[reflects_fo_mp] + refl_on_fo_mp * geom_eps
                            directions[ri_fo_mp] = new_d_fo_mp
                        continue
            # --- end face_optics override in MP path ---

            dot_dn = np.einsum("ij,j->i", directions[hit_idx], face_normal)
            entering = dot_dn < 0

            # on_into: normal pointing INTO the new medium.
            # Entering: on_into = -face_normal (box interior side)
            # Exiting: on_into = +face_normal (air side)
            on_into = np.where(entering[:, None], -face_normal, face_normal)
            on_back = -on_into   # points toward incoming ray (old medium)

            n1_arr = current_n[hit_idx].copy()
            exit_n = n_stack[hit_idx, np.maximum(n_depth[hit_idx] - 1, 0)]
            n2_arr = np.where(entering, box_n, exit_n)

            cos_i_arr = np.clip(np.einsum("ij,ij->i", directions[hit_idx], on_into), 0.0, 1.0)
            R_arr = _fresnel_unpolarized(cos_i_arr, n1_arr, n2_arr)

            roll = rng.random(len(hit_idx))
            reflects = roll < R_arr
            refracts = ~reflects

            # Flux accounting
            for local_i, global_i in enumerate(hit_idx):
                fid = face_id
                w = float(weights[global_i])
                if entering[local_i]:
                    sb_stats[box.name][fid]["entering_flux"] += w
                else:
                    sb_stats[box.name][fid]["exiting_flux"] += w

            # Refracted rays
            if refracts.any():
                ri = hit_idx[refracts]
                on_r = on_into[refracts]
                n1_r = n1_arr[refracts]
                n2_r = n2_arr[refracts]
                new_dirs = _refract_snell(directions[ri], on_r, n1_r, n2_r)
                current_n[ri] = n2_r
                _n_stack_update(n_depth, n_stack, ri, entering[refracts], n1_r)
                origins[ri] = hit_pts[refracts] + on_r * geom_eps
                directions[ri] = new_dirs

            # Reflected rays
            if reflects.any():
                rfl_i = hit_idx[reflects]
                on_b = on_back[reflects]
                d_rfl = directions[rfl_i]
                dot_vals = np.einsum("ij,ij->i", d_rfl, on_b)[:, None]
                new_dirs = d_rfl - 2.0 * dot_vals * on_b
                norms = np.linalg.norm(new_dirs, axis=1, keepdims=True)
                new_dirs = new_dirs / np.maximum(norms, 1e-12)
                origins[rfl_i] = hit_pts[reflects] + on_b * geom_eps
                directions[rfl_i] = new_dirs

        # SolidCylinder face hits (type 4) -- Fresnel/TIR physics
        for cfi, cface in enumerate(cyl_faces):
            mask = (best_type == 4) & (best_obj == cfi)
            if not mask.any():
                continue
            hit_idx = active_idx[mask]
            t_vals = best_t[mask]
            hit_pts = origins[hit_idx] + t_vals[:, None] * directions[hit_idx]
            cyl, face_id, cyl_n, geom_eps = cyl_face_map[cface.name]
            if isinstance(cface, CylinderSide):
                cyl_axis = cface.axis
                diff = hit_pts - cyl.center
                proj = np.einsum("ij,j->i", diff, cyl_axis)
                radial = diff - proj[:, None] * cyl_axis
                r_norms = np.linalg.norm(radial, axis=1, keepdims=True)
                face_normals = radial / np.maximum(r_norms, 1e-12)
                dot_dn = np.einsum("ij,ij->i", directions[hit_idx], face_normals)
                entering = dot_dn < 0
                on_into = np.where(entering[:, None], -face_normals, face_normals)
            else:
                face_normal = cface.normal
                dot_dn = np.einsum("ij,j->i", directions[hit_idx], face_normal)
                entering = dot_dn < 0
                on_into = np.where(entering[:, None], -face_normal, face_normal)
            on_back = -on_into
            # --- face_optics override: per-face optical property ---
            _fo_name = getattr(cface, "optical_properties_name", "")
            if _fo_name:
                _fo = project.optical_properties.get(_fo_name)
                if _fo is not None and _fo.surface_type in ("reflector", "absorber", "diffuser"):
                    for local_i, global_i in enumerate(hit_idx):
                        w = float(weights[global_i])
                        if entering[local_i]:
                            sb_stats[cyl.name][face_id]["entering_flux"] += w
                        else:
                            sb_stats[cyl.name][face_id]["exiting_flux"] += w
                    if _fo.surface_type == "absorber":
                        alive[hit_idx] = False
                        continue
                    elif _fo.surface_type == "reflector":
                        weights[hit_idx] *= _fo.reflectance
                        new_dirs = _reflect_batch(directions[hit_idx], on_back,
                                                  _fo.is_diffuse, rng)
                        if _fo.haze > 0 and not _fo.is_diffuse:
                            new_dirs = scatter_haze(new_dirs, _fo.haze, rng)
                        origins[hit_idx] = hit_pts + on_back * geom_eps
                        directions[hit_idx] = new_dirs
                        continue
                    elif _fo.surface_type == "diffuser":
                        _n_fo = len(hit_idx)
                        _roll_fo = rng.uniform(size=_n_fo)
                        _transmits = _roll_fo < _fo.transmittance
                        if _transmits.any():
                            _ti = hit_idx[_transmits]
                            _through_n = on_into[_transmits]
                            origins[_ti] = hit_pts[_transmits] + _through_n * geom_eps
                            _n_tr = int(_transmits.sum())
                            _new_d = np.empty((_n_tr, 3))
                            for _j in range(_n_tr):
                                _new_d[_j] = sample_lambertian(1, _through_n[_j], rng)[0]
                            directions[_ti] = _new_d
                        _reflects = ~_transmits
                        if _reflects.any():
                            _ri = hit_idx[_reflects]
                            weights[_ri] *= _fo.reflectance
                            _refl_on = on_back[_reflects]
                            _new_d_r = _reflect_batch(directions[_ri], _refl_on,
                                                       _fo.is_diffuse, rng)
                            origins[_ri] = hit_pts[_reflects] + _refl_on * geom_eps
                            directions[_ri] = _new_d_r
                        continue
            n1_arr = current_n[hit_idx].copy()
            exit_n = n_stack[hit_idx, np.maximum(n_depth[hit_idx] - 1, 0)]
            n2_arr = np.where(entering, cyl_n, exit_n)
            cos_i_arr = np.clip(np.einsum("ij,ij->i", directions[hit_idx], on_into), 0.0, 1.0)
            R_arr = _fresnel_unpolarized(cos_i_arr, n1_arr, n2_arr)
            roll = rng.random(len(hit_idx))
            reflects = roll < R_arr
            refracts = ~reflects
            for local_i, global_i in enumerate(hit_idx):
                w = float(weights[global_i])
                if entering[local_i]:
                    sb_stats[cyl.name][face_id]["entering_flux"] += w
                else:
                    sb_stats[cyl.name][face_id]["exiting_flux"] += w
            if refracts.any():
                ri = hit_idx[refracts]
                on_r = on_into[refracts]
                n1_r = n1_arr[refracts]
                n2_r = n2_arr[refracts]
                new_dirs = _refract_snell(directions[ri], on_r, n1_r, n2_r)
                current_n[ri] = n2_r
                _n_stack_update(n_depth, n_stack, ri, entering[refracts], n1_r)
                origins[ri] = hit_pts[refracts] + on_r * geom_eps
                directions[ri] = new_dirs
            if reflects.any():
                rfl_i = hit_idx[reflects]
                on_b = on_back[reflects]
                d_rfl = directions[rfl_i]
                dot_vals = np.einsum("ij,ij->i", d_rfl, on_b)[:, None]
                new_dirs = d_rfl - 2.0 * dot_vals * on_b
                norms_r = np.linalg.norm(new_dirs, axis=1, keepdims=True)
                new_dirs = new_dirs / np.maximum(norms_r, 1e-12)
                origins[rfl_i] = hit_pts[reflects] + on_b * geom_eps
                directions[rfl_i] = new_dirs

        # SolidPrism face hits (type 5) -- Fresnel/TIR physics
        for pfi, pface in enumerate(prism_faces):
            mask = (best_type == 5) & (best_obj == pfi)
            if not mask.any():
                continue
            hit_idx = active_idx[mask]
            t_vals = best_t[mask]
            hit_pts = origins[hit_idx] + t_vals[:, None] * directions[hit_idx]
            prism, face_id, prism_n, geom_eps = prism_face_map[pface.name]
            face_normal = pface.normal
            dot_dn = np.einsum("ij,j->i", directions[hit_idx], face_normal)
            entering = dot_dn < 0
            on_into = np.where(entering[:, None], -face_normal, face_normal)
            on_back = -on_into
            # --- face_optics override: per-face optical property ---
            _fo_name = getattr(pface, "optical_properties_name", "")
            if _fo_name:
                _fo = project.optical_properties.get(_fo_name)
                if _fo is not None and _fo.surface_type in ("reflector", "absorber", "diffuser"):
                    for local_i, global_i in enumerate(hit_idx):
                        w = float(weights[global_i])
                        if entering[local_i]:
                            sb_stats[prism.name][face_id]["entering_flux"] += w
                        else:
                            sb_stats[prism.name][face_id]["exiting_flux"] += w
                    if _fo.surface_type == "absorber":
                        alive[hit_idx] = False
                        continue
                    elif _fo.surface_type == "reflector":
                        weights[hit_idx] *= _fo.reflectance
                        new_dirs = _reflect_batch(directions[hit_idx], on_back,
                                                  _fo.is_diffuse, rng)
                        if _fo.haze > 0 and not _fo.is_diffuse:
                            new_dirs = scatter_haze(new_dirs, _fo.haze, rng)
                        origins[hit_idx] = hit_pts + on_back * geom_eps
                        directions[hit_idx] = new_dirs
                        continue
                    elif _fo.surface_type == "diffuser":
                        _n_fo = len(hit_idx)
                        _roll_fo = rng.uniform(size=_n_fo)
                        _transmits = _roll_fo < _fo.transmittance
                        if _transmits.any():
                            _ti = hit_idx[_transmits]
                            _through_n = on_into[_transmits]
                            origins[_ti] = hit_pts[_transmits] + _through_n * geom_eps
                            _n_tr = int(_transmits.sum())
                            _new_d = np.empty((_n_tr, 3))
                            for _j in range(_n_tr):
                                _new_d[_j] = sample_lambertian(1, _through_n[_j], rng)[0]
                            directions[_ti] = _new_d
                        _reflects = ~_transmits
                        if _reflects.any():
                            _ri = hit_idx[_reflects]
                            weights[_ri] *= _fo.reflectance
                            _refl_on = on_back[_reflects]
                            _new_d_r = _reflect_batch(directions[_ri], _refl_on,
                                                       _fo.is_diffuse, rng)
                            origins[_ri] = hit_pts[_reflects] + _refl_on * geom_eps
                            directions[_ri] = _new_d_r
                        continue
            n1_arr = current_n[hit_idx].copy()
            exit_n = n_stack[hit_idx, np.maximum(n_depth[hit_idx] - 1, 0)]
            n2_arr = np.where(entering, prism_n, exit_n)
            cos_i_arr = np.clip(np.einsum("ij,ij->i", directions[hit_idx], on_into), 0.0, 1.0)
            R_arr = _fresnel_unpolarized(cos_i_arr, n1_arr, n2_arr)
            roll = rng.random(len(hit_idx))
            reflects = roll < R_arr
            refracts = ~reflects
            for local_i, global_i in enumerate(hit_idx):
                w = float(weights[global_i])
                if entering[local_i]:
                    sb_stats[prism.name][face_id]["entering_flux"] += w
                else:
                    sb_stats[prism.name][face_id]["exiting_flux"] += w
            if refracts.any():
                ri = hit_idx[refracts]
                on_r = on_into[refracts]
                n1_r = n1_arr[refracts]
                n2_r = n2_arr[refracts]
                new_dirs = _refract_snell(directions[ri], on_r, n1_r, n2_r)
                current_n[ri] = n2_r
                _n_stack_update(n_depth, n_stack, ri, entering[refracts], n1_r)
                origins[ri] = hit_pts[refracts] + on_r * geom_eps
                directions[ri] = new_dirs
            if reflects.any():
                rfl_i = hit_idx[reflects]
                on_b = on_back[reflects]
                d_rfl = directions[rfl_i]
                dot_vals = np.einsum("ij,ij->i", d_rfl, on_b)[:, None]
                new_dirs = d_rfl - 2.0 * dot_vals * on_b
                norms_r = np.linalg.norm(new_dirs, axis=1, keepdims=True)
                new_dirs = new_dirs / np.maximum(norms_r, 1e-12)
                origins[rfl_i] = hit_pts[reflects] + on_b * geom_eps
                directions[rfl_i] = new_dirs

        # Surface hits (simplified — no path recording in MP mode)
        surf_hit_mask = (best_type == 0) & ~missed
        if surf_hit_mask.any():
            for si, surf in enumerate(surfaces):
                smask = surf_hit_mask & (best_obj == si)
                if not smask.any():
                    continue
                hit_idx = active_idx[smask]
                t_vals = best_t[smask]
                hit_pts = origins[hit_idx] + t_vals[:, None] * directions[hit_idx]
                normal = surf.normal
                # Resolve optical properties (optical_properties_name takes priority)
                mat = None
                if getattr(surf, 'optical_properties_name', ''):
                    mat = project.optical_properties.get(surf.optical_properties_name)
                if mat is None:
                    mat = materials.get(surf.material_name)
                if mat is None or mat.surface_type == "absorber":
                    alive[hit_idx] = False
                    continue
                dot = np.einsum("ij,j->i", directions[hit_idx], normal)
                flip = dot > 0
                on = np.where(flip[:, None], -normal, normal)
                # Spectral R/T lookup (before BSDF dispatch).
                # NOTE: spectral+MP is guarded at run() entry; wavelengths are always None here.
                # When spectral+MP support is added, wire wavelength interpolation here
                # (see _bounce_surfaces lines 1125-1141 for the single-thread implementation).
                optics_name_mp = getattr(surf, 'optical_properties_name', '') or surf.material_name
                spec_data_mp = None
                r_vals_mp = None
                # BSDF dispatch
                bsdf_name_mp = getattr(mat, 'bsdf_profile_name', '')
                if bsdf_name_mp and bsdf_cdf_cache_mp.get(bsdf_name_mp) is not None:
                    bsdf_prof_mp = (getattr(project, 'bsdf_profiles', {}) or {}).get(bsdf_name_mp, {})
                    cdfs_mp = bsdf_cdf_cache_mp[bsdf_name_mp]
                    # Determine R/T probability from BSDF angular distribution
                    theta_in_vals_mp = cdfs_mp['theta_in']
                    refl_total_mp = cdfs_mp['refl_total']
                    trans_total_mp = cdfs_mp['trans_total']
                    cos_i_mp = np.clip(np.einsum('ij,ij->i', -directions[hit_idx], on), 0.0, 1.0)
                    theta_i_deg_mp = np.degrees(np.arccos(cos_i_mp))
                    bin_idx_mp = np.clip(
                        np.searchsorted(theta_in_vals_mp, theta_i_deg_mp, side='right') - 1,
                        0, len(theta_in_vals_mp) - 1
                    )
                    r_total_mp = refl_total_mp[bin_idx_mp]
                    t_total_mp = trans_total_mp[bin_idx_mp]
                    rt_sum_mp = r_total_mp + t_total_mp
                    roll_mp = rng.random(len(hit_idx))
                    p_refl_mp = np.where(rt_sum_mp > 0, r_total_mp / np.maximum(rt_sum_mp, 1e-12), 1.0)
                    refl_bsdf_mp = roll_mp < p_refl_mp
                    trans_bsdf_mp = ~refl_bsdf_mp
                    if refl_bsdf_mp.any():
                        ri = hit_idx[refl_bsdf_mp]
                        on_r = on[refl_bsdf_mp]
                        flip_r = flip[refl_bsdf_mp]
                        new_dirs = np.empty_like(directions[ri])
                        for side_val, side_n in [(False, normal), (True, -normal)]:
                            sm = flip_r == side_val
                            if not sm.any():
                                continue
                            new_dirs[sm] = sample_bsdf(int(sm.sum()), directions[ri][sm], side_n, bsdf_prof_mp, 'reflect', rng, cdfs=cdfs_mp)
                        origins[ri] = hit_pts[refl_bsdf_mp] + on_r * _EPSILON
                        directions[ri] = new_dirs
                    if trans_bsdf_mp.any():
                        ti2 = hit_idx[trans_bsdf_mp]
                        on_t = on[trans_bsdf_mp]
                        flip_t = flip[trans_bsdf_mp]
                        new_dirs = np.empty_like(directions[ti2])
                        for side_val, side_n in [(False, normal), (True, -normal)]:
                            sm = flip_t == side_val
                            if not sm.any():
                                continue
                            new_dirs[sm] = sample_bsdf(int(sm.sum()), directions[ti2][sm], side_n, bsdf_prof_mp, 'transmit', rng, cdfs=cdfs_mp)
                        through_n = -on_t
                        origins[ti2] = hit_pts[trans_bsdf_mp] + through_n * _EPSILON
                        directions[ti2] = new_dirs
                    continue
                if mat.surface_type == "reflector":
                    weights[hit_idx] *= mat.reflectance
                    new_dirs = _reflect_batch(directions[hit_idx], on, mat.is_diffuse, rng)
                    if mat.haze > 0 and not mat.is_diffuse:
                        new_dirs = scatter_haze(new_dirs, mat.haze, rng)
                    origins[hit_idx] = hit_pts + on * _EPSILON
                    directions[hit_idx] = new_dirs
                elif mat.surface_type == "diffuser":
                    n_rays = len(hit_idx)
                    roll = rng.uniform(size=n_rays)
                    transmits = roll < mat.transmittance
                    if transmits.any():
                        ti = hit_idx[transmits]
                        through_n = -on[transmits]
                        flip_t = flip[transmits]
                        new_d = np.empty((int(transmits.sum()), 3))
                        for side_val, side_n in [(False, -normal), (True, normal)]:
                            sm = flip_t == side_val
                            if not sm.any():
                                continue
                            new_d[sm] = sample_lambertian(int(sm.sum()), side_n, rng)
                        origins[ti] = hit_pts[transmits] + through_n * _EPSILON
                        directions[ti] = new_d
                    reflects = ~transmits
                    if reflects.any():
                        ri = hit_idx[reflects]
                        weights[ri] *= mat.reflectance
                        refl_on = on[reflects]
                        new_d = _reflect_batch(directions[ri], refl_on, mat.is_diffuse, rng)
                        origins[ri] = hit_pts[reflects] + refl_on * _EPSILON
                        directions[ri] = new_d

        alive[weights < settings.energy_threshold] = False

    spectral_grids = {
        det_name: dg["spectral_grid"]
        for det_name, dg in det_grids.items()
        if dg.get("spectral_grid") is not None
    }
    return {
        "grids": det_grids,
        "spectral_grids": spectral_grids,
        "escaped": escaped_flux,
        "sb_stats": sb_stats,
        "sph_grids": sph_grids,
    }


def _aabb_ray_candidates(origins, directions, aabbs):
    """Return indices of AABBs potentially hit by any ray in the batch (slab test).

    Parameters
    ----------
    origins : (N, 3) float64 — ray origins
    directions : (N, 3) float64 — ray directions (unit vectors)
    aabbs : (M, 6) float64 — [xmin, xmax, ymin, ymax, zmin, zmax] per AABB

    Returns
    -------
    list[int] — indices into aabbs that pass the slab test for at least one ray.
    """
    if aabbs is None or len(aabbs) == 0:
        return []
    inv_dirs = np.where(np.abs(directions) > 1e-15, 1.0 / directions, np.inf)
    candidates = []
    for fi in range(len(aabbs)):
        lo = aabbs[fi, [0, 2, 4]]  # xmin, ymin, zmin
        hi = aabbs[fi, [1, 3, 5]]  # xmax, ymax, zmax
        t0 = (lo - origins) * inv_dirs   # (N, 3)
        t1 = (hi - origins) * inv_dirs   # (N, 3)
        tmin = np.maximum.reduce([np.minimum(t0, t1)], axis=0)   # (N, 3)
        tmax = np.minimum.reduce([np.maximum(t0, t1)], axis=0)   # (N, 3)
        tenter = tmin.max(axis=1)   # (N,)
        texit  = tmax.min(axis=1)   # (N,)
        if np.any((texit >= tenter) & (texit > _EPSILON)):
            candidates.append(fi)
    return candidates


def _reflect_batch(dirs, oriented_normals, is_diffuse, rng):
    """Reflect or scatter an array of rays. oriented_normals is (n,3)."""
    n = len(dirs)
    if is_diffuse:
        out = np.empty_like(dirs)
        # Split by unique normals (flat surfaces have at most 2)
        ref = oriented_normals[0]
        same = np.all(oriented_normals == ref, axis=1)
        if same.all():
            out = sample_diffuse_reflection(n, ref, rng)
        else:
            out[same] = sample_diffuse_reflection(int(same.sum()), ref, rng)
            other = ~same
            out[other] = sample_diffuse_reflection(int(other.sum()), oriented_normals[other][0], rng)
        return out
    else:
        # Per-ray specular reflection: d - 2(d·n)n
        dot = np.einsum("ij,ij->i", dirs, oriented_normals)
        return dirs - 2.0 * dot[:, None] * oriented_normals



# ---------------------------------------------------------------------------
# Cylinder / Prism intersection helpers
# ---------------------------------------------------------------------------

def _intersect_rays_cylinder_side(origins, directions, center, axis, radius, half_length):
    """Analytic ray-cylinder intersection (curved surface). Returns (N,) t values."""
    n_rays = len(origins)
    result = np.full(n_rays, np.inf)
    oc = origins - center
    d_axis = np.einsum("ij,j->i", directions, axis)
    oc_axis = np.einsum("ij,j->i", oc, axis)
    d_perp = directions - d_axis[:, None] * axis
    oc_perp = oc - oc_axis[:, None] * axis
    a = np.einsum("ij,ij->i", d_perp, d_perp)
    b = 2.0 * np.einsum("ij,ij->i", d_perp, oc_perp)
    c = np.einsum("ij,ij->i", oc_perp, oc_perp) - radius * radius
    disc = b * b - 4.0 * a * c
    hit_mask = (a > 1e-14) & (disc >= 0.0)
    if not hit_mask.any():
        return result
    sqrt_disc = np.sqrt(np.maximum(disc[hit_mask], 0.0))
    a_h = a[hit_mask]
    b_h = b[hit_mask]
    t1 = (-b_h - sqrt_disc) / (2.0 * a_h)
    t2 = (-b_h + sqrt_disc) / (2.0 * a_h)
    hit_idx = np.where(hit_mask)[0]
    for k, global_i in enumerate(hit_idx):
        for t_cand in (float(t1[k]), float(t2[k])):
            if t_cand <= _EPSILON:
                continue
            hit_pt = origins[global_i] + t_cand * directions[global_i]
            proj = float(np.dot(hit_pt - center, axis))
            if abs(proj) <= half_length:
                result[global_i] = t_cand
                break
    return result


def _intersect_rays_disc(origins, directions, center, normal, radius):
    """Ray-disc intersection (circular flat cap). Returns (N,) t values."""
    n_rays = len(origins)
    result = np.full(n_rays, np.inf)
    denom = directions @ normal
    nonzero = np.abs(denom) > 1e-12
    if not nonzero.any():
        return result
    d_plane = float(normal @ center)
    t = np.full(n_rays, np.inf)
    t[nonzero] = (d_plane - origins[nonzero] @ normal) / denom[nonzero]
    valid = nonzero & (t > _EPSILON)
    if not valid.any():
        return result
    hit_pts = origins[valid] + t[valid, None] * directions[valid]
    diff = hit_pts - center
    dist_sq = np.einsum("ij,ij->i", diff, diff)
    in_disc = dist_sq <= radius * radius
    valid_idx = np.where(valid)[0]
    result[valid_idx[in_disc]] = t[valid][in_disc]
    return result


def _intersect_prism_cap(origins, directions, cap):
    """Ray-polygon cap intersection using precomputed edge normals. Returns (N,) t values."""
    n_rays = len(origins)
    result = np.full(n_rays, np.inf)
    normal = cap.normal
    denom = directions @ normal
    nonzero = np.abs(denom) > 1e-12
    if not nonzero.any():
        return result
    d_plane = float(normal @ cap.center)
    t = np.full(n_rays, np.inf)
    t[nonzero] = (d_plane - origins[nonzero] @ normal) / denom[nonzero]
    valid = nonzero & (t > _EPSILON)
    if not valid.any():
        return result
    hit_pts = origins[valid] + t[valid, None] * directions[valid]
    local = hit_pts - cap.center
    u_coord = local @ cap.u_axis
    v_coord = local @ cap.v_axis
    verts = cap.vertices_2d
    enorms = cap.edge_normals_2d
    hit_pts_2d = np.column_stack([u_coord, v_coord])
    inside = np.ones(len(hit_pts_2d), dtype=bool)
    for j in range(len(verts)):
        diff_2d = hit_pts_2d - verts[j]
        inside &= (diff_2d @ enorms[j]) <= 0.0
    valid_idx = np.where(valid)[0]
    result[valid_idx[inside]] = t[valid][inside]
    return result

def _intersect_rays_plane(
    origins: np.ndarray,
    directions: np.ndarray,
    normal: np.ndarray,
    center: np.ndarray,
    u_axis: np.ndarray,
    v_axis: np.ndarray,
    size: tuple[float, float],
) -> np.ndarray:
    """General ray-plane intersection with rectangular bounds.

    Works for any surface orientation (axis-aligned or tilted).
    Returns (N,) array of t values (np.inf = no hit).
    """
    n_rays = len(origins)
    result = np.full(n_rays, np.inf)

    denom = directions @ normal          # (N,)
    nonzero = np.abs(denom) > 1e-12
    if not nonzero.any():
        return result

    d_plane = float(normal @ center)
    t = np.full(n_rays, np.inf)
    t[nonzero] = (d_plane - origins[nonzero] @ normal) / denom[nonzero]

    valid = nonzero & (t > _EPSILON)
    if not valid.any():
        return result

    hit_pts = origins[valid] + t[valid, None] * directions[valid]
    local = hit_pts - center                         # (M, 3)
    u_coord = local @ u_axis                         # (M,)
    v_coord = local @ v_axis                         # (M,)

    hw, hh = size[0] / 2.0, size[1] / 2.0
    in_bounds = (np.abs(u_coord) <= hw) & (np.abs(v_coord) <= hh)

    valid_idx = np.where(valid)[0]
    result[valid_idx[in_bounds]] = t[valid][in_bounds]
    return result


def _intersect_rays_sphere(
    origins: np.ndarray,
    directions: np.ndarray,
    center: np.ndarray,
    radius: float,
) -> np.ndarray:
    """Ray-sphere intersection. Returns (N,) t values (np.inf = no hit)."""
    n_rays = len(origins)
    result = np.full(n_rays, np.inf)
    L = origins - center                          # (N, 3)
    a = np.einsum("ij,ij->i", directions, directions)  # (N,)
    b = 2.0 * np.einsum("ij,ij->i", directions, L)     # (N,)
    c = np.einsum("ij,ij->i", L, L) - radius * radius   # (N,)
    disc = b * b - 4.0 * a * c
    has_hit = disc >= 0
    if not has_hit.any():
        return result
    sqrt_disc = np.sqrt(np.maximum(disc[has_hit], 0.0))
    a_h = a[has_hit]
    b_h = b[has_hit]
    t1 = (-b_h - sqrt_disc) / (2.0 * a_h)
    t2 = (-b_h + sqrt_disc) / (2.0 * a_h)
    # Pick the nearest positive t
    t_near = np.where(t1 > _EPSILON, t1, np.where(t2 > _EPSILON, t2, np.inf))
    idx = np.where(has_hit)[0]
    result[idx] = t_near
    return result


def _accumulate_sphere(sd: "SphereDetector", result: "SphereDetectorResult",
                       hit_pts: np.ndarray, hit_weights: np.ndarray):
    """Bin hit points on a sphere into (theta, phi) grid (near_field mode)."""
    d = hit_pts - sd.center                       # (M, 3)
    r = np.linalg.norm(d, axis=1, keepdims=True)
    r = np.maximum(r, 1e-12)
    d_norm = d / r
    # theta: angle from +Z (0=north pole, pi=south pole)
    theta = np.arccos(np.clip(d_norm[:, 2], -1.0, 1.0))
    # phi: azimuthal angle (0..2pi)
    phi = np.arctan2(d_norm[:, 1], d_norm[:, 0])
    phi = np.where(phi < 0, phi + 2.0 * np.pi, phi)

    n_phi, n_theta = sd.resolution
    i_theta = np.clip((theta / np.pi * n_theta).astype(int), 0, n_theta - 1)
    i_phi = np.clip((phi / (2.0 * np.pi) * n_phi).astype(int), 0, n_phi - 1)

    accumulate_sphere_jit(result.grid, i_theta, i_phi, hit_weights)
    result.total_hits += len(hit_weights)
    result.total_flux += float(hit_weights.sum())


def _accumulate_sphere_farfield(sd: "SphereDetector", result: "SphereDetectorResult",
                                directions_at_hit: np.ndarray, hit_weights: np.ndarray):
    """Bin ray directions into (theta, phi) grid for far-field accumulation.

    Uses the ray direction at the moment of sphere intersection (negated to give
    the outgoing direction from the luminaire region).
    """
    # Negate: rays travel toward the sphere; outgoing direction = -ray_direction
    d = -directions_at_hit                        # (M, 3) outgoing directions
    r = np.linalg.norm(d, axis=1, keepdims=True)
    r = np.maximum(r, 1e-12)
    d_norm = d / r
    # theta: angle from +Z (0=north pole, pi=south pole)
    theta = np.arccos(np.clip(d_norm[:, 2], -1.0, 1.0))
    # phi: azimuthal angle (0..2pi)
    phi = np.arctan2(d_norm[:, 1], d_norm[:, 0])
    phi = np.where(phi < 0, phi + 2.0 * np.pi, phi)

    n_phi, n_theta = sd.resolution
    i_theta = np.clip((theta / np.pi * n_theta).astype(int), 0, n_theta - 1)
    i_phi = np.clip((phi / (2.0 * np.pi) * n_phi).astype(int), 0, n_phi - 1)

    accumulate_sphere_jit(result.grid, i_theta, i_phi, hit_weights)
    result.total_hits += len(hit_weights)
    result.total_flux += float(hit_weights.sum())


def compute_farfield_candela(sd: "SphereDetector", result: "SphereDetectorResult"):
    """Compute candela distribution from raw flux grid using solid angle normalization.

    candela_grid[i, j] = result.grid[i, j] / solid_angle_per_bin[i]
    where solid_angle_per_bin[i] = (pi / n_theta) * (2*pi / n_phi) * sin(theta_center[i])
    with a floor of 1e-6 on sin(theta) to avoid division by zero at poles.
    """
    n_phi, n_theta = sd.resolution
    theta_centers = (np.arange(n_theta) + 0.5) * np.pi / n_theta  # (n_theta,)
    sin_theta = np.maximum(np.sin(theta_centers), 1e-6)             # floor at poles
    solid_angle_per_bin = (np.pi / n_theta) * (2.0 * np.pi / n_phi) * sin_theta  # (n_theta,)
    result.candela_grid = result.grid / solid_angle_per_bin[:, None]


def _accumulate(det: DetectorSurface, result: DetectorResult,
                hit_pts: np.ndarray, hit_weights: np.ndarray,
                color_rgb: tuple[float, float, float] | None = None,
                wavelengths: np.ndarray | None = None,
                spec_centers: np.ndarray | None = None):
    """Bin hit points into the detector grid using local u/v coordinates."""
    local = hit_pts - det.center                   # (M, 3)
    u = local @ det.u_axis                         # (M,)
    v = local @ det.v_axis                         # (M,)

    hw, hh = det.size[0] / 2.0, det.size[1] / 2.0
    nx, ny = det.resolution

    ix = np.clip(((u + hw) / det.size[0] * nx).astype(int), 0, nx - 1)
    iy = np.clip(((v + hh) / det.size[1] * ny).astype(int), 0, ny - 1)

    accumulate_grid_jit(result.grid, iy, ix, hit_weights)
    result.total_hits += len(hit_weights)
    result.total_flux += float(hit_weights.sum())

    # Accumulate RGB channels if color data present
    if color_rgb is not None and result.grid_rgb is not None:
        for ch in range(3):
            accumulate_grid_jit(result.grid_rgb[:, :, ch], iy, ix, hit_weights * color_rgb[ch])

    # Accumulate spectral bins
    if wavelengths is not None and spec_centers is not None and result.grid_spectral is not None:
        n_bins = len(spec_centers)
        bin_width = (LAMBDA_MAX - LAMBDA_MIN) / max(n_bins - 1, 1)
        i_bin = np.clip(((wavelengths - LAMBDA_MIN) / bin_width).astype(int), 0, n_bins - 1)
        for b in range(n_bins):
            bmask = i_bin == b
            if bmask.any():
                accumulate_grid_jit(result.grid_spectral[:, :, b], iy[bmask], ix[bmask], hit_weights[bmask])
