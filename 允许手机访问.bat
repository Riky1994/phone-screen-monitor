@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\allow-firewall.ps1"
exit /b 0
