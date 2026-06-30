"""Import SoftDent and QuickBooks export rows into the Documents page queue.

Reads the canonical import cache under app_data/nr2/document_inbox and converts
verified tabular exports into document-intake rows the Accounting Documents page
can review alongside OCR inbox items.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from document_sync import DOCUMENTS_KEY, _age_days, _format_money, _load_documents_state, _recompute_period, _status_tone


def _slug(value: str, limit: int = 32) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", str(value or "").strip()).strip("-").upper()
    return (cleaned or "ROW")[:limit]


def _pick(row: dict[str, Any], *names: str) -> Any:
    lowered = {str(key).casefold(): value for key, value in row.items()}
    for name in names:
        if name.casefold() in lowered:
            return lowered[name.casefold()]
    return None


def _parse_amount(value: Any) -> float | None:
    if value is None:
        return None
    raw = str(value).replace("$", "").replace(",", "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_date(value: Any, fallback: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    for fmt in ("%Y-%m-%d", "%Y-%m", "%m/%d/%Y", "%m/%d/%y"):
        try:
            parsed = datetime.strptime(raw, fmt)
            if fmt == "%Y-%m":
                return f"{raw}-01"
            return parsed.date().isoformat()
        except ValueError:
            continue
    if re.fullmatch(r"\d{4}-\d{2}", raw):
        return f"{raw}-01"
    return fallback


def _short_category_label(value: str) -> str:
    parts = [part.strip() for part in str(value or "").split("·") if part.strip()]
    return parts[-1] if parts else str(value or "QuickBooks Category").strip() or "QuickBooks Category"


def _document_entry(
    *,
    doc_id: str,
    doc_type: str,
    vendor: str,
    date: str,
    amount: float | None,
    status: str,
    source_system: str,
    source_file: str,
    source_kind: str,
    text_preview: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    doc = {
        "id": doc_id,
        "type": doc_type,
        "vendor": vendor,
        "date": date,
        "amount": _format_money(amount),
        "status": status,
        "statusTone": _status_tone(status),
        "age": _age_days(date),
        "autoImported": True,
        "sourceSystem": source_system,
        "sourceFile": source_file,
        "sourceKind": source_kind,
    }
    preview = {
        "vendor": vendor.upper(),
        "invoice": doc_id,
        "date": date,
        "total": _format_money(amount),
        "file": source_file,
        "pages": "Import row",
        "uploaded": datetime.now(timezone.utc).date().isoformat(),
        "textPreview": text_preview,
        "sourceExpired": False,
        "fileUnavailable": "Source export row — no PDF attached.",
        "previewAvailable": False,
    }
    return doc, preview


def _rows_from_dataset(dataset: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not dataset:
        return []
    rows = dataset.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def build_source_import_documents(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build document queue rows from the current SoftDent/QuickBooks import cache."""
    if bundle is None:
        from import_loader import load_import_bundle

        bundle = load_import_bundle(sync=False, deep=False)

    today = datetime.now(timezone.utc).date().isoformat()
    queue: list[dict[str, Any]] = []
    previews: dict[str, Any] = {}
    counts = {"quickbooks": 0, "softdent": 0}
    warnings: list[str] = []

    qb = (bundle or {}).get("quickbooks") or {}
    sd = (bundle or {}).get("softdent") or {}

    expense_categories = _rows_from_dataset(qb.get("expenseCategories"))
    for index, row in enumerate(expense_categories[:40]):
        category = _short_category_label(str(_pick(row, "Category", "category") or f"Category {index + 1}"))
        amount = _parse_amount(_pick(row, "Amount", "amount", "TotalExpense", "Total"))
        source_file = str((qb.get("expenseCategories") or {}).get("sourceFile") or "quickbooks_expense_categories.csv")
        doc_id = f"QB-CAT-{_slug(category)}"
        doc, preview = _document_entry(
            doc_id=doc_id,
            doc_type="Bill",
            vendor=category,
            date=today,
            amount=amount,
            status="Ready to Post",
            source_system="quickbooks",
            source_file=source_file,
            source_kind="expenseCategory",
            text_preview=f"QuickBooks expense category import · {category}",
        )
        queue.append(doc)
        previews[doc_id] = preview
        counts["quickbooks"] += 1

    for row in _rows_from_dataset(qb.get("expenses")):
        period = str(_pick(row, "Period", "period", "Month", "month") or "unknown")
        amount = _parse_amount(_pick(row, "TotalExpense", "Amount", "amount", "total"))
        source_file = str((qb.get("expenses") or {}).get("sourceFile") or "quickbooks_expenses.csv")
        doc_id = f"QB-EXP-{_slug(period)}"
        doc, preview = _document_entry(
            doc_id=doc_id,
            doc_type="Statement",
            vendor="QuickBooks Operating Expenses",
            date=_parse_date(period, today),
            amount=amount,
            status="Ready to Post",
            source_system="quickbooks",
            source_file=source_file,
            source_kind="monthlyExpenses",
            text_preview=f"QuickBooks monthly expense total · period {period}",
        )
        queue.append(doc)
        previews[doc_id] = preview
        counts["quickbooks"] += 1

    for row in _rows_from_dataset(qb.get("revenue")):
        period = str(_pick(row, "Period", "period", "Month", "month") or "unknown")
        amount = _parse_amount(_pick(row, "TotalIncome", "Revenue", "Amount", "amount", "total"))
        source_file = str((qb.get("revenue") or {}).get("sourceFile") or "quickbooks_revenue.csv")
        doc_id = f"QB-REV-{_slug(period)}"
        doc, preview = _document_entry(
            doc_id=doc_id,
            doc_type="Statement",
            vendor="QuickBooks Revenue",
            date=_parse_date(period, today),
            amount=amount,
            status="Ready to Post",
            source_system="quickbooks",
            source_file=source_file,
            source_kind="monthlyRevenue",
            text_preview=f"QuickBooks monthly revenue total · period {period}",
        )
        queue.append(doc)
        previews[doc_id] = preview
        counts["quickbooks"] += 1

    for row in _rows_from_dataset(sd.get("claims"))[:50]:
        claim_id = str(_pick(row, "ClaimId", "claimId", "id") or "").strip()
        patient = str(_pick(row, "PatientName", "patient", "Patient") or "Unknown Patient").strip()
        amount = _parse_amount(_pick(row, "ClaimAmount", "amount", "Amount", "Billed"))
        service_date = _parse_date(_pick(row, "ServiceDate", "serviceDate", "DOS", "date"), today)
        source_file = str((sd.get("claims") or {}).get("sourceFile") or "softdent_claims_export.csv")
        doc_id = f"SD-CLM-{_slug(claim_id or patient)}"
        doc, preview = _document_entry(
            doc_id=doc_id,
            doc_type="Claim",
            vendor=patient,
            date=service_date,
            amount=amount,
            status="Pending Review",
            source_system="softdent",
            source_file=source_file,
            source_kind="claim",
            text_preview=f"SoftDent claim import · {claim_id or patient}",
        )
        queue.append(doc)
        previews[doc_id] = preview
        counts["softdent"] += 1

    for row in _rows_from_dataset(sd.get("ar")):
        bucket = str(_pick(row, "Bucket", "bucket", "AgingBucket", "Range") or "Total")
        amount = _parse_amount(_pick(row, "Balance", "Amount", "amount", "total"))
        source_file = str((sd.get("ar") or {}).get("sourceFile") or "softdent_ar_aging.csv")
        doc_id = f"SD-AR-{_slug(bucket)}"
        doc, preview = _document_entry(
            doc_id=doc_id,
            doc_type="A/R Aging",
            vendor=f"SoftDent A/R · {bucket}",
            date=today,
            amount=amount,
            status="Ready to Post",
            source_system="softdent",
            source_file=source_file,
            source_kind="arAging",
            text_preview=f"SoftDent A/R aging bucket · {bucket}",
        )
        queue.append(doc)
        previews[doc_id] = preview
        counts["softdent"] += 1

    for row in _rows_from_dataset(sd.get("dashboard"))[:12]:
        period = str(_pick(row, "period", "Period", "Month", "month") or "current")
        production = _parse_amount(_pick(row, "production", "Production"))
        collections = _parse_amount(_pick(row, "collections", "Collections"))
        provider = str(_pick(row, "provider", "Provider", "providerName") or "SoftDent Dashboard")
        source_file = str((sd.get("dashboard") or {}).get("sourceFile") or "softdent_dashboard_data.json")
        doc_id = f"SD-DASH-{_slug(period)}"
        doc, preview = _document_entry(
            doc_id=doc_id,
            doc_type="Production Summary",
            vendor=provider,
            date=_parse_date(period, today),
            amount=production if production is not None else collections,
            status="Ready to Post",
            source_system="softdent",
            source_file=source_file,
            source_kind="dashboard",
            text_preview=(
                f"SoftDent dashboard import · production {_format_money(production)} · "
                f"collections {_format_money(collections)}"
            ),
        )
        queue.append(doc)
        previews[doc_id] = preview
        counts["softdent"] += 1

    if not counts["quickbooks"] and not counts["softdent"]:
        warnings.append("No SoftDent or QuickBooks rows found in the import cache for document intake.")

    return {
        "importedAt": datetime.now(timezone.utc).isoformat(),
        "queue": queue,
        "previewById": previews,
        "counts": counts,
        "warnings": warnings,
    }


def merge_source_documents(state: dict[str, Any], source_payload: dict[str, Any]) -> dict[str, Any]:
    """Merge source-import documents into an existing documents state."""
    manual_queue = [
        doc
        for doc in list(state.get("queue") or [])
        if not doc.get("autoImported") or not str(doc.get("sourceSystem") or "").strip()
    ]
    ocr_queue = [
        doc
        for doc in list(state.get("queue") or [])
        if doc.get("autoImported") and not str(doc.get("sourceSystem") or "").strip()
    ]
    manual_ids = {str(doc.get("id") or "") for doc in manual_queue}
    manual_previews = {
        key: value for key, value in dict(state.get("previewById") or {}).items() if key in manual_ids
    }
    ocr_previews = {
        key: value
        for key, value in dict(state.get("previewById") or {}).items()
        if key not in manual_ids
    }

    source_queue = list(source_payload.get("queue") or [])
    source_previews = dict(source_payload.get("previewById") or {})

    seen: set[str] = set(manual_ids)
    merged_queue = list(manual_queue)
    merged_previews = dict(manual_previews)

    for doc in ocr_queue + source_queue:
        doc_id = str(doc.get("id") or "")
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        merged_queue.append(doc)
        preview = source_previews.get(doc_id) or ocr_previews.get(doc_id)
        if preview:
            merged_previews[doc_id] = preview

    state["queue"] = merged_queue
    state["previewById"] = merged_previews
    if not str(state.get("entity") or "").strip():
        state["entity"] = "New Ridge Family Financial"
    state["period"] = _recompute_period(merged_queue)
    return state


def sync_source_documents(store: Any) -> dict[str, Any]:
    """Standalone sync: merge SoftDent/QuickBooks import rows into nr2:v2:documents."""
    payload = build_source_import_documents()
    state = _load_documents_state(store)
    merge_source_documents(state, payload)
    store.set(DOCUMENTS_KEY, __import__("json").dumps(state))
    return {
        "syncedAt": payload["importedAt"],
        "counts": payload["counts"],
        "warnings": payload["warnings"],
        "queueCount": len(state.get("queue") or []),
        "state": state,
    }


if __name__ == "__main__":
    import json

    from local_store import LocalStore
    from document_sync import NR2_DATA_DIR

    store = LocalStore(NR2_DATA_DIR)
    print(json.dumps(sync_source_documents(store), indent=2))
