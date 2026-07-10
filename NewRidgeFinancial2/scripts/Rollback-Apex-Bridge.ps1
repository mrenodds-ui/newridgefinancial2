<#
.SYNOPSIS
  Rollback NR2-Apex Starship Bridge (hal-10230+) to pre-bridge shell (hal-10220).

.DESCRIPTION
  Restores site/index.html from index.pre-bridge-hal-10220.html (or app_data backup).
  Does NOT delete practice data. Does NOT kill Python processes.
  After rollback, restart NR2 and hard-refresh the browser.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File NewRidgeFinancial2\scripts\Rollback-Apex-Bridge.ps1
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

$ErrorActionPreference = "Stop"

$nr2 = Join-Path $RepoRoot "NewRidgeFinancial2"
$site = Join-Path $nr2 "site"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$safetyDir = Join-Path $nr2 "app_data\nr2-backup-P0\bridge-before-rollback-$stamp"

$candidates = @(
  (Join-Path $site "index.pre-bridge-hal-10220.html"),
  (Join-Path $nr2 "app_data\nr2-backup-P0\index.pre-bridge-hal-10220.html")
)
$backup = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $backup) {
  Write-Error "Pre-bridge index backup not found. Looked for:`n  $($candidates -join "`n  ")"
}

Write-Host "NR2-Apex Bridge Rollback"
Write-Host "  Backup : $backup"
Write-Host "  Target : $(Join-Path $site 'index.html')"
Write-Host "  Safety : $safetyDir"

if ($PSCmdlet.ShouldProcess($site, "Restore pre-bridge index.html")) {
  New-Item -ItemType Directory -Force -Path $safetyDir | Out-Null

  $preserve = @(
    "index.html",
    "apex-bridge.css",
    "apex-ticker.js",
    "apex-narratives.js",
    "apex-core.js",
    "apex-hal-bridge.js",
    "apex-animations.css",
    "apex-tokens.css",
    "nr2-build.json"
  )
  foreach ($name in $preserve) {
    $src = Join-Path $site $name
    if (Test-Path $src) {
      Copy-Item -Force $src (Join-Path $safetyDir $name)
    }
  }

  Copy-Item -Force $backup (Join-Path $site "index.html")
  Write-Host "Restored index.html from pre-bridge backup."
  Write-Host "Bridge CSS/JS files left in place (unused by restored shell)."
  Write-Host "Safety copy of current bridge assets: $safetyDir"
  Write-Host "Restart NR2 (StartProgram.bat) and hard-refresh the browser (Ctrl+F5)."
}
