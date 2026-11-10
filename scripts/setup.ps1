# NEXUS AI - one-time setup (Windows PowerShell 5.1+)
# Started by double-clicking SETUP.bat in the project folder.
# Everything is written to setup-log.txt so it can be shared if something fails.

$ErrorActionPreference = 'Continue'
$root     = Split-Path $PSScriptRoot -Parent
$backend  = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$log      = Join-Path $root 'setup-log.txt'
Start-Transcript -Path $log -Force | Out-Null

function Step($n, $text) { Write-Host ""; Write-Host "[$n] $text" -ForegroundColor Cyan }
function Ok($text)   { Write-Host "    OK   $text" -ForegroundColor Green }
function Fail($text) { Write-Host "    FAIL $text" -ForegroundColor Red; $script:failed = $true }
$failed = $false

Write-Host "=== NEXUS AI setup ===" -ForegroundColor White
Write-Host "Project folder: $root"

# ---------------------------------------------------------------- 1
Step 1 "Checking project files"
$need = @('backend\requirements.txt', 'backend\app\main.py', 'frontend\package.json', '.env.example')
$missing = $need | Where-Object { -not (Test-Path (Join-Path $root $_)) }
if ($missing) {
    Fail "Missing: $($missing -join ', ')"
    Write-Host "    SETUP.bat must sit in the nexus-ai folder next to 'backend' and 'frontend'." -ForegroundColor Yellow
    Stop-Transcript | Out-Null; exit 1
}
Ok "all project files present"
if ($root -match 'OneDrive') { Write-Host "    WARNING: folder is inside OneDrive - move it to C:\dev if npm fails." -ForegroundColor Yellow }

# ---------------------------------------------------------------- 2
Step 2 "Finding Python"
$pyCmd = $null
foreach ($v in '3.12', '3.11', '3.13') {
    $out = & py "-$v" --version 2>$null
    if ($LASTEXITCODE -eq 0 -and $out) { $pyCmd = @('py', "-$v"); Ok "using $out (via py -$v)"; break }
}
if (-not $pyCmd) {
    $out = & python --version 2>$null
    if ($LASTEXITCODE -eq 0 -and $out) { $pyCmd = @('python'); Ok "using $out (via python)" }
}
if (-not $pyCmd) { Fail "Python not found. Run:  winget install Python.Python.3.12  then run SETUP.bat again."; Stop-Transcript | Out-Null; exit 1 }

# ---------------------------------------------------------------- 3
Step 3 "Creating virtual environment (backend\.venv)"
$venvPy = Join-Path $backend '.venv\Scripts\python.exe'
if (Test-Path $venvPy) {
    Ok "already exists: $(& $venvPy --version)"
} else {
    $exe = $pyCmd[0]; $args1 = @($pyCmd | Select-Object -Skip 1) + @('-m', 'venv', (Join-Path $backend '.venv'))
    & $exe @args1
    if (Test-Path $venvPy) { Ok "created" } else { Fail "could not create venv"; Stop-Transcript | Out-Null; exit 1 }
}

# ---------------------------------------------------------------- 4
Step 4 "Installing backend packages (1-3 minutes)"
& $venvPy -m pip install --upgrade pip --quiet
& $venvPy -m pip install -r (Join-Path $backend 'requirements.txt') --quiet
if ($LASTEXITCODE -eq 0) { Ok "backend packages installed" } else { Fail "pip install failed (see messages above)" }

# ---------------------------------------------------------------- 5
Step 5 "Creating .env from .env.example"
$envFile = Join-Path $root '.env'
if (Test-Path $envFile) { Ok ".env already exists (left unchanged)" }
else { Copy-Item (Join-Path $root '.env.example') $envFile; Ok ".env created" }

# ---------------------------------------------------------------- 6
Step 6 "Running backend tests"
Push-Location $backend
& $venvPy -m pytest -q -p no:warnings
if ($LASTEXITCODE -eq 0) { Ok "all tests passed" } else { Fail "some tests failed" }
Pop-Location

# ---------------------------------------------------------------- 7
Step 7 "Checking Node.js"
$nodeV = & node --version 2>$null
if ($LASTEXITCODE -eq 0 -and $nodeV) { Ok "node $nodeV" }
else { Fail "Node.js not found. Run:  winget install OpenJS.NodeJS.LTS  then close this window and run SETUP.bat again."; Stop-Transcript | Out-Null; exit 1 }

# ---------------------------------------------------------------- 8
Step 8 "Installing frontend packages (1-3 minutes)"
Push-Location $frontend
& npm install --no-fund --no-audit
if ($LASTEXITCODE -eq 0) { Ok "frontend packages installed" } else { Fail "npm install failed (see messages above)" }
Pop-Location

# ---------------------------------------------------------------- done
Write-Host ""
if ($failed) {
    Write-Host "Setup finished WITH ERRORS. Send setup-log.txt (in the nexus-ai folder) to your mentor." -ForegroundColor Red
} else {
    Write-Host "Setup complete. Now double-click START.bat" -ForegroundColor Green
}
Stop-Transcript | Out-Null
