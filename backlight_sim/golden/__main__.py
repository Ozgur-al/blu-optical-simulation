"""CLI entry: ``python -m backlight_sim.golden [--report] [--out DIR] [--rays N] [--cases LIST]``.

Runs the case registry from ``backlight_sim.golden.cases.ALL_CASES`` and emits a
per-case PASS/FAIL summary. With ``--report``, also writes an HTML + markdown
report via ``backlight_sim.golden.report``.

Stdlib argparse only (no typer/click - no new deps per RESEARCH.md Standard Stack).
Mirrors ``build_exe.py`` argparse pattern (the only other CLI in the repo).

Exit codes:
* 0 - every registered case passed
* 1 - at least one case failed (CI gate semantics)
* 2 - usage / config error (empty registry, unknown ``--cases`` value)
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from backlight_sim.golden.cases import ALL_CASES, run_case
from backlight_sim.golden.report import write_html_report, write_markdown_report


def _default_out_dir() -> Path:
    return Path("golden_reports") / datetime.now().strftime("%Y%m%d_%H%M%S")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m backlight_sim.golden",
        description="Run the golden-reference validation suite and emit a report.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Write HTML + markdown summary (default: print to stdout only)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory (default: ./golden_reports/<timestamp>)",
    )
    parser.add_argument(
        "--rays",
        type=int,
        default=None,
        help="Override per-case ray count (smaller = faster smoke run)",
    )
    parser.add_argument(
        "--cases",
        type=str,
        default=None,
        help="Comma-separated case names (default: all registered cases)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print per-case progress lines",
    )
    args = parser.parse_args(argv)

    if not ALL_CASES:
        print(
            "[golden] ERROR: no cases registered in ALL_CASES - "
            "is backlight_sim.golden.cases correctly populated?",
            file=sys.stderr,
        )
        return 2

    if args.cases is None:
        cases = list(ALL_CASES)
    else:
        wanted = {c.strip() for c in args.cases.split(",") if c.strip()}
        cases = [c for c in ALL_CASES if c.name in wanted]
        if not cases:
            print(
                f"[golden] ERROR: no cases matched {sorted(wanted)}",
                file=sys.stderr,
            )
            return 2

    print(f"[golden] Running {len(cases)} case(s)...")
    results = []
    for case in cases:
        gr = run_case(case, rays_override=args.rays, verbose=args.verbose)
        results.append(gr)
        if not args.verbose:
            status = "PASS" if gr.passed else "FAIL"
            print(
                f"  [{status}] {gr.name}: residual={gr.residual:.4g} "
                f"tol={gr.tolerance:.4g} rays={gr.rays}"
            )

    passed = sum(1 for r in results if r.passed)
    print(f"\n[golden] {passed}/{len(results)} cases passed")

    if args.report:
        out_dir = args.out if args.out is not None else _default_out_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        html_path = out_dir / "report.html"
        md_path = out_dir / "report.md"
        write_html_report(results, html_path)
        write_markdown_report(results, md_path)
        print(f"[golden] Wrote report to {out_dir}")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
