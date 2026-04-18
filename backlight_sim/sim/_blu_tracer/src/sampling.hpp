#pragma once
#include "types.hpp"
#include <random>
#include <vector>

// Build orthonormal basis (u, v) perpendicular to w (unit vector)
void build_basis(double wx, double wy, double wz,
                 double& ux, double& uy, double& uz,
                 double& vx, double& vy, double& vz);

// Sample n isotropic unit directions
void sample_isotropic(int n, std::mt19937_64& rng,
                      RayBatch& batch);  // fills dx,dy,dz for rays 0..n-1

// Sample n Lambertian (cosine-weighted hemisphere) directions around normal
void sample_lambertian(int n,
                       double nx, double ny, double nz,
                       std::mt19937_64& rng,
                       RayBatch& batch);

// Sample n directions from 1D angular distribution I(theta) via CDF inversion
void sample_angular_distribution(int n,
                                 double dir_x, double dir_y, double dir_z,
                                 const std::vector<double>& theta_deg,
                                 const std::vector<double>& intensity,
                                 std::mt19937_64& rng,
                                 RayBatch& batch);

// Sample a single Lambertian direction around normal (used for material dispatch)
void sample_lambertian_single(double nx, double ny, double nz,
                               std::mt19937_64& rng,
                               double& out_x, double& out_y, double& out_z);

// Specular reflection: d - 2(d.n)n
void reflect_specular(double dx, double dy, double dz,
                      double nx, double ny, double nz,
                      double& rdx, double& rdy, double& rdz);

// Haze scatter: perturb direction within a cone (half_angle_deg)
void scatter_haze_single(double dx, double dy, double dz,
                          double half_angle_deg,
                          std::mt19937_64& rng,
                          double& out_x, double& out_y, double& out_z);
