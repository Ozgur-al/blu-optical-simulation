#include "intersect.hpp"
#include <cmath>
#include <limits>

double intersect_plane(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    double nx, double ny, double nz,
    double cx, double cy, double cz,
    double ux, double uy, double uz,
    double vx, double vy, double vz,
    double half_w, double half_h, double eps)
{
    (void)ox; (void)oy; (void)oz;
    (void)dx; (void)dy; (void)dz;
    (void)nx; (void)ny; (void)nz;
    (void)cx; (void)cy; (void)cz;
    (void)ux; (void)uy; (void)uz;
    (void)vx; (void)vy; (void)vz;
    (void)half_w; (void)half_h; (void)eps;
    return INF;  // TODO: implement in Plan 02
}

double intersect_disc(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    double cx, double cy, double cz,
    double nx, double ny, double nz,
    double radius, double eps)
{
    (void)ox; (void)oy; (void)oz;
    (void)dx; (void)dy; (void)dz;
    (void)cx; (void)cy; (void)cz;
    (void)nx; (void)ny; (void)nz;
    (void)radius; (void)eps;
    return INF;  // TODO: implement in Plan 02
}

double intersect_cylinder_side(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    double cx, double cy, double cz,
    double ax, double ay, double az,
    double radius, double half_length, double eps)
{
    (void)ox; (void)oy; (void)oz;
    (void)dx; (void)dy; (void)dz;
    (void)cx; (void)cy; (void)cz;
    (void)ax; (void)ay; (void)az;
    (void)radius; (void)half_length; (void)eps;
    return INF;  // TODO: implement in Plan 02
}

double intersect_sphere(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    double sx, double sy, double sz,
    double radius, double eps)
{
    (void)ox; (void)oy; (void)oz;
    (void)dx; (void)dy; (void)dz;
    (void)sx; (void)sy; (void)sz;
    (void)radius; (void)eps;
    return INF;  // TODO: implement in Plan 02
}

double intersect_prism_cap(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    const ScenePrismCap& cap, double eps)
{
    (void)ox; (void)oy; (void)oz;
    (void)dx; (void)dy; (void)dz;
    (void)cap; (void)eps;
    return INF;  // TODO: implement in Plan 02
}

bool intersect_aabb(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    double xmin, double xmax,
    double ymin, double ymax,
    double zmin, double zmax)
{
    (void)ox; (void)oy; (void)oz;
    (void)dx; (void)dy; (void)dz;
    (void)xmin; (void)xmax;
    (void)ymin; (void)ymax;
    (void)zmin; (void)zmax;
    return true;  // TODO: implement in Plan 02
}
