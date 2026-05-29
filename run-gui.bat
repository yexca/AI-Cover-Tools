@echo off
setlocal
set "INSTALL_DIR=%cd%"
set "ENV_DIR=%INSTALL_DIR%\env"
set "MINICONDA_DIR=%UserProfile%\Miniconda3"

if exist "%MINICONDA_DIR%\condabin\conda.bat" (
    call "%MINICONDA_DIR%\condabin\conda.bat" activate "%ENV_DIR%"
    python -u -m app.gui %*
    exit /b %errorlevel%
)

if exist "%ENV_DIR%\python.exe" (
    "%ENV_DIR%\python.exe" -u -m app.gui %*
    exit /b %errorlevel%
)

python -u -m app.gui %*
