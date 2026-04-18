"""Batch export: package project + results into a single zip file.

Phase 4 Wave 3: KPI CSV gains CI columns (mean/half_width/std/lower/upper/
n_batches/conf_level) — legacy rows write empty CI cells so downstream
consumers can filter on ``n_batches == 0`` to distinguish UQ-off runs.
"""

from __future__ import annotations

import csv
import io as _io_mod
import json
import zipfile
from pathlib import Path

import numpy as np

from backlight_sim.core.project_model import Project
from backlight_sim.core.detectors import SimulationResult
from backlight_sim.core.kpi import (
    compute_all_kpi_cis,
    corner_ratio as _corner_ratio,
    edge_center_ratio as _edge_center_ratio,
    uniformity_in_center as _uniformity_in_center,
)
from backlight_sim.core.uq import CIEstimate
from backlight_sim.io.project_io import project_to_dict
from backlight_sim.io.report import generate_html_report


_CI_HEADER = (
    "metric",
    "value",
    "unit",
    "mean",
    "half_width",
    "std",
    "lower",
    "upper",
    "n_batches",
    "conf_level",
)


def _ci_cells(ci: CIEstimate | None) -> list[str]:
    """Return seven CI column cells for a CIEstimate (or empty strings)."""
    if ci is None or ci.n_batches == 0 or not np.isfinite(ci.half_width):
        return ["", "", "", "", "", "", ""]
    return [
        f"{ci.mean:.6g}",
        f"{ci.half_width:.6g}",
        f"{ci.std:.6g}",
        f"{ci.lower:.6g}",
        f"{ci.upper:.6g}",
        str(ci.n_batches),
        f"{ci.conf_level:.2f}",
    ]


def _row(
    metric: str,
    value: str,
    unit: str = "",
    ci: CIEstimate | None = None,
) -> list[str]:
    return [metric, value, unit] + _ci_cells(ci)


def export_batch_zip(
    project: Project,
    result: SimulationResult | None,
    path: str | Path,
) -> None:
    """Create a zip archive containing project JSON, KPI CSV, grid CSVs, and HTML report.

    If *result* is None, only the project JSON is included.
    """
    p = Path(path)
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Project JSON
        proj_json = json.dumps(project_to_dict(project), indent=2)
        zf.writestr("project.json", proj_json)

        if result is None or not result.detectors:
            return

        # 2. KPI CSV with CI columns (Phase 4 Wave 3 schema)
        kpi_ci_dict = compute_all_kpi_cis(result, conf_level=0.95)

        buf = _io_mod.StringIO()
        writer = csv.writer(buf)
        writer.writerow(_CI_HEADER)

        for det_name, dr in result.detectors.items():
            grid = dr.grid
            avg = float(grid.mean())
            peak = float(grid.max())
            mn = float(grid.min())
            std = float(grid.std())
            cv = std / avg if avg > 0 else 0.0
            hot = peak / avg if avg > 0 else 0.0
            ecr = _edge_center_ratio(grid)
            corner = _corner_ratio(grid)

            writer.writerow(_row("detector", det_name))
            writer.writerow(_row("avg_flux", f"{avg:.6g}", ci=kpi_ci_dict.get("avg")))
            writer.writerow(_row("peak_flux", f"{peak:.6g}", ci=kpi_ci_dict.get("peak")))
            writer.writerow(_row("min_flux", f"{mn:.6g}", ci=kpi_ci_dict.get("min")))
            writer.writerow(_row("std_dev", f"{std:.6g}"))
            writer.writerow(_row("cv", f"{cv:.4f}", "%", ci=kpi_ci_dict.get("cv")))
            writer.writerow(_row("hotspot", f"{hot:.4f}", ci=kpi_ci_dict.get("hot")))
            writer.writerow(_row("edge_center_ratio", f"{ecr:.4f}", ci=kpi_ci_dict.get("ecr")))
            writer.writerow(_row("corner_ratio", f"{corner:.4f}", ci=kpi_ci_dict.get("corner")))
            writer.writerow(_row("total_hits", str(dr.total_hits)))
            writer.writerow(_row("total_flux", f"{dr.total_flux:.6g}"))

            for label, frac in [("1_4", 0.25), ("1_6", 1 / 6), ("1_10", 0.1)]:
                u_avg, u_max = _uniformity_in_center(grid, frac)
                writer.writerow(_row(
                    f"uniformity_{label}_min_avg",
                    f"{u_avg:.4f}",
                    ci=kpi_ci_dict.get(f"uni_{label}_min_avg"),
                ))
                writer.writerow(_row(
                    f"uniformity_{label}_min_max",
                    f"{u_max:.4f}",
                ))

        if result.total_emitted_flux > 0:
            emitted = result.total_emitted_flux
            escaped = result.escaped_flux
            all_det = sum(d.total_flux for d in result.detectors.values())
            absorbed = max(0.0, emitted - all_det - escaped)
            writer.writerow(_row("total_emitted_flux", f"{emitted:.6g}"))
            writer.writerow(_row(
                "efficiency_pct",
                f"{all_det / emitted * 100:.2f}",
                "%",
                ci=kpi_ci_dict.get("efficiency_pct"),
            ))
            writer.writerow(_row("absorbed_pct", f"{absorbed / emitted * 100:.2f}", "%"))
            writer.writerow(_row("escaped_pct", f"{escaped / emitted * 100:.2f}", "%"))
            writer.writerow(_row("led_count", str(result.source_count)))

        zf.writestr("kpi.csv", buf.getvalue())

        # 3. Grid CSVs — one per detector
        for det_name, dr in result.detectors.items():
            gbuf = _io_mod.StringIO()
            np.savetxt(gbuf, dr.grid, delimiter=",", fmt="%.6g")
            safe_name = det_name.replace(" ", "_").replace("/", "_")
            zf.writestr(f"grid_{safe_name}.csv", gbuf.getvalue())

        # 4. HTML report
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            generate_html_report(project, result, tmp_path)
            zf.write(tmp_path, "report.html")
        finally:
            os.unlink(tmp_path)
