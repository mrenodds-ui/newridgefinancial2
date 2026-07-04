"""Desktop bridge for journal drafting and SQLite posting queue."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from accounting_tools import draft_journal_entry_for_common_case, get_chart_of_accounts, is_period_open
from accounting_validation import build_journal_validation
from posting_queue_store import (
    ENQUEUE_MODE_MANUAL_REVIEW_QUEUE,
    POSTING_QUEUE_STATUS_PENDING_REVIEW,
    PostingQueueStore,
    new_queue_id,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _line_to_js(line: dict[str, Any]) -> dict[str, Any]:
    return {
        "accountCode": str(line.get("account_code") or ""),
        "accountName": str(line.get("account_name") or ""),
        "debit": line.get("debit", 0),
        "credit": line.get("credit", 0),
        "memo": line.get("memo"),
    }


def _validation_to_js(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "balanced": bool(validation.get("balanced")),
        "debitTotal": validation.get("debit_total", 0),
        "creditTotal": validation.get("credit_total", 0),
        "openPeriod": bool(validation.get("open_period")),
        "accountValidationPassed": bool(validation.get("account_validation_passed")),
        "amountValidationPassed": bool(validation.get("amount_validation_passed")),
        "issues": list(validation.get("issues") or []),
    }


def draft_journal_payload(
    *,
    description: str,
    period: str,
    amount: float,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = context if isinstance(context, dict) else {}
    accounting_period = str(period or datetime.now(timezone.utc).strftime("%Y-%m"))[:7]
    transaction_type, lines = draft_journal_entry_for_common_case(
        description=str(description or "Journal entry"),
        accounting_period=accounting_period,
        amount=float(amount),
        context=context,
    )
    coa = get_chart_of_accounts()
    validation = build_journal_validation(
        lines=lines,
        chart_of_accounts=coa,
        open_period=is_period_open(accounting_period),
    )
    js_validation = _validation_to_js(validation)
    return {
        "meta": {
            "schema": "nr2-hal-skill-v1",
            "kind": "accounting.journalDraft",
            "source": "accounting_bridge",
            "localOnly": True,
            "generatedAt": _utc_now(),
        },
        "transactionType": transaction_type,
        "period": accounting_period,
        "description": str(description or ""),
        "amount": round(float(amount), 2),
        "lines": [_line_to_js(line) for line in lines],
        "validation": js_validation,
        "draftStatus": "draftOnly",
        "safety": {"postedToLedger": False},
        "chartOfAccounts": coa,
    }


def list_posting_queue(store_path: Any, *, limit: int = 20, status: str | None = None) -> dict[str, Any]:
    queue = PostingQueueStore(store_path)
    return {
        "items": queue.list_entries(limit=limit, status=status),
        "metrics": queue.metrics(),
    }


def enqueue_journal_posting(
    store_path: Any,
    *,
    description: str,
    period: str,
    amount: float,
    actor: str = "HAL",
    context: dict[str, Any] | None = None,
    transaction_date: str | None = None,
    enqueue_mode: str = ENQUEUE_MODE_MANUAL_REVIEW_QUEUE,
) -> dict[str, Any]:
    draft = draft_journal_payload(description=description, period=period, amount=amount, context=context)
    if draft["validation"]["issues"]:
        raise ValueError("; ".join(draft["validation"]["issues"]))
    queue = PostingQueueStore(store_path)
    queue_id = new_queue_id()
    accounting_period = draft["period"]
    entry = {
        "queue_id": queue_id,
        "created_at_utc": _utc_now(),
        "actor": str(actor or "HAL"),
        "target_system": "quickbooks_desktop",
        "status": POSTING_QUEUE_STATUS_PENDING_REVIEW,
        "description": draft["description"],
        "transaction_date": transaction_date or datetime.now(timezone.utc).date().isoformat(),
        "accounting_period": accounting_period,
        "amount": draft["amount"],
        "transaction_type": draft["transactionType"],
        "source_audit_id": queue_id,
        "enqueue_mode": enqueue_mode,
        "lines": [
            {
                "account_code": line["accountCode"],
                "account_name": line["accountName"],
                "debit": line["debit"],
                "credit": line["credit"],
                "memo": line.get("memo"),
            }
            for line in draft["lines"]
        ],
        "validation": {
            "balanced": draft["validation"]["balanced"],
            "debit_total": draft["validation"]["debitTotal"],
            "credit_total": draft["validation"]["creditTotal"],
            "open_period": draft["validation"]["openPeriod"],
            "account_validation_passed": draft["validation"]["accountValidationPassed"],
            "amount_validation_passed": draft["validation"]["amountValidationPassed"],
            "issues": draft["validation"]["issues"],
        },
    }
    saved = queue.insert_entry(entry)
    return {"draft": draft, "queueEntry": saved, "draftStatus": "enqueued"}


def review_posting_queue_entry(
    store_path: Any,
    *,
    queue_id: str,
    action: str,
    reviewer_actor: str,
    review_note: str | None = None,
) -> dict[str, Any]:
    if action not in {"approved", "rejected"}:
        raise ValueError("action must be approved or rejected")
    if not str(reviewer_actor or "").strip():
        raise ValueError("reviewer_actor is required")
    queue = PostingQueueStore(store_path)
    return queue.review_entry(
        queue_id=str(queue_id),
        action=action,
        reviewer_actor=str(reviewer_actor).strip(),
        review_note=review_note,
    )


def bulk_review_posting_queue(
    store_path: Any,
    *,
    action: str = "approved",
    reviewer_actor: str,
    review_note: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    if action not in {"approved", "rejected"}:
        raise ValueError("action must be approved or rejected")
    if not str(reviewer_actor or "").strip():
        raise ValueError("reviewer_actor is required")
    queue = PostingQueueStore(store_path)
    pending = queue.list_entries(limit=max(1, min(limit, 100)), status=POSTING_QUEUE_STATUS_PENDING_REVIEW)
    reviewed: list[dict[str, Any]] = []
    for entry in pending:
        queue_id = str(entry.get("queueId") or entry.get("queue_id") or "")
        if not queue_id:
            continue
        reviewed.append(
            queue.review_entry(
                queue_id=queue_id,
                action=action,
                reviewer_actor=str(reviewer_actor).strip(),
                review_note=review_note,
            )
        )
    return {"action": action, "reviewedCount": len(reviewed), "items": reviewed, "metrics": queue.metrics()}


def export_approved_posting_queue_csv(store_path: Any, *, limit: int = 200) -> dict[str, Any]:
    """Export approved queue entries as CSV rows for manual QuickBooks entry (never posts externally)."""
    import csv
    from io import StringIO

    from posting_queue_store import POSTING_QUEUE_STATUS_APPROVED

    queue = PostingQueueStore(store_path)
    entries = queue.list_entries(limit=max(1, min(limit, 500)), status=POSTING_QUEUE_STATUS_APPROVED)
    buffer = StringIO()
    fieldnames = [
        "queueId",
        "accountingPeriod",
        "transactionDate",
        "description",
        "transactionType",
        "accountCode",
        "accountName",
        "debit",
        "credit",
        "memo",
        "reviewerActor",
        "reviewedAtUtc",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    row_count = 0
    for entry in entries:
        for line in entry.get("lines") or []:
            writer.writerow(
                {
                    "queueId": entry.get("queueId"),
                    "accountingPeriod": entry.get("accountingPeriod"),
                    "transactionDate": entry.get("transactionDate"),
                    "description": entry.get("description"),
                    "transactionType": entry.get("transactionType"),
                    "accountCode": line.get("account_code") or line.get("accountCode"),
                    "accountName": line.get("account_name") or line.get("accountName"),
                    "debit": line.get("debit", 0),
                    "credit": line.get("credit", 0),
                    "memo": line.get("memo") or entry.get("description"),
                    "reviewerActor": entry.get("reviewerActor"),
                    "reviewedAtUtc": entry.get("reviewedAtUtc"),
                }
            )
            row_count += 1
    return {
        "csv": buffer.getvalue(),
        "entryCount": len(entries),
        "lineCount": row_count,
        "exportedAt": _utc_now(),
    }


def export_approved_posting_queue_iif(store_path: Any, *, limit: int = 200) -> dict[str, Any]:
    """Export approved queue entries as QuickBooks IIF (manual import in QuickBooks)."""
    from posting_queue_store import POSTING_QUEUE_STATUS_APPROVED

    queue = PostingQueueStore(store_path)
    entries = queue.list_entries(limit=max(1, min(limit, 500)), status=POSTING_QUEUE_STATUS_APPROVED)
    lines: list[str] = []
    lines.append("!TRNS\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tMEMO")
    lines.append("!SPL\tSPLID\tTRNSTYPE\tDATE\tACCNT\tNAME\tAMOUNT\tMEMO")
    lines.append("!ENDTRNS")
    row_count = 0
    for entry in entries:
        trns_date = str(entry.get("transactionDate") or entry.get("accountingPeriod") or "")[:10]
        desc = str(entry.get("description") or "Journal entry").replace("\t", " ")
        entry_lines = entry.get("lines") or []
        if not entry_lines:
            continue
        first = entry_lines[0]
        debit = float(first.get("debit") or 0)
        credit = float(first.get("credit") or 0)
        amount = debit if debit else -credit
        accnt = str(first.get("account_name") or first.get("accountName") or first.get("account_code") or "Misc")
        lines.append(f"TRNS\tGENERAL JOURNAL\t{trns_date}\t{accnt}\t\t{amount:.2f}\t{desc}")
        for idx, line in enumerate(entry_lines):
            d = float(line.get("debit") or 0)
            c = float(line.get("credit") or 0)
            lamt = d if d else -c
            lacnt = str(line.get("account_name") or line.get("accountName") or line.get("account_code") or "Misc")
            lmemo = str(line.get("memo") or desc).replace("\t", " ")
            lines.append(f"SPL\t{idx + 1}\tGENERAL JOURNAL\t{trns_date}\t{lacnt}\t\t{lamt:.2f}\t{lmemo}")
            row_count += 1
        lines.append("ENDTRNS")
    iif_text = "\n".join(lines) + ("\n" if lines else "")
    export_dir = Path(store_path).resolve().parent / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    export_path = export_dir / f"journal_posting_queue_{stamp}.iif"
    if iif_text.strip():
        export_path.write_text(iif_text, encoding="utf-8")
    return {
        "iif": iif_text,
        "exportPath": str(export_path) if iif_text.strip() else None,
        "entryCount": len(entries),
        "lineCount": row_count,
        "exportedAt": _utc_now(),
    }


def parse_context_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
