"""Golden-reference case registry — shared source of truth for pytest + CLI.

Mirrors backlight_sim/io/presets.py factory/registry pattern. Each GoldenCase
carries a project factory and a measurement function; run_case() runs the tracer
and produces a GoldenResult that pytest asserts on and the CLI reports on.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from backlight_sim.core.project_model import Project


@dataclass
class GoldenResult:
    name: str
    expected: float
    measured: float
    residual: float
    tolerance: float
    rays: int
    passed: Optional[bool] = None
    notes: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class GoldenCase:
    name: str
    description: str
    build_project: Callable[[Optional[int]], Project]
    measure: Callable[[Project, Any], GoldenResult]
    default_rays: int
    expected_runtime_s: float


def run_case(
    case: GoldenCase,
    rays_override: Optional[int] = None,
    verbose: bool = False,
) -> GoldenResult:
    """Build a case's project, run the tracer, produce a GoldenResult with .passed set."""
    from backlight_sim.sim.tracer import RayTracer  # lazy — keeps import cheap
    project = case.build_project(rays_override)
    result = RayTracer(project).run()
    gr = case.measure(project, result)
    gr.passed = bool(gr.residual < gr.tolerance)
    if verbose:
        status = "PASS" if gr.passed else "FAIL"
        print(
            f"[{status}] {gr.name}: residual={gr.residual:.4g} "
            f"tol={gr.tolerance:.4g} rays={gr.rays}"
        )
    return gr


# Populated by Waves 1-3 via module-level appends in conftest-import helpers
# OR via explicit `from ... import CASE` + `ALL_CASES.append(CASE)` in each
# case file. Wave 0 leaves this empty — Wave 1/2/3 wire entries.
ALL_CASES: list[GoldenCase] = []
