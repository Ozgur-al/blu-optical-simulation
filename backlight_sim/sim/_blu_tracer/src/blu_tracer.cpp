#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "types.hpp"
#include "intersect.hpp"
#include "sampling.hpp"
#include "material.hpp"
#include "bvh.hpp"

#include <random>
#include <vector>
#include <array>
#include <string>
#include <stdexcept>
#include <cmath>
#include <cstring>
#include <unordered_map>
#include <utility>
#include <algorithm>

namespace py = pybind11;

// ---------------------------------------------------------------------------
// Deserialization helpers
// ---------------------------------------------------------------------------

static std::vector<double> list_to_vec(py::object obj) {
    auto lst = obj.cast<py::list>();
    std::vector<double> out;
    out.reserve(py::len(lst));
    for (auto& item : lst) out.push_back(item.cast<double>());
    return out;
}

static std::array<double,3> list_to_arr3(py::object obj) {
    auto lst = obj.cast<py::list>();
    return {lst[0].cast<double>(), lst[1].cast<double>(), lst[2].cast<double>()};
}

static SceneMaterial parse_material(const py::dict& d) {
    SceneMaterial m;
    m.surface_type  = d.contains("surface_type") ? d["surface_type"].cast<std::string>()
                                                 : std::string("absorber");
    m.reflectance   = d.contains("reflectance")  ? d["reflectance"].cast<double>()  : 0.0;
    m.transmittance = d.contains("transmittance")? d["transmittance"].cast<double>(): 0.0;
    m.is_diffuse    = d.contains("is_diffuse")   ? d["is_diffuse"].cast<bool>()     : true;
    m.haze          = d.contains("haze")         ? d["haze"].cast<double>()         : 0.0;
    return m;
}

// ---------------------------------------------------------------------------
// Grid accumulators
// ---------------------------------------------------------------------------

struct GridAccum {
    std::vector<double> grid;  // (ny * nx) row-major
    int nx;
    int ny;
    long long hits;
    double flux;
};

struct SphGridAccum {
    std::vector<double> grid;  // (n_theta * n_phi) row-major
    int n_phi;
    int n_theta;
    long long hits;
    double flux;
};

// Mirror of accel.py::accumulate_grid_jit.
static void accumulate_grid(
    GridAccum& accum,
    double hit_x, double hit_y, double hit_z,
    double cx, double cy, double cz,
    double ux, double uy, double uz,
    double vx, double vy, double vz,
    double half_w, double half_h,
    double weight)
{
    const double lx = hit_x - cx;
    const double ly = hit_y - cy;
    const double lz = hit_z - cz;
    const double u_c = lx*ux + ly*uy + lz*uz;
    const double v_c = lx*vx + ly*vy + lz*vz;
    int ix = (int)std::floor((u_c / (2.0*half_w) + 0.5) * accum.nx);
    int iy = (int)std::floor((v_c / (2.0*half_h) + 0.5) * accum.ny);
    if (ix < 0) ix = 0; else if (ix >= accum.nx) ix = accum.nx - 1;
    if (iy < 0) iy = 0; else if (iy >= accum.ny) iy = accum.ny - 1;
    accum.grid[(size_t)iy * (size_t)accum.nx + (size_t)ix] += weight;
    accum.hits += 1;
    accum.flux += weight;
}

// Mirror of accel.py::accumulate_sphere_jit (near-field spherical bins).
static void accumulate_sphere(
    SphGridAccum& accum,
    double hx, double hy, double hz,
    double cx, double cy, double cz,
    double weight)
{
    const double dx = hx - cx;
    const double dy = hy - cy;
    const double dz = hz - cz;
    const double norm = std::sqrt(dx*dx + dy*dy + dz*dz);
    if (norm < 1e-12) return;
    constexpr double PI = 3.14159265358979323846;
    double phi = std::atan2(dy, dx);
    if (phi < 0.0) phi += 2.0*PI;
    const double cos_t = std::max(-1.0, std::min(1.0, dz/norm));
    const double theta = std::acos(cos_t);
    int i_phi   = (int)std::floor(phi   / (2.0*PI) * accum.n_phi);
    int i_theta = (int)std::floor(theta /      PI  * accum.n_theta);
    if (i_phi   < 0) i_phi   = 0; else if (i_phi   >= accum.n_phi)   i_phi   = accum.n_phi   - 1;
    if (i_theta < 0) i_theta = 0; else if (i_theta >= accum.n_theta) i_theta = accum.n_theta - 1;
    accum.grid[(size_t)i_theta * (size_t)accum.n_phi + (size_t)i_phi] += weight;
    accum.hits += 1;
    accum.flux += weight;
}

// ---------------------------------------------------------------------------
// Real Monte Carlo bounce loop.
// Replaces the Wave 1 run_stub_bounce; closely mirrors tracer.py::_trace_single_source.
// Brute-force intersection over all scene surfaces (BVH disabled for Wave 2).
// ---------------------------------------------------------------------------

static py::dict run_bounce_loop(
    const SceneSource& source,
    const std::vector<ScenePlane>& surfaces,
    const std::vector<ScenePlane>& detector_planes,
    const std::vector<std::array<int,2>>& detector_resolutions,
    const std::vector<SceneSphereDetector>& sphere_dets,
    const std::unordered_map<std::string, SceneMaterial>& materials,
    const std::unordered_map<std::string, SceneMaterial>& optical_props,
    const std::unordered_map<std::string, AngularProfile>& ang_dists,
    int n_rays, int max_bounces, double energy_threshold,
    uint64_t seed)
{
    // Input validation (T-02-04 mitigation)
    if (n_rays <= 0) {
        throw std::invalid_argument("n_rays must be positive");
    }
    if (max_bounces < 0) {
        throw std::invalid_argument("max_bounces must be non-negative");
    }

    std::mt19937_64 rng(seed);

    // --- Detector accumulators ---
    std::vector<GridAccum> det_accums(detector_planes.size());
    for (size_t d = 0; d < detector_planes.size(); ++d) {
        int nx = detector_resolutions[d][0]; if (nx <= 0) nx = 1;
        int ny = detector_resolutions[d][1]; if (ny <= 0) ny = 1;
        det_accums[d].nx = nx;
        det_accums[d].ny = ny;
        det_accums[d].grid.assign((size_t)nx * (size_t)ny, 0.0);
        det_accums[d].hits = 0;
        det_accums[d].flux = 0.0;
    }

    std::vector<SphGridAccum> sph_accums(sphere_dets.size());
    for (size_t s = 0; s < sphere_dets.size(); ++s) {
        int n_phi   = sphere_dets[s].n_phi   > 0 ? sphere_dets[s].n_phi   : 1;
        int n_theta = sphere_dets[s].n_theta > 0 ? sphere_dets[s].n_theta : 1;
        sph_accums[s].n_phi = n_phi;
        sph_accums[s].n_theta = n_theta;
        sph_accums[s].grid.assign((size_t)n_phi * (size_t)n_theta, 0.0);
        sph_accums[s].hits = 0;
        sph_accums[s].flux = 0.0;
    }

    double escaped_flux = 0.0;
    const double weight_per_ray = source.effective_flux / (double)n_rays;

    // --- Ray batch ---
    RayBatch batch;
    batch.n = n_rays;
    batch.ox.assign(n_rays, source.px);
    batch.oy.assign(n_rays, source.py);
    batch.oz.assign(n_rays, source.pz);
    batch.dx.assign(n_rays, 0.0);
    batch.dy.assign(n_rays, 0.0);
    batch.dz.assign(n_rays, 0.0);
    batch.weights.assign(n_rays, weight_per_ray);
    batch.alive.assign(n_rays, true);
    batch.current_n.assign(n_rays, 1.0);
    batch.n_stack.assign(n_rays, std::array<double, N_STACK_MAX>{});
    for (auto& s : batch.n_stack) s.fill(1.0);
    batch.n_depth.assign(n_rays, 0);

    // --- Emit ---
    if (source.distribution == "lambertian") {
        sample_lambertian(n_rays, source.dir_x, source.dir_y, source.dir_z, rng, batch);
    } else if (source.distribution == "isotropic") {
        sample_isotropic(n_rays, rng, batch);
    } else {
        auto it = ang_dists.find(source.distribution);
        if (it != ang_dists.end()) {
            sample_angular_distribution(
                n_rays, source.dir_x, source.dir_y, source.dir_z,
                it->second.theta_deg, it->second.intensity, rng, batch);
        } else {
            // Unknown profile — fall back to Lambertian (matches Python)
            sample_lambertian(n_rays, source.dir_x, source.dir_y, source.dir_z, rng, batch);
        }
    }

    // --- Bounce loop ---
    std::vector<int> active_idx;
    active_idx.reserve(n_rays);

    for (int bounce = 0; bounce < max_bounces; ++bounce) {
        active_idx.clear();
        for (int i = 0; i < n_rays; ++i) {
            if (batch.alive[i]) active_idx.push_back(i);
        }
        if (active_idx.empty()) break;

        const int n_active = (int)active_idx.size();
        std::vector<double> best_t(n_active, INF);
        // 0 = surface, 1 = detector plane, 2 = sphere detector
        std::vector<int> best_type(n_active, -1);
        std::vector<int> best_obj(n_active, -1);

        // --- Intersect surfaces (brute force) ---
        for (size_t si = 0; si < surfaces.size(); ++si) {
            const auto& surf = surfaces[si];
            for (int ri = 0; ri < n_active; ++ri) {
                const int i = active_idx[ri];
                const double t = intersect_plane(
                    batch.ox[i], batch.oy[i], batch.oz[i],
                    batch.dx[i], batch.dy[i], batch.dz[i],
                    surf.nx, surf.ny, surf.nz,
                    surf.cx, surf.cy, surf.cz,
                    surf.ux, surf.uy, surf.uz,
                    surf.vx, surf.vy, surf.vz,
                    surf.half_w, surf.half_h, EPSILON);
                if (t < best_t[ri]) {
                    best_t[ri] = t; best_type[ri] = 0; best_obj[ri] = (int)si;
                }
            }
        }

        // --- Intersect detector planes ---
        for (size_t di = 0; di < detector_planes.size(); ++di) {
            const auto& det = detector_planes[di];
            for (int ri = 0; ri < n_active; ++ri) {
                const int i = active_idx[ri];
                const double t = intersect_plane(
                    batch.ox[i], batch.oy[i], batch.oz[i],
                    batch.dx[i], batch.dy[i], batch.dz[i],
                    det.nx, det.ny, det.nz,
                    det.cx, det.cy, det.cz,
                    det.ux, det.uy, det.uz,
                    det.vx, det.vy, det.vz,
                    det.half_w, det.half_h, EPSILON);
                if (t < best_t[ri]) {
                    best_t[ri] = t; best_type[ri] = 1; best_obj[ri] = (int)di;
                }
            }
        }

        // --- Intersect sphere detectors ---
        for (size_t sdi = 0; sdi < sphere_dets.size(); ++sdi) {
            const auto& sd = sphere_dets[sdi];
            for (int ri = 0; ri < n_active; ++ri) {
                const int i = active_idx[ri];
                const double t = intersect_sphere(
                    batch.ox[i], batch.oy[i], batch.oz[i],
                    batch.dx[i], batch.dy[i], batch.dz[i],
                    sd.cx, sd.cy, sd.cz, sd.radius, EPSILON);
                if (t < best_t[ri]) {
                    best_t[ri] = t; best_type[ri] = 2; best_obj[ri] = (int)sdi;
                }
            }
        }

        // --- Process hits ---
        for (int ri = 0; ri < n_active; ++ri) {
            const int i = active_idx[ri];
            if (best_t[ri] == INF) {
                escaped_flux += batch.weights[i];
                batch.alive[i] = false;
                continue;
            }
            const double t = best_t[ri];
            const double hit_x = batch.ox[i] + t*batch.dx[i];
            const double hit_y = batch.oy[i] + t*batch.dy[i];
            const double hit_z = batch.oz[i] + t*batch.dz[i];
            const int type = best_type[ri];
            const int obj  = best_obj[ri];

            if (type == 1) {
                // Detector plane hit — accumulate, pass through.
                const auto& det = detector_planes[obj];
                accumulate_grid(det_accums[obj],
                    hit_x, hit_y, hit_z,
                    det.cx, det.cy, det.cz,
                    det.ux, det.uy, det.uz,
                    det.vx, det.vy, det.vz,
                    det.half_w, det.half_h,
                    batch.weights[i]);
                // Advance origin past detector; ray dies (matches Python semantics
                // where detector hits terminate the ray — see tracer.py _bounce_detectors).
                batch.alive[i] = false;
                continue;
            }

            if (type == 2) {
                // Sphere detector hit — accumulate, terminate.
                const auto& sd = sphere_dets[obj];
                accumulate_sphere(sph_accums[obj],
                    hit_x, hit_y, hit_z,
                    sd.cx, sd.cy, sd.cz,
                    batch.weights[i]);
                batch.alive[i] = false;
                continue;
            }

            // Surface hit — material dispatch.
            const auto& surf = surfaces[obj];
            const SceneMaterial* mat_ptr = nullptr;
            if (!surf.optical_properties_name.empty()) {
                auto it = optical_props.find(surf.optical_properties_name);
                if (it != optical_props.end()) mat_ptr = &it->second;
            }
            if (!mat_ptr) {
                auto it = materials.find(surf.material_name);
                if (it != materials.end()) mat_ptr = &it->second;
            }
            if (!mat_ptr) {
                // No material found — absorb.
                batch.alive[i] = false;
                continue;
            }
            apply_material(i, batch, *mat_ptr,
                hit_x, hit_y, hit_z,
                surf.nx, surf.ny, surf.nz,
                surf.geom_eps, rng);
        }

        // Energy threshold kill
        for (int i = 0; i < n_rays; ++i) {
            if (batch.alive[i] && batch.weights[i] < energy_threshold) {
                batch.alive[i] = false;
            }
        }
    }

    // Any rays still alive at end of bounce budget didn't terminate — count as escaped.
    for (int i = 0; i < n_rays; ++i) {
        if (batch.alive[i]) {
            escaped_flux += batch.weights[i];
            batch.alive[i] = false;
        }
    }

    // --- Build return dict ---
    py::dict grids;
    for (size_t d = 0; d < detector_planes.size(); ++d) {
        const auto& accum = det_accums[d];
        std::vector<py::ssize_t> shape = {(py::ssize_t)accum.ny, (py::ssize_t)accum.nx};
        py::array_t<double> arr(shape);
        std::memcpy(arr.mutable_data(), accum.grid.data(),
                    sizeof(double) * accum.grid.size());
        py::dict entry;
        entry["grid"] = arr;
        entry["hits"] = py::int_(accum.hits);
        entry["flux"] = py::float_(accum.flux);
        grids[detector_planes[d].name.c_str()] = entry;
    }

    py::dict sph_grids;
    for (size_t s = 0; s < sphere_dets.size(); ++s) {
        const auto& accum = sph_accums[s];
        std::vector<py::ssize_t> shape = {(py::ssize_t)accum.n_theta, (py::ssize_t)accum.n_phi};
        py::array_t<double> arr(shape);
        std::memcpy(arr.mutable_data(), accum.grid.data(),
                    sizeof(double) * accum.grid.size());
        py::dict entry;
        entry["grid"] = arr;
        entry["hits"] = py::int_(accum.hits);
        entry["flux"] = py::float_(accum.flux);
        sph_grids[sphere_dets[s].name.c_str()] = entry;
    }

    py::dict result;
    result["grids"] = grids;
    result["spectral_grids"] = py::dict();
    result["escaped"] = py::float_(escaped_flux);
    result["sb_stats"] = py::dict();
    result["sph_grids"] = sph_grids;
    return result;
}

// ---------------------------------------------------------------------------
// Main entry point: trace_source(project_dict, source_name, seed) -> dict
// ---------------------------------------------------------------------------

py::dict trace_source(py::dict project_dict, std::string source_name, int seed) {
    // --- Settings ---
    auto settings = project_dict["settings"].cast<py::dict>();
    const int n_rays = settings["rays_per_source"].cast<int>();
    const int max_bounces = settings["max_bounces"].cast<int>();
    const double energy_threshold = settings["energy_threshold"].cast<double>();

    if (n_rays <= 0) {
        throw std::invalid_argument("settings.rays_per_source must be positive");
    }

    // --- Locate source ---
    SceneSource source;
    bool found = false;
    for (auto& src_item : project_dict["sources"].cast<py::list>()) {
        auto src = src_item.cast<py::dict>();
        if (!src["enabled"].cast<bool>()) continue;
        if (src["name"].cast<std::string>() != source_name) continue;
        auto pos = list_to_arr3(src["position"]);
        auto dir = list_to_arr3(src["direction"]);
        source.name = source_name;
        source.px = pos[0]; source.py = pos[1]; source.pz = pos[2];
        source.dir_x = dir[0]; source.dir_y = dir[1]; source.dir_z = dir[2];
        source.effective_flux = src["effective_flux"].cast<double>();
        source.distribution = src["distribution"].cast<std::string>();
        source.enabled = true;
        found = true;
        break;
    }
    if (!found) {
        throw std::runtime_error(
            "Source '" + source_name +
            "' not found or not enabled in project_dict");
    }

    // --- Surfaces ---
    std::vector<ScenePlane> surfaces;
    for (auto& surf_item : project_dict["surfaces"].cast<py::list>()) {
        auto surf = surf_item.cast<py::dict>();
        ScenePlane p;
        auto c = list_to_arr3(surf["center"]);
        auto n = list_to_arr3(surf["normal"]);
        auto u = list_to_arr3(surf["u_axis"]);
        auto v = list_to_arr3(surf["v_axis"]);
        auto sz = surf["size"].cast<py::list>();
        p.cx=c[0]; p.cy=c[1]; p.cz=c[2];
        p.nx=n[0]; p.ny=n[1]; p.nz=n[2];
        p.ux=u[0]; p.uy=u[1]; p.uz=u[2];
        p.vx=v[0]; p.vy=v[1]; p.vz=v[2];
        p.half_w = sz[0].cast<double>() / 2.0;
        p.half_h = sz[1].cast<double>() / 2.0;
        p.name = surf["name"].cast<std::string>();
        p.material_name = surf["material_name"].cast<std::string>();
        p.optical_properties_name = surf.contains("optical_properties_name")
            ? surf["optical_properties_name"].cast<std::string>() : "";
        p.refractive_index = 1.0;
        p.geom_eps = EPSILON;
        p.type = 0;
        p.index = (int)surfaces.size();
        surfaces.push_back(p);
    }

    // --- Detectors ---
    std::vector<ScenePlane> detectors;
    std::vector<std::array<int,2>> detector_resolutions;
    for (auto& det_item : project_dict["detectors"].cast<py::list>()) {
        auto det = det_item.cast<py::dict>();
        ScenePlane p;
        auto c = list_to_arr3(det["center"]);
        auto n = list_to_arr3(det["normal"]);
        auto u = list_to_arr3(det["u_axis"]);
        auto v = list_to_arr3(det["v_axis"]);
        auto sz = det["size"].cast<py::list>();
        p.cx=c[0]; p.cy=c[1]; p.cz=c[2];
        p.nx=n[0]; p.ny=n[1]; p.nz=n[2];
        p.ux=u[0]; p.uy=u[1]; p.uz=u[2];
        p.vx=v[0]; p.vy=v[1]; p.vz=v[2];
        p.half_w = sz[0].cast<double>() / 2.0;
        p.half_h = sz[1].cast<double>() / 2.0;
        p.name = det["name"].cast<std::string>();
        p.material_name = "";
        p.refractive_index = 1.0;
        p.geom_eps = EPSILON;
        p.type = 1;
        p.index = (int)detectors.size();
        detectors.push_back(p);

        std::array<int,2> res = {1, 1};
        if (det.contains("resolution")) {
            auto rl = det["resolution"].cast<py::list>();
            res[0] = rl[0].cast<int>();
            res[1] = rl[1].cast<int>();
        }
        detector_resolutions.push_back(res);
    }

    // --- Sphere detectors ---
    std::vector<SceneSphereDetector> sphere_dets;
    if (project_dict.contains("sphere_detectors")) {
        for (auto& sd_item : project_dict["sphere_detectors"].cast<py::list>()) {
            auto sd = sd_item.cast<py::dict>();
            SceneSphereDetector s;
            auto c = list_to_arr3(sd["center"]);
            s.cx=c[0]; s.cy=c[1]; s.cz=c[2];
            s.radius = sd["radius"].cast<double>();
            s.name = sd["name"].cast<std::string>();
            auto res = sd["resolution"].cast<py::list>();
            s.n_phi = res[0].cast<int>();
            s.n_theta = res[1].cast<int>();
            s.mode = sd.contains("mode") ? sd["mode"].cast<std::string>()
                                         : std::string("near_field");
            s.index = (int)sphere_dets.size();
            sphere_dets.push_back(s);
        }
    }

    // --- Materials ---
    std::unordered_map<std::string, SceneMaterial> materials;
    if (project_dict.contains("materials")) {
        for (auto kv : project_dict["materials"].cast<py::dict>()) {
            const std::string name = kv.first.cast<std::string>();
            materials[name] = parse_material(kv.second.cast<py::dict>());
        }
    }

    // --- Optical properties (override by name) ---
    std::unordered_map<std::string, SceneMaterial> optical_props;
    if (project_dict.contains("optical_properties")) {
        for (auto kv : project_dict["optical_properties"].cast<py::dict>()) {
            const std::string name = kv.first.cast<std::string>();
            optical_props[name] = parse_material(kv.second.cast<py::dict>());
        }
    }

    // --- Angular distributions ---
    std::unordered_map<std::string, AngularProfile> ang_dists;
    if (project_dict.contains("angular_distributions")) {
        for (auto kv : project_dict["angular_distributions"].cast<py::dict>()) {
            const std::string name = kv.first.cast<std::string>();
            auto prof = kv.second.cast<py::dict>();
            AngularProfile ap;
            ap.name = name;
            if (prof.contains("theta_deg")) ap.theta_deg = list_to_vec(prof["theta_deg"]);
            if (prof.contains("intensity")) ap.intensity = list_to_vec(prof["intensity"]);
            ang_dists[name] = std::move(ap);
        }
    }

    // --- Run real bounce loop ---
    return run_bounce_loop(
        source, surfaces, detectors, detector_resolutions, sphere_dets,
        materials, optical_props, ang_dists,
        n_rays, max_bounces, energy_threshold, (uint64_t)seed);
}

// ---------------------------------------------------------------------------
// pybind11 module registration
// ---------------------------------------------------------------------------

PYBIND11_MODULE(blu_tracer, m) {
    m.doc() = "BluOpticalSim C++ Monte Carlo ray tracer core (pybind11)";
    m.def("trace_source", &trace_source,
          py::arg("project_dict"),
          py::arg("source_name"),
          py::arg("seed"),
          R"doc(
Trace all rays from one source and return detector grids.

Parameters
----------
project_dict : dict
    Serialized Project: sources, surfaces, detectors, sphere_detectors,
    materials, optical_properties, angular_distributions, settings.
source_name : str
    Name of the enabled source to trace.
seed : int
    Random seed for the C++ mt19937_64 RNG.

Returns
-------
dict with keys:
    grids         : {det_name: {"grid": ndarray(ny,nx), "hits": int, "flux": float}}
    spectral_grids: {} (always empty - spectral stays Python)
    escaped       : float  (flux that left the scene without hitting anything
                    plus flux still alive at max_bounces cutoff)
    sb_stats      : {} (Wave 2: solid body stats reserved; filled in future phase)
    sph_grids     : {sd_name: {"grid": ndarray(n_theta,n_phi), "hits": int, "flux": float}}
)doc");
}
