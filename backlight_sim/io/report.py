"""Generate a self-contained HTML report from simulation results."""

from __future__ import annotations

import base64
import io
from pathlib import Path

import numpy as np

from backlight_sim.core.project_model import Project
from backlight_sim.core.detectors import SimulationResult


def _grid_to_png_base64(grid: np.ndarray) -> str:
    """Render a 2D grid as a colormap PNG and return base64-encoded string."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return ""

    fig, ax = plt.subplots(figsize=(6, 4))
    im = ax.imshow(grid, origin="lower", cmap="inferno", aspect="auto")
    fig.colorbar(im, ax=ax, label="Flux")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_title("Detector Heatmap")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def generate_html_report(
    project: Project,
    result: SimulationResult,
    path: str | Path,
) -> None:
    """Write a self-contained HTML report to *path*."""
    from backlight_sim.gui.heatmap_panel import (
        _uniformity_in_center, _edge_center_ratio, _corner_ratio,
    )

    lines: list[str] = []

    # Collect KPIs per detector
    det_sections = []
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

        rmse_norm = std / avg if avg > 0 else 0.0
        mad_norm = float(np.mean(np.abs(grid - avg))) / avg if avg > 0 else 0.0

        uni_rows = ""
        for label, frac in [("1/4", 0.25), ("1/6", 1/6), ("1/10", 0.1)]:
            u_avg, u_max = _uniformity_in_center(grid, frac)
            uni_rows += f"<tr><td>U ({label} area)</td><td>{u_avg:.4f}</td><td>{u_max:.4f}</td></tr>\n"

        img_b64 = _grid_to_png_base64(grid)
        img_html = f'<img src="data:image/png;base64,{img_b64}" style="max-width:100%;">' if img_b64 else "<em>(matplotlib not available)</em>"

        energy_html = ""
        if result.total_emitted_flux > 0:
            emitted = result.total_emitted_flux
            escaped = result.escaped_flux
            all_det = sum(d.total_flux for d in result.detectors.values())
            absorbed = max(0.0, emitted - all_det - escaped)
            eff = dr.total_flux / emitted * 100
            energy_html = f"""
            <h3>Energy Balance</h3>
            <table>
                <tr><td>Efficiency</td><td>{eff:.1f} %</td></tr>
                <tr><td>Absorbed</td><td>{absorbed / emitted * 100:.1f} %</td></tr>
                <tr><td>Escaped</td><td>{escaped / emitted * 100:.1f} %</td></tr>
                <tr><td>LED count</td><td>{result.source_count}</td></tr>
            </table>
            """

        # Color Uniformity section (only when spectral data available)
        color_html = ""
        if dr.grid_spectral is not None:
            try:
                from backlight_sim.sim.spectral import compute_color_kpis, spectral_bin_centers
                n_bins = dr.grid_spectral.shape[2]
                wl = spectral_bin_centers(n_bins)
                ckpis = compute_color_kpis(dr.grid_spectral, wl)

                def _fmt_delta(v):
                    if isinstance(v, float) and not (v != v):
                        return f"{v:.4f}"
                    return "N/A"

                def _fmt_cct(v):
                    if isinstance(v, float) and not (v != v) and v > 0:
                        return f"{int(round(v))} K"
                    return "N/A"

                center_rows = ""
                for row_label, frac_key in [
                    ("Center 1/4", "center_1_4"),
                    ("Center 1/6", "center_1_6"),
                    ("Center 1/10", "center_1_10"),
                ]:
                    cd = ckpis.get(frac_key, {})
                    center_rows += (
                        f"<tr>"
                        f"<td>{row_label}</td>"
                        f"<td>{_fmt_delta(cd.get('delta_ccx', float('nan')))}</td>"
                        f"<td>{_fmt_delta(cd.get('delta_ccy', float('nan')))}</td>"
                        f"<td>{_fmt_delta(cd.get('delta_uprime', float('nan')))}</td>"
                        f"<td>{_fmt_delta(cd.get('delta_vprime', float('nan')))}</td>"
                        f"<td>--</td><td>--</td>"
                        f"</tr>\n"
                    )

                color_html = f"""
            <h3>Color Uniformity</h3>
            <table>
                <tr>
                    <th>Region</th>
                    <th>delta-CCx</th><th>delta-CCy</th>
                    <th>delta-u'</th><th>delta-v'</th>
                    <th>CCT avg</th><th>CCT range</th>
                </tr>
                <tr>
                    <td>Full</td>
                    <td>{_fmt_delta(ckpis.get('delta_ccx', float('nan')))}</td>
                    <td>{_fmt_delta(ckpis.get('delta_ccy', float('nan')))}</td>
                    <td>{_fmt_delta(ckpis.get('delta_uprime', float('nan')))}</td>
                    <td>{_fmt_delta(ckpis.get('delta_vprime', float('nan')))}</td>
                    <td>{_fmt_cct(ckpis.get('cct_avg', float('nan')))}</td>
                    <td>{_fmt_delta(ckpis.get('cct_range', float('nan')))}</td>
                </tr>
                {center_rows}
            </table>
            """
            except Exception:
                pass  # Non-critical — skip color uniformity on error

        det_sections.append(f"""
        <h2>Detector: {det_name}</h2>
        {img_html}
        <h3>Grid Statistics</h3>
        <table>
            <tr><td>Average</td><td>{avg:.6g}</td></tr>
            <tr><td>Peak</td><td>{peak:.6g}</td></tr>
            <tr><td>Min</td><td>{mn:.6g}</td></tr>
            <tr><td>Std Dev</td><td>{std:.6g}</td></tr>
            <tr><td>CV</td><td>{cv:.4f}</td></tr>
            <tr><td>Hotspot (peak/avg)</td><td>{hot:.4f}</td></tr>
            <tr><td>Edge/Center</td><td>{ecr:.4f}</td></tr>
            <tr><td>Corner/avg</td><td>{corner:.4f}</td></tr>
            <tr><td>RMSE/avg</td><td>{rmse_norm:.4f}</td></tr>
            <tr><td>MAD/avg</td><td>{mad_norm:.4f}</td></tr>
            <tr><td>Total hits</td><td>{dr.total_hits}</td></tr>
            <tr><td>Total flux</td><td>{dr.total_flux:.6g}</td></tr>
        </table>
        <h3>Uniformity</h3>
        <table>
            <tr><th>Region</th><th>min/avg</th><th>min/max</th></tr>
            {uni_rows}
        </table>
        {energy_html}
        {color_html}
        """)

    s = project.settings
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Simulation Report — {project.name}</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           max-width: 900px; margin: 2em auto; padding: 0 1em; color: #222; }}
    h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.3em; }}
    h2 {{ color: #1a5276; margin-top: 2em; }}
    table {{ border-collapse: collapse; margin: 0.5em 0 1em; }}
    td, th {{ padding: 4px 12px; border: 1px solid #ccc; text-align: left; }}
    th {{ background: #f0f0f0; }}
    .meta {{ color: #666; font-size: 0.9em; }}
</style>
</head>
<body>
<h1>Simulation Report: {project.name}</h1>
<p class="meta">
    Sources: {len([s for s in project.sources if s.enabled])} |
    Surfaces: {len(project.surfaces)} |
    Detectors: {len(project.detectors)} |
    Rays/source: {s.rays_per_source:,} |
    Max bounces: {s.max_bounces} |
    Seed: {s.random_seed}
</p>

{"".join(det_sections)}

<hr>
<p class="meta">Generated by Blu Optical Simulation</p>
</body>
</html>"""

    Path(path).write_text(html, encoding="utf-8")
