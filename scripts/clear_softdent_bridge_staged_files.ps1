# SoftDent staged-data clear script
# Removes the canonical SoftDent import files so the app no longer reads the current bridge or demo exports.

$projectRoot = Split-Path -Parent $PSScriptRoot
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

$destinationRoot = Get-SoftDentImportDirectory

$removed = @()
$alreadyMissing = @()

foreach ($fileName in $trackedFiles) {
	$targetPath = Join-Path $destinationRoot $fileName
	if (Test-Path $targetPath) {
		Remove-Item $targetPath -Force
		$removed += $targetPath
		Write-Host "Removed canonical SoftDent import file $targetPath"
		continue
	}

	$alreadyMissing += $targetPath
	Write-Host "Already absent: $targetPath"
}

$summary = [ordered]@{
	removed = $removed
	already_missing = $alreadyMissing
}

$summary | ConvertTo-Json -Depth 2
Write-Host "SoftDent canonical import files cleared. Bridge source exports were left untouched."