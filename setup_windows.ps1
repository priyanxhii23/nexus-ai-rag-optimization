<#
.SYNOPSIS
    NEXUS AI - first-time setup (safe to re-run).

.DESCRIPTION
    1. Checks Python 3.11+, Node.js 22.12+, npm and Git
    2. Creates data folders and .env (from .env.example) if missing
    3. Creates the backend Python virtual environment (backend\.venv)
    4. Installs Python dependencies
    5. Installs frontend (npm) dependencies
    6. Validates configuration, initialises storage, downloads the embedding model

    It NEVER deletes or overwrites your .env, documents, database or vectors.

.EXAMPLE
    # From the project root in PowerShell:
    powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1

.PARAMETER SkipFrontend
    Skip "npm install".
.PARAMETER SkipModelDownload
    Skip pre-downloading the embedding model (it then downloads on first use).
.PARAMETER RunTests
    Also run the backend test suite (pytest) at the end.
#>
[CmdletBinding()]
param(
    [switch]$SkipFrontend,
    [switch]$SkipModelDownload,
    [switch]$RunTests
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

# ---------------------------------------------------------------- helpers
function Write-Step($msg)  { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "    [OK]   $msg" -ForegroundColor Green }
function Write-Warn2($msg) { Write-Host "    [WARN] $msg" -ForegroundColor Yellow }
function Write-Info($msg)  { Write-Host "    $msg" -ForegroundColor Gray }
function Fail($msg, $hint) {
    Write-Host ""
    Write-Host "    [FAILED] $msg" -ForegroundColor Red
    if ($hint) { Write-Host "    How to fix: $hint" -ForegroundColor Yellow }
    Write-Host ""
    exit 1
}

# Works on Windows PowerShell 5.1 (no $IsWindows variable) and PowerShell 7.
$OnWindows = ($env:OS -eq 'Windows_NT')

# Always work relative to the folder this script lives in (the project root),
# no matter which folder the terminal is currently in.
$Root        = $PSScriptRoot
$BackendDir  = Join-Path $Root 'backend'
$FrontendDir = Join-Path $Root 'frontend'
$VenvDir     = Join-Path $BackendDir '.venv'
if ($OnWindows) { $VenvPython = Join-Path (Join-Path $VenvDir 'Scripts') 'python.exe' }
else            { $VenvPython = Join-Path (Join-Path $VenvDir 'bin') 'python' }

Write-Host ""
Write-Host "  NEXUS AI - setup" -ForegroundColor Magenta
Write-Host "  Project folder: $Root"

# ---------------------------------------------------------------- 1. Python
Write-Step "Checking Python (3.11 or newer required)"

function Get-PythonVersion([string]$exe, [string[]]$extraArgs) {
    # Returns [version] or $null. Ignores the Windows Store "python" stub,
    # which prints nothing useful.
    try {
        $out = & $exe @extraArgs -c "import sys; print('%d.%d.%d' % sys.version_info[:3])" 2>$null
        if ($LASTEXITCODE -eq 0 -and "$out" -match '^\d+\.\d+\.\d+$') { return [version]"$out" }
    } catch { }
    return $null
}

$PythonExe = $null; $PythonArgs = @(); $PyVersion = $null
$candidates = @()
if ($OnWindows) {
    # The "py" launcher lets us pick a specific version even if several are installed.
    foreach ($v in @('3.12', '3.13', '3.11', '3.14')) { $candidates += ,@('py', @("-$v")) }
    $candidates += ,@('python', @())
} else {
    foreach ($exe in @('python3.12', 'python3.13', 'python3.11', 'python3')) { $candidates += ,@($exe, @()) }
}
foreach ($c in $candidates) {
    if (-not (Get-Command $c[0] -ErrorAction SilentlyContinue)) { continue }
    $ver = Get-PythonVersion $c[0] $c[1]
    if ($ver -and $ver -ge [version]'3.11.0') { $PythonExe = $c[0]; $PythonArgs = $c[1]; $PyVersion = $ver; break }
}
if (-not $PythonExe) {
    Fail "Python 3.11+ was not found." `
         "Install Python 3.12 from https://www.python.org/downloads/ and tick 'Add python.exe to PATH' during install. Then open a NEW terminal and run this script again."
}
Write-Ok "Python $PyVersion  ($PythonExe $($PythonArgs -join ' '))"

# ---------------------------------------------------------------- 2. Node / npm / git
Write-Step "Checking Node.js (22.12 or newer), npm and Git"
if (-not $SkipFrontend) {
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        Fail "Node.js was not found." "Install the Node.js 22 LTS (or newer) from https://nodejs.org/ then open a NEW terminal."
    }
    $nodeRaw = (& node --version).Trim().TrimStart('v')
    $nodeVer = [version]($nodeRaw -replace '[^0-9.].*$', '')
    if ($nodeVer -lt [version]'22.12.0') {
        Fail "Node.js $nodeRaw is too old (need 22.12+)." "Install the current Node.js LTS from https://nodejs.org/"
    }
    Write-Ok "Node.js $nodeRaw"
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        Fail "npm was not found." "npm ships with Node.js - reinstall Node.js from https://nodejs.org/"
    }
    Write-Ok "npm $((& npm --version) | Select-Object -Last 1)"
} else {
    Write-Info "Skipped (-SkipFrontend)"
}
if (Get-Command git -ErrorAction SilentlyContinue) {
    Write-Ok "$(& git --version)"
} else {
    Write-Warn2 "Git not found. The app still runs, but you need Git to publish to GitHub (https://git-scm.com/download/win)."
}

# ---------------------------------------------------------------- 3. folders + .env
Write-Step "Preparing data folders and .env"
foreach ($d in @('data', 'data\documents', 'data\chroma', 'data\benchmarks', 'data\models', 'data\logs')) {
    $p = Join-Path $Root ($d -replace '\\', [IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p | Out-Null; Write-Ok "Created $d" }
    else { Write-Ok "$d exists (kept)" }
}
$envFile = Join-Path $Root '.env'
$envExample = Join-Path $Root '.env.example'
if (Test-Path $envFile) {
    Write-Ok ".env exists (kept - not overwritten)"
} elseif (Test-Path $envExample) {
    Copy-Item $envExample $envFile
    Write-Ok "Created .env from .env.example  -> add your API keys there later"
} else {
    Fail ".env.example is missing." "Restore it from the repository (git checkout -- .env.example)."
}

# ---------------------------------------------------------------- 4. virtual environment
Write-Step "Creating the Python virtual environment (backend\.venv)"
if (Test-Path $VenvPython) {
    $venvVer = Get-PythonVersion $VenvPython @()
    if (-not $venvVer) {
        Fail "backend\.venv exists but is broken." "Delete the folder backend\.venv and run this script again."
    }
    Write-Ok "Existing virtual environment found (Python $venvVer) - reusing it"
} else {
    & $PythonExe @PythonArgs -m venv $VenvDir
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) {
        Fail "Could not create the virtual environment." "Make sure Python was installed with the 'venv' module (standard python.org installer)."
    }
    Write-Ok "Virtual environment created"
}

# ---------------------------------------------------------------- 5. Python packages
Write-Step "Installing Python packages (first time: several minutes, ~1 GB download for PyTorch)"
& $VenvPython -m pip install --upgrade pip --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { Fail "pip upgrade failed." "Check your internet connection and try again." }
& $VenvPython -m pip install -r (Join-Path $BackendDir 'requirements.txt') --disable-pip-version-check
if ($LASTEXITCODE -ne 0) {
    Fail "Installing Python packages failed (see the error above)." `
         "Check your internet connection. If the error mentions 'Microsoft Visual C++', install 'Microsoft C++ Build Tools'. Then run this script again."
}
Write-Ok "Python packages installed"

# ---------------------------------------------------------------- 6. frontend packages
if (-not $SkipFrontend) {
    Write-Step "Installing frontend packages (npm install)"
    Push-Location $FrontendDir
    try {
        & npm install --no-fund --no-audit
        $npmExit = $LASTEXITCODE
    } finally { Pop-Location }
    if ($npmExit -ne 0) { Fail "npm install failed (see the error above)." "Check your internet connection and run this script again." }
    Write-Ok "Frontend packages installed"
}

# ---------------------------------------------------------------- 7. initialise app
Write-Step "Validating configuration and initialising storage"
$initArgs = @((Join-Path (Join-Path $BackendDir 'scripts') 'init_app.py'))
if (-not $SkipModelDownload) { $initArgs += '--download-model' }
& $VenvPython @initArgs
if ($LASTEXITCODE -ne 0) { Fail "Initialisation failed (see messages above)." "Fix the reported problem and run this script again." }

if ($RunTests) {
    Write-Step "Running the backend tests (no paid API calls)"
    Push-Location $BackendDir
    try { & $VenvPython -m pytest -q; $testExit = $LASTEXITCODE } finally { Pop-Location }
    if ($testExit -ne 0) { Fail "Some backend tests failed (see above)." "Send the output above to your mentor." }
    Write-Ok "All backend tests passed"
}

# ---------------------------------------------------------------- done
Write-Host ""
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "  Next steps:"
Write-Host "    1. (Optional) put your API keys in .env  - without keys the app runs in TEST MODE (labelled mock answers)"
Write-Host "    2. Start everything:   .\start_all.bat"
Write-Host "    3. Open                http://localhost:5173"
Write-Host ""
exit 0
