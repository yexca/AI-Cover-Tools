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
    extra = str(getattr(config, "AUDIO_SEPARATOR_INSTALL_EXTRA", "gpu")).strip()
    cuda_index_urls = list(
        getattr(
            config,
            "PYTORCH_CUDA_INDEX_URLS",
            [
                "https://download.pytorch.org/whl/cu128",
                "https://download.pytorch.org/whl/cu126",
                "https://download.pytorch.org/whl/cu124",
                "https://download.pytorch.org/whl/cu121",
            ],
        )
    )

    if extra.lower() == "gpu":
        _install_cuda_torch(cuda_index_urls)

    if bool(getattr(config, "USE_LOCAL_AUDIO_SEPARATOR_SOURCE", True)) and source_dir.exists():
        primary = [sys.executable, "-m", "pip", "install", "-e", _editable_extra(extra)]
        fallback = [sys.executable, "-m", "pip", "install", "-e", ".[cpu]"]
        _run_install_with_cpu_fallback(primary, fallback, source_dir, extra)
    else:
        primary = [sys.executable, "-m", "pip", "install", _package_extra(extra)]
        fallback = [sys.executable, "-m", "pip", "install", "audio-separator[cpu]"]
        _run_install_with_cpu_fallback(primary, fallback, None, extra)


def _editable_extra(extra: str) -> str:
    return f".[{extra}]" if extra else "."


def _package_extra(extra: str) -> str:
    return f"audio-separator[{extra}]" if extra else "audio-separator"


def _run_install_with_cpu_fallback(primary: list[str], fallback: list[str], cwd: Path | None, extra: str) -> None:
    print("Installing audio-separator dependencies. This may take a while...")
    try:
        subprocess.run(primary, cwd=cwd, check=True)
    except subprocess.CalledProcessError:
        if extra.lower() == "cpu":
            raise
        print("GPU dependency installation failed. Falling back to CPU dependencies...")
        subprocess.run(fallback, cwd=cwd, check=True)


def _install_cuda_torch(cuda_index_urls: list[str]) -> None:
    for cuda_index_url in cuda_index_urls:
        command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--force-reinstall",
            "torch",
            "torchvision",
            "torchaudio",
            "--index-url",
            cuda_index_url,
        ]
        try:
            subprocess.run(command, check=True)
            return
        except subprocess.CalledProcessError:
            continue

    print("CUDA PyTorch installation failed for all configured CUDA wheel sources. Falling back to default PyTorch package...")
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "torch", "torchvision", "torchaudio"], check=True)
