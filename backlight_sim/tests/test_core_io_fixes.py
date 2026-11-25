"""Regression tests for core/io bug fixes (KPI CIs, exports, IES/LDT, geometry
builder, far-field KPIs, project save, update checker).

Pure numpy — no PySide6, no tracer import.
"""

from __future__ import annotations

import csv
import io
import zipfile

import numpy as np
import pytest

from backlight_sim.core.detectors import DetectorResult, SimulationResult
from backlight_sim.core.kpi import compute_all_kpi_cis, uniformity_in_center
from backlight_sim.core.project_model import Project, SimulationSettings


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _det_from_batches(name: str, gb: np.ndarray, src_per_batch: float) -> DetectorResult:
    K = gb.shape[0]
    return DetectorResult(
        detector_name=name,
        grid=gb.sum(axis=0),
        total_hits=int(gb.sum()),
        total_flux=float(gb.sum()),
        grid_batches=gb,
        flux_batches=gb.sum(axis=(1, 2)),
        rays_per_batch=[1000] * K,
        n_batches=K,
    )


def _poisson_batches(rng, K=10, lam=None, shape=(20, 20)):
    if lam is None:
        yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
        lam = 40.0 + 20.0 * np.exp(-((yy - 10) ** 2 + (xx - 10) ** 2) / 40.0)
    return rng.poisson(lam, size=(K,) + shape).astype(float)


def _cv(g):
    return g.std() / g.mean() * 100.0


# ---------------------------------------------------------------------------
# #2 — CI mean is the full-grid KPI; jackknife half-width is sensible
# ---------------------------------------------------------------------------

def test_ci_mean_equals_full_grid_kpi():
    rng = np.random.default_rng(1)
    gb = _poisson_batches(rng)
    det = _det_from_batches("d", gb, 0.0)
    res = SimulationResult(detectors={"d": det},
                           total_emitted_flux=float(gb.sum()) * 2.0)
    cis = compute_all_kpi_cis(res)
    full = det.grid
    assert cis["avg"].mean == pytest.approx(full.mean())
    assert cis["peak"].mean == pytest.approx(full.max())
    assert cis["min"].mean == pytest.approx(full.min())
    assert cis["cv"].mean == pytest.approx(_cv(full))
    assert cis["hot"].mean == pytest.approx(full.max() / full.mean())
    assert cis["uni_1_4_min_avg"].mean == pytest.approx(
        uniformity_in_center(full, 0.25)[0])
    assert cis["efficiency_pct"].mean == pytest.approx(50.0)
    for k, ci in cis.items():
        assert ci is not None and np.isfinite(ci.half_width) and ci.half_width >= 0, k


def test_ci_mean_uses_detector_grid_scale():
    """If det.grid is on a different overall scale than sum(batches), the
    point estimate follows det.grid and the interval is rescaled to it."""
    rng = np.random.default_rng(2)
    gb = _poisson_batches(rng)
    det = _det_from_batches("d", gb, 0.0)
    det.grid = gb.sum(axis=0) / 10.0
    res = SimulationResult(detectors={"d": det}, total_emitted_flux=1.0)
    ci = compute_all_kpi_cis(res)["avg"]
    assert ci.mean == pytest.approx(det.grid.mean())
    assert ci.half_width < 0.05 * ci.mean


@pytest.mark.parametrize("kpi", ["avg", "cv", "uni_1_4_min_avg", "hot"])
def test_jackknife_half_width_matches_replication_spread(kpi):
    """Jackknife SE ~ true sampling SD of the full-grid KPI (within 2x),
    and the 95% interval covers the truth in most replications."""
    rng = np.random.default_rng(7)
    yy, xx = np.mgrid[0:20, 0:20]
    lam = 40.0 + 20.0 * np.exp(-((yy - 10) ** 2 + (xx - 10) ** 2) / 40.0)
    n_rep, K = 200, 10
    points, ses, cis = [], [], []
    for _ in range(n_rep):
        gb = rng.poisson(lam, size=(K, 20, 20)).astype(float)
        det = _det_from_batches("d", gb, 0.0)
        res = SimulationResult(detectors={"d": det}, total_emitted_flux=1.0)
        ci = compute_all_kpi_cis(res)[kpi]
        points.append(ci.mean)
        ses.append(ci.half_width / 2.2622)   # t_{0.975, 9}
        cis.append(ci)
    true_sd = float(np.std(points, ddof=1))
    med_se = float(np.median(ses))
    assert 0.5 * true_sd < med_se < 2.0 * true_sd, (kpi, true_sd, med_se)
    centre = float(np.mean(points))
    coverage = np.mean([c.lower <= centre <= c.upper for c in cis])
    assert coverage > 0.80, (kpi, coverage)


def test_ci_none_when_uq_off():
    det = DetectorResult("d", grid=np.ones((4, 4)), n_batches=0)
    res = SimulationResult(detectors={"d": det}, total_emitted_flux=1.0)
    assert all(v is None for v in compute_all_kpi_cis(res).values())


# ---------------------------------------------------------------------------
# #3/#4/#14 — per-detector CIs, CV percent, HTML escaping
# ---------------------------------------------------------------------------

def _two_detector_result():
    rng = np.random.default_rng(3)
    ga = _poisson_batches(rng, lam=np.full((10, 10), 50.0), shape=(10, 10))
    gb = _poisson_batches(rng, lam=np.full((10, 10), 5.0), shape=(10, 10))
    da = _det_from_batches("A", ga, 0.0)
    db = _det_from_batches("B<x>", gb, 0.0)
    total = float(ga.sum() + gb.sum()) * 2.0
    return SimulationResult(detectors={"A": da, "B<x>": db},
                            total_emitted_flux=total, escaped_flux=0.0,
                            source_count=1)


def test_compute_all_kpi_cis_per_detector():
    res = _two_detector_result()
    a = compute_all_kpi_cis(res, detector_name="A")
    b = compute_all_kpi_cis(res, detector_name="B<x>")
    assert a["avg"].mean == pytest.approx(res.detectors["A"].grid.mean())
    assert b["avg"].mean == pytest.approx(res.detectors["B<x>"].grid.mean())
    assert b["efficiency_pct"].mean == pytest.approx(
        res.detectors["B<x>"].total_flux / res.total_emitted_flux * 100)


def test_batch_export_csv_per_detector_and_cv_percent(tmp_path):
    from backlight_sim.io.batch_export import export_batch_zip

    res = _two_detector_result()
    out = tmp_path / "b.zip"
    export_batch_zip(Project(name="p", settings=SimulationSettings()), res, out)
    with zipfile.ZipFile(out) as zf:
        rows = list(csv.reader(io.StringIO(zf.read("kpi.csv").decode("utf-8"))))
    header = rows[0]
    i_val, i_mean = header.index("value"), header.index("mean")
    sections: dict[str, dict[str, list[str]]] = {}
    cur = None
    for r in rows[1:]:
        if r[0] == "detector":
            cur = r[1]
            sections[cur] = {}
        elif cur is not None:
            sections[cur].setdefault(r[0], r)
    for name, dr in res.detectors.items():
        rows_d = sections[name]
        assert float(rows_d["avg_flux"][i_mean]) == pytest.approx(dr.grid.mean(), rel=1e-5)
        assert float(rows_d["avg_flux"][i_val]) == pytest.approx(dr.grid.mean(), rel=1e-5)
        cv_pct = _cv(dr.grid)
        assert float(rows_d["cv"][i_val]) == pytest.approx(cv_pct, abs=1e-3)
        assert float(rows_d["cv"][i_mean]) == pytest.approx(cv_pct, rel=1e-4)


def test_report_per_detector_and_escaped(tmp_path):
    from backlight_sim.io.report import generate_html_report

    res = _two_detector_result()
    res.uq_warnings.append("<b>warn</b>")
    out = tmp_path / "r.html"
    generate_html_report(Project(name="a<b>&c", settings=SimulationSettings()), res, out)
    html = out.read_text(encoding="utf-8")
    assert "a&lt;b&gt;&amp;c" in html and "a<b>&c" not in html
    assert "B&lt;x&gt;" in html and "<h2>Detector: B<x>" not in html
    assert "&lt;b&gt;warn&lt;/b&gt;" in html
    avg_b = res.detectors["B<x>"].grid.mean()
    avg_a = res.detectors["A"].grid.mean()
    sec_b = html.split("Detector: B&lt;x&gt;")[1]
    sec_a = html.split("Detector: A")[1].split("Detector: B")[0]

    def _avg_cell(sec: str) -> float:
        cell = sec.split("Average</td><td>")[1].split("</td>")[0]
        return float(cell.split()[0])

    assert _avg_cell(sec_b) == pytest.approx(avg_b, rel=0.01)
    assert _avg_cell(sec_a) == pytest.approx(avg_a, rel=0.01)
    assert " %" in sec_a.split("CV</td>")[1].split("</tr>")[0]


# ---------------------------------------------------------------------------
# #5/#6 — IES / LDT parsing
# ---------------------------------------------------------------------------

_IES_HEADER = """IESNA:LM-63-2002
[TEST] fixture
[MANUFAC] test
"""


def test_ies_tilt_none(tmp_path):
    from backlight_sim.io.ies_parser import load_ies

    p = tmp_path / "a.ies"
    p.write_text(_IES_HEADER + """TILT=NONE
1 1000 2.0 3 1 1 2 0 0 0
1.0 1.0 10
0 45 90
0
100 70 0
""")
    r = load_ies(p)
    assert r["theta_deg"] == [0.0, 45.0, 90.0]
    assert r["intensity"] == pytest.approx([1.0, 0.7, 0.0])


def test_ies_tilt_include(tmp_path):
    from backlight_sim.io.ies_parser import load_ies

    p = tmp_path / "b.ies"
    p.write_text(_IES_HEADER + """TILT=INCLUDE
1
3
0 45 90
1.0 0.9 0.8
1 1000 1 3 1 1 2 0 0 0
1 1 10
0 45 90
0
100 70 0
""")
    r = load_ies(p)
    assert r["theta_deg"] == [0.0, 45.0, 90.0]
    assert r["intensity"] == pytest.approx([1.0, 0.7, 0.0])


def test_ies_cplane_weighting_nonuniform(tmp_path):
    """C-planes 0, 10, 90 (quadrant symmetry): trapezoid weights 5/45/40."""
    from backlight_sim.io.ies_parser import load_ies

    p = tmp_path / "c.ies"
    p.write_text(_IES_HEADER + """TILT=NONE
1 1000 1 2 3 1 2 0 0 0
1 1 10
0 60
0 10 90
100 100
100 0
100 0
""")
    r = load_ies(p)
    assert r["intensity"][1] == pytest.approx(100 * 5 / 90 / 100)


def test_ies_full_circle_without_360_wraps(tmp_path):
    """Planes 0, 90, 180, 270 (no 360): each plane must get equal weight."""
    from backlight_sim.io.ies_parser import load_ies

    p = tmp_path / "d.ies"
    p.write_text(_IES_HEADER + """TILT=NONE
1 1000 1 2 4 1 2 0 0 0
1 1 10
0 60
0 90 180 270
100 40
100 0
100 0
100 0
""")
    r = load_ies(p)
    assert r["intensity"][1] == pytest.approx(0.1)


def _ldt_text(isym: int, mc: int, dc: float, gammas: list[float],
              planes: list[list[float]], conv: float = 1.0,
              n_sets: int = 1, blank_text_fields: bool = True) -> str:
    ng = len(gammas)
    L = [
        "ACME", "1", str(isym), str(mc), str(dc), str(ng),
        str(gammas[1] - gammas[0]),
        "" if blank_text_fields else "rep",   # 8 report number (may be empty)
        "Fixture",                             # 9 luminaire name
        "",                                    # 10 luminaire number
        "fixture.ldt", "2026",                 # 11, 12
        "100", "100", "50", "100", "100", "0", "0", "0", "0",  # 13-21
        "100", "80", str(conv), "0", str(n_sets),               # 22-26
    ]
    for _ in range(n_sets):
        L += ["1", "LED module", "1000", "4000", "80", "10"]
    L += ["0.1"] * 10
    L += [str(i * dc) for i in range(mc)]
    L += [str(g) for g in gammas]
    for pl in planes:
        L += [str(v) for v in pl]
    return "\n".join(L) + "\n"


def test_ldt_isym0_full(tmp_path):
    from backlight_sim.io.ies_parser import load_ldt

    p = tmp_path / "a.ldt"
    planes = [[100, 80, 0], [100, 40, 0], [100, 80, 0], [100, 40, 0]]
    p.write_text(_ldt_text(0, 4, 90, [0, 45, 90], planes, n_sets=2))
    r = load_ldt(p)
    assert r["theta_deg"] == [0.0, 45.0, 90.0]
    assert r["intensity"] == pytest.approx([1.0, 0.6, 0.0])


def test_ldt_isym1_single_plane(tmp_path):
    from backlight_sim.io.ies_parser import load_ldt

    p = tmp_path / "b.ldt"
    p.write_text(_ldt_text(1, 36, 10, [0, 30, 60, 90], [[200, 150, 50, 0]],
                           conv=2.5))
    r = load_ldt(p)
    assert r["theta_deg"] == [0.0, 30.0, 60.0, 90.0]
    assert r["intensity"] == pytest.approx([1.0, 0.75, 0.25, 0.0])


def test_ldt_isym2_half(tmp_path):
    """Isym=2, Mc=4 -> planes C0, C90, C180 with weights 45/90/45."""
    from backlight_sim.io.ies_parser import load_ldt

    p = tmp_path / "c.ldt"
    planes = [[100, 0], [100, 100], [100, 0]]
    p.write_text(_ldt_text(2, 4, 90, [0, 60], planes))
    r = load_ldt(p)
    assert r["intensity"] == pytest.approx([1.0, 0.5])


def test_ldt_isym4_quadrant(tmp_path):
    """Isym=4, Mc=8 -> planes C0, C45, C90 with weights 1/2/1."""
    from backlight_sim.io.ies_parser import load_ldt

    p = tmp_path / "d.ldt"
    planes = [[100, 0], [100, 100], [100, 0]]
    p.write_text(_ldt_text(4, 8, 45, [0, 60], planes))
    r = load_ldt(p)
    assert r["intensity"] == pytest.approx([1.0, 0.5])


def test_ldt_truncated_raises(tmp_path):
    from backlight_sim.io.ies_parser import load_ldt

    p = tmp_path / "e.ldt"
    p.write_text(_ldt_text(0, 4, 90, [0, 45, 90], [[1, 1, 1]]))
    with pytest.raises(ValueError):
        load_ldt(p)


# ---------------------------------------------------------------------------
# #11 — IES export compliance + round trip
# ---------------------------------------------------------------------------

def test_export_ies_lm63_angles_and_roundtrip(tmp_path):
    from backlight_sim.io.ies_parser import export_ies, load_ies

    nt, nphi = 36, 72
    th = (np.arange(nt) + 0.5) * 180.0 / nt
    g = np.clip(np.cos(np.radians(th)), 0, None)[:, None] * np.ones((1, nphi)) * 100
    p = tmp_path / "o.ies"
    export_ies(p, th, g, 314.0)
    lines = p.read_text().splitlines()
    i = lines.index("TILT=NONE")
    hdr = lines[i + 1].split()
    assert len(hdr) == 10 and len(lines[i + 2].split()) == 3
    vert = [float(v) for v in lines[i + 3].split()]
    horiz = [float(v) for v in lines[i + 4].split()]
    assert vert[0] == 0.0 and vert[-1] == 180.0
    assert horiz[0] == 0.0 and horiz[-1] == 360.0
    assert int(hdr[3]) == len(vert) and int(hdr[4]) == len(horiz)
    r = load_ies(p)
    assert r["intensity"][0] == pytest.approx(1.0)
    expect = np.clip(np.cos(np.radians(r["theta_deg"])), 0, None)
    expect = expect / expect.max()
    assert np.allclose(r["intensity"], expect, atol=0.01)


# ---------------------------------------------------------------------------
# #9 — far-field beam / field angle about the actual beam axis
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("flip", [False, True])
def test_farfield_beam_angle_independent_of_pole(flip):
    from backlight_sim.io.ies_parser import compute_farfield_kpis

    nt, nphi = 36, 72
    th = (np.arange(nt) + 0.5) * 180.0 / nt
    g = np.clip(np.cos(np.radians(th)), 0, None)[:, None] * np.ones((1, nphi))
    if flip:
        g = g[::-1]
    k = compute_farfield_kpis(g, th)
    assert k["beam_angle"] == pytest.approx(120.0, abs=3.0)
    assert k["field_angle"] == pytest.approx(2 * np.degrees(np.arccos(0.1)), abs=3.0)


def test_farfield_beam_angle_tilted_axis():
    """Narrow beam pointing at theta=90 deg (horizontal): beam angle stays
    the same as when it points along the pole."""
    from backlight_sim.io.ies_parser import compute_farfield_kpis

    nt, nphi = 90, 180
    th = np.radians((np.arange(nt) + 0.5) * 180.0 / nt)
    ph = np.radians((np.arange(nphi) + 0.5) * 360.0 / nphi)
    TH, PH = np.meshgrid(th, ph, indexing="ij")
    d = np.stack([np.sin(TH) * np.cos(PH), np.sin(TH) * np.sin(PH), np.cos(TH)], -1)

    def beam(axis):
        c = np.clip(d @ axis, 0, None) ** 8
        return compute_farfield_kpis(c, np.degrees(th))["beam_angle"]

    b_pole = beam(np.array([0.0, 0.0, 1.0]))
    b_side = beam(np.array([1.0, 0.0, 0.0]))
    expected = 2 * np.degrees(np.arccos(0.5 ** (1 / 8)))
    assert b_pole == pytest.approx(expected, abs=3.0)
    assert b_side == pytest.approx(expected, abs=3.0)


# ---------------------------------------------------------------------------
# #7 — tilted cavity corner seams are closed
# ---------------------------------------------------------------------------

def _ray_hits_rect(o, d, r) -> bool:
    n = r.normal
    den = float(np.dot(d, n))
    if abs(den) < 1e-12:
        return False
    t = float(np.dot(r.center - o, n)) / den
    if t <= 0:
        return False
    p = o + t * d - r.center
    return (abs(np.dot(p, r.u_axis)) <= r.size[0] / 2 + 1e-9
            and abs(np.dot(p, r.v_axis)) <= r.size[1] / 2 + 1e-9)


@pytest.mark.parametrize("ax,ay", [(10.0, 10.0), (20.0, 5.0), (0.0, 15.0), (30.0, 0.0)])
def test_tilted_cavity_corner_seams_closed(ax, ay):
    from backlight_sim.io.geometry_builder import build_cavity

    p = Project()
    w, h, dpt = 120.0, 60.0, 10.0
    build_cavity(p, w, h, dpt, wall_angle_x_deg=ax, wall_angle_y_deg=ay)
    walls = [s for s in p.surfaces if s.name.startswith("Wall")]
    tx, ty = np.tan(np.radians(ax)), np.tan(np.radians(ay))
    o = np.array([0.0, 0.0, dpt / 2.0])
    for z in np.linspace(0.05, dpt - 0.05, 15):
        for sx in (-1, 1):
            for sy in (-1, 1):
                seam = np.array([sx * (w / 2 + z * tx), sy * (h / 2 + z * ty), z])
                # Aim just inside the seam towards the corner; the ray must
                # hit some wall instead of escaping through a gap.
                d = seam - o
                d /= np.linalg.norm(d)
                assert any(_ray_hits_rect(o, d, wr) for wr in walls), (z, sx, sy)


def test_tilted_cavity_normals_unchanged_and_bottom_edges_on_floor():
    from backlight_sim.io.geometry_builder import build_cavity

    p = Project()
    build_cavity(p, 100.0, 50.0, 10.0, wall_angle_x_deg=10.0, wall_angle_y_deg=10.0)
    walls = {s.name: s for s in p.surfaces}
    c, s_ = np.cos(np.radians(10)), np.sin(np.radians(10))
    assert np.allclose(walls["Wall Right"].normal, [c, 0, -s_])
    assert np.allclose(walls["Wall Left"].normal, [-c, 0, -s_])
    assert np.allclose(walls["Wall Back"].normal, [0, c, -s_])
    assert np.allclose(walls["Wall Front"].normal, [0, -c, -s_])
    r = walls["Wall Right"]
    bottom = r.center - r.v_axis * r.size[1] / 2
    assert bottom[0] == pytest.approx(50.0) and bottom[2] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# #8 — LED grid count mode
# ---------------------------------------------------------------------------

def test_led_grid_count_one_is_single_centered_led():
    from backlight_sim.io.geometry_builder import build_led_grid

    p = Project()
    n = build_led_grid(p, 100, 60, 10, 10, 10, 10, 1.0, "lambertian",
                       count_x=1, count_y=1)
    assert n == 1
    assert np.allclose(p.sources[0].position[:2], [0.0, 0.0])


def test_led_grid_count_one_on_one_axis():
    from backlight_sim.io.geometry_builder import build_led_grid

    p = Project()
    n = build_led_grid(p, 100, 60, 10, 10, 10, 10, 1.0, "lambertian",
                       count_x=5, count_y=1)
    assert n == 5
    xs = sorted(s.position[0] for s in p.sources)
    assert xs == pytest.approx([-40, -20, 0, 20, 40])
    assert all(s.position[1] == pytest.approx(0.0) for s in p.sources)


def test_led_grid_count_exact_no_float_drift():
    from backlight_sim.io.geometry_builder import build_led_grid

    p = Project()
    n = build_led_grid(p, 300.1, 77.7, 1, 1, 3.3, 2.2, 1.0, "lambertian",
                       count_x=37, count_y=11)
    assert n == 37 * 11


# ---------------------------------------------------------------------------
# #12 — project save: numpy scalars + atomic write
# ---------------------------------------------------------------------------

def test_save_project_numpy_scalars_and_atomic(tmp_path):
    from backlight_sim.core.detectors import DetectorSurface
    from backlight_sim.core.sources import PointSource
    from backlight_sim.io.project_io import load_project, save_project

    p = Project(name="np")
    p.detectors.append(DetectorSurface.axis_aligned(
        "d", [0, 0, 0], (np.float32(10), 10.0), 2, 1.0,
        (np.int64(50), np.int64(40))))
    p.sources.append(PointSource("s", [0, 0, 0], flux=np.float32(5.0)))
    p.settings.rays_per_source = np.int64(1234)
    p.cavity_recipe = {"depth": np.float64(3.0), "arr": np.array([1, 2])}
    path = tmp_path / "x.blu"
    path.write_text("OLD", encoding="utf-8")
    save_project(p, path)
    assert [f.name for f in tmp_path.iterdir()] == ["x.blu"]
    q = load_project(path)
    assert q.detectors[0].resolution == (50, 40)
    assert q.settings.rays_per_source == 1234
    assert q.cavity_recipe["arr"] == [1, 2]


def test_save_project_failure_keeps_old_file(tmp_path):
    from backlight_sim.io.project_io import save_project

    p = Project(name="bad")
    p.cavity_recipe = {"x": object()}
    path = tmp_path / "y.blu"
    path.write_text("OLD", encoding="utf-8")
    with pytest.raises(TypeError):
        save_project(p, path)
    assert path.read_text(encoding="utf-8") == "OLD"
    assert [f.name for f in tmp_path.iterdir()] == ["y.blu"]


# ---------------------------------------------------------------------------
# #13 — update checker version comparison
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cur,latest,newer", [
    ("1.0.0", "1.1.0-beta", True),
    ("1.1.0-beta", "1.1.0", True),
    ("1.1.0", "1.1.0-beta", False),
    ("1.1.0-alpha", "1.1.0-beta", True),
    ("1.1.0rc1", "1.1.0rc2", True),
    ("2.9", "2.10", True),
    ("2.10", "2.9", False),
    ("1.0", "1.0.0", False),
    ("1.0.0", "1.0", False),
    ("1.0.0", "v1.0.1", True),
    ("1.0.0", "garbage", False),
    ("1.0.0", "", False),
])
def test_compare_versions(cur, latest, newer):
    from backlight_sim.update_checker import _compare_versions

    assert _compare_versions(cur, latest) is newer


def test_check_for_update_non_dict_json(monkeypatch):
    from backlight_sim import update_checker as uc

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"[1, 2, 3]"

    monkeypatch.setattr(uc.urllib.request, "urlopen", lambda *a, **k: _Resp())
    info = uc.check_for_update(timeout=0.1)
    assert info.available is False and info.error
