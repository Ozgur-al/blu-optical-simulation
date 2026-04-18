"""GOLD-06: integration tests for ``python -m backlight_sim.golden --report``.

Spawns the CLI as a subprocess (``sys.executable`` for env portability),
asserts both report files are created, and verifies every registered case
name is present in the markdown output - the regression guard that catches
a dropped case. Uses ``--rays 5000`` for CI speed where applicable; these
tests verify WIRING and artifact coverage, not physics accuracy.

Pattern: mirrors tempfile + subprocess usage in
``test_tracer.py::test_project_serialization_new_fields``. Uses pytest's
``tmp_path`` fixture on Windows-aware platforms (no hardcoded /tmp paths).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from backlight_sim.golden.cases import ALL_CASES


def test_cli_report_writes_html_and_markdown(tmp_path: Path):
    """CLI produces both report artifacts; every registered case name appears in markdown."""
    assert ALL_CASES, "ALL_CASES is empty - Plans 02/03 must populate it first"
    out = tmp_path / "golden_report"
    cmd = [
        sys.executable,
        "-m",
        "backlight_sim.golden",
        "--report",
        "--out",
        str(out),
        "--rays",
        "5000",  # small - we test wiring, not physics accuracy
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    # Non-zero exit allowed IF ray-count reduction caused a physics case to
    # miss its tolerance - this test is about artifacts + case coverage,
    # not physics. test_cli_exits_zero_when_all_pass covers exit code.
    assert (out / "report.html").exists(), (
        f"report.html missing. stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert (out / "report.md").exists(), (
        f"report.md missing. stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )

    md_text = (out / "report.md").read_text(encoding="utf-8")
    # Regression guard: every registered case must appear in the report.
    missing = [c.name for c in ALL_CASES if c.name not in md_text]
    assert not missing, f"Case names missing from report: {missing}"

    html_text = (out / "report.html").read_text(encoding="utf-8")
    assert "Golden-Reference Validation Report" in html_text
    assert "<table" in html_text


def test_cli_exits_zero_when_all_pass(tmp_path: Path):
    """Full-ray-count run - confirms CLI returns 0 on a green suite."""
    out = tmp_path / "golden_report"
    cmd = [
        sys.executable,
        "-m",
        "backlight_sim.golden",
        "--report",
        "--out",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, (
        f"CLI returned {proc.returncode} - some cases failed.\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )


def test_cli_cases_filter(tmp_path: Path):
    """``--cases`` flag filters to the named subset."""
    assert ALL_CASES
    first_case_name = ALL_CASES[0].name
    out = tmp_path / "golden_report"
    cmd = [
        sys.executable,
        "-m",
        "backlight_sim.golden",
        "--report",
        "--out",
        str(out),
        "--cases",
        first_case_name,
        "--rays",
        "5000",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    md_path = out / "report.md"
    assert md_path.exists(), (
        f"report.md missing from filtered run.\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    md_text = md_path.read_text(encoding="utf-8")
    assert first_case_name in md_text
    # A second, distinct case name must NOT appear in the filtered report.
    if len(ALL_CASES) > 1:
        other_name = ALL_CASES[1].name
        if other_name != first_case_name:
            assert other_name not in md_text, (
                f"--cases filter didn't exclude {other_name}"
            )


def test_golden_suite_runtime_under_budget():
    """VALIDATION.md 300 s hard budget - enforced as a test assertion.

    Invokes the FULL golden suite via pytest in a subprocess with an
    absolute 300-second timeout. If the suite ever slips past this budget,
    ``subprocess.run`` raises ``TimeoutExpired`` and the test fails loudly.

    This is the single gate that enforces the Phase 03 runtime budget at
    the test-suite level (Warning #3 from checker feedback). Excludes this
    test file from the inner pytest invocation to avoid infinite recursion.
    """
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "backlight_sim/tests/golden/",
                "--ignore=backlight_sim/tests/golden/test_cli_report.py",
                "-x",
                "-q",
            ],
            timeout=300,  # VALIDATION.md hard budget - do not raise without re-deriving tolerances
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(
            f"Golden suite exceeded 300 s runtime budget (VALIDATION.md GOLD-08). "
            f"Partial stdout:\n{exc.stdout!r}\n"
            f"Partial stderr:\n{exc.stderr!r}"
        ) from None
    assert proc.returncode == 0, (
        f"Golden suite failed (not a timeout).\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
