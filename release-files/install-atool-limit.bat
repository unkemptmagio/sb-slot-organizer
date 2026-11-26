@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-atool-limit.ps1" %*
pause
