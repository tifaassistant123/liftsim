@echo off
cd /d "%~dp0"
set PYTHONPATH=%~dp0

echo 🛗 LiftSim Launcher
echo -------------------

REM Check if pygame-ce is installed
python -c "import pygame; exit(0)" 2>nul
if %errorlevel% neq 0 (
    echo ⚠ pygame-ce not found! Installing now...
    pip install pygame-ce
    if %errorlevel% neq 0 (
        echo ❌ Failed to install pygame-ce.
        echo    Make sure Python and pip are installed correctly.
        pause
        exit /b 1
    )
    echo ✅ pygame-ce installed!
)

echo 🚀 Starting LiftSim...
python main.py
if %errorlevel% neq 0 (
    echo.
    echo ⚠ Something went wrong. Error code: %errorlevel%
    pause
)
