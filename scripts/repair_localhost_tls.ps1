# Regenerate NR2 localhost TLS with IP SAN (Chrome requires IP:127.0.0.1 for https://127.0.0.1/).
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$tlsDir = Join-Path $repoRoot 'app_data\nr2\tls'
$pfxPath = Join-Path $tlsDir '127.0.0.1.pfx'
$certPath = Join-Path $tlsDir '127.0.0.1.pem'
$keyPath = Join-Path $tlsDir '127.0.0.1-key.pem'
$pfxPassword = 'nr2-local'
$stamp = Get-Date -Format 'yyyyMMddTHHmmss'

New-Item -ItemType Directory -Force -Path $tlsDir | Out-Null

function Backup-TlsFile {
    param([string]$Path)
    if (Test-Path $Path) {
        Copy-Item $Path "$Path.bak-$stamp" -Force
        Remove-Item $Path -Force
    }
}

function Remove-TrustedCertByThumbprint {
    param([string]$Thumbprint)
    if (-not $Thumbprint) { return }
    $rootStore = New-Object System.Security.Cryptography.X509Certificates.X509Store('Root', 'CurrentUser')
    $rootStore.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
    try {
        $existing = $rootStore.Certificates.Find(
            [System.Security.Cryptography.X509Certificates.X509FindType]::FindByThumbprint,
            $Thumbprint,
            $false
        )
        foreach ($c in $existing) {
            $rootStore.Remove($c)
            Write-Host "Removed old trusted cert $Thumbprint from CurrentUser\Root." -ForegroundColor Yellow
        }
    } finally {
        $rootStore.Close()
    }
}

$oldThumb = $null
if (Test-Path $pfxPath) {
    try {
        $securePwd = ConvertTo-SecureString -String $pfxPassword -Force -AsPlainText
        $oldCert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2
        $oldCert.Import($pfxPath, $pfxPassword, [System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::Exportable)
        $oldThumb = $oldCert.Thumbprint
    } catch {}
}

Backup-TlsFile $pfxPath
Backup-TlsFile $certPath
Backup-TlsFile $keyPath
Remove-TrustedCertByThumbprint $oldThumb

$openssl = Get-Command openssl -ErrorAction SilentlyContinue
if ($openssl) {
    Write-Host 'Generating TLS cert with OpenSSL (IP + DNS SAN)...' -ForegroundColor Cyan
    & $openssl.Source req -x509 -newkey rsa:2048 -keyout $keyPath -out $certPath -days 825 -nodes `
        -subj '/CN=NR2 Localhost' `
        -addext 'subjectAltName=DNS:localhost,DNS:127.0.0.1,IP:127.0.0.1,IP:0:0:0:0:0:0:0:1'
    if ($LASTEXITCODE -ne 0) {
        throw 'OpenSSL certificate generation failed.'
    }
    $securePwd = ConvertTo-SecureString -String $pfxPassword -Force -AsPlainText
    $tempCert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($certPath)
    Export-PfxCertificate -Cert $tempCert -FilePath $pfxPath -Password $securePwd | Out-Null
} else {
    Write-Host 'Generating TLS cert with PowerShell (IP + DNS SAN)...' -ForegroundColor Cyan
    $cert = New-SelfSignedCertificate `
        -Subject 'CN=NR2 Localhost' `
        -FriendlyName 'NR2 Localhost' `
        -KeyAlgorithm RSA -KeyLength 2048 `
        -HashAlgorithm SHA256 `
        -CertStoreLocation 'Cert:\CurrentUser\My' `
        -KeyExportPolicy Exportable `
        -NotAfter (Get-Date).AddDays(825) `
        -TextExtension @(
            '2.5.29.37={text}1.3.6.1.5.5.7.3.1',
            '2.5.29.17={text}IPAddress=127.0.0.1&IPAddress=::1&DNS=localhost&DNS=127.0.0.1'
        )
    $securePwd = ConvertTo-SecureString -String $pfxPassword -Force -AsPlainText
    Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $securePwd | Out-Null
    $exportScript = Join-Path $repoRoot 'NewRidgeFinancial2\scripts\export_pfx_to_pem.py'
    $python = Get-Command py -ErrorAction SilentlyContinue
    if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
    if (-not $python) { throw 'Python required to export PEM from PFX.' }
    & $python.Source $exportScript
    if ($LASTEXITCODE -ne 0) { throw 'PEM export failed.' }
}

if (-not ((Test-Path $certPath) -and (Test-Path $keyPath))) {
    throw "TLS repair did not produce $certPath and $keyPath"
}

& (Join-Path $repoRoot 'scripts\trust_localhost_tls.ps1')

$newCert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($pfxPath, $pfxPassword)
Write-Host "New cert thumbprint: $($newCert.Thumbprint)" -ForegroundColor Green
$newCert.Extensions | Where-Object { $_.Oid.FriendlyName -eq 'Subject Alternative Name' } | ForEach-Object {
    Write-Host "SAN: $($_.Format($false))"
}
Write-Host 'TLS repair complete. Restart NR2 (StartProgram.bat) then open https://127.0.0.1:8765/ or https://localhost:8765/' -ForegroundColor Cyan
