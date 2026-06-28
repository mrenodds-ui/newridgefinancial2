<#
.SYNOPSIS
  Retired launcher for the legacy New Ridge Family Financial program.

.DESCRIPTION
  The legacy program has been archived to _legacy/ for reference only.
  Use NewRidgeFinancial 2.0 instead (StartNewRidgeFinancial2.bat).
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent

Write-Host "The legacy New Ridge Family Financial program is retired (reference only)." -ForegroundColor Yellow
Write-Host ""
Write-Host "Use NewRidgeFinancial 2.0 instead:" -ForegroundColor Cyan
Write-Host "  Start: $Root\StartNewRidgeFinancial2.bat"
Write-Host "  URL:   http://127.0.0.1:1966/"
Write-Host ""
Write-Host "Legacy code remains in _legacy/ for reference only."
exit 1
