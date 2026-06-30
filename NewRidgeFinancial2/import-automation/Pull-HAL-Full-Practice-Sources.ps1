[CmdletBinding()]
param(
    [switch]$VerifyHal,
    [switch]$ScanResources,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$repoRoot = Split-Path -Parent $projectRoot
$verifyScript = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "Verify-HAL-Readiness.ps1"

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

$env:NR2_HAL_FULL_PULL = "1"
$env:NR2_HAL_PRACTICE_PULL_APPROVED = "1"
if ($ScanResources) { $env:NR2_HAL_PULL_SCAN_RESOURCES = "1" }

if (-not $Quiet) {
    Write-Host ""
    Write-Host "HAL FULL practice source pull (100% SoftDent + QuickBooks)" -ForegroundColor Cyan
    Write-Host "Repo: $repoRoot"
    Write-Host ""
}

Push-Location $projectRoot
try {
    $scanFlag = if ($ScanResources) { "True" } else { "False" }
    $pullJson = python -c "from practice_source_access import pull_all_practice_sources; import json; print(json.dumps(pull_all_practice_sources(full=True, scan_resources=$scanFlag)))"
    $pull = $pullJson | ConvertFrom-Json
} finally {
    Pop-Location
}

if (-not $Quiet) {
    Write-Host "Pull OK: $($pull.ok)" -ForegroundColor $(if ($pull.ok) { "Green" } else { "Red" })
    Write-Host "SoftDent resources: $($pull.summary.softdentResourcesOk)"
    Write-Host "QuickBooks resources: $($pull.summary.quickbooksResourcesOk)"
    Write-Host "Claims verified: $($pull.summary.claimsOk) ($($pull.summary.claimsRowCount) rows)"
    Write-Host "Narrative templates: $($pull.summary.narrativeTemplates)"
    Write-Host "Document queue: $($pull.summary.documentQueueCount)"
    if ($pull.claimsVerification -and $pull.claimsVerification.claimIds) {
        Write-Host "Claim IDs: $($pull.claimsVerification.claimIds -join ', ')"
    }
    if ($pull.narrativeLibrary -and $pull.narrativeLibrary.selections) {
        Write-Host ""
        Write-Host "Best narrative per claim:" -ForegroundColor Yellow
        foreach ($sel in $pull.narrativeLibrary.selections) {
            $pick = $sel.selected
            Write-Host "  $($sel.claimRef) -> $($pick.id) ($($pick.focus), score $($sel.score))"
        }
    }
    Write-Host ""
}

if ($VerifyHal) {
    if (-not $Quiet) { Write-Host "Running HAL visibility check..." -ForegroundColor Cyan }
    Push-Location $projectRoot
    node ask-hal-documents-check.mjs | Out-Null
    Pop-Location
    if (Test-Path (Join-Path $projectRoot "hal-check-out.json")) {
        $halOut = Get-Content (Join-Path $projectRoot "hal-check-out.json") -Raw | ConvertFrom-Json
        if (-not $Quiet) {
            Write-Host "HAL claims widget posture:" -ForegroundColor Cyan
            ($halOut.responses | Where-Object { $_.command -match "widget|job requirements" }) | ForEach-Object {
                Write-Host $_.text.Substring(0, [Math]::Min(400, $_.text.Length))
                Write-Host "..."
            }
        }
    }
}

if (-not $pull.summary.claimsOk) { exit 1 }
exit 0
