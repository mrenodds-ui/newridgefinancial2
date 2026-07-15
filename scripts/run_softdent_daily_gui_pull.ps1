# SoftDent daily GUI master pull (interactive 5 PM).
# Opens SoftDent UI, exports Phase-1 reports into SoftDentReportExports, then refresh.
# Requires: user logged on (interactive desktop). Do NOT use Session-0 / S4U-only.
$ErrorActionPreference = 'Stop'

$RepoRoot = if ($env:NEWRIDGE_FINANCIAL_REPO) {
    $env:NEWRIDGE_FINANCIAL_REPO
} elseif (Test-Path -LiteralPath 'C:\Users\mreno\newridgefamilyfinancial') {
    'C:\Users\mreno\newridgefamilyfinancial'
} else {
    'C:\NewRidgeFamilyFinancial'
}
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $Python)) {
    $Python = 'python.exe'
}
$Master = Join-Path $RepoRoot 'scripts\run_softdent_daily_master_pull.py'
if (!(Test-Path -LiteralPath $Master)) {
    throw "Missing master pull script: $Master"
}

$LogDir = 'C:\SoftDentFinancialExports\dashboard_logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$LogFile = Join-Path $LogDir "softdent_daily_gui_pull_console_$Stamp.log"

$Today = Get-Date
$Start = Get-Date -Year $Today.Year -Month $Today.Month -Day 1
$StartIso = $Start.ToString('yyyy-MM-dd')
$EndIso = $Today.ToString('yyyy-MM-dd')

$argsList = @(
    $Master,
    '--start', $StartIso,
    '--end', $EndIso
)

Write-Host "SoftDent daily GUI pull starting $StartIso .. $EndIso"
& $Python @argsList *>&1 | Tee-Object -FilePath $LogFile
$code = $LASTEXITCODE
Write-Host "SoftDent daily GUI pull exit=$code log=$LogFile"
exit $code
