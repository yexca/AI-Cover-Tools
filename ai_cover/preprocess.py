from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from types import ModuleType

from .separator_runner import AudioItem


def preprocess_group_inputs(config: ModuleType, group_name: str, items: list[AudioItem]) -> list[AudioItem]:
    if not bool(getattr(config, "PREPROCESS_INPUTS", True)):
        return items

    output_dir = Path(config.WORK_OUTPUTS_DIR) / f"{group_name}-inputs1"
    output_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("ai_cover.preprocess")
    converted: list[AudioItem] = []

    for item in items:
        target = output_dir / f"{item.original_id}.wav"
        if target.exists() and not bool(getattr(config, "PREPROCESS_OVERWRITE", True)):
            converted.append(AudioItem(original_id=item.original_id, current_path=target))
            continue

        if item.current_path.suffix.lower() == ".wav" and _can_copy_wav(config):
            shutil.copy2(item.current_path, target)
            logger.info("Copied WAV input: %s -> %s", item.current_path, target)
        else:
            _convert_to_wav(config, item.current_path, target)
            logger.info("Converted input to WAV: %s -> %s", item.current_path, target)

        converted.append(AudioItem(original_id=item.original_id, current_path=target))

    return converted


def _can_copy_wav(config: ModuleType) -> bool:
    return getattr(config, "PREPROCESS_SAMPLE_RATE", None) is None and getattr(config, "PREPROCESS_CHANNELS", None) is None


def _convert_to_wav(config: ModuleType, source: Path, target: Path) -> None:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source)]

    sample_rate = getattr(config, "PREPROCESS_SAMPLE_RATE", None)
    channels = getattr(config, "PREPROCESS_CHANNELS", None)
    if sample_rate:
        command.extend(["-ar", str(sample_rate)])
    if channels:
        command.extend(["-ac", str(channels)])

    wav_codec = str(getattr(config, "PREPROCESS_WAV_CODEC", "pcm_s24le"))
    command.extend(["-c:a", wav_codec, str(target)])

    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg was not found. Run run-install.bat or install FFmpeg before running the pipeline.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Failed to convert input audio to WAV: {source}") from exc
