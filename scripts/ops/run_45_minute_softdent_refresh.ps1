# NR2 SoftDent ~45-minute refresh (replaces missing C:\New folder\ops script).
# Copies/transforms export files only — never writes SoftDent.
$ErrorActionPreference = 'Continue'

$RepoRoot = if ($env:NEWRIDGE_FINANCIAL_REPO) {
    $env:NEWRIDGE_FINANCIAL_REPO
} elseif (Test-Path 'C:\Users\mreno\newridgefamilyfinancial') {
    'C:\Users\mreno\newridgefamilyfinancial'
} else {
    'C:\NewRidgeFamilyFinancial'
}

$Sync = Join-Path $RepoRoot 'NewRidgeFinancial2\import-automation\Sync-HAL-Imports.ps1'
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $Python)) { $Python = 'python.exe' }

$StateDir = 'C:\SoftDentFinancialExports'
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
$StatePath = Join-Path $StateDir 'softdent_45min_refresh_state.json'
$LogDir = Join-Path $StateDir 'dashboard_logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$LogFile = Join-Path $LogDir "softdent_45min_refresh_$Stamp.log"

$started = (Get-Date).ToUniversalTime().ToString('o')
$errors = New-Object System.Collections.Generic.List[string]
$ok = $true

Write-Host "SoftDent 45-min refresh starting repo=$RepoRoot"
if (!(Test-Path -LiteralPath $Sync)) {
    $ok = $false
    $errors.Add("Missing $Sync")
} else {
    # Import sync stderr warnings (e.g. missing optional nr2_contracts) must not abort.
    $syncOut = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Sync 2>&1
    $syncOut | Tee-Object -FilePath $LogFile -Append | Out-Null
    $syncCode = $LASTEXITCODE
    if ($syncCode -ne 0) {
        $ok = $false
        $errors.Add("Sync-HAL-Imports exit $syncCode")
        $errors.Add((($syncOut | Out-String).Trim().Substring(0, [Math]::Min(500, (($syncOut | Out-String).Trim().Length)))))
    }
}

# Best-effort period import refresh (optional; failure is soft unless import sync failed).
$periodPy = @"
import json, sys
from pathlib import Path
repo = Path(r'''$RepoRoot''')
sys.path.insert(0, str(repo / 'NewRidgeFinancial2'))
try:
    from apex_backend import refresh_softdent_period_imports
    r = refresh_softdent_period_imports()
    print(json.dumps({'ok': bool(r.get('ok')), 'keys': sorted(list(r.keys()))[:20]}, default=str))
except Exception as exc:
    print(json.dumps({'ok': False, 'soft': True, 'error': type(exc).__name__ + ':' + str(exc)[:400]}))
"@
$periodOut = & $Python -c $periodPy 2>&1
$periodOut | Tee-Object -FilePath $LogFile -Append | Out-Null
# Do not fail the task solely for soft period-refresh / missing optional packs.

$finished = (Get-Date).ToUniversalTime().ToString('o')
$payload = [ordered]@{
    startedAt = $started
    finishedAt = $finished
    success = $ok
    status = if ($ok) { 'success' } else { 'failed' }
    projectRoot = $RepoRoot
    refreshScript = $Sync
    logPath = $LogFile
    latestLogPath = (Join-Path $LogDir 'softdent_45min_refresh.log')
    errors = @($errors)
    runner = 'scripts/ops/run_45_minute_softdent_refresh.ps1'
}
$payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $StatePath -Encoding UTF8
Copy-Item -LiteralPath $LogFile -Destination (Join-Path $LogDir 'softdent_45min_refresh.log') -Force
Write-Host "SoftDent 45-min refresh success=$ok log=$LogFile"
if ($ok) { exit 0 } else { exit 1 }
