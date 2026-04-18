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

// ---------------------------------------------------------------------------
// Stub bounce loop — returns empty/zero-filled grids
// Wave 1: correct dict shape only; Wave 2 (plan 02-02) fills real physics.
// ---------------------------------------------------------------------------

static py::dict run_stub_bounce(
    const SceneSource& source,
    const std::vector<ScenePlane>& surfaces,
    const std::vector<ScenePlane>& detectors,
    const std::vector<std::array<int,2>>& detector_resolutions,
    const std::vector<SceneSphereDetector>& sphere_dets,
    int n_rays, int max_bounces, double energy_threshold,
    uint64_t seed)
{
    (void)source; (void)surfaces;
    (void)n_rays; (void)max_bounces; (void)energy_threshold;
    (void)seed;

    // Detector grids: (ny, nx) zero-filled float64 arrays.
    py::dict grids;
    for (size_t i = 0; i < detectors.size(); ++i) {
        const auto& det = detectors[i];
        int nx = detector_resolutions[i][0];
        int ny = detector_resolutions[i][1];
        if (nx <= 0) nx = 1;
        if (ny <= 0) ny = 1;
        std::vector<py::ssize_t> shape = {(py::ssize_t)ny, (py::ssize_t)nx};
        py::array_t<double> grid(shape);
        std::memset(grid.mutable_data(), 0,
                    sizeof(double) * (size_t)nx * (size_t)ny);
        py::dict det_entry;
        det_entry["grid"] = grid;
        det_entry["hits"] = py::int_(0);
        det_entry["flux"] = py::float_(0.0);
        grids[det.name.c_str()] = det_entry;
    }

    // Sphere detector grids: (n_theta, n_phi) zero-filled.
    py::dict sph_grids;
    for (const auto& sd : sphere_dets) {
        int n_theta = sd.n_theta > 0 ? sd.n_theta : 1;
        int n_phi   = sd.n_phi   > 0 ? sd.n_phi   : 1;
        std::vector<py::ssize_t> shape = {(py::ssize_t)n_theta, (py::ssize_t)n_phi};
        py::array_t<double> grid(shape);
        std::memset(grid.mutable_data(), 0,
                    sizeof(double) * (size_t)n_theta * (size_t)n_phi);
        py::dict sd_entry;
        sd_entry["grid"] = grid;
        sd_entry["hits"] = py::int_(0);
        sd_entry["flux"] = py::float_(0.0);
        sph_grids[sd.name.c_str()] = sd_entry;
    }

    py::dict result;
    result["grids"] = grids;
    result["spectral_grids"] = py::dict();
    result["escaped"] = py::float_(0.0);
    result["sb_stats"] = py::dict();
    result["sph_grids"] = sph_grids;
    return result;
}

// ---------------------------------------------------------------------------
// Main entry point: trace_source(project_dict, source_name, seed) -> dict
// ---------------------------------------------------------------------------

py::dict trace_source(py::dict project_dict, std::string source_name, int seed) {
    // --- Deserialize settings ---
    auto settings = project_dict["settings"].cast<py::dict>();
    int n_rays = settings["rays_per_source"].cast<int>();
    int max_bounces = settings["max_bounces"].cast<int>();
    double energy_threshold = settings["energy_threshold"].cast<double>();

    // --- Find the target source ---
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

    // --- Deserialize surfaces ---
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

    // --- Deserialize detectors ---
    std::vector<ScenePlane> detectors;
    std::vector<std::array<int,2>> detector_resolutions;  // (nx, ny)
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

        // resolution: (nx, ny)
        std::array<int,2> res = {1, 1};
        if (det.contains("resolution")) {
            auto rl = det["resolution"].cast<py::list>();
            res[0] = rl[0].cast<int>();
            res[1] = rl[1].cast<int>();
        }
        detector_resolutions.push_back(res);
    }

    // --- Deserialize sphere detectors ---
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

    // --- Run (stub) bounce loop ---
    return run_stub_bounce(source, surfaces, detectors, detector_resolutions,
                           sphere_dets,
                           n_rays, max_bounces, energy_threshold,
                           (uint64_t)seed);
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
    materials, angular_distributions, settings.
source_name : str
    Name of the enabled source to trace.
seed : int
    Random seed for the C++ mt19937_64 RNG.

Returns
-------
dict with keys:
    grids         : {det_name: {"grid": ndarray(ny,nx), "hits": int, "flux": float}}
    spectral_grids: {} (always empty - spectral stays Python)
    escaped       : float  (flux that left the scene without hitting anything)
    sb_stats      : {body_name: {face_id: {"entering_flux": float, "exiting_flux": float}}}
    sph_grids     : {sd_name: {"grid": ndarray(n_theta,n_phi), "hits": int, "flux": float}}
)doc");
}
