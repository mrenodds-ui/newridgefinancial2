"""Production must-fix startup checks — Moonshot program re-eval."""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path


LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def resolve_bind_host() -> str:
    host = os.environ.get("NR2_BIND_HOST", "127.0.0.1").strip() or "127.0.0.1"
    if host.lower() in LOOPBACK_HOSTS:
        return host
    if os.environ.get("NR2_ALLOW_LAN_BIND", "").strip().lower() in ("1", "true", "yes"):
        return host
    print(
        f"FATAL: NR2 must bind to loopback (127.0.0.1). Refusing bind host {host!r}. "
        "Set NR2_ALLOW_LAN_BIND=1 only with TLS and client auth.",
        file=sys.stderr,
    )
    raise SystemExit(1)


def require_loopback_bind_host(host: str) -> None:
    if host.lower() in LOOPBACK_HOSTS:
        return
    if os.environ.get("NR2_ALLOW_LAN_BIND", "").strip().lower() in ("1", "true", "yes"):
        return
    print(f"FATAL: Server attempted to bind to non-loopback host {host!r}.", file=sys.stderr)
    raise SystemExit(1)


def require_sqlcipher_available() -> None:
    from nr2_db_crypto import db_encryption_enabled

    if not db_encryption_enabled():
        print(
            "FATAL: NR2 requires SQLCipher (NR2_DB_ENCRYPTION=1 by default). "
            "Install: pip install pysqlcipher3 keyring",
            file=sys.stderr,
        )
        raise SystemExit(1)
    try:
        from pysqlcipher3 import dbapi2 as _sqlcipher  # type: ignore  # noqa: F401
    except ImportError:
        try:
            import sqlcipher3 as _sqlcipher  # type: ignore  # noqa: F401
        except ImportError:
            print(
                "FATAL: pysqlcipher3 or sqlcipher3 required. pip install pysqlcipher3 keyring",
                file=sys.stderr,
            )
            raise SystemExit(1) from None


def _is_plaintext_sqlite(db_path: Path) -> bool:
    if not db_path.is_file():
        return False
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("SELECT name FROM sqlite_master LIMIT 1")
        conn.close()
        return True
    except sqlite3.DatabaseError:
        return False


def ensure_encrypted_database(db_path: Path) -> dict:
    """Create or migrate DB to SQLCipher at db_path."""
    from nr2_db_crypto import _sqlcipher_connect, db_encryption_enabled, get_master_key

    if not db_encryption_enabled():
        return {"ok": False, "error": "encryption_disabled"}

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.is_file():
        conn = _sqlcipher_connect(db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()
        return {"ok": True, "created": True, "path": str(db_path)}

    if not _is_plaintext_sqlite(db_path):
        conn = _sqlcipher_connect(db_path)
        conn.execute("SELECT 1")
        conn.close()
        return {"ok": True, "encrypted": True, "path": str(db_path)}

    backup = db_path.with_suffix(db_path.suffix + ".pre-crypto-bak")
    tmp = db_path.with_suffix(db_path.suffix + ".enc-migrating")
    import shutil

    shutil.copy2(db_path, backup)
    if tmp.is_file():
        tmp.unlink()
    try:
        src = sqlite3.connect(str(db_path))
        dst = _sqlcipher_connect(tmp)
        src.backup(dst)
        src.close()
        dst.close()
        plain_count = sqlite3.connect(str(db_path)).execute("SELECT COUNT(*) FROM app_state").fetchone()[0]
        enc_count = _sqlcipher_connect(tmp).execute("SELECT COUNT(*) FROM app_state").fetchone()[0]
        if plain_count != enc_count:
            tmp.unlink(missing_ok=True)
            return {"ok": False, "error": "row_count_mismatch"}
        db_path.unlink()
        tmp.replace(db_path)
        _ = get_master_key()
        return {"ok": True, "migrated": True, "backup": str(backup), "path": str(db_path)}
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        return {"ok": False, "error": str(exc)}


def run_browser_production_checks(repo_root: Path, data_dir: Path) -> dict:
    require_sqlcipher_available()
    db_result = ensure_encrypted_database(data_dir / "nr2.sqlite3")
    if not db_result.get("ok"):
        print(f"FATAL: Database encryption setup failed: {db_result}", file=sys.stderr)
        raise SystemExit(1)
    bind_host = resolve_bind_host()
    from nr2_tls import require_tls_for_browser_app

    cert, key = require_tls_for_browser_app(repo_root)
    return {"bindHost": bind_host, "tlsCert": cert, "tlsKey": key, "database": db_result}
