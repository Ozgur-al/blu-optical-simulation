#include "sampling.hpp"
#include <cmath>

void build_basis(double wx, double wy, double wz,
                 double& ux, double& uy, double& uz,
                 double& vx, double& vy, double& vz)
{
    (void)wx; (void)wy; (void)wz;
    // TODO: implement in Plan 02
    ux = 1.0; uy = 0.0; uz = 0.0;
    vx = 0.0; vy = 1.0; vz = 0.0;
}

void sample_isotropic(int n, std::mt19937_64& rng, RayBatch& batch) {
    (void)rng;
    // TODO: implement in Plan 02
    for (int i = 0; i < n; ++i) {
        batch.dx[i] = 0.0; batch.dy[i] = 0.0; batch.dz[i] = 1.0;
    }
}

void sample_lambertian(int n, double nx, double ny, double nz,
                       std::mt19937_64& rng, RayBatch& batch) {
    (void)rng;
    // TODO: implement in Plan 02
    for (int i = 0; i < n; ++i) {
        batch.dx[i] = nx; batch.dy[i] = ny; batch.dz[i] = nz;
    }
}

void sample_angular_distribution(int n,
                                  double dir_x, double dir_y, double dir_z,
                                  const std::vector<double>& theta_deg,
                                  const std::vector<double>& intensity,
                                  std::mt19937_64& rng, RayBatch& batch) {
    (void)theta_deg; (void)intensity;
    // TODO: implement in Plan 02
    sample_lambertian(n, dir_x, dir_y, dir_z, rng, batch);
}

void sample_lambertian_single(double nx, double ny, double nz,
                               std::mt19937_64& rng,
                               double& out_x, double& out_y, double& out_z) {
    (void)rng;
    out_x = nx; out_y = ny; out_z = nz;  // TODO: implement in Plan 02
}

void reflect_specular(double dx, double dy, double dz,
                      double nx, double ny, double nz,
                      double& rdx, double& rdy, double& rdz) {
    double dot = dx*nx + dy*ny + dz*nz;
    rdx = dx - 2.0*dot*nx;
    rdy = dy - 2.0*dot*ny;
    rdz = dz - 2.0*dot*nz;
}

void scatter_haze_single(double dx, double dy, double dz,
                          double half_angle_deg, std::mt19937_64& rng,
                          double& out_x, double& out_y, double& out_z) {
    (void)half_angle_deg; (void)rng;
    out_x = dx; out_y = dy; out_z = dz;  // TODO: implement in Plan 02
}
