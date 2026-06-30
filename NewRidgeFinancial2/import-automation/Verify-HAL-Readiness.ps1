[CmdletBinding()]
param(
    [switch]$Pull,
    [switch]$PullFull,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$repoRoot = Split-Path -Parent $projectRoot

function Import-DotEnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $name = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim()
        if ($name) { Set-Item -Path "Env:$name" -Value $value }
    }
}

Import-DotEnvFile (Join-Path $repoRoot ".env")
Import-DotEnvFile (Join-Path $projectRoot ".env")

function Resolve-RepoPath {
    param([string]$RelativeOrAbsolute)
    if ([string]::IsNullOrWhiteSpace($RelativeOrAbsolute)) { return $null }
    $candidate = $RelativeOrAbsolute
    if (-not [System.IO.Path]::IsPathRooted($candidate)) {
        $candidate = Join-Path $repoRoot $RelativeOrAbsolute
    }
    $resolved = Resolve-Path $candidate -ErrorAction SilentlyContinue
    if ($resolved) { return $resolved.Path }
    return (Join-Path $repoRoot $RelativeOrAbsolute)
}

function Get-EnvOrDefault {
    param([string]$Name, [string]$Default)
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value
}

$softdentDir = Resolve-RepoPath (Get-EnvOrDefault "SOFTDENT_IMPORT_DIR" "app_data/nr2/document_inbox/softdent")
$quickbooksDir = Resolve-RepoPath (Get-EnvOrDefault "QUICKBOOKS_IMPORT_DIR" "app_data/nr2/document_inbox/quickbooks")

function Find-NewestFile {
    param(
        [string]$Directory,
        [string[]]$Names
    )
    if (-not (Test-Path $Directory)) { return $null }
    $matches = @()
    foreach ($name in $Names) {
        $path = Join-Path $Directory $name
        if (Test-Path $path) { $matches += Get-Item $path }
    }
    if (-not $matches.Count) { return $null }
    return ($matches | Sort-Object LastWriteTime -Descending | Select-Object -First 1)
}

function Read-DashboardPeriods {
    param([string]$FilePath)
    if (-not $FilePath) { return @() }
    try {
        $raw = Get-Content -Raw -Encoding UTF8 $FilePath
        if ($FilePath -match '\.json$') {
            $data = $raw | ConvertFrom-Json
            $rows = if ($data -is [System.Array]) { @($data) } else { @($data) }
            return @($rows | ForEach-Object {
                $p = $null
                if ($_.PSObject.Properties.Name -contains "period") { $p = $_.period }
                elseif ($_.PSObject.Properties.Name -contains "Period") { $p = $_.Period }
                elseif ($_.PSObject.Properties.Name -contains "month") { $p = $_.month }
                elseif ($_.PSObject.Properties.Name -contains "Month") { $p = $_.Month }
                if ($p) { [string]$p }
            } | Where-Object { $_ } | Select-Object -Unique)
        }
        if ($FilePath -match '\.csv$') {
            return @((Import-Csv $FilePath | ForEach-Object {
                $p = $null
                if ($_.PSObject.Properties.Name -contains "period") { $p = $_.period }
                elseif ($_.PSObject.Properties.Name -contains "Period") { $p = $_.Period }
                elseif ($_.PSObject.Properties.Name -contains "Month") { $p = $_.Month }
                elseif ($_.PSObject.Properties.Name -contains "month") { $p = $_.month }
                if ($p) { [string]$p }
            } | Where-Object { $_ } | Select-Object -Unique))
        }
    } catch {
        return @()
    }
    return @()
}

function Read-CsvRowCount {
    param([string]$FilePath)
    if (-not $FilePath) { return 0 }
    try {
        return @((Import-Csv $FilePath)).Count
    } catch {
        return 0
    }
}

function Add-Check {
    param(
        [string]$Phase,
        [string]$Id,
        [string]$Label,
        [bool]$Ok,
        [string]$Detail,
        [string]$Action
    )
    $script:checks += [pscustomobject]@{
        Phase  = $Phase
        Id     = $Id
        Label  = $Label
        Ok     = $Ok
        Detail = $Detail
        Action = $Action
    }
}

$checks = @()

# --- Phase 1: highest impact ---
$claimsFile = Find-NewestFile $softdentDir @(
    "softdent_claims_export.csv",
    "softdent_claims_data.csv",
    "softdent_claims_export.json",
    "softdent_claims_data.json"
)
$claimsRows = if ($claimsFile -and $claimsFile.Extension -eq ".csv") { Read-CsvRowCount $claimsFile.FullName } else { if ($claimsFile) { 1 } else { 0 } }
Add-Check "1" "softdent.claims" "SoftDent claims export" ($null -ne $claimsFile -and $claimsRows -gt 0) `
    $(if ($claimsFile) { "$($claimsFile.Name) - $claimsRows row(s) - $($claimsFile.LastWriteTime)" } else { "No claims file in $softdentDir" }) `
    "Export claims from SoftDent to $softdentDir\softdent_claims_export.csv"

$dashboardFile = Find-NewestFile $softdentDir @(
    "softdent_dashboard_data.json",
    "softdent_dashboard_export.json",
    "softdent_dashboard_data.csv",
    "softdent_dashboard_export.csv"
)
$periods = Read-DashboardPeriods $(if ($dashboardFile) { $dashboardFile.FullName } else { $null })
$hasPriorMonth = $periods.Count -ge 2
Add-Check "1" "softdent.dashboard.depth" "SoftDent dashboard (2+ months)" $hasPriorMonth `
    $(if ($dashboardFile) { "$($dashboardFile.Name) - periods: $(if ($periods.Count) { $periods -join ', ' } else { 'none parsed' })" } else { "No dashboard file in $softdentDir" }) `
    "Add current + prior month rows to softdent_dashboard_data.json in $softdentDir"

$arFile = Find-NewestFile $softdentDir @(
    "softdent_ar_aging.csv",
    "softdent_accounts_receivable.csv",
    "softdent_ar_aging.json",
    "patient_aging.csv",
    "ar_aging.csv"
)
$arRows = if ($arFile -and $arFile.Extension -eq ".csv") { Read-CsvRowCount $arFile.FullName } else { if ($arFile) { 1 } else { 0 } }
Add-Check "1" "softdent.ar" "SoftDent A/R aging" ($null -ne $arFile -and $arRows -gt 0) `
    $(if ($arFile) { "$($arFile.Name) - $arRows bucket(s) - $($arFile.LastWriteTime)" } else { "No A/R file in $softdentDir" }) `
    "Refresh softdent_ar_aging.csv in $softdentDir"

# --- Phase 2: QuickBooks + documents ---
$qbFiles = @{
    "quickbooks.revenue"           = @("quickbooks_revenue.csv", "quickbooks_revenue.json")
    "quickbooks.expenses"          = @("quickbooks_expenses.csv", "quickbooks_expenses.json")
    "quickbooks.expenseCategories" = @("quickbooks_expense_categories.csv")
    "quickbooks.profitAndLoss"     = @("quickbooks_profit_and_loss.csv", "quickbooks_profit_loss.csv")
}
foreach ($key in $qbFiles.Keys) {
    $names = $qbFiles[$key]
    $file = Find-NewestFile $quickbooksDir $names
    Add-Check "2" $key "QuickBooks: $($names[0])" ($null -ne $file) `
        $(if ($file) { "$($file.Name) - $($file.LastWriteTime)" } else { "Missing in $quickbooksDir" }) `
        "Refresh $($names[0]) in $quickbooksDir (or run scheduled sync)"
}

# Documents store (nr2:v2:documents) via Python quick read
$docQueueCount = $null
$docSources = $null
$pendingReview = 0
$snapshotScript = Join-Path $projectRoot "hal_readiness_snapshot.py"
try {
    Push-Location $projectRoot
    if (Test-Path $snapshotScript) {
        $docJson = python $snapshotScript 2>$null
        if ($docJson) {
            $docState = $docJson | ConvertFrom-Json
            $docQueueCount = [int]$docState.queueCount
            $docSources = $docState.counts
            $pendingReview = [int]$docState.pendingReview
        }
    }
} catch {
    # optional
} finally {
    Pop-Location
}

Add-Check "2" "local.documents" "Documents page queue" ($docQueueCount -gt 0) `
    $(if ($docQueueCount -gt 0) {
        "Queue: $docQueueCount - QB $($docSources.quickbooks) - SD $($docSources.softdent) - OCR $($docSources.ocr) - pending review: $pendingReview"
    } else {
        "Empty - run Pull or drop exports + OCR inbox files"
    }) `
    "Ask HAL: Pull SoftDent and QuickBooks data - review pending OCR invoices in Documents page"

if ($pendingReview -gt 0) {
    Add-Check "2" "local.documents.review" "Staff: pending document review" $false `
        "$pendingReview invoice(s) still Pending Review" `
        "Open Accounting Documents - review Glidewell / Prairie Dental rows before period close"
}

# --- Phase 3: optional ---
$optionalSd = @{
    "softdent.newPatients"     = @("softdent_new_patients.csv", "new_patients.csv")
    "softdent.treatmentPlans"  = @("treatment_plan_summary.csv", "softdent_treatment_plan_summary.csv")
    "softdent.caseAcceptance"  = @("case_acceptance.csv", "softdent_case_acceptance.csv")
}
foreach ($key in $optionalSd.Keys) {
    $names = $optionalSd[$key]
    $file = Find-NewestFile $softdentDir $names
    Add-Check "3" $key "Optional: $($names[0])" ($null -ne $file) `
        $(if ($file) { "Found $($file.Name)" } else { "Not configured" }) `
        "Export only if you use the matching SoftDent practice widget"
}

# --- Report ---
$required = $checks | Where-Object { $_.Phase -in @("1", "2") -and $_.Id -ne "local.documents.review" }
$requiredMissing = @($required | Where-Object { -not $_.Ok })
$phase1Missing = @($checks | Where-Object { $_.Phase -eq "1" -and -not $_.Ok })
$optionalMissing = @($checks | Where-Object { $_.Phase -eq "3" -and -not $_.Ok })

if (-not $Quiet) {
    Write-Host ""
    Write-Host "HAL readiness check - New Ridge Financial" -ForegroundColor Cyan
    Write-Host "SoftDent cache:  $softdentDir"
    Write-Host "QuickBooks cache: $quickbooksDir"
    Write-Host ""

    foreach ($phase in @("1", "2", "3")) {
        $phaseLabel = switch ($phase) {
            "1" { "Phase 1 - do first (claims, dashboard depth, A/R)" }
            "2" { "Phase 2 - QuickBooks + documents" }
            "3" { "Phase 3 - optional practice widgets" }
        }
        $phaseRows = $checks | Where-Object { $_.Phase -eq $phase }
        if (-not $phaseRows.Count) { continue }
        Write-Host $phaseLabel -ForegroundColor Yellow
        foreach ($row in $phaseRows) {
            $mark = if ($row.Ok) { "[OK]" } else { "[MISSING]" }
            $color = if ($row.Ok) { "Green" } else { "Red" }
            Write-Host "  $mark $($row.Label)" -ForegroundColor $color
            Write-Host "       $($row.Detail)"
            if (-not $row.Ok) {
                Write-Host "       -> $($row.Action)" -ForegroundColor DarkYellow
            }
        }
        Write-Host ""
    }

    if ($phase1Missing.Count -eq 0 -and $requiredMissing.Count -eq 0) {
        Write-Host "All required HAL inputs are present." -ForegroundColor Green
    } else {
        Write-Host "Required gaps: $($requiredMissing.Count) - Phase 1 gaps: $($phase1Missing.Count)" -ForegroundColor $(if ($phase1Missing.Count) { "Red" } else { "Yellow" })
    }

    Write-Host ""
    Write-Host "After fixing gaps, tell HAL:" -ForegroundColor Cyan
    Write-Host '  1. "Pull SoftDent and QuickBooks data"'
    Write-Host '  2. "Show manager dashboard widgets"'
    Write-Host '  3. "What do you need to do your job"'
    Write-Host ""
}

if ($PullFull) {
    $fullPullPs = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "Pull-HAL-Full-Practice-Sources.ps1"
    if (-not (Test-Path $fullPullPs)) { throw "Full pull script not found: $fullPullPs" }
    & $fullPullPs -VerifyHal:(-not $Quiet)
    exit $LASTEXITCODE
}

if ($Pull) {
    if ($phase1Missing.Count -gt 0 -and -not $Quiet) {
        Write-Host "Pull will still run, but Phase 1 gaps remain - claims/trend widgets may stay FAILED." -ForegroundColor Yellow
    }
    $pullScript = Join-Path $projectRoot "sync_document_sources.py"
    $pullPs = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "Sync-HAL-Document-Sources.ps1"
    if (Test-Path $pullPs) {
        Write-Host "Running HAL document source sync..." -ForegroundColor Cyan
        & $pullPs
    } elseif (Test-Path $pullScript) {
        Push-Location $projectRoot
        python $pullScript
        Pop-Location
    } else {
        throw "Sync script not found: $pullPs"
    }
}

# Exit code: 0 = all phase 1+2 required (except staff review) OK; 1 = gaps remain
$blocking = @($required | Where-Object { -not $_.Ok })
if ($blocking.Count -gt 0) { exit 1 }
exit 0
