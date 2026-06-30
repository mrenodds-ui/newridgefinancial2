[CmdletBinding()]
param(
    [switch]$SkipImportPull,
    [string]$SoftDentSource,
    [string]$QuickBooksSource
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$repoRoot = Split-Path -Parent $projectRoot
$syncScript = Join-Path $projectRoot "sync_document_sources.py"

function Import-DotEnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $name = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim()
        if ($name) { Set-Item -Path "Env:$name" -Value $value }
    }
}

Import-DotEnvFile (Join-Path $repoRoot ".env")
Import-DotEnvFile (Join-Path $projectRoot ".env")

if (-not [string]::IsNullOrWhiteSpace($SoftDentSource)) {
    $env:NR2_SOFTDENT_EXPORT_SOURCE = $SoftDentSource
}
if (-not [string]::IsNullOrWhiteSpace($QuickBooksSource)) {
    $env:NR2_QUICKBOOKS_EXPORT_SOURCE = $QuickBooksSource
}

if (-not (Test-Path $syncScript)) {
    throw "Document source sync script not found: $syncScript"
}

Write-Host "Running document source sync: $syncScript"
Push-Location $projectRoot
try {
    $args = @($syncScript)
    if ($SkipImportPull) {
        $args += "--skip-import-pull"
    }
    & python @args
    if ($LASTEXITCODE -ne 0) {
        throw "sync_document_sources.py exited with code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

Write-Host "Document source sync complete (SoftDent/QuickBooks -> Documents page)."
