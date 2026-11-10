# NEXUS AI - environment checker (Windows PowerShell)
# Run from the project root:   .\scripts\check_env.ps1
# Then copy the whole output and paste it back to your mentor.

function Check($label, $cmd) {
    try {
        $out = Invoke-Expression $cmd 2>&1 | Select-Object -First 1
        Write-Host ("[OK]   {0,-14} {1}" -f $label, $out) -ForegroundColor Green
    } catch {
        Write-Host ("[MISS] {0,-14} not found" -f $label) -ForegroundColor Red
    }
}

Write-Host "`n=== NEXUS AI prerequisite check ===`n"
Check "Python 3.12" "py -3.12 --version"
Check "Python (any)" "python --version"
Check "pip" "py -3.12 -m pip --version"
Check "Node.js" "node --version"
Check "npm" "npm --version"
Check "Git" "git --version"
Check "VS Code" "code --version"

$os  = Get-CimInstance Win32_OperatingSystem
$ram = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
$disk = Get-PSDrive -Name (Get-Location).Drive.Name
Write-Host ("`nOS:        {0}" -f $os.Caption)
Write-Host ("RAM:       {0} GB" -f $ram)
Write-Host ("Free disk: {0} GB on drive {1}:" -f [math]::Round($disk.Free/1GB,1), $disk.Name)
Write-Host ("Exec policy (CurrentUser): {0}" -f (Get-ExecutionPolicy -Scope CurrentUser))
Write-Host ("Long paths enabled: {0}" -f ((Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -ErrorAction SilentlyContinue).LongPathsEnabled -eq 1))
Write-Host ""
