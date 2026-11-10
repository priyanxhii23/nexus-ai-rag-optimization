@echo off
REM ================================================================
REM  NEXUS AI - stop backend + frontend
REM ================================================================
setlocal
cd /d "%~dp0"
echo.
echo   NEXUS AI - stopping...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_services.ps1"
echo.
echo   Done.
pause
