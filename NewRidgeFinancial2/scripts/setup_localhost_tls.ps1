# Optional localhost TLS for NR2 (Moonshot must-fix - auto-run on first StartProgram if missing)
$ErrorActionPreference = "Stop"

function Export-Nr2PemFromPfx {
  param(
    [string]$PfxPath,
    [string]$Password,
    [string]$CertPath,
    [string]$KeyPath
  )
  $py = Get-Command py -ErrorAction SilentlyContinue
  if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
  if ($py) {
    & $py.Source (Join-Path $PSScriptRoot "export_pfx_to_pem.py")
    return
  }
  throw "PEM export requires Python (cryptography) or OpenSSL."
}

$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$tlsDir = Join-Path $repoRoot "app_data\nr2\tls"
New-Item -ItemType Directory -Force -Path $tlsDir | Out-Null

$certPath = Join-Path $tlsDir "127.0.0.1.pem"
$keyPath = Join-Path $tlsDir "127.0.0.1-key.pem"
$pfxPath = Join-Path $tlsDir "127.0.0.1.pfx"
$pfxPassword = "nr2-local"

if ((Test-Path $certPath) -and (Test-Path $keyPath)) {
  Write-Host "TLS certs already present: $certPath"
  exit 0
}

if ((Test-Path $pfxPath) -and -not ((Test-Path $certPath) -and (Test-Path $keyPath))) {
  $py = Get-Command py -ErrorAction SilentlyContinue
  if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
  if ($py) {
    & $py.Source (Join-Path $PSScriptRoot "export_pfx_to_pem.py")
    Write-Host "TLS PEM exported from existing PFX via Python: $certPath"
    exit 0
  }
  throw "Existing PFX found but PEM missing. Install Python or OpenSSL to export."
}

if (Get-Command mkcert -ErrorAction SilentlyContinue) {
  Push-Location $tlsDir
  mkcert -install
  mkcert -cert-file $certPath -key-file $keyPath 127.0.0.1 localhost ::1
  Pop-Location
  Write-Host "TLS certs written via mkcert: $certPath"
} elseif (Get-Command openssl -ErrorAction SilentlyContinue) {
  & openssl req -x509 -newkey rsa:2048 -keyout $keyPath -out $certPath -days 825 -nodes -subj "/CN=NR2 Localhost" -addext "subjectAltName=DNS:localhost,DNS:127.0.0.1,IP:127.0.0.1,IP:0:0:0:0:0:0:0:1"
  Write-Host "TLS certs written via openssl: $certPath"
} else {
  $cert = New-SelfSignedCertificate `
    -Subject "CN=NR2 Localhost" `
    -FriendlyName "NR2 Localhost" `
    -KeyAlgorithm RSA -KeyLength 2048 `
    -HashAlgorithm SHA256 `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -KeyExportPolicy Exportable `
    -NotAfter (Get-Date).AddDays(825) `
    -TextExtension @(
      "2.5.29.37={text}1.3.6.1.5.5.7.3.1",
      "2.5.29.17={text}IPAddress=127.0.0.1&IPAddress=::1&DNS=localhost&DNS=127.0.0.1"
    )
  $pwd = ConvertTo-SecureString -String $pfxPassword -Force -AsPlainText
  Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $pwd | Out-Null
  if (Get-Command openssl -ErrorAction SilentlyContinue) {
    & openssl pkcs12 -in $pfxPath -out $certPath -clcerts -nokeys -passin pass:$pfxPassword
    & openssl pkcs12 -in $pfxPath -out $keyPath -nocerts -nodes -passin pass:$pfxPassword
    Write-Host "TLS PEM exported from PFX: $certPath"
  } else {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
    if ($py) {
      & $py.Source (Join-Path $PSScriptRoot "export_pfx_to_pem.py")
      if ((Test-Path $certPath) -and (Test-Path $keyPath)) {
        Write-Host "TLS PEM exported from PFX via Python: $certPath"
      } else {
        throw "Python PFX export did not produce PEM files."
      }
    } else {
      throw "Cannot export PEM from PFX. Install Python+cryptography, OpenSSL, or mkcert."
    }
  }
}

Write-Host "NR2 uses HTTPS by default (NR2_ENFORCE_TLS=1)."
Write-Host "Trusting localhost certificate for Chrome/Edge..."
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
& (Join-Path $repoRoot "scripts\trust_localhost_tls.ps1")
Write-Host "Optional overrides:"
Write-Host "  NR2_TLS_CERT=$certPath"
Write-Host "  NR2_TLS_KEY=$keyPath"
Write-Host "  NR2_ALLOW_HTTP=1  (dev only - not for production)"
