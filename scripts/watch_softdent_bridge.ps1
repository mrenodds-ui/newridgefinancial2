# RETIRED — NewRidgeFinancial 2.0 uses NewRidgeFinancial2\import-automation\Sync-HAL-Imports.ps1
Write-Error @"
RETIRED: This legacy SoftDent bridge watcher is no longer used.
Use: NewRidgeFinancial2\import-automation\Sync-HAL-Imports.ps1 -Watch
"@
exit 1

# SoftDent Bridge Automation Script
# Watches the bridge export drop for dashboard, claims, and clinical note files and copies them into the canonical SoftDent import directory.

$projectRoot = Split-Path -Parent $PSScriptRoot
$sourcePath = "C:\Users\mreno\SoftDentBridge\exports"
$trackedFiles = @(
    "softdent_dashboard_data.json",
    "softdent_claims_export.csv",
    "softdent_clinical_notes_data.json"
)

function Get-SoftDentImportDirectory {
    $configured = $env:SOFTDENT_IMPORT_DIR
    if ([string]::IsNullOrWhiteSpace($configured)) {
        return (Join-Path $projectRoot "app\data\imports\softdent")
    }

    if ([System.IO.Path]::IsPathRooted($configured)) {
        return $configured
    }

    return (Join-Path $projectRoot $configured)
}

function Get-PythonExecutable {
    $preferred = Join-Path $projectRoot ".venv\Scripts\python.exe"
    if (Test-Path $preferred) {
        return $preferred
    }

    $fallback = Join-Path $projectRoot ".venv-py313\Scripts\python.exe"
    if (Test-Path $fallback) {
        return $fallback
    }

    throw "Python virtual environment not found under $projectRoot"
}

function Sync-BridgeExportFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceFile
    )

    $fileName = [System.IO.Path]::GetFileName($SourceFile)
    if ($trackedFiles -notcontains $fileName) {
        return
    }

    $destinationRoot = Get-SoftDentImportDirectory
    New-Item -ItemType Directory -Path $destinationRoot -Force | Out-Null
    $destinationPath = Join-Path $destinationRoot $fileName
    Copy-Item $SourceFile $destinationPath -Force
    Write-Host "Imported $fileName to $destinationPath"

    $pythonExe = Get-PythonExecutable
    $refreshScript = Join-Path $projectRoot "scripts\refresh_from_softdent_and_verify.py"
    & $pythonExe $refreshScript
}

if (-not (Test-Path $sourcePath)) {
    New-Item -ItemType Directory -Path $sourcePath -Force | Out-Null
}

$watcher = New-Object System.IO.FileSystemWatcher $sourcePath, "*.*"
$watcher.IncludeSubdirectories = $false
$watcher.EnableRaisingEvents = $true

$action = {
    $src = $Event.SourceEventArgs.FullPath
    if (-not (Test-Path $src)) {
        return
    }

    Sync-BridgeExportFile -SourceFile $src
}

Register-ObjectEvent $watcher Created -Action $action | Out-Null
Register-ObjectEvent $watcher Changed -Action $action | Out-Null
Register-ObjectEvent $watcher Renamed -Action $action | Out-Null

Write-Host "Watching $sourcePath for SoftDent export updates. Press Enter to exit."
[Console]::ReadLine()
