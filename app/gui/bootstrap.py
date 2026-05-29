from __future__ import annotations

import os
import sys
from pathlib import Path


def configure_windows_dll_paths() -> None:
    if sys.platform != "win32" or not hasattr(os, "add_dll_directory"):
        return

    env_root = Path(sys.executable).resolve().parent
    candidates = [
        env_root / "Lib" / "site-packages" / "PySide6",
        env_root,
        env_root / "DLLs",
        env_root / "Library" / "bin",
    ]
    for path in candidates:
        if path.exists():
            os.add_dll_directory(str(path))
