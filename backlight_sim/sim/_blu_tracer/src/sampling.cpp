#include "sampling.hpp"
#include <cmath>
#include <algorithm>
#include <vector>

static constexpr double PI = 3.14159265358979323846;

// ---------------------------------------------------------------------------
// Orthonormal basis construction.
// Matches sampling.py::_build_basis: picks ref=(1,0,0) unless |wx| >= 0.9,
// in which case ref=(0,1,0). tangent = cross(w, ref) / |.|; bitangent = cross(w, tangent).
// ---------------------------------------------------------------------------
void build_basis(double wx, double wy, double wz,
                 double& ux, double& uy, double& uz,
                 double& vx, double& vy, double& vz)
{
    double ref_x = 1.0, ref_y = 0.0, ref_z = 0.0;
    if (std::abs(wx) >= 0.9) { ref_x = 0.0; ref_y = 1.0; ref_z = 0.0; }
    // tangent = cross(w, ref)
    ux = wy*ref_z - wz*ref_y;
    uy = wz*ref_x - wx*ref_z;
    uz = wx*ref_y - wy*ref_x;
    double norm_u = std::sqrt(ux*ux + uy*uy + uz*uz);
    if (norm_u < 1e-12) norm_u = 1.0;
    ux /= norm_u; uy /= norm_u; uz /= norm_u;
    // bitangent = cross(w, tangent)
    vx = wy*uz - wz*uy;
    vy = wz*ux - wx*uz;
    vz = wx*uy - wy*ux;
    double norm_v = std::sqrt(vx*vx + vy*vy + vz*vz);
    if (norm_v < 1e-12) norm_v = 1.0;
    vx /= norm_v; vy /= norm_v; vz /= norm_v;
}

void sample_isotropic(int n, std::mt19937_64& rng, RayBatch& batch) {
    std::uniform_real_distribution<double> uni_z(-1.0, 1.0);
    std::uniform_real_distribution<double> uni_phi(0.0, 2.0*PI);
    for (int i = 0; i < n; ++i) {
        const double z = uni_z(rng);
        const double phi = uni_phi(rng);
        const double r = std::sqrt(std::max(0.0, 1.0 - z*z));
        batch.dx[i] = r * std::cos(phi);
        batch.dy[i] = r * std::sin(phi);
        batch.dz[i] = z;
    }
}

void sample_lambertian(int n, double nx, double ny, double nz,
                       std::mt19937_64& rng, RayBatch& batch)
{
    // Normalize the normal defensively
    double nn = std::sqrt(nx*nx + ny*ny + nz*nz);
    if (nn < 1e-12) { nx = 0.0; ny = 0.0; nz = 1.0; nn = 1.0; }
    nx /= nn; ny /= nn; nz /= nn;

    double ux, uy, uz, vx, vy, vz;
    build_basis(nx, ny, nz, ux, uy, uz, vx, vy, vz);
    std::uniform_real_distribution<double> uni(0.0, 1.0);
    for (int i = 0; i < n; ++i) {
        const double r = std::sqrt(uni(rng));
        const double phi = uni(rng) * 2.0*PI;
        const double xl = r * std::cos(phi);
        const double yl = r * std::sin(phi);
        const double zl = std::sqrt(std::max(0.0, 1.0 - xl*xl - yl*yl));
        batch.dx[i] = xl*ux + yl*vx + zl*nx;
        batch.dy[i] = xl*uy + yl*vy + zl*ny;
        batch.dz[i] = xl*uz + yl*vz + zl*nz;
    }
}

void sample_angular_distribution(int n,
                                  double dir_x, double dir_y, double dir_z,
                                  const std::vector<double>& theta_deg,
                                  const std::vector<double>& intensity,
                                  std::mt19937_64& rng, RayBatch& batch)
{
    if (theta_deg.size() < 2 || intensity.size() != theta_deg.size()) {
        sample_lambertian(n, dir_x, dir_y, dir_z, rng, batch);
        return;
    }
    // Normalize direction
    double nn = std::sqrt(dir_x*dir_x + dir_y*dir_y + dir_z*dir_z);
    if (nn < 1e-12) { dir_x = 0.0; dir_y = 0.0; dir_z = 1.0; nn = 1.0; }
    dir_x /= nn; dir_y /= nn; dir_z /= nn;

    // Build 2048-point grid and CDF (matches sampling.py::sample_angular_distribution)
    const int NGRID = 2048;
    const double theta_min_rad = theta_deg.front() * PI / 180.0;
    const double theta_max_rad = theta_deg.back()  * PI / 180.0;
    std::vector<double> grid(NGRID);
    for (int k = 0; k < NGRID; ++k) {
        grid[k] = theta_min_rad + (theta_max_rad - theta_min_rad) * k / (NGRID - 1);
    }

    auto interp_deg = [&](double x_rad) -> double {
        const double x_deg = x_rad * 180.0 / PI;
        if (x_deg <= theta_deg.front()) return intensity.front();
        if (x_deg >= theta_deg.back())  return intensity.back();
        auto it = std::lower_bound(theta_deg.begin(), theta_deg.end(), x_deg);
        const int hi = (int)(it - theta_deg.begin());
        const int lo = hi - 1;
        const double denom = theta_deg[hi] - theta_deg[lo];
        const double frac = denom > 0.0 ? (x_deg - theta_deg[lo]) / denom : 0.0;
        return intensity[lo] + frac*(intensity[hi] - intensity[lo]);
    };

    std::vector<double> cdf(NGRID);
    double total = 0.0;
    for (int k = 0; k < NGRID; ++k) {
        const double w = std::max(0.0, interp_deg(grid[k])) * std::sin(grid[k]);
        total += w;
        cdf[k] = total;
    }
    if (total <= 0.0) {
        sample_lambertian(n, dir_x, dir_y, dir_z, rng, batch);
        return;
    }
    for (auto& c : cdf) c /= total;

    double ux, uy, uz, vx, vy, vz;
    build_basis(dir_x, dir_y, dir_z, ux, uy, uz, vx, vy, vz);
    std::uniform_real_distribution<double> uni(0.0, 1.0);
    for (int i = 0; i < n; ++i) {
        const double u_val = uni(rng);
        auto it = std::lower_bound(cdf.begin(), cdf.end(), u_val);
        int idx = (int)(it - cdf.begin());
        if (idx >= NGRID) idx = NGRID - 1;
        const double sample_theta = grid[idx];
        const double phi = uni(rng) * 2.0*PI;
        const double sin_t = std::sin(sample_theta);
        const double cos_t = std::cos(sample_theta);
        const double xl = sin_t * std::cos(phi);
        const double yl = sin_t * std::sin(phi);
        const double zl = cos_t;
        batch.dx[i] = xl*ux + yl*vx + zl*dir_x;
        batch.dy[i] = xl*uy + yl*vy + zl*dir_y;
        batch.dz[i] = xl*uz + yl*vz + zl*dir_z;
    }
}

void sample_lambertian_single(double nx, double ny, double nz,
                               std::mt19937_64& rng,
                               double& out_x, double& out_y, double& out_z)
{
    double nn = std::sqrt(nx*nx + ny*ny + nz*nz);
    if (nn < 1e-12) { nx = 0.0; ny = 0.0; nz = 1.0; nn = 1.0; }
    nx /= nn; ny /= nn; nz /= nn;

    double ux, uy, uz, vx, vy, vz;
    build_basis(nx, ny, nz, ux, uy, uz, vx, vy, vz);
    std::uniform_real_distribution<double> uni(0.0, 1.0);
    const double r = std::sqrt(uni(rng));
    const double phi = uni(rng) * 2.0*PI;
    const double xl = r * std::cos(phi);
    const double yl = r * std::sin(phi);
    const double zl = std::sqrt(std::max(0.0, 1.0 - xl*xl - yl*yl));
    out_x = xl*ux + yl*vx + zl*nx;
    out_y = xl*uy + yl*vy + zl*ny;
    out_z = xl*uz + yl*vz + zl*nz;
}

void reflect_specular(double dx, double dy, double dz,
                      double nx, double ny, double nz,
                      double& rdx, double& rdy, double& rdz)
{
    const double dot = dx*nx + dy*ny + dz*nz;
    rdx = dx - 2.0*dot*nx;
    rdy = dy - 2.0*dot*ny;
    rdz = dz - 2.0*dot*nz;
    const double norm = std::sqrt(rdx*rdx + rdy*rdy + rdz*rdz);
    if (norm > 1e-12) { rdx /= norm; rdy /= norm; rdz /= norm; }
}

void scatter_haze_single(double dx, double dy, double dz,
                          double half_angle_deg,
                          std::mt19937_64& rng,
                          double& out_x, double& out_y, double& out_z)
{
    if (half_angle_deg <= 0.0) {
        out_x = dx; out_y = dy; out_z = dz;
        return;
    }
    double nn = std::sqrt(dx*dx + dy*dy + dz*dz);
    if (nn < 1e-12) { out_x = dx; out_y = dy; out_z = dz; return; }
    dx /= nn; dy /= nn; dz /= nn;

    const double half_rad = half_angle_deg * PI / 180.0;
    const double cos_max = std::cos(half_rad);
    std::uniform_real_distribution<double> uni(0.0, 1.0);
    const double cos_t = cos_max + (1.0 - cos_max)*uni(rng);
    const double sin_t = std::sqrt(std::max(0.0, 1.0 - cos_t*cos_t));
    const double phi = uni(rng) * 2.0*PI;
    double ux, uy, uz, vx, vy, vz;
    build_basis(dx, dy, dz, ux, uy, uz, vx, vy, vz);
    out_x = sin_t*std::cos(phi)*ux + sin_t*std::sin(phi)*vx + cos_t*dx;
    out_y = sin_t*std::cos(phi)*uy + sin_t*std::sin(phi)*vy + cos_t*dy;
    out_z = sin_t*std::cos(phi)*uz + sin_t*std::sin(phi)*vz + cos_t*dz;
    const double norm = std::sqrt(out_x*out_x + out_y*out_y + out_z*out_z);
    if (norm > 1e-12) { out_x /= norm; out_y /= norm; out_z /= norm; }
}
