<#
.SYNOPSIS
    Used by stop_all.bat: stops the NEXUS AI backend and frontend.

    1. Stops the process tree recorded in data\logs\*.pid (the windows that
       start_backend.ps1 / start_frontend.ps1 opened, plus their children).
    2. As a fallback, stops python/node/uvicorn processes still LISTENING on
       ports 8000 / 5173. Other programs on those ports are left alone.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Continue'
$OnWindows = ($env:OS -eq 'Windows_NT')
$Root      = Split-Path -Parent $PSScriptRoot
$LogsDir   = Join-Path (Join-Path $Root 'data') 'logs'

function Stop-Tree([int]$procId) {
    if ($OnWindows) {
        & taskkill.exe /PID $procId /T /F 2>&1 | Out-Null
    } else {
        $kids = @(& ps -o pid= --ppid $procId 2>$null | ForEach-Object { [int]$_.Trim() })
        foreach ($k in $kids) { Stop-Tree $k }
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
}

function Get-ListenerPids([int]$port) {
    if ($OnWindows) {
        return @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
                 Select-Object -ExpandProperty OwningProcess -Unique)
    }
    if (Get-Command lsof -ErrorAction SilentlyContinue) {
        return @(& lsof -t "-iTCP:$port" -sTCP:LISTEN 2>$null | ForEach-Object { [int]$_ })
    }
    return @()
}

$stoppedAny = $false
foreach ($svc in @(@{ Name = 'backend'; Port = 8000 }, @{ Name = 'frontend'; Port = 5173 })) {
    $pidFile = Join-Path $LogsDir "$($svc.Name).pid"
    if (Test-Path $pidFile) {
        $recorded = [int](Get-Content $pidFile -Raw).Trim()
        if (Get-Process -Id $recorded -ErrorAction SilentlyContinue) {
            Stop-Tree $recorded
            Write-Host "[OK] Stopped $($svc.Name) (process tree $recorded)" -ForegroundColor Green
            $stoppedAny = $true
        }
        Remove-Item $pidFile -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 500
    foreach ($p in (Get-ListenerPids $svc.Port)) {
        $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
        if (-not $proc) { continue }
        if ($proc.ProcessName -match '^(python|python3.*|node|uvicorn)$') {
            Stop-Tree $p
            Write-Host "[OK] Stopped $($proc.ProcessName) listening on port $($svc.Port) (PID $p)" -ForegroundColor Green
            $stoppedAny = $true
        } else {
            Write-Host "[WARN] Port $($svc.Port) is used by '$($proc.ProcessName)' (PID $p) - not a NEXUS AI process, left running." -ForegroundColor Yellow
        }
    }
}
if (-not $stoppedAny) { Write-Host "Nothing to stop - NEXUS AI was not running." }
exit 0
