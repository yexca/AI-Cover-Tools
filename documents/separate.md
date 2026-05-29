# Separate Module

`app/separate` contains the currently executable workflow.

Files:

- `dependencies.py`: ensures `python-audio-separator` is importable or installed.
- `models.py`: checks and downloads configured separation models.
- `preprocess.py`: copies or converts input audio to normalized WAV files.
- `runner.py`: wraps `audio-separator`, selects target stems, and moves outputs to the next step.
- `workflow.py`: orchestrates input discovery, preprocessing, model steps, manifests, and archival.

Processing flow:

1. Find folders under `inputs`, such as `Kano` and `nameless`.
2. Sort audio files inside each folder.
3. Convert or copy every file into WAV under `outputs/<group>-inputs1`.
4. Write `<group>-rename-map.md`.
5. Run each model in `MODEL_PIPELINE` in order.
6. Write raw model outputs under `outputs/<group>-outputs<step>-<label>`.
7. Move the configured target stem into `outputs/<group>-inputs<next>`.
8. Move final WAV files into `outputs/<group>-end`.
9. Write `manifest.json`.
10. Move the whole `outputs` folder into `archives/outputs-YYYYmmdd-HHMMSS`.

CLI:

```bat
run.bat
run.bat --dry-run
run.bat --preprocess-only
run.bat --download-models-only
```

## GUI Configuration

The Separate page is organized as cards:

- Presets: load, save, delete, add module, run, and stop.
- Common settings: `MODEL_BATCH_SIZE`, `MODEL_OVERLAP`, `MODEL_SEGMENT_SIZE`, and `MODEL_OVERRIDE_SEGMENT_SIZE`.
- Model modules: one card per pipeline step.

Supported module categories:

- `instrumental`: remove instrumental / accompaniment.
- `harmony`: remove harmony.
- `reverb`: remove reverb.
- `noise`: remove noise.

Each model card edits:

- `label`
- `model_filename`
- `keep_stem`
- `stem_aliases`
- `pitch_shift`

GUI data is stored under `user_data`:

- `separate_presets.json`: user-saved presets.
- `separate_models.json`: model metadata grouped by category and indexed by `model_filename`.

Model metadata should only be written after a successful separation run. The current GUI builds the storage and editing structure; wiring the actual run result into model-library saving is the next integration step.
