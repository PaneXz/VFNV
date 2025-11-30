@echo off
REM Build VRChat Friend Network Visualizer executable
REM Usage: Double-click this file or run from command line

cd /d "%~dp0"
python build_exe.py
pause
