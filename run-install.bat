@echo off
setlocal enabledelayedexpansion
title AI-Cover Installer

set "INSTALL_DIR=%cd%"
set "ENV_DIR=%INSTALL_DIR%\env"
set "MINICONDA_DIR=%UserProfile%\Miniconda3"
set "MINICONDA_URL=https://repo.anaconda.com/miniconda/Miniconda3-py312_25.11.1-1-Windows-x86_64.exe"
set "CONDA_EXE=%MINICONDA_DIR%\Scripts\conda.exe"

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
if exist "%INSTALL_DIR%\sample\python-audio-separator\pyproject.toml" (
    pushd "%INSTALL_DIR%\sample\python-audio-separator"
    python -m pip install -e ".[cpu]"
    popd
    if errorlevel 1 goto :error
) else (
    python -m pip install -r "%INSTALL_DIR%\requirements.txt"
    if errorlevel 1 goto :error
)
call "%MINICONDA_DIR%\condabin\conda.bat" deactivate

echo Installation complete.
echo Use run.bat to start the pipeline.
pause
exit /b 0

:error
echo Installation failed. Please check the messages above.
pause
exit /b 1
