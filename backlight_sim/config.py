"""Application configuration constants and user data directory resolution.

This module provides:
- App identity constants (name, version, organisation)
- User data directory path (platform-aware, %LOCALAPPDATA% on Windows)
- ensure_user_data_dir() helper that creates the directory on first access

Constraints: NO PySide6 imports — this module must be importable from
headless/server contexts (io/, sim/) as well as the GUI layer.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from backlight_sim.__version__ import __version__

__all__ = [
    "APP_NAME",
    "APP_VERSION",
    "APP_ORG",
    "user_data_dir",
    "ensure_user_data_dir",
]

APP_NAME: str = "Blu Optical Simulation"
APP_VERSION: str = __version__
APP_ORG: str = "BluOptical"


def user_data_dir() -> Path:
    """Return the platform-appropriate user data directory.

    Windows: ``%LOCALAPPDATA%\\BluOpticalSim``  (e.g. C:\\Users\\<user>\\AppData\\Local\\BluOpticalSim)
    Other:   ``~/.bluopticalsim``

    The directory is *not* created; call :func:`ensure_user_data_dir` if you
    need it to exist on disk.
    """
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "BluOpticalSim"
        # Fallback: LOCALAPPDATA not set (unusual, but handle gracefully)
        return Path.home() / "AppData" / "Local" / "BluOpticalSim"
    return Path.home() / ".bluopticalsim"


def ensure_user_data_dir() -> Path:
    """Create the user data directory (and any parents) if it does not exist.

    Returns the resolved :class:`pathlib.Path` so callers can chain
    ``ensure_user_data_dir() / "settings.json"`` immediately.
    """
    path = user_data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path
