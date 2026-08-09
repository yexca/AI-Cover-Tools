# AI Cover Tools

Languages: [English](README.md) | [简体中文](README.zh-cn.md) | [日本語](README.ja.md)

AI Cover Tools is a Windows toolkit for preparing local AI cover audio materials. It currently focuses on the pre-training audio workflow: vocal extraction, training-clip slicing, audio quality checks, total duration analysis, pitch analysis, and peak normalization.

Currently available features:

- GUI: Separate, Slicer, Tools, Settings, and About.
- Separate: batch process audio with `python-audio-separator` and a configurable model chain to remove accompaniment, harmony, reverb, noise, or keep selected stems.
- Slicer: split audio into training-friendly clips according to silence and duration settings.
- Tools: spectrogram-based audio quality checks, folder duration summary, pitch report, and peak normalization.

Train and Inference pages are already reserved in the GUI, but they are placeholders for now. For voice model training and final cover inference, mature external tools such as Applio are recommended at this stage.

## Quick Start

Run the installer first:

```bat
run-install.bat
```

The installer creates or reuses the project-local `env` environment and installs GUI, PyTorch, FFmpeg, audio separation, and tool dependencies. Normal usage does not rely on system Python.

After installation, start the GUI:

```bat
run-gui.bat
```

If you only want to run the command-line separation workflow:

```bat
run.bat
```

To start the node-based WebUI:

```bat
run-webui.bat
```

Then open `http://127.0.0.1:7657` in a browser. The launcher always uses the project-local `env` and prints a clear error if the environment has not been installed. Uvicorn options can be passed through, for example `run-webui.bat --port 8000`.

## WebUI MVP

The WebUI is a ComfyUI-style audio workflow editor with single-audio and folder inputs, model-based separation, audio slicing, peak normalization, and folder outputs. Processing models are grouped by function in the left sidebar, with architecture available as a filter; model output ports are derived from the model registry metadata. Output folders support standard naming and Smart classification, which accepts multiple separator-derived inputs and writes `<model>_<stem>/<relative source folder>/<song>.<ext>`.

Drag a library item onto the canvas, or double-click it to add a node. Drag any non-interactive part of a node to move it; selecting a node shows a compact toolbar above it for duplication and confirmed deletion, while the lower-right handle resizes it. The Single audio control uses the browser's file chooser and uploads the selection to the local service; input and output folder fields keep the native Windows folder picker. Create connections by dragging in either direction, or by clicking two compatible ports. Before a run starts, the server validates paths, uploads, models, ports, and graph structure. Branches that cannot reach an Output folder are not executed, and same-name output files follow the selected rename, overwrite, or skip policy.

The interface follows the browser language by default and currently supports Simplified Chinese, Japanese, and English. The language selector in the top bar can override the browser setting and remembers the choice locally.

On startup, the WebUI shows the saved registry immediately and starts a local-only background scan for installed model changes. This scan reads local filenames and metadata and does not download models or load them into GPU memory. Use **Refresh models** to trigger another local scan. Online catalog synchronization is a separate manual action so a slow or unavailable network cannot block startup. Models whose function or outputs cannot be identified remain marked for confirmation instead of being guessed silently.

## Recommended Flow

1. Put source songs or vocal materials into `inputs`.
2. Use the GUI Separate page to extract cleaner vocals.
3. Use the Tools page to check audio quality, total duration, pitch range, and normalize files when needed.
4. Use the Slicer page to generate short training clips.
5. Train and run inference with an external voice model tool.

## GUI Features

### Separate

The Separate page edits and runs an ordered model processing chain. You can add multiple model modules and configure:

- model filename
- stem to keep
- stem aliases
- pitch shift
- common settings such as batch size, overlap, and segment size

The GUI writes its settings to `user_data/gui_separate_config.py`, then calls the same command-line separation workflow. Separation output is first written to `outputs`, then archived to `archives/outputs-YYYYmmdd-HHMMSS` after a successful run.

### Slicer

The Slicer page recursively scans an input folder and splits audio into training-friendly clips. The default input is `inputs`, the default output is `outputs`, and the default output format is `wav`.

Common settings:

- Threshold: silence threshold
- Minimum Length: shortest clip length
- Minimum Interval: shortest silence interval
- Hop Size: analysis step size
- Maximum Size Length: maximum kept silence length

Supported input formats include `wav`, `flac`, `mp3`, `m4a`, `ogg`, `opus`, `wma`, and `aiff`. Supported output formats are `wav`, `flac`, and `mp3`.

### Tools

The Tools page includes four standalone utilities:

- Audio quality: generate Spek-like spectrogram images. Long audio is split into 10-minute segments.
- Total duration: summarize the total duration of all supported audio files in a folder.
- Pitch report: analyze dataset pitch range and distribution with Praat or RMVPE.
- Normalize: batch peak-normalize audio while preserving the original folder structure.

Tool outputs are written to the selected output path, or to tool-specific folders under `outputs`.

### Settings

The Settings page currently provides live appearance previews such as background image, blur, text color, and background tint. These settings are preview-only in the current implementation and are not persisted yet.

## Command-Line Separation

The command-line separation workflow expects first-level grouped folders under `inputs`:

```text
inputs/
  SingerA/
    song-a.wav
    song-b.mp3
  SingerB/
    take-001.flac
```

Each first-level folder is treated as one group. Source files are never modified. The workflow first copies or converts them into stable numbered WAV files, then runs the configured model chain.

Useful commands:

```bat
run.bat
run.bat --dry-run
run.bat --preprocess-only
run.bat --download-models-only
run.bat --skip-model-download
```

You can also specify a config file:

```bat
run.bat --config config.py
```

## Output Locations

Common project folders:

```text
inputs/      source audio files
outputs/     active run output, slicer output, and tool output
archives/    archived separation runs
models/      separation model cache
user_data/   GUI presets and GUI-generated config
img/         GUI icon and background image
```

A separation archive usually contains:

- `<group>-inputs1`: preprocessed numbered WAV files.
- `<group>-outputs<step>-<label>`: raw output from each model step.
- `<group>-inputs<next>`: target stems passed to the next step.
- `<group>-end`: final WAV files for that group.
- `<group>-rename-map.md`: mapping between original filenames and numbered filenames.
- `manifest.json`: run record.
- `run-YYYYmmdd-HHMMSS.log`: run log.

## Configure The Model Chain

The command line reads `config.py` by default. The most commonly edited section is `MODEL_PIPELINE`:

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

Field meanings:

- `label`: step name used in output folders and filenames.
- `model_filename`: model file to load or download.
- `keep_stem`: target stem to keep and pass to the next step.
- `stem_aliases`: alternate stem names that may appear in model output.
- `pitch_shift`: pitch shift for this step.

Common global settings also live in `config.py`:

```python
MODEL_BATCH_SIZE = 16
MODEL_OVERLAP = 2
MODEL_SEGMENT_SIZE = 256
MODEL_OVERRIDE_SEGMENT_SIZE = False
```

See [documents/configuration.md](documents/configuration.md) for the full configuration reference.

## Notes

- The first installation and first use of some models require network access.
- CUDA PyTorch is installed first. If it fails, the installer falls back to available dependencies.
- RMVPE pitch analysis downloads `rmvpe.onnx` on first use. If the network is unavailable, use Praat instead.
- The separation workflow may clean or reuse `outputs` according to configuration. Treat archived results under `archives` as the important completed output.

## Developer Documents

Developer-facing documents are in [documents/README.md](documents/README.md). They cover architecture, environment setup, GUI, separation, slicer, tools, and configuration details.
