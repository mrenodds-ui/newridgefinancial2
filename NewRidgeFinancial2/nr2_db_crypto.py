"""SQLCipher key management — Moonshot Sprint 1 (keyring + optional encryption)."""

from __future__ import annotations

import logging
import os
import secrets
import shutil
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "NewRidgeFinancial2"
KEYRING_USER = "nr2_db_key"


def db_encryption_enabled() -> bool:
    return os.environ.get("NR2_DB_ENCRYPTION", "1").strip().lower() in ("1", "true", "yes", "on")


def get_master_key() -> str:
    try:
        import keyring

        key = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
        if key:
            return str(key)
        key = secrets.token_urlsafe(32)
        keyring.set_password(KEYRING_SERVICE, KEYRING_USER, key)
        return key
    except Exception as exc:
        logger.warning("keyring unavailable (%s); using env NR2_DB_KEY fallback", exc)
        fallback = os.environ.get("NR2_DB_KEY", "").strip()
        if fallback:
            return fallback
        key = secrets.token_urlsafe(32)
        os.environ["NR2_DB_KEY"] = key
        return key


def sqlcipher_module():
    """Return (module, backend_name) for SQLCipher or (None, None)."""
    try:
        from pysqlcipher3 import dbapi2 as sqlcipher  # type: ignore

        return sqlcipher, "pysqlcipher3"
    except ImportError:
        try:
            import sqlcipher3 as sqlcipher  # type: ignore

            return sqlcipher, "sqlcipher3"
        except ImportError:
            return None, None


def sqlcipher_available() -> bool:
    mod, _ = sqlcipher_module()
    return mod is not None


def _sqlcipher_connect(db_path: Path):
    sqlcipher, backend = sqlcipher_module()
    if sqlcipher is None:
        raise RuntimeError(
            "NR2_DB_ENCRYPTION=1 requires pysqlcipher3 or sqlcipher3. "
            "Install with: pip install sqlcipher3 keyring"
        )
    conn = sqlcipher.connect(str(db_path))
    key = get_master_key().replace("'", "''")
    conn.execute(f"PRAGMA key = '{key}'")
    return conn


def open_encrypted_db(db_path: Path) -> sqlite3.Connection:
    if db_encryption_enabled():
        return _sqlcipher_connect(db_path)
    return sqlite3.connect(str(db_path))


def migrate_plaintext_to_encrypted(plain_path: Path, enc_path: Path) -> dict:
    """Atomic plaintext → SQLCipher copy with row-count verification."""
    if not plain_path.is_file():
        return {"ok": False, "error": "plaintext_missing"}
    if enc_path.is_file():
        return {"ok": True, "skipped": "encrypted_exists"}
    if not db_encryption_enabled():
        return {"ok": False, "error": "encryption_disabled"}

    backup = plain_path.with_suffix(plain_path.suffix + ".pre-crypto-bak")
    shutil.copy2(plain_path, backup)
    tmp = enc_path.with_suffix(enc_path.suffix + ".tmp")
    if tmp.is_file():
        tmp.unlink()

    try:
        src = sqlite3.connect(str(plain_path))
        dst = _sqlcipher_connect(tmp)
        src.backup(dst)
        src.close()
        dst.close()

        verify_plain = sqlite3.connect(str(plain_path))
        plain_count = verify_plain.execute("SELECT COUNT(*) FROM app_state").fetchone()[0]
        verify_plain.close()

        verify_enc = _sqlcipher_connect(tmp)
        enc_count = verify_enc.execute("SELECT COUNT(*) FROM app_state").fetchone()[0]
        verify_enc.close()

        if plain_count != enc_count:
            tmp.unlink(missing_ok=True)
            return {"ok": False, "error": "row_count_mismatch", "plain": plain_count, "enc": enc_count}

        tmp.replace(enc_path)
        return {"ok": True, "path": str(enc_path), "backup": str(backup)}
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        return {"ok": False, "error": str(exc)}
