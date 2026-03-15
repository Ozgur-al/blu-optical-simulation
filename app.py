"""Blu Optical Simulation — application entry point."""

import sys
import os


def main():
    # 1. Create QApplication (minimal imports so far)
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon

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
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

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
    splash.set_progress(90)
    splash.set_status("Ready")
    app.processEvents()

    # 5. Show main window, close splash
    window.show()
    splash.set_progress(100)
    app.processEvents()
    splash.close()

    # 6. Check for updates (non-blocking, after window is visible)
    from backlight_sim.update_checker import check_for_update_async

    def _on_update_check(info):
        """Called from background thread when update check completes."""
        if info.available:
            # Use QTimer.singleShot to safely show notification from main thread
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: _show_update_notification(window, info))

    def _show_update_notification(parent, info):
        """Show a non-modal update notification in the status bar."""
        msg = (
            f"Update available: v{info.latest_version} "
            f"(current: v{info.current_version})"
        )
        if hasattr(parent, "statusBar"):
            parent.statusBar().showMessage(msg, 15000)  # Show for 15 seconds

    check_for_update_async(_on_update_check)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
