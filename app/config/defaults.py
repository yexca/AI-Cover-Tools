from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]

INPUTS_DIR = ROOT_DIR / "inputs"
WORK_OUTPUTS_DIR = ROOT_DIR / "outputs"
ARCHIVE_DIR = ROOT_DIR / "archives"
MODELS_DIR = ROOT_DIR / "models"

PREPROCESS_INPUTS = True
PREPROCESS_OUTPUT_FORMAT = "wav"
PREPROCESS_WAV_CODEC = "pcm_s24le"
PREPROCESS_SAMPLE_RATE = None
PREPROCESS_CHANNELS = None
PREPROCESS_OVERWRITE = True

FINAL_OUTPUT_PREFIX = "outputs"
FINAL_OUTPUT_TIME_FORMAT = "%Y%m%d-%H%M%S"
FINAL_OUTPUT_GROUP_SUBDIRS = True

USE_LOCAL_AUDIO_SEPARATOR_SOURCE = True
AUDIO_SEPARATOR_SOURCE_DIR = ROOT_DIR / "sample" / "python-audio-separator"
AUDIO_SEPARATOR_INSTALL_EXTRA = "gpu"
PYTORCH_CUDA_INDEX_URLS = [
    "https://download.pytorch.org/whl/cu128",
    "https://download.pytorch.org/whl/cu126",
    "https://download.pytorch.org/whl/cu124",
    "https://download.pytorch.org/whl/cu121",
]
AUTO_INSTALL_DEPENDENCIES = True
VERIFY_RELATED_MODEL_FILES = True

AUDIO_EXTENSIONS = {
    ".wav",
    ".flac",
    ".mp3",
    ".ogg",
    ".opus",
    ".m4a",
    ".aiff",
    ".aif",
    ".ac3",
}

RECURSIVE_INPUT_SCAN = True
STOP_ON_ERROR = True
CLEAN_WORK_OUTPUTS_BEFORE_RUN = True
CLEAN_WORK_OUTPUTS_AFTER_SUCCESS = False

LOG_LEVEL = "INFO"

COMMON_SEPARATOR_OPTIONS = {
    "output_format": "WAV",
    "output_bitrate": None,
    "normalization_threshold": 0.9,
    "amplification_threshold": 0.0,
    "invert_using_spec": False,
    "sample_rate": 44100,
    "use_soundfile": False,
    "use_autocast": False,
    "chunk_duration": None,
    "output_single_stem": False,
}

DEFAULT_MDX_PARAMS = {
    "hop_length": 1024,
    "segment_size": 256,
    "overlap": 0.25,
    "batch_size": 1,
    "enable_denoise": False,
}

DEFAULT_VR_PARAMS = {
    "batch_size": 1,
    "window_size": 512,
    "aggression": 5,
    "enable_tta": False,
    "enable_post_process": False,
    "post_process_threshold": 0.2,
    "high_end_process": False,
}

DEFAULT_DEMUCS_PARAMS = {
    "segment_size": "Default",
    "shifts": 2,
    "overlap": 0.25,
    "segments_enabled": True,
}

DEFAULT_MDXC_PARAMS = {
    "segment_size": 256,
    "override_model_segment_size": False,
    "batch_size": 1,
    "overlap": 8,
    "pitch_shift": 0,
}
