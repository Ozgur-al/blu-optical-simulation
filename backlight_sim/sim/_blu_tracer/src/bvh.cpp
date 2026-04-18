#include "bvh.hpp"
#include "intersect.hpp"

std::vector<BVHNode> build_bvh(
    const std::vector<std::array<double,6>>& surface_aabbs)
{
    (void)surface_aabbs;
    // TODO: port from accel.py::build_bvh_flat in Plan 02
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
    // TODO: implement in Plan 02
    return {INF, -1};
}
