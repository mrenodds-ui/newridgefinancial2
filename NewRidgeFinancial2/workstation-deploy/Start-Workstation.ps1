<#
.SYNOPSIS
  Launch NR2 Office Workstation from the installed package folder.

.DESCRIPTION
  Default (desktop shortcut): show messenger window, or raise an already-running instance.
  -Hidden: background start for Startup folder (popups only, no main window).
#>
[CmdletBinding()]
param(
    [switch]$Hidden,
    [switch]$SkipModelWarmup
)

$ErrorActionPreference = 'Stop'
$PkgRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Join-Path $PkgRoot 'NewRidgeFinancial2'
$SiteDir = Join-Path $AppDir 'site'
$WorkstationScript = Join-Path $AppDir 'workstation_app.py'
$DefaultPort = 8766

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

Import-DotEnvFile (Join-Path $PkgRoot '.env')

if (-not $env:NR2_WORKSTATION_FAST_HAL) { $env:NR2_WORKSTATION_FAST_HAL = '1' }
$env:NR2_WORKSTATION_PORT = [string]$DefaultPort
$nr2Port = [int]$env:NR2_WORKSTATION_PORT

function Resolve-PackagedPython {
    $bundled = @(
        (Join-Path $PkgRoot 'python\Scripts\pythonw.exe'),
        (Join-Path $PkgRoot 'python\Scripts\python.exe')
    )
    foreach ($c in $bundled) {
        if (Test-Path $c) { return $c }
    }
    foreach ($cmd in @('pythonw', 'python')) {
        $hit = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($hit) { return $hit.Source }
    }
    throw "Python not found. Re-run Install.bat on this package folder."
}

function Test-WorkstationListening {
    param([int]$Port)
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/workstation/index.html" -UseBasicParsing -TimeoutSec 4
        return $true
    } catch {
        return $false
    }
}

function Show-RunningWorkstation {
    param([int]$Port)
    try {
        $result = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/workstation/show" -Method Post -TimeoutSec 8
        if ($result -and $result.ok -ne $false) {
            Write-Host 'NR2 Workstation window opened.' -ForegroundColor Green
            return $true
        }
    } catch {}
    return $false
}

function Stop-PortListener {
    param([int]$Port)
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "Stopping listener on port $Port (PID $($_.OwningProcess))..." -ForegroundColor Yellow
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path (Join-Path $SiteDir 'workstation\index.html'))) {
    throw "Workstation UI missing: $(Join-Path $SiteDir 'workstation\index.html')"
}

if (-not $Hidden) {
    if (Test-WorkstationListening -Port $nr2Port) {
        if (Show-RunningWorkstation -Port $nr2Port) { return }
    }
    $env:NR2_WORKSTATION_START_HIDDEN = '0'
} else {
    $env:NR2_WORKSTATION_START_HIDDEN = '1'
}

$manifestPath = Join-Path $AppDir 'nr2-build.json'
$schemaVersion = 'unknown'
if (Test-Path $manifestPath) {
    try {
        $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
        if ($manifest.schemaVersion) { $schemaVersion = [string]$manifest.schemaVersion }
    } catch {}
}

$python = Resolve-PackagedPython
$logDir = Join-Path $PkgRoot 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stdoutLog = Join-Path $logDir 'nr2-workstation.out.log'
$stderrLog = Join-Path $logDir 'nr2-workstation.err.log'
$dataDir = Join-Path $PkgRoot 'app_data\nr2'
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
$pidFile = Join-Path $dataDir 'nr2-workstation.pid'

function Stop-ExistingWorkstation {
    param([string]$PidPath)
    if (-not (Test-Path $PidPath)) { return }
    try {
        $existingPid = [int](Get-Content $PidPath -Raw)
        if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
            Write-Host "Stopping previous NR2 Workstation (PID $existingPid)..." -ForegroundColor Yellow
            Stop-Process -Id $existingPid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
        }
    } catch {}
    Remove-Item $PidPath -Force -ErrorAction SilentlyContinue
}

Stop-ExistingWorkstation -PidPath $pidFile
Stop-PortListener -Port $nr2Port

$windowStyle = 'Hidden'
if ($python -match 'python\.exe$') { $windowStyle = 'Normal' }

$process = Start-Process -FilePath $python -ArgumentList @($WorkstationScript) -WorkingDirectory $AppDir -WindowStyle $windowStyle -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru
Set-Content -Path $pidFile -Value $process.Id
if ($Hidden) {
    Write-Host "NR2 Workstation started in background (schema $schemaVersion, port $nr2Port, PID $($process.Id))." -ForegroundColor Green
} else {
    Write-Host "NR2 Workstation messenger opened (schema $schemaVersion, port $nr2Port, PID $($process.Id))." -ForegroundColor Green
}
