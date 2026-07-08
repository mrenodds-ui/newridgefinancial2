<#
.SYNOPSIS
  Launch NewRidgeFinancial 2.0 browser program on loopback port 8765 and open the default browser.
#>
[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$Restart,
    [switch]$SkipModelWarmup,
    [switch]$SkipValidation
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$AppDir = Join-Path $Root 'NewRidgeFinancial2'
$SiteDir = Join-Path $AppDir 'site'
$BrowserScript = Join-Path $AppDir 'browser_app.py'
$ModelWarmupScript = Join-Path $AppDir 'model-automation\Keep-HAL-Models-Warm.ps1'
$DefaultPort = 8765

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

if (-not $env:NR2_HTTP_PORT) {
    $env:NR2_HTTP_PORT = [string]$DefaultPort
}
$nr2Port = [int]$env:NR2_HTTP_PORT

function Resolve-Python {
    $candidates = @(
        (Join-Path $Root '.venv\Scripts\python.exe'),
        (Join-Path $Root '.venv-py313\Scripts\python.exe'),
        (Join-Path $Root '.venv\Scripts\pythonw.exe'),
        (Join-Path $Root '.venv-py313\Scripts\pythonw.exe')
    )
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
    $python = Get-Command 'python' -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    return 'python'
}

function Stop-PortListener {
    param([int]$Port)
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "Stopping listener on port $Port (PID $($_.OwningProcess))..." -ForegroundColor Yellow
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
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

function Get-Nr2BaseUrl {
    param([int]$Port)
    $allowHttp = $env:NR2_ALLOW_HTTP -match '^(1|true|yes)$'
    $enforceTls = -not $allowHttp -and ($env:NR2_ENFORCE_TLS -ne '0')
    if (-not $env:NR2_ENFORCE_TLS) { $enforceTls = $true }
    $scheme = if ($enforceTls) { 'https' } else { 'http' }
    return "${scheme}://127.0.0.1:$Port/"
}

function Enable-LocalhostTlsBypass {
    if (-not ([System.Management.Automation.PSTypeName]'TrustAllCertsPolicy').Type) {
        Add-Type @"
using System.Net;
using System.Net.Security;
using System.Security.Cryptography.X509Certificates;
public class TrustAllCertsPolicy {
    public static bool Validator(object sender, X509Certificate certificate, X509Chain chain, SslPolicyErrors errors) { return true; }
}
"@
    }
    [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { param($s,$c,$ch,$e) return $true }
}

function Wait-ForServer {
    param([int]$Port, [int]$TimeoutSec = 120)
    $url = Get-Nr2BaseUrl -Port $Port
    if ($url.StartsWith('https')) { Enable-LocalhostTlsBypass }
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if (-not $listening) {
            Start-Sleep -Milliseconds 500
            continue
        }
        try {
            if (Get-Command Invoke-WebRequest | Select-Object -ExpandProperty Parameters | Where-Object { $_.Keys -contains 'SkipCertificateCheck' }) {
                $null = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5 -SkipCertificateCheck
            } else {
                $null = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
            }
            return $true
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    return $false
}

if (-not (Test-Path (Join-Path $SiteDir 'index.html'))) {
    throw "NewRidgeFinancial 2.0 site not found at $SiteDir"
}

Write-Host 'Start Program - NewRidgeFinancial 2.0 (browser app)' -ForegroundColor Green
$basePreview = Get-Nr2BaseUrl -Port $nr2Port
Write-Host "Server: $basePreview - financial pages + HAL in your browser." -ForegroundColor Cyan

if (-not $SkipValidation) {
    $validatorScript = Join-Path $Root 'scripts\Invoke-NR2Validators.ps1'
    if (Test-Path $validatorScript) {
        & $validatorScript -Nr2Dir $AppDir
    }
} else {
    Write-Host 'Skipping NR2 validators (-SkipValidation).' -ForegroundColor Yellow
}

$manifestPath = Join-Path $AppDir 'nr2-build.json'
$schemaVersion = 'unknown'
if (Test-Path $manifestPath) {
    try {
        $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
        if ($manifest.schemaVersion) { $schemaVersion = [string]$manifest.schemaVersion }
    } catch {}
}

$python = Resolve-Python
if (-not (Get-Command $python -ErrorAction SilentlyContinue)) {
    throw 'Python is required to run NewRidgeFinancial 2.0.'
}

$logDir = Join-Path $Root '.tmp'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stdoutLog = Join-Path $logDir 'nr2-browser.out.log'
$stderrLog = Join-Path $logDir 'nr2-browser.err.log'
$warmupStdoutLog = Join-Path $logDir 'nr2-model-warmup.out.log'
$warmupStderrLog = Join-Path $logDir 'nr2-model-warmup.err.log'
$dataDir = Join-Path $Root 'app_data\nr2'
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
$pidFile = Join-Path $dataDir 'nr2-browser.pid'

function Stop-AllBrowserAppProcesses {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match 'browser_app\.py' } |
        ForEach-Object {
            Write-Host "Stopping NR2 browser_app.py (PID $($_.ProcessId))..." -ForegroundColor Yellow
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
}

function Stop-ExistingNR2 {
    param([string]$PidPath)
    if (-not (Test-Path $PidPath)) { return }
    try {
        $existingPid = [int](Get-Content $PidPath -Raw)
        if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
            Write-Host "Stopping previous NR2 browser server (PID $existingPid)..." -ForegroundColor Yellow
            Stop-Process -Id $existingPid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
        }
    } catch {
        Write-Host "Could not stop previous server: $($_.Exception.Message)" -ForegroundColor Yellow
    }
    Remove-Item $PidPath -Force -ErrorAction SilentlyContinue
}

function Ensure-TlsKeyPair {
    param([string]$Python, [string]$AppDirPath)
    $tlsDir = Join-Path $Root 'app_data\nr2\tls'
    $keyPath = Join-Path $tlsDir '127.0.0.1-key.pem'
    $pfxPath = Join-Path $tlsDir '127.0.0.1.pfx'
    if ((Test-Path $keyPath) -or -not (Test-Path $pfxPath)) { return }
    $exportScript = Join-Path $AppDirPath 'scripts\export_pfx_to_pem.py'
    if (-not (Test-Path $exportScript)) {
        Write-Host 'TLS private key missing and export script not found.' -ForegroundColor Yellow
        return
    }
    Write-Host 'Exporting TLS key from PFX...' -ForegroundColor Yellow
    & $Python $exportScript
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to export TLS key PEM from PFX.'
    }
}

function Ensure-TlsTrusted {
    $trustScript = Join-Path $Root 'scripts\trust_localhost_tls.ps1'
    if (Test-Path $trustScript) {
        & $trustScript
    }
}

Stop-AllBrowserAppProcesses
Stop-ExistingNR2 -PidPath $pidFile
Stop-PortListener -Port $nr2Port

Ensure-TlsKeyPair -Python $python -AppDirPath $AppDir
Ensure-TlsTrusted

Start-ModelWarmup -ScriptPath $ModelWarmupScript -StdoutPath $warmupStdoutLog -StderrPath $warmupStderrLog

$process = Start-Process -FilePath $python -ArgumentList @($BrowserScript) -WorkingDirectory $AppDir -WindowStyle Hidden -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru
Set-Content -Path $pidFile -Value $process.Id
Write-Host "NR2 server started (schema $schemaVersion, PID $($process.Id))." -ForegroundColor Green

if (-not $NoBrowser) {
    $openUrl = Get-Nr2BaseUrl -Port $nr2Port
    if (Wait-ForServer -Port $nr2Port) {
        Start-Process $openUrl
        Write-Host "Opened $openUrl in your default browser." -ForegroundColor Green
    } else {
        Write-Host "Server did not respond in time - open $openUrl manually." -ForegroundColor Yellow
    }
} else {
    $openUrl = Get-Nr2BaseUrl -Port $nr2Port
    Write-Host "Browser launch skipped (-NoBrowser). Open $openUrl when ready." -ForegroundColor DarkGray
}
