@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop.ps1"
ping -n 3 127.0.0.1 >nul 2>&1
exit /b 0
