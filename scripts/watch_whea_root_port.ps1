[CmdletBinding()]
param(
    [string]$RootPortHardwareId = 'PCI\VEN_8086&DEV_AE4D&SUBSYS_88EF1043&REV_10',
    [int]$WindowMinutes = 5,
    [int]$WarningThreshold = 25,
    [int]$PollSeconds = 30,
    [switch]$Continuous,
    [string]$OutputPath = ''
)

$ErrorActionPreference = 'Stop'

function Get-WheaWindowCount {
    param(
        [string]$HardwareId,
        [int]$Minutes
    )

    $start = (Get-Date).AddMinutes(-1 * $Minutes)
    $events = Get-WinEvent -FilterHashtable @{
        LogName = 'System'
        ProviderName = 'Microsoft-Windows-WHEA-Logger'
        StartTime = $start
    } -ErrorAction SilentlyContinue

    $matchedEvents = @(
        $events | Where-Object {
            $_.Id -eq 17 -and
            $_.Message -match [regex]::Escape($HardwareId)
        }
    )

    return [pscustomobject]@{
        Count = $matchedEvents.Count
        StartTime = $start
        EndTime = Get-Date
        Recent = @($matchedEvents | Select-Object -First 5 TimeCreated, Id, LevelDisplayName, Message)
    }
}

function Write-WatcherLine {
    param([string]$Line)
    Write-Host $Line
    if ($OutputPath) {
        Add-Content -Path $OutputPath -Value $Line
    }
}

function Invoke-WheaCheck {
    $window = Get-WheaWindowCount -HardwareId $RootPortHardwareId -Minutes $WindowMinutes
    $count = [int]$window.Count
    $status = if ($count -ge $WarningThreshold) { 'ALERT' } else { 'OK' }

    $line = "[$(Get-Date -Format s)] $status WHEA17 root-port events in last $WindowMinutes minute(s): $count (threshold=$WarningThreshold)"
    Write-WatcherLine -Line $line

    if ($status -eq 'ALERT') {
        Write-WatcherLine -Line 'Recent matching WHEA events:'
        if ($window.Recent.Count -gt 0) {
            $window.Recent | Format-Table -AutoSize | Out-String | ForEach-Object { Write-WatcherLine -Line $_ }
        } else {
            Write-WatcherLine -Line 'No recent event details were available.'
        }
        return 2
    }

    return 0
}

if ($OutputPath) {
    "WHEA root-port watcher started at $(Get-Date -Format s)" | Set-Content -Path $OutputPath -Encoding UTF8
}

if ($Continuous) {
    Write-WatcherLine -Line "Continuous mode enabled. Polling every $PollSeconds second(s)."
    while ($true) {
        [void](Invoke-WheaCheck)
        Start-Sleep -Seconds $PollSeconds
    }
}

$exitCode = Invoke-WheaCheck
exit $exitCode