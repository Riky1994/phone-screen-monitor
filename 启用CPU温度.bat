@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\enable-temp.ps1"
echo.
pause
exit /b 0
