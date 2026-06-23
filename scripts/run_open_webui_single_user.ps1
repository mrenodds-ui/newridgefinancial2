[CmdletBinding()]
param(
    [string]$BindHost = '127.0.0.1',
    [int]$Port = 8080,
    [string]$DataDir = (Join-Path $env:LOCALAPPDATA 'OpenWebUI')
)

$ErrorActionPreference = 'Stop'

$resolvedDataDir = [System.IO.Path]::GetFullPath($DataDir)
$null = New-Item -ItemType Directory -Path $resolvedDataDir -Force

$env:DATA_DIR = $resolvedDataDir
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
$env:WEBUI_AUTH = 'False'
$env:ENABLE_SIGNUP = 'False'
$env:ENABLE_LOGIN_FORM = 'False'
$env:WEBUI_URL = "http://$BindHost`:$Port"

$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCommand) {
    throw 'uv is not available on PATH. Open WebUI auto-start cannot launch until uv is installed and available for the current user.'
}

Set-Location $resolvedDataDir

Write-Host "Starting Open WebUI in single-user mode at http://$BindHost`:$Port"
Write-Host "Data directory: $resolvedDataDir"
Write-Host 'Authentication disabled via WEBUI_AUTH=False'

& $uvCommand.Source tool run --from open-webui open-webui serve --host $BindHost --port $Port