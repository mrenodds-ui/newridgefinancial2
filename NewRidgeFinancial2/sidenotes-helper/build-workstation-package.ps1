<#
  Builds the HAL SideNotes workstation package: a self-contained, drop-in
  folder (including the bundled 32-bit Python runtime) plus a zip you can copy
  to each workstation.

  Output:
    dist\HAL-SideNotes-Workstation\        (the folder to copy)
    dist\HAL-SideNotes-Workstation.zip     (zipped, easy to hand out)

  Run from anywhere:
    powershell -ExecutionPolicy Bypass -File build-workstation-package.ps1
#>

[CmdletBinding()]
param(
  [switch]$SkipZip
)

$ErrorActionPreference = "Stop"
$helper = Split-Path -Parent $MyInvocation.MyCommand.Path
$distRoot = Join-Path $helper "dist"
$pkgName = "HAL-SideNotes-Workstation"
$pkg = Join-Path $distRoot $pkgName

Write-Host "Building $pkgName ..."

# Clean previous build.
if (Test-Path $pkg) { Remove-Item $pkg -Recurse -Force }
New-Item -ItemType Directory -Path $pkg -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $pkg "work") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $pkg "data") -Force | Out-Null

# 1. Core watcher files.
$coreFiles = @(
  "sidenotes_watcher.py",
  "vdb_reader.py",
  "announcer.py",
  "config.json"
)
foreach ($f in $coreFiles) {
  $src = Join-Path $helper $f
  if (-not (Test-Path $src)) { throw "Missing required file: $src" }
  Copy-Item $src (Join-Path $pkg $f) -Force
}

# 2. Deploy scaffolding (installer/launcher/readme) -> package ROOT.
$deployDir = Join-Path $helper "deploy"
Copy-Item (Join-Path $deployDir "Install.bat")             (Join-Path $pkg "Install.bat") -Force
Copy-Item (Join-Path $deployDir "Setup-Station.ps1")       (Join-Path $pkg "Setup-Station.ps1") -Force
Copy-Item (Join-Path $deployDir "Start-HAL-SideNotes.bat") (Join-Path $pkg "Start-HAL-SideNotes.bat") -Force
Copy-Item (Join-Path $deployDir "README-WORKSTATION.md")   (Join-Path $pkg "README.md") -Force

# 3. Bundled 32-bit Python runtime (the big part).
$py32 = Join-Path $helper "py32"
if (-not (Test-Path (Join-Path $py32 "python.exe"))) {
  throw "py32\python.exe not found. The bundled runtime is required for the package."
}
Write-Host "Copying py32 runtime (this is the large step) ..."
Copy-Item $py32 (Join-Path $pkg "py32") -Recurse -Force
# Drop caches to keep the package lean.
Get-ChildItem (Join-Path $pkg "py32") -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
  ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }

# 4. Reset config.json to a clean template (no machine-specific paths/state).
function Set-Prop($obj, $name, $value) {
  if ($obj.PSObject.Properties.Name -contains $name) { $obj.$name = $value }
  else { $obj | Add-Member -NotePropertyName $name -NotePropertyValue $value -Force }
}
$cfgPath = Join-Path $pkg "config.json"
$cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
Set-Prop $cfg "myStation" ""           # set by Setup-Station.ps1
Set-Prop $cfg "inboxPath" ""           # set by Setup-Station.ps1 (kept local)
Set-Prop $cfg "stationInboxPath" ""    # set by Setup-Station.ps1 (shared folder)
Set-Prop $cfg "announceScope" "all"
($cfg | ConvertTo-Json -Depth 6) | Set-Content -Path $cfgPath -Encoding UTF8

$sizeMB = [math]::Round((Get-ChildItem $pkg -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
Write-Host "Package folder ready: $pkg  (~$sizeMB MB)"

# 5. Zip it.
if (-not $SkipZip) {
  $zip = Join-Path $distRoot "$pkgName.zip"
  if (Test-Path $zip) { Remove-Item $zip -Force }
  Write-Host "Creating zip ..."
  Compress-Archive -Path $pkg -DestinationPath $zip -CompressionLevel Optimal
  $zipMB = [math]::Round((Get-Item $zip).Length / 1MB, 1)
  Write-Host "Zip ready: $zip  (~$zipMB MB)"
}

Write-Host ""
Write-Host "Done. Copy the folder or zip to each workstation and run Install.bat."
