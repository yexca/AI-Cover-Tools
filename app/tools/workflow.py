from __future__ import annotations

import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile
from PIL import Image, ImageDraw, ImageFont
from scipy import signal


AUDIO_EXTENSIONS = {".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aac", ".wma"}
SEGMENT_SECONDS = 10 * 60


@dataclass(frozen=True)
class SpectrogramSegment:
    index: int
    start_seconds: float
    end_seconds: float
    image_path: Path


@dataclass(frozen=True)
class AudioQualityResult:
    source_path: Path
    output_dir: Path
    duration_seconds: float
    sample_rate: int
    channels: int
    segments: list[SpectrogramSegment]


@dataclass(frozen=True)
class DurationSummary:
    directory: Path
    file_count: int
    failed_count: int
    total_seconds: float

    @property
    def formatted(self) -> str:
        seconds = int(round(self.total_seconds))
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        remaining = seconds % 60
        return f"{hours} h {minutes} m {remaining} s"


@dataclass(frozen=True)
class PitchFileSummary:
    file_name: str
    voiced_frames: int
    minimum_hz: float | None
    maximum_hz: float | None
    error: str | None = None


@dataclass(frozen=True)
class PitchReport:
    directory: Path
    file_count: int
    failed_count: int
    voiced_frames: int
    absolute_min_hz: float | None
    absolute_max_hz: float | None
    primary_peak_hz: float | None
    effective_min_hz: float | None
    effective_max_hz: float | None
    plot_path: Path | None
    files: list[PitchFileSummary]

    def to_text(self) -> str:
        lines = [
            f"Files scanned: {self.file_count}",
            f"Failed files: {self.failed_count}",
            f"Voiced frames: {self.voiced_frames}",
        ]
        if self.voiced_frames == 0:
            lines.append("No valid voiced pitch frames were detected.")
            return "\n".join(lines)

        lines.extend(
            [
                f"Absolute raw range: {self.absolute_min_hz:.1f} Hz to {self.absolute_max_hz:.1f} Hz",
                f"Primary pitch concentration: ~{self.primary_peak_hz:.1f} Hz",
                f"Effective RVC target range: {self.effective_min_hz:.1f} Hz to {self.effective_max_hz:.1f} Hz",
            ]
        )
        if self.plot_path is not None:
            lines.append(f"Distribution plot: {self.plot_path}")
        lines.append("")
        lines.append("Per-file ranges:")
        for item in self.files:
            if item.error:
                lines.append(f"- {item.file_name}: failed ({item.error})")
            elif item.voiced_frames == 0:
                lines.append(f"- {item.file_name}: no valid voiced speech detected")
            else:
                lines.append(f"- {item.file_name}: {item.minimum_hz:.1f} Hz - {item.maximum_hz:.1f} Hz")
        return "\n".join(lines)


def iter_audio_files(directory: Path) -> list[Path]:
    directory = directory.expanduser().resolve()
    if not directory.exists():
        return []
    return sorted(path for path in directory.rglob("*") if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS)


def analyze_audio_quality(audio_path: Path, output_root: Path, segment_seconds: int = SEGMENT_SECONDS) -> AudioQualityResult:
    audio_path = audio_path.expanduser().resolve()
    if not audio_path.is_file():
        raise FileNotFoundError(audio_path)

    output_dir = output_root.expanduser().resolve() / "audio_quality" / audio_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    with soundfile.SoundFile(audio_path) as audio_file:
        sample_rate = audio_file.samplerate
        channels = audio_file.channels
        total_frames = len(audio_file)
        duration_seconds = total_frames / sample_rate if sample_rate else 0.0
        frames_per_segment = max(1, int(segment_seconds * sample_rate))
        segment_count = max(1, math.ceil(total_frames / frames_per_segment))
        segments: list[SpectrogramSegment] = []

        for index in range(segment_count):
            start_frame = index * frames_per_segment
            frame_count = min(frames_per_segment, max(0, total_frames - start_frame))
            audio_file.seek(start_frame)
            data = audio_file.read(frame_count, dtype="float32", always_2d=True)
            mono = np.mean(data, axis=1) if data.size else np.zeros(1, dtype=np.float32)
            start_seconds = start_frame / sample_rate
            end_seconds = (start_frame + frame_count) / sample_rate
            image_path = output_dir / f"{audio_path.stem}_segment_{index + 1:03d}.png"
            _render_spectrogram(mono, sample_rate, start_seconds, end_seconds, image_path)
            segments.append(
                SpectrogramSegment(
                    index=index,
                    start_seconds=start_seconds,
                    end_seconds=end_seconds,
                    image_path=image_path,
                )
            )

    return AudioQualityResult(
        source_path=audio_path,
        output_dir=output_dir,
        duration_seconds=duration_seconds,
        sample_rate=sample_rate,
        channels=channels,
        segments=segments,
    )


def calculate_total_duration(directory: Path) -> DurationSummary:
    directory = directory.expanduser().resolve()
    files = iter_audio_files(directory)
    total_seconds = 0.0
    failed_count = 0
    for path in files:
        try:
            with soundfile.SoundFile(path) as audio_file:
                if audio_file.samplerate:
                    total_seconds += len(audio_file) / audio_file.samplerate
        except Exception:
            duration = _probe_duration(path)
            if duration is None:
                failed_count += 1
            else:
                total_seconds += duration
    return DurationSummary(directory=directory, file_count=len(files), failed_count=failed_count, total_seconds=total_seconds)


def analyze_dataset_pitch(directory: Path, output_root: Path, outlier_percentile: float = 1.0) -> PitchReport:
    try:
        import parselmouth
    except ImportError as exc:
        raise RuntimeError("praat-parselmouth is not installed. Please run run-install.bat again.") from exc

    directory = directory.expanduser().resolve()
    files = iter_audio_files(directory)
    all_pitch_frames: list[np.ndarray] = []
    summaries: list[PitchFileSummary] = []
    failed_count = 0

    for path in files:
        try:
            sound = parselmouth.Sound(str(path))
            pitch = sound.to_pitch()
            pitch_values = pitch.selected_array["frequency"]
            voiced_frames = pitch_values[pitch_values > 0]
            if len(voiced_frames) == 0:
                summaries.append(PitchFileSummary(path.name, 0, None, None))
                continue
            all_pitch_frames.append(voiced_frames)
            summaries.append(
                PitchFileSummary(
                    file_name=path.name,
                    voiced_frames=int(len(voiced_frames)),
                    minimum_hz=float(np.min(voiced_frames)),
                    maximum_hz=float(np.max(voiced_frames)),
                )
            )
        except Exception as exc:
            failed_count += 1
            summaries.append(PitchFileSummary(path.name, 0, None, None, f"{type(exc).__name__}: {exc}"))

    if not all_pitch_frames:
        return PitchReport(
            directory=directory,
            file_count=len(files),
            failed_count=failed_count,
            voiced_frames=0,
            absolute_min_hz=None,
            absolute_max_hz=None,
            primary_peak_hz=None,
            effective_min_hz=None,
            effective_max_hz=None,
            plot_path=None,
            files=summaries,
        )

    pitch_frames = np.concatenate(all_pitch_frames)
    absolute_min_hz = float(np.min(pitch_frames))
    absolute_max_hz = float(np.max(pitch_frames))
    effective_min_hz = float(np.percentile(pitch_frames, outlier_percentile))
    effective_max_hz = float(np.percentile(pitch_frames, 100.0 - outlier_percentile))
    counts, bin_edges = np.histogram(pitch_frames, bins=50)
    peak_index = int(np.argmax(counts))
    primary_peak_hz = float((bin_edges[peak_index] + bin_edges[peak_index + 1]) / 2)

    plot_dir = output_root.expanduser().resolve() / "pitch"
    plot_dir.mkdir(parents=True, exist_ok=True)
    plot_path = plot_dir / "dataset_pitch_distribution.png"
    _render_pitch_distribution(pitch_frames, effective_min_hz, effective_max_hz, plot_path)

    return PitchReport(
        directory=directory,
        file_count=len(files),
        failed_count=failed_count,
        voiced_frames=int(len(pitch_frames)),
        absolute_min_hz=absolute_min_hz,
        absolute_max_hz=absolute_max_hz,
        primary_peak_hz=primary_peak_hz,
        effective_min_hz=effective_min_hz,
        effective_max_hz=effective_max_hz,
        plot_path=plot_path,
        files=summaries,
    )


def _probe_duration(path: Path) -> float | None:
    ffprobe = _find_ffprobe()
    if ffprobe is None:
        return None
    try:
        completed = subprocess.run(
            [
                str(ffprobe),
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return float(completed.stdout.strip())
    except Exception:
        return None


def _find_ffprobe() -> Path | None:
    executable = shutil.which("ffprobe")
    if executable:
        return Path(executable)
    env_root = Path(sys.executable).resolve().parent
    candidates = [
        env_root / "Library" / "bin" / "ffprobe.exe",
        env_root / "Scripts" / "ffprobe.exe",
        env_root / "ffprobe.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _render_spectrogram(samples: np.ndarray, sample_rate: int, start_seconds: float, end_seconds: float, output_path: Path) -> None:
    samples = np.asarray(samples, dtype=np.float32)
    if samples.size == 0:
        samples = np.zeros(1, dtype=np.float32)

    nperseg = max(1, min(4096, samples.size))
    noverlap = 0 if nperseg == 1 else nperseg // 2
    frequencies, times, spectrogram = signal.spectrogram(
        samples,
        fs=sample_rate,
        window="hann",
        nperseg=nperseg,
        noverlap=noverlap,
        mode="magnitude",
    )
    if spectrogram.size == 0:
        spectrogram = np.zeros((1, 1), dtype=np.float32)
        frequencies = np.array([0.0], dtype=np.float32)
        times = np.array([0.0], dtype=np.float32)

    max_frequency = min(sample_rate / 2, 22050)
    mask = frequencies <= max_frequency
    spectrogram = spectrogram[mask]
    frequencies = frequencies[mask]
    db = 20 * np.log10(np.maximum(spectrogram, 1e-10))
    db = np.clip(db, -120, 0)
    normalized = (db + 120) / 120

    plot_width = 980
    plot_height = 520
    left = 68
    top = 34
    right = 28
    bottom = 54
    image = Image.new("RGB", (plot_width, plot_height), (13, 16, 22))
    draw = ImageDraw.Draw(image)
    plot_box = (left, top, plot_width - right, plot_height - bottom)
    draw.rectangle(plot_box, fill=(5, 7, 12), outline=(70, 78, 94))

    spec_image = _spectrogram_image(normalized, plot_box[2] - plot_box[0], plot_box[3] - plot_box[1])
    image.paste(spec_image, (plot_box[0], plot_box[1]))
    _draw_spectrogram_axes(draw, plot_box, start_seconds, end_seconds, max_frequency)
    title = f"{output_path.stem}  {_format_time(start_seconds)} - {_format_time(end_seconds)}"
    draw.text((left, 10), title, fill=(235, 240, 248), font=_font(14))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def _spectrogram_image(values: np.ndarray, width: int, height: int) -> Image.Image:
    values = np.flipud(values)
    source = Image.fromarray(np.uint8(values * 255), mode="L").resize((width, height), Image.Resampling.BILINEAR)
    arr = np.asarray(source, dtype=np.float32) / 255.0
    colors = np.zeros((height, width, 3), dtype=np.uint8)
    stops = np.array(
        [
            [5, 7, 12],
            [24, 46, 94],
            [46, 116, 166],
            [220, 184, 72],
            [246, 243, 180],
        ],
        dtype=np.float32,
    )
    scaled = arr * (len(stops) - 1)
    lower = np.floor(scaled).astype(np.int32)
    upper = np.clip(lower + 1, 0, len(stops) - 1)
    weight = scaled - lower
    for channel in range(3):
        colors[:, :, channel] = (
            stops[lower, channel] * (1 - weight) + stops[upper, channel] * weight
        ).astype(np.uint8)
    return Image.fromarray(colors, mode="RGB")


def _draw_spectrogram_axes(
    draw: ImageDraw.ImageDraw,
    plot_box: tuple[int, int, int, int],
    start_seconds: float,
    end_seconds: float,
    max_frequency: float,
) -> None:
    left, top, right, bottom = plot_box
    font = _font(11)
    grid_color = (48, 56, 70)
    text_color = (190, 199, 214)
    for index in range(1, 5):
        x = left + (right - left) * index / 5
        draw.line((x, top, x, bottom), fill=grid_color)
        seconds = start_seconds + (end_seconds - start_seconds) * index / 5
        draw.text((x - 22, bottom + 10), _format_time(seconds), fill=text_color, font=font)
    for index in range(0, 5):
        y = bottom - (bottom - top) * index / 4
        draw.line((left, y, right, y), fill=grid_color)
        hz = max_frequency * index / 4
        label = f"{hz / 1000:.1f}k" if hz >= 1000 else f"{hz:.0f}"
        draw.text((10, y - 7), label, fill=text_color, font=font)
    draw.text((left, bottom + 30), "time", fill=text_color, font=font)
    draw.text((10, top - 22), "Hz", fill=text_color, font=font)


def _render_pitch_distribution(
    pitch_frames: np.ndarray,
    effective_min_hz: float,
    effective_max_hz: float,
    output_path: Path,
) -> None:
    width = 980
    height = 420
    left = 62
    top = 28
    right = 24
    bottom = 48
    image = Image.new("RGB", (width, height), (13, 16, 22))
    draw = ImageDraw.Draw(image)
    plot_box = (left, top, width - right, height - bottom)
    draw.rectangle(plot_box, fill=(8, 11, 17), outline=(70, 78, 94))

    counts, edges = np.histogram(pitch_frames, bins=100, density=True)
    max_count = float(np.max(counts)) if counts.size else 1.0
    for index, count in enumerate(counts):
        x1 = left + (plot_box[2] - left) * index / len(counts)
        x2 = left + (plot_box[2] - left) * (index + 1) / len(counts)
        y = plot_box[3] - (plot_box[3] - top) * (float(count) / max_count if max_count else 0)
        draw.rectangle((x1, y, x2, plot_box[3]), fill=(83, 165, 198))

    minimum = float(edges[0])
    maximum = float(edges[-1])
    for value in (effective_min_hz, effective_max_hz):
        x = left + (plot_box[2] - left) * ((value - minimum) / max(1e-9, maximum - minimum))
        draw.line((x, top, x, plot_box[3]), fill=(230, 82, 93), width=2)
        draw.text((x + 4, top + 8), f"{value:.1f} Hz", fill=(240, 210, 214), font=_font(11))

    font = _font(11)
    draw.text((left, height - 30), f"{minimum:.1f} Hz", fill=(190, 199, 214), font=font)
    draw.text((plot_box[2] - 70, height - 30), f"{maximum:.1f} Hz", fill=(190, 199, 214), font=font)
    draw.text((left, 8), "Dataset Pitch Distribution", fill=(235, 240, 248), font=_font(14))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def _format_time(seconds: float) -> str:
    seconds = int(round(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining = seconds % 60
    if hours:
        return f"{hours}:{minutes:02d}:{remaining:02d}"
    return f"{minutes}:{remaining:02d}"


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("segoeui.ttf", size)
    except OSError:
        return ImageFont.load_default()
