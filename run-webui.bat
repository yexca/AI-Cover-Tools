@echo off
setlocal
title AI-Cover WebUI

set "INSTALL_DIR=%~dp0"
set "PYTHON_CMD=%INSTALL_DIR%env\python.exe"

if not exist "%PYTHON_CMD%" (
    echo Project-local environment was not found: %PYTHON_CMD%
    echo Run run-install.bat first.
    pause
    exit /b 1
)

pushd "%INSTALL_DIR%"
"%PYTHON_CMD%" -u -m app.web %*
set "EXIT_CODE=%ERRORLEVEL%"
popd

if not "%EXIT_CODE%"=="0" (
    echo.
    echo WebUI stopped with exit code %EXIT_CODE%.
    echo Check the messages above for details.
    pause
)

exit /b %EXIT_CODE%
