"""Golden-suite HTML + markdown report renderers.

Mirrors ``backlight_sim/io/report.py`` matplotlib Agg + base64 PNG convention
(io/report.py:15-35). Degrades to text-only when matplotlib is absent
(Pitfall 7 per RESEARCH.md).

Both writers are side-effect-only — they return ``None`` and write to ``path``.
The markdown writer never imports matplotlib; the HTML writer attempts to
import matplotlib and falls back to an inline placeholder string when the
import fails.

No PySide6 / pyqtgraph / GUI imports — this module is part of the shipped
``backlight_sim.golden`` package and must remain headless.
"""
from __future__ import annotations

import base64
import importlib.util
import io as _io
import platform
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

from backlight_sim.golden.cases import GoldenResult


# ---------------------------------------------------------------------------
# Plot helpers — matplotlib Agg, graceful fallback (pattern from io/report.py:15-35)
# ---------------------------------------------------------------------------


def _try_import_matplotlib():
    """Return the ``pyplot`` module on the Agg backend, or ``None`` if unavailable."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        return None


def _fresnel_plot_base64(results: list[GoldenResult]) -> str:
    """Fresnel T(theta) scatter vs analytical curve. Returns base64 PNG or ''."""
    fresnel_results = [r for r in results if r.name.startswith("fresnel_T_theta=")]
    if len(fresnel_results) < 2:
        return ""
    plt = _try_import_matplotlib()
    if plt is None:
        return ""
    thetas: list[float] = []
    measured: list[float] = []
    expected: list[float] = []
    for r in fresnel_results:
        # Name format: fresnel_T_theta=30
        try:
            theta = float(r.name.split("=")[-1])
        except ValueError:
            continue
        thetas.append(theta)
        measured.append(r.measured)
        expected.append(r.expected)
    if len(thetas) < 2:
        return ""
    idx = np.argsort(thetas)
    thetas_arr = np.array(thetas)[idx]
    measured_arr = np.array(measured)[idx]
    fig, ax = plt.subplots(figsize=(6, 4))
    theta_fine = np.linspace(0, 90, 200)
    try:
        from backlight_sim.tests.golden.references import (
            fresnel_transmittance_unpolarized,
        )
        T_curve = np.array([
            fresnel_transmittance_unpolarized(np.radians(t), 1.0, 1.5)
            for t in theta_fine
        ])
        ax.plot(theta_fine, T_curve, "b-", label="Analytical (n=1.5)", linewidth=1.5)
    except Exception:
        # If references import fails (shouldn't happen since it's always shipped with
        # the test package), still show measured points.
        pass
    ax.plot(thetas_arr, measured_arr, "ro", label="Measured", markersize=7)
    ax.set_xlabel("Incidence angle theta (deg)")
    ax.set_ylabel("Transmittance T(theta)")
    ax.set_title("Fresnel T(theta) - golden reference")
    ax.grid(True, alpha=0.3)
    ax.legend()
    buf = _io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _prism_plot_base64(results: list[GoldenResult]) -> str:
    """Prism total-deviation vs wavelength scatter. Returns base64 PNG or ''."""
    prism_results = [r for r in results if r.name.startswith("prism_theta_lambda=")]
    if len(prism_results) < 2:
        return ""
    plt = _try_import_matplotlib()
    if plt is None:
        return ""
    lambdas: list[float] = []
    measured: list[float] = []
    expected: list[float] = []
    for r in prism_results:
        try:
            lam = float(r.name.split("=")[-1])
        except ValueError:
            continue
        lambdas.append(lam)
        measured.append(r.measured)
        expected.append(r.expected)
    if len(lambdas) < 2:
        return ""
    idx = np.argsort(lambdas)
    lambdas_arr = np.array(lambdas)[idx]
    measured_arr = np.array(measured)[idx]
    expected_arr = np.array(expected)[idx]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(lambdas_arr, expected_arr, "b-o", label="Snell expected", linewidth=1.5, markersize=7)
    ax.plot(lambdas_arr, measured_arr, "r^", label="Measured", markersize=9)
    ax.set_xlabel("Wavelength lambda (nm)")
    ax.set_ylabel("Total deviation D (deg)")
    ax.set_title("Prism dispersion - golden reference")
    ax.grid(True, alpha=0.3)
    ax.legend()
    buf = _io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


# ---------------------------------------------------------------------------
# Markdown — always works, no matplotlib dependency
# ---------------------------------------------------------------------------


def write_markdown_report(results: Iterable[GoldenResult], path: Path) -> None:
    """Text-only markdown summary. Works without matplotlib.

    Produces a header + metadata block + one-row-per-case table. Every
    ``result.name`` appears verbatim in the table so the integration test
    can verify presence by substring match.
    """
    results_list = list(results)
    total = len(results_list)
    passed = sum(1 for r in results_list if r.passed)
    verdict = "ALL PASS" if passed == total and total > 0 else f"{passed}/{total} PASSED"
    lines: list[str] = [
        "# Golden-Reference Validation Report",
        "",
        f"**Generated:** {datetime.now().isoformat(timespec='seconds')}",
        f"**Python:** {platform.python_version()} ({platform.platform()})",
        f"**C++ extension:** `{_blu_tracer_origin()}`",
        f"**Overall:** {verdict}",
        "",
        "| Case | Expected | Measured | Residual | Tolerance | Rays | Status |",
        "|------|----------|----------|----------|-----------|------|--------|",
    ]
    for r in results_list:
        status = "PASS" if r.passed else "FAIL"
        lines.append(
            f"| {r.name} | {r.expected:.4g} | {r.measured:.4g} | "
            f"{r.residual:.4g} | {r.tolerance:.4g} | {r.rays} | {status} |"
        )
    lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# HTML — embeds base64 PNG plots when matplotlib available
# ---------------------------------------------------------------------------


def _blu_tracer_origin() -> str:
    """Reproducibility: return the ``.pyd`` origin (C++ extension) or a sentinel."""
    try:
        spec = importlib.util.find_spec("backlight_sim.sim.blu_tracer")
    except Exception:
        return "(not importable)"
    if spec is None or not spec.origin:
        return "(not found)"
    return spec.origin


def write_html_report(results: Iterable[GoldenResult], path: Path) -> None:
    """HTML report with embedded matplotlib PNGs (when available).

    Mirrors ``backlight_sim/io/report.py:181-215`` template shape. When
    matplotlib is not importable, Fresnel / prism plot slots show an
    inline placeholder note instead of PNG images; the file still writes
    successfully.
    """
    results_list = list(results)
    total = len(results_list)
    passed = sum(1 for r in results_list if r.passed)
    verdict_color = "#2b7d2b" if passed == total and total > 0 else "#b71c1c"
    verdict_text = (
        "ALL PASS" if passed == total and total > 0 else f"{passed}/{total} PASSED"
    )

    # Per-case rows — colored green (pass) or red (fail)
    rows_html: list[str] = []
    for r in results_list:
        row_color = "#e8f5e9" if r.passed else "#ffebee"
        status = "PASS" if r.passed else "FAIL"
        rows_html.append(
            f"<tr style='background:{row_color}'>"
            f"<td>{r.name}</td><td>{r.expected:.4g}</td>"
            f"<td>{r.measured:.4g}</td><td>{r.residual:.4g}</td>"
            f"<td>{r.tolerance:.4g}</td><td>{r.rays}</td>"
            f"<td><b>{status}</b></td></tr>"
        )
    table_html = "\n".join(rows_html)

    # Plots
    fresnel_png = _fresnel_plot_base64(results_list)
    prism_png = _prism_plot_base64(results_list)
    mpl_missing_note = (
        "<em>(matplotlib not available - install matplotlib to enable plots)</em>"
    )
    fresnel_block = (
        f'<img src="data:image/png;base64,{fresnel_png}" alt="Fresnel T(theta)">'
        if fresnel_png
        else mpl_missing_note
    )
    prism_block = (
        f'<img src="data:image/png;base64,{prism_png}" alt="Prism dispersion">'
        if prism_png
        else mpl_missing_note
    )

    pyd_origin = _blu_tracer_origin()
    now = datetime.now().isoformat(timespec="seconds")

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Golden-Reference Validation Report</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       max-width: 900px; margin: 2em auto; padding: 0 1em; color: #222; }}
h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.3em; }}
h2 {{ color: #1a5276; margin-top: 2em; }}
.verdict {{ font-size: 1.3em; font-weight: bold; color: {verdict_color};
           padding: 0.5em; border: 2px solid {verdict_color};
           display: inline-block; margin: 1em 0; }}
table {{ border-collapse: collapse; margin: 0.5em 0 1em; width: 100%; }}
td, th {{ padding: 4px 12px; border: 1px solid #ccc; text-align: left; }}
th {{ background: #f0f0f0; }}
.meta {{ color: #666; font-size: 0.9em; }}
img {{ max-width: 100%; border: 1px solid #ddd; padding: 4px; }}
</style>
</head>
<body>
<h1>Golden-Reference Validation Report</h1>
<div class="verdict">{verdict_text}</div>
<p class="meta">Generated: {now} &mdash; Python {platform.python_version()} on {platform.platform()}</p>
<p class="meta">C++ extension: <code>{pyd_origin}</code></p>

<h2>Per-case results</h2>
<table>
<tr><th>Case</th><th>Expected</th><th>Measured</th><th>Residual</th>
<th>Tolerance</th><th>Rays</th><th>Status</th></tr>
{table_html}
</table>

<h2>Fresnel T(theta)</h2>
{fresnel_block}

<h2>Prism dispersion</h2>
{prism_block}

</body>
</html>"""
    Path(path).write_text(html, encoding="utf-8")
