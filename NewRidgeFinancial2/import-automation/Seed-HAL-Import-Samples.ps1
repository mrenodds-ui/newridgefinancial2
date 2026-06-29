[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$Refresh
)

$ErrorActionPreference = "Stop"

$automationRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent (Split-Path -Parent $automationRoot)
$samplesDir = Join-Path $automationRoot "samples"
$softDentDestination = Join-Path $repoRoot "app\data\imports\softdent"
$quickBooksDestination = Join-Path $repoRoot "app\data\imports\quickbooks"

# Source = tracked sample filename in samples\. DestName = canonical import
# filename HAL reads. SoftDent samples use a .sample suffix so they can be
# tracked without tripping the PHI-protection .gitignore rules for the real
# softdent_* export filenames.
$seedFiles = @(
    @{ Source = "softdent_dashboard_data.sample.json"; DestName = "softdent_dashboard_data.json"; DestinationDir = $softDentDestination },
    @{ Source = "softdent_claims_export.sample.csv"; DestName = "softdent_claims_export.csv"; DestinationDir = $softDentDestination },
    @{ Source = "softdent_clinical_notes_data.sample.json"; DestName = "softdent_clinical_notes_data.json"; DestinationDir = $softDentDestination },
    @{ Source = "softdent_ar_aging.csv"; DestName = "softdent_ar_aging.csv"; DestinationDir = $softDentDestination },
    @{ Source = "quickbooks_revenue.csv"; DestName = "quickbooks_revenue.csv"; DestinationDir = $quickBooksDestination },
    @{ Source = "quickbooks_expenses.csv"; DestName = "quickbooks_expenses.csv"; DestinationDir = $quickBooksDestination }
)

New-Item -ItemType Directory -Path $softDentDestination -Force | Out-Null
New-Item -ItemType Directory -Path $quickBooksDestination -Force | Out-Null

$now = Get-Date
$seeded = 0
$refreshed = 0
foreach ($entry in $seedFiles) {
    $sourceFile = Join-Path $samplesDir $entry.Source
    $destinationFile = Join-Path $entry.DestinationDir $entry.DestName
    if (-not (Test-Path $sourceFile)) {
        throw "Missing sample file: $sourceFile"
    }

    $exists = Test-Path $destinationFile
    if ($exists -and -not $Force -and -not $Refresh) {
        Write-Host "Skipped existing file: $destinationFile"
        continue
    }

    if (-not $exists -or $Force) {
        Copy-Item $sourceFile $destinationFile -Force
        $seeded += 1
        Write-Host "Seeded $($entry.Source) -> $($entry.DestinationDir)"
    }

    # Stamp the destination as current so HAL's source-freshness panel reports
    # an up-to-date import. Copy-Item preserves the source timestamp, so this
    # explicit write is what makes freshness read "current".
    (Get-Item $destinationFile).LastWriteTime = $now
    if ($exists) { $refreshed += 1 }
}

Write-Host "HAL import sample seed complete. Seeded: $seeded. Refreshed timestamps: $refreshed."
Write-Host "Read-only boundary: this writes only HAL's local import cache. It never touches SoftDent or QuickBooks."
