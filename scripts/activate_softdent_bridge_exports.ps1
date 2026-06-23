# SoftDent bridge export activation script
# Clears canonical SoftDent import files, then imports whatever is currently present in the bridge export drop.

$projectRoot = Split-Path -Parent $PSScriptRoot
$clearScript = Join-Path $projectRoot "scripts\clear_softdent_bridge_staged_files.ps1"
$syncScript = Join-Path $projectRoot "scripts\sync_softdent_bridge.ps1"

if (-not (Test-Path $clearScript)) {
	throw "Clear script not found at $clearScript"
}

if (-not (Test-Path $syncScript)) {
	throw "Sync script not found at $syncScript"
}

Write-Host "Clearing canonical SoftDent import files..."
& powershell -ExecutionPolicy Bypass -File $clearScript
if ($LASTEXITCODE -ne 0) {
	throw "Clearing staged SoftDent files failed with exit code $LASTEXITCODE"
}

Write-Host "Importing current SoftDent bridge exports into the canonical SoftDent import directory..."
& powershell -ExecutionPolicy Bypass -File $syncScript
if ($LASTEXITCODE -ne 0) {
	throw "Staging bridge exports failed with exit code $LASTEXITCODE"
}

Write-Host "Current SoftDent bridge exports are active in the canonical SoftDent import directory."