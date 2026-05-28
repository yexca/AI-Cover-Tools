@echo off
setlocal enabledelayedexpansion
title AI-Cover Installer

set "INSTALL_DIR=%cd%"
set "ENV_DIR=%INSTALL_DIR%\env"
set "MINICONDA_DIR=%UserProfile%\Miniconda3"
set "MINICONDA_URL=https://repo.anaconda.com/miniconda/Miniconda3-py312_25.11.1-1-Windows-x86_64.exe"
set "CONDA_EXE=%MINICONDA_DIR%\Scripts\conda.exe"
set "PYTORCH_CUDA_INDEX_URLS=https://download.pytorch.org/whl/cu128 https://download.pytorch.org/whl/cu126 https://download.pytorch.org/whl/cu124 https://download.pytorch.org/whl/cu121"

if not exist "%CONDA_EXE%" (
    echo Miniconda not found. Downloading installer...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%MINICONDA_URL%' -OutFile '%INSTALL_DIR%\miniconda.exe'"
    if errorlevel 1 goto :error
    start /wait "" "%INSTALL_DIR%\miniconda.exe" /InstallationType=JustMe /RegisterPython=0 /S /D=%MINICONDA_DIR%
    if errorlevel 1 goto :error
    del "%INSTALL_DIR%\miniconda.exe"
)

if not exist "%ENV_DIR%\python.exe" (
    echo Creating local environment...
    call "%MINICONDA_DIR%\condabin\conda.bat" create --no-shortcuts -y -k --prefix "%ENV_DIR%" python=3.12 ffmpeg -c conda-forge
    if errorlevel 1 goto :error
)

echo Installing Python dependencies...
call "%MINICONDA_DIR%\condabin\conda.bat" activate "%ENV_DIR%"
if errorlevel 1 goto :error
python -m pip install --upgrade pip
if errorlevel 1 goto :error

echo Installing CUDA-enabled PyTorch first...
set "TORCH_CUDA_INSTALLED=0"
for %%U in (%PYTORCH_CUDA_INDEX_URLS%) do (
    if "!TORCH_CUDA_INSTALLED!"=="0" (
        echo Trying PyTorch CUDA wheels from %%U
        python -m pip install --upgrade --force-reinstall torch torchvision torchaudio --index-url "%%U"
        if not errorlevel 1 set "TORCH_CUDA_INSTALLED=1"
    )
)
if "%TORCH_CUDA_INSTALLED%"=="0" (
    echo CUDA PyTorch installation failed for all configured CUDA wheel sources. Falling back to default PyTorch package...
    python -m pip install --upgrade torch torchvision torchaudio
    if errorlevel 1 goto :error
)

if exist "%INSTALL_DIR%\sample\python-audio-separator\pyproject.toml" (
    pushd "%INSTALL_DIR%\sample\python-audio-separator"
    python -m pip install -e ".[gpu]"
    if errorlevel 1 (
        echo GPU dependency installation failed. Falling back to CPU dependencies...
        python -m pip install -e ".[cpu]"
    )
    popd
    if errorlevel 1 goto :error
) else (
    python -m pip install -r "%INSTALL_DIR%\requirements.txt"
    if errorlevel 1 (
        echo GPU dependency installation failed. Falling back to CPU dependencies...
        python -m pip install "audio-separator[cpu]"
        if errorlevel 1 goto :error
    )
)
python -m pip install --upgrade onnxruntime-gpu
if errorlevel 1 echo ONNX Runtime GPU installation failed. Continuing; Torch CUDA may still accelerate Roformer models.

python -c "import torch; print('Torch CUDA available:', torch.cuda.is_available()); print('Torch version:', torch.__version__); print('CUDA version:', torch.version.cuda); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
call "%MINICONDA_DIR%\condabin\conda.bat" deactivate

echo Installation complete.
echo Use run.bat to start the pipeline.
pause
exit /b 0

:error
echo Installation failed. Please check the messages above.
pause
exit /b 1
