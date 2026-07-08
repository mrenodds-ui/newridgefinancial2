"""NR2 SQLite backup — timestamped copies with rotation (Moonshot hal-10073)."""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nr2_sqlite_backup import backup_sqlite

DEFAULT_RETAIN = int(os.environ.get("NR2_SQLITE_BACKUP_RETAIN", "7"))


def backup_db(db_path: Path, *, retain: int = DEFAULT_RETAIN, include_cache: bool = True) -> dict[str, Any]:
    db_path = Path(db_path)
    result = backup_sqlite(db_path, retain=max(1, int(retain or DEFAULT_RETAIN)))
    if not result.get("ok"):
        return result
    cache_copy = None
    if include_cache:
        cache_dir = db_path.parent / "document_inbox"
        if cache_dir.is_dir():
            backup_dir = db_path.parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            dest = backup_dir / f"cache-{ts}"
            try:
                shutil.copytree(cache_dir, dest, dirs_exist_ok=True)
                cache_copy = str(dest)
            except OSError as exc:
                result["cacheWarning"] = str(exc)
    if cache_copy:
        result["cachePath"] = cache_copy
    return result


def run_scheduled_backup(store: Any) -> dict[str, Any]:
    db_path = Path(getattr(store, "db_path", store))
    return backup_db(db_path)
