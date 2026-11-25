"""Blu Optical Simulation — application entry point."""

import sys
import os


def main():
    # 1. Create QApplication (minimal imports so far)
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon

    # On Windows the taskbar groups by process AppUserModelID. Without an
    # explicit ID, python.exe owns the grouping and the taskbar shows the
    # generic Python icon regardless of setWindowIcon. Must be set BEFORE
    # the first window is shown.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "BluOptical.Simulation.2.0"
            )
        except (AttributeError, OSError):
            pass

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Blu Optical Simulation")
    app.setOrganizationName("BluOptical")

    # 2. Set application icon — works in dev mode and PyInstaller frozen mode
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_path, "assets", "icon.ico")
    app_icon = QIcon(icon_path) if os.path.exists(icon_path) else None
    if app_icon is not None:
        app.setWindowIcon(app_icon)

    # 3. Apply dark theme and show splash (theme must come before any pg widget)
    from backlight_sim.gui.theme import apply_dark_theme, BG_BASE, TEXT_PRIMARY
    import pyqtgraph as pg
    pg.setConfigOption("background", BG_BASE)
    pg.setConfigOption("foreground", TEXT_PRIMARY)
    apply_dark_theme(app)

    from backlight_sim.gui.splash import SplashScreen
    splash = SplashScreen()
    splash.show()
    app.processEvents()

    # 4. Staged loading with progress updates
    splash.set_status("Loading modules...")
    splash.set_progress(20)
    app.processEvents()

    from backlight_sim.gui.main_window import MainWindow
    splash.set_progress(60)
    splash.set_status("Initializing GUI...")
    app.processEvents()

    window = MainWindow()
    if app_icon is not None:
        window.setWindowIcon(app_icon)
    splash.set_progress(90)
    splash.set_status("Ready")
    app.processEvents()

    # 5. Show main window, close splash
    window.show()
    splash.set_progress(100)
    app.processEvents()
    splash.close()

    # 6. Check for updates (non-blocking, after window is visible)
    from PySide6.QtCore import QObject, Signal, Slot, Qt as _Qt
    from backlight_sim.update_checker import check_for_update_async

    class _UpdateNotifier(QObject):
        # Emitted from the checker's plain Python thread.  The receiver (this
        # QObject) lives in the GUI thread, so the queued connection runs the
        # slot on the GUI thread.  (QTimer.singleShot called from a non-Qt
        # thread has no event loop to fire in, so the old code never showed.)
        update_available = Signal(object)

        def __init__(self, parent):
            super().__init__(parent)
            self.update_available.connect(
                self._show, _Qt.ConnectionType.QueuedConnection
            )

        @Slot(object)
        def _show(self, info):
            """Show a non-modal update notification in the status bar."""
            msg = (
                f"Update available: v{info.latest_version} "
                f"(current: v{info.current_version})"
            )
            if hasattr(window, "statusBar"):
                window.statusBar().showMessage(msg, 15000)  # 15 seconds

    notifier = _UpdateNotifier(window)  # parented: lives in the GUI thread

    def _on_update_check(info):
        """Called from background thread when update check completes."""
        if info.available:
            notifier.update_available.emit(info)

    check_for_update_async(_on_update_check)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
