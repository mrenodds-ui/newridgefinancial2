# Optional localhost TLS for NR2 (Moonshot must-fix — auto-run on first StartProgram if missing)
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$tlsDir = Join-Path $repoRoot "app_data\nr2\tls"
New-Item -ItemType Directory -Force -Path $tlsDir | Out-Null

$certPath = Join-Path $tlsDir "127.0.0.1.pem"
$keyPath = Join-Path $tlsDir "127.0.0.1-key.pem"

if ($certPath -and (Test-Path $certPath) -and (Test-Path $keyPath)) {
  Write-Host "TLS certs already present: $certPath"
  exit 0
}

if (Get-Command mkcert -ErrorAction SilentlyContinue) {
  Push-Location $tlsDir
  mkcert -install
  mkcert -cert-file $certPath -key-file $keyPath 127.0.0.1 localhost ::1
  Pop-Location
  Write-Host "TLS certs written via mkcert: $certPath"
} elseif (Get-Command openssl -ErrorAction SilentlyContinue) {
  & openssl req -x509 -newkey rsa:2048 -keyout $keyPath -out $certPath -days 825 -nodes -subj "/CN=127.0.0.1"
  Write-Host "TLS certs written via openssl: $certPath"
} else {
  $cert = New-SelfSignedCertificate -DnsName "127.0.0.1","localhost","::1" -CertStoreLocation "Cert:\CurrentUser\My" -FriendlyName "NR2 Localhost" -KeyExportPolicy Exportable
  $pwd = ConvertTo-SecureString -String "nr2-local" -Force -AsPlainText
  $pfxPath = Join-Path $tlsDir "127.0.0.1.pfx"
  Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $pwd | Out-Null
  if (Get-Command openssl -ErrorAction SilentlyContinue) {
    & openssl pkcs12 -in $pfxPath -out $certPath -clcerts -nokeys -passin pass:nr2-local
    & openssl pkcs12 -in $pfxPath -out $keyPath -nocerts -nodes -passin pass:nr2-local
    Write-Host "TLS PEM exported from PFX: $certPath"
  } else {
    Write-Host "PFX created at $pfxPath — install OpenSSL or mkcert to export PEM, or let browser_app auto-generate on start."
  }
}

Write-Host "NR2 uses HTTPS by default (NR2_ENFORCE_TLS=1)."
Write-Host "Optional overrides:"
Write-Host "  NR2_TLS_CERT=$certPath"
Write-Host "  NR2_TLS_KEY=$keyPath"
Write-Host "  NR2_ALLOW_HTTP=1  (dev only — not for production)"
