"""Blu Optical Simulation — application entry point."""

import sys
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from backlight_sim.gui.theme import apply_dark_theme, BG_BASE, TEXT_PRIMARY


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Blu Optical Simulation")
    app.setOrganizationName("BluOptical")

    # Apply dark theme BEFORE constructing any widgets — pyqtgraph picks up
    # the global config options set inside apply_dark_theme().
    pg.setConfigOption("background", BG_BASE)
    pg.setConfigOption("foreground", TEXT_PRIMARY)
    apply_dark_theme(app)

    from backlight_sim.gui.main_window import MainWindow
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
