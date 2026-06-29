[CmdletBinding()]
param(
    [switch]$Watch,
    [int]$DebounceMs = 750
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$importSyncScript = Join-Path $projectRoot "import_sync.py"

function Invoke-Nr2ImportSync {
    if (-not (Test-Path $importSyncScript)) {
        throw "NR2 import sync not found: $importSyncScript"
    }
    Write-Host "Running NR2 import sync: $importSyncScript"
    Push-Location $projectRoot
    try {
        & python $importSyncScript
        if ($LASTEXITCODE -ne 0) {
            throw "import_sync.py exited with code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
}

Invoke-Nr2ImportSync
Write-Host "HAL import sync complete (Python authority)."
Write-Host "Read-only boundary: sync copies and transforms export files only. It never writes to SoftDent or QuickBooks."

if (-not $Watch) {
    return
}

$global:lastSyncAt = Get-Date "2000-01-01"

function Request-Sync {
    $now = Get-Date
    if (($now - $global:lastSyncAt).TotalMilliseconds -lt $DebounceMs) {
        return
    }
    $global:lastSyncAt = $now
    Start-Sleep -Milliseconds $DebounceMs
    Invoke-Nr2ImportSync
}

$watchRoots = @(
    $env:NR2_SOFTDENT_EXPORT_SOURCE,
    $env:SOFTDENT_SOURCE_DIR,
    "C:\Users\mreno\SoftDentBridge\exports",
    "C:\SoftDentFinancialExports",
    "C:\NewRidgeBridge\exports",
    $env:NR2_QUICKBOOKS_EXPORT_SOURCE,
    "C:\Users\mreno\QuickBooksExports"
) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique

$watchers = @()
foreach ($source in $watchRoots) {
    if (-not (Test-Path $source)) {
        continue
    }
    $watcher = New-Object System.IO.FileSystemWatcher $source, "*.*"
    $watcher.IncludeSubdirectories = $true
    $watcher.EnableRaisingEvents = $true
    Register-ObjectEvent $watcher Created -Action { Request-Sync } | Out-Null
    Register-ObjectEvent $watcher Changed -Action { Request-Sync } | Out-Null
    Register-ObjectEvent $watcher Renamed -Action { Request-Sync } | Out-Null
    $watchers += $watcher
}

Write-Host "Watching NR2 import source roots:"
foreach ($source in $watchRoots) {
    if (Test-Path $source) {
        Write-Host "  $source"
    }
}
Write-Host "Press Ctrl+C to stop."

while ($true) {
    Wait-Event -Timeout 5 | Out-Null
}
