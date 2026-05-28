@echo off
setlocal
set "INSTALL_DIR=%cd%"
set "ENV_DIR=%INSTALL_DIR%\env"
set "MINICONDA_DIR=%UserProfile%\Miniconda3"

if exist "%ENV_DIR%\python.exe" (
    "%ENV_DIR%\python.exe" "%INSTALL_DIR%\main.py" %*
    exit /b %errorlevel%
)

if exist "%MINICONDA_DIR%\condabin\conda.bat" (
    call "%MINICONDA_DIR%\condabin\conda.bat" activate "%ENV_DIR%"
    python "%INSTALL_DIR%\main.py" %*
    exit /b %errorlevel%
)

python "%INSTALL_DIR%\main.py" %*
