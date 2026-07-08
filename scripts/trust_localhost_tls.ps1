# Trust NR2 localhost TLS certificate in Windows (Chrome/Edge loopback HTTPS).
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$tlsDir = Join-Path $repoRoot 'app_data\nr2\tls'
$pfxPath = Join-Path $tlsDir '127.0.0.1.pfx'
$certPath = Join-Path $tlsDir '127.0.0.1.pem'
$pfxPassword = 'nr2-local'

if (-not (Test-Path $pfxPath)) {
    Write-Host 'No NR2 localhost PFX found — run setup_localhost_tls.ps1 first.' -ForegroundColor Yellow
    exit 0
}

$securePwd = ConvertTo-SecureString -String $pfxPassword -Force -AsPlainText
$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2
$cert.Import($pfxPath, $pfxPassword, [System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::Exportable)
$thumbprint = $cert.Thumbprint

$rootStore = New-Object System.Security.Cryptography.X509Certificates.X509Store('Root', 'CurrentUser')
$rootStore.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
try {
    $existing = $rootStore.Certificates.Find(
        [System.Security.Cryptography.X509Certificates.X509FindType]::FindByThumbprint,
        $thumbprint,
        $false
    )
    if ($existing.Count -gt 0) {
        Write-Host "NR2 localhost cert already trusted (thumbprint $thumbprint)."
        exit 0
    }
    $rootStore.Add($cert)
    Write-Host "Trusted NR2 localhost cert in CurrentUser\Root (thumbprint $thumbprint)." -ForegroundColor Green
    Write-Host 'Chrome should now load https://127.0.0.1:8765/ without certificate warnings.' -ForegroundColor Cyan
} finally {
    $rootStore.Close()
}

if (-not (Test-Path $certPath)) {
    Write-Host "Certificate PEM missing at $certPath (PFX trust is sufficient for the browser)."
}
