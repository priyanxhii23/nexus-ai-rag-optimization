<#
.SYNOPSIS
    Start the NEXUS AI backend (FastAPI + Uvicorn) on http://localhost:8000
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\start_backend.ps1
.PARAMETER NoReload
    Disable auto-reload (reload restarts the server when you edit Python files).
#>
[CmdletBinding()]
param([switch]$NoReload, [int]$Port = 8000)

$ErrorActionPreference = 'Stop'
$OnWindows  = ($env:OS -eq 'Windows_NT')
$Root       = $PSScriptRoot
$BackendDir = Join-Path $Root 'backend'
$LogsDir    = Join-Path (Join-Path $Root 'data') 'logs'
if ($OnWindows) { $VenvPython = Join-Path (Join-Path (Join-Path $BackendDir '.venv') 'Scripts') 'python.exe' }
else            { $VenvPython = Join-Path (Join-Path (Join-Path $BackendDir '.venv') 'bin') 'python' }

try { $Host.UI.RawUI.WindowTitle = 'NEXUS AI - Backend' } catch { }

function Test-PortFree([int]$p) {
    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $p)
        $listener.Start(); return $true
    } catch { return $false } finally { if ($listener) { $listener.Stop() } }
}

Write-Host "NEXUS AI backend" -ForegroundColor Magenta

if (-not (Test-Path $VenvPython)) {
    Write-Host "[FAILED] Python virtual environment not found at backend\.venv" -ForegroundColor Red
    Write-Host "         Run setup first:  powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1" -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Path (Join-Path $Root '.env'))) {
    Write-Host "[WARN] No .env file - running with defaults (LOCAL TEST MODE)." -ForegroundColor Yellow
}
if (-not (Test-PortFree $Port)) {
    try {
        $h = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 3
        if ($h.app -eq 'NEXUS AI') {
            Write-Host "[OK] The NEXUS AI backend is already running on port $Port." -ForegroundColor Green
            exit 0
        }
    } catch { }
    Write-Host "[FAILED] Port $Port is used by another program." -ForegroundColor Red
    Write-Host "         Run .\stop_all.bat, or close the program using port $Port, then try again." -ForegroundColor Yellow
    exit 1
}

# Record our PID so stop_all can stop exactly this process tree.
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null
Set-Content -Path (Join-Path $LogsDir 'backend.pid') -Value $PID -Encoding ascii

$uvArgs = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$Port")
if (-not $NoReload) { $uvArgs += @('--reload', '--reload-dir', 'app') }

Write-Host "API:       http://localhost:$Port"
Write-Host "API docs:  http://localhost:$Port/docs"
Write-Host "Press Ctrl+C to stop." -ForegroundColor Gray
Write-Host ""

Push-Location $BackendDir
try {
    & $VenvPython @uvArgs
    $code = $LASTEXITCODE
} finally {
    Pop-Location
    Remove-Item (Join-Path $LogsDir 'backend.pid') -ErrorAction SilentlyContinue
}
if ($code -ne 0) {
    Write-Host ""
    Write-Host "[FAILED] The backend stopped with exit code $code. Read the error above." -ForegroundColor Red
}
exit $code
