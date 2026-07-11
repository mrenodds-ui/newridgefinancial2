# Start website appointment webhook relay + Cloudflare quick tunnel.
# Exposes ONLY the webhook port (8777), not full NR2 (8765).

param(
    [int]$Port = 8777,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$Nr2 = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Nr2 "website_webhook_relay.py"))) {
    throw "website_webhook_relay.py not found under $Nr2"
}
$RepoRoot = Split-Path -Parent $Nr2
$DataDir = Join-Path $RepoRoot "app_data\nr2"
$LogDir = Join-Path $RepoRoot ".local_logs\website_webhook"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

$secretFile = Join-Path $DataDir "website_webhook_secret.txt"
if (-not (Test-Path $secretFile)) {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $secret = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
    Set-Content -Path $secretFile -Value $secret -Encoding utf8NoBOM
} else {
    $secret = (Get-Content -Path $secretFile -Raw).Trim()
}
$env:NR2_WEBSITE_WEBHOOK_SECRET = $secret
$env:NR2_WEBSITE_WEBHOOK_PORT = "$Port"
$env:NR2_DATA_DIR = $DataDir

function Find-Python314 {
    $candidates = @(
        "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe",
        (Get-Command py -ErrorAction SilentlyContinue | ForEach-Object { $_.Source })
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c) -and ($c -like "*python.exe")) {
            return $c
        }
    }
    $viaPy = & py -3.14 -c "import sys; print(sys.executable)" 2>$null
    if ($viaPy -and (Test-Path $viaPy.Trim())) { return $viaPy.Trim() }
    throw "Python 3.14 with sqlcipher3/keyring required (NR2 encrypted DB)."
}

function Find-Cloudflared {
    $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($p in @(
        "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe",
        "$env:ProgramFiles\cloudflared\cloudflared.exe",
        "$env:LOCALAPPDATA\Microsoft\WinGet\Links\cloudflared.exe",
        "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Cloudflare.cloudflared_Microsoft.Winget.Source_*\cloudflared.exe"
    )) {
        $hit = Get-Item $p -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    $winget = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Filter "cloudflared.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($winget) { return $winget.FullName }
    throw "cloudflared not found. Install with: winget install Cloudflare.cloudflared"
}

$cloudflared = Find-Cloudflared
$python = Find-Python314
# Verify sqlcipher available in this interpreter
& $python -c "import sqlcipher3,keyring" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Selected Python lacks sqlcipher3/keyring: $python"
}

# Stop prior relay on this port if ours
Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
}

$relayLog = Join-Path $LogDir "relay.log"
$tunnelLog = Join-Path $LogDir "tunnel.log"
$urlFile = Join-Path $LogDir "public_url.txt"

Write-Host "Starting webhook relay on 127.0.0.1:$Port ..."
$relay = Start-Process -FilePath $python -ArgumentList @((Join-Path $Nr2 "website_webhook_relay.py")) `
    -WorkingDirectory $Nr2 -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $relayLog -RedirectStandardError (Join-Path $LogDir "relay.err.log")

Start-Sleep -Seconds 1
if ($relay.HasExited) {
    throw "Relay exited early. See $relayLog / relay.err.log"
}

Write-Host "Starting Cloudflare quick tunnel -> http://127.0.0.1:$Port ..."
if (Test-Path $tunnelLog) { Remove-Item $tunnelLog -Force }
$tunnel = Start-Process -FilePath $cloudflared -ArgumentList @("tunnel","--url","http://127.0.0.1:$Port","--no-autoupdate") `
    -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $tunnelLog -RedirectStandardError (Join-Path $LogDir "tunnel.err.log")

$publicUrl = $null
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    foreach ($logPath in @($tunnelLog, (Join-Path $LogDir "tunnel.err.log"))) {
        if (-not (Test-Path $logPath)) { continue }
        $txt = Get-Content -Path $logPath -Raw -ErrorAction SilentlyContinue
        if ($txt -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
            $publicUrl = $Matches[0]
            break
        }
    }
    if ($publicUrl) { break }
}

if (-not $publicUrl) {
    Write-Warning "Tunnel started but URL not parsed yet. Check $tunnelLog"
} else {
    $webhookUrl = "$publicUrl/api/webhooks/website-appointment"
    Set-Content -Path $urlFile -Value $webhookUrl -Encoding utf8NoBOM
    $meta = @{
        publicBase = $publicUrl
        webhookUrl = $webhookUrl
        secretHeader = "X-NR2-Webhook-Secret"
        secretFile = $secretFile
        relayPid = $relay.Id
        tunnelPid = $tunnel.Id
        port = $Port
        startedAt = (Get-Date).ToString("o")
    } | ConvertTo-Json
    Set-Content -Path (Join-Path $LogDir "tunnel_meta.json") -Value $meta -Encoding utf8NoBOM

    Write-Host ""
    Write-Host "=== LIVE WEBSITE APPOINTMENT WEBHOOK ===" -ForegroundColor Green
    Write-Host "URL:    $webhookUrl"
    Write-Host "Header: X-NR2-Webhook-Secret: (see $secretFile)"
    Write-Host "Relay PID $($relay.Id) | Tunnel PID $($tunnel.Id)"
    Write-Host "Meta:   $(Join-Path $LogDir 'tunnel_meta.json')"
    Write-Host ""
}

# Keep script attached so operator can Ctrl+C to stop both
try {
    while ($true) {
        if ($relay.HasExited -or $tunnel.HasExited) {
            Write-Warning "Relay or tunnel exited (relay=$($relay.HasExited) tunnel=$($tunnel.HasExited))"
            break
        }
        Start-Sleep -Seconds 5
    }
} finally {
    foreach ($p in @($tunnel, $relay)) {
        if ($p -and -not $p.HasExited) {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
