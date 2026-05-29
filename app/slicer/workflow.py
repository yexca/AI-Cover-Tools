from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile

from .engine import Slicer


SUPPORTED_AUDIO_EXTENSIONS = {
    ".wav",
    ".flac",
    ".mp3",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".wma",
    ".aiff",
    ".aif",
}
SUPPORTED_OUTPUT_FORMATS = {"wav", "flac", "mp3"}


@dataclass(frozen=True)
class SlicerSettings:
    threshold: float = -40.0
    min_length: int = 5000
    min_interval: int = 300
    hop_size: int = 10
    max_sil_kept: int = 1000


@dataclass(frozen=True)
class SlicerFileResult:
    source_path: Path
    success: bool
    output_paths: tuple[Path, ...] = ()
    error: str = ""

    @property
    def output_count(self) -> int:
        return len(self.output_paths)


@dataclass(frozen=True)
class SlicerRunResult:
    input_dir: Path
    output_dir: Path
    output_format: str
    files: tuple[SlicerFileResult, ...]

    @property
    def source_count(self) -> int:
        return len(self.files)

    @property
    def success_count(self) -> int:
        return sum(1 for file in self.files if file.success)

    @property
    def output_count(self) -> int:
        return sum(file.output_count for file in self.files)

    @property
    def failed_count(self) -> int:
        return sum(1 for file in self.files if not file.success)


def run_slicer(
    input_dir: str | Path,
    output_dir: str | Path,
    output_format: str = "wav",
    settings: SlicerSettings | None = None,
) -> SlicerRunResult:
    input_path = Path(input_dir).expanduser().resolve()
    output_path = Path(output_dir).expanduser().resolve()
    normalized_format = output_format.lower().lstrip(".")
    slicer_settings = settings or SlicerSettings()

    if normalized_format not in SUPPORTED_OUTPUT_FORMATS:
        raise ValueError(f"Unsupported output format: {output_format}")
    if not input_path.exists() or not input_path.is_dir():
        raise FileNotFoundError(f"Input folder does not exist: {input_path}")

    output_path.mkdir(parents=True, exist_ok=True)
    audio_files = discover_audio_files(input_path)
    results = tuple(
        run_slicing_task(source, output_path, normalized_format, slicer_settings)
        for source in audio_files
    )
    return SlicerRunResult(
        input_dir=input_path,
        output_dir=output_path,
        output_format=normalized_format,
        files=results,
    )


def discover_audio_files(input_dir: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in input_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
        ),
        key=lambda path: str(path).lower(),
    )


def run_slicing_task(
    source_path: Path,
    output_dir: Path,
    output_format: str,
    settings: SlicerSettings,
) -> SlicerFileResult:
    written_paths: list[Path] = []

    try:
        ranges, sample_rate, channels = analyze_slicing_task(source_path, settings)
        target_dir = output_dir / source_path.stem
        target_dir.mkdir(parents=True, exist_ok=True)

        for index, (begin, end) in enumerate(ranges):
            output_path = target_dir / f"{source_path.stem}_{index:03d}.{output_format}"
            write_slice_range(source_path, output_path, sample_rate, channels, begin, end)
            written_paths.append(output_path)
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
        return SlicerFileResult(
            source_path=source_path,
            success=False,
            output_paths=tuple(written_paths),
            error=message,
        )

    return SlicerFileResult(
        source_path=source_path,
        success=True,
        output_paths=tuple(written_paths),
    )


def analyze_slicing_task(
    source_path: Path,
    settings: SlicerSettings,
) -> tuple[list[tuple[int, int]], int, int]:
    with soundfile.SoundFile(source_path) as source_file:
        sample_rate = source_file.samplerate
        channels = source_file.channels
        total_samples = len(source_file)

        slicer = Slicer(
            sr=sample_rate,
            threshold=settings.threshold,
            min_length=settings.min_length,
            min_interval=settings.min_interval,
            hop_size=settings.hop_size,
            max_sil_kept=settings.max_sil_kept,
        )

        if (total_samples + slicer.hop_size - 1) // slicer.hop_size <= slicer.min_length:
            return [(0, total_samples)], sample_rate, channels

        rms_list = build_rms_list_from_file(source_file, slicer)
        ranges = slicer.slice_ranges_from_rms(rms_list, total_samples)
        return ranges, sample_rate, channels


def build_rms_list_from_file(
    source_file: soundfile.SoundFile,
    slicer: Slicer,
    read_size: int = 131072,
) -> np.ndarray:
    source_file.seek(0)
    pad = slicer.win_size // 2
    buffer = np.zeros(pad, dtype=np.float32)
    rms_parts: list[np.ndarray] = []

    while True:
        chunk = source_file.read(read_size, dtype="float32", always_2d=True)
        if len(chunk) == 0:
            break
        mono = chunk.mean(axis=1, dtype=np.float32)
        buffer = np.concatenate((buffer, mono.astype(np.float32, copy=False)))
        values, buffer = _consume_rms_frames(buffer, slicer)
        if values.size:
            rms_parts.append(values)

    buffer = np.concatenate((buffer, np.zeros(pad, dtype=np.float32)))
    values, _ = _consume_rms_frames(buffer, slicer)
    if values.size:
        rms_parts.append(values)

    if not rms_parts:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(rms_parts)


def write_slice_range(
    source_path: Path,
    output_path: Path,
    sample_rate: int,
    channels: int,
    begin: int,
    end: int,
    chunk_size: int = 65536,
) -> None:
    frames_remaining = max(0, end - begin)
    with (
        soundfile.SoundFile(source_path) as source_file,
        soundfile.SoundFile(output_path, mode="w", samplerate=sample_rate, channels=channels) as output_file,
    ):
        source_file.seek(begin)
        while frames_remaining > 0:
            block = source_file.read(min(chunk_size, frames_remaining), dtype="float32", always_2d=True)
            if len(block) == 0:
                break
            output_file.write(block)
            frames_remaining -= len(block)


def _consume_rms_frames(buffer: np.ndarray, slicer: Slicer) -> tuple[np.ndarray, np.ndarray]:
    if buffer.shape[0] < slicer.win_size:
        return np.zeros(0, dtype=np.float32), buffer

    usable = ((buffer.shape[0] - slicer.win_size) // slicer.hop_size) + 1
    window_view = np.lib.stride_tricks.sliding_window_view(buffer, slicer.win_size)
    windows = window_view[:: slicer.hop_size][:usable]
    rms_values = np.sqrt(np.mean(np.abs(windows) ** 2, axis=1, dtype=np.float64)).astype(np.float32)
    remaining = buffer[usable * slicer.hop_size :]
    return rms_values, remaining
