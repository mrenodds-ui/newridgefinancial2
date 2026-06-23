$ErrorActionPreference = 'Stop'

$gpuInstanceId = 'PCI\VEN_1002&DEV_7590&SUBSYS_24291458&REV_C0\6&273CBDEF&0&00000030'
$rootPortInstanceId = 'PCI\VEN_8086&DEV_AE4D&SUBSYS_88EF1043&REV_10\3&11583659&0&30'
$rootPortHardwareId = 'PCI\VEN_8086&DEV_AE4D&SUBSYS_88EF1043&REV_10'
$bootTime = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$wheaEvents = Get-WinEvent -FilterHashtable @{
    LogName = 'System'
    ProviderName = 'Microsoft-Windows-WHEA-Logger'
    StartTime = $bootTime
} -ErrorAction SilentlyContinue

$rootPortWarnings = @(
    $wheaEvents | Where-Object {
        $_.Id -eq 17 -and
        $_.Message -match [regex]::Escape($rootPortHardwareId)
    }
)

$informationalEvents = @($wheaEvents | Where-Object { $_.Id -eq 3 })
$recentWarnings = @($rootPortWarnings | Select-Object -First 5 TimeCreated, Id, LevelDisplayName, Message)

$gpuPaths = Get-PnpDeviceProperty -InstanceId $gpuInstanceId -KeyName 'DEVPKEY_Device_LocationPaths' |
    Select-Object -ExpandProperty Data
$rootPortPaths = Get-PnpDeviceProperty -InstanceId $rootPortInstanceId -KeyName 'DEVPKEY_Device_LocationPaths' |
    Select-Object -ExpandProperty Data

Write-Host '=== GPU PCIe Stability Report ==='
[pscustomobject]@{
    LastBoot = $bootTime
    SinceBoot_WHEA17_RootPort = $rootPortWarnings.Count
    SinceBoot_WHEA3_All = $informationalEvents.Count
    RootPortDevice = $rootPortInstanceId
    GpuDevice = $gpuInstanceId
} | Format-List | Out-String | Write-Host

Write-Host '=== Root Port Paths ==='
$rootPortPaths | Out-String | Write-Host

Write-Host '=== GPU Paths ==='
$gpuPaths | Out-String | Write-Host

Write-Host '=== Recent Root Port Warnings ==='
if ($recentWarnings.Count -gt 0) {
    $recentWarnings | Format-List | Out-String | Write-Host
} else {
    Write-Host 'None since boot.'
}