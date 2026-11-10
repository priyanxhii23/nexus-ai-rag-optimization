@echo off
REM ================================================================
REM  NEXUS AI - start backend + frontend (double-click or run from any folder)
REM ================================================================
setlocal
REM %~dp0 = the folder this .bat file lives in (the project root)
cd /d "%~dp0"
title NEXUS AI - launcher
echo.
echo   NEXUS AI - starting...
echo   Project folder: %CD%
echo.

where powershell >nul 2>nul
if errorlevel 1 goto :no_powershell
where node >nul 2>nul
if errorlevel 1 goto :no_node
if not exist "backend\.venv\Scripts\python.exe" goto :no_setup
if not exist "frontend\node_modules" goto :no_setup
if not exist ".env" echo   [WARN] No .env file found - the app will run in LOCAL TEST MODE.

echo   Opening the backend window...
start "NEXUS AI - Backend" powershell -NoExit -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_backend.ps1"
echo   Opening the frontend window...
start "NEXUS AI - Frontend" powershell -NoExit -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_frontend.ps1"
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\wait_for_services.ps1"
if errorlevel 1 goto :start_failed
echo.
pause
exit /b 0

:no_powershell
echo   [FAILED] Windows PowerShell was not found on PATH.
goto :fail
:no_node
echo   [FAILED] Node.js was not found. Install it from https://nodejs.org/ then open a NEW terminal.
goto :fail
:no_setup
echo   [FAILED] Setup has not been completed yet - virtual environment or node_modules missing.
echo            Run this first, from the project folder:
echo            powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1
goto :fail
:start_failed
echo.
echo   [FAILED] Something did not start. Check the Backend / Frontend windows for the error,
echo            then run stop_all.bat before trying again.
goto :fail
:fail
echo.
pause
exit /b 1
