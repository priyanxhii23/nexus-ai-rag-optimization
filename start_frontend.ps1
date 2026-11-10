<#
.SYNOPSIS
    Start the NEXUS AI frontend (Vite dev server) on http://localhost:5173
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\start_frontend.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Root        = $PSScriptRoot
$FrontendDir = Join-Path $Root 'frontend'
$LogsDir     = Join-Path (Join-Path $Root 'data') 'logs'
$Port        = 5173

try { $Host.UI.RawUI.WindowTitle = 'NEXUS AI - Frontend' } catch { }

function Test-PortFree([int]$p) {
    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $p)
        $listener.Start(); return $true
    } catch { return $false } finally { if ($listener) { $listener.Stop() } }
}

Write-Host "NEXUS AI frontend" -ForegroundColor Magenta

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "[FAILED] Node.js not found. Install it from https://nodejs.org/ and open a new terminal." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path (Join-Path $FrontendDir 'node_modules'))) {
    Write-Host "[FAILED] Frontend packages are not installed (frontend\node_modules missing)." -ForegroundColor Red
    Write-Host "         Run setup first:  powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1" -ForegroundColor Yellow
    exit 1
}
if (-not (Test-PortFree $Port)) {
    Write-Host "[FAILED] Port $Port is already in use (is the frontend already running?)." -ForegroundColor Red
    Write-Host "         Run .\stop_all.bat and try again." -ForegroundColor Yellow
    exit 1
}

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null
Set-Content -Path (Join-Path $LogsDir 'frontend.pid') -Value $PID -Encoding ascii

Write-Host "Dashboard: http://localhost:$Port"
Write-Host "Press Ctrl+C to stop." -ForegroundColor Gray
Write-Host ""

Push-Location $FrontendDir
try {
    & npm run dev
    $code = $LASTEXITCODE
} finally {
    Pop-Location
    Remove-Item (Join-Path $LogsDir 'frontend.pid') -ErrorAction SilentlyContinue
}
exit $code
