@echo off
setlocal enabledelayedexpansion
title AI-Cover Installer

set "INSTALL_DIR=%cd%"
set "ENV_DIR=%INSTALL_DIR%\env"
set "LOCAL_CONDA_DIR=%ENV_DIR%\conda"
set "LOCAL_CONDA_BAT=%LOCAL_CONDA_DIR%\condabin\conda.bat"
set "MINICONDA_URL=https://repo.anaconda.com/miniconda/Miniconda3-py312_25.11.1-1-Windows-x86_64.exe"
set "PYTHON_CMD=%ENV_DIR%\python.exe"
set "PYTORCH_CUDA_INDEX_URLS=https://download.pytorch.org/whl/cu128 https://download.pytorch.org/whl/cu126 https://download.pytorch.org/whl/cu124 https://download.pytorch.org/whl/cu121"
set "PYSIDE_VERSION=6.8.1"

if not exist "%PYTHON_CMD%" (
    call :ensure_local_conda
    if errorlevel 1 goto :error

    echo Creating local environment...
    call "%LOCAL_CONDA_BAT%" create --no-shortcuts -y -k --prefix "%ENV_DIR%" python=3.12 ffmpeg -c conda-forge
    if errorlevel 1 goto :error
) else (
    echo Local env found: %ENV_DIR%
)

set "PATH=%ENV_DIR%;%ENV_DIR%\Scripts;%PATH%"

call :ensure_pip
if errorlevel 1 goto :error

call :ensure_pyside
if errorlevel 1 goto :error

call :ensure_torch
if errorlevel 1 goto :error

call :ensure_audio_separator
if errorlevel 1 goto :error

call :ensure_onnxruntime
if errorlevel 1 goto :error

"%PYTHON_CMD%" -c "import torch; print('Torch CUDA available:', torch.cuda.is_available()); print('Torch version:', torch.__version__); print('CUDA version:', torch.version.cuda); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
"%PYTHON_CMD%" -c "from PySide6.QtWidgets import QApplication; print('PySide6 GUI available')"
if errorlevel 1 goto :error

echo Installation complete.
echo Use run.bat to start the pipeline.
echo Use run-gui.bat to start the GUI.
pause
exit /b 0

:ensure_local_conda
if exist "%LOCAL_CONDA_BAT%" exit /b 0

echo Local conda was not found. Downloading installer...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%MINICONDA_URL%' -OutFile '%INSTALL_DIR%\miniconda.exe'"
if errorlevel 1 exit /b 1

start /wait "" "%INSTALL_DIR%\miniconda.exe" /InstallationType=JustMe /RegisterPython=0 /S /D=%LOCAL_CONDA_DIR%
if errorlevel 1 exit /b 1

del "%INSTALL_DIR%\miniconda.exe"
if not exist "%LOCAL_CONDA_BAT%" exit /b 1
exit /b 0

:ensure_pip
"%PYTHON_CMD%" -m pip --version >nul 2>nul
if not errorlevel 1 exit /b 0
echo Installing pip...
"%PYTHON_CMD%" -m ensurepip --upgrade
if errorlevel 1 exit /b 1
"%PYTHON_CMD%" -m pip install --upgrade pip
exit /b %errorlevel%

:ensure_pyside
echo Checking PySide6...
"%PYTHON_CMD%" -c "from PySide6.QtWidgets import QApplication; import PySide6; print('PySide6 already available:', PySide6.__version__)"
if not errorlevel 1 exit /b 0

echo Installing PySide6...
if exist "%LOCAL_CONDA_BAT%" (
    call "%LOCAL_CONDA_BAT%" install --prefix "%ENV_DIR%" -y -c conda-forge "pyside6=%PYSIDE_VERSION%"
    if not errorlevel 1 (
        "%PYTHON_CMD%" -c "from PySide6.QtWidgets import QApplication; import PySide6; print('PySide6 installed:', PySide6.__version__)"
        if not errorlevel 1 exit /b 0
    )
)

"%PYTHON_CMD%" -m pip install --force-reinstall "PySide6==%PYSIDE_VERSION%" "PySide6_Addons==%PYSIDE_VERSION%" "PySide6_Essentials==%PYSIDE_VERSION%" "shiboken6==%PYSIDE_VERSION%"
if errorlevel 1 exit /b 1
"%PYTHON_CMD%" -c "from PySide6.QtWidgets import QApplication; import PySide6; print('PySide6 installed:', PySide6.__version__)"
exit /b %errorlevel%

:ensure_torch
echo Checking PyTorch...
"%PYTHON_CMD%" -c "import torch, torchvision, torchaudio; print('PyTorch already available:', torch.__version__)"
if not errorlevel 1 exit /b 0

echo Installing CUDA-enabled PyTorch first...
set "TORCH_CUDA_INSTALLED=0"
for %%U in (%PYTORCH_CUDA_INDEX_URLS%) do (
    if "!TORCH_CUDA_INSTALLED!"=="0" (
        echo Trying PyTorch CUDA wheels from %%U
        "%PYTHON_CMD%" -m pip install torch torchvision torchaudio --index-url "%%U"
        if not errorlevel 1 set "TORCH_CUDA_INSTALLED=1"
    )
)
if "%TORCH_CUDA_INSTALLED%"=="0" (
    echo CUDA PyTorch installation failed for all configured CUDA wheel sources. Falling back to default PyTorch package...
    "%PYTHON_CMD%" -m pip install torch torchvision torchaudio
    if errorlevel 1 exit /b 1
)
exit /b 0

:ensure_audio_separator
echo Checking audio-separator...
"%PYTHON_CMD%" -c "import audio_separator.separator; print('audio-separator already available')"
if not errorlevel 1 exit /b 0

echo Installing audio-separator...
if exist "%INSTALL_DIR%\sample\python-audio-separator\pyproject.toml" (
    pushd "%INSTALL_DIR%\sample\python-audio-separator"
    "%PYTHON_CMD%" -m pip install -e ".[gpu]"
    if errorlevel 1 (
        echo GPU dependency installation failed. Falling back to CPU dependencies...
        "%PYTHON_CMD%" -m pip install -e ".[cpu]"
    )
    popd
    exit /b %errorlevel%
)

"%PYTHON_CMD%" -m pip install "audio-separator[gpu]"
if not errorlevel 1 exit /b 0
echo GPU dependency installation failed. Falling back to CPU dependencies...
"%PYTHON_CMD%" -m pip install "audio-separator[cpu]"
exit /b %errorlevel%

:ensure_onnxruntime
echo Checking ONNX Runtime GPU...
"%PYTHON_CMD%" -c "import onnxruntime; print('ONNX Runtime already available:', onnxruntime.__version__)"
if not errorlevel 1 exit /b 0

"%PYTHON_CMD%" -m pip install onnxruntime-gpu
if errorlevel 1 (
    echo ONNX Runtime GPU installation failed. Continuing; Torch CUDA may still accelerate Roformer models.
    exit /b 0
)
exit /b 0

:error
echo Installation failed. Please check the messages above.
pause
exit /b 1
