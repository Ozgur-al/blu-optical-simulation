#pragma once
#include <vector>
#include <array>
#include <string>
#include <limits>
#include <cmath>

constexpr double EPSILON = 1e-6;
constexpr double INF = std::numeric_limits<double>::infinity();
constexpr int N_STACK_MAX = 8;

// Struct-of-Arrays ray batch for the hot intersection loop
struct RayBatch {
    std::vector<double> ox, oy, oz;    // origins (SoA)
    std::vector<double> dx, dy, dz;    // directions (SoA)
    std::vector<double> weights;
    std::vector<bool>   alive;
    std::vector<double> current_n;     // per-ray refractive index (starts 1.0)
    std::vector<std::array<double, N_STACK_MAX>> n_stack;  // refractive index stack
    std::vector<int>    n_depth;       // current stack depth per ray
    int n;
};

// A flat surface (Rectangle, DetectorSurface, SolidBox face)
struct ScenePlane {
    double cx, cy, cz;          // center
    double nx, ny, nz;          // normal (unit)
    double ux, uy, uz;          // u_axis (unit)
    double vx, vy, vz;          // v_axis (unit)
    double half_w, half_h;      // half extents
    std::string name;
    std::string material_name;
    std::string optical_properties_name;
    double refractive_index;    // for solid body faces
    double geom_eps;            // per-body epsilon
    int type;  // 0=surface, 1=detector, 3=solid_box_face
    int index; // index into its own list
};

// Cylinder cap (disc)
struct SceneCylinderCap {
    double cx, cy, cz;    // center
    double nx, ny, nz;    // normal (unit)
    double radius;
    std::string name;
    std::string material_name;
    double refractive_index;
    double geom_eps;
    int index;
};

// Cylinder side surface
struct SceneCylinderSide {
    double cx, cy, cz;    // center
    double ax, ay, az;    // axis (unit)
    double radius;
    double half_length;
    std::string name;
    std::string material_name;
    double refractive_index;
    double geom_eps;
    int index;
};

// Prism cap (polygon)
struct ScenePrismCap {
    double cx, cy, cz;    // center
    double nx, ny, nz;    // normal (unit)
    double ux, uy, uz;    // u_axis (unit)
    double vx, vy, vz;    // v_axis (unit)
    int n_sides;
    std::vector<std::array<double,2>> vertices_2d;    // polygon vertices in local u/v
    std::vector<std::array<double,2>> edge_normals_2d; // outward edge normals
    std::string name;
    std::string material_name;
    double refractive_index;
    double geom_eps;
    int index;
};

// Rectangle prism side face (same as ScenePlane but index into prism_faces)
struct ScenePrismSideFace {
    double cx, cy, cz;
    double nx, ny, nz;
    double ux, uy, uz;
    double vx, vy, vz;
    double half_w, half_h;
    std::string name;
    std::string material_name;
    double refractive_index;
    double geom_eps;
    int index;
};

// Sphere detector
struct SceneSphereDetector {
    double cx, cy, cz;
    double radius;
    std::string name;
    int n_phi, n_theta;
    std::string mode;  // "near_field" or "far_field"
    int index;
};

// Material optical properties
struct SceneMaterial {
    std::string surface_type;  // "reflector", "absorber", "diffuser"
    double reflectance;
    double transmittance;
    bool is_diffuse;
    double haze;           // forward-scatter half-angle degrees (0 = no haze)
};

// Angular distribution profile (for sampling)
struct AngularProfile {
    std::string name;
    std::vector<double> theta_deg;
    std::vector<double> intensity;
};

// Source description (deserialized from project_dict)
struct SceneSource {
    std::string name;
    double px, py, pz;          // position
    double dir_x, dir_y, dir_z; // direction (unit)
    double effective_flux;
    std::string distribution;   // "isotropic", "lambertian", or profile name
    bool enabled;
};

// BVH flat node (ported from accel.py)
struct BVHNode {
    double xmin, xmax, ymin, ymax, zmin, zmax;  // AABB
    int left_child;   // index of left child, or -1 if leaf
    int right_child;  // index of right child, or -1 if leaf
    int surf_start;   // leaf: start index in sorted surface list
    int surf_end;     // leaf: end index (exclusive)
};
