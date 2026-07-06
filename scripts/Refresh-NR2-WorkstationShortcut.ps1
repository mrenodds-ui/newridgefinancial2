<#
.SYNOPSIS
  Create or refresh desktop shortcuts for NR2 Office Workstation (StartWorkstation.bat).
#>
[CmdletBinding()]
param(
    [string[]]$Names = @('NR2 Workstation', 'Start Workstation')
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$Target = Join-Path $Root 'StartWorkstation.bat'
$Icon = Join-Path $Root 'assets\nr2-icon.ico'
$manifestPath = Join-Path $Root 'NewRidgeFinancial2\nr2-build.json'
$SchemaVersion = 'unknown'
if (Test-Path $manifestPath) {
    try {
        $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
        if ($manifest.schemaVersion) { $SchemaVersion = [string]$manifest.schemaVersion }
    } catch {}
}

if (-not (Test-Path $Target)) { throw "Start Workstation launcher not found: $Target" }

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
        $shortcut.Description = "NR2 Office Workstation - messaging and Ask HAL ($SchemaVersion)"
        $shortcut.WindowStyle = 7
        $shortcut.Save()
        Write-Host "Updated shortcut: $linkPath" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Start Workstation: $Target" -ForegroundColor Cyan
Write-Host "Double-click NR2 Workstation on your desktop to launch the popup." -ForegroundColor Cyan
