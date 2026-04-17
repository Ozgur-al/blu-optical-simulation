---
phase: 2
slug: converting-main-simulation-loop-to-cpp-for-faster-computation
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-18
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.0+ (already installed) |
| **Config file** | none — run from repo root |
| **Quick run command** | `pytest backlight_sim/tests/test_tracer.py -x -q` |
| **Full suite command** | `pytest backlight_sim/tests/ -q` |
| **Estimated runtime** | ~30 seconds (quick), ~60 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `pytest backlight_sim/tests/test_tracer.py -x -q`
- **After every plan wave:** Run `pytest backlight_sim/tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| C++-01 | 01 | 1 | C++-01 | — | N/A | smoke | `python -c "from backlight_sim.sim import blu_tracer"` | Wave 0 | ⬜ pending |
| C++-02 | 01 | 1 | C++-02 | — | N/A | unit | `pytest tests/test_cpp_tracer.py::test_trace_source_returns_valid_dict` | Wave 0 (new) | ⬜ pending |
| C++-03 | 02 | 2 | C++-03 | — | N/A | regression | `pytest backlight_sim/tests/test_tracer.py -q` | ✅ exists | ⬜ pending |
| C++-04 | 01 | 1 | C++-04 | — | N/A | unit | `pytest tests/test_cpp_tracer.py::test_determinism` | Wave 0 (new) | ⬜ pending |
| C++-05 | 02 | 2 | C++-05 | — | N/A | physics | `pytest tests/test_cpp_tracer.py::test_energy_conservation` | Wave 0 (new) | ⬜ pending |
| C++-06 | 04 | 4 | C++-06 | — | N/A | regression | `pytest tests/test_cpp_tracer.py::test_statistical_equivalence` | Wave 0 (new) | ⬜ pending |
| C++-07 | 04 | 4 | C++-07 | — | N/A | perf | `pytest tests/test_cpp_tracer.py::test_speedup -s` | Wave 0 (new) | ⬜ pending |
| C++-08 | 03 | 3 | C++-08 | — | N/A | regression | `pytest tests/test_cpp_tracer.py::test_no_numba_imports` | Wave 0 (new) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backlight_sim/tests/test_cpp_tracer.py` — new file covering C++-01 through C++-08 (stubs initially)
- [ ] `backlight_sim/sim/_blu_tracer/` directory — create in Wave 0 with CMakeLists.txt and C++ source stubs
- [ ] `blu_tracer.cp312-win_amd64.pyd` — built by Wave 0 build task, checked into repo

*Note: Existing 20 tests in `test_tracer.py` cover regression — Wave 0 adds new C++ specific tests.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 3–8x speedup vs Numba baseline on typical scene | C++-07 (perf) | Requires timing measurement with real ray counts; CI variability | Run `pytest tests/test_cpp_tracer.py::test_speedup -s` and observe printed timing ratios |
| .pyd loads on a clean machine without MSVC installed | D-07/D-08 | Requires a separate machine/env | Copy `blu_tracer.cp312-win_amd64.pyd` to clean venv, run smoke test |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
