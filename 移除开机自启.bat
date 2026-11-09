@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\remove-startup.ps1"
echo.
pause
