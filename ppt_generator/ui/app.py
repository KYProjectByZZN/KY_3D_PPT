"""Desktop application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def create_application(argv: list[str] | None = None) -> QApplication:
    application = QApplication.instance() or QApplication(argv or sys.argv)
    application.setApplicationName("KY AI PPT Studio")
    application.setOrganizationName("KY Project")
    application.setStyle("Fusion")
    application.setFont(QFont("Microsoft YaHei UI", 10))
    return application


def main() -> int:
    application = create_application()
    window = MainWindow()
    window.show()
    return application.exec()
