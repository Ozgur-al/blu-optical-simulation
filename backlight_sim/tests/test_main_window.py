"""Small tests for main window helpers that do not require full UI construction."""

from __future__ import annotations


def test_cpp_status_helpers_reflect_extension_availability(monkeypatch):
    from backlight_sim.gui import main_window as main_window_mod

    monkeypatch.setattr(main_window_mod, "_blu_tracer", None)
    assert main_window_mod._cpp_active() is False
    assert main_window_mod._cpp_status_text() == "C++: Off"
    assert "pure Python" in main_window_mod._cpp_status_log_message()

    monkeypatch.setattr(main_window_mod, "_blu_tracer", object())
    assert main_window_mod._cpp_active() is True
    assert main_window_mod._cpp_status_text() == "C++: Active"
    assert "blu_tracer extension loaded" in main_window_mod._cpp_status_log_message()
