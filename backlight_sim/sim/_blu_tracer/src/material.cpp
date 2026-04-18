#include "material.hpp"
#include "sampling.hpp"
#include <cmath>

double fresnel_unpolarized(double cos_theta_i, double n1, double n2) {
    (void)cos_theta_i; (void)n1; (void)n2;
    // TODO: implement full Fresnel in Plan 02
    return 0.0;
}

bool refract_snell(
    double dx, double dy, double dz,
    double on_x, double on_y, double on_z,
    double n1, double n2,
    double& rdx, double& rdy, double& rdz)
{
    (void)on_x; (void)on_y; (void)on_z;
    (void)n1; (void)n2;
    // TODO: implement in Plan 02
    rdx = dx; rdy = dy; rdz = dz;
    return true;
}

void apply_material(
    int i, RayBatch& batch,
    const SceneMaterial& mat,
    double hit_x, double hit_y, double hit_z,
    double face_nx, double face_ny, double face_nz,
    double geom_eps, std::mt19937_64& rng)
{
    (void)hit_x; (void)hit_y; (void)hit_z;
    (void)face_nx; (void)face_ny; (void)face_nz;
    (void)geom_eps; (void)rng;
    // TODO: implement full material dispatch in Plan 02
    if (mat.surface_type == "absorber") {
        batch.alive[i] = false;
    }
}
