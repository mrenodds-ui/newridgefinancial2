#!/usr/bin/env python3
"""Export NR2 localhost PFX to PEM (fallback when OpenSSL/mkcert unavailable)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent
TLS_DIR = REPO_ROOT / "app_data" / "nr2" / "tls"
PFX_PATH = TLS_DIR / "127.0.0.1.pfx"
CERT_PATH = TLS_DIR / "127.0.0.1.pem"
KEY_PATH = TLS_DIR / "127.0.0.1-key.pem"
DEFAULT_PASSWORD = b"nr2-local"


def export_pfx_to_pem(
    *,
    pfx_path: Path = PFX_PATH,
    cert_path: Path = CERT_PATH,
    key_path: Path = KEY_PATH,
    password: bytes = DEFAULT_PASSWORD,
) -> tuple[str, str]:
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, pkcs12

    if not pfx_path.is_file():
        raise FileNotFoundError(f"PFX not found: {pfx_path}")
    key, cert, _ = pkcs12.load_key_and_certificates(pfx_path.read_bytes(), password)
    if key is None or cert is None:
        raise RuntimeError("PFX did not contain both private key and certificate.")
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    cert_path.write_bytes(cert.public_bytes(Encoding.PEM))
    key_path.write_bytes(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    return str(cert_path), str(key_path)


def main() -> int:
    try:
        cert, key = export_pfx_to_pem()
    except Exception as exc:
        print(f"export_pfx_to_pem failed: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {cert} and {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
