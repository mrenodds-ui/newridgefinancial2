# PowerShell script to install and configure QuickBooks ODBC Node.js server as a Windows service using NSSM
# Run as Administrator

$nodePath = "C:\Program Files\nodejs\node.exe"
$scriptPath = "C:\NewRidgeFamilyFinancial\frontend\scripts\quickbooks-odbc-server.cjs"
$serviceName = "QuickBooksODBCServer"
$nssmPath = "nssm"  # Assumes nssm.exe is in PATH

# Install service
Write-Host "Registering Node.js ODBC server as Windows service..."
& $nssmPath install $serviceName $nodePath $scriptPath

# Set working directory
& $nssmPath set $serviceName AppDirectory (Split-Path $scriptPath)

# Set service to start automatically
Set-Service -Name $serviceName -StartupType Automatic

# Start the service
Start-Service -Name $serviceName

Write-Host "Service '$serviceName' installed and started."
Write-Host "You can manage it from Windows Services or with 'nssm' commands."
