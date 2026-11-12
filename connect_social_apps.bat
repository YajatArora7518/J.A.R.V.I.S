@echo off
cd /d "%~dp0"
title JARVIS - Connect Social Apps
python scripts\setup_social_sessions.py
if errorlevel 1 pause
