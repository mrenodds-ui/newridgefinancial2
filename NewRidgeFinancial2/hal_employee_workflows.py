"""HAL employee workflows — collections, deposits, claims, EOB/ERA, month-end."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from employee_actions import check_action_consent


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_employee_workflow_schemas(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS nr2_collections_queue (
            id TEXT PRIMARY KEY,
            created_at_utc TEXT NOT NULL,
            patient_id TEXT,
            patient_name TEXT,
            balance REAL NOT NULL DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'normal',
            status TEXT NOT NULL DEFAULT 'open',
            notes TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS nr2_deposits_recon (
            id TEXT PRIMARY KEY,
            created_at_utc TEXT NOT NULL,
            deposit_date TEXT,
            bank_amount REAL NOT NULL DEFAULT 0,
            ledger_amount REAL NOT NULL DEFAULT 0,
            variance REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'draft',
            draft_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS nr2_claims_preflight (
            id TEXT PRIMARY KEY,
            created_at_utc TEXT NOT NULL,
            claim_id TEXT,
            patient_id TEXT,
            payer TEXT,
            status TEXT NOT NULL DEFAULT 'staged',
            checklist_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS nr2_eob_match (
            id TEXT PRIMARY KEY,
            created_at_utc TEXT NOT NULL,
            source_type TEXT NOT NULL,
            reference_id TEXT,
            matched_claim_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            detail_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS era_match_feedback (
            id TEXT PRIMARY KEY,
            era_line_id TEXT NOT NULL,
            predicted_claim_id TEXT,
            corrected_claim_id TEXT,
            confidence_at_prediction REAL,
            operator_verified INTEGER,
            feedback_ts TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS shift_handoffs (
            id TEXT PRIMARY KEY,
            created_at_utc TEXT NOT NULL,
            employee_id TEXT NOT NULL,
            report_markdown TEXT NOT NULL,
            open_item_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    from hal_alerts import ensure_alert_schema
    from voip_actions import ensure_call_log_schema
    from sms_actions import ensure_sms_schema
    from nr2_scheduler import ensure_scheduler_schema

    ensure_alert_schema(conn)
    ensure_call_log_schema(conn)
    ensure_sms_schema(conn)
    ensure_scheduler_schema(conn)


def compile_shift_handoff(store, *, employee_id: str = "HAL") -> dict[str, Any]:
    """Aggregate open work into markdown handoff report."""
    open_collections = list_collections_queue(store, limit=100).get("items") or []
    open_items = [i for i in open_collections if str(i.get("status") or "open") == "open"]
    heal_note = "Import heal not run this shift."
    try:
        from import_healing import heal_import_pipeline

        heal = heal_import_pipeline(force=False)
        heal_note = str(heal.get("message") or heal.get("status") or "heal checked")
    except Exception:
        pass
    consent = check_action_consent(str(employee_id or "HAL"), "qbo-post", None, store=store)
    month_end = generate_month_end_tasks(store)
    tasks = (month_end.get("tasks") or []) if isinstance(month_end, dict) else []
    open_tasks = [t for t in tasks if not t.get("completed")]
    lines = [
        f"# HAL Shift Handoff — {_utc_now()}",
        f"Employee: {employee_id}",
        "",
        "## Import Health",
        f"- {heal_note}",
        "",
        "## Collections (open)",
    ]
    for item in open_items[:15]:
        lines.append(f"- {item.get('patientName') or item.get('patient_id')}: ${item.get('balance', 0)}")
    if not open_items:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Consent Budget",
            f"- Tier {consent.get('tier')}; qbo-post allowed: {consent.get('allowed')}",
            "",
            "## Month-End Tasks Open",
        ]
    )
    for task in open_tasks[:10]:
        lines.append(f"- {task.get('title') or task.get('id')}")
    if not open_tasks:
        lines.append("- None")
    report = "\n".join(lines)
    return {
        "ok": True,
        "reportMarkdown": report,
        "openItemCount": len(open_items),
        "openCollections": len(open_items),
        "openMonthEndTasks": len(open_tasks),
    }


def record_era_match_feedback_api(store, payload: dict[str, Any]) -> dict[str, Any]:
    from era_ml_trainer import record_match_feedback

    conn = store._connect()
    init_employee_workflow_schemas(conn)
    return record_match_feedback(
        conn,
        era_line_id=str(payload.get("eraLineId") or payload.get("era_line_id") or payload.get("referenceId") or ""),
        predicted_claim_id=str(payload.get("predictedClaimId") or payload.get("predicted_claim_id") or ""),
        corrected_claim_id=str(payload.get("correctedClaimId") or payload.get("corrected_claim_id") or "") or None,
        approved=bool(payload.get("approved", payload.get("is_correct", True))),
        confidence_at_prediction=float(payload.get("confidence") or payload.get("confidenceScore") or 0),
    )


def _parse_money(value: Any) -> float:
    raw = str(value or "").replace("$", "").replace(",", "").strip()
    try:
        return float(raw) if raw else 0.0
    except ValueError:
        return 0.0


def _load_ar_rows(store_path: Any) -> list[dict[str, Any]]:
    try:
        from import_loader import load_import_bundle

        bundle = load_import_bundle(sync=False, deep=False)
        sd = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
        ar = sd.get("ar") if isinstance(sd.get("ar"), dict) else {}
        rows = ar.get("rows") if isinstance(ar.get("rows"), list) else []
        if rows:
            return rows
    except Exception:
        pass
    try:
        from financial_reports import build_financial_reports

        reports = build_financial_reports(sync_exports=False)
        buckets = reports.get("arAgingBuckets") or []
        if buckets:
            return [{"bucket": b.get("bucket"), "amount": b.get("amount"), "Balance": b.get("amount")} for b in buckets]
    except Exception:
        pass
    return []


def generate_collections_queue(store, *, limit: int = 25) -> dict[str, Any]:
    if not store:
        return {"ok": False, "error": "no_store"}
    rows = _load_ar_rows(store.db_path)
    items: list[dict[str, Any]] = []
    with store._connect() as conn:
        init_employee_workflow_schemas(conn)
        for row in rows[:limit]:
            balance = _parse_money(row.get("Balance") or row.get("Outstanding") or row.get("amount"))
            if balance <= 0:
                continue
            bucket = str(row.get("Aging") or row.get("Bucket") or row.get("bucket") or "")
            priority = "high" if "90" in bucket else "normal"
            entry_id = str(uuid.uuid4())
            patient = str(row.get("Patient") or row.get("patient") or row.get("Name") or "Unknown")
            conn.execute(
                """
                INSERT OR REPLACE INTO nr2_collections_queue
                (id, created_at_utc, patient_id, patient_name, balance, priority, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    _utc_now(),
                    str(row.get("PatientId") or row.get("id") or ""),
                    patient,
                    balance,
                    priority,
                    "open",
                    f"A/R bucket {bucket}".strip(),
                ),
            )
            items.append(
                {
                    "id": entry_id,
                    "patientName": patient,
                    "balance": balance,
                    "priority": priority,
                    "status": "open",
                }
            )
    return {"ok": True, "items": items, "count": len(items)}


def list_collections_queue(store, *, limit: int = 50) -> dict[str, Any]:
    if not store:
        return {"ok": True, "items": [], "count": 0}
    with store._connect() as conn:
        init_employee_workflow_schemas(conn)
        rows = conn.execute(
            """
            SELECT id, created_at_utc, patient_id, patient_name, balance, priority, status, notes
            FROM nr2_collections_queue
            ORDER BY created_at_utc DESC
            LIMIT ?
            """,
            (max(1, min(int(limit or 50), 200)),),
        ).fetchall()
    items = [
        {
            "id": r[0],
            "createdAtUtc": r[1],
            "patientId": r[2],
            "patientName": r[3],
            "balance": r[4],
            "priority": r[5],
            "status": r[6],
            "notes": r[7],
        }
        for r in rows
    ]
    return {"ok": True, "items": items, "count": len(items)}


def draft_deposit_reconciliation(store, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not store:
        return {"ok": False, "error": "no_store"}
    data = payload if isinstance(payload, dict) else {}
    bank = float(data.get("bankAmount") or data.get("bank_amount") or 0)
    ledger = float(data.get("ledgerAmount") or data.get("ledger_amount") or 0)
    variance = round(bank - ledger, 2)
    entry_id = str(uuid.uuid4())
    draft = {
        "depositDate": str(data.get("depositDate") or data.get("deposit_date") or ""),
        "bankAmount": bank,
        "ledgerAmount": ledger,
        "variance": variance,
        "suggestedActions": [],
    }
    if abs(variance) > 0.01:
        draft["suggestedActions"].append("Review unmatched deposits and same-day patient payments.")
    if variance > 0:
        draft["suggestedActions"].append("Bank total exceeds ledger — check unposted deposits.")
    elif variance < 0:
        draft["suggestedActions"].append("Ledger exceeds bank — verify duplicate postings.")
    with store._connect() as conn:
        init_employee_workflow_schemas(conn)
        conn.execute(
            """
            INSERT INTO nr2_deposits_recon
            (id, created_at_utc, deposit_date, bank_amount, ledger_amount, variance, status, draft_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                _utc_now(),
                draft["depositDate"],
                bank,
                ledger,
                variance,
                "draft",
                json.dumps(draft),
            ),
        )
    return {"ok": True, "id": entry_id, "draft": draft, "variance": variance}


def stage_claim_preflight(store, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not store:
        return {"ok": False, "error": "no_store"}
    data = payload if isinstance(payload, dict) else {}
    claim_id = str(data.get("claimId") or data.get("claim_id") or "")
    patient_id = str(data.get("patientId") or data.get("patient_id") or "")
    payer = str(data.get("payer") or "")
    checklist = {
        "narrativePresent": bool(data.get("narrativePresent")),
        "attachmentsReady": bool(data.get("attachmentsReady")),
        "feeScheduleVerified": bool(data.get("feeScheduleVerified")),
        "insuranceVerified": bool(data.get("insuranceVerified")),
        "clinicalSummaryLinked": bool(data.get("clinicalSummaryLinked")),
    }
    ready = all(checklist.values())
    entry_id = str(uuid.uuid4())
    with store._connect() as conn:
        init_employee_workflow_schemas(conn)
        conn.execute(
            """
            INSERT INTO nr2_claims_preflight
            (id, created_at_utc, claim_id, patient_id, payer, status, checklist_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                _utc_now(),
                claim_id,
                patient_id,
                payer,
                "ready" if ready else "staged",
                json.dumps(checklist),
            ),
        )
    return {
        "ok": True,
        "id": entry_id,
        "claimId": claim_id,
        "status": "ready" if ready else "staged",
        "checklist": checklist,
        "ready": ready,
    }


def generate_collection_letter(store, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not store:
        return {"ok": False, "error": "no_store"}
    data = payload if isinstance(payload, dict) else {}
    patient_name = str(data.get("patientName") or data.get("patient_name") or "Patient")
    balance = _parse_money(data.get("balance") or data.get("amount"))
    consent = check_action_consent(str(data.get("employeeId") or "HAL"), "email", balance, store=store)
    letter = (
        f"Dear {patient_name},\n\n"
        f"Our records show an outstanding balance of ${balance:,.2f}. "
        "Please contact our office to arrange payment or discuss a payment plan.\n\n"
        "Thank you,\nNew Ridge Family Dental — Billing Office"
    )
    entry_id = str(uuid.uuid4())
    with store._connect() as conn:
        init_employee_workflow_schemas(conn)
        conn.execute(
            """
            INSERT INTO nr2_collections_queue
            (id, created_at_utc, patient_id, patient_name, balance, priority, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                _utc_now(),
                str(data.get("patientId") or ""),
                patient_name,
                balance,
                "normal",
                "letter_draft",
                letter[:500],
            ),
        )
    return {
        "ok": True,
        "id": entry_id,
        "letter": letter,
        "requiresApproval": not consent.get("allowed"),
        "consent": consent,
    }


def schedule_call_task(store, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not store:
        return {"ok": False, "error": "no_store"}
    data = payload if isinstance(payload, dict) else {}
    patient_name = str(data.get("patientName") or data.get("patient_name") or "Patient")
    balance = _parse_money(data.get("balance") or 0)
    entry_id = str(uuid.uuid4())
    script = (
        f"Hello, may I speak with {patient_name}? "
        f"This is the billing office at New Ridge Family Dental regarding a balance of ${balance:,.2f}. "
        "Do you have a moment to review payment options?"
    )
    with store._connect() as conn:
        init_employee_workflow_schemas(conn)
        conn.execute(
            """
            INSERT INTO nr2_collections_queue
            (id, created_at_utc, patient_id, patient_name, balance, priority, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                _utc_now(),
                str(data.get("patientId") or ""),
                patient_name,
                balance,
                str(data.get("priority") or "high"),
                "call_scheduled",
                script[:500],
            ),
        )
    return {"ok": True, "id": entry_id, "callScript": script, "status": "call_scheduled"}


def parse_era_import(store, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from era835_parser import fuzzy_match_claims, parse_835_text

    data = payload if isinstance(payload, dict) else {}
    content = str(data.get("era835") or data.get("content") or data.get("text") or "")
    if not content.strip():
        return {"ok": False, "error": "era_content_required"}
    parsed = parse_835_text(content)
    claim_rows: list[dict[str, Any]] = []
    try:
        from import_loader import load_import_bundle

        bundle = load_import_bundle(sync=False, deep=False)
        sd = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
        claims = sd.get("claims") if isinstance(sd.get("claims"), dict) else {}
        claim_rows = claims.get("rows") if isinstance(claims.get("rows"), list) else []
    except Exception:
        claim_rows = []
    matches = fuzzy_match_claims(parsed.get("segments") or [], claim_rows)
    results = []
    for match in matches:
        results.append(process_eob_match(store, {**data, **match, "sourceType": "era"}))
    return {"ok": True, "parsed": parsed, "matches": matches, "processed": results, "count": len(results)}


def process_eob_match(store, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not store:
        return {"ok": False, "error": "no_store"}
    data = payload if isinstance(payload, dict) else {}
    source_type = str(data.get("sourceType") or data.get("source_type") or "eob").lower()
    reference_id = str(data.get("referenceId") or data.get("reference_id") or data.get("eobId") or "")
    claim_id = str(data.get("claimId") or data.get("claim_id") or data.get("matchedClaimId") or "")
    paid = _parse_money(data.get("paidAmount") or data.get("paid_amount") or data.get("paid"))
    confidence = float(data.get("confidence") or 0.0)

    if not claim_id and (data.get("era835") or data.get("content")):
        era_result = parse_era_import(store, data)
        if era_result.get("processed"):
            return era_result["processed"][0] if era_result["processed"] else era_result

    if not claim_id:
        from era835_parser import fuzzy_match_claims

        seg = {
            "claimId": reference_id,
            "patientName": str(data.get("patientName") or data.get("patient_name") or ""),
            "paid": paid,
            "serviceDate": str(data.get("serviceDate") or ""),
        }
        claim_rows: list[dict[str, Any]] = []
        try:
            from import_loader import load_import_bundle

            bundle = load_import_bundle(sync=False, deep=False)
            sd = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
            claims = sd.get("claims") if isinstance(sd.get("claims"), dict) else {}
            claim_rows = claims.get("rows") if isinstance(claims.get("rows"), list) else []
        except Exception:
            pass
        fuzzy = fuzzy_match_claims([seg], claim_rows)
        if fuzzy and fuzzy[0].get("claimId"):
            claim_id = str(fuzzy[0]["claimId"])
            confidence = float(fuzzy[0].get("confidence") or confidence)

    if confidence >= 0.85 and claim_id and paid:
        detail_conf = "high"
    elif claim_id and reference_id:
        detail_conf = "high"
    elif claim_id:
        detail_conf = "medium"
    else:
        detail_conf = "low"
    detail = {
        "referenceId": reference_id,
        "claimId": claim_id,
        "paidAmount": paid,
        "sourceType": source_type,
        "matchConfidence": detail_conf,
        "confidenceScore": confidence,
    }
    status = "matched" if claim_id and detail_conf in ("high", "medium") else "review"
    entry_id = str(uuid.uuid4())
    with store._connect() as conn:
        init_employee_workflow_schemas(conn)
        conn.execute(
            """
            INSERT INTO nr2_eob_match
            (id, created_at_utc, source_type, reference_id, matched_claim_id, status, detail_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (entry_id, _utc_now(), source_type, reference_id, claim_id, status, json.dumps(detail)),
        )
    if status == "matched" and paid and claim_id:
        try:
            from accounting_bridge import enqueue_journal_posting, parse_context_json

            enqueue_journal_posting(
                store.db_path,
                description=f"EOB/ERA payment match {reference_id or claim_id}",
                period="",
                amount=paid,
                actor="HAL",
                context=parse_context_json(json.dumps({"eobMatchId": entry_id, "claimId": claim_id})),
                enqueue_mode="manual_review_queue",
            )
        except Exception:
            pass
    return {"ok": True, "id": entry_id, "status": status, "detail": detail}


def batch_approve_postings(store, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not store:
        return {"ok": False, "error": "no_store"}
    data = payload if isinstance(payload, dict) else {}
    queue_ids = data.get("queueIds") or data.get("queue_ids") or []
    if not isinstance(queue_ids, list):
        queue_ids = []
    from accounting_bridge import bulk_review_posting_queue, list_posting_queue

    pending = list_posting_queue(store.db_path, limit=200, status="pending_review")
    items = pending.get("items") or []
    total_amount = sum(float(it.get("amount") or 0) for it in items if it.get("queueId") in queue_ids or not queue_ids)
    consent = check_action_consent(
        str(data.get("employeeId") or "HAL"),
        "qbo-post",
        total_amount,
        store=store,
    )
    if not consent.get("allowed"):
        return {"ok": False, "error": "consent_denied", "consent": consent}
    reviewer = str(data.get("reviewerActor") or data.get("reviewer") or "HAL")
    note = str(data.get("reviewNote") or "Batch approved via HAL employee workflow")
    if queue_ids:
        from accounting_bridge import review_posting_queue_entry

        results = []
        for qid in queue_ids:
            try:
                results.append(
                    review_posting_queue_entry(
                        store.db_path,
                        queue_id=str(qid),
                        action="approved",
                        reviewer_actor=reviewer,
                        review_note=note,
                    )
                )
            except ValueError as exc:
                results.append({"ok": False, "queueId": qid, "error": str(exc)})
        return {"ok": True, "results": results, "consent": consent}
    result = bulk_review_posting_queue(store.db_path, action="approved", reviewer_actor=reviewer, review_note=note)
    return {"ok": True, "result": result, "consent": consent}


def generate_month_end_tasks(store, *, period: str | None = None) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    try:
        from daily_closeout import build_daily_closeout

        closeout = build_daily_closeout(store)
        if closeout.get("overall") != "green":
            tasks.append(
                {
                    "id": "closeout-review",
                    "title": "Review daily closeout blockers",
                    "priority": "high",
                    "detail": closeout.get("summary") or "",
                }
            )
    except Exception:
        pass
    tasks.extend(
        [
            {"id": "posting-queue", "title": "Clear approved posting queue export", "priority": "high"},
            {"id": "ar-90", "title": "Review 90+ day A/R balances", "priority": "medium"},
            {"id": "denied-claims", "title": "Triage denied claims for resubmit", "priority": "medium"},
            {"id": "deposit-recon", "title": "Reconcile bank deposits to ledger", "priority": "high"},
            {"id": "month-end-adjustments", "title": "Draft month-end adjusting entries", "priority": "medium"},
        ]
    )
    acct_period = str(period or datetime.now(timezone.utc).strftime("%Y-%m"))
    return {"ok": True, "period": acct_period, "tasks": tasks, "count": len(tasks)}
