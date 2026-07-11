# Stop website appointment webhook relay + Cloudflare quick tunnel.

$ErrorActionPreference = "Continue"
$LogDir = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) ".local_logs\website_webhook"
# scripts -> NewRidgeFinancial2 -> repo root
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$LogDir = Join-Path $RepoRoot ".local_logs\website_webhook"
$metaPath = Join-Path $LogDir "tunnel_meta.json"

if (Test-Path $metaPath) {
    try {
        $meta = Get-Content $metaPath -Raw | ConvertFrom-Json
        foreach ($id in @($meta.relayPid, $meta.tunnelPid)) {
            if ($id) { Stop-Process -Id ([int]$id) -Force -ErrorAction SilentlyContinue }
        }
    } catch {}
}

Get-NetTCPConnection -LocalPort 8777 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}
Get-Process cloudflared -ErrorAction SilentlyContinue | Where-Object {
    try {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
        $cmd -match "127\.0\.0\.1:8777"
    } catch { $false }
} | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "Website webhook tunnel stopped."
