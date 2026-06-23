param(
    [switch]$PreviewOnly,
    [string]$RootPortHardwareId = 'PCI\VEN_8086&DEV_AE4D&SUBSYS_88EF1043&REV_10',
    [int]$ValidationWindowMinutes = 5,
    [int]$ValidationThreshold = 25
)

$ErrorActionPreference = 'Stop'

function Get-WheaRootPortWindowCount {
    param(
        [string]$HardwareId,
        [int]$Minutes
    )

    $startTime = (Get-Date).AddMinutes(-1 * $Minutes)
    $events = Get-WinEvent -FilterHashtable @{
        LogName = 'System'
        ProviderName = 'Microsoft-Windows-WHEA-Logger'
        StartTime = $startTime
    } -ErrorAction SilentlyContinue

    $matchedEvents = @(
        $events | Where-Object {
            $_.Id -eq 17 -and
            $_.Message -match [regex]::Escape($HardwareId)
        }
    )

    return [pscustomobject]@{
        Count = $matchedEvents.Count
        StartTime = $startTime
        EndTime = Get-Date
        Recent = @($matchedEvents | Select-Object -First 5 TimeCreated, Id, LevelDisplayName)
    }
}

$reportPath = Join-Path $PSScriptRoot 'gpu_stability_mitigation_report.txt'
$timestamp = Get-Date -Format s
$schemeLine = powercfg /GETACTIVESCHEME
$schemeGuid = ($schemeLine -replace '.*GUID:\s*([a-fA-F0-9\-]+).*', '$1').Trim()

if (-not $schemeGuid) {
    throw 'Unable to determine active power scheme GUID.'
}

$before = (powercfg /Q $schemeGuid SUB_PCIEXPRESS ASPM | Out-String)
$aspmAlreadyOffBefore = (
    $before -match 'Current AC Power Setting Index:\s*0x00000000' -and
    $before -match 'Current DC Power Setting Index:\s*0x00000000'
)

if (-not $PreviewOnly) {
    powercfg /SETACVALUEINDEX $schemeGuid SUB_PCIEXPRESS ASPM 0 | Out-Null
    powercfg /SETDCVALUEINDEX $schemeGuid SUB_PCIEXPRESS ASPM 0 | Out-Null
    powercfg /S $schemeGuid | Out-Null
}

$after = (powercfg /Q $schemeGuid SUB_PCIEXPRESS ASPM | Out-String)
$validation = Get-WheaRootPortWindowCount -HardwareId $RootPortHardwareId -Minutes $ValidationWindowMinutes
$validationStatus = if ($validation.Count -ge $ValidationThreshold) {
    'ALERT'
} elseif ($validation.Count -gt 0) {
    'NOISY'
} else {
    'CLEAR'
}
$recentValidationLines = if ($validation.Recent.Count -gt 0) {
    @($validation.Recent | ForEach-Object {
        "RecentWheaEvent: $($_.TimeCreated.ToString('s')) | Id=$($_.Id) | Level=$($_.LevelDisplayName)"
    })
} else {
    @('RecentWheaEvent: none')
}

$logLines = @(
    'GPU Stability Mitigation Report',
    "Timestamp: $timestamp",
    "PreviewOnly: $PreviewOnly",
    "ActiveScheme: $schemeGuid",
    "ASPMAlreadyOffBefore: $aspmAlreadyOffBefore",
    '--- PCIe ASPM Before ---',
    $before,
    '--- PCIe ASPM After ---',
    $after,
    '--- Root Port Validation ---',
    "RootPortHardwareId: $RootPortHardwareId",
    "ValidationWindowMinutes: $ValidationWindowMinutes",
    "ValidationThreshold: $ValidationThreshold",
    "ValidationStatus: $validationStatus",
    "WHEA17RootPortEventsInWindow: $($validation.Count)",
    $recentValidationLines,
    '--- Notes ---',
    'This mitigation disables PCIe Link State Power Management (ASPM) for AC and DC on the active power plan.',
    'Reboot is recommended for a clean telemetry baseline.',
    'If ASPM was already off before this run, this mitigation is only a verification step.',
    'If validation remains NOISY or ALERT, the remaining issue is likely firmware, driver, slot, power delivery, or device hardware rather than the Windows PCIe power plan.'
)

$logLines | Set-Content -Path $reportPath -Encoding UTF8
Write-Host "Mitigation report written to $reportPath"