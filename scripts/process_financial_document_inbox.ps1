[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$InboxPath = "",
    [string]$ArchivePath = "",
    [string]$PythonExe = "",
    [string]$DbPath = ""
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $InboxPath) {
    $InboxPath = Join-Path $scriptRoot "..\local_accounting_inbox"
}
if (-not $ArchivePath) {
    $ArchivePath = Join-Path $scriptRoot "..\local_accounting_inbox\processed"
}
if (-not $PythonExe) {
    $PythonExe = Join-Path $scriptRoot "..\.venv\Scripts\python.exe"
}

$scriptPath = Join-Path $scriptRoot "process_financial_document.py"
$supportedExtensions = @('.pdf', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.txt')

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found at $PythonExe"
}

if (-not (Test-Path $scriptPath)) {
    throw "OCR ingestion script not found at $scriptPath"
}

New-Item -ItemType Directory -Force -Path $InboxPath | Out-Null
New-Item -ItemType Directory -Force -Path $ArchivePath | Out-Null

$files = Get-ChildItem -Path $InboxPath -File | Where-Object { $supportedExtensions -contains $_.Extension.ToLowerInvariant() }

foreach ($file in $files) {
    $jsonOutput = Join-Path $ArchivePath ($file.BaseName + '.ocr.json')
    $command = @(
        $scriptPath,
        '--input', $file.FullName,
        '--json-output', $jsonOutput
    )

    if ($DbPath) {
        $command += @('--db-path', $DbPath)
    }

    if ($PSCmdlet.ShouldProcess($file.FullName, 'OCR and archive financial document')) {
        & $PythonExe @command
        if ($LASTEXITCODE -ne 0) {
            throw "OCR ingestion failed for $($file.FullName)"
        }

        $destinationPath = Join-Path $ArchivePath $file.Name
        Move-Item -Path $file.FullName -Destination $destinationPath -Force
    }
}