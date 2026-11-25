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
import re
import threading
import urllib.request
from dataclasses import dataclass, field

from backlight_sim.__version__ import __version__

# ---------------------------------------------------------------------------
# Configuration — update URL is abstracted so it can be swapped later
# ---------------------------------------------------------------------------
_GITHUB_OWNER = "Ozgur-al"
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
_VERSION_RE = re.compile(
    r"^\s*v?(\d+(?:\.\d+)*)"              # release: 1, 1.2, 1.2.3 ...
    r"(?:[-_.]?([A-Za-z]+)[-_.]?(\d*))?"     # pre-release: -beta, rc1, .dev2
    r"(?:\+[0-9A-Za-z.-]*)?\s*$"            # build metadata (ignored)
)

# Pre-release labels in increasing order; a final release sorts after all.
_PRE_RANK = {"dev": 0, "a": 1, "alpha": 1, "b": 2, "beta": 2,
             "pre": 3, "c": 3, "rc": 3}
_FINAL_RANK = 10


def _parse_version(text: str) -> tuple:
    """Parse ``"1.2.3"``, ``"v1.2"``, ``"1.1.0-beta"``, ``"2.0rc1"`` ...

    Returns a sortable key ``(release_tuple_padded, pre_rank, pre_num)``.
    Trailing zeros are stripped so ``1.0 == 1.0.0``; a final release ranks
    above any of its pre-releases.  Raises ``ValueError`` on garbage.
    """
    m = _VERSION_RE.match(text or "")
    if not m:
        raise ValueError(f"unparseable version: {text!r}")
    release = [int(x) for x in m.group(1).split(".")]
    while len(release) > 1 and release[-1] == 0:
        release.pop()
    label = (m.group(2) or "").lower()
    if not label:
        rank, num = _FINAL_RANK, 0
    else:
        if label not in _PRE_RANK:
            raise ValueError(f"unknown pre-release label in {text!r}")
        rank, num = _PRE_RANK[label], int(m.group(3) or 0)
    return (tuple(release), rank, num)


def _compare_versions(current: str, latest: str) -> bool:
    """Return True if latest is strictly newer than current.

    Understands pre-release tags (``1.1.0-beta`` < ``1.1.0``) and treats
    ``1.0`` and ``1.0.0`` as equal.  Falls back to False on any parse error
    so the app never crashes on a malformed tag.
    """
    try:
        c = _parse_version(current)
        la = _parse_version(latest)
    except (ValueError, TypeError, AttributeError):
        return False
    # Compare release tuples with zero padding.
    n = max(len(c[0]), len(la[0]))
    ck = (c[0] + (0,) * (n - len(c[0])), c[1], c[2])
    lk = (la[0] + (0,) * (n - len(la[0])), la[1], la[2])
    return lk > ck


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

        if not isinstance(data, dict):
            return UpdateInfo(available=False, error="Unexpected response format")
        tag = str(data.get("tag_name") or "").strip().lstrip("vV")
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
