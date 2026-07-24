# AI Cover Tools Developer Documents

This folder is the source of truth for the current project structure and behavior.

## Map

- [Architecture](architecture.md): package boundaries, data flow, and ownership rules.
- [Environment](environment.md): local `env`, installer behavior, and dependency groups.
- [GUI](gui.md): desktop shell, pages, widgets, threading, and i18n.
- [WebUI](webui.md): browser graph editor, model registry, API, validation, and execution.
- [Separate](separate.md): separation CLI and GUI model pipeline.
- [Slicer](slicer.md): training-clip slicing workflow.
- [Tools](tools.md): audio quality, duration, pitch, and normalize utilities.
- [Configuration](configuration.md): config loading, defaults, and pipeline keys.
- [Development](development.md): implementation conventions and verification checklist.

## Current State

Implemented pages:

- Home
- Separate
- Slicer
- Tools
- Settings
- About

Placeholder pages:

- Train
- Inference

Implemented WebUI node types:

- Single audio file input
- Audio folder input
- Model-based separator
- Audio slicer
- Peak normalizer
- Output folder

Main runnable entry points:

```bat
run-install.bat
run.bat
run-gui.bat
run-webui.bat
```

The desktop GUI should call workflow modules. Audio processing should stay outside `app/gui`. The WebUI owns a separate graph executor under `app/web` and must keep its frontend, API contracts, validation, and execution handles consistent.
