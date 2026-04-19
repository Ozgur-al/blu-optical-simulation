"""Simulation package bootstrap helpers."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from importlib.machinery import EXTENSION_SUFFIXES
from pathlib import Path
from types import ModuleType


def _iter_extension_candidates() -> list[Path]:
    """Return plausible on-disk locations for the compiled tracer module.

    The editable source checkout does not always contain ``blu_tracer`` next to
    the Python package, but packaged builds place the compiled module under the
    bundled app's ``_internal/backlight_sim/sim`` directory. Search both so the
    source tree can reuse an already-built binary when present.
    """
    package_dir = Path(__file__).resolve().parent
    repo_root = package_dir.parents[1]
    search_roots = [
        package_dir,
        repo_root / "dist" / "BluOpticalSim" / "_internal" / "backlight_sim" / "sim",
        repo_root / "build",
    ]

    candidates: list[Path] = []
    for root in search_roots:
        if not root.exists():
            continue
        for suffix in EXTENSION_SUFFIXES:
            pattern = f"blu_tracer*{suffix}"
            if root.name == "build":
                candidates.extend(sorted(root.rglob(pattern)))
            else:
                candidates.extend(sorted(root.glob(pattern)))
    return candidates


def _load_blu_tracer() -> tuple[ModuleType | None, Exception | None]:
    """Load the optional compiled extension, if available."""
    module_name = f"{__name__}.blu_tracer"
    first_error: Exception | None = None

    try:
        return importlib.import_module(module_name), None
    except ImportError as exc:
        first_error = exc

    for candidate in _iter_extension_candidates():
        try:
            spec = importlib.util.spec_from_file_location(module_name, candidate)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            return module, None
        except Exception as exc:  # pragma: no cover - platform-specific loader errors
            first_error = exc
            sys.modules.pop(module_name, None)

    return None, first_error


blu_tracer, cpp_extension_error = _load_blu_tracer()

__all__ = ["blu_tracer", "cpp_extension_error"]
