[CmdletBinding()]
param(
    [string]$BindHost = '127.0.0.1',
    [int]$Port = 8080,
    [string]$DataDir = (Join-Path $env:LOCALAPPDATA 'OpenWebUI'),
    [int]$WaitSeconds = 45,
    [switch]$ForceRestart,
    [switch]$OpenBrowser
)

$ErrorActionPreference = 'Stop'

function Test-OpenWebUiReady {
    param(
        [string]$BaseUrl
    )

    try {
        $response = Invoke-WebRequest -Uri $BaseUrl -TimeoutSec 3
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    } catch {
        return $false
    }
}

function Get-OpenWebUiProcesses {
    Get-CimInstance Win32_Process |
        Where-Object {
            ($_.Name -match 'powershell|pwsh') -and
            $_.CommandLine -and
            (
                $_.CommandLine -match 'run_open_webui_single_user\.ps1' -or
                $_.CommandLine -match 'open-webui serve'
            )
        }
}

$baseUrl = "http://$BindHost`:$Port"
$resolvedDataDir = [System.IO.Path]::GetFullPath($DataDir)
$logDir = Join-Path $resolvedDataDir 'logs'
$stdoutLog = Join-Path $logDir 'open-webui.stdout.log'
$stderrLog = Join-Path $logDir 'open-webui.stderr.log'
$runnerPath = Join-Path $PSScriptRoot 'run_open_webui_single_user.ps1'

$null = New-Item -ItemType Directory -Path $resolvedDataDir -Force
$null = New-Item -ItemType Directory -Path $logDir -Force

if ($ForceRestart) {
    $existing = @(Get-OpenWebUiProcesses)
    foreach ($process in $existing) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 750
}

if (-not $ForceRestart -and (Test-OpenWebUiReady -BaseUrl $baseUrl)) {
    Write-Host "Open WebUI is already responding at $baseUrl"
    if ($OpenBrowser) {
        Start-Process $baseUrl | Out-Null
    }
    return
}

if (Test-Path $stdoutLog) {
    Remove-Item $stdoutLog -Force -ErrorAction SilentlyContinue
}
if (Test-Path $stderrLog) {
    Remove-Item $stderrLog -Force -ErrorAction SilentlyContinue
}

$arguments = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', $runnerPath,
    '-BindHost', $BindHost,
    '-Port', $Port,
    '-DataDir', $resolvedDataDir
)

$startProcessArgs = @{
    FilePath = 'powershell.exe'
    ArgumentList = $arguments
    WindowStyle = 'Hidden'
    RedirectStandardOutput = $stdoutLog
    RedirectStandardError = $stderrLog
}

Start-Process @startProcessArgs | Out-Null

$deadline = (Get-Date).AddSeconds($WaitSeconds)
while ((Get-Date) -lt $deadline) {
    if (Test-OpenWebUiReady -BaseUrl $baseUrl) {
        Write-Host "Open WebUI is responding at $baseUrl"
        Write-Host "Logs: $stdoutLog"
        if ($OpenBrowser) {
            Start-Process $baseUrl | Out-Null
        }
        return
    }
    Start-Sleep -Seconds 1
}

$stderrTail = ''
if (Test-Path $stderrLog) {
    $stderrTail = (Get-Content $stderrLog -Tail 40 -ErrorAction SilentlyContinue) -join [Environment]::NewLine
}

throw "Open WebUI did not become ready within $WaitSeconds seconds at $baseUrl. See $stderrLog. Last error output: $stderrTail"