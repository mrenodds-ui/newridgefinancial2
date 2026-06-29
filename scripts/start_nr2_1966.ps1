<#
.SYNOPSIS
  Launch NewRidgeFinancial 2.0 as a single-window desktop program.
#>
[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$Restart,
    [switch]$SkipModelWarmup
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$AppDir = Join-Path $Root 'NewRidgeFinancial2'
$SiteDir = Join-Path $AppDir 'site'
$DesktopScript = Join-Path $AppDir 'desktop_app.py'
$ModelWarmupScript = Join-Path $AppDir 'model-automation\Keep-HAL-Models-Warm.ps1'

function Import-DotEnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith('#')) { return }
        $idx = $line.IndexOf('=')
        if ($idx -lt 1) { return }
        $name = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim()
        if ($name) { Set-Item -Path "Env:$name" -Value $value }
    }
}

Import-DotEnvFile (Join-Path $Root '.env')
Import-DotEnvFile (Join-Path $AppDir '.env')

function Resolve-Python {
    # Prefer pythonw.exe (no console window) so closing a console cannot kill the
    # desktop window. Fall back to python.exe only if pythonw is unavailable.
    $candidates = @(
        (Join-Path $Root '.venv\Scripts\pythonw.exe'),
        (Join-Path $Root '.venv-py313\Scripts\pythonw.exe'),
        (Join-Path $Root '.venv\Scripts\python.exe'),
        (Join-Path $Root '.venv-py313\Scripts\python.exe')
    )
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
    $pythonw = Get-Command 'pythonw' -ErrorAction SilentlyContinue
    if ($pythonw) { return $pythonw.Source }
    return 'python'
}

function Start-ModelWarmup {
    param(
        [string]$ScriptPath,
        [string]$StdoutPath,
        [string]$StderrPath
    )

    if ($SkipModelWarmup) {
        Write-Host 'HAL model warmup skipped by -SkipModelWarmup.' -ForegroundColor Yellow
        return
    }
    if (-not (Test-Path $ScriptPath)) {
        Write-Host "HAL model warmup script not found: $ScriptPath" -ForegroundColor Yellow
        return
    }

    try {
        Start-Process `
            -FilePath 'powershell.exe' `
            -ArgumentList @('-NoProfile', '-WindowStyle', 'Hidden', '-ExecutionPolicy', 'Bypass', '-File', $ScriptPath) `
            -WindowStyle Hidden `
            -RedirectStandardOutput $StdoutPath `
            -RedirectStandardError $StderrPath | Out-Null
        Write-Host 'HAL model warmup started (loads the active model into GPU via Ollama).' -ForegroundColor Green
    } catch {
        Write-Host "HAL model warmup could not be started: $($_.Exception.Message)" -ForegroundColor Yellow
    }
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
$warmupStdoutLog = Join-Path $logDir 'nr2-model-warmup.out.log'
$warmupStderrLog = Join-Path $logDir 'nr2-model-warmup.err.log'
$dataDir = Join-Path $Root 'app_data\nr2'
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
$pidFile = Join-Path $dataDir 'nr2-desktop.pid'

Start-ModelWarmup -ScriptPath $ModelWarmupScript -StdoutPath $warmupStdoutLog -StderrPath $warmupStderrLog

$process = Start-Process -FilePath $python -ArgumentList @($DesktopScript) -WorkingDirectory $AppDir -WindowStyle Normal -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru
Set-Content -Path $pidFile -Value $process.Id
Write-Host 'Desktop app launched (single pywebview window — no HTTP server).' -ForegroundColor Green
