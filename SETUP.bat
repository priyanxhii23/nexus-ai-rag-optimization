@echo off
REM Kept for compatibility: SETUP.bat now runs setup_windows.ps1
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1" %*
echo.
pause
