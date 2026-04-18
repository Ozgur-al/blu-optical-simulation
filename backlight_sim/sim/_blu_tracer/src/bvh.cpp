#include "bvh.hpp"
#include "intersect.hpp"

// BVH is disabled in Wave 2: brute-force intersection is used for correctness
// validation. Threshold is set to 9999 in the bounce loop so these stubs are
// never invoked. Full BVH port (accel.py::build_bvh_flat/traverse_bvh_batch)
// is deferred to a future cleanup phase per CONTEXT.md.

std::vector<BVHNode> build_bvh(
    const std::vector<std::array<double,6>>& surface_aabbs)
{
    (void)surface_aabbs;
    return {};
}

std::pair<double, int> traverse_bvh(
    double ox, double oy, double oz,
    double dx, double dy, double dz,
    const std::vector<BVHNode>& bvh,
    const std::vector<ScenePlane>& planes)
{
    (void)ox; (void)oy; (void)oz;
    (void)dx; (void)dy; (void)dz;
    (void)bvh; (void)planes;
    return {INF, -1};
}
