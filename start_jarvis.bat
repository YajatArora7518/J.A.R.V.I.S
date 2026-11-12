@echo off
:: JARVIS Launcher — always runs from its own directory regardless of how it was invoked
cd /d "%~dp0"
title J.A.R.V.I.S
python main.py %*
if errorlevel 1 (
    echo.
    echo [JARVIS] Process exited with error. Press any key to close.
    pause >nul
)
