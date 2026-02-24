"""Monte Carlo ray tracing engine — general plane intersection."""

from __future__ import annotations

from typing import Callable

import numpy as np

from backlight_sim.core.project_model import Project
from backlight_sim.core.geometry import Rectangle
from backlight_sim.core.detectors import DetectorSurface, DetectorResult, SimulationResult
from backlight_sim.sim.sampling import (
    sample_isotropic,
    sample_lambertian,
    sample_angular_distribution,
    sample_diffuse_reflection,
    reflect_specular,
)

_EPSILON = 1e-6


class RayTracer:
    def __init__(self, project: Project):
        self.project = project
        self.rng = np.random.default_rng(project.settings.random_seed)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self, progress_callback: Callable[[float], None] | None = None) -> SimulationResult:
        self._cancelled = False
        settings = self.project.settings
        sources = self.project.sources
        surfaces = self.project.surfaces
        detectors = self.project.detectors
        materials = self.project.materials
        distributions = self.project.angular_distributions
        n_record = settings.record_ray_paths

        # Initialise detector grids
        det_results: dict[str, DetectorResult] = {}
        for det in detectors:
            grid = np.zeros((det.resolution[1], det.resolution[0]), dtype=float)
            det_results[det.name] = DetectorResult(
                detector_name=det.name, grid=grid
            )

        if not sources or (not surfaces and not detectors):
            return SimulationResult(detectors=det_results)

        total_rays = len(sources) * settings.rays_per_source
        rays_processed = 0
        all_paths: list[list[np.ndarray]] = []

        for src_idx, source in enumerate(sources):
            if self._cancelled:
                break

            n = settings.rays_per_source

            # ---- emit rays ----
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
            weights = np.full(n, source.flux / n)
            alive = np.ones(n, dtype=bool)

            # ---- path recording setup ----
            # Only record for the first source, first n_record rays
            record = (src_idx == 0) and (n_record > 0)
            n_rec = min(n_record, n) if record else 0
            paths: list[list[np.ndarray]] = [
                [source.position.copy()] for _ in range(n_rec)
            ]

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

                for si, surf in enumerate(surfaces):
                    t = _intersect_rays_plane(active_origins, active_dirs, surf.normal, surf.center,
                                               surf.u_axis, surf.v_axis, surf.size)
                    closer = t < best_t
                    best_t[closer] = t[closer]
                    best_type[closer] = 0
                    best_obj[closer] = si

                for di, det in enumerate(detectors):
                    t = _intersect_rays_plane(active_origins, active_dirs, det.normal, det.center,
                                               det.u_axis, det.v_axis, det.size)
                    closer = t < best_t
                    best_t[closer] = t[closer]
                    best_type[closer] = 1
                    best_obj[closer] = di

                # Rays that escape
                missed = best_t == np.inf
                alive[active_idx[missed]] = False

                # Detector hits
                for di, det in enumerate(detectors):
                    mask = (best_type == 1) & (best_obj == di)
                    if not mask.any():
                        continue
                    hit_idx = active_idx[mask]
                    hit_pts = origins[hit_idx] + best_t[mask, None] * directions[hit_idx]
                    _accumulate(det, det_results[det.name], hit_pts, weights[hit_idx])
                    # Record path waypoints
                    if n_rec > 0:
                        for local_i, global_i in enumerate(hit_idx):
                            if global_i < n_rec:
                                paths[global_i].append(hit_pts[local_i].copy())
                    alive[hit_idx] = False

                # Surface hits
                surf_hit_mask = (best_type == 0) & ~missed
                if surf_hit_mask.any():
                    self._bounce_surfaces(
                        surf_hit_mask, active_idx, best_t, best_obj,
                        origins, directions, weights, alive, surfaces, materials,
                        paths, n_rec,
                    )

                alive[weights < settings.energy_threshold] = False

            # Collect paths for this source
            if record:
                all_paths.extend(paths)

            rays_processed += n
            if progress_callback:
                progress_callback(rays_processed / total_rays)

        return SimulationResult(detectors=det_results, ray_paths=all_paths)

    # ------------------------------------------------------------------

    def _bounce_surfaces(
        self, surf_hit, active_idx, best_t, best_obj,
        origins, directions, weights, alive,
        surfaces, materials, paths, n_rec,
    ):
        for si, surf in enumerate(surfaces):
            mask = surf_hit & (best_obj == si)
            if not mask.any():
                continue

            hit_idx = active_idx[mask]
            t_vals = best_t[mask]
            hit_pts = origins[hit_idx] + t_vals[:, None] * directions[hit_idx]
            normal = surf.normal

            mat = materials.get(surf.material_name)

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

            if mat.surface_type == "reflector":
                weights[hit_idx] *= mat.reflectance
                new_dirs = _reflect_batch(directions[hit_idx], on, mat.is_diffuse, self.rng)
                origins[hit_idx] = hit_pts + on * _EPSILON
                directions[hit_idx] = new_dirs

            elif mat.surface_type == "diffuser":
                n_rays = len(hit_idx)
                roll = self.rng.uniform(size=n_rays)
                transmits = roll < mat.transmittance

                if transmits.any():
                    ti = hit_idx[transmits]
                    through_n = -on[transmits]
                    new_dirs = sample_lambertian(int(transmits.sum()), through_n[0], self.rng)
                    origins[ti] = hit_pts[transmits] + through_n * _EPSILON
                    directions[ti] = new_dirs

                reflects = ~transmits
                if reflects.any():
                    ri = hit_idx[reflects]
                    weights[ri] *= mat.reflectance
                    refl_on = on[reflects]
                    new_dirs = _reflect_batch(directions[ri], refl_on, mat.is_diffuse, self.rng)
                    origins[ri] = hit_pts[reflects] + refl_on * _EPSILON
                    directions[ri] = new_dirs


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


def _accumulate(det: DetectorSurface, result: DetectorResult,
                hit_pts: np.ndarray, hit_weights: np.ndarray):
    """Bin hit points into the detector grid using local u/v coordinates."""
    local = hit_pts - det.center                   # (M, 3)
    u = local @ det.u_axis                         # (M,)
    v = local @ det.v_axis                         # (M,)

    hw, hh = det.size[0] / 2.0, det.size[1] / 2.0
    nx, ny = det.resolution

    ix = np.clip(((u + hw) / det.size[0] * nx).astype(int), 0, nx - 1)
    iy = np.clip(((v + hh) / det.size[1] * ny).astype(int), 0, ny - 1)

    np.add.at(result.grid, (iy, ix), hit_weights)
    result.total_hits += len(hit_weights)
    result.total_flux += float(hit_weights.sum())
