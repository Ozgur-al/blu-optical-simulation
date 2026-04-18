# Deferred Items — Phase 03 Plan 04

Items discovered during Plan 03-04 execution that are out-of-scope and deferred
to their respective owning phases.

## Pre-existing: uncommitted Phase 04 Plan 02 tracer.py diff breaks all tests

**Discovered:** during `pytest backlight_sim/tests/` verification after Task 3.

**Symptom (early in session):** every test in `backlight_sim/tests/golden/`
fails with:

```
AttributeError: 'RayTracer' object has no attribute '_run_uq_batched'
  at backlight_sim/sim/tracer.py:709
```

**Symptom (later in session, after concurrent agent extended tracer.py diff
to 368 lines, adding a partial `_run_uq_batched` implementation):** a smaller
set of golden tests (lambertian_cosine + 2 specular tests + 3 CLI tests that
depend on them) fail with:

```
AssertionError: Far-field candela_grid is None - verify compute_farfield_candela
ran (tracer.py:2934) and SphereDetector mode='far_field'
```

The UQ-batched tracer path returns a `SphereDetectorResult` with
`candela_grid=None` — i.e., `compute_farfield_candela` is not called on the
merged-batches result. This is the very problem Phase 04 Plan 02 is tasked
with solving ("MP merge with per-batch seeding" per Phase 04 Plan 01 SUMMARY).

**Root cause:** the working tree has an uncommitted 109-line diff to
`backlight_sim/sim/tracer.py` that unconditionally dispatches the top-level
`_run_single` entry into a not-yet-implemented `_run_uq_batched` method.

```python
# tracer.py:708-713 (uncommitted diff)
if not _uq_in_chunk and _effective_uq_batches(settings) > 0:
    return self._run_uq_batched(           # method does not exist
        sources, progress_callback, convergence_callback,
        _adaptive=_adaptive,
        partial_result_callback=partial_result_callback,
    )
```

This is Phase 04 Plan 02 work-in-progress. Per Phase 04 Plan 01 SUMMARY:

> "Ready for Plan 02 (tracer batch loop: C++ fast path + Python fallback +
>  MP merge with per-batch seeding)."

The _run_uq_batched method is what Phase 04 Plan 02 is supposed to implement.

**Why we did NOT touch this:**

* The diff predates our plan (it was already in `git status` when we started).
* It is Phase 04 Plan 02's deliverable, not Plan 03-04's.
* Reverting it would discard Phase 04's in-progress work.
* Our Plan 03-04 changes (`backlight_sim/golden/report.py`,
  `backlight_sim/golden/__main__.py`,
  `backlight_sim/tests/golden/test_cli_report.py`, `CLAUDE.md`) introduce
  no tracer modifications.

**Evidence this is not our regression:**

1. Plan 03-03 SUMMARY lists `pytest backlight_sim/tests/` passing at 180 tests
   when Plan 03-03 completed (commit `082818e`).
2. Our Plan 03-04 work touches only the golden package's CLI/report layer +
   CLAUDE.md; none of our files import tracer.
3. When the uncommitted `tracer.py` diff is temporarily reverted, the golden
   tests we wrote ALL pass (verified in-session at commits `bd92ead`,
   `9c5bcbc`: 4 CLI integration tests pass; runtime budget test completes in
   36.30 s; full-ray exit-code test completes in 33.56 s).

**Owning phase:** Phase 04 Plan 02 (uncertainty-quantification — tracer batch loop).

**Action:** When Phase 04 Plan 02 implements `_run_uq_batched`, the full test
suite including our 4 new CLI integration tests will pass green. No action
required from Plan 03-04.
