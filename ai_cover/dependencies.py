from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
from types import ModuleType


def ensure_audio_separator_available(config: ModuleType) -> None:
    source_dir = Path(getattr(config, "AUDIO_SEPARATOR_SOURCE_DIR", "sample/python-audio-separator"))
    use_local = bool(getattr(config, "USE_LOCAL_AUDIO_SEPARATOR_SOURCE", True))

    if use_local and source_dir.exists():
        source_text = str(source_dir.resolve())
        if source_text not in sys.path:
            sys.path.insert(0, source_text)

    if _can_import_separator():
        return

    if not bool(getattr(config, "AUTO_INSTALL_DEPENDENCIES", True)):
        raise RuntimeError("audio-separator is not installed. Enable AUTO_INSTALL_DEPENDENCIES or run run-install.bat.")

    _install_audio_separator(config)

    if use_local and source_dir.exists():
        importlib.invalidate_caches()
        source_text = str(source_dir.resolve())
        if source_text not in sys.path:
            sys.path.insert(0, source_text)

    if not _can_import_separator():
        raise RuntimeError("audio-separator could not be imported after installation.")


def _can_import_separator() -> bool:
    try:
        importlib.import_module("audio_separator.separator")
        return True
    except Exception:
        return False


def _install_audio_separator(config: ModuleType) -> None:
    if not (3, 10) <= sys.version_info[:2] <= (3, 13):
        raise RuntimeError(
            "audio-separator requires Python 3.10-3.13. "
            "Run run-install.bat to create the local Python 3.12 environment, then use run.bat."
        )

    source_dir = Path(getattr(config, "AUDIO_SEPARATOR_SOURCE_DIR", "sample/python-audio-separator")).resolve()
    extra = str(getattr(config, "AUDIO_SEPARATOR_INSTALL_EXTRA", "cpu")).strip()
    extra_suffix = f"[{extra}]" if extra else ""

    if bool(getattr(config, "USE_LOCAL_AUDIO_SEPARATOR_SOURCE", True)) and source_dir.exists():
        cmd = [sys.executable, "-m", "pip", "install", "-e", f".{extra_suffix}"]
        cwd = source_dir
    else:
        cmd = [sys.executable, "-m", "pip", "install", f"audio-separator{extra_suffix}"]
        cwd = None

    print("Installing audio-separator dependencies. This may take a while...")
    subprocess.run(cmd, cwd=cwd, check=True)
