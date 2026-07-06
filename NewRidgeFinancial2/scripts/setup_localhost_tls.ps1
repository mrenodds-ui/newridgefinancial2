# Optional localhost TLS for NR2 (Moonshot Sprint 3)
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$tlsDir = Join-Path $repoRoot "app_data\nr2\tls"
New-Item -ItemType Directory -Force -Path $tlsDir | Out-Null

$certPath = Join-Path $tlsDir "127.0.0.1.pem"
$keyPath = Join-Path $tlsDir "127.0.0.1-key.pem"

if (Get-Command mkcert -ErrorAction SilentlyContinue) {
  Push-Location $tlsDir
  mkcert -install
  mkcert -cert-file $certPath -key-file $keyPath 127.0.0.1 localhost ::1
  Pop-Location
  Write-Host "TLS certs written via mkcert: $certPath"
} else {
  $cert = New-SelfSignedCertificate -DnsName "127.0.0.1","localhost" -CertStoreLocation "Cert:\CurrentUser\My" -FriendlyName "NR2 Localhost"
  $pwd = ConvertTo-SecureString -String "nr2-local" -Force -AsPlainText
  Export-PfxCertificate -Cert $cert -FilePath (Join-Path $tlsDir "127.0.0.1.pfx") -Password $pwd | Out-Null
  Write-Host "Self-signed PFX created. Set NR2_TLS_CERT / NR2_TLS_KEY after exporting PEM."
}

Write-Host "Set environment:"
Write-Host "  NR2_TLS_CERT=$certPath"
Write-Host "  NR2_TLS_KEY=$keyPath"
