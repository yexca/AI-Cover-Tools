# Environment

The project uses a local environment under the repository root:

```text
env/
```

Do not rely on system Python for normal operation.

## Installer

Run:

```bat
run-install.bat
```

Behavior:

1. If `env/python.exe` exists, reuse it.
2. If it does not exist, download Miniconda into `env/conda`.
3. Create `env` with Python 3.12 and ffmpeg from conda-forge.
4. Add `env`, `env/Scripts`, and the normal conda binary paths to the process path as needed.
5. Check and install desktop GUI, WebUI, PyTorch, separation, ONNX, and tools dependencies.

## Dependency Groups

### GUI

- `PySide6==6.8.1`

The installer tries conda-forge first and pip as fallback.

The WebUI Windows path picker reuses PySide6 in a short-lived subprocess. This keeps Qt on the subprocess main thread and does not add another GUI dependency.

### WebUI

- `fastapi==0.116.1`
- `uvicorn[standard]==0.35.0`

The WebUI frontend uses browser-native JavaScript and CSS and has no package-manager or build dependency.

### Torch

- `torch`
- `torchvision`
- `torchaudio`

CUDA wheel indexes are tried in this order:

- CUDA 12.8
- CUDA 12.6
- CUDA 12.4
- CUDA 12.1

If all CUDA wheel sources fail, the installer falls back to the default PyTorch package.

### Separation

- `audio-separator[gpu]` or local editable `sample/python-audio-separator`
- `onnxruntime-gpu` when available

If GPU audio-separator install fails, the installer falls back to CPU extras.

### Tools

- `ffmpeg-normalize`
- `Pillow`
- `praat-parselmouth`
- `rmvpe-onnx`
- `scipy`
- `librosa`
- `huggingface-hub`

`rmvpe-onnx` is installed with `--no-deps` after its shared dependencies so it does not force-replace the ONNX Runtime package chosen by the installer.

## Requirements Files

- `requirements.txt`: pip-oriented dependency list.
- `environment.yml`: conda environment reference.
- `run-install.bat`: authoritative Windows setup path for this app.

When adding a dependency:

1. Add it to `requirements.txt`.
2. Add it to `environment.yml` when relevant.
3. Add installer checks or install commands to `run-install.bat` if the GUI depends on it.
4. Verify through `env/python.exe`, not system Python.

## RMVPE Model Download

`rmvpe-onnx` downloads `rmvpe.onnx` from Hugging Face on first use.

Default package path:

```text
env/Lib/site-packages/rmvpe_onnx/data/rmvpe.onnx
```

If the network is unavailable, the RMVPE option will fail with an error message. Praat remains available when `praat-parselmouth` is installed.
