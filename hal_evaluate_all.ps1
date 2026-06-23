
# cSpell:ignore LASTEXITCODE venv pytest flake8 noqa
# PowerShell script to simulate a HAL-style evaluation of the entire codebase
# Runs lint, typecheck, and tests for all major subprojects and summarizes results

$ErrorActionPreference = 'Continue'

function Invoke-Step {
    param(
        [string]$Label,
        [string]$Command,
        [string]$WorkingDir = $null
    )
    Write-Output "\n=== $Label ==="
    if ($WorkingDir) { Push-Location $WorkingDir }
    Write-Output "[COMMAND] $Command"
    try {
        $output = Invoke-Expression $Command 2>&1
        Write-Output "[OUTPUT START]"
        if ($null -eq $output -or $output -eq "") {
            Write-Output "(No output from command)"
        } else {
            Write-Output $output
        }
        Write-Output "[OUTPUT END]"
        if ($LASTEXITCODE -eq 0) {
            Write-Output "[PASS] $Label"
        } else {
            Write-Output "[FAIL] $Label (exit code $LASTEXITCODE)"
        }
    } catch {
        Write-Output "[ERROR] $Label"
        Write-Output $_
    }
    if ($WorkingDir) { Pop-Location }
}


# Frontend checks
if (Test-Path ./frontend/package.json) {
    Invoke-Step "Frontend: npm install" "npm install" "./frontend"
    Invoke-Step "Frontend: lint" "npm run lint" "./frontend"
    Invoke-Step "Frontend: typecheck" "npm run typecheck" "./frontend"
    Invoke-Step "Frontend: test" "npm test -- --verbose" "./frontend"
}

Write-Output "\n=== HAL-style evaluation complete ==="