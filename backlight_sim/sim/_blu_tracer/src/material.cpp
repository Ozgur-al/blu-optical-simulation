#include "material.hpp"
#include "sampling.hpp"
#include <cmath>
#include <algorithm>

// ---------------------------------------------------------------------------
// Fresnel reflectance (unpolarized) — ported from tracer.py::_fresnel_unpolarized
// ---------------------------------------------------------------------------
double fresnel_unpolarized(double cos_theta_i, double n1, double n2) {
    const double cos_i = std::max(0.0, std::min(1.0, cos_theta_i));
    const double ratio = n1 / n2;
    const double sin_t_sq = ratio * ratio * (1.0 - cos_i*cos_i);
    if (sin_t_sq >= 1.0) return 1.0;  // TIR
    const double cos_t = std::sqrt(std::max(0.0, 1.0 - sin_t_sq));
    const double denom_s = std::max(1e-12, n1*cos_i + n2*cos_t);
    const double denom_p = std::max(1e-12, n2*cos_i + n1*cos_t);
    const double rs = (n1*cos_i - n2*cos_t) / denom_s;
    const double rp = (n2*cos_i - n1*cos_t) / denom_p;
    return 0.5*(rs*rs + rp*rp);
}

// ---------------------------------------------------------------------------
// Snell refraction — ported from tracer.py::_refract_snell
// on_into points into the new medium. Returns false on TIR.
// ---------------------------------------------------------------------------
bool refract_snell(
    double dx, double dy, double dz,
    double on_x, double on_y, double on_z,
    double n1, double n2,
    double& rdx, double& rdy, double& rdz)
{
    const double eta = n1 / n2;
    const double cos_i = std::max(0.0, std::min(1.0, dx*on_x + dy*on_y + dz*on_z));
    const double sin_t_sq = eta*eta*(1.0 - cos_i*cos_i);
    if (sin_t_sq >= 1.0) return false;  // TIR
    const double cos_t = std::sqrt(std::max(0.0, 1.0 - sin_t_sq));
    // n_hat points back into the old medium (opposite on_into)
    const double nx_h = -on_x, ny_h = -on_y, nz_h = -on_z;
    rdx = eta*dx + (eta*cos_i - cos_t)*nx_h;
    rdy = eta*dy + (eta*cos_i - cos_t)*ny_h;
    rdz = eta*dz + (eta*cos_i - cos_t)*nz_h;
    const double norm = std::sqrt(rdx*rdx + rdy*rdy + rdz*rdz);
    if (norm > 1e-12) { rdx /= norm; rdy /= norm; rdz /= norm; }
    return true;
}

// ---------------------------------------------------------------------------
// Apply material dispatch at a regular (non-solid-body) surface hit.
// Matches tracer.py::_bounce_surfaces for surface_type reflector/absorber/diffuser.
// ---------------------------------------------------------------------------
void apply_material(
    int i, RayBatch& batch,
    const SceneMaterial& mat,
    double hit_x, double hit_y, double hit_z,
    double face_nx, double face_ny, double face_nz,
    double geom_eps, std::mt19937_64& rng)
{
    if (mat.surface_type == "absorber") {
        batch.alive[i] = false;
        return;
    }
    // Orient normal AGAINST the incoming ray (pointing back toward where the ray came from)
    const double dot_dn = batch.dx[i]*face_nx + batch.dy[i]*face_ny + batch.dz[i]*face_nz;
    const double on_x = (dot_dn > 0.0) ? -face_nx : face_nx;
    const double on_y = (dot_dn > 0.0) ? -face_ny : face_ny;
    const double on_z = (dot_dn > 0.0) ? -face_nz : face_nz;

    if (mat.surface_type == "reflector") {
        batch.weights[i] *= mat.reflectance;
        double rdx, rdy, rdz;
        if (mat.is_diffuse) {
            sample_lambertian_single(on_x, on_y, on_z, rng, rdx, rdy, rdz);
        } else {
            reflect_specular(batch.dx[i], batch.dy[i], batch.dz[i],
                             on_x, on_y, on_z, rdx, rdy, rdz);
            if (mat.haze > 0.0) {
                double sx, sy, sz;
                scatter_haze_single(rdx, rdy, rdz, mat.haze, rng, sx, sy, sz);
                rdx = sx; rdy = sy; rdz = sz;
            }
        }
        batch.ox[i] = hit_x + on_x*geom_eps;
        batch.oy[i] = hit_y + on_y*geom_eps;
        batch.oz[i] = hit_z + on_z*geom_eps;
        batch.dx[i] = rdx; batch.dy[i] = rdy; batch.dz[i] = rdz;
        return;
    }

    if (mat.surface_type == "diffuser") {
        std::uniform_real_distribution<double> uni(0.0, 1.0);
        if (uni(rng) < mat.transmittance) {
            // Transmit: Lambertian through the plane (reverse normal direction)
            const double through_x = -on_x;
            const double through_y = -on_y;
            const double through_z = -on_z;
            double tdx, tdy, tdz;
            sample_lambertian_single(through_x, through_y, through_z, rng, tdx, tdy, tdz);
            batch.ox[i] = hit_x + through_x*geom_eps;
            batch.oy[i] = hit_y + through_y*geom_eps;
            batch.oz[i] = hit_z + through_z*geom_eps;
            batch.dx[i] = tdx; batch.dy[i] = tdy; batch.dz[i] = tdz;
        } else {
            // Reflect: Lambertian with weight * reflectance
            batch.weights[i] *= mat.reflectance;
            double rdx, rdy, rdz;
            sample_lambertian_single(on_x, on_y, on_z, rng, rdx, rdy, rdz);
            batch.ox[i] = hit_x + on_x*geom_eps;
            batch.oy[i] = hit_y + on_y*geom_eps;
            batch.oz[i] = hit_z + on_z*geom_eps;
            batch.dx[i] = rdx; batch.dy[i] = rdy; batch.dz[i] = rdz;
        }
        return;
    }

    // Unknown type — default to absorb (defensive)
    batch.alive[i] = false;
}
