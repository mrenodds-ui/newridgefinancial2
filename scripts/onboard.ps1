# Onboarding automation script
Write-Host "Setting up Python environment..."
pip install -r requirements.txt -r requirements-dev.txt
Write-Host "Setting up Node environments..."
Push-Location frontend
npm ci
Pop-Location
Write-Host "Running initial tests..."
.\.venv\Scripts\python.exe -m pytest app/tests
Push-Location frontend
npm test
Pop-Location
Write-Host "Onboarding complete."
