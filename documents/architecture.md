# Architecture

AI-Cover is a local audio workflow application with a PySide6 desktop GUI, a FastAPI browser WebUI, and separate workflow modules.

## Top-Level Layout

```text
main.py                 CLI entry for separation
config.py               user-facing separation config
run.bat                 CLI launcher
run-gui.bat             GUI launcher
run-webui.bat           WebUI launcher
run-install.bat         local environment installer
app/
  config/               defaults and config loader support
  gui/                  PySide6 shell and pages
  web/                  FastAPI graph editor, model registry, and executor
  separate/             audio-separator pipeline
  slicer/               RMS silence slicing
  tools/                standalone audio utilities
  train/                placeholder workflow module
  inference/            placeholder workflow module
  utils/                shared small primitives
documents/              developer documentation
img/                    GUI background image and application icon
inputs/                 user source audio
models/                 model cache
outputs/                active outputs and tool outputs
archives/               archived separation runs
sample/                 reference or vendored sample projects
user_data/              GUI presets, WebUI state, run records, and generated config
```

## Workflow Modules

- `app/separate`: scans grouped input audio, preprocesses WAV files, runs `python-audio-separator`, moves selected stems between pipeline steps, writes manifests, and archives completed output folders.
- `app/slicer`: recursively scans audio files and slices them into training clips using the local RMS slicer implementation.
- `app/tools`: standalone utilities for inspecting or preparing audio assets: spectrogram images, total duration, pitch reports, and peak normalization.
- `app/train`: placeholder for future training integration.
- `app/inference`: placeholder for future cover-generation integration.
- `app/utils`: shared helpers such as `AudioItem`, safe names, and numbered IDs.
- `app/gui`: GUI layer. It owns widgets, pages, translations, and worker wiring, but not the audio algorithms.
- `app/web`: local browser application. It owns the graph editor, API contracts, model metadata registry, structured validation, and its queued audio graph executor.

## Dependency Direction

```text
main.py / app.gui
  -> app.separate | app.slicer | app.tools | app.train | app.inference
       -> app.utils

app.web
  -> python-audio-separator | app.slicer | app.tools | app.config.defaults
  -> models | user_data | selected input/output paths
```

Rules:

- GUI pages may call workflow APIs and display dataclass results.
- Workflow modules must not import GUI code.
- Desktop GUI code belongs under `app/gui`; browser and API code belongs under `app/web`.
- WebUI port handles are execution contracts. Frontend code must preserve exact backend stem values.
- WebUI task classification, architecture, installation state, and output-confirmation state are separate dimensions. Missing output stems must not be represented as a task category.
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
- Pydantic models for WebUI request, workflow, node, and edge contracts.

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
- WebUI model metadata is cached in `user_data/model_registry.json`.
- WebUI workflows are stored as independent revisioned files under `user_data/workflows`; `user_data/web_workflows.json` is only a retained migration source.
- Each WebUI run owns `user_data/web_runs/<run-id>/run.json`, an immutable `workflow.json` snapshot, and node-specific intermediate output. Output nodes copy or convert final artifacts into their configured folders.

## WebUI State Ownership

- The server workflow store is authoritative for saved workflow revisions. A client must send the revision it loaded, and stale updates fail with `409` instead of overwriting a newer save.
- The browser editor owns open tabs, per-tab undo history and transforms, and bounded recoverable drafts for unsaved changes.
- `RunManager` is authoritative for queue and history state. Run records survive a server restart; runs interrupted by shutdown are restored as failed.
- The frontend obtains a `/api/runs` snapshot at startup and reduces `/api/events/runs` events into it. Active run presentation is selected by the active workflow ID, so switching tabs does not transfer run ownership.
