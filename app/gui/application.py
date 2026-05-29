from __future__ import annotations

import sys

from .bootstrap import configure_windows_dll_paths

configure_windows_dll_paths()

from PySide6.QtWidgets import QApplication

from .i18n.translator import Translator
from .main_window import MainWindow


def run_gui() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("AI-Cover")
    app.setOrganizationName("AI-Cover")

    translator = Translator.from_system_locale()
    window = MainWindow(translator)
    window.show()

    return app.exec()
