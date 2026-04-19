"""Generate a self-contained HTML report from simulation results.

Phase 4 Wave 3: every scalar KPI row additionally shows its 95% confidence
interval via the shared :func:`backlight_sim.core.kpi.compute_all_kpi_cis`
helper.  Heatmap and KPI summary visuals are rendered as inline SVG data URIs,
so the report stays self-contained without optional plotting dependencies.
"""

from __future__ import annotations

import base64
from html import escape as _escape
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


def _svg_data_uri(svg: str) -> str:
    """Return an inline SVG data URI."""
    return "data:image/svg+xml;base64," + base64.b64encode(
        svg.encode("utf-8")
    ).decode("ascii")


def _palette_color(norm: float) -> str:
    """Map a normalized scalar in [0, 1] onto a warm heatmap palette."""
    stops = [
        (0.00, (0, 0, 4)),
        (0.25, (66, 10, 104)),
        (0.50, (147, 38, 103)),
        (0.75, (228, 92, 33)),
        (1.00, (252, 255, 164)),
    ]
    clamped = min(1.0, max(0.0, float(norm)))
    for idx, (pos, rgb) in enumerate(stops[1:], start=1):
        prev_pos, prev_rgb = stops[idx - 1]
        if clamped <= pos:
            span = max(pos - prev_pos, 1e-12)
            t = (clamped - prev_pos) / span
            color = tuple(
                int(round(prev_rgb[ch] + (rgb[ch] - prev_rgb[ch]) * t))
                for ch in range(3)
            )
            return "#{:02x}{:02x}{:02x}".format(*color)
    last = stops[-1][1]
    return "#{:02x}{:02x}{:02x}".format(*last)


def _grid_to_image_data_uri(grid: np.ndarray) -> str:
    """Render a detector heatmap as an inline SVG image."""
    arr = np.asarray(grid, dtype=float)
    if arr.ndim != 2 or arr.size == 0:
        return ""

    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        vmin = vmax = 0.0
    else:
        vmin = float(finite.min())
        vmax = float(finite.max())
    span = max(vmax - vmin, 1e-12)

    ny, nx = arr.shape
    cell = 26
    left = 42
    top = 34
    inner_w = nx * cell
    inner_h = ny * cell
    width = left + inner_w + 22
    height = top + inner_h + 56

    rects: list[str] = []
    for row in range(ny):
        for col in range(nx):
            value = float(arr[row, col])
            norm = 0.0 if not np.isfinite(value) else (value - vmin) / span
            x = left + col * cell
            y = top + (ny - row - 1) * cell
            rects.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'fill="{_palette_color(norm)}"/>'
            )

    svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="{width / 2:.1f}" y="22" text-anchor="middle" font-size="16" font-family="Segoe UI, Arial, sans-serif" fill="#222">Detector Heatmap</text>
  <g>{"".join(rects)}</g>
  <rect x="{left}" y="{top}" width="{inner_w}" height="{inner_h}" fill="none" stroke="#444" stroke-width="1"/>
  <text x="{left}" y="{height - 18}" font-size="12" font-family="Segoe UI, Arial, sans-serif" fill="#555">min {vmin:.4g}</text>
  <text x="{left + inner_w}" y="{height - 18}" text-anchor="end" font-size="12" font-family="Segoe UI, Arial, sans-serif" fill="#555">max {vmax:.4g}</text>
</svg>
""".strip()
    return _svg_data_uri(svg)


def _errorbar_chart_data_uri(kpi_ci_dict: dict[str, CIEstimate | None]) -> str:
    """Render KPI confidence intervals as an inline SVG image."""
    names: list[str] = []
    means: list[float] = []
    errs: list[float] = []
    for name, ci in kpi_ci_dict.items():
        if ci is not None and ci.n_batches > 0 and np.isfinite(ci.half_width):
            names.append(name)
            means.append(float(ci.mean))
            errs.append(float(ci.half_width))
    if not names:
        return ""

    width = 760
    height = 360
    left = 70
    right = 24
    top = 42
    bottom = 88
    plot_w = width - left - right
    plot_h = height - top - bottom

    y_min = min(mean - err for mean, err in zip(means, errs))
    y_max = max(mean + err for mean, err in zip(means, errs))
    if not np.isfinite(y_min) or not np.isfinite(y_max):
        return ""
    if abs(y_max - y_min) < 1e-12:
        pad = max(abs(y_max) * 0.1, 1.0)
        y_min -= pad
        y_max += pad

    def _x_pos(idx: int) -> float:
        return left + plot_w * (idx + 0.5) / len(names)

    def _y_pos(value: float) -> float:
        norm = (value - y_min) / (y_max - y_min)
        return top + plot_h * (1.0 - norm)

    y_ticks: list[str] = []
    for tick_idx in range(5):
        value = y_min + (y_max - y_min) * tick_idx / 4.0
        y = _y_pos(value)
        y_ticks.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#d9d9d9" stroke-width="1"/>'
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="12" font-family="Segoe UI, Arial, sans-serif" fill="#555">{value:.3g}</text>'
        )

    markers: list[str] = []
    labels: list[str] = []
    for idx, (name, mean, err) in enumerate(zip(names, means, errs)):
        x = _x_pos(idx)
        y_mid = _y_pos(mean)
        y_low = _y_pos(mean - err)
        y_high = _y_pos(mean + err)
        markers.append(
            f'<line x1="{x:.1f}" y1="{y_high:.1f}" x2="{x:.1f}" y2="{y_low:.1f}" stroke="#2f6db0" stroke-width="2"/>'
            f'<line x1="{x - 7:.1f}" y1="{y_high:.1f}" x2="{x + 7:.1f}" y2="{y_high:.1f}" stroke="#2f6db0" stroke-width="2"/>'
            f'<line x1="{x - 7:.1f}" y1="{y_low:.1f}" x2="{x + 7:.1f}" y2="{y_low:.1f}" stroke="#2f6db0" stroke-width="2"/>'
            f'<circle cx="{x:.1f}" cy="{y_mid:.1f}" r="4.5" fill="#f08c2e" stroke="#2f6db0" stroke-width="1.5"/>'
        )
        labels.append(
            f'<text x="{x:.1f}" y="{height - 26}" text-anchor="middle" font-size="11" font-family="Segoe UI, Arial, sans-serif" fill="#333" transform="rotate(28 {x:.1f},{height - 26})">{_escape(name)}</text>'
        )

    svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="{width / 2:.1f}" y="24" text-anchor="middle" font-size="16" font-family="Segoe UI, Arial, sans-serif" fill="#222">KPIs with 95% CI</text>
  <g>{"".join(y_ticks)}</g>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#444" stroke-width="1.5"/>
  <line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#444" stroke-width="1.5"/>
  <g>{"".join(markers)}</g>
  <g>{"".join(labels)}</g>
</svg>
""".strip()
    return _svg_data_uri(svg)


def _fmt_ci_cell(ci: CIEstimate | None, fallback: str, unit: str = "") -> str:
    """Return CI string when available, else the legacy fallback value."""
    if ci is None or ci.n_batches == 0 or not np.isfinite(ci.half_width):
        return fallback
    return ci.format(precision=4, unit=unit)


def generate_html_report(
    project: Project,
    result: SimulationResult,
    path: str | Path,
) -> None:
    """Write a self-contained HTML report to *path*."""
    lines: list[str] = []

    # Shared CI lookup (rays_per_batch-aware efficiency scaling — checker I5).
    kpi_ci_dict = compute_all_kpi_cis(result, conf_level=0.95)
    errorbar_src = _errorbar_chart_data_uri(kpi_ci_dict)

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
        for label, frac in [("1/4", 0.25), ("1/6", 1 / 6), ("1/10", 0.1)]:
            u_avg, u_max = _uniformity_in_center(grid, frac)
            key_avg = "uni_{}_min_avg".format(label.replace("/", "_"))
            ci_uavg = kpi_ci_dict.get(key_avg)
            uni_rows += (
                f"<tr><td>U ({label} area)</td>"
                f"<td>{_fmt_ci_cell(ci_uavg, f'{u_avg:.4f}')}</td>"
                f"<td>{u_max:.4f}</td></tr>\n"
            )

        img_src = _grid_to_image_data_uri(grid)
        img_html = (
            f'<img src="{img_src}" style="max-width:100%;">'
            if img_src else "<em>(image unavailable)</em>"
        )

        errorbar_html = ""
        if errorbar_src:
            errorbar_html = (
                f'<h3>KPIs with 95% CI</h3>\n'
                f'<img src="{errorbar_src}" '
                f'style="max-width:100%;">'
            )

        energy_html = ""
        if result.total_emitted_flux > 0:
            emitted = result.total_emitted_flux
            escaped = result.escaped_flux
            all_det = sum(d.total_flux for d in result.detectors.values())
            absorbed = max(0.0, emitted - all_det - escaped)
            eff = dr.total_flux / emitted * 100
            ci_eff = kpi_ci_dict.get("efficiency_pct")
            energy_html = f"""
            <h3>Energy Balance</h3>
            <table>
                <tr><td>Efficiency</td><td>{_fmt_ci_cell(ci_eff, f'{eff:.1f} %', unit=' %')}</td></tr>
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
            except Exception as exc:
                import warnings
                warnings.warn(f"Color uniformity report section failed: {exc}", stacklevel=2)

        ci_avg = kpi_ci_dict.get("avg")
        ci_peak = kpi_ci_dict.get("peak")
        ci_min = kpi_ci_dict.get("min")
        ci_cv = kpi_ci_dict.get("cv")
        ci_hot = kpi_ci_dict.get("hot")
        ci_ecr = kpi_ci_dict.get("ecr")
        ci_corner = kpi_ci_dict.get("corner")

        det_sections.append(f"""
        <h2>Detector: {det_name}</h2>
        {img_html}
        <h3>Grid Statistics</h3>
        <table>
            <tr><td>Average</td><td>{_fmt_ci_cell(ci_avg, f'{avg:.6g}')}</td></tr>
            <tr><td>Peak</td><td>{_fmt_ci_cell(ci_peak, f'{peak:.6g}')}</td></tr>
            <tr><td>Min</td><td>{_fmt_ci_cell(ci_min, f'{mn:.6g}')}</td></tr>
            <tr><td>Std Dev</td><td>{std:.6g}</td></tr>
            <tr><td>CV</td><td>{_fmt_ci_cell(ci_cv, f'{cv:.4f}')}</td></tr>
            <tr><td>Hotspot (peak/avg)</td><td>{_fmt_ci_cell(ci_hot, f'{hot:.4f}')}</td></tr>
            <tr><td>Edge/Center</td><td>{_fmt_ci_cell(ci_ecr, f'{ecr:.4f}')}</td></tr>
            <tr><td>Corner/avg</td><td>{_fmt_ci_cell(ci_corner, f'{corner:.4f}')}</td></tr>
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
        {errorbar_html}
        {color_html}
        """)

    uq_warnings_html = ""
    warnings_list = getattr(result, "uq_warnings", []) or []
    if warnings_list:
        items = "".join(f"<li>{w}</li>" for w in warnings_list)
        uq_warnings_html = (
            f'<div class="warning"><h3>UQ warnings</h3><ul>{items}</ul></div>'
        )

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
    .warning {{ color: #b96a00; background: #fff7e6; border-left: 4px solid #e09c46;
                padding: 0.6em 1em; margin: 1em 0; }}
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
{uq_warnings_html}

{"".join(det_sections)}

<hr>
<p class="meta">Generated by Blu Optical Simulation</p>
</body>
</html>"""

    Path(path).write_text(html, encoding="utf-8")
