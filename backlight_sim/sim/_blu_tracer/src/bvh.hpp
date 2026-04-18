#pragma once
#include "types.hpp"
#include <vector>
#include <utility>

// Build a flat BVH from surface AABBs (ported from accel.py::build_bvh_flat)
// surface_aabbs: (N, 6) layout [xmin, xmax, ymin, ymax, zmin, zmax]
std::vector<BVHNode> build_bvh(
    const std::vector<std::array<double,6>>& surface_aabbs
);

// Traverse BVH for a single ray; returns (t, surface_index) or (INF, -1)
std::pair<double, int> traverse_bvh(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    const std::vector<BVHNode>& bvh,
    const std::vector<ScenePlane>& planes
);
