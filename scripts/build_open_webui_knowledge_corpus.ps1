# Builds a curated Open WebUI knowledge-import bundle from repo docs and current local exports.

[CmdletBinding()]
param(
	[string]$ProjectRoot,
	[string]$OutputRoot = "C:\Users\mreno\open-webui-data\knowledge-imports\newridge-family-financial"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
	$ProjectRoot = Split-Path -Parent $PSScriptRoot
}

$coreDocs = @(
	"README.md",
	"ARCHITECTURE.md",
	"docs\API.md",
	"docs\export_automation_instructions.md",
	"docs\hal_phi_rag_architecture.md",
	"docs\quickbooks_desktop_safe_architecture.md",
	"docs\schedule_softdent_bridge_sync.md",
	"docs\softdent_bridge_automation.md"
)

$accountingDocs = @(
	"docs\accounting\accounting_policy_playbook.md",
	"docs\accounting\month_end_close_checklist.md"
)

$liveExports = @(
	"softdent_dashboard_data.json",
	"softdent_claims_export.csv",
	"softdent_clinical_notes_data.json",
	"test_dashboard.json"
)

function New-CleanDirectory {
	param([string]$Path)

	if (Test-Path $Path) {
		Remove-Item -Path $Path -Recurse -Force
	}

	New-Item -ItemType Directory -Path $Path -Force | Out-Null
}

function Copy-ExistingFiles {
	param(
		[string]$SourceRoot,
		[string[]]$RelativePaths,
		[string]$DestinationRoot,
		[System.Collections.Generic.List[object]]$Manifest,
		[string]$CollectionName
	)

	foreach ($relativePath in $RelativePaths) {
		$sourcePath = Join-Path $SourceRoot $relativePath
		if (-not (Test-Path $sourcePath)) {
			Write-Warning "Skipping missing file: $sourcePath"
			continue
		}

		$destinationPath = Join-Path $DestinationRoot $relativePath
		$destinationDir = Split-Path -Parent $destinationPath
		if (-not (Test-Path $destinationDir)) {
			New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null
		}

		Copy-Item -Path $sourcePath -Destination $destinationPath -Force
		$fileInfo = Get-Item $destinationPath

		$Manifest.Add([pscustomobject]@{
			collection = $CollectionName
			relative_path = $relativePath
			source_path = $sourcePath
			destination_path = $destinationPath
			size_bytes = $fileInfo.Length
			last_write_time_utc = $fileInfo.LastWriteTimeUtc.ToString("o")
		}) | Out-Null
	}
}

if (-not (Test-Path $ProjectRoot)) {
	throw "Project root not found: $ProjectRoot"
}

$stagedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
$collections = @(
	@{ Name = "01-core-docs"; Paths = $coreDocs; Title = "Core repo docs" },
	@{ Name = "02-accounting-policies"; Paths = $accountingDocs; Title = "Accounting playbooks" },
	@{ Name = "03-live-softdent-exports"; Paths = $liveExports; Title = "Current local exports" }
)

New-CleanDirectory -Path $OutputRoot

$manifest = New-Object 'System.Collections.Generic.List[object]'

foreach ($collection in $collections) {
	$collectionRoot = Join-Path $OutputRoot $collection.Name
	New-Item -ItemType Directory -Path $collectionRoot -Force | Out-Null

	Copy-ExistingFiles -SourceRoot $ProjectRoot -RelativePaths $collection.Paths -DestinationRoot $collectionRoot -Manifest $manifest -CollectionName $collection.Name
}

$overview = @"
# New Ridge Family Financial Open WebUI Knowledge Bundle

Staged at UTC: $stagedAtUtc

This folder is built for local Open WebUI knowledge ingestion.

## Recommended Collection Order

1. `01-core-docs`
2. `02-accounting-policies`
3. `03-live-softdent-exports`

## Collection Notes

- `01-core-docs` gives the model repo boundaries, API behavior, SoftDent bridge workflow, QuickBooks safety rules, and PHI-safe HAL guidance.
- `02-accounting-policies` gives the model close-process and policy context for accounting questions.
- `03-live-softdent-exports` gives the model the freshest local operational data already staged in this repo.

## Suggested Usage In Open WebUI

- Create a knowledge collection for docs and policy context first.
- Create a separate knowledge collection for live SoftDent exports so you can refresh it independently.
- Re-run `scripts\build_open_webui_knowledge_corpus.ps1` whenever docs or local export files change.

## Output Manifest

See `manifest.json` for the staged file inventory.
"@

$overview | Set-Content -Path (Join-Path $OutputRoot "00-upload-order.md") -Encoding UTF8

$manifestPayload = [pscustomobject]@{
	staged_at_utc = $stagedAtUtc
	project_root = $ProjectRoot
	output_root = $OutputRoot
	files = $manifest
}

$manifestPayload | ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $OutputRoot "manifest.json") -Encoding UTF8

Write-Host "Open WebUI knowledge bundle created at $OutputRoot"
Write-Host "Collections staged: $($collections.Name -join ', ')"
Write-Host "Files staged: $($manifest.Count)"