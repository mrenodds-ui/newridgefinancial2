<#
.SYNOPSIS
  Rollback NR2-Apex P0 wipe — restore site/ from pre-Apex backup.

.DESCRIPTION
  Restores NewRidgeFinancial2/site from app_data/nr2-backup-P0/site-pre-apex.
  Does NOT delete practice data under app_data (other than overwriting site/).
  Does NOT kill Python/Chrome processes.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File NewRidgeFinancial2\scripts\Rollback-Apex-P0.ps1
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

$ErrorActionPreference = "Stop"

$nr2 = Join-Path $RepoRoot "NewRidgeFinancial2"
$backup = Join-Path $nr2 "app_data\nr2-backup-P0\site-pre-apex"
$site = Join-Path $nr2 "site"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$safety = Join-Path $nr2 "app_data\nr2-backup-P0\site-apex-before-rollback-$stamp"

if (-not (Test-Path $backup)) {
  Write-Error "Backup not found: $backup`nCannot rollback without nr2-backup-P0/site-pre-apex."
}

Write-Host "NR2-Apex P0 Rollback"
Write-Host "  Backup : $backup"
Write-Host "  Target : $site"
Write-Host "  Safety : $safety"

if ($PSCmdlet.ShouldProcess($site, "Restore from site-pre-apex")) {
  New-Item -ItemType Directory -Force -Path (Split-Path $safety) | Out-Null
  if (Test-Path $site) {
    Write-Host "Saving current site to safety copy..."
    robocopy $site $safety /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
  }

  Write-Host "Restoring pre-Apex site..."
  if (Test-Path $site) {
    # Remove Apex-only files that may not exist in backup, then mirror restore
    Get-ChildItem $site -Force | ForEach-Object {
      Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
  } else {
    New-Item -ItemType Directory -Force -Path $site | Out-Null
  }

  $rc = 0
  robocopy $backup $site /E /NFL /NDL /NJH /NJS /nc /ns /np
  $rc = $LASTEXITCODE
  if ($rc -ge 8) {
    Write-Error "robocopy failed with exit code $rc"
  }

  Write-Host "Rollback complete. Restart NR2 (StartProgram.bat) and hard-refresh the browser."
  Write-Host "Pre-rollback Apex tree kept at: $safety"
}
