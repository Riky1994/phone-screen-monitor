@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\enable-fps.ps1"
echo.
pause
exit /b 0
