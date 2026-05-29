# Configuration

Configuration has two layers:

- `app/config/defaults.py`: application defaults.
- `config.py`: user-facing CLI overrides.

The loader reads defaults first and overlays user config.

## Root Config

Root `config.py` currently owns the most commonly edited separation keys:

- `MODEL_BATCH_SIZE`
- `MODEL_OVERLAP`
- `MODEL_SEGMENT_SIZE`
- `MODEL_OVERRIDE_SEGMENT_SIZE`
- `MODEL_PIPELINE`

Example:

```python
MODEL_PIPELINE = [
    {
        "label": "vocals",
        "model_filename": "mel_band_roformer_kim_ft3_unwa.ckpt",
        "keep_stem": "vocals",
        "stem_aliases": ["Vocals", "vocal"],
        "pitch_shift": 0,
    },
]
```

Each step can override detailed separator settings with:

- `mdx_params`
- `vr_params`
- `demucs_params`
- `mdxc_params`
- `separator_options`

## Default Paths

From `app/config/defaults.py`:

- `ROOT_DIR`
- `INPUTS_DIR`
- `WORK_OUTPUTS_DIR`
- `ARCHIVE_DIR`
- `MODELS_DIR`

## Preprocessing

- `PREPROCESS_INPUTS`
- `PREPROCESS_OUTPUT_FORMAT`
- `PREPROCESS_WAV_CODEC`
- `PREPROCESS_SAMPLE_RATE`
- `PREPROCESS_CHANNELS`
- `PREPROCESS_OVERWRITE`

The separation workflow preprocesses source files into stable numbered WAV inputs before model steps.

## Final Outputs

- `FINAL_OUTPUT_PREFIX`
- `FINAL_OUTPUT_TIME_FORMAT`
- `FINAL_OUTPUT_GROUP_SUBDIRS`

These control archive names and whether final files are grouped by input folder.

## Dependency Setup

- `USE_LOCAL_AUDIO_SEPARATOR_SOURCE`
- `AUDIO_SEPARATOR_SOURCE_DIR`
- `AUDIO_SEPARATOR_INSTALL_EXTRA`
- `PYTORCH_CUDA_INDEX_URLS`
- `AUTO_INSTALL_DEPENDENCIES`
- `VERIFY_RELATED_MODEL_FILES`

`run-install.bat` is still the preferred full environment setup path.

## Runtime

- `AUDIO_EXTENSIONS`
- `RECURSIVE_INPUT_SCAN`
- `STOP_ON_ERROR`
- `CLEAN_WORK_OUTPUTS_BEFORE_RUN`
- `CLEAN_WORK_OUTPUTS_AFTER_SUCCESS`
- `LOG_LEVEL`

## Separator Defaults

Common separator options:

- `output_format`
- `output_bitrate`
- `normalization_threshold`
- `amplification_threshold`
- `invert_using_spec`
- `sample_rate`
- `use_soundfile`
- `use_autocast`
- `chunk_duration`
- `output_single_stem`

Architecture defaults:

- `DEFAULT_MDX_PARAMS`
- `DEFAULT_VR_PARAMS`
- `DEFAULT_DEMUCS_PARAMS`
- `DEFAULT_MDXC_PARAMS`

## GUI-Generated Config

The Separate GUI page writes:

```text
user_data/gui_separate_config.py
```

That generated config imports uppercase values from root `config.py`, then overrides common model settings and `MODEL_PIPELINE` from the GUI controls.

Do not edit `user_data/gui_separate_config.py` by hand; it is generated before GUI separation runs.

## Tool Settings

Tool settings currently live in widget state, not persistent config.

Defaults:

- audio quality segment length: 10 minutes
- duration input folder: `inputs`
- pitch input folder: `inputs`
- pitch algorithm: `Praat`
- normalize input folder: `inputs`
- normalize output folder: `outputs`
- normalize target peak: `-3.0 dB`
