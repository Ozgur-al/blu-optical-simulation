#pragma once
#include "types.hpp"
#include <random>
#include <string>

// Vectorized unpolarized Fresnel reflectance for a single ray
double fresnel_unpolarized(double cos_theta_i, double n1, double n2);

// Refract using Snell's law; returns false if TIR
bool refract_snell(
    double dx, double dy, double dz,
    double on_x, double on_y, double on_z,   // normal into new medium
    double n1, double n2,
    double& rdx, double& rdy, double& rdz
);

// Apply material dispatch to one ray at a surface hit.
// Updates origins/directions/weights/alive in batch at index i.
void apply_material(
    int i,
    RayBatch& batch,
    const SceneMaterial& mat,
    double hit_x, double hit_y, double hit_z,
    double face_nx, double face_ny, double face_nz,
    double geom_eps,
    std::mt19937_64& rng
);
