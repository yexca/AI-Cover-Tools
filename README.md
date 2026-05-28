# AI-Cover

AI-Cover is a local batch pipeline for preparing AI cover training data. It reads audio from `inputs`, converts every source file into clean numbered WAV files, then runs the configured `audio-separator` model chain. User input files are never modified.

## Folder Layout

```text
inputs/
  Kano/
    your original files here
  nameless/
    your original files here
models/
outputs/
outputs-YYYYmmdd-HHMMSS/
env/
```

- `inputs`: user-provided source folders. Files inside are ignored by git.
- `outputs`: intermediate files, including converted first-step WAV files.
- `models`: downloaded `audio-separator` models and related model data.
- `outputs-YYYYmmdd-HHMMSS`: final WAV files from a completed run.
- `env`: local Python environment created by `run-install.bat`.

## Install

```bat
run-install.bat
```

The installer creates `env`, installs Python 3.12 and FFmpeg, then installs GPU-enabled `audio-separator` dependencies first. If GPU dependency installation fails, it falls back to CPU dependencies. When `sample/python-audio-separator` exists, the installer uses that local source; otherwise it installs from PyPI.

## Run

```bat
run.bat
```

Useful commands:

```bat
run.bat --dry-run
run.bat --preprocess-only
run.bat --download-models-only
```

`--preprocess-only` converts or copies files from `inputs/<group>` into `outputs/<group>-inputs1/01.wav`, `02.wav`, and so on. This is useful for checking non-English filenames and MP3 conversion before downloading models.

## Processing Flow

1. Find folders under `inputs`, such as `Kano` and `nameless`.
2. Sort audio files inside each folder.
3. Convert or copy every file into WAV under `outputs/<group>-inputs1`.
4. Run each model in `MODEL_PIPELINE` in order.
5. Put each model's raw output under `outputs/<group>-outputs<step>-<label>`.
6. Copy the configured target stem into the next input folder as a clean WAV.
7. Copy final WAV files into `outputs-YYYYmmdd-HHMMSS`.

## Config Reference

Edit `config.py`.

`ROOT_DIR`: Project root. Usually leave this as-is.

`INPUTS_DIR`: Where user source folders live. The program reads from here and does not write processed files here.

`WORK_OUTPUTS_DIR`: Where all intermediate folders are created.

`PREPROCESS_INPUTS`: Enables the first conversion/renaming stage. Keep this `True` for stable ASCII WAV inputs.

`PREPROCESS_OUTPUT_FORMAT`: Preprocess output extension. This should stay `"wav"` because the pipeline expects WAV.

`PREPROCESS_WAV_CODEC`: WAV codec used when decoding non-WAV inputs. The default is `"pcm_s24le"` to avoid unnecessary bit-depth reduction for lossless sources.

`PREPROCESS_SAMPLE_RATE`: Optional sample rate for converted WAV files. `None` preserves the source rate when possible.

`PREPROCESS_CHANNELS`: Optional channel count. `None` preserves the source channel layout when possible.

`PREPROCESS_OVERWRITE`: Whether preprocessing replaces existing `outputs/<group>-inputs1/*.wav`.

`FINAL_OUTPUT_PREFIX`: Prefix for final output folders.

`FINAL_OUTPUT_TIME_FORMAT`: Timestamp format used in final output folder names.

`FINAL_OUTPUT_GROUP_SUBDIRS`: If `True`, final results are grouped by singer/source folder.

`MODELS_DIR`: Local model cache used by `audio-separator`.

`USE_LOCAL_AUDIO_SEPARATOR_SOURCE`: If `True`, install/import from `sample/python-audio-separator`.

`AUDIO_SEPARATOR_SOURCE_DIR`: Path to the optional local `python-audio-separator` source checkout.

`AUDIO_SEPARATOR_INSTALL_EXTRA`: Dependency flavor. The default is `"gpu"` so compatible NVIDIA/CUDA systems are used first. Use `"cpu"` for CPU-only machines or `"dml"` for DirectML.

`AUTO_INSTALL_DEPENDENCIES`: If `True`, missing Python dependencies are installed automatically when possible.

`VERIFY_RELATED_MODEL_FILES`: If `True`, model checks also let `audio-separator` fetch related YAML/data files.

`AUDIO_EXTENSIONS`: Source audio suffixes the scanner accepts.

`RECURSIVE_INPUT_SCAN`: If `True`, files nested inside input subfolders are also scanned.

`STOP_ON_ERROR`: If `True`, the whole run stops when one group or model step fails.

`CLEAN_WORK_OUTPUTS_BEFORE_RUN`: If `True`, deletes `outputs` before each run so old intermediate files cannot conflict with the new run.

`CLEAN_WORK_OUTPUTS_AFTER_SUCCESS`: If `True`, deletes intermediate `outputs` after a successful full run.

`LOG_LEVEL`: Console and file logging level, such as `"INFO"` or `"DEBUG"`.

`COMMON_SEPARATOR_OPTIONS`: General options passed to `audio-separator`.

- `output_format`: Forced to `"WAV"` for this project.
- `output_bitrate`: Usually `None` for WAV.
- `normalization_threshold`: Peak normalization target used by `audio-separator`.
- `amplification_threshold`: Minimum amplification threshold.
- `invert_using_spec`: Uses spectrogram inversion for secondary stems when supported.
- `sample_rate`: Output sample rate requested from `audio-separator`.
- `use_soundfile`: Alternate writer that may help with long audio.
- `use_autocast`: Faster GPU inference when supported.
- `chunk_duration`: Optional chunk length in seconds for long files.
- `output_single_stem`: If `False`, writes all stems and AI-Cover keeps the target stem. This is safer for mixed models.

`DEFAULT_MDX_PARAMS`, `DEFAULT_VR_PARAMS`, `DEFAULT_DEMUCS_PARAMS`, `DEFAULT_MDXC_PARAMS`: Architecture defaults passed to `audio-separator`. Step-level values override these.

`MODEL_PIPELINE`: Ordered model steps. Each item supports:

- `label`: Short output label, used in folder and file names, such as `vocals` or `dereverb`.
- `model_filename`: Exact model filename to load or download.
- `keep_stem`: Target stem to keep and pass to the next step.
- `stem_aliases`: Alternate stem names that may appear in model output.
- `segment_size`: Processing segment size.
- `override_model_segment_size`: Whether to override a model's own segment size.
- `overlap`: Overlap between processing windows.
- `batch_size`: Inference batch size.
- `pitch_shift`: Semitone shift used by supported MDXC/Roformer models.
- `mdx_params`, `vr_params`, `demucs_params`, `mdxc_params`: Optional per-step architecture-specific overrides.
- `separator_options`: Optional per-step overrides for `COMMON_SEPARATOR_OPTIONS`.

## Git

The repository keeps folder placeholders under `inputs`, but ignores real input audio. It also ignores generated or local-only folders such as `env`, `models`, `outputs`, `outputs-*`, and `sample`.
