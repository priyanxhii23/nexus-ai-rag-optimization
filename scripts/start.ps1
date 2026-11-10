# NEXUS AI - start backend + frontend in two separate windows.
# Started by double-clicking START.bat. Close the two windows to stop.

$root     = Split-Path $PSScriptRoot -Parent
$backend  = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$venvPy   = Join-Path $backend '.venv\Scripts\python.exe'

if (-not (Test-Path $venvPy) -or -not (Test-Path (Join-Path $frontend 'node_modules'))) {
    Write-Host "Setup has not been completed. Double-click SETUP.bat first." -ForegroundColor Red
    exit 1
}

$backendCmd  = "`$host.UI.RawUI.WindowTitle='NEXUS backend'; Set-Location -LiteralPath '$backend'; & '$venvPy' -m uvicorn app.main:app --reload --port 8000"
$frontendCmd = "`$host.UI.RawUI.WindowTitle='NEXUS frontend'; Set-Location -LiteralPath '$frontend'; npm run dev"

Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-Command', $backendCmd
Start-Sleep -Seconds 4
Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-Command', $frontendCmd

Write-Host "Waiting for the servers to start..."
$up = $false
foreach ($i in 1..20) {
    Start-Sleep -Seconds 1
    try { Invoke-WebRequest 'http://localhost:5173' -UseBasicParsing -TimeoutSec 2 | Out-Null; $up = $true; break } catch {}
}
if ($up) {
    Start-Process 'http://localhost:5173'
    Write-Host "NEXUS AI is running at http://localhost:5173" -ForegroundColor Green
} else {
    Write-Host "Frontend did not respond yet. Check the 'NEXUS frontend' window for errors." -ForegroundColor Yellow
}
