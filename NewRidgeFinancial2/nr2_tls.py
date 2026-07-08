"""Localhost TLS — Moonshot must-fix: enforce HTTPS by default on NR2 browser app."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def tls_enforced() -> bool:
    if os.environ.get("NR2_ALLOW_HTTP", "").strip().lower() in ("1", "true", "yes"):
        return False
    return os.environ.get("NR2_ENFORCE_TLS", "1").strip().lower() in ("1", "true", "yes", "on")


def default_tls_paths(repo_root: Path) -> tuple[Path, Path]:
    tls_dir = repo_root / "app_data" / "nr2" / "tls"
    return tls_dir / "127.0.0.1.pem", tls_dir / "127.0.0.1-key.pem"


def ensure_tls_key_material(certfile: str | Path, keyfile: str | Path) -> tuple[str, str]:
    """Re-export PEM key if pywebview deleted it on a prior run."""
    cert_path = Path(certfile)
    key_path = Path(keyfile)
    if key_path.is_file() and cert_path.is_file():
        return str(cert_path), str(key_path)
    pfx_path = cert_path.parent / "127.0.0.1.pfx"
    if pfx_path.is_file():
        script = Path(__file__).resolve().parent / "scripts" / "export_pfx_to_pem.py"
        if script.is_file():
            import subprocess
            import sys

            subprocess.run([sys.executable, str(script)], check=True, timeout=60)
    if not key_path.is_file() or not cert_path.is_file():
        raise RuntimeError(f"TLS key material missing: cert={cert_path} key={key_path}")
    return str(cert_path), str(key_path)


def ensure_localhost_tls_certificates(repo_root: Path) -> tuple[str, str]:
    cert_path, key_path = default_tls_paths(repo_root)
    if cert_path.is_file() and key_path.is_file():
        return str(cert_path), str(key_path)

    cert_path.parent.mkdir(parents=True, exist_ok=True)
    openssl = _find_openssl()
    if not openssl:
        raise RuntimeError(
            "NR2_ENFORCE_TLS=1 requires TLS certificates. Install OpenSSL or run "
            "NewRidgeFinancial2/scripts/setup_localhost_tls.ps1"
        )

    cmd = [
        openssl,
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-keyout",
        str(key_path),
        "-out",
        str(cert_path),
        "-days",
        "825",
        "-nodes",
        "-subj",
        "/CN=127.0.0.1",
        "-addext",
        "subjectAltName=DNS:localhost,IP:127.0.0.1",
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
    except subprocess.CalledProcessError as exc:
        # Older OpenSSL without -addext
        cmd_fallback = [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
            "-days",
            "825",
            "-nodes",
            "-subj",
            "/CN=127.0.0.1",
        ]
        subprocess.run(cmd_fallback, check=True, capture_output=True, text=True, timeout=120)

    if not cert_path.is_file() or not key_path.is_file():
        raise RuntimeError("Failed to generate localhost TLS certificate files.")
    return str(cert_path), str(key_path)


def resolve_tls_certificates(repo_root: Path) -> tuple[str | None, str | None]:
    env_cert = os.environ.get("NR2_TLS_CERT", "").strip()
    env_key = os.environ.get("NR2_TLS_KEY", "").strip()
    if env_cert and env_key:
        return env_cert, env_key
    cert_path, key_path = default_tls_paths(repo_root)
    if cert_path.is_file() and key_path.is_file():
        return str(cert_path), str(key_path)
    if tls_enforced():
        return ensure_localhost_tls_certificates(repo_root)
    return None, None


def _find_openssl() -> str | None:
    for candidate in ("openssl", "openssl.exe"):
        try:
            subprocess.run([candidate, "version"], check=True, capture_output=True, timeout=10)
            return candidate
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
    return None


def require_tls_for_browser_app(repo_root: Path) -> tuple[str | None, str | None]:
    if not tls_enforced():
        return resolve_tls_certificates(repo_root)
    cert, key = resolve_tls_certificates(repo_root)
    if not cert or not key:
        print("FATAL: TLS enforced but certificate files are missing.", file=sys.stderr)
        raise SystemExit(1)
    return cert, key
