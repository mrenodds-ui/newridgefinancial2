"""Ephemeral import cache — relevant periods only, auto-purge after retention window.

Imported SoftDent / QuickBooks files are replaced each sync (never accumulated).
After NR2_IMPORT_RETENTION_DAYS (default 7) the cache is cleared so stale
multi-period totals cannot keep stacking in widgets.

Moonshot inbox coherence: never wipe SoftDent AR/dashboard (or QB expenses) when
those critical files are present; prefer content-hash no-op writes for no-op syncs.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from import_loader import quickbooks_import_dir, softdent_import_dir

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_NAME = "import_cache_manifest.json"

# Protected from retention empty-wipes (Moonshot inbox sync coherence).
CRITICAL_INBOX_FILENAMES: frozenset[str] = frozenset(
    {
        "softdent_ar_aging.csv",
        "softdent_ar_aging.json",
        "softdent_accounts_receivable.csv",
        "softdent_dashboard_data.json",
        "softdent_dashboard_export.json",
        "quickbooks_expenses.csv",
        "quickbooks_expenses.json",
        "quickbooks_expense_detail.csv",
    }
)


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


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_bytes_if_changed(path: Path, data: bytes) -> bool:
    """Write only when content differs. Returns True if the file was mutated."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        try:
            if path.read_bytes() == data:
                return False
        except OSError:
            pass
    path.write_bytes(data)
    return True


def write_text_if_changed(path: Path, text: str, *, encoding: str = "utf-8") -> bool:
    return write_bytes_if_changed(path, text.encode(encoding))


def critical_inbox_files_present() -> dict[str, bool]:
    softdent = softdent_import_dir()
    qb = quickbooks_import_dir()
    return {
        "softdent.ar": any(
            (softdent / name).is_file() and (softdent / name).stat().st_size > 10
            for name in ("softdent_ar_aging.csv", "softdent_ar_aging.json", "softdent_accounts_receivable.csv")
        ),
        "softdent.dashboard": any(
            (softdent / name).is_file() and (softdent / name).stat().st_size > 10
            for name in ("softdent_dashboard_data.json", "softdent_dashboard_export.json")
        ),
        "quickbooks.expenses": any(
            (qb / name).is_file() and (qb / name).stat().st_size > 10
            for name in ("quickbooks_expenses.csv", "quickbooks_expenses.json", "quickbooks_expense_detail.csv")
        ),
    }


def has_usable_critical_inbox() -> bool:
    present = critical_inbox_files_present()
    return bool(present.get("softdent.ar") and present.get("softdent.dashboard"))


def collect_dataset_checksums(softdent_dir: Path, quickbooks_dir: Path) -> dict[str, dict[str, str]]:
    """SHA256 fingerprints for the newest on-disk file per import contract dataset."""
    from import_contract import _FALLBACK_DATASET_NAMES
    from import_loader import _newest_existing

    system_dirs = {"softdent": softdent_dir, "quickbooks": quickbooks_dir}
    checksums: dict[str, dict[str, str]] = {}
    for dataset_key, names in _FALLBACK_DATASET_NAMES.items():
        system = dataset_key.split(".", 1)[0]
        directory = system_dirs.get(system)
        if directory is None:
            continue
        path = _newest_existing(directory, names)
        if path is None:
            continue
        file_sha = sha256_file(path)
        if not file_sha:
            continue
        checksums[dataset_key] = {
            "sourceFile": path.name,
            "sha256": file_sha,
            "modifiedAt": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        }
    return checksums


def _ocr_archive_dirs() -> list[Path]:
    """Retention-managed OCR archive folders that can feed document previews."""
    dirs: list[Path] = []
    nr2_processed = REPO_ROOT / "app_data" / "nr2" / "document_inbox" / "processed"
    legacy_processed = REPO_ROOT / "local_accounting_inbox" / "processed"
    legacy_imports_processed = REPO_ROOT / "app" / "data" / "imports" / "processed"
    for candidate in (nr2_processed, legacy_processed, legacy_imports_processed):
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


def purge_import_cache(*, preserve_criticals: bool = True) -> list[str]:
    """Clear SoftDent/QB inbox files.

    Default preserves AR / dashboard / QB expenses so retention cannot empty-wipe
    money-critical datasets (Moonshot inbox sync coherence).
    """
    removed: list[str] = []
    for directory in _import_dirs():
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if not path.is_file():
                continue
            if path.name.startswith("."):
                continue
            if preserve_criticals and path.name in CRITICAL_INBOX_FILENAMES:
                continue
            path.unlink(missing_ok=True)
            removed.append(path.name)
    manifest = manifest_path()
    if manifest.is_file():
        manifest.unlink(missing_ok=True)
        removed.append(MANIFEST_NAME)
    return removed


def purge_if_expired() -> dict[str, Any]:
    """Retention purge with soft-skip when SoftDent critical inbox files exist."""
    manifest = load_manifest()
    if not manifest_expired(manifest):
        return {"purged": False, "removed": [], "reason": "cache-current"}
    if has_usable_critical_inbox():
        return {
            "purged": False,
            "removed": [],
            "reason": "retention-soft-skip-criticals-present",
            "criticals": critical_inbox_files_present(),
        }
    removed = purge_import_cache(preserve_criticals=True)
    return {"purged": bool(removed), "removed": removed, "reason": "retention-expired"}


def write_manifest(
    *,
    synced_at: str,
    periods: dict[str, list[str]],
    purge_result: dict[str, Any] | None = None,
    dataset_checksums: dict[str, dict[str, str]] | None = None,
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
    if dataset_checksums:
        payload["datasetChecksums"] = dataset_checksums
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
