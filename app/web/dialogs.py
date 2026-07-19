from __future__ import annotations

import ipaddress
import json
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from .formats import AUDIO_EXTENSIONS


_DIALOG_LOCK = threading.Lock()
_DIALOG_TITLES = {
    "en": {
        "audio_file": "Select audio file",
        "input_directory": "Select input audio folder",
        "output_directory": "Select output folder",
        "audio_files": "Audio files",
    },
    "zh-CN": {
        "audio_file": "选择音频文件",
        "input_directory": "选择输入音频文件夹",
        "output_directory": "选择输出文件夹",
        "audio_files": "音频文件",
    },
    "ja": {
        "audio_file": "音声ファイルを選択",
        "input_directory": "入力音声フォルダーを選択",
        "output_directory": "出力フォルダーを選択",
        "audio_files": "音声ファイル",
    },
}

class DialogError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class DialogBusyError(DialogError):
    def __init__(self) -> None:
        super().__init__("dialog_busy", "Another native path dialog is already open.")


class DialogRequest(BaseModel):
    kind: Literal["audio_file", "input_directory", "output_directory"]
    initial_path: str | None = None
    locale: Literal["zh-CN", "ja", "en"] = "en"


def is_loopback_client(host: str | None) -> bool:
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host.split("%")[0])
    except ValueError:
        return False
    if address.is_loopback:
        return True
    return bool(address.version == 6 and address.ipv4_mapped and address.ipv4_mapped.is_loopback)


def _load_tk() -> tuple[Any, Any]:
    import tkinter as tk
    from tkinter import filedialog

    return tk, filedialog


def _initial_options(initial_path: str | None) -> dict[str, str]:
    if not initial_path:
        return {}
    candidate = Path(initial_path).expanduser()
    if candidate.is_file():
        return {"initialdir": str(candidate.parent), "initialfile": candidate.name}
    if candidate.is_dir():
        return {"initialdir": str(candidate)}
    parent = candidate.parent
    while parent != parent.parent and not parent.exists():
        parent = parent.parent
    return {"initialdir": str(parent)} if parent.exists() else {}


def _audio_file_types(locale: str) -> list[tuple[str, str]]:
    label = _DIALOG_TITLES.get(locale, _DIALOG_TITLES["en"])["audio_files"]
    return [
        (label, " ".join(f"*{extension}" for extension in sorted(AUDIO_EXTENSIONS))),
        ("WAV", "*.wav"),
        ("FLAC", "*.flac"),
        ("MP3", "*.mp3"),
    ]


def _pick_path_tk(kind: str, initial_path: str | None, locale: str) -> str:
    root = None
    try:
        tk, filedialog = _load_tk()
        titles = _DIALOG_TITLES.get(locale, _DIALOG_TITLES["en"])
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update_idletasks()
        options = {"parent": root, **_initial_options(initial_path)}
        if kind == "audio_file":
            selected = filedialog.askopenfilename(
                title=titles["audio_file"], filetypes=_audio_file_types(locale), **options
            )
        elif kind == "input_directory":
            options.pop("initialfile", None)
            selected = filedialog.askdirectory(title=titles["input_directory"], mustexist=True, **options)
        elif kind == "output_directory":
            options.pop("initialfile", None)
            selected = filedialog.askdirectory(title=titles["output_directory"], mustexist=False, **options)
        else:
            raise ValueError(f"Unsupported dialog kind: {kind}")
        return str(selected)
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                logging.getLogger("ai_cover.web").warning("Unable to destroy native dialog root", exc_info=True)


def _pick_path_windows(kind: str, initial_path: str | None, locale: str) -> str:
    titles = _DIALOG_TITLES.get(locale, _DIALOG_TITLES["en"])
    environment = os.environ.copy()
    environment.update(
        {
            "AUDIOFLOW_DIALOG_KIND": kind,
            "AUDIOFLOW_DIALOG_TITLE": titles[kind],
            "AUDIOFLOW_AUDIO_LABEL": titles["audio_files"],
            "AUDIOFLOW_AUDIO_FILTER": ";".join(f"*{extension}" for extension in sorted(AUDIO_EXTENSIONS)),
            "AUDIOFLOW_INITIAL_PATH": initial_path or "",
        }
    )
    startupinfo_factory = getattr(subprocess, "STARTUPINFO", None)
    startupinfo = startupinfo_factory() if startupinfo_factory else None
    if startupinfo is not None:
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 1  # SW_SHOWNORMAL
    completed = subprocess.run(
        [sys.executable, "-m", "app.web.dialog_worker"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        cwd=str(Path(__file__).resolve().parents[2]),
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        startupinfo=startupinfo,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "Unable to open the system path picker."
        raise DialogError("dialog_failed", message)
    marker = "AUDIOFLOW_DIALOG_RESULT="
    result_line = next((line for line in completed.stdout.splitlines() if line.startswith(marker)), None)
    if result_line is None:
        raise DialogError("dialog_failed", "The system path picker returned an invalid response.")
    try:
        result = json.loads(result_line.removeprefix(marker))
    except json.JSONDecodeError as exc:
        raise DialogError("dialog_failed", "The system path picker returned invalid JSON.") from exc
    return str(result.get("path") or "")


def _pick_dialog_backend(kind: str, initial_path: str | None, locale: str) -> str:
    if os.name == "nt":
        return _pick_path_windows(kind, initial_path, locale)
    return _pick_path_tk(kind, initial_path, locale)


def pick_path(kind: str, initial_path: str | None = None, locale: str = "en") -> dict[str, Any]:
    """Open one native dialog. Must be called from a request worker thread."""

    if not _DIALOG_LOCK.acquire(blocking=False):
        raise DialogBusyError()
    try:
        selected = _pick_dialog_backend(kind, initial_path, locale)
        if kind == "audio_file" and selected and Path(selected).suffix.lower() not in AUDIO_EXTENSIONS:
            raise DialogError("unsupported_audio_file", f"Unsupported audio file type: {Path(selected).suffix or selected}")
        return {"path": str(Path(selected).resolve()) if selected else None, "cancelled": not bool(selected), "error": None}
    finally:
        _DIALOG_LOCK.release()
