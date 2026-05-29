# Architecture

AI-Cover is organized around four workflow modules:

```text
separate -> slicer -> train -> inference
```

Project layout:

```text
main.py
run.bat
run-gui.bat
config.py
app/
  config/
  separate/
  slicer/
  train/
  inference/
  utils/
  gui/
documents/
sample/
```

Module responsibilities:

- `app/separate`: input scanning, WAV normalization, model checks, `python-audio-separator` execution, separation manifests.
- `app/config`: application defaults for CLI, GUI, and workflow modules.
- `app/slicer`: audio slicing workflow for training-ready clips.
- `app/train`: future training workflow and backend integration.
- `app/inference`: future cover generation workflow.
- `app/utils`: shared primitives that are not tied to a specific workflow stage.
- `app/gui`: PySide6 desktop interface. The GUI should call workflow APIs, not contain audio processing logic.

Dependency direction:

```text
main / app.gui
  -> app.separate | app.slicer | app.train | app.inference
       -> app.utils
```

Avoid sideways imports between workflow modules. For example, `train` should not import `separate.runner`; it should receive paths or manifests produced by the previous stage.

Use these boundary types between stages:

- `Path` objects for concrete files and directories.
- Small dataclasses in `app/utils` for shared concepts.
- JSON manifests for persistent cross-stage state.

Stage-specific third-party imports should stay inside that stage. `audio_separator` belongs in `app/separate`; `soundfile` and the RMS slicer implementation belong in `app/slicer`; future RVC or Applio integration should live in `app/train` and `app/inference`.
