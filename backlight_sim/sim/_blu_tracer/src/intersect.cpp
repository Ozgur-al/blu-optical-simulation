#include "intersect.hpp"
#include <cmath>
#include <algorithm>
#include <limits>

// ---------------------------------------------------------------------------
// Plane (Rectangle / DetectorSurface / SolidBox face)
// Ported from accel.py::intersect_plane_jit
// ---------------------------------------------------------------------------
double intersect_plane(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    double nx, double ny, double nz,
    double cx, double cy, double cz,
    double ux, double uy, double uz,
    double vx, double vy, double vz,
    double half_w, double half_h, double eps)
{
    const double denom = dx*nx + dy*ny + dz*nz;
    if (std::abs(denom) <= 1e-12) return INF;
    const double d_plane = nx*cx + ny*cy + nz*cz;
    const double t = (d_plane - (ox*nx + oy*ny + oz*nz)) / denom;
    if (t <= eps) return INF;
    const double hx = ox + t*dx - cx;
    const double hy = oy + t*dy - cy;
    const double hz = oz + t*dz - cz;
    const double u_coord = hx*ux + hy*uy + hz*uz;
    const double v_coord = hx*vx + hy*vy + hz*vz;
    if (std::abs(u_coord) <= half_w && std::abs(v_coord) <= half_h) return t;
    return INF;
}

// ---------------------------------------------------------------------------
// Disc (CylinderCap) — plane hit + radial clip
// ---------------------------------------------------------------------------
double intersect_disc(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    double cx, double cy, double cz,
    double nx, double ny, double nz,
    double radius, double eps)
{
    const double denom = dx*nx + dy*ny + dz*nz;
    if (std::abs(denom) <= 1e-12) return INF;
    const double d_plane = nx*cx + ny*cy + nz*cz;
    const double t = (d_plane - (ox*nx + oy*ny + oz*nz)) / denom;
    if (t <= eps) return INF;
    const double hx = ox + t*dx - cx;
    const double hy = oy + t*dy - cy;
    const double hz = oz + t*dz - cz;
    const double r2 = hx*hx + hy*hy + hz*hz;
    if (r2 <= radius*radius) return t;
    return INF;
}

// ---------------------------------------------------------------------------
// Cylinder side (CylinderSide) — quadratic formula, axis-bounded
// Reference: PBR Book 3ed, Cylinders chapter
// ---------------------------------------------------------------------------
double intersect_cylinder_side(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    double cx, double cy, double cz,
    double ax, double ay, double az,
    double radius, double half_length, double eps)
{
    // Project ray onto plane perpendicular to cylinder axis
    const double ocx = ox - cx;
    const double ocy = oy - cy;
    const double ocz = oz - cz;
    const double d_dot_a = dx*ax + dy*ay + dz*az;
    const double oc_dot_a = ocx*ax + ocy*ay + ocz*az;
    const double dpx = dx - d_dot_a*ax;
    const double dpy = dy - d_dot_a*ay;
    const double dpz = dz - d_dot_a*az;
    const double opx = ocx - oc_dot_a*ax;
    const double opy = ocy - oc_dot_a*ay;
    const double opz = ocz - oc_dot_a*az;
    const double a = dpx*dpx + dpy*dpy + dpz*dpz;
    if (a < 1e-14) return INF;  // ray parallel to axis
    const double b = 2.0*(dpx*opx + dpy*opy + dpz*opz);
    const double c = opx*opx + opy*opy + opz*opz - radius*radius;
    const double disc = b*b - 4.0*a*c;
    if (disc < 0.0) return INF;
    const double sqrt_disc = std::sqrt(disc);
    const double inv2a = 1.0 / (2.0*a);
    const double t1 = (-b - sqrt_disc)*inv2a;
    const double t2 = (-b + sqrt_disc)*inv2a;
    // Pick smallest positive t that satisfies axis bounds
    const double candidates[2] = {t1, t2};
    for (int k = 0; k < 2; ++k) {
        const double t_cand = candidates[k];
        if (t_cand <= eps) continue;
        const double hx = ox + t_cand*dx;
        const double hy = oy + t_cand*dy;
        const double hz = oz + t_cand*dz;
        const double proj = (hx-cx)*ax + (hy-cy)*ay + (hz-cz)*az;
        if (std::abs(proj) <= half_length) return t_cand;
    }
    return INF;
}

// ---------------------------------------------------------------------------
// Sphere (SphereDetector)
// Ported from accel.py::intersect_sphere_jit
// ---------------------------------------------------------------------------
double intersect_sphere(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    double sx, double sy, double sz,
    double radius, double eps)
{
    const double lx = ox - sx;
    const double ly = oy - sy;
    const double lz = oz - sz;
    const double a = dx*dx + dy*dy + dz*dz;
    const double b = 2.0*(dx*lx + dy*ly + dz*lz);
    const double c = lx*lx + ly*ly + lz*lz - radius*radius;
    const double disc = b*b - 4.0*a*c;
    if (disc < 0.0) return INF;
    const double sqrt_disc = std::sqrt(disc);
    const double inv2a = 1.0/(2.0*a);
    const double t1 = (-b - sqrt_disc)*inv2a;
    const double t2 = (-b + sqrt_disc)*inv2a;
    if (t1 > eps) return t1;
    if (t2 > eps) return t2;
    return INF;
}

// ---------------------------------------------------------------------------
// Prism cap (polygon containment via half-plane test)
// ---------------------------------------------------------------------------
double intersect_prism_cap(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    const ScenePrismCap& cap, double eps)
{
    const double denom = dx*cap.nx + dy*cap.ny + dz*cap.nz;
    if (std::abs(denom) <= 1e-12) return INF;
    const double d_plane = cap.nx*cap.cx + cap.ny*cap.cy + cap.nz*cap.cz;
    const double t = (d_plane - (ox*cap.nx + oy*cap.ny + oz*cap.nz)) / denom;
    if (t <= eps) return INF;
    const double hx = ox + t*dx - cap.cx;
    const double hy = oy + t*dy - cap.cy;
    const double hz = oz + t*dz - cap.cz;
    const double u_c = hx*cap.ux + hy*cap.uy + hz*cap.uz;
    const double v_c = hx*cap.vx + hy*cap.vy + hz*cap.vz;
    // Polygon containment via outward-half-plane test per edge
    for (int e = 0; e < cap.n_sides; ++e) {
        const double vx2d = cap.vertices_2d[e][0];
        const double vy2d = cap.vertices_2d[e][1];
        const double enx = cap.edge_normals_2d[e][0];
        const double eny = cap.edge_normals_2d[e][1];
        const double d = (u_c - vx2d)*enx + (v_c - vy2d)*eny;
        if (d > 0.0) return INF;  // outside this edge
    }
    return t;
}

// ---------------------------------------------------------------------------
// AABB slab test (for BVH broad-phase filtering)
// ---------------------------------------------------------------------------
bool intersect_aabb(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    double xmin, double xmax,
    double ymin, double ymax,
    double zmin, double zmax)
{
    auto safe_inv = [](double d) {
        return std::abs(d) > 1e-15 ? 1.0/d : (d >= 0 ? 1e15 : -1e15);
    };
    const double inv_dx = safe_inv(dx);
    const double inv_dy = safe_inv(dy);
    const double inv_dz = safe_inv(dz);
    const double tx0 = (xmin - ox)*inv_dx, tx1 = (xmax - ox)*inv_dx;
    const double ty0 = (ymin - oy)*inv_dy, ty1 = (ymax - oy)*inv_dy;
    const double tz0 = (zmin - oz)*inv_dz, tz1 = (zmax - oz)*inv_dz;
    const double tenter = std::max({std::min(tx0,tx1), std::min(ty0,ty1), std::min(tz0,tz1)});
    const double texit  = std::min({std::max(tx0,tx1), std::max(ty0,ty1), std::max(tz0,tz1)});
    return texit >= tenter && texit > EPSILON;
}
