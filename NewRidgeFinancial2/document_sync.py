"""Sync OCR-processed accounting documents into the NR2 document intake queue.

Reads the local accounting SQLite ledger (OCR inbox output) and merges records
into ``nr2:v2:documents`` so the Documents page and HAL widgets reflect automated
intake — not a separate C: drive ledger the UI never reads.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
NR2_DATA_DIR = REPO_ROOT / "app_data" / "nr2"
DOCUMENTS_KEY = "nr2:v2:documents"

FINANCIAL_DOC_TYPES = frozenset({"Statement", "Production Summary", "A/R Aging"})
FINANCIAL_SOURCE_KINDS = frozenset({"monthlyExpenses", "monthlyRevenue", "arAging", "dashboard"})


def hal_financial_numbers_only() -> bool:
    """When true, HAL syncs aggregate financial rows only — not OCR invoices or bill line items."""
    raw = os.environ.get("NR2_HAL_FINANCIAL_NUMBERS_ONLY", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def is_financial_summary_document(doc: dict[str, Any]) -> bool:
    kind = str(doc.get("sourceKind") or "").strip()
    if kind in FINANCIAL_SOURCE_KINDS:
        return True
    doc_type = str(doc.get("type") or "").strip()
    return doc_type in FINANCIAL_DOC_TYPES


def _env_path(name: str, default: Path | None = None) -> Path | None:
    configured = os.environ.get(name, "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        return candidate.resolve()
    return default.resolve() if default else None


def resolve_inbox_path() -> Path:
    return _env_path("NR2_DOCUMENT_INBOX", NR2_DATA_DIR / "document_inbox") or (NR2_DATA_DIR / "document_inbox")


def resolve_archive_path() -> Path:
    configured = os.environ.get("NR2_DOCUMENT_INBOX_ARCHIVE", "").strip()
    if configured:
        return _env_path("NR2_DOCUMENT_INBOX_ARCHIVE") or (resolve_inbox_path() / "processed")
    return resolve_inbox_path() / "processed"


def _preferred_accounting_db_path() -> Path:
    return NR2_DATA_DIR / "accounting_documents.sqlite3"


def _migrate_legacy_accounting_db_if_needed() -> Path | None:
    """Copy hal_local.sqlite3 into NR2 app data once so OCR ledger lives under app_data/nr2."""
    preferred = _preferred_accounting_db_path()
    if preferred.is_file():
        return preferred
    legacy = REPO_ROOT / "hal_local.sqlite3"
    if not legacy.is_file():
        return None
    preferred.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy, preferred)
    return preferred


def accounting_db_candidates() -> list[Path]:
    candidates: list[Path] = []
    for candidate in (
        _env_path("LOCAL_AI_ACCOUNTING_DB_PATH"),
        _env_path("HAL_SQLITE_PATH"),
        _migrate_legacy_accounting_db_if_needed(),
        _preferred_accounting_db_path(),
        REPO_ROOT / "hal_local.sqlite3",
    ):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def resolve_accounting_db_path() -> Path | None:
    for candidate in accounting_db_candidates():
        if candidate.is_file():
            return candidate
    return None


def _format_money(amount: float | int | None) -> str:
    if amount is None:
        return "—"
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return "—"
    return f"${value:,.2f}"


def _normalize_date(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return datetime.now(timezone.utc).date().isoformat()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return raw


def _document_type_label(value: str | None) -> str:
    mapping = {
        "invoice": "Invoice",
        "receipt": "Receipt",
        "bank_statement": "Statement",
        "financial_document": "Accounting Document",
    }
    key = str(value or "").strip().lower()
    return mapping.get(key, key.title() if key else "Accounting Document")


def _document_id(row: dict[str, Any]) -> str:
    invoice = str(row.get("invoice_number") or "").strip()
    if invoice:
        return re.sub(r"\s+", "-", invoice)[:48]
    sha = str(row.get("sha256") or "").strip()
    if sha:
        return f"DOC-{sha[:12].upper()}"
    source = str(row.get("source_name") or "document").strip()
    stem = Path(source).stem or "document"
    return re.sub(r"[^A-Za-z0-9_-]+", "-", stem)[:48] or "DOC-UNKNOWN"


def _age_days(date_value: str) -> int:
    try:
        parsed = datetime.fromisoformat(date_value).date()
    except ValueError:
        return 0
    delta = datetime.now(timezone.utc).date() - parsed
    return max(0, delta.days)


def _status_for_row(row: dict[str, Any]) -> str:
    if int(row.get("review_required") or 0):
        return "Pending Review"
    confidence = str(row.get("confidence_label") or "").strip().lower()
    if "manual" in confidence or "review" in confidence:
        return "Pending Review"
    return "Ready to Post"


def _status_tone(status: str) -> str:
    if status == "Posted":
        return "info"
    if status == "Ready to Post":
        return "ok"
    return "warn"


def _read_accounting_rows(db_path: Path) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='local_accounting_documents'"
        ).fetchone()
        if not table:
            return []
        columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(local_accounting_documents)").fetchall()
        }
        review_sql = "review_required" if "review_required" in columns else "0 AS review_required"
        confidence_sql = "confidence_label" if "confidence_label" in columns else "'' AS confidence_label"
        rows = connection.execute(
            f"""
            SELECT
                source_path,
                source_name,
                sha256,
                processed_at_utc,
                document_type,
                vendor_name,
                invoice_number,
                document_date,
                total_amount,
                text_preview,
                {review_sql},
                {confidence_sql}
            FROM local_accounting_documents
            ORDER BY processed_at_utc DESC, id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def _retention_days() -> int:
    raw = os.environ.get("NR2_IMPORT_RETENTION_DAYS", "7").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 7


def _is_within_retention(path: Path) -> bool:
    try:
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(days=_retention_days())
    return modified >= cutoff


def _live_archive_file(row: dict[str, Any], archive_dir: Path) -> str | None:
    """Return a current (within-retention) preview file name, else None."""
    source_name = str(row.get("source_name") or "").strip()
    if not source_name:
        return None
    search_dirs = [archive_dir]
    legacy_archive = REPO_ROOT / "local_accounting_inbox" / "processed"
    if legacy_archive not in search_dirs:
        search_dirs.append(legacy_archive)
    for folder in search_dirs:
        for candidate in (
            folder / source_name,
            folder / f"{Path(source_name).stem}.pdf",
            folder / f"{Path(source_name).stem}.txt",
        ):
            # Ignore retention-expired preview files so purged artifacts do not
            # silently reappear in document previews.
            if candidate.is_file() and _is_within_retention(candidate):
                return candidate.name
    return None


def _archive_file_for_row(row: dict[str, Any], archive_dir: Path) -> tuple[str, bool]:
    """Return (display file label, sourceExpired). Never pretend a purged file exists."""
    live = _live_archive_file(row, archive_dir)
    if live:
        return live, False
    source_name = str(row.get("source_name") or "").strip()
    if source_name:
        return "", True
    doc_id = _document_id(row)
    return f"{doc_id}.pdf", False


def _queue_entry_from_row(row: dict[str, Any], archive_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    doc_id = _document_id(row)
    status = _status_for_row(row)
    date = _normalize_date(str(row.get("document_date") or ""))
    vendor = str(row.get("vendor_name") or "Unassigned Vendor").strip() or "Unassigned Vendor"
    amount = _format_money(row.get("total_amount"))
    file_name, source_expired = _archive_file_for_row(row, archive_dir)
    text_preview = str(row.get("text_preview") or "").strip()
    doc = {
        "id": doc_id,
        "type": _document_type_label(row.get("document_type")),
        "vendor": vendor,
        "date": date,
        "amount": amount,
        "status": status,
        "statusTone": _status_tone(status),
        "age": _age_days(date),
        "autoImported": True,
        "sourceSha": str(row.get("sha256") or ""),
        "sourceName": str(row.get("source_name") or ""),
        "previewAvailable": not source_expired and bool(file_name),
        "sourceExpired": source_expired,
    }
    preview = {
        "vendor": vendor.upper(),
        "invoice": doc_id,
        "date": date,
        "total": amount,
        "file": file_name,
        "pages": "1 of 1",
        "uploaded": _normalize_date(str(row.get("processed_at_utc") or "")[:10]),
        "textPreview": text_preview,
        "sourceExpired": source_expired,
        "fileUnavailable": (
            "Source file expired after retention window — extracted fields shown below."
            if source_expired
            else None
        ),
        "previewAvailable": not source_expired and bool(file_name),
    }
    return doc, preview


def _recompute_period(queue: list[dict[str, Any]]) -> dict[str, Any]:
    total = 0.0
    posted = 0.0
    pending = 0.0
    for doc in queue:
        raw = str(doc.get("amount") or "").replace("$", "").replace(",", "").strip()
        try:
            value = float(raw)
        except ValueError:
            value = 0.0
        total += value
        status = str(doc.get("status") or "")
        if status == "Posted":
            posted += value
        elif status == "Pending Review":
            pending += value
    ready = sum(1 for doc in queue if doc.get("status") == "Ready to Post")
    posted_count = sum(1 for doc in queue if doc.get("status") == "Posted")
    count = len(queue)
    return {
        "label": datetime.now(timezone.utc).strftime("%Y-%m"),
        "documents": count,
        "totalAmount": _format_money(total) if count else "—",
        "postedAmount": _format_money(posted) if count else "—",
        "pendingAmount": _format_money(pending) if count else "—",
        "reviewedPct": round(((posted_count + ready) / count) * 100) if count else 0,
        "postedPct": round((posted_count / count) * 100) if count else 0,
        "pendingPct": round((sum(1 for doc in queue if doc.get("status") == "Pending Review") / count) * 100) if count else 0,
        "readyPct": round((ready / count) * 100) if count else 0,
    }


def _load_documents_state(store: Any) -> dict[str, Any]:
    raw = store.get(DOCUMENTS_KEY)
    if not raw:
        return {
            "entity": "New Ridge Family Financial",
            "queue": [],
            "previewById": {},
            "period": _recompute_period([]),
        }
    try:
        state = json.loads(raw)
    except json.JSONDecodeError:
        state = {}
    state.setdefault("entity", "New Ridge Family Financial")
    state.setdefault("queue", [])
    state.setdefault("previewById", {})
    return state


def _apply_source_import(store: Any, state: dict[str, Any]) -> dict[str, Any]:
    """Merge SoftDent/QuickBooks import rows into documents state."""
    source_import_result: dict[str, Any] = {"counts": {"quickbooks": 0, "softdent": 0}, "warnings": []}
    try:
        from document_source_import import build_source_import_documents, merge_source_documents

        source_payload = build_source_import_documents()
        merge_source_documents(state, source_payload)
        source_import_result = {
            "counts": source_payload.get("counts") or {"quickbooks": 0, "softdent": 0},
            "warnings": source_payload.get("warnings") or [],
            "imported": len(source_payload.get("queue") or []),
        }
    except Exception as exc:
        source_import_result = {
            "counts": {"quickbooks": 0, "softdent": 0},
            "warnings": [f"SoftDent/QuickBooks document import skipped: {exc}"],
            "imported": 0,
        }
    if not str(state.get("entity") or "").strip():
        state["entity"] = "New Ridge Family Financial"
    state["period"] = _recompute_period(state.get("queue") or [])
    store.set(DOCUMENTS_KEY, json.dumps(state))
    return source_import_result


def sync_accounting_documents(store: Any) -> dict[str, Any]:
    """Merge financial summary rows into the NR2 document intake queue."""
    financial_only = hal_financial_numbers_only()
    db_path = resolve_accounting_db_path()
    archive_dir = resolve_archive_path()
    result: dict[str, Any] = {
        "syncedAt": datetime.now(timezone.utc).isoformat(),
        "financialNumbersOnly": financial_only,
        "dbPath": str(db_path) if db_path else None,
        "inboxPath": str(resolve_inbox_path()),
        "archivePath": str(archive_dir),
        "imported": 0,
        "updated": 0,
        "skipped": 0,
        "manualKept": 0,
        "warnings": [],
    }
    if financial_only:
        result["warnings"].append(
            "HAL financial-numbers-only mode: OCR invoices and bill line items are not synced into Documents."
        )
        state = _load_documents_state(store)
        result["sourceImport"] = _apply_source_import(store, state)
        result["state"] = state
        result["queueCount"] = len(state.get("queue") or [])
        return result

    if not db_path:
        result["warnings"].append("No accounting document database found yet. Drop files in the NR2 document inbox for OCR.")
        state = _load_documents_state(store)
        result["sourceImport"] = _apply_source_import(store, state)
        result["state"] = state
        result["queueCount"] = len(state.get("queue") or [])
        return result

    rows = _read_accounting_rows(db_path)
    if not rows:
        result["warnings"].append(f"Accounting database is empty: {db_path}")
        state = _load_documents_state(store)
        result["sourceImport"] = _apply_source_import(store, state)
        result["state"] = state
        result["queueCount"] = len(state.get("queue") or [])
        return result

    state = _load_documents_state(store)
    manual_queue = [doc for doc in list(state.get("queue") or []) if not doc.get("autoImported")]
    manual_ids = {str(doc.get("id") or "") for doc in manual_queue}
    manual_previews = {
        key: value
        for key, value in dict(state.get("previewById") or {}).items()
        if key in manual_ids
    }
    result["manualKept"] = len(manual_queue)

    auto_queue: list[dict[str, Any]] = []
    previews: dict[str, Any] = {}
    seen: set[str] = set()
    missing_sources = 0
    for row in rows:
        sha = str(row.get("sha256") or "").strip()
        doc, preview = _queue_entry_from_row(row, archive_dir)
        dedupe_key = sha or doc["id"]
        if dedupe_key in seen:
            result["skipped"] += 1
            continue
        seen.add(dedupe_key)
        source_name = str(row.get("source_name") or "").strip()
        if source_name and _live_archive_file(row, archive_dir) is None:
            missing_sources += 1
        auto_queue.append(doc)
        previews[doc["id"]] = preview
        result["imported"] += 1
    if missing_sources:
        result["warnings"].append(
            f"{missing_sources} document(s) reference a source file removed by retention; preview unavailable."
        )

    state["queue"] = manual_queue + auto_queue
    state["previewById"] = dict(manual_previews)
    for doc in manual_queue:
        preview = (state.get("previewById") or {}).get(doc.get("id"))
        if preview:
            state["previewById"][str(doc["id"])] = preview
    state["previewById"].update(previews)

    result["sourceImport"] = _apply_source_import(store, state)
    merged_queue = state.get("queue") or []
    result["queueCount"] = len(merged_queue)
    result["autoCount"] = len(auto_queue)
    result["state"] = state
    return result


if __name__ == "__main__":
    from local_store import LocalStore

    store = LocalStore(NR2_DATA_DIR)
    print(json.dumps(sync_accounting_documents(store), indent=2))
