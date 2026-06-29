[CmdletBinding()]
param(
    [string]$SoftDentSource = $env:NR2_SOFTDENT_EXPORT_SOURCE,
    [string]$QuickBooksSource = $env:NR2_QUICKBOOKS_EXPORT_SOURCE,
    [switch]$Watch,
    [int]$DebounceMs = 750
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$repoRoot = Split-Path -Parent $projectRoot

if ([string]::IsNullOrWhiteSpace($SoftDentSource)) {
    $SoftDentSource = "C:\Users\mreno\SoftDentBridge\exports"
}

if ([string]::IsNullOrWhiteSpace($QuickBooksSource)) {
    $QuickBooksSource = "C:\Users\mreno\QuickBooksExports"
}

$softDentFiles = @(
    "softdent_dashboard_data.json",
    "softdent_dashboard_export.json",
    "softdent_dashboard_data.csv",
    "softdent_claims_export.csv",
    "softdent_claims_data.csv",
    "softdent_claims_export.json",
    "softdent_clinical_notes_data.json",
    "softdent_clinical_notes_export.json",
    "softdent_ar_aging.csv",
    "softdent_accounts_receivable.csv",
    "softdent_ar_aging.json",
    "patient_aging.csv",
    "ar_aging.csv"
)

$quickBooksFiles = @(
    "quickbooks_revenue.csv",
    "quickbooks_revenue.json",
    "quickbooks_profit_and_loss.csv",
    "quickbooks_profit_loss.csv",
    "quickbooks_expenses.csv",
    "quickbooks_expense_detail.csv",
    "quickbooks_expense_categories.csv",
    "quickbooks_expenses.json",
    "quickbooks_ar.csv",
    "quickbooks_accounts_receivable.csv",
    "quickbooks_aging.csv"
)

function Resolve-ImportDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$EnvName,
        [Parameter(Mandatory = $true)]
        [string]$DefaultRelative
    )

    $configured = [Environment]::GetEnvironmentVariable($EnvName)
    if ([string]::IsNullOrWhiteSpace($configured)) {
        return (Join-Path $repoRoot $DefaultRelative)
    }

    if ([System.IO.Path]::IsPathRooted($configured)) {
        return $configured
    }

    return (Join-Path $repoRoot $configured)
}

function Copy-ApprovedFiles {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceDir,
        [Parameter(Mandatory = $true)]
        [string]$DestinationDir,
        [Parameter(Mandatory = $true)]
        [string[]]$ApprovedFiles,
        [Parameter(Mandatory = $true)]
        [string]$SourceName
    )

    if (-not (Test-Path $SourceDir)) {
        New-Item -ItemType Directory -Path $SourceDir -Force | Out-Null
        Write-Host "$SourceName source folder created: $SourceDir"
    }

    New-Item -ItemType Directory -Path $DestinationDir -Force | Out-Null

    $copied = 0
    foreach ($fileName in $ApprovedFiles) {
        $sourceFile = Join-Path $SourceDir $fileName
        if (-not (Test-Path $sourceFile)) {
            continue
        }

        $destinationFile = Join-Path $DestinationDir $fileName
        Copy-Item $sourceFile $destinationFile -Force
        $copied += 1
        Write-Host "Imported $SourceName file: $fileName -> $DestinationDir"
    }

    if ($copied -eq 0) {
        Write-Host "No approved $SourceName files found in $SourceDir"
    }

    return $copied
}

function Sync-HalImports {
    $softDentDestination = Resolve-ImportDirectory -EnvName "SOFTDENT_IMPORT_DIR" -DefaultRelative "app\data\imports\softdent"
    $quickBooksDestination = Resolve-ImportDirectory -EnvName "QUICKBOOKS_IMPORT_DIR" -DefaultRelative "app\data\imports\quickbooks"

    $softDentCopied = Copy-ApprovedFiles -SourceDir $SoftDentSource -DestinationDir $softDentDestination -ApprovedFiles $softDentFiles -SourceName "SoftDent"
    $quickBooksCopied = Copy-ApprovedFiles -SourceDir $QuickBooksSource -DestinationDir $quickBooksDestination -ApprovedFiles $quickBooksFiles -SourceName "QuickBooks"

    Write-Host "HAL import sync complete. SoftDent files: $softDentCopied. QuickBooks files: $quickBooksCopied."
    Write-Host "Read-only boundary: this script copies export files only. It never writes to SoftDent or QuickBooks."
}

Sync-HalImports

if (-not $Watch) {
    return
}

$global:lastSyncAt = Get-Date "2000-01-01"

function Request-Sync {
    $now = Get-Date
    if (($now - $global:lastSyncAt).TotalMilliseconds -lt $DebounceMs) {
        return
    }
    $global:lastSyncAt = $now
    Start-Sleep -Milliseconds $DebounceMs
    Sync-HalImports
}

$watchers = @()
foreach ($source in @($SoftDentSource, $QuickBooksSource)) {
    if (-not (Test-Path $source)) {
        New-Item -ItemType Directory -Path $source -Force | Out-Null
    }

    $watcher = New-Object System.IO.FileSystemWatcher $source, "*.*"
    $watcher.IncludeSubdirectories = $false
    $watcher.EnableRaisingEvents = $true
    Register-ObjectEvent $watcher Created -Action { Request-Sync } | Out-Null
    Register-ObjectEvent $watcher Changed -Action { Request-Sync } | Out-Null
    Register-ObjectEvent $watcher Renamed -Action { Request-Sync } | Out-Null
    $watchers += $watcher
}

Write-Host "Watching import folders:"
Write-Host "  SoftDent:   $SoftDentSource"
Write-Host "  QuickBooks: $QuickBooksSource"
Write-Host "Press Ctrl+C to stop."

while ($true) {
    Wait-Event -Timeout 5 | Out-Null
}
