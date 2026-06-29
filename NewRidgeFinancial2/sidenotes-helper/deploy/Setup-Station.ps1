<#
  HAL SideNotes — per-workstation setup.

  Run this once on each workstation after copying the package folder there.
  It writes config.json for THIS station, points the station inbox at the
  shared HAL data folder, and creates Desktop + Startup shortcuts so the
  watcher launches automatically.

  Local only: reads SideNotesIM routing metadata (sender/recipient/time) and
  never reads message bodies.
#>

[CmdletBinding()]
param(
  [string]$Station,
  [string]$SharedDataFolder,
  [switch]$NoStartup,
  [switch]$Quiet
)

$ErrorActionPreference = "Stop"
# In the built package, this script sits at the package root next to py32,
# the .py files, and config.json.
$helperDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$configPath = Join-Path $helperDir "config.json"
$python = Join-Path $helperDir "py32\python.exe"
$launcher = Join-Path $helperDir "Start-HAL-SideNotes.bat"
$defaultHubData = "C:\softdent\HAL-SideNotes-Workstation\data"

function Write-Info($msg) { if (-not $Quiet) { Write-Host $msg } }

function Get-Slug([string]$value) {
  if ($null -eq $value) { $value = "" }
  $s = $value.ToLowerInvariant()
  $s = [regex]::Replace($s, "[^a-z0-9]+", "-")
  $s = $s.Trim("-")
  if ([string]::IsNullOrWhiteSpace($s)) { return "unknown" }
  return $s
}

function Set-Prop($obj, $name, $value) {
  if ($obj.PSObject.Properties.Name -contains $name) { $obj.$name = $value }
  else { $obj | Add-Member -NotePropertyName $name -NotePropertyValue $value -Force }
}

Write-Info ""
Write-Info "==================================================="
Write-Info "  HAL SideNotes - Workstation Setup"
Write-Info "==================================================="
Write-Info ""

# --- 0. Sanity checks ---------------------------------------------------------
if (-not (Test-Path $python)) {
  throw "Bundled 32-bit Python not found at: $python`nThis package looks incomplete. Re-copy the whole folder."
}
$simDir = "C:\Program Files (x86)\SideNotesIM"
if (-not (Test-Path (Join-Path $simDir "VistaDBCOM20.DLL"))) {
  Write-Warning "SideNotesIM was not detected at $simDir."
  Write-Warning "The watcher needs SideNotesIM installed on this workstation to read history.vdb."
}

# --- 1. Station name ----------------------------------------------------------
$knownStations = @(
  "Server","Room 2","Room 3","Room 4","Room 5",
  "Frontdesk 1","Frontdesk 2","Office Manager"
)
if (-not $Station) {
  Write-Info "Which SideNotesIM station is THIS computer?"
  Write-Info "(Type the station name EXACTLY as it appears in SideNotesIM.)"
  Write-Info ""
  for ($i = 0; $i -lt $knownStations.Count; $i++) {
    Write-Info ("  {0}. {1}" -f ($i + 1), $knownStations[$i])
  }
  Write-Info "  (or type a custom name)"
  Write-Info ""
  $ans = Read-Host "Station (number or name) [default: $env:COMPUTERNAME]"
  if ([string]::IsNullOrWhiteSpace($ans)) {
    $Station = $env:COMPUTERNAME
  } elseif ($ans -match '^[0-9]+$' -and [int]$ans -ge 1 -and [int]$ans -le $knownStations.Count) {
    $Station = $knownStations[[int]$ans - 1]
  } else {
    $Station = $ans.Trim()
  }
}
$slug = Get-Slug $Station
Write-Info ""
Write-Info "Station: '$Station'  ->  inbox file: sidenotes-inbox-$slug.json"

# --- 2. Shared data folder ----------------------------------------------------
if (-not $SharedDataFolder) {
  Write-Info ""
  Write-Info "Where should this station publish its inbox so HAL can read it?"
  Write-Info "Default is the shared SoftDent hub used by all workstations:"
  Write-Info "  $defaultHubData"
  Write-Info "Press Enter to use that, or type a UNC path if this station reaches"
  Write-Info "the hub through a share (for example \\SERVER\softdent\HAL-SideNotes-Workstation\data)."
  Write-Info ""
  $SharedDataFolder = (Read-Host "Shared data folder [$defaultHubData]").Trim('"').Trim()
  if ([string]::IsNullOrWhiteSpace($SharedDataFolder)) {
    $SharedDataFolder = $defaultHubData
  }
}

$stationInboxPath = ""
if ([string]::IsNullOrWhiteSpace($SharedDataFolder)) {
  Write-Warning "No shared folder given - this station will publish locally only and HAL on another PC won't see it."
} else {
  if (-not (Test-Path $SharedDataFolder)) {
    try {
      New-Item -ItemType Directory -Path $SharedDataFolder -Force | Out-Null
      Write-Info "Created shared inbox folder: $SharedDataFolder"
    } catch {
      Write-Warning "Shared folder not reachable right now: $SharedDataFolder"
      Write-Warning "Setup will still write the path; make sure the share is available when the watcher runs."
    }
  }
  $stationInboxPath = (Join-Path $SharedDataFolder ("sidenotes-inbox-{0}.json" -f $slug))
  Write-Info "Will publish to: $stationInboxPath"
}

# --- 3. Write config.json -----------------------------------------------------
# Start from the template config in the package, then override per-station keys.
$cfg = $null
if (Test-Path $configPath) {
  try { $cfg = Get-Content $configPath -Raw | ConvertFrom-Json } catch { $cfg = $null }
}
if ($null -eq $cfg) { $cfg = [pscustomobject]@{} }

Set-Prop $cfg "myStation" $Station
Set-Prop $cfg "announceScope" "all"
# Keep the legacy combined file LOCAL so stations never clobber a shared one.
Set-Prop $cfg "inboxPath" (Join-Path $helperDir "work\sidenotes-inbox.json")
Set-Prop $cfg "stationInboxPath" $stationInboxPath

($cfg | ConvertTo-Json -Depth 6) | Set-Content -Path $configPath -Encoding UTF8
Write-Info ""
Write-Info "Wrote config: $configPath"

# --- 4. Shortcuts -------------------------------------------------------------
function New-Shortcut($linkPath, $target) {
  $ws = New-Object -ComObject WScript.Shell
  $sc = $ws.CreateShortcut($linkPath)
  $sc.TargetPath = $target
  $sc.WorkingDirectory = (Split-Path -Parent $target)
  $sc.WindowStyle = 7   # minimized
  $sc.Description = "HAL SideNotes watcher ($Station)"
  $sc.Save()
}

$desktop = [Environment]::GetFolderPath("Desktop")
$desktopLink = Join-Path $desktop "HAL SideNotes.lnk"
New-Shortcut $desktopLink $launcher
Write-Info "Created desktop shortcut: $desktopLink"

if (-not $NoStartup) {
  $startup = [Environment]::GetFolderPath("Startup")
  $startupLink = Join-Path $startup "HAL SideNotes.lnk"
  New-Shortcut $startupLink $launcher
  Write-Info "Added to Windows startup: $startupLink"
}

Write-Info ""
Write-Info "==================================================="
Write-Info "  Setup complete for station: $Station"
Write-Info "==================================================="
Write-Info ""
Write-Info "Start it now by double-clicking 'HAL SideNotes' on the Desktop,"
Write-Info "or it will auto-start at next sign-in."
Write-Info ""

if (-not $Quiet) {
  $go = Read-Host "Start the watcher now? (Y/n)"
  if ([string]::IsNullOrWhiteSpace($go) -or $go -match '^[Yy]') {
    Start-Process -FilePath $launcher -WorkingDirectory $helperDir
    Write-Info "Watcher launched."
  }
}
