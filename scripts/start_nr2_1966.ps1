<#
.SYNOPSIS
  Launch NewRidgeFinancial 2.0 as a single-window desktop program.
#>
[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$Restart
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$AppDir = Join-Path $Root 'NewRidgeFinancial2'
$SiteDir = Join-Path $AppDir 'site'
$DesktopScript = Join-Path $AppDir 'desktop_app.py'

function Resolve-Python {
    $candidates = @(
        (Join-Path $Root '.venv\Scripts\python.exe'),
        (Join-Path $Root '.venv-py313\Scripts\python.exe')
    )
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
    return 'python'
}

if (-not (Test-Path (Join-Path $SiteDir 'index.html'))) {
    throw "NewRidgeFinancial 2.0 site not found at $SiteDir"
}

Write-Host 'NewRidgeFinancial 2.0 Desktop' -ForegroundColor Green

$python = Resolve-Python
if (-not (Get-Command $python -ErrorAction SilentlyContinue)) {
    throw "Python is required to run NewRidgeFinancial 2.0 desktop app."
}

$logDir = Join-Path $Root '.tmp'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stdoutLog = Join-Path $logDir 'nr2-desktop.out.log'
$stderrLog = Join-Path $logDir 'nr2-desktop.err.log'
$dataDir = Join-Path $Root 'app_data\nr2'
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
$pidFile = Join-Path $dataDir 'nr2-desktop.pid'

$process = Start-Process -FilePath $python -ArgumentList @($DesktopScript) -WorkingDirectory $AppDir -WindowStyle Normal -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru
Set-Content -Path $pidFile -Value $process.Id
Write-Host 'Desktop app launched (single window, no browser, no localhost server).' -ForegroundColor Green
