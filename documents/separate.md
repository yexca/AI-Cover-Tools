# Separate

`app/separate` contains the audio-separation workflow used by the CLI and the GUI Separate page.

## Files

- `dependencies.py`: checks or installs `python-audio-separator`.
- `models.py`: checks and downloads configured separation models.
- `preprocess.py`: copies or converts source audio into stable preprocessed WAV files.
- `runner.py`: wraps `audio-separator`, maps output stems, and prepares the next pipeline input.
- `workflow.py`: orchestrates input discovery, preprocessing, model steps, manifests, logging, and archival.

## Input Model

The CLI workflow expects grouped folders under `inputs`.

Example:

```text
inputs/
  Kano/
    song-a.wav
    song-b.mp3
  nameless/
    take-001.flac
```

Each first-level folder is a group. Files inside the group may be scanned recursively when `RECURSIVE_INPUT_SCAN` is true.

## Processing Flow

1. Clear `outputs` if `CLEAN_WORK_OUTPUTS_BEFORE_RUN` is true.
2. Discover input groups under `INPUTS_DIR`.
3. Preprocess each group's source files into `outputs/<group>-inputs1`.
4. Write a rename map for stable numbered audio IDs.
5. Run each `MODEL_PIPELINE` step in order.
6. Write raw separator outputs under `outputs/<group>-outputs<step>-<label>`.
7. Move the configured kept stem into `outputs/<group>-inputs<next>`.
8. Move final files into `outputs/<group>-end`.
9. Write `outputs/manifest.json`.
10. Move `outputs` into `archives/outputs-YYYYmmdd-HHMMSS`.

If `STOP_ON_ERROR` is true, a failed group or model step stops the run.

## CLI

```bat
run.bat
run.bat --dry-run
run.bat --preprocess-only
run.bat --download-models-only
```

`main.py` loads config through `app.utils.config_loader`.

## GUI Page

The Separate page is a card-based editor for `MODEL_PIPELINE`.

Cards:

- Presets: load, save, delete, add module, run, stop.
- Common settings: `MODEL_BATCH_SIZE`, `MODEL_OVERLAP`, `MODEL_SEGMENT_SIZE`, `MODEL_OVERRIDE_SEGMENT_SIZE`.
- Model modules: ordered pipeline steps.

Supported module categories:

- `instrumental`
- `harmony`
- `reverb`
- `noise`

Each model card edits:

- `label`
- `model_filename`
- `keep_stem`
- `stem_aliases`
- `pitch_shift`

The GUI writes `user_data/gui_separate_config.py` and runs:

```text
python main.py --config user_data/gui_separate_config.py
```

It uses `QProcess`, streams process output into the status bar, and supports stopping a run.

## GUI Storage

Stored under `user_data`:

- `separate_presets.json`: named user presets.
- `separate_models.json`: successfully used model metadata grouped by category.

Model metadata is saved after successful GUI separation runs.
