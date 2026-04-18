#pragma once
#include "types.hpp"

// Plane (Rectangle / DetectorSurface / SolidBox face)
double intersect_plane(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    double nx, double ny, double nz,
    double cx, double cy, double cz,
    double ux, double uy, double uz,
    double vx, double vy, double vz,
    double half_w, double half_h,
    double eps
);

// Disc (CylinderCap)
double intersect_disc(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    double cx, double cy, double cz,
    double nx, double ny, double nz,
    double radius, double eps
);

// Cylinder side surface (CylinderSide)
double intersect_cylinder_side(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    double cx, double cy, double cz,
    double ax, double ay, double az,
    double radius, double half_length, double eps
);

// Sphere (SphereDetector)
double intersect_sphere(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    double sx, double sy, double sz,
    double radius, double eps
);

// Prism cap (polygon containment test)
double intersect_prism_cap(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    const ScenePrismCap& cap, double eps
);

// AABB slab test (for BVH broad-phase)
bool intersect_aabb(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    double xmin, double xmax,
    double ymin, double ymax,
    double zmin, double zmax
);
