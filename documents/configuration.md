# Configuration

Configuration is split into two layers:

- `config.py`: user-facing CLI configuration. Keep commonly edited model pipeline and shared model parameters here.
- `app/config/defaults.py`: application defaults for paths, preprocessing, dependency setup, separator defaults, and future GUI defaults.

The loader merges `app/config/defaults.py` first, then overlays `config.py`.

Root `config.py` currently owns:

- `MODEL_BATCH_SIZE`
- `MODEL_OVERLAP`
- `MODEL_SEGMENT_SIZE`
- `MODEL_OVERRIDE_SEGMENT_SIZE`
- `MODEL_PIPELINE`

Shared model parameters are applied to every `MODEL_PIPELINE` step unless that step explicitly overrides the same key.

Default paths:

- `ROOT_DIR`: project root.
- `INPUTS_DIR`: source audio folders. The program reads from here and does not modify user audio.
- `WORK_OUTPUTS_DIR`: intermediate outputs.
- `ARCHIVE_DIR`: completed run folders.
- `MODELS_DIR`: local model cache for `audio-separator`.

Preprocessing:

- `PREPROCESS_INPUTS`: enables copy/convert into stable WAV files.
- `PREPROCESS_WAV_CODEC`: WAV codec used for conversion.
- `PREPROCESS_SAMPLE_RATE`: optional sample rate override.
- `PREPROCESS_CHANNELS`: optional channel count override.
- `PREPROCESS_OVERWRITE`: whether to replace existing preprocessed files.

Runtime:

- `AUDIO_EXTENSIONS`: accepted source audio suffixes.
- `RECURSIVE_INPUT_SCAN`: scans nested files inside input group folders.
- `STOP_ON_ERROR`: stops the whole run when a group or model step fails.
- `CLEAN_WORK_OUTPUTS_BEFORE_RUN`: clears `outputs` before starting.
- `LOG_LEVEL`: console and file logging level.

Dependency setup defaults:

- `USE_LOCAL_AUDIO_SEPARATOR_SOURCE`: use `sample/python-audio-separator` when available.
- `AUDIO_SEPARATOR_SOURCE_DIR`: local source checkout path.
- `AUDIO_SEPARATOR_INSTALL_EXTRA`: `gpu`, `cpu`, or `dml`.
- `PYTORCH_CUDA_INDEX_URLS`: CUDA wheel indexes tried by the installer.
- `AUTO_INSTALL_DEPENDENCIES`: allows automatic dependency installation.
- `VERIFY_RELATED_MODEL_FILES`: lets `audio-separator` fetch related model data files.

GUI dependency:

- PySide6 is installed by `run-install.bat` into the local conda environment.
- The installer first checks whether `from PySide6.QtWidgets import QApplication` works.
- If it does not work, the installer tries conda-forge, then pip as a fallback.
- The installer does not inspect or reuse system Python or system conda.
- If the project `env` exists, it uses that local env directly.
- If the project `env` does not exist, it downloads Miniconda into `env/conda` and creates `env`.
- Existing PySide6, PyTorch, audio-separator, and ONNX Runtime installs are checked before downloading anything.

Model pipeline:

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

Each step can override architecture parameters with `mdx_params`, `vr_params`, `demucs_params`, `mdxc_params`, and `separator_options`.
