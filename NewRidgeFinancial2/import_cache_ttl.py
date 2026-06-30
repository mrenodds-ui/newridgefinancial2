"""Ephemeral import cache — relevant periods only, auto-purge after retention window.

Imported SoftDent / QuickBooks files are replaced each sync (never accumulated).
After NR2_IMPORT_RETENTION_DAYS (default 7) the cache is cleared so stale
multi-period totals cannot keep stacking in widgets.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from import_loader import quickbooks_import_dir, softdent_import_dir

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_NAME = "import_cache_manifest.json"


def retention_days() -> int:
    raw = os.environ.get("NR2_IMPORT_RETENTION_DAYS", "7").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 7


def manifest_path() -> Path:
    return softdent_import_dir().parent / MANIFEST_NAME


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def load_manifest() -> dict[str, Any] | None:
    path = manifest_path()
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def manifest_expired(manifest: dict[str, Any] | None) -> bool:
    if not manifest:
        return False
    expires = _parse_iso(str(manifest.get("expiresAt") or ""))
    if expires is None:
        return False
    return _utc_now() >= expires


def _import_dirs() -> list[Path]:
    return [softdent_import_dir(), quickbooks_import_dir()]


def _ocr_archive_dirs() -> list[Path]:
    """Retention-managed OCR archive folders that can feed document previews."""
    dirs: list[Path] = []
    nr2_processed = REPO_ROOT / "app_data" / "nr2" / "document_inbox" / "processed"
    legacy_processed = REPO_ROOT / "local_accounting_inbox" / "processed"
    for candidate in (nr2_processed, legacy_processed):
        if candidate not in dirs:
            dirs.append(candidate)
    configured = os.environ.get("NR2_DOCUMENT_INBOX_ARCHIVE", "").strip()
    if configured:
        archive = Path(configured).expanduser()
        if not archive.is_absolute():
            archive = REPO_ROOT / archive
        archive = archive.resolve()
        if archive not in dirs:
            dirs.append(archive)
    return dirs


def purge_expired_ocr_files(reference: datetime | None = None) -> list[str]:
    """Delete OCR archive files older than the retention window (by mtime)."""
    now = reference or _utc_now()
    cutoff = now - timedelta(days=retention_days())
    removed: list[str] = []
    for directory in _ocr_archive_dirs():
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if not path.is_file():
                continue
            if path.name.startswith("."):
                continue
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            except OSError:
                continue
            if modified >= cutoff:
                continue
            path.unlink(missing_ok=True)
            removed.append(path.name)
    return removed


def purge_import_cache() -> list[str]:
    removed: list[str] = []
    for directory in _import_dirs():
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if not path.is_file():
                continue
            if path.name.startswith("."):
                continue
            path.unlink(missing_ok=True)
            removed.append(path.name)
    manifest = manifest_path()
    if manifest.is_file():
        manifest.unlink(missing_ok=True)
        removed.append(MANIFEST_NAME)
    return removed


def purge_if_expired() -> dict[str, Any]:
    manifest = load_manifest()
    if not manifest_expired(manifest):
        return {"purged": False, "removed": [], "reason": "cache-current"}
    removed = purge_import_cache()
    return {"purged": True, "removed": removed, "reason": "retention-expired"}


def write_manifest(
    *,
    synced_at: str,
    periods: dict[str, list[str]],
    purge_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started = _parse_iso(synced_at) or _utc_now()
    expires = started + timedelta(days=retention_days())
    payload: dict[str, Any] = {
        "syncedAt": started.isoformat(),
        "expiresAt": expires.isoformat(),
        "retentionDays": retention_days(),
        "periods": periods,
        "policy": "relevant-periods-only",
    }
    if purge_result:
        payload["lastPurge"] = purge_result
    path = manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def relevant_period_labels(reference: datetime | None = None) -> list[str]:
    """Current calendar month and prior calendar month (YYYY-MM)."""
    now = reference or _utc_now()
    current = now.strftime("%Y-%m")
    year = now.year
    month = now.month - 1
    if month == 0:
        month = 12
        year -= 1
    prior = f"{year:04d}-{month:02d}"
    return [current, prior]


def _period_key(value: str | None) -> str:
    raw = str(value or "").strip()
    return raw[:7] if len(raw) >= 7 else raw


def _round_money(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def enforce_quickbooks_period_files(destination: Path) -> list[str]:
    """Keep only current + prior month rows in QuickBooks import CSVs."""
    import csv

    allowed = set(relevant_period_labels())
    touched: list[str] = []
    specs = {
        "quickbooks_revenue.csv": ["Period", "TotalIncome"],
        "quickbooks_expenses.csv": ["Period", "TotalExpense"],
        "quickbooks_profit_and_loss.csv": ["Period", "TotalIncome", "TotalExpense", "NetIncome"],
    }
    for filename, fieldnames in specs.items():
        path = destination / filename
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        trimmed = [row for row in rows if _period_key(row.get("Period") or row.get("period")) in allowed]
        if not trimmed:
            continue
        cleaned_rows: list[dict[str, Any]] = []
        for row in trimmed:
            cleaned: dict[str, Any] = {}
            for key in fieldnames:
                value = row.get(key, "")
                if key in ("NetIncome", "TotalIncome", "TotalExpense"):
                    rounded = _round_money(value)
                    value = rounded if rounded is not None else value
                cleaned[key] = value
            cleaned_rows.append(cleaned)
        unchanged = len(cleaned_rows) == len(rows) and all(
            all(str(cleaned_rows[i].get(key, "")) == str(rows[i].get(key, "")) for key in fieldnames)
            for i in range(len(cleaned_rows))
        )
        if unchanged:
            continue
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for cleaned in cleaned_rows:
                writer.writerow(cleaned)
        touched.append(filename)
    return touched
