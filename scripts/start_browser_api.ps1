param(
  [int]$Port = 8096
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
  Write-Error "Missing .venv. Create the virtual environment before starting the browser API."
}

$env:APP_AUTH_USERS_JSON = @'
[
  {
    "username": "office.manager",
    "display_name": "Office Manager",
    "password": "office-manager",
    "roles": ["dashboard:read", "hal:operator"]
  }
]
'@

$env:HAL_BROWSER_DEV_AUTH = "1"
$env:HAL_OLLAMA_MODEL = "hal-chat:8b"

Write-Host "Starting HAL browser API on http://127.0.0.1:$Port"
Write-Host "Dev auth enabled (HAL_BROWSER_DEV_AUTH=1). Login user: office.manager / office-manager"

& ".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload
