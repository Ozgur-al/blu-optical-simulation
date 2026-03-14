"""Monte Carlo ray tracing engine — general plane intersection."""

from __future__ import annotations

import multiprocessing
from concurrent.futures import ProcessPoolExecutor
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
from backlight_sim.sim.spectral import (
    sample_wavelengths, spectral_bin_centers, N_SPECTRAL_BINS, LAMBDA_MIN, LAMBDA_MAX,
    get_spd_from_project,
)
from backlight_sim.sim.accel import (
    _NUMBA_AVAILABLE,
    intersect_plane as _intersect_plane_accel,
    intersect_sphere as _intersect_sphere_accel,
    accumulate_grid_jit,
    accumulate_sphere_jit,
    compute_surface_aabbs,
    build_bvh_flat,
    traverse_bvh_batch,
)

_EPSILON = 1e-6

# BVH activation threshold: use BVH when total plane surfaces >= this count
_BVH_THRESHOLD = 50


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
    ) -> SimulationResult:
        self._cancelled = False
        settings = self.project.settings

        # Use multiprocessing if enabled and there are multiple sources
        sources = [s for s in self.project.sources if s.enabled]

        # Spectral + MP guard: wavelength-dependent material lookup is not yet
        # implemented in the MP path (_trace_single_source).  Fall back to
        # single-thread mode and warn.
        has_spectral = any(s.spd != "white" for s in sources)
        if has_spectral and settings.use_multiprocessing:
            import warnings
            warnings.warn(
                "Spectral simulation forcing single-thread mode "
                "(spectral + multiprocessing is not yet optimized)",
                stacklevel=2,
            )
            return self._run_single(sources, progress_callback, convergence_callback)

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

        if (settings.use_multiprocessing and len(sources) > 1
                and not settings.record_ray_paths):
            return self._run_multiprocess(sources, progress_callback)

        return self._run_single(sources, progress_callback, convergence_callback,
                                _adaptive=_adaptive)

    def _run_multiprocess(self, sources, progress_callback):
        """Run each source in a separate process and merge results."""
        settings = self.project.settings
        detectors = self.project.detectors

        det_results: dict[str, DetectorResult] = {}
        for det in detectors:
            grid = np.zeros((det.resolution[1], det.resolution[0]), dtype=float)
            det_results[det.name] = DetectorResult(detector_name=det.name, grid=grid)

        # Initialize merged solid_body_stats
        merged_sb_stats: dict[str, dict[str, dict[str, float]]] = {}
        for box in self.project.solid_bodies:
            merged_sb_stats[box.name] = {
                fid: {"entering_flux": 0.0, "exiting_flux": 0.0}
                for fid in FACE_NAMES
            }

        total_emitted_flux = sum(s.effective_flux for s in sources)

        n_workers = min(len(sources), max(1, multiprocessing.cpu_count() - 1))
        completed = 0
        total = len(sources)
        escaped_total = 0.0

        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            futures = []
            for src in sources:
                f = pool.submit(
                    _trace_single_source,
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
                # Merge solid_body_stats
                for box_name, face_map in result.get("sb_stats", {}).items():
                    if box_name in merged_sb_stats:
                        for fid, flux_data in face_map.items():
                            merged_sb_stats[box_name][fid]["entering_flux"] += flux_data["entering_flux"]
                            merged_sb_stats[box_name][fid]["exiting_flux"] += flux_data["exiting_flux"]
                completed += 1
                if progress_callback:
                    progress_callback(completed / total)

            if errors:
                import warnings
                warnings.warn(
                    f"{len(errors)} source(s) failed in multiprocessing: {errors[0]}"
                )

        return SimulationResult(
            detectors=det_results,
            total_emitted_flux=total_emitted_flux,
            escaped_flux=escaped_total,
            source_count=len(sources),
            solid_body_stats=merged_sb_stats,
        )

    def _run_single(self, sources, progress_callback, convergence_callback=None,
                    _adaptive=None):
        settings = self.project.settings
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

        # ---- BVH setup for plane surfaces (activated when total plane count >= threshold) ----
        n_all_planes = len(surfaces) + len(solid_faces)
        use_bvh = n_all_planes >= _BVH_THRESHOLD
        bvh_bounds = bvh_meta = bvh_n_nodes = None
        bvh_normals = bvh_centers = bvh_u = bvh_v = bvh_hw = bvh_hh = None
        n_surf_planes = len(surfaces)  # boundary index: idx < n_surf_planes -> surface, else solid face

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

        # Pre-compute BSDF CDFs for all profiles in the project
        bsdf_cdf_cache: dict[str, dict] = {}
        for bsdf_name, bsdf_profile in (self.project.bsdf_profiles or {}).items():
            bsdf_cdf_cache[bsdf_name] = precompute_bsdf_cdfs(bsdf_profile)

        total_rays = len(sources) * settings.rays_per_source
        rays_processed = 0
        all_paths: list[list[np.ndarray]] = []
        escaped_flux = 0.0

        for src_idx, source in enumerate(sources):
            if self._cancelled:
                break

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

                    # SolidCylinder face intersections (type 4)
                    for cfi, cface in enumerate(cyl_faces):
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

                    # SolidPrism face intersections (type 5)
                    for pfi, pface in enumerate(prism_faces):
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
                        n2_arr = np.where(entering, box_n, 1.0)

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
                            # Update refractive index: entering→box_n, exiting→1.0
                            current_n[ri] = n2_r
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
                        n1_arr = current_n[hit_idx].copy()
                        n2_arr = np.where(entering, cyl_n, 1.0)
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
                        n1_arr = current_n[hit_idx].copy()
                        n2_arr = np.where(entering, prism_n, 1.0)
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
                progress_callback(rays_processed / total_rays)

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

            # --- BSDF dispatch: overrides all scalar R/T/diffuse behavior ---
            bsdf_name = getattr(mat, "bsdf_profile_name", "")
            if bsdf_name and (bsdf_cdf_cache or {}).get(bsdf_name) is not None:
                bsdf_profile = (self.project.bsdf_profiles or {}).get(bsdf_name, {})
                cdfs = (bsdf_cdf_cache or {}).get(bsdf_name)
                n_hit = len(hit_idx)
                # Apply reflectance weight scaling (energy conservation via material reflectance)
                weights[hit_idx] *= mat.reflectance
                # Determine R/T probability from BSDF profile angular distribution
                # refl_total / trans_total give relative probabilities per theta_in bin
                theta_in_vals = cdfs["theta_in"]
                refl_total = cdfs["refl_total"]   # (M,) — sin-weighted integrals
                trans_total = cdfs["trans_total"]  # (M,)
                cos_i = np.clip(np.einsum("ij,j->i", -directions[hit_idx], on[0]), 0.0, 1.0)
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
                    # oriented surface normal (pointing away from incoming ray) for each hit ray
                    on_r = on[reflects_bsdf]
                    # Use first on as surface normal for BSDF (majority normal)
                    surf_n = on_r[0] if len(on_r) > 0 else normal
                    new_dirs = sample_bsdf(
                        int(reflects_bsdf.sum()), inc, surf_n, bsdf_profile, "reflect",
                        self.rng, cdfs=cdfs,
                    )
                    origins[ri] = hit_pts[reflects_bsdf] + on_r * _EPSILON
                    directions[ri] = new_dirs
                if transmits_bsdf.any():
                    ti = hit_idx[transmits_bsdf]
                    inc = directions[ti]
                    on_t = on[transmits_bsdf]
                    surf_n = on_t[0] if len(on_t) > 0 else normal
                    # Transmit through: opposite side of normal
                    new_dirs = sample_bsdf(
                        int(transmits_bsdf.sum()), inc, surf_n, bsdf_profile, "transmit",
                        self.rng, cdfs=cdfs,
                    )
                    through_n = -on_t
                    origins[ti] = hit_pts[transmits_bsdf] + through_n * _EPSILON
                    directions[ti] = new_dirs
                continue

            # Resolve spectral material properties (per-wavelength R/T lookup)
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
                    new_dirs = sample_lambertian(int(transmits.sum()), through_n[0], self.rng)
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
    materials = project.materials
    distributions = project.angular_distributions

    det_grids = {}
    for det in detectors:
        det_grids[det.name] = {
            "grid": np.zeros((det.resolution[1], det.resolution[0]), dtype=float),
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
    escaped_flux = 0.0

    # Pre-compute BSDF CDFs for all profiles in the project
    bsdf_cdf_cache_mp: dict[str, dict] = {}
    for bsdf_nm, bsdf_prof in (getattr(project, "bsdf_profiles", {}) or {}).items():
        bsdf_cdf_cache_mp[bsdf_nm] = precompute_bsdf_cdfs(bsdf_prof)

    # BVH setup for MP path
    n_all_planes_mp = len(surfaces) + len(solid_faces)
    use_bvh_mp = n_all_planes_mp >= _BVH_THRESHOLD
    bvh_bounds_mp = bvh_meta_mp = bvh_n_nodes_mp = None
    bvh_normals_mp = bvh_centers_mp = bvh_u_mp = bvh_v_mp = bvh_hw_mp = bvh_hh_mp = None
    n_surf_planes_mp = len(surfaces)

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

        # Detectors always tested separately
        for di, det in enumerate(detectors):
            t = _intersect_plane_accel(active_origins, active_dirs, det.normal, det.center,
                                       det.u_axis, det.v_axis, det.size)
            closer = t < best_t
            best_t[closer] = t[closer]
            best_type[closer] = 1
            best_obj[closer] = di

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
            # Pass-through: advance ray past the detector plane
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

            dot_dn = np.einsum("ij,j->i", directions[hit_idx], face_normal)
            entering = dot_dn < 0

            # on_into: normal pointing INTO the new medium.
            # Entering: on_into = -face_normal (box interior side)
            # Exiting: on_into = +face_normal (air side)
            on_into = np.where(entering[:, None], -face_normal, face_normal)
            on_back = -on_into   # points toward incoming ray (old medium)

            n1_arr = current_n[hit_idx].copy()
            n2_arr = np.where(entering, box_n, 1.0)

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
                # BSDF dispatch
                bsdf_name_mp = getattr(mat, 'bsdf_profile_name', '')
                if bsdf_name_mp and bsdf_cdf_cache_mp.get(bsdf_name_mp) is not None:
                    bsdf_prof_mp = (getattr(project, 'bsdf_profiles', {}) or {}).get(bsdf_name_mp, {})
                    cdfs_mp = bsdf_cdf_cache_mp[bsdf_name_mp]
                    # Apply reflectance weight scaling (energy conservation)
                    weights[hit_idx] *= mat.reflectance
                    # Determine R/T probability from BSDF angular distribution
                    theta_in_vals_mp = cdfs_mp['theta_in']
                    refl_total_mp = cdfs_mp['refl_total']
                    trans_total_mp = cdfs_mp['trans_total']
                    cos_i_mp = np.clip(np.einsum('ij,j->i', -directions[hit_idx], on[0]), 0.0, 1.0)
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
                        surf_n_mp = on_r[0] if len(on_r) > 0 else normal
                        new_dirs = sample_bsdf(int(refl_bsdf_mp.sum()), directions[ri], surf_n_mp, bsdf_prof_mp, 'reflect', rng, cdfs=cdfs_mp)
                        origins[ri] = hit_pts[refl_bsdf_mp] + on_r * _EPSILON
                        directions[ri] = new_dirs
                    if trans_bsdf_mp.any():
                        ti2 = hit_idx[trans_bsdf_mp]
                        on_t = on[trans_bsdf_mp]
                        surf_n_mp = on_t[0] if len(on_t) > 0 else normal
                        new_dirs = sample_bsdf(int(trans_bsdf_mp.sum()), directions[ti2], surf_n_mp, bsdf_prof_mp, 'transmit', rng, cdfs=cdfs_mp)
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
                        new_d = sample_lambertian(int(transmits.sum()), through_n[0], rng)
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

    return {"grids": det_grids, "escaped": escaped_flux, "sb_stats": sb_stats}


def _reflect_batch(dirs, oriented_normals, is_diffuse, rng):
    """Reflect or scatter an array of rays. oriented_normals is (n,3)."""
    n = len(dirs)
    if is_diffuse:
        # Each ray may have a different oriented normal — handle vectorised
        out = np.empty_like(dirs)
        # Group by unique normals is complex; for small n just loop
        if n <= 32:
            for i in range(n):
                out[i] = sample_diffuse_reflection(1, oriented_normals[i], rng)[0]
        else:
            # Use majority normal as approximation for large batches
            majority = oriented_normals[0]
            out = sample_diffuse_reflection(n, majority, rng)
        return out
    else:
        return reflect_specular(dirs, oriented_normals[0])



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
