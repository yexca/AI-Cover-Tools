# AI-Cover Developer Documents

This folder is the source of truth for the current project structure and behavior.

## Map

- [Architecture](architecture.md): package boundaries, data flow, and ownership rules.
- [Environment](environment.md): local `env`, installer behavior, and dependency groups.
- [GUI](gui.md): desktop shell, pages, widgets, threading, and i18n.
- [Separate](separate.md): separation CLI and GUI model pipeline.
- [Slicer](slicer.md): training-clip slicing workflow.
- [Tools](tools.md): audio quality, duration, pitch, and normalize utilities.
- [Configuration](configuration.md): config loading, defaults, and pipeline keys.
- [Development](development.md): implementation conventions and verification checklist.

## Current State

Implemented pages:

- Separate
- Slicer
- Tools
- Settings

Placeholder pages:

- Home
- Train
- Inference
- About

Main runnable entry points:

```bat
run-install.bat
run.bat
run-gui.bat
```

The GUI should call workflow modules. Audio processing should stay outside `app/gui`.
