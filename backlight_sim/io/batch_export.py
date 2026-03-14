"""Batch export: package project + results into a single zip file."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np

from backlight_sim.core.project_model import Project
from backlight_sim.core.detectors import SimulationResult
from backlight_sim.io.project_io import project_to_dict
from backlight_sim.io.report import generate_html_report


def export_batch_zip(
    project: Project,
    result: SimulationResult | None,
    path: str | Path,
) -> None:
    """Create a zip archive containing project JSON, KPI CSV, grid CSVs, and HTML report.

    If *result* is None, only the project JSON is included.
    """
    from backlight_sim.gui.heatmap_panel import (
        _uniformity_in_center, _edge_center_ratio, _corner_ratio,
    )

    p = Path(path)
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Project JSON
        proj_json = json.dumps(project_to_dict(project), indent=2)
        zf.writestr("project.json", proj_json)

        if result is None or not result.detectors:
            return

        # 2. KPI CSV
        kpi_lines = ["Metric,Value"]
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

            kpi_lines.append(f"Detector,{det_name}")
            kpi_lines.append(f"Average flux,{avg:.6g}")
            kpi_lines.append(f"Peak flux,{peak:.6g}")
            kpi_lines.append(f"Min flux,{mn:.6g}")
            kpi_lines.append(f"Std Dev,{std:.6g}")
            kpi_lines.append(f"CV,{cv:.4f}")
            kpi_lines.append(f"Hotspot,{hot:.4f}")
            kpi_lines.append(f"Edge/Center,{ecr:.4f}")
            kpi_lines.append(f"Corner/avg,{corner:.4f}")
            kpi_lines.append(f"Total hits,{dr.total_hits}")
            kpi_lines.append(f"Total flux,{dr.total_flux:.6g}")

            for label, frac in [("1/4", 0.25), ("1/6", 1/6), ("1/10", 0.1)]:
                u_avg, u_max = _uniformity_in_center(grid, frac)
                kpi_lines.append(f"U({label}) min/avg,{u_avg:.4f}")
                kpi_lines.append(f"U({label}) min/max,{u_max:.4f}")

        if result.total_emitted_flux > 0:
            emitted = result.total_emitted_flux
            escaped = result.escaped_flux
            all_det = sum(d.total_flux for d in result.detectors.values())
            absorbed = max(0.0, emitted - all_det - escaped)
            kpi_lines.append(f"Total emitted,{emitted:.6g}")
            kpi_lines.append(f"Efficiency %,{all_det / emitted * 100:.2f}")
            kpi_lines.append(f"Absorbed %,{absorbed / emitted * 100:.2f}")
            kpi_lines.append(f"Escaped %,{escaped / emitted * 100:.2f}")
            kpi_lines.append(f"LED count,{result.source_count}")

        zf.writestr("kpi.csv", "\n".join(kpi_lines))

        # 3. Grid CSVs — one per detector
        for det_name, dr in result.detectors.items():
            import io
            buf = io.StringIO()
            np.savetxt(buf, dr.grid, delimiter=",", fmt="%.6g")
            safe_name = det_name.replace(" ", "_").replace("/", "_")
            zf.writestr(f"grid_{safe_name}.csv", buf.getvalue())

        # 4. HTML report
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            generate_html_report(project, result, tmp_path)
            zf.write(tmp_path, "report.html")
        finally:
            os.unlink(tmp_path)
