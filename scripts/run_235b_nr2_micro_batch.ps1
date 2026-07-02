<#
.SYNOPSIS
  Run NR2 micro 235B sections sequentially (1a-2c) with lane isolation.
#>
[CmdletBinding()]
param(
    [ValidateSet('1a', '1b', '1c', '2a', '2b', '2c')]
    [string[]]$Sections = @('1a', '1b', '1c', '2a', '2b', '2c')
)

$ErrorActionPreference = 'Continue'
$Root = Split-Path $PSScriptRoot -Parent
$runner = Join-Path $PSScriptRoot 'run_235b_isolated_section.ps1'
$logDir = Join-Path $Root '.local_logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$batchLog = Join-Path $logDir '235b_nr2_micro_batch.log'

function Write-BatchLog([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -Path $batchLog -Value $line
    Write-Host $line
}

Write-BatchLog "Starting NR2 micro batch: $($Sections -join ', ')"

foreach ($section in $Sections) {
    Write-BatchLog "=== Section $section ==="
    $logFile = Join-Path $logDir "235b_section${section}_run.log"
    $output = & $runner -Section $section -AllowDirtyRepo -ForceStopOllamaApp -OverwriteReport 2>&1
    $output | Tee-Object -FilePath $logFile
    $sectionExit = $LASTEXITCODE
    if (-not $? -or ($sectionExit -ne 0 -and $null -ne $sectionExit)) {
        Write-BatchLog "Section $section failed (exit=$sectionExit) - stopping batch."
        exit 1
    }
    Write-BatchLog "Section $section complete."
}

Write-BatchLog "Batch complete."
