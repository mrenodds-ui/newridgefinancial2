# NR2 QuickBooks SDK / monthly export refresh (replaces missing C:\New folder\ops script).
# Read-only: never posts to QuickBooks.
$ErrorActionPreference = 'Continue'

$RepoRoot = if ($env:NEWRIDGE_FINANCIAL_REPO) {
    $env:NEWRIDGE_FINANCIAL_REPO
} elseif (Test-Path 'C:\Users\mreno\newridgefamilyfinancial') {
    'C:\Users\mreno\newridgefamilyfinancial'
} else {
    'C:\NewRidgeFamilyFinancial'
}

$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $Python)) {
    $Python = 'python.exe'
}

$StateDir = 'C:\SoftDentFinancialExports'
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
$StatePath = Join-Path $StateDir 'quickbooks_sdk_refresh_state.json'
$LogDir = Join-Path $StateDir 'dashboard_logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$LogFile = Join-Path $LogDir "qb_sdk_refresh_$Stamp.log"

$started = (Get-Date).ToUniversalTime().ToString('o')
$Runner = Join-Path $RepoRoot 'scripts\ops\run_quickbooks_sdk_refresh.py'
Write-Host "QB SDK refresh starting repo=$RepoRoot"
$jsonOut = & $Python $Runner 2>&1 | Tee-Object -FilePath $LogFile
$code = $LASTEXITCODE
$finished = (Get-Date).ToUniversalTime().ToString('o')
$tail = (($jsonOut | Out-String).Trim())
if ($tail.Length -gt 4000) { $tail = $tail.Substring(0, 4000) }

$payload = [ordered]@{
    startedAt = $started
    finishedAt = $finished
    status = if ($code -eq 0) { 'success' } else { 'failed' }
    exitCode = $code
    repoRoot = $RepoRoot
    logPath = $LogFile
    runner = 'scripts/ops/run_quickbooks_sdk_refresh.ps1'
    outputTail = $tail
}
$payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $StatePath -Encoding UTF8
Write-Host "QB SDK refresh exit=$code log=$LogFile"
exit $code
