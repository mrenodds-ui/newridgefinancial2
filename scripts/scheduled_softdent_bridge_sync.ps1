# SoftDent Bridge Scheduled Sync Script
# Copies the expected export files into the canonical SoftDent import directory and refreshes the dashboard state.

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

if (-not (Test-Path $sourcePath)) {
    New-Item -ItemType Directory -Path $sourcePath -Force | Out-Null
}

$destinationRoot = Get-SoftDentImportDirectory
New-Item -ItemType Directory -Path $destinationRoot -Force | Out-Null

$copied = $false
foreach ($fileName in $trackedFiles) {
    $sourceFile = Join-Path $sourcePath $fileName
    if (-not (Test-Path $sourceFile)) {
        continue
    }

    $destinationPath = Join-Path $destinationRoot $fileName
    Copy-Item $sourceFile $destinationPath -Force
    Write-Host "Imported $fileName to $destinationPath"
    $copied = $true
}

if (-not $copied) {
    Write-Host "No SoftDent bridge exports were present under $sourcePath"
    exit 0
}

$pythonExe = Get-PythonExecutable
$refreshScript = Join-Path $projectRoot "scripts\refresh_from_softdent_and_verify.py"
& $pythonExe $refreshScript

Write-Host "Scheduled sync complete."
