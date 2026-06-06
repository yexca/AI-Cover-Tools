from __future__ import annotations

import sys

from .bootstrap import configure_windows_dll_paths

configure_windows_dll_paths()

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from .i18n.translator import Translator
from .main_window import MainWindow
from .paths import APP_ICON


def run_gui() -> int:
    print("Starting AI Cover Tools GUI...", flush=True)
    app = QApplication(sys.argv)
    app.setApplicationName("AI Cover Tools")
    app.setOrganizationName("AI Cover Tools")
    if APP_ICON.exists():
        app.setWindowIcon(QIcon(str(APP_ICON)))

    translator = Translator.from_system_locale()
    window = MainWindow(translator)
    window.statusBar().messageChanged.connect(lambda message: print(message, flush=True) if message else None)
    window.show()

    exit_code = app.exec()
    print(f"AI Cover Tools GUI exited with code {exit_code}.", flush=True)
    return exit_code
