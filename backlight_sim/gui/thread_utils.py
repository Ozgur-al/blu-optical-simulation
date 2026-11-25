"""Shared helpers for stopping worker QThreads safely.

A QThread must never be destroyed while it is still running (Qt aborts the
process).  Dialogs call :func:`stop_thread` from ``done()`` so Close / Esc /
window-X all cancel the worker; threads that do not stop within the timeout
are parked in a module-level registry (keeping them alive) and the main
window waits for them on exit via :func:`wait_lingering_threads`.
"""

from __future__ import annotations

from PySide6.QtCore import QThread

_LINGERING: set[QThread] = set()


def stop_thread(thread: QThread | None, timeout_ms: int = 3000) -> bool:
    """Cancel *thread* and wait up to *timeout_ms*.  Returns True when stopped."""
    if thread is None or not thread.isRunning():
        return True
    cancel = getattr(thread, "cancel", None)
    if callable(cancel):
        cancel()
    if thread.wait(timeout_ms):
        return True
    # Still busy (e.g. mid ray-trace): keep a strong reference until it ends.
    _LINGERING.add(thread)
    thread.finished.connect(lambda t=thread: _LINGERING.discard(t))
    return False


def wait_lingering_threads(timeout_ms: int = 10000) -> bool:
    """Cancel and wait for every parked thread.  Returns True when all stopped."""
    ok = True
    for t in list(_LINGERING):
        cancel = getattr(t, "cancel", None)
        if callable(cancel):
            cancel()
        if t.wait(timeout_ms):
            _LINGERING.discard(t)
        else:
            ok = False
    return ok
