<#
.SYNOPSIS
    Used by start_all.bat: waits until backend and frontend respond, prints the
    URLs and opens the dashboard in your browser.
#>
[CmdletBinding()]
param([int]$TimeoutSeconds = 120, [switch]$NoBrowser)

$ErrorActionPreference = 'Stop'
$OnWindows = ($env:OS -eq 'Windows_NT')

function Wait-Url([string]$name, [string]$url, [int]$timeout) {
    $deadline = (Get-Date).AddSeconds($timeout)
    Write-Host -NoNewline "Waiting for $name "
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $url -TimeoutSec 3 -UseBasicParsing
            if ($r.StatusCode -eq 200) { Write-Host " ready" -ForegroundColor Green; return $true }
        } catch { }
        Write-Host -NoNewline "."
        Start-Sleep -Seconds 2
    }
    Write-Host " not responding" -ForegroundColor Red
    return $false
}

$backendOk  = Wait-Url 'backend ' 'http://127.0.0.1:8000/api/health' $TimeoutSeconds
$frontendOk = Wait-Url 'frontend' 'http://localhost:5173/' $TimeoutSeconds

Write-Host ""
if ($backendOk -and $frontendOk) {
    Write-Host "NEXUS AI is running:" -ForegroundColor Green
    Write-Host "  Dashboard : http://localhost:5173"
    Write-Host "  Backend   : http://localhost:8000"
    Write-Host "  API docs  : http://localhost:8000/docs"
    Write-Host ""
    Write-Host "To stop everything run stop_all.bat (or press Ctrl+C in each window)."
    if ($OnWindows -and -not $NoBrowser) { Start-Process 'http://localhost:5173' }
    exit 0
}
if (-not $backendOk)  { Write-Host "The BACKEND did not start. Read the error in the 'NEXUS AI - Backend' window." -ForegroundColor Red }
if (-not $frontendOk) { Write-Host "The FRONTEND did not start. Read the error in the 'NEXUS AI - Frontend' window." -ForegroundColor Red }
exit 1
