# SoftDent sample data seed script
# Regenerates the canonical sample exports and imports them into the canonical SoftDent import directory.

$projectRoot = Split-Path -Parent $PSScriptRoot
$generatorScript = Join-Path $projectRoot "DataAnalysisExpert\generate_softdent_bridge_samples.py"
$syncScript = Join-Path $projectRoot "scripts\sync_softdent_bridge.ps1"

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

if (-not (Test-Path $generatorScript)) {
	throw "Sample generator not found at $generatorScript"
}

if (-not (Test-Path $syncScript)) {
	throw "Sync script not found at $syncScript"
}

$pythonExe = Get-PythonExecutable

Write-Host "Generating SoftDent bridge sample exports..."
& $pythonExe $generatorScript
if ($LASTEXITCODE -ne 0) {
	throw "Sample export generation failed with exit code $LASTEXITCODE"
}

Write-Host "Importing SoftDent bridge sample exports into the canonical SoftDent import directory..."
& powershell -ExecutionPolicy Bypass -File $syncScript
if ($LASTEXITCODE -ne 0) {
	throw "Sample export staging failed with exit code $LASTEXITCODE"
}

Write-Host "SoftDent bridge sample data seeded successfully."