<#
.SYNOPSIS
  Refresh desktop shortcuts for Start Program (NR2 pywebview desktop app).
#>
[CmdletBinding()]
param(
    [string[]]$Names = @('Start Program', 'New Ridge Financial')
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$Target = Join-Path $Root 'StartProgram.bat'
$Icon = Join-Path $Root 'assets\nr2-icon.ico'
$manifestPath = Join-Path $Root 'NewRidgeFinancial2\nr2-build.json'
$SchemaVersion = 'hal-94'
if (Test-Path $manifestPath) {
    try {
        $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
        if ($manifest.schemaVersion) { $SchemaVersion = [string]$manifest.schemaVersion }
    } catch {}
}

if (-not (Test-Path $Target)) { throw "Start Program launcher not found: $Target" }

function Get-DesktopFolders {
    $folders = New-Object System.Collections.Generic.List[string]
    $local = [Environment]::GetFolderPath('Desktop')
    if ($local) { $folders.Add($local) | Out-Null }
    try {
        $reg = Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders' -ErrorAction SilentlyContinue
        if ($reg -and $reg.Desktop) {
            $expanded = [Environment]::ExpandEnvironmentVariables([string]$reg.Desktop)
            if ($expanded -and (Test-Path $expanded) -and -not $folders.Contains($expanded)) {
                $folders.Add($expanded) | Out-Null
            }
        }
    } catch {}
    return $folders | Select-Object -Unique
}

$desktops = Get-DesktopFolders
$shell = New-Object -ComObject WScript.Shell

foreach ($desktop in $desktops) {
    foreach ($name in $Names) {
        $linkPath = Join-Path $desktop ("{0}.lnk" -f $name)
        $shortcut = $shell.CreateShortcut($linkPath)
        $shortcut.TargetPath = $Target
        $shortcut.WorkingDirectory = $Root
        if (Test-Path $Icon) { $shortcut.IconLocation = "$Icon,0" }
        $shortcut.Description = "Start Program - NewRidgeFinancial 2.0 desktop ($SchemaVersion)"
        $shortcut.WindowStyle = 7
        $shortcut.Save()
        Write-Host "Updated shortcut: $linkPath" -ForegroundColor Green
    }
}

$legacyPatterns = @('start_program.ps1', 'run_frontend_model.ps1', '127.0.0.1:1966', '127.0.0.1:8765', '5173', 'MissionControl', 'StartNewRidgeFinancial2.bat')
$scanRoots = $desktops + @(
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu'),
    (Join-Path $env:ProgramData 'Microsoft\Windows\Start Menu\Programs')
)

foreach ($root in ($scanRoots | Select-Object -Unique)) {
    if (-not (Test-Path $root)) { continue }
    Get-ChildItem $root -Recurse -Filter *.lnk -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            $sc = $shell.CreateShortcut($_.FullName)
            $hay = "$($sc.TargetPath) $($sc.Arguments)"
            foreach ($pattern in $legacyPatterns) {
                if ($hay -match [regex]::Escape($pattern)) {
                    Write-Host "LEGACY shortcut (update or delete): $($_.FullName) -> $hay" -ForegroundColor Yellow
                }
            }
        } catch {}
    }
}

Write-Host ""
Write-Host "Start Program: $Target" -ForegroundColor Cyan
Write-Host "Window title should show: NewRidgeFinancial 2.0 ($SchemaVersion)" -ForegroundColor Cyan
