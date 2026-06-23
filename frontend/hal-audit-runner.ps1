Set-Location "$PSScriptRoot"
$logPath = Join-Path $PSScriptRoot "hal-audit-task.log"
if (Test-Path $logPath) {
	Remove-Item $logPath -Force
}
$env:HAL_EVAL_USERNAME = 'admin'
$env:HAL_EVAL_PASSWORD = 'password'
& .\node_modules\.bin\playwright.cmd test --config="$PSScriptRoot\playwright.config.ts" src/e2e/hal-random-audit.spec.ts --project=chromium --reporter=line *>&1 |
	Tee-Object -FilePath $logPath
$exitCode = $LASTEXITCODE
"EXIT:$exitCode" | Tee-Object -FilePath $logPath -Append
exit $exitCode
