# SoftDent demo-mode activation script
# Clears canonical SoftDent import files, regenerates canonical sample exports, and imports them.

$projectRoot = Split-Path -Parent $PSScriptRoot
$clearScript = Join-Path $projectRoot "scripts\clear_softdent_bridge_staged_files.ps1"
$seedScript = Join-Path $projectRoot "scripts\seed_softdent_bridge_samples.ps1"

if (-not (Test-Path $clearScript)) {
	throw "Clear script not found at $clearScript"
}

if (-not (Test-Path $seedScript)) {
	throw "Seed script not found at $seedScript"
}

Write-Host "Clearing canonical SoftDent import files..."
& powershell -ExecutionPolicy Bypass -File $clearScript
if ($LASTEXITCODE -ne 0) {
	throw "Clearing staged SoftDent files failed with exit code $LASTEXITCODE"
}

Write-Host "Rebuilding and importing canonical SoftDent demo exports..."
& powershell -ExecutionPolicy Bypass -File $seedScript
if ($LASTEXITCODE -ne 0) {
	throw "Activating SoftDent demo mode failed with exit code $LASTEXITCODE"
}

Write-Host "SoftDent demo mode is active in the canonical SoftDent import directory."