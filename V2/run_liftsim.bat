@echo off
REM LiftSim V2 Launcher — auto-installs pygame-ce if missing
cd /d "%~dp0"

echo Checking dependencies...
python -c "import pygame" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Installing pygame-ce...
    pip install pygame-ce
)

echo Starting LiftSim V2...
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo LiftSim exited with error code %ERRORLEVEL%
    pause
)
