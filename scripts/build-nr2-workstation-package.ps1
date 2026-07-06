<#
.SYNOPSIS
  Build NR2 Office Workstation install package (folder + zip) for operatory PCs.

.DESCRIPTION
  Creates dist\NR2-Office-Workstation\ with:
    - NewRidgeFinancial2 app bundle (site + Python modules + SideNotes py32)
    - Install.bat / Setup-Workstation.ps1 / Start-NR2-Workstation.bat
    - Optional bundled python\ venv (pywebview + bottle)

  Output zip: dist\NR2-Office-Workstation.zip

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\build-nr2-workstation-package.ps1
#>
[CmdletBinding()]
param(
    [switch]$SkipZip,
    [switch]$SkipPython,
    [switch]$SkipPythonBootstrap
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path $PSScriptRoot -Parent
$Nr2Dir = Join-Path $RepoRoot 'NewRidgeFinancial2'
$DeployDir = Join-Path $Nr2Dir 'workstation-deploy'
$DistRoot = Join-Path $RepoRoot 'dist'
$PkgName = 'NR2-Office-Workstation'
$Pkg = Join-Path $DistRoot $PkgName

function Copy-TreeFiltered {
    param(
        [string]$Source,
        [string]$Dest,
        [string[]]$ExcludeDirNames = @()
    )
    if (-not (Test-Path $Source)) { throw "Missing source: $Source" }
    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
    Get-ChildItem -Path $Source -Force | ForEach-Object {
        if ($ExcludeDirNames -contains $_.Name) { return }
        $target = Join-Path $Dest $_.Name
        if ($_.PSIsContainer) {
            Copy-TreeFiltered -Source $_.FullName -Dest $target -ExcludeDirNames $ExcludeDirNames
        } else {
            Copy-Item $_.FullName $target -Force
        }
    }
}

Write-Host "Building $PkgName ..." -ForegroundColor Cyan

if (Test-Path $Pkg) { Remove-Item $Pkg -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Pkg | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Pkg 'app_data\nr2') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Pkg 'logs') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Pkg 'assets') | Out-Null

$appDest = Join-Path $Pkg 'NewRidgeFinancial2'
New-Item -ItemType Directory -Force -Path $appDest | Out-Null

# Python modules at NR2 root (skip tests and heavy automation folders).
Get-ChildItem $Nr2Dir -Filter '*.py' -File | Where-Object { $_.Name -notmatch '^test_' } | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $appDest $_.Name) -Force
}

foreach ($file in @('nr2-build.json', 'requirements-workstation.txt', 'office-programs.schema.json')) {
    $src = Join-Path $Nr2Dir $file
    if (Test-Path $src) { Copy-Item $src (Join-Path $appDest $file) -Force }
}

# Full site bundle (workstation UI + shared HAL assets).
Copy-TreeFiltered -Source (Join-Path $Nr2Dir 'site') -Dest (Join-Path $appDest 'site')

# SideNotes 32-bit helper runtime (required for history.vdb on workstations).
$snSrc = Join-Path $Nr2Dir 'sidenotes-helper'
$snDest = Join-Path $appDest 'sidenotes-helper'
Copy-TreeFiltered -Source $snSrc -Dest $snDest -ExcludeDirNames @('dist', '__pycache__')
$py32 = Join-Path $snDest 'py32\python.exe'
if (-not (Test-Path $py32)) {
    throw "SideNotes py32 runtime missing at $py32 - required for workstation package."
}

# Deploy scaffolding at package root.
foreach ($f in @('Install.bat', 'Start-NR2-Workstation.bat', 'Start-NR2-Workstation-Hidden.bat', 'Start-Workstation.ps1', 'Setup-Workstation.ps1', '.env.example')) {
    Copy-Item (Join-Path $DeployDir $f) (Join-Path $Pkg $f) -Force
}
Copy-Item (Join-Path $DeployDir 'README-WORKSTATION.md') (Join-Path $Pkg 'README.md') -Force

$iconSrc = Join-Path $RepoRoot 'assets\nr2-icon.ico'
if (Test-Path $iconSrc) {
    Copy-Item $iconSrc (Join-Path $Pkg 'assets\nr2-icon.ico') -Force
}

$manifestPath = Join-Path $Nr2Dir 'nr2-build.json'
$schemaVersion = 'unknown'
if (Test-Path $manifestPath) {
    try {
        $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
        if ($manifest.schemaVersion) { $schemaVersion = [string]$manifest.schemaVersion }
    } catch {}
}
Set-Content -Path (Join-Path $Pkg 'VERSION.txt') -Value $schemaVersion -Encoding UTF8

# Bundled 64-bit Python for pywebview.
if (-not $SkipPython) {
    Write-Host 'Bootstrapping bundled python\ runtime ...' -ForegroundColor Cyan
    $PythonDir = Join-Path $Pkg 'python'
    $PythonW = Join-Path $PythonDir 'Scripts\pythonw.exe'
    $ReqFile = Join-Path $appDest 'requirements-workstation.txt'

    if (-not (Test-Path $PythonW)) {
        $pyLauncher = Get-Command 'py' -ErrorAction SilentlyContinue
        $created = $false
        if ($pyLauncher) {
            foreach ($ver in @('-3.13', '-3.12', '-3.11')) {
                try {
                    & $pyLauncher.Source $ver -m venv $PythonDir --copies 2>$null
                    if (Test-Path $PythonW) { $created = $true; break }
                } catch { continue }
            }
            if (-not $created) {
                & $pyLauncher.Source -m venv $PythonDir --copies
                $created = Test-Path $PythonW
            }
        }
        if (-not $created) {
            $python = Get-Command 'python' -ErrorAction SilentlyContinue
            if ($python) {
                & $python.Source -m venv $PythonDir --copies
                $created = Test-Path $PythonW
            }
        }
        if (-not $created) {
            Write-Warning 'Could not bundle python\ during build. Target PCs must run Install.bat (needs Python 3.11+ once).'
        } else {
            $pip = Join-Path $PythonDir 'Scripts\pip.exe'
            & $pip install --disable-pip-version-check -r $ReqFile
            if ($LASTEXITCODE -ne 0) { throw 'pip install failed during package build' }
            Write-Host "Bundled python ready: $PythonW" -ForegroundColor Green
        }
    }
}

# Remove build-time .env if created
Remove-Item (Join-Path $Pkg '.env') -Force -ErrorAction SilentlyContinue

Get-ChildItem $Pkg -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }

$sizeMB = [math]::Round((Get-ChildItem $Pkg -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
Write-Host "Package folder: $Pkg  (~$sizeMB MB)" -ForegroundColor Green

if (-not $SkipZip) {
    New-Item -ItemType Directory -Force -Path $DistRoot | Out-Null
    $zipBase = Join-Path $DistRoot $PkgName
    $zip = "$zipBase.zip"
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Write-Host 'Creating zip (this may take a minute) ...' -ForegroundColor Cyan
    Compress-Archive -Path $Pkg -DestinationPath $zip -CompressionLevel Optimal
    $zipMB = [math]::Round((Get-Item $zip).Length / 1MB, 1)
    Write-Host "Zip ready: $zip  (~$zipMB MB)" -ForegroundColor Green
}

Write-Host ''
Write-Host 'Hand out the zip to each workstation. Extract and run Install.bat.' -ForegroundColor Cyan
