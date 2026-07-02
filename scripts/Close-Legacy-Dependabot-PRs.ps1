<#
.SYNOPSIS
  Close open Dependabot PRs for legacy frontend/Actions (requires GitHub CLI).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\Close-Legacy-Dependabot-PRs.ps1
#>
[CmdletBinding()]
param(
    [string]$Repo = 'mrenodds-ui/newridgefamilyfinancial'
)

$ErrorActionPreference = 'Stop'
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host 'GitHub CLI (gh) not installed. Close PRs manually or rely on .github/workflows/close-legacy-dependabot-prs.yml on push.' -ForegroundColor Yellow
    exit 1
}

$pulls = gh pr list --repo $Repo --author app/dependabot --state open --json number,title | ConvertFrom-Json
if (-not $pulls -or $pulls.Count -eq 0) {
    Write-Host 'No open Dependabot PRs.' -ForegroundColor Green
    exit 0
}

foreach ($pr in $pulls) {
    Write-Host "Closing #$($pr.number): $($pr.title)" -ForegroundColor Cyan
    gh pr close $pr.number --repo $Repo --comment 'Legacy NR2 hygiene: Dependabot disabled for frontend/Actions; see .github/dependabot.yml.'
}

Write-Host "Closed $($pulls.Count) PR(s)." -ForegroundColor Green
