from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent

# User input lives here. The pipeline treats this directory as read-only.
INPUTS_DIR = ROOT_DIR / "inputs"

# Intermediate step outputs and next-step inputs live here.
WORK_OUTPUTS_DIR = ROOT_DIR / "outputs"

# Every input file is first copied or converted into WAV here:
# WORK_OUTPUTS_DIR / f"{group_name}-inputs1".
PREPROCESS_INPUTS = True
PREPROCESS_OUTPUT_FORMAT = "wav"
PREPROCESS_WAV_CODEC = "pcm_s24le"
PREPROCESS_SAMPLE_RATE = None
PREPROCESS_CHANNELS = None
PREPROCESS_OVERWRITE = True

# Final results are copied into ROOT_DIR / f"{FINAL_OUTPUT_PREFIX}-{timestamp}".
FINAL_OUTPUT_PREFIX = "outputs"
FINAL_OUTPUT_TIME_FORMAT = "%Y%m%d-%H%M%S"
FINAL_OUTPUT_GROUP_SUBDIRS = True

# Model cache used by audio-separator.
MODELS_DIR = ROOT_DIR / "models"

# Prefer the sample checkout you placed in this project. If it is missing,
# the installer falls back to installing audio-separator from PyPI.
USE_LOCAL_AUDIO_SEPARATOR_SOURCE = True
AUDIO_SEPARATOR_SOURCE_DIR = ROOT_DIR / "sample" / "python-audio-separator"
AUDIO_SEPARATOR_INSTALL_EXTRA = "cpu"  # cpu, gpu, or dml
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
CLEAN_WORK_OUTPUTS_BEFORE_RUN = False
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
    # Leave False unless you are certain the configured stem name matches the
    # model exactly. False is slower but safer for unknown models.
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

# Edit this list to change the order of processing. keep_stem is the target
# product to pass to the next model and to keep in the final output.
MODEL_PIPELINE = [
    {
        "label": "vocals",
        "model_filename": "mel_band_roformer_kim_ft3_unwa.ckpt",
        "keep_stem": "vocals",
        "stem_aliases": ["Vocals", "vocal"],
        "segment_size": 256,
        "override_model_segment_size": False,
        "overlap": 8,
        "batch_size": 1,
        "pitch_shift": 0,
    },
    {
        "label": "dechorus",
        "model_filename": "mel_band_roformer_karaoke_gabox_v2.ckpt",
        "keep_stem": "vocals",
        "stem_aliases": ["Vocals", "Lead Vocals", "lead_vocals", "vocal"],
        "segment_size": 256,
        "override_model_segment_size": False,
        "overlap": 8,
        "batch_size": 1,
        "pitch_shift": 0,
    },
    {
        "label": "dereverb",
        "model_filename": "dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt",
        "keep_stem": "noreverb",
        "stem_aliases": ["No Reverb", "NoReverb", "noreverb", "dry", "Dry"],
        "segment_size": 256,
        "override_model_segment_size": False,
        "overlap": 8,
        "batch_size": 1,
        "pitch_shift": 0,
    },
]
