# AI-Cover

AI-Cover is a local batch pipeline for preparing AI cover training data. It reads audio from `inputs`, converts every source file into clean numbered WAV files, then runs the configured `audio-separator` model chain. User input files are never modified.

## Install

```bat
run-install.bat
```

The installer creates `env`, installs Python 3.12 and FFmpeg, then installs CUDA-enabled PyTorch and GPU-enabled `audio-separator` dependencies first. If GPU dependency installation fails, it falls back to CPU dependencies.

## Run

Put audio files into subfolders under `inputs`, for example:

```text
inputs/
  Kano/
    song.wav
  nameless/
    song.mp3
```

Then run:

```bat
run.bat
```

Useful commands:

```bat
run.bat --dry-run
run.bat --preprocess-only
run.bat --download-models-only
```

## Output

During a run, temporary work is written to `outputs`. When the run finishes, the whole folder is moved to:

```text
archives/outputs-YYYYmmdd-HHMMSS/
```

Inside the archived run you will find:

- `<group>-inputs1`: renamed/converted WAV inputs such as `01.wav`
- `<group>-outputs<step>-<label>`: raw model outputs for each step
- `<group>-inputs<next>`: target stems moved forward to the next step
- `<group>-end`: final WAV files for that input group
- `<group>-rename-map.md`: Markdown table mapping original filenames to normalized WAV names
- `manifest.json` and the run log

## Common Config

Edit `config.py`.

The most commonly changed section is `MODEL_PIPELINE`:

```python
MODEL_PIPELINE = [
    {
        "label": "vocals",
        "model_filename": "mel_band_roformer_kim_ft3_unwa.ckpt",
        "keep_stem": "vocals",
        "stem_aliases": ["Vocals", "vocal"],
        "segment_size": 256,
        "override_model_segment_size": False,
        "overlap": 2,
        "batch_size": 16,
        "pitch_shift": 0,
    },
]
```

- `label`: name used in output folders and filenames.
- `model_filename`: exact model file to load or download.
- `keep_stem`: model output stem to keep and pass to the next step.
- `stem_aliases`: alternate names that may appear in model output.
- `segment_size`, `overlap`, `batch_size`, `pitch_shift`: inference parameters.

Full configuration and development notes are in [documents/development.md](documents/development.md).
