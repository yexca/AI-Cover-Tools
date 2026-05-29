# Architecture

AI-Cover is a local audio workflow application with a PySide6 GUI and separate workflow modules.

## Top-Level Layout

```text
main.py                 CLI entry for separation
config.py               user-facing separation config
run.bat                 CLI launcher
run-gui.bat             GUI launcher
run-install.bat         local environment installer
app/
  config/               defaults and config loader support
  gui/                  PySide6 shell and pages
  separate/             audio-separator pipeline
  slicer/               RMS silence slicing
  tools/                standalone audio utilities
  train/                placeholder workflow module
  inference/            placeholder workflow module
  utils/                shared small primitives
documents/              developer documentation
inputs/                 user source audio
models/                 model cache
outputs/                active outputs and tool outputs
archives/               archived separation runs
sample/                 reference or vendored sample projects
user_data/              GUI presets and generated GUI config
```

## Workflow Modules

- `app/separate`: scans grouped input audio, preprocesses WAV files, runs `python-audio-separator`, moves selected stems between pipeline steps, writes manifests, and archives completed output folders.
- `app/slicer`: recursively scans audio files and slices them into training clips using the local RMS slicer implementation.
- `app/tools`: standalone utilities for inspecting or preparing audio assets: spectrogram images, total duration, pitch reports, and peak normalization.
- `app/train`: placeholder for future training integration.
- `app/inference`: placeholder for future cover-generation integration.
- `app/utils`: shared helpers such as `AudioItem`, safe names, and numbered IDs.
- `app/gui`: GUI layer. It owns widgets, pages, translations, and worker wiring, but not the audio algorithms.

## Dependency Direction

```text
main.py / app.gui
  -> app.separate | app.slicer | app.tools | app.train | app.inference
       -> app.utils
```

Rules:

- GUI pages may call workflow APIs and display dataclass results.
- Workflow modules must not import GUI code.
- Avoid sideways imports between workflow modules unless a helper is intentionally shared through `app/utils`.
- Stage-specific third-party imports should stay near the stage that needs them.

Examples:

- `audio_separator` belongs in `app/separate`.
- `soundfile` and the RMS slicer belong in `app/slicer`.
- `praat-parselmouth`, `rmvpe-onnx`, `Pillow`, `scipy`, and `ffmpeg-normalize` belong in `app/tools`.
- Future RVC or Applio dependencies should live under `app/train` or `app/inference`.

## Data Boundaries

Use these boundary types:

- `Path` for concrete files and directories.
- Dataclasses for in-process results.
- JSON files for persistent GUI data or manifests.

Existing result dataclasses:

- `app.separate.workflow.PipelineResult`
- `app.slicer.workflow.SlicerRunResult`
- `app.tools.workflow.AudioQualityResult`
- `app.tools.workflow.DurationSummary`
- `app.tools.workflow.PitchReport`
- `app.tools.workflow.NormalizeResult`

## Output Ownership

- Separation owns `outputs` during a CLI run and normally archives it to `archives/outputs-YYYYmmdd-HHMMSS`.
- Slicer writes user-selected output folders and does not archive automatically.
- Tools write under user-selected paths or tool-specific folders under `outputs`.
- GUI-generated separation config is written to `user_data/gui_separate_config.py`.
