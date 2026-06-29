[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$automationRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent (Split-Path -Parent $automationRoot)
$samplesDir = Join-Path $automationRoot "samples"
$softDentDestination = Join-Path $repoRoot "app\data\imports\softdent"
$quickBooksDestination = Join-Path $repoRoot "app\data\imports\quickbooks"

$seedFiles = @(
    @{ Source = "softdent_ar_aging.csv"; DestinationDir = $softDentDestination },
    @{ Source = "quickbooks_revenue.csv"; DestinationDir = $quickBooksDestination },
    @{ Source = "quickbooks_expenses.csv"; DestinationDir = $quickBooksDestination }
)

New-Item -ItemType Directory -Path $softDentDestination -Force | Out-Null
New-Item -ItemType Directory -Path $quickBooksDestination -Force | Out-Null

$seeded = 0
foreach ($entry in $seedFiles) {
    $sourceFile = Join-Path $samplesDir $entry.Source
    $destinationFile = Join-Path $entry.DestinationDir $entry.Source
    if (-not (Test-Path $sourceFile)) {
        throw "Missing sample file: $sourceFile"
    }
    if ((Test-Path $destinationFile) -and -not $Force) {
        Write-Host "Skipped existing file: $destinationFile"
        continue
    }
    Copy-Item $sourceFile $destinationFile -Force
    $seeded += 1
    Write-Host "Seeded $($entry.Source) -> $($entry.DestinationDir)"
}

Write-Host "HAL import sample seed complete. Files written: $seeded."
