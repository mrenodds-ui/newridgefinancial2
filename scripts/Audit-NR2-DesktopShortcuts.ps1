<#
.SYNOPSIS
  Audit desktop and Start Menu shortcuts that launch NR2 or legacy frontends.
#>
[CmdletBinding()]
param(
    [switch]$FixShortcuts,
    [switch]$VerboseLinks
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$Target = Join-Path $Root 'StartProgram.bat'
$Nr2Dir = Join-Path $Root 'NewRidgeFinancial2'
$manifestPath = Join-Path $Nr2Dir 'nr2-build.json'
$schemaVersion = 'hal-94'
if (Test-Path $manifestPath) {
    try {
        $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
        if ($manifest.schemaVersion) { $schemaVersion = [string]$manifest.schemaVersion }
    } catch {}
}

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

$legacyPatterns = @(
    'start_program.ps1',
    'run_frontend_model.ps1',
    '127.0.0.1:1966',
    '127.0.0.1:8765',
    ':5173',
    'MissionControl',
    'StartNewRidgeFinancial2.bat',
    'desktop_app.py',
    'PATCH_BACKUP'
)

$canonicalPatterns = @('StartProgram.bat', 'start_program.ps1', 'start_nr2_desktop.ps1')

$scanRoots = (Get-DesktopFolders) + @(
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu'),
    (Join-Path $env:ProgramData 'Microsoft\Windows\Start Menu\Programs'),
    $Root
)

$shell = New-Object -ComObject WScript.Shell
$rows = New-Object System.Collections.Generic.List[object]

foreach ($root in ($scanRoots | Select-Object -Unique)) {
    if (-not (Test-Path $root)) { continue }
    Get-ChildItem $root -Recurse -Filter *.lnk -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            $sc = $shell.CreateShortcut($_.FullName)
            $hay = "$($sc.TargetPath) $($sc.Arguments) $($sc.WorkingDirectory)"
            $isNr2 = $hay -match 'NewRidgeFamilyFinancial|NewRidgeFinancial2|StartProgram|desktop_app\.py|start_nr2_desktop|start_nr2_1966'
            if (-not $isNr2) { return }

            $status = 'ok'
            foreach ($pattern in $legacyPatterns) {
                if ($hay -match [regex]::Escape($pattern)) {
                    $status = 'legacy'
                    break
                }
            }
            if ($status -eq 'ok' -and $sc.TargetPath -ne $Target -and $hay -notmatch 'StartProgram\.bat') {
                if ($hay -match 'desktop_app\.py|start_nr2_desktop|start_nr2_1966|start_program\.ps1') {
                    $status = 'indirect'
                }
            }

            $rows.Add([pscustomobject]@{
                Status = $status
                Path = $_.FullName
                Target = $sc.TargetPath
                Arguments = $sc.Arguments
                WorkingDirectory = $sc.WorkingDirectory
            }) | Out-Null
        } catch {}
    }
}

Write-Host "NR2 shortcut audit (expected target: $Target, schema: $schemaVersion)" -ForegroundColor Cyan
Write-Host ""

$grouped = $rows | Sort-Object Status, Path
if (-not $grouped -or $grouped.Count -eq 0) {
    Write-Host 'No NR2-related shortcuts found.' -ForegroundColor Yellow
} else {
    foreach ($row in $grouped) {
        $color = switch ($row.Status) {
            'ok' { 'Green' }
            'indirect' { 'Yellow' }
            default { 'Red' }
        }
        Write-Host "[$($row.Status.ToUpper())] $($row.Path)" -ForegroundColor $color
        if ($VerboseLinks) {
            Write-Host "  Target: $($row.Target)" -ForegroundColor DarkGray
            Write-Host "  Args: $($row.Arguments)" -ForegroundColor DarkGray
            Write-Host "  CWD: $($row.WorkingDirectory)" -ForegroundColor DarkGray
        }
    }
}

$legacyCount = @($grouped | Where-Object { $_.Status -ne 'ok' }).Count
if ($legacyCount -gt 0) {
    Write-Host ""
    Write-Host "$legacyCount shortcut(s) need attention." -ForegroundColor Yellow
    Write-Host "Run: scripts\Refresh-NR2-DesktopShortcut.ps1" -ForegroundColor Yellow
}

if ($FixShortcuts) {
    $refresh = Join-Path $PSScriptRoot 'Refresh-NR2-DesktopShortcut.ps1'
    if (-not (Test-Path $refresh)) { throw "Refresh script not found: $refresh" }
    & $refresh
}

if ($legacyCount -gt 0) { exit 1 }
exit 0
