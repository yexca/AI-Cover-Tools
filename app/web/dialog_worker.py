from __future__ import annotations

import json
import os
import sys
from pathlib import Path


RESULT_PREFIX = "AUDIOFLOW_DIALOG_RESULT="


def main() -> None:
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QApplication, QFileDialog

    kind = os.environ["AUDIOFLOW_DIALOG_KIND"]
    title = os.environ["AUDIOFLOW_DIALOG_TITLE"]
    initial_path = os.environ.get("AUDIOFLOW_INITIAL_PATH", "")
    audio_label = os.environ.get("AUDIOFLOW_AUDIO_LABEL", "Audio files")
    audio_filter = os.environ.get("AUDIOFLOW_AUDIO_FILTER", "*.wav")

    app = QApplication(sys.argv[:1])
    dialog = QFileDialog()
    dialog.setWindowTitle(title)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    dialog.setOption(QFileDialog.Option.DontUseNativeDialog, False)

    candidate = Path(initial_path).expanduser() if initial_path else None
    if candidate and candidate.is_file():
        dialog.setDirectory(str(candidate.parent))
        dialog.selectFile(candidate.name)
    elif candidate and candidate.is_dir():
        dialog.setDirectory(str(candidate))

    if kind == "audio_file":
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setNameFilter(f"{audio_label} ({audio_filter})")
    elif kind in {"input_directory", "output_directory"}:
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
    else:
        raise ValueError(f"Unsupported dialog kind: {kind}")

    QTimer.singleShot(0, lambda: (dialog.raise_(), dialog.activateWindow()))
    selected = dialog.selectedFiles()[0] if dialog.exec() and dialog.selectedFiles() else ""
    print(f"{RESULT_PREFIX}{json.dumps({'path': selected}, ensure_ascii=False)}", flush=True)
    app.quit()


if __name__ == "__main__":
    main()
