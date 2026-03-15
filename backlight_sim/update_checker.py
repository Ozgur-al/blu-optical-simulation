"""Non-blocking update checker for Blu Optical Simulation.

Uses stdlib only (urllib.request, json, threading, dataclasses).
No PySide6 imports — safe to call from any thread.

Usage:
    # Blocking (for testing):
    from backlight_sim.update_checker import check_for_update
    info = check_for_update(timeout=5.0)

    # Non-blocking (preferred for GUI startup):
    from backlight_sim.update_checker import check_for_update_async
    check_for_update_async(callback=lambda info: print(info))
"""

from __future__ import annotations

import json
import threading
import urllib.request
from dataclasses import dataclass, field

from backlight_sim.__version__ import __version__

# ---------------------------------------------------------------------------
# Configuration — update URL is abstracted so it can be swapped later
# ---------------------------------------------------------------------------
_GITHUB_OWNER = "blu-optical"
_GITHUB_REPO = "blu-optical-simulation"
_UPDATE_URL = (
    f"https://api.github.com/repos/{_GITHUB_OWNER}/{_GITHUB_REPO}/releases/latest"
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class UpdateInfo:
    """Result of an update check."""

    available: bool
    current_version: str = __version__
    latest_version: str = ""
    download_url: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Version comparison (no external dependencies)
# ---------------------------------------------------------------------------
def _compare_versions(current: str, latest: str) -> bool:
    """Return True if latest is strictly newer than current.

    Compares dot-separated integer tuples.  Falls back to False on any parse
    error so the app never crashes on a malformed tag.
    """
    try:
        c = tuple(int(x) for x in current.strip().split("."))
        la = tuple(int(x) for x in latest.strip().split("."))
        return la > c
    except (ValueError, AttributeError):
        return False


# ---------------------------------------------------------------------------
# Core (blocking) check
# ---------------------------------------------------------------------------
def check_for_update(
    timeout: float = 5.0,
    url: str = _UPDATE_URL,
) -> UpdateInfo:
    """Check for a newer release.

    Makes a single HTTP GET to ``url`` with ``timeout`` seconds.  Returns an
    :class:`UpdateInfo` dataclass regardless of what happens on the network —
    it NEVER raises.

    Parameters
    ----------
    timeout:
        Seconds before the request times out.  Keep short (default 5 s) so
        corporate proxy/firewall hangs do not affect startup.
    url:
        GitHub Releases API endpoint.  Override for testing.

    Returns
    -------
    UpdateInfo
        ``available=True`` only when the remote version is strictly newer.
        ``available=False`` (with ``error`` populated) on any failure.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": f"BluOpticalSim/{__version__}",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        tag = data.get("tag_name", "").lstrip("v")
        download = data.get("html_url", "")

        if not tag:
            return UpdateInfo(available=False, error="Empty tag_name in response")

        is_newer = _compare_versions(__version__, tag)
        return UpdateInfo(
            available=is_newer,
            latest_version=tag,
            download_url=download,
        )

    except Exception as exc:  # noqa: BLE001 — intentional broad catch
        return UpdateInfo(available=False, error=str(exc))


# ---------------------------------------------------------------------------
# Non-blocking async wrapper
# ---------------------------------------------------------------------------
def check_for_update_async(
    callback,
    timeout: float = 5.0,
    url: str = _UPDATE_URL,
) -> threading.Thread:
    """Run :func:`check_for_update` in a daemon thread.

    Parameters
    ----------
    callback:
        Callable that receives a single :class:`UpdateInfo` argument.  Called
        from the background thread — if you need to update Qt widgets, marshal
        the call back to the main thread using ``QTimer.singleShot(0, ...)``.
    timeout:
        Forwarded to :func:`check_for_update`.
    url:
        Forwarded to :func:`check_for_update`.

    Returns
    -------
    threading.Thread
        The daemon thread (already started).  Callers can ignore the return
        value; it is provided for testing convenience.
    """

    def _run() -> None:
        info = check_for_update(timeout=timeout, url=url)
        try:
            callback(info)
        except Exception:  # noqa: BLE001
            pass  # Never let the callback crash the daemon thread

    t = threading.Thread(target=_run, daemon=True, name="update-checker")
    t.start()
    return t
