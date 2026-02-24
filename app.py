"""Blu Optical Simulation — application entry point."""

import sys
from PySide6.QtWidgets import QApplication
from backlight_sim.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Blu Optical Simulation")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
