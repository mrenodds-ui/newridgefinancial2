"""HAL employee workflows — collections, deposits, claims, EOB/ERA, month-end."""

from __future__ import annotations

import json
import re
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


def _claims_ops_snapshot() -> dict[str, Any]:
    """Best-effort SoftDent claims stats for handoff / morning routine."""
    out: dict[str, Any] = {
        "total": 0,
        "denied": 0,
        "genericPayer": 0,
        "namedPayer": 0,
        "agingOver60": 0,
        "agingOver90": 0,
        "topAging": [],
    }
    try:
        from import_loader import load_import_bundle

        bundle = load_import_bundle(sync=False, deep=False)
        sd = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
        claims = sd.get("claims") if isinstance(sd.get("claims"), dict) else {}
        rows = claims.get("rows") if isinstance(claims.get("rows"), list) else []
    except Exception:
        rows = []
    out["total"] = len(rows)
    aging_candidates: list[tuple[int, str, str]] = []
    for row in rows:
        status = str(row.get("ClaimStatus") or row.get("status") or "").lower()
        if "denied" in status:
            out["denied"] += 1
        payer = str(row.get("Payer") or row.get("payer") or "").strip().lower()
        if payer in {"", "insurance", "unknown", "n/a", "-", "—"}:
            out["genericPayer"] += 1
        else:
            out["namedPayer"] += 1
        age = None
        for key in ("Days", "days", "Age", "age"):
            if row.get(key) not in (None, ""):
                try:
                    age = int(float(str(row.get(key)).replace(",", "")))
                except ValueError:
                    age = None
                break
        if age is None:
            dos = str(row.get("ServiceDate") or row.get("serviceDate") or "")[:10]
            if dos:
                try:
                    from datetime import date as _date

                    d = _date.fromisoformat(dos)
                    age = max(0, (datetime.now(timezone.utc).date() - d).days)
                except ValueError:
                    age = None
        if age is not None and age >= 60:
            out["agingOver60"] += 1
            if age >= 90:
                out["agingOver90"] += 1
            cid = str(row.get("ClaimId") or row.get("claimId") or row.get("id") or "?")
            aging_candidates.append((age, cid, status or "?"))
    aging_candidates.sort(key=lambda t: -t[0])
    out["topAging"] = [
        {"claimId": cid, "ageDays": age, "status": st} for age, cid, st in aging_candidates[:5]
    ]
    return out


def _softdent_named_payer_brief() -> dict[str, Any]:
    """SoftDent ODBC/extract + named-payer gap for handoff / morning briefing."""
    claims = _claims_ops_snapshot()
    extract: dict[str, Any] = {}
    try:
        from softdent_odbc_extract import read_extract_status

        extract = read_extract_status() or {}
    except Exception as exc:
        extract = {"ok": False, "error": str(exc)}
    table_counts = extract.get("tableCounts") if isinstance(extract.get("tableCounts"), dict) else {}
    sd_claims_rows = int(table_counts.get("sd_claims") or 0)
    named = int(claims.get("namedPayer") or 0)
    generic = int(claims.get("genericPayer") or 0)
    total = int(claims.get("total") or 0)
    odbc_ok = bool(extract.get("odbcConfigured"))
    stale = bool(extract.get("stale"))
    queries = int(extract.get("queriesConfigured") or 0)
    configured = extract.get("configuredQueryTables") or []
    has_claims_query = "sd_claims" in configured if isinstance(configured, list) else False
    if named > 0 and generic == 0:
        summary = f"Named payers on all {named} imported claim(s)."
    elif named > 0:
        summary = (
            f"Named payers on {named}/{total} claim(s); {generic} still generic \"Insurance\"."
        )
    elif total > 0:
        summary = (
            f"All {total} imported claim(s) lack named Payer — need SoftDent claims CSV/ODBC (sd_claims={sd_claims_rows})."
        )
    else:
        summary = "No SoftDent claims rows in import yet."
    if odbc_ok and not has_claims_query and named == 0:
        summary += " ODBC DSN set but SOFTDENT_ODBC_CLAIMS_QUERY / discovery claims query missing."
    elif stale and odbc_ok:
        summary += " Extract marked stale — refresh Sync SoftDent."
    next_steps = list(extract.get("nextSteps") or [])[:3]
    return {
        "ok": bool(extract.get("ok", True)),
        "summary": summary,
        "namedPayer": named,
        "genericPayer": generic,
        "claimsTotal": total,
        "sdClaimsRows": sd_claims_rows,
        "odbcConfigured": odbc_ok,
        "queriesConfigured": queries,
        "hasClaimsQuery": has_claims_query,
        "stale": stale,
        "lastExtractAt": extract.get("lastExtractAt"),
        "lastMode": extract.get("lastMode"),
        "nextSteps": next_steps,
        "extract": {
            "populatedTables": extract.get("populatedTables"),
            "senseiDatasyncAvailable": extract.get("senseiDatasyncAvailable"),
            "discoveryPresent": extract.get("discoveryPresent"),
        },
    }


def seed_underpay_to_collections(store, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Seed a collections-queue follow-up when fee scrub flags true underpay (local only)."""
    if not store:
        return {"ok": False, "error": "no_store"}
    data = dict(payload) if isinstance(payload, dict) else {}
    shortfall = _parse_money(
        data.get("shortfall") or data.get("balance") or data.get("delta") or data.get("amount")
    )
    if shortfall < 0:
        shortfall = abs(shortfall)
    if shortfall <= 0:
        return {"ok": False, "error": "shortfall_required", "summary": "Need underpay shortfall amount to seed collections."}
    patient = str(
        data.get("patientName") or data.get("patient") or data.get("PatientName") or "Insurance underpay"
    ).strip()
    patient_id = str(data.get("patientId") or data.get("patient_id") or data.get("claimId") or "").strip()
    cdt = str(data.get("cdt") or "").strip().upper()
    payer = str(data.get("payer") or "").strip()
    claim_id = str(data.get("claimId") or data.get("claim_id") or "").strip()
    notes = str(data.get("notes") or "").strip()
    if not notes:
        parts = ["Fee underpay vs schedule"]
        if cdt:
            parts.append(cdt)
        if payer:
            parts.append(payer)
        if claim_id:
            parts.append(f"claim {claim_id}")
        parts.append(f"shortfall ${shortfall:,.2f} — staff review before patient balance")
        notes = " · ".join(parts)

    # Dedupe open underpay rows for same patient/claim
    existing = list_collections_queue(store, limit=100).get("items") or []
    for item in existing:
        if str(item.get("status") or "") != "open":
            continue
        hay = f"{item.get('patientName')} {item.get('patientId')} {item.get('notes')}".lower()
        if "underpay" in hay and (
            (claim_id and claim_id.lower() in hay)
            or (patient_id and patient_id.lower() == str(item.get("patientId") or "").lower())
            or (patient.lower() in str(item.get("patientName") or "").lower() and abs(float(item.get("balance") or 0) - shortfall) < 0.02)
        ):
            return {
                "ok": True,
                "seeded": False,
                "duplicate": True,
                "id": item.get("id"),
                "summary": f"Underpay already on collections queue ({item.get('id')}).",
            }

    call_script = ""
    try:
        from voip_actions import get_voice_script

        scripted = get_voice_script(
            "underpay",
            patient_name=patient,
            balance=f"${shortfall:,.2f}",
        )
        call_script = str(scripted.get("script") or "")
        if call_script:
            notes = f"{notes} · Script: {call_script}"[:500]
    except Exception:
        call_script = ""

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
                patient_id or claim_id,
                patient,
                shortfall,
                "high",
                "open",
                notes[:500],
            ),
        )
    return {
        "ok": True,
        "seeded": True,
        "id": entry_id,
        "source": "fee_underpay",
        "balance": shortfall,
        "callScript": call_script,
        "summary": (
            f"Seeded underpay follow-up ${shortfall:,.2f} for {patient} (collections queue — staff contact)."
            + (f"\nCall script: {call_script}" if call_script else "")
        ),
    }


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
    era = list_pending_era_matches(store, limit=25) if store else {"items": [], "count": 0}
    era_items = era.get("items") or []
    claims_ops = _claims_ops_snapshot()
    posting_pending: list[dict[str, Any]] = []
    posting_metrics: dict[str, Any] = {}
    if store:
        try:
            from accounting_bridge import list_posting_queue

            pq = list_posting_queue(store.db_path, limit=25, status="pending_review")
            posting_pending = list(pq.get("items") or [])
            posting_metrics = pq.get("metrics") if isinstance(pq.get("metrics"), dict) else {}
        except Exception:
            posting_pending = []
    underpay_items = [
        i
        for i in open_items
        if "underpay" in str(i.get("notes") or "").lower() or str(i.get("source") or "") == "fee_underpay"
    ]
    odbc_brief = _softdent_named_payer_brief()
    lines = [
        f"# HAL Shift Handoff — {_utc_now()}",
        f"Employee: {employee_id}",
        "",
        "## Import Health",
        f"- {heal_note}",
        f"- SoftDent claims/ODBC: {odbc_brief.get('summary') or 'status unavailable'}",
        "",
        "## ERA/EOB Pending Review",
    ]
    if era_items:
        lines.append(f"- {len(era_items)} match(es) need staff confirm before posting.")
        for item in era_items[:8]:
            lines.append(
                f"- {item.get('referenceId') or item.get('id')} → claim "
                f"{item.get('predictedClaimId') or '?'} · {item.get('status')} · "
                f"{item.get('confidenceBadge') or '?'}"
            )
        lines.append("- Ask HAL: confirm ERA match <id> to claim <ClaimId>")
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Claims Ops",
            f"- Total {claims_ops['total']} · Denied {claims_ops['denied']} · "
            f"Carrier gap (generic Insurance) {claims_ops['genericPayer']} · Named {claims_ops['namedPayer']}",
            f"- Aging ≥60d: {claims_ops['agingOver60']} · ≥90d: {claims_ops['agingOver90']}",
        ]
    )
    for row in claims_ops.get("topAging") or []:
        lines.append(f"- {row.get('claimId')} · {row.get('ageDays')}d · {row.get('status')}")
    if claims_ops["denied"]:
        lines.append("- Ask HAL: build appeal packet / prepare denial finish-line for a denied claim")
    lines.extend(["", "## Posting Queue (pending review)"])
    if posting_pending:
        lines.append(f"- {len(posting_pending)} journal(s) awaiting staff approve/export.")
        for entry in posting_pending[:8]:
            lines.append(
                f"- {entry.get('queue_id') or entry.get('id')}: "
                f"${entry.get('amount', 0)} · {entry.get('description') or 'journal'}"
            )
        lines.append("- Ask HAL: list posting queue / batch approve postings (consent-gated)")
    else:
        lines.append("- None")
    if underpay_items:
        lines.extend(["", "## Fee underpay follow-ups"])
        for item in underpay_items[:8]:
            lines.append(
                f"- {item.get('patientName')}: ${item.get('balance', 0)} — {item.get('notes') or 'underpay'}"
            )
    lines.extend(["", "## Collections (open)"])
    for item in open_items[:15]:
        lines.append(
            f"- [{item.get('priority') or 'normal'}] {item.get('patientName') or item.get('patient_id')}: "
            f"${item.get('balance', 0)}"
            + (f" · {item.get('bucket')}" if item.get("bucket") else "")
        )
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
        detail = str(task.get("detail") or "")[:80]
        lines.append(
            f"- [{task.get('priority') or 'medium'}] {task.get('title') or task.get('id')}"
            + (f" — {detail}" if detail else "")
        )
    if not open_tasks:
        lines.append("- None")
    report = "\n".join(lines)
    open_item_count = (
        len(open_items) + len(era_items) + len(posting_pending) + int(claims_ops.get("denied") or 0)
    )
    return {
        "ok": True,
        "reportMarkdown": report,
        "openItemCount": open_item_count,
        "openCollections": len(open_items),
        "openMonthEndTasks": len(open_tasks),
        "pendingEraMatches": len(era_items),
        "pendingPostings": len(posting_pending),
        "postingMetrics": posting_metrics,
        "underpayFollowUps": len(underpay_items),
        "claimsOps": claims_ops,
        "softdentOdbc": odbc_brief,
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


def confirm_era_match(store, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Staff confirms a pending ERA/EOB match → matched + optional posting queue seed.

    Does not post to QuickBooks live — only enqueues local journal for review.
    """
    if not store:
        return {"ok": False, "error": "no_store"}
    data = payload if isinstance(payload, dict) else {}
    match_id = str(
        data.get("matchId") or data.get("id") or data.get("eraLineId") or data.get("era_line_id") or ""
    ).strip()
    claim_id = str(
        data.get("claimId") or data.get("claim_id") or data.get("correctedClaimId") or data.get("matchedClaimId") or ""
    ).strip()
    if not match_id:
        return {"ok": False, "error": "match_id_required", "summary": "Need pending ERA match id to confirm."}

    with store._connect() as conn:
        init_employee_workflow_schemas(conn)
        row = conn.execute(
            """
            SELECT id, created_at_utc, source_type, reference_id, matched_claim_id, status, detail_json
            FROM nr2_eob_match WHERE id = ?
            """,
            (match_id,),
        ).fetchone()
        if not row:
            # Allow lookup by reference_id
            row = conn.execute(
                """
                SELECT id, created_at_utc, source_type, reference_id, matched_claim_id, status, detail_json
                FROM nr2_eob_match
                WHERE reference_id = ? AND status IN ('pending', 'review')
                ORDER BY created_at_utc DESC LIMIT 1
                """,
                (match_id,),
            ).fetchone()
        if not row:
            return {"ok": False, "error": "match_not_found", "summary": f"No pending ERA/EOB match for {match_id}."}
        match_id = str(row[0])
        try:
            detail = json.loads(row[6] or "{}")
        except json.JSONDecodeError:
            detail = {}
        predicted = str(row[4] or detail.get("claimId") or "")
        if not claim_id:
            claim_id = predicted
        if not claim_id:
            return {
                "ok": False,
                "error": "claim_id_required",
                "summary": "Confirm needs a claim id (predicted empty) — pass claimId.",
                "matchId": match_id,
            }
        paid = _parse_money(data.get("paidAmount") or detail.get("paidAmount") or detail.get("paid"))
        detail.update(
            {
                "claimId": claim_id,
                "paidAmount": paid if paid else detail.get("paidAmount"),
                "confirmedAt": _utc_now(),
                "confirmedBy": str(data.get("actor") or "Staff"),
                "matchConfidence": "high",
                "confidenceScore": max(float(detail.get("confidenceScore") or 0), 0.9),
            }
        )
        conn.execute(
            """
            UPDATE nr2_eob_match
            SET matched_claim_id = ?, status = ?, detail_json = ?
            WHERE id = ?
            """,
            (claim_id, "matched", json.dumps(detail), match_id),
        )

    feedback = record_era_match_feedback_api(
        store,
        {
            "eraLineId": match_id,
            "predictedClaimId": predicted,
            "correctedClaimId": claim_id if claim_id != predicted else "",
            "approved": True,
            "confidence": detail.get("confidenceScore") or 0.9,
        },
    )

    posting = None
    paid_final = _parse_money(detail.get("paidAmount"))
    if paid_final > 0 and claim_id:
        try:
            from accounting_bridge import enqueue_journal_posting, parse_context_json

            posting = enqueue_journal_posting(
                store.db_path,
                description=f"ERA/EOB confirmed match {detail.get('referenceId') or match_id}",
                period="",
                amount=paid_final,
                actor=str(data.get("actor") or "HAL"),
                context=parse_context_json(
                    json.dumps({"eobMatchId": match_id, "claimId": claim_id, "confirmed": True})
                ),
                enqueue_mode="manual_review_queue",
            )
        except Exception as exc:
            posting = {"ok": False, "error": str(exc)}

    fee_scrub = None
    if paid_final > 0 and (data.get("cdt") or data.get("procedure")):
        try:
            fee_scrub = scrub_fee_vs_paid(
                {
                    "cdt": data.get("cdt") or data.get("cdtCode") or "",
                    "procedure": data.get("procedure") or "",
                    "payer": data.get("payer") or "",
                    "paidAmount": paid_final,
                    "billedAmount": data.get("billedAmount"),
                    "remark": data.get("remark") or "",
                    "claimId": claim_id,
                    "patientName": data.get("patientName") or data.get("patient") or "",
                    "patientId": data.get("patientId") or "",
                },
                store=store,
            )
        except Exception:
            fee_scrub = None

    summary = (
        f"Confirmed ERA/EOB match {match_id}: → claim {claim_id}"
        + (f" · paid ${paid_final:,.2f}" if paid_final else "")
        + (" · posting queued for review" if posting and posting.get("ok") is not False else "")
        + ". Nothing posted live to QuickBooks."
    )
    if fee_scrub and fee_scrub.get("ok"):
        summary += f" Fee scrub: {fee_scrub.get('classification')}."
        if fee_scrub.get("collectionsSeed") and fee_scrub["collectionsSeed"].get("seeded"):
            summary += " Underpay seeded to collections."

    return {
        "ok": True,
        "matchId": match_id,
        "claimId": claim_id,
        "status": "matched",
        "detail": detail,
        "feedback": feedback,
        "posting": posting,
        "feeScrub": fee_scrub,
        "summary": summary,
        "localOnly": True,
    }


def list_pending_era_matches(store, *, limit: int = 25) -> dict[str, Any]:
    if not store:
        return {"ok": False, "items": []}
    conn = store._connect()
    init_employee_workflow_schemas(conn)
    cur = conn.execute(
        """
        SELECT id, created_at_utc, source_type, reference_id, matched_claim_id, status, detail_json
        FROM nr2_eob_match
        WHERE status IN ('pending', 'review')
        ORDER BY created_at_utc DESC
        LIMIT ?
        """,
        (max(1, min(int(limit or 25), 100)),),
    )
    items = []
    for row in cur.fetchall():
        try:
            detail = json.loads(row[6] or "{}")
        except json.JSONDecodeError:
            detail = {}
        conf = float(detail.get("confidenceScore") or 0)
        if conf >= 0.85:
            badge = "high"
        elif conf >= 0.6:
            badge = "medium"
        else:
            badge = "low"
        items.append(
            {
                "id": row[0],
                "eraLineId": row[0],
                "createdAt": row[1],
                "sourceType": row[2],
                "referenceId": row[3],
                "predictedClaimId": row[4],
                "status": row[5],
                "confidence": conf,
                "confidenceBadge": badge,
                "paidAmount": detail.get("paidAmount"),
            }
        )
    return {"ok": True, "items": items, "count": len(items)}


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


def _ar_bucket_rank(bucket: str) -> int:
    b = str(bucket or "").lower()
    if "90" in b or "120" in b or "+" in b:
        return 0
    if "61" in b or "60-90" in b or "61-90" in b:
        return 1
    if "31" in b or "30-60" in b or "31-60" in b:
        return 2
    if "0-30" in b or "current" in b:
        return 3
    return 2


def generate_collections_queue(store, *, limit: int = 25) -> dict[str, Any]:
    if not store:
        return {"ok": False, "error": "no_store"}
    rows = _load_ar_rows(store.db_path)
    ranked: list[dict[str, Any]] = []
    for row in rows:
        balance = _parse_money(
            row.get("Balance") or row.get("Outstanding") or row.get("amount") or row.get("Amount")
        )
        if balance <= 0:
            continue
        bucket = str(row.get("Aging") or row.get("Bucket") or row.get("bucket") or "")
        patient = str(
            row.get("Patient")
            or row.get("patient")
            or row.get("PatientName")
            or row.get("Name")
            or row.get("bucket")
            or "Unknown"
        )
        phone = str(row.get("Phone") or row.get("phone") or row.get("HomePhone") or "").strip()
        priority = "high" if _ar_bucket_rank(bucket) <= 1 or balance >= 500 else "normal"
        ranked.append(
            {
                "patientId": str(row.get("PatientId") or row.get("patient_id") or row.get("id") or ""),
                "patientName": patient,
                "balance": balance,
                "bucket": bucket or "Unknown",
                "priority": priority,
                "phone": phone,
                "_rank": (_ar_bucket_rank(bucket), -balance),
            }
        )
    ranked.sort(key=lambda r: r["_rank"])
    items: list[dict[str, Any]] = []
    with store._connect() as conn:
        init_employee_workflow_schemas(conn)
        for row in ranked[: max(1, min(int(limit or 25), 100))]:
            entry_id = str(uuid.uuid4())
            notes = f"A/R bucket {row['bucket']}".strip()
            if row.get("phone"):
                notes += f" · phone {row['phone']}"
            conn.execute(
                """
                INSERT OR REPLACE INTO nr2_collections_queue
                (id, created_at_utc, patient_id, patient_name, balance, priority, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    _utc_now(),
                    row["patientId"],
                    row["patientName"],
                    row["balance"],
                    row["priority"],
                    "open",
                    notes,
                ),
            )
            call_script = ""
            try:
                from voip_actions import get_voice_script

                scenario = "underpay" if "underpay" in notes.lower() else "collections"
                scripted = get_voice_script(
                    scenario,
                    patient_name=row["patientName"],
                    balance=f"${row['balance']:,.2f}",
                )
                call_script = str(scripted.get("script") or "")
            except Exception:
                call_script = ""
            items.append(
                {
                    "id": entry_id,
                    "patientName": row["patientName"],
                    "patientId": row["patientId"],
                    "balance": row["balance"],
                    "bucket": row["bucket"],
                    "priority": row["priority"],
                    "phone": row.get("phone") or "",
                    "status": "open",
                    "notes": notes,
                    "callScript": call_script,
                }
            )
    high = sum(1 for i in items if i.get("priority") == "high")
    total_bal = round(sum(float(i.get("balance") or 0) for i in items), 2)
    summary = (
        f"Collections call list: {len(items)} account(s) · ${total_bal:,.2f} · {high} high priority. "
        "Staff owns patient contact — HAL drafts locally only. Scripts attached per row."
        if items
        else "No positive A/R balances flagged for collections in the current import."
    )
    return {
        "ok": True,
        "items": items,
        "count": len(items),
        "highPriorityCount": high,
        "totalBalance": total_bal,
        "summary": summary,
    }


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
    items: list[dict[str, Any]] = []
    for r in rows:
        notes = str(r[7] or "")
        scenario = "underpay" if "underpay" in notes.lower() else "collections"
        call_script = ""
        try:
            from voip_actions import get_voice_script

            scripted = get_voice_script(
                scenario,
                patient_name=str(r[3] or ""),
                balance=f"${float(r[4] or 0):,.2f}",
            )
            call_script = str(scripted.get("script") or "")
        except Exception:
            call_script = ""
        # Prefer script already embedded in notes after "Script:"
        if "script:" in notes.lower():
            idx = notes.lower().rfind("script:")
            embedded = notes[idx + len("script:") :].strip()
            if embedded:
                call_script = embedded
        items.append(
            {
                "id": r[0],
                "createdAtUtc": r[1],
                "patientId": r[2],
                "patientName": r[3],
                "balance": r[4],
                "priority": r[5],
                "status": r[6],
                "notes": notes,
                "callScript": call_script,
                "source": "fee_underpay" if "underpay" in notes.lower() else "ar",
            }
        )
    return {"ok": True, "items": items, "count": len(items)}


def _seed_deposit_amounts_from_analytics(data: dict[str, Any]) -> dict[str, Any]:
    """Fill bank/ledger from SoftDent collections vs QB deposits when caller omitted amounts."""
    bank_raw = data.get("bankAmount", data.get("bank_amount", None))
    ledger_raw = data.get("ledgerAmount", data.get("ledger_amount", None))
    has_bank = bank_raw not in (None, "", 0, 0.0, "0")
    has_ledger = ledger_raw not in (None, "", 0, 0.0, "0")
    if has_bank and has_ledger:
        return {"seeded": False, "source": None, "analytics": None}
    try:
        from nr2_analytics import collection_deposit_variance

        analytics = collection_deposit_variance()
    except Exception:
        return {"seeded": False, "source": None, "analytics": None}
    if not analytics or not analytics.get("hasData"):
        return {"seeded": False, "source": None, "analytics": analytics}
    qb = analytics.get("quickbooksDeposits")
    sd = analytics.get("softdentCollections")
    if qb is None or sd is None:
        return {"seeded": False, "source": None, "analytics": analytics}
    if not has_bank:
        data["bankAmount"] = float(qb)
    if not has_ledger:
        data["ledgerAmount"] = float(sd)
    if not str(data.get("depositDate") or data.get("deposit_date") or "").strip():
        data["depositDate"] = str(analytics.get("period") or "")
    return {
        "seeded": True,
        "source": "collection_deposit_variance",
        "analytics": analytics,
    }


def draft_deposit_reconciliation(store, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not store:
        return {"ok": False, "error": "no_store"}
    data = dict(payload) if isinstance(payload, dict) else {}
    seed = _seed_deposit_amounts_from_analytics(data)
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
        "seededFromAnalytics": bool(seed.get("seeded")),
        "seedSource": seed.get("source"),
    }
    analytics = seed.get("analytics") if isinstance(seed.get("analytics"), dict) else None
    if analytics and analytics.get("summary"):
        draft["analyticsSummary"] = analytics.get("summary")
        draft["variancePct"] = analytics.get("variancePct")
    if abs(variance) > 0.01:
        draft["suggestedActions"].append("Review unmatched deposits and same-day patient payments.")
    if variance > 0:
        draft["suggestedActions"].append("Bank total exceeds ledger — check unposted deposits.")
    elif variance < 0:
        draft["suggestedActions"].append("Ledger exceeds bank — verify duplicate postings.")
    if seed.get("seeded"):
        draft["suggestedActions"].append(
            "Amounts seeded from SoftDent collections vs QuickBooks deposits analytics — confirm period before posting."
        )
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
    return {
        "ok": True,
        "id": entry_id,
        "draft": draft,
        "variance": variance,
        "seededFromAnalytics": bool(seed.get("seeded")),
    }


def _match_eligibility_for_claim(
    *,
    payer: str = "",
    patient_id: str = "",
    patient: str = "",
) -> dict[str, Any] | None:
    """Best-effort fresh eligibility-cache hit for preflight (payer-first; never invents benefits)."""
    if not payer or payer.lower() in {"", "insurance", "unknown", "n/a", "-", "—"}:
        return None
    try:
        from eligibility_cache_store import search_eligibility_cache

        query = " ".join(p for p in (payer, patient_id, patient) if p).strip()
        hits = search_eligibility_cache(query or payer, limit=3)
    except Exception:
        return None
    if not hits:
        return None
    top = hits[0]
    return {
        "payerName": top.get("payerName"),
        "payerId": top.get("payerId"),
        "planDescription": top.get("planDescription"),
        "deductibleRemaining": top.get("deductibleRemaining"),
        "annualMaxRemaining": top.get("annualMaxRemaining"),
        "coinsuranceBasic": top.get("coinsuranceBasic"),
        "coinsuranceMajor": top.get("coinsuranceMajor"),
        "cachedAt": top.get("cachedAt"),
        "limitations": top.get("limitations"),
    }


def _infer_claim_preflight_checklist(data: dict[str, Any]) -> dict[str, Any]:
    """Derive checklist from claim fields when caller didn't supply booleans."""
    payer = str(data.get("payer") or data.get("Payer") or "").strip()
    generic_payer = payer.lower() in {"", "insurance", "unknown", "n/a", "-", "—"}
    procedure = str(data.get("procedure") or data.get("Procedure") or "").strip()
    cdt = str(data.get("cdt") or data.get("cdtCode") or "").strip().upper()
    if not cdt:
        m = re.search(r"\b(D\d{4})\b", procedure, re.I)
        cdt = m.group(1).upper() if m else ""
    narrative = bool(
        data.get("narrativePresent")
        if "narrativePresent" in data
        else (data.get("narrative") or data.get("clinicalNote") or data.get("clinicalSummaryLinked"))
    )
    attachments = bool(data.get("attachmentsReady")) if "attachmentsReady" in data else False
    clinical = bool(
        data.get("clinicalSummaryLinked")
        if "clinicalSummaryLinked" in data
        else (data.get("clinicalNote") or narrative)
    )
    eligibility_hit = None
    if "insuranceVerified" in data:
        insurance_verified = bool(data.get("insuranceVerified"))
    else:
        # Named payer alone is not eligibility — join fresh cache when present.
        eligibility_hit = _match_eligibility_for_claim(
            payer=payer,
            patient_id=str(data.get("patientId") or data.get("patient_id") or ""),
            patient=str(data.get("patient") or data.get("PatientName") or ""),
        )
        insurance_verified = bool(eligibility_hit)

    fee_verified = bool(data.get("feeScheduleVerified")) if "feeScheduleVerified" in data else False
    fee_detail = None
    if not fee_verified and cdt and not generic_payer:
        try:
            from fee_schedule_store import lookup_cdt

            hit = lookup_cdt(cdt, payer)
            if hit.get("ok") and hit.get("amounts"):
                fee_verified = True
                fee_detail = {
                    "code": cdt,
                    "schedule": (hit.get("amounts") or [{}])[0].get("scheduleName"),
                    "amount": (hit.get("amounts") or [{}])[0].get("amount"),
                }
        except Exception:
            pass

    checklist = {
        "narrativePresent": narrative,
        "attachmentsReady": attachments,
        "feeScheduleVerified": fee_verified,
        "insuranceVerified": insurance_verified,
        "clinicalSummaryLinked": clinical,
        "namedPayerPresent": bool(payer) and not generic_payer,
    }
    gaps: list[str] = []
    if not checklist["namedPayerPresent"]:
        gaps.append("Named payer missing (generic Insurance) — SoftDent claims export / InsCo needed")
    if not checklist["insuranceVerified"]:
        if checklist["namedPayerPresent"]:
            gaps.append("Eligibility not verified — no fresh cache hit for this payer (run 271 or paste redacted snapshot)")
        else:
            gaps.append("Insurance / eligibility not verified")
    if not checklist["narrativePresent"]:
        gaps.append("Narrative / clinical note missing")
    if not checklist["feeScheduleVerified"]:
        gaps.append("Fee schedule not verified for CDT/carrier")
    if not checklist["attachmentsReady"]:
        gaps.append("Attachments not confirmed ready")
    if not checklist["clinicalSummaryLinked"]:
        gaps.append("Clinical summary not linked")
    return {
        "checklist": checklist,
        "gaps": gaps,
        "cdt": cdt or None,
        "genericPayer": generic_payer,
        "feeDetail": fee_detail,
        "eligibilityHit": eligibility_hit,
    }


def _load_clinical_note_rows() -> list[dict[str, Any]]:
    try:
        from import_loader import load_import_bundle

        bundle = load_import_bundle(sync=False, deep=False)
        sd = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
        clinical = sd.get("clinicalNotes") if isinstance(sd.get("clinicalNotes"), dict) else {}
        rows = clinical.get("rows") if isinstance(clinical.get("rows"), list) else []
        return [r for r in rows if isinstance(r, dict)]
    except Exception:
        return []


def _find_clinical_notes_for_claim(
    *,
    patient: str = "",
    patient_id: str = "",
    procedure: str = "",
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Match SoftDent clinical-notes export rows to a claim patient/procedure."""
    rows = _load_clinical_note_rows()
    if not rows:
        return []
    pat = str(patient or "").strip().lower()
    pid = str(patient_id or "").strip().lower()
    proc_tokens = set(re.findall(r"[a-z0-9]{3,}", str(procedure or "").lower()))
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        name = str(row.get("PatientName") or row.get("patient") or "").strip().lower()
        mrn = str(row.get("MRN") or row.get("patientId") or row.get("PatientId") or "").strip().lower()
        note = str(row.get("ClinicalNote") or row.get("clinicalNote") or row.get("NoteText") or "").strip()
        if not note:
            continue
        score = 0
        if pid and mrn and (pid == mrn or pid in mrn or mrn in pid):
            score += 8
        if pat and name:
            if pat == name:
                score += 6
            elif pat in name or name in pat:
                score += 4
            else:
                # last-name token overlap
                pat_parts = set(pat.replace(",", " ").split())
                name_parts = set(name.replace(",", " ").split())
                if pat_parts & name_parts:
                    score += 2
        if proc_tokens:
            proc_hay = str(row.get("Procedure") or row.get("procedure") or note).lower()
            overlap = sum(1 for t in proc_tokens if t in proc_hay)
            score += min(3, overlap)
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda pair: -pair[0])
    out: list[dict[str, Any]] = []
    for score, row in scored[: max(1, int(limit))]:
        out.append(
            {
                "patientName": row.get("PatientName") or row.get("patient"),
                "mrn": row.get("MRN") or row.get("patientId"),
                "noteDate": row.get("NoteDate") or row.get("noteDate"),
                "provider": row.get("Provider") or row.get("provider"),
                "procedure": row.get("Procedure") or row.get("procedure"),
                "clinicalNote": str(row.get("ClinicalNote") or row.get("clinicalNote") or row.get("NoteText") or ""),
                "matchScore": score,
            }
        )
    return out


def _claim_age_days(row: dict[str, Any]) -> int | None:
    for key in ("Days", "days", "Age", "age", "ageDays"):
        if row.get(key) not in (None, ""):
            try:
                return int(float(str(row.get(key)).replace(",", "")))
            except ValueError:
                pass
    dos = str(row.get("ServiceDate") or row.get("serviceDate") or "")[:10]
    if dos:
        try:
            from datetime import date as _date

            d = _date.fromisoformat(dos)
            return max(0, (datetime.now(timezone.utc).date() - d).days)
        except ValueError:
            return None
    return None


def _load_claim_rows_for_autonomy() -> list[dict[str, Any]]:
    try:
        from import_loader import load_import_bundle

        bundle = load_import_bundle(sync=False, deep=False)
        sd = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
        claims = sd.get("claims") if isinstance(sd.get("claims"), dict) else {}
        rows = claims.get("rows") if isinstance(claims.get("rows"), list) else []
        return [r for r in rows if isinstance(r, dict)]
    except Exception:
        return []


def stage_pending_appeal_packets(store, *, limit: int = 5) -> dict[str, Any]:
    """Autonomously stage local appeal packets for denied / aging named-payer claims.

    Writes JSON under exports/staged_appeals/. Does NOT build consent zip or dial/submit.
    """
    from pathlib import Path

    try:
        from outbound_actions import _exports_subdir

        out_dir = _exports_subdir("staged_appeals")
    except Exception:
        out_dir = Path(__file__).resolve().parent / "app_data" / "nr2" / "exports" / "staged_appeals"
        out_dir.mkdir(parents=True, exist_ok=True)

    cap = max(1, min(int(limit or 5), 10))
    rows = _load_claim_rows_for_autonomy()
    candidates: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        payer = str(row.get("Payer") or row.get("payer") or "").strip()
        if payer.lower() in {"", "insurance", "unknown", "n/a", "-", "—"}:
            continue  # generic daysheet — skip autonomous appeal staging
        status = str(row.get("ClaimStatus") or row.get("status") or row.get("Status") or "")
        age = _claim_age_days(row)
        denied = "denied" in status.lower()
        aging = age is not None and age >= 60
        if not denied and not aging:
            continue
        # Priority: denied first, then older age
        score = (0 if denied else 1, -(age or 0))
        candidates.append((score[0] * 10_000 + score[1], row))
    candidates.sort(key=lambda t: t[0])

    items: list[dict[str, Any]] = []
    for _, row in candidates[:cap]:
        claim_id = str(row.get("ClaimId") or row.get("claimId") or row.get("id") or "").strip()
        if not claim_id:
            continue
        packet = build_appeal_packet(
            store,
            {
                "claimId": claim_id,
                "payer": row.get("Payer") or row.get("payer") or "",
                "procedure": row.get("Procedure") or row.get("procedure") or "",
                "status": row.get("ClaimStatus") or row.get("status") or "",
                "denialReason": row.get("DenialReason") or row.get("denialReason") or "",
                "patient": row.get("PatientName") or row.get("patient") or "",
                "amount": row.get("ClaimAmount") or row.get("amount") or "",
            },
        )
        if not packet.get("ok"):
            continue
        slim = {
            "claimId": packet.get("claimId"),
            "stagedAt": _utc_now(),
            "localOnly": True,
            "notSubmitted": True,
            "consentRequiredForZip": True,
            "claim": packet.get("claim"),
            "narrative": packet.get("narrative"),
            "gaps": packet.get("gaps"),
            "preflight": packet.get("preflight"),
            "denialRisk": {
                "riskScore": (packet.get("denialRisk") or {}).get("riskScore"),
                "flags": (packet.get("denialRisk") or {}).get("flags"),
                "genericPayer": (packet.get("denialRisk") or {}).get("genericPayer"),
            },
            "payerJoin": packet.get("payerJoin"),
            "clinicalNotesAttached": packet.get("clinicalNotesAttached"),
            "finishLine": packet.get("finishLine"),
            "summary": packet.get("summary"),
        }
        safe_name = claim_id.replace("/", "-").replace("\\", "-")
        path = out_dir / f"{safe_name}_appeal.json"
        try:
            path.write_text(json.dumps(slim, indent=2), encoding="utf-8")
        except OSError as exc:
            items.append({"claimId": claim_id, "ok": False, "error": str(exc)})
            continue
        status = str(row.get("ClaimStatus") or row.get("status") or "")
        items.append(
            {
                "ok": True,
                "claimId": claim_id,
                "path": str(path),
                "payer": row.get("Payer") or row.get("payer"),
                "denied": "denied" in status.lower(),
                "ageDays": _claim_age_days(row),
                "summary": f"Staged local appeal for {claim_id} → {path.name} (zip still needs consent).",
            }
        )

    return {
        "ok": True,
        "count": len(items),
        "items": items,
        "localOnly": True,
        "notSubmitted": True,
        "summary": (
            f"Staged {len(items)} local appeal packet(s) under staged_appeals/ — staff consent for zip/portal."
            if items
            else "No named-payer denied/aging claims available to stage."
        ),
    }


def build_appeal_packet(store, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Assemble a local denial/appeal packet: claim facts + preflight + denial risk + payer/fee.

    Does not submit. Zip export still requires staff consent via outbound claim-packet.
    """
    data = dict(payload) if isinstance(payload, dict) else {}
    claim_id = str(data.get("claimId") or data.get("claim_id") or data.get("id") or "").strip()
    claim_row: dict[str, Any] = {}
    if claim_id:
        try:
            from outbound_actions import _load_claim_row

            loaded = _load_claim_row(claim_id)
            if isinstance(loaded, dict):
                claim_row = loaded
        except Exception:
            claim_row = {}
    # Merge explicit payload over CSV row
    for key in (
        "payer",
        "Payer",
        "procedure",
        "Procedure",
        "status",
        "Status",
        "narrative",
        "clinicalNote",
        "denialReason",
        "DenialReason",
        "patientId",
        "patient",
        "PatientName",
        "cdt",
        "amount",
        "ClaimAmount",
    ):
        if data.get(key) not in (None, ""):
            claim_row[key] = data.get(key)

    payer = str(claim_row.get("payer") or claim_row.get("Payer") or data.get("payer") or "").strip()
    procedure = str(claim_row.get("procedure") or claim_row.get("Procedure") or "").strip()
    status = str(claim_row.get("status") or claim_row.get("Status") or claim_row.get("ClaimStatus") or "").strip()
    denial_reason = str(
        claim_row.get("denialReason") or claim_row.get("DenialReason") or data.get("denialReason") or ""
    ).strip()
    patient_name = str(
        claim_row.get("PatientName")
        or claim_row.get("patient")
        or data.get("patient")
        or data.get("PatientName")
        or ""
    ).strip()
    patient_id = str(data.get("patientId") or claim_row.get("patientId") or claim_row.get("MRN") or "").strip()
    clinical_hits = _find_clinical_notes_for_claim(
        patient=patient_name,
        patient_id=patient_id,
        procedure=procedure,
        limit=3,
    )
    clinical_note_text = "\n\n".join(
        f"[{h.get('noteDate') or 'note'}] {h.get('clinicalNote')}" for h in clinical_hits if h.get("clinicalNote")
    ).strip()

    narrative = str(
        data.get("narrative")
        or claim_row.get("narrative")
        or claim_row.get("clinicalNote")
        or clinical_note_text
        or ""
    ).strip()
    narrative_draft: dict[str, Any] | None = None
    if clinical_hits and narrative == clinical_note_text:
        narrative_draft = {
            "ok": True,
            "focus": "Denial Appeal",
            "source": "softdent_clinical_notes",
            "noteCount": len(clinical_hits),
        }
    # Auto-draft Denial Appeal narrative when missing (local text only).
    if not narrative and data.get("skipNarrativeDraft") not in (True, "true", "1"):
        try:
            # Lazy import path used by site skills is JS; use a minimal Python draft.
            cdt = str(data.get("cdt") or "").strip().upper()
            if not cdt:
                m = re.search(r"\b(D\d{4})\b", procedure, re.I)
                cdt = m.group(1).upper() if m else ""
            parts = [
                "DENIAL APPEAL DRAFT (local — staff must review before portal upload)",
                f"Claim: {claim_id or 'n/a'}",
                f"Payer: {payer or 'verify InsCo'}",
                f"Procedure: {procedure or 'n/a'}" + (f" ({cdt})" if cdt else ""),
            ]
            if denial_reason:
                parts.append(f"Denial reason on file: {denial_reason}")
            payer_themes: list[str] = []
            try:
                from payer_reference_store import enrich_claim_payer

                early_join = enrich_claim_payer(payer) if payer else None
                if early_join:
                    if early_join.get("narrativeNotes"):
                        payer_themes.append(f"Payer narrative themes: {early_join['narrativeNotes']}")
                    codes = early_join.get("commonDenialCodes") or []
                    if codes:
                        payer_themes.append("Common denial themes: " + ", ".join(str(c) for c in codes[:6]))
            except Exception:
                early_join = None
            parts.extend(
                [
                    "",
                    "Clinical necessity (staff complete from chart):",
                    "- Document diagnosis, tooth/site, and why the service was required.",
                    "- Reference pre-op radiograph date and findings.",
                    "- Note prior treatment and current clinical status.",
                ]
            )
            if payer_themes:
                parts.append("")
                parts.extend(payer_themes)
            parts.extend(
                [
                    "",
                    "Request: reconsideration / overturn of denial with attached documentation.",
                ]
            )
            narrative = "\n".join(parts)
            narrative_draft = {
                "ok": True,
                "focus": "Denial Appeal",
                "source": "hal_appeal_scaffold",
                "payerThemes": bool(payer_themes),
            }
        except Exception:
            narrative_draft = None
    elif clinical_note_text and narrative_draft and narrative_draft.get("source") == "softdent_clinical_notes":
        # Wrap imported notes in appeal framing
        cdt = str(data.get("cdt") or "").strip().upper()
        if not cdt:
            m = re.search(r"\b(D\d{4})\b", procedure, re.I)
            cdt = m.group(1).upper() if m else ""
        theme_lines: list[str] = []
        try:
            from payer_reference_store import enrich_claim_payer

            pj = enrich_claim_payer(payer) if payer else None
            if pj and pj.get("narrativeNotes"):
                theme_lines.append(f"Payer narrative themes: {pj['narrativeNotes']}")
            if pj and pj.get("commonDenialCodes"):
                theme_lines.append(
                    "Common denial themes: " + ", ".join(str(c) for c in (pj.get("commonDenialCodes") or [])[:6])
                )
        except Exception:
            theme_lines = []
        narrative = "\n".join(
            [
                "DENIAL APPEAL DRAFT (from SoftDent clinical notes — staff must review)",
                f"Claim: {claim_id or 'n/a'} · Payer: {payer or 'verify InsCo'}",
                f"Procedure: {procedure or 'n/a'}" + (f" ({cdt})" if cdt else ""),
                f"Denial reason: {denial_reason or 'n/a'}",
                "",
                "Chart notes on file:",
                clinical_note_text,
                *([""] + theme_lines if theme_lines else []),
                "",
                "Request: reconsideration / overturn of denial with attached documentation.",
            ]
        )

    preflight_payload = {
        "claimId": claim_id,
        "patientId": patient_id,
        "payer": payer,
        "procedure": procedure,
        "cdt": data.get("cdt") or claim_row.get("cdt") or "",
        "narrative": narrative,
        "clinicalNote": clinical_note_text or claim_row.get("clinicalNote") or "",
        "narrativePresent": bool(narrative) if narrative else data.get("narrativePresent"),
        "attachmentsReady": data.get("attachmentsReady"),
        "feeScheduleVerified": data.get("feeScheduleVerified"),
        "insuranceVerified": data.get("insuranceVerified"),
        "clinicalSummaryLinked": True if clinical_hits else data.get("clinicalSummaryLinked"),
    }
    # Infer without persisting when store missing; otherwise stage for audit trail
    if store:
        preflight = stage_claim_preflight(store, preflight_payload)
    else:
        inferred = _infer_claim_preflight_checklist(preflight_payload)
        preflight = {
            "ok": True,
            "status": "staged",
            "checklist": inferred["checklist"],
            "gaps": inferred["gaps"],
            "cdt": inferred.get("cdt"),
            "genericPayer": inferred.get("genericPayer"),
            "feeDetail": inferred.get("feeDetail"),
            "eligibilityHit": inferred.get("eligibilityHit"),
            "ready": False,
        }

    denial: dict[str, Any] = {}
    try:
        from era_denial_trainer import predict_denial_risk

        denial = predict_denial_risk(
            claim={
                "id": claim_id,
                "payer": payer,
                "procedure": procedure,
                "narrative": narrative,
                "status": status,
                "denialReason": denial_reason,
                "cdt": preflight.get("cdt") or data.get("cdt") or "",
            },
            has_narrative=bool(narrative),
        )
    except Exception as exc:
        denial = {"ok": False, "error": str(exc)}

    payer_join = None
    if payer:
        try:
            from payer_reference_store import enrich_claim_payer

            payer_join = enrich_claim_payer(payer)
        except Exception:
            payer_join = None

    staff_steps = [
        "Review narrative draft and claim facts — nothing has been submitted.",
        "Confirm named payer / InsCo and fee schedule for the CDT.",
        "Attach radiographs / perio charting required by the denial reason.",
        "With staff consent, build the local claim packet zip for portal upload.",
    ]
    gaps = list(preflight.get("gaps") or [])
    if denial.get("genericPayer"):
        gaps.append("Generic payer blocks reliable appeal routing")
    if denial.get("highRisk"):
        gaps.append(f"High denial risk ({denial.get('riskScore')}) — scrub before resubmit/appeal")

    summary_lines = [
        f"Appeal packet (local only) for claim {claim_id or '?'}:",
        f"- Status: {status or 'unknown'} · Payer: {payer or 'Insurance (generic?)'}",
        f"- Preflight: {preflight.get('status')} · Ready: {bool(preflight.get('ready'))}",
    ]
    if preflight.get("cdt"):
        summary_lines.append(f"- CDT: {preflight.get('cdt')}")
    if denial.get("ok"):
        pct = int(round(float(denial.get("riskScore") or 0) * 100))
        flags = ", ".join(denial.get("flags") or []) or "none"
        summary_lines.append(f"- Denial risk: {pct}% · flags: {flags}")
    if payer_join:
        summary_lines.append(
            f"- Payer join: {payer_join.get('claimPayer')} → {payer_join.get('matchedName')}"
        )
        if payer_join.get("eligibilityNotes"):
            summary_lines.append(f"  Contacts: {payer_join['eligibilityNotes']}")
        if payer_join.get("narrativeNotes"):
            summary_lines.append(f"  Narrative themes: {payer_join['narrativeNotes']}")
        if payer_join.get("commonDenialCodes"):
            summary_lines.append(
                "  Common denials: " + ", ".join(str(c) for c in (payer_join.get("commonDenialCodes") or [])[:6])
            )
    elig = preflight.get("eligibilityHit") if isinstance(preflight.get("eligibilityHit"), dict) else None
    if elig:
        summary_lines.append(
            f"- Eligibility cache: {elig.get('payerName')}"
            + (f" · deductible rem ${elig.get('deductibleRemaining')}" if elig.get("deductibleRemaining") is not None else "")
            + (f" · annual max rem ${elig.get('annualMaxRemaining')}" if elig.get("annualMaxRemaining") is not None else "")
        )
    if gaps:
        summary_lines.append("Gaps:")
        summary_lines.extend(f"- {g}" for g in gaps[:8])
    if clinical_hits:
        summary_lines.append(f"- SoftDent clinical notes attached: {len(clinical_hits)} (staff must verify).")
    elif narrative:
        summary_lines.append("- Narrative draft included (staff must edit clinical specifics).")
    summary_lines.append(
        "Next: with staff consent, build claim packet zip "
        "(POST /api/outbound/claim-packet) — HAL does not upload to payer portals."
    )

    return {
        "ok": True,
        "claimId": claim_id,
        "localOnly": True,
        "notSubmitted": True,
        "claim": {
            "id": claim_id,
            "payer": payer,
            "procedure": procedure,
            "status": status,
            "denialReason": denial_reason,
            "patient": claim_row.get("PatientName") or claim_row.get("patient") or data.get("patient"),
            "amount": claim_row.get("ClaimAmount") or claim_row.get("amount") or data.get("amount"),
        },
        "narrative": narrative,
        "narrativeDraft": narrative_draft,
        "clinicalNotes": clinical_hits,
        "clinicalNotesAttached": bool(clinical_hits),
        "preflight": {
            "status": preflight.get("status"),
            "ready": bool(preflight.get("ready")),
            "checklist": preflight.get("checklist") or {},
            "gaps": preflight.get("gaps") or [],
            "cdt": preflight.get("cdt"),
            "feeDetail": preflight.get("feeDetail"),
            "genericPayer": preflight.get("genericPayer"),
            "eligibilityHit": preflight.get("eligibilityHit"),
        },
        "denialRisk": denial,
        "payerJoin": payer_join,
        "staffSteps": staff_steps,
        "gaps": gaps,
        "summary": "\n".join(summary_lines),
        "consentRequiredForZip": True,
        "finishLine": {
            "appealBuilt": True,
            "narrativeReady": bool(narrative),
            "clinicalNotesAttached": bool(clinical_hits),
            "zipNeedsConsent": True,
            "claimId": claim_id,
            "suggestedConsentCommand": f"Build claim packet zip for {claim_id} with consent",
            "pendingConsentReady": bool(claim_id),
        },
    }


def stage_claim_preflight(store, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not store:
        return {"ok": False, "error": "no_store"}
    data = payload if isinstance(payload, dict) else {}
    claim_id = str(data.get("claimId") or data.get("claim_id") or "")
    patient_id = str(data.get("patientId") or data.get("patient_id") or "")
    payer = str(data.get("payer") or data.get("Payer") or "")
    inferred = _infer_claim_preflight_checklist(data)
    checklist = inferred["checklist"]
    # Core five for ready status (named payer is advisory but blocks ready when missing)
    core_ready = all(
        [
            checklist["narrativePresent"],
            checklist["attachmentsReady"],
            checklist["feeScheduleVerified"],
            checklist["insuranceVerified"],
            checklist["clinicalSummaryLinked"],
            checklist["namedPayerPresent"],
        ]
    )
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
                "ready" if core_ready else "staged",
                json.dumps(checklist),
            ),
        )
    return {
        "ok": True,
        "id": entry_id,
        "claimId": claim_id,
        "status": "ready" if core_ready else "staged",
        "checklist": checklist,
        "ready": core_ready,
        "gaps": inferred["gaps"],
        "cdt": inferred.get("cdt"),
        "genericPayer": inferred.get("genericPayer"),
        "feeDetail": inferred.get("feeDetail"),
        "eligibilityHit": inferred.get("eligibilityHit"),
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


def update_collections_queue_status(
    store,
    payload: dict[str, Any] | None = None,
    *,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Flip collections-queue status after a dial/log outcome (local only)."""
    data = payload if isinstance(payload, dict) else {}
    queue_id = str(data.get("queueId") or data.get("queue_id") or data.get("id") or "").strip()
    patient_id = str(data.get("patientId") or data.get("patient_id") or "").strip()
    patient_name = str(data.get("patientName") or data.get("patient_name") or "").strip()
    status = str(data.get("status") or "called").strip().lower() or "called"
    allowed = {
        "open",
        "called",
        "promised",
        "no_answer",
        "closed",
        "call_scheduled",
        "letter_draft",
    }
    if status not in allowed:
        status = "called"
    outcome = str(data.get("outcome") or "").strip()
    notes_extra = str(data.get("notes") or "").strip()
    call_id = str(data.get("callId") or data.get("call_id") or "").strip()

    owns_conn = conn is None
    if owns_conn:
        if not store:
            return {"ok": False, "error": "no_store"}
        conn = store._connect()
    assert conn is not None
    init_employee_workflow_schemas(conn)
    row = None
    if queue_id:
        row = conn.execute(
            """
            SELECT id, patient_id, patient_name, balance, priority, status, notes
            FROM nr2_collections_queue WHERE id = ?
            """,
            (queue_id,),
        ).fetchone()
    if not row and patient_id:
        row = conn.execute(
            """
            SELECT id, patient_id, patient_name, balance, priority, status, notes
            FROM nr2_collections_queue
            WHERE patient_id = ? AND status IN ('open', 'call_scheduled', 'called', 'no_answer', 'promised')
            ORDER BY created_at_utc DESC LIMIT 1
            """,
            (patient_id,),
        ).fetchone()
    if not row and patient_name:
        row = conn.execute(
            """
            SELECT id, patient_id, patient_name, balance, priority, status, notes
            FROM nr2_collections_queue
            WHERE lower(patient_name) = lower(?) AND status IN ('open', 'call_scheduled', 'called', 'no_answer', 'promised')
            ORDER BY created_at_utc DESC LIMIT 1
            """,
            (patient_name,),
        ).fetchone()
    if not row:
        if owns_conn:
            conn.close()
        return {"ok": False, "error": "queue_row_not_found", "summary": "No matching collections queue row to update."}

    entry_id = str(row[0])
    prior_notes = str(row[6] or "")
    stamp_bits = [f"[{_utc_now()[:16]}] status→{status}"]
    if outcome:
        stamp_bits.append(f"outcome={outcome}")
    if call_id:
        stamp_bits.append(f"call={call_id}")
    if notes_extra:
        stamp_bits.append(notes_extra[:120])
    stamp = " · ".join(stamp_bits)
    new_notes = f"{prior_notes}\n{stamp}".strip()[:500]
    conn.execute(
        "UPDATE nr2_collections_queue SET status = ?, notes = ? WHERE id = ?",
        (status, new_notes, entry_id),
    )
    conn.commit()
    if owns_conn:
        conn.close()
    return {
        "ok": True,
        "id": entry_id,
        "status": status,
        "patientId": row[1],
        "patientName": row[2],
        "summary": f"Collections queue {entry_id}: {status}" + (f" ({outcome})" if outcome else ""),
    }


def schedule_call_task(store, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not store:
        return {"ok": False, "error": "no_store"}
    data = payload if isinstance(payload, dict) else {}
    patient_name = str(data.get("patientName") or data.get("patient_name") or "Patient")
    balance = _parse_money(data.get("balance") or 0)
    phone = str(data.get("phone") or data.get("phoneNumber") or data.get("phone_number") or "").strip()
    claim_id = str(data.get("claimId") or data.get("claim_id") or "").strip()
    payer = str(data.get("payer") or data.get("Payer") or "").strip()
    scenario = str(data.get("scenario") or data.get("scriptScenario") or "collections").strip() or "collections"
    if "underpay" in str(data.get("notes") or "").lower() or scenario.lower() in {"underpay", "fee_underpay"}:
        scenario = "underpay"
    elif "aging" in scenario.lower() or "claim" in scenario.lower() or claim_id:
        scenario = "claims_aging"
    entry_id = str(uuid.uuid4())
    try:
        from voip_actions import get_voice_script

        scripted = get_voice_script(
            scenario,
            patient_name=patient_name,
            balance=f"${balance:,.2f}" if balance else "",
        )
        script = str(scripted.get("script") or "")
    except Exception:
        script = ""
    if not script:
        script = (
            f"Hello, may I speak with {patient_name}? "
            f"This is the billing office at New Ridge Family Dental regarding a balance of ${balance:,.2f}. "
            "Do you have a moment to review payment options?"
        )
    note_bits = [script]
    if claim_id:
        note_bits.append(f"claim {claim_id}")
    if payer:
        note_bits.append(f"payer {payer}")
    if phone:
        note_bits.append(f"phone {phone}")
    notes = " · ".join(note_bits)[:500]
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
                str(data.get("patientId") or claim_id or ""),
                patient_name,
                balance,
                str(data.get("priority") or "high"),
                "call_scheduled",
                notes,
            ),
        )
    return {
        "ok": True,
        "id": entry_id,
        "callScript": script,
        "scenario": scenario,
        "phone": phone,
        "claimId": claim_id or None,
        "status": "call_scheduled",
        "summary": (
            f"Call scheduled for {patient_name}"
            + (f" · {scenario}" if scenario else "")
            + (f" · {phone}" if phone else "")
            + f".\nScript: {script}"
        ),
    }


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
    fee_scrub = None
    cdt = str(data.get("cdt") or data.get("cdtCode") or "").strip()
    payer = str(data.get("payer") or data.get("Payer") or "").strip()
    if paid > 0 and (cdt or data.get("procedure")):
        try:
            fee_scrub = scrub_fee_vs_paid(
                {
                    "cdt": cdt,
                    "procedure": data.get("procedure") or "",
                    "payer": payer,
                    "paidAmount": paid,
                    "billedAmount": data.get("billedAmount") or data.get("billed"),
                    "remark": data.get("remark") or data.get("carc") or "",
                    "claimId": claim_id,
                    "patientName": data.get("patientName") or data.get("patient") or "",
                    "patientId": data.get("patientId") or "",
                },
                store=store,
            )
            if fee_scrub.get("ok"):
                detail["feeScrub"] = {
                    "classification": fee_scrub.get("classification"),
                    "allowedAmount": fee_scrub.get("allowedAmount"),
                    "delta": fee_scrub.get("delta"),
                    "scheduleName": fee_scrub.get("scheduleName"),
                }
        except Exception:
            fee_scrub = None
    result = {"ok": True, "id": entry_id, "status": status, "detail": detail}
    if fee_scrub and fee_scrub.get("ok"):
        result["feeScrub"] = fee_scrub
        result["summary"] = (
            f"EOB match {status}: {reference_id or '?'} → {claim_id or '?'}. "
            f"{fee_scrub.get('classification')}: paid ${paid:,.2f} vs allowed ${fee_scrub.get('allowedAmount')}."
        )
        if fee_scrub.get("collectionsSeed") and fee_scrub["collectionsSeed"].get("seeded"):
            result["summary"] += " Underpay seeded to collections."
    return result


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
    """Month-end checklist grounded in live analytics when available."""
    tasks: list[dict[str, Any]] = []
    signals: list[str] = []
    acct_period = str(period or datetime.now(timezone.utc).strftime("%Y-%m"))

    try:
        from daily_closeout import build_daily_closeout

        closeout = build_daily_closeout(store)
        if closeout.get("overall") != "ok":
            tasks.append(
                {
                    "id": "closeout-review",
                    "title": "Review daily closeout blockers",
                    "priority": "high",
                    "detail": closeout.get("summary") or "",
                    "source": "daily_closeout",
                }
            )
            signals.append("closeout_not_ok")
    except Exception:
        pass

    analytics: dict[str, Any] = {}
    try:
        from nr2_analytics import analytics_snapshot

        analytics = analytics_snapshot()
    except Exception:
        analytics = {}

    dep = analytics.get("collectionDepositVariance") if isinstance(analytics, dict) else None
    if isinstance(dep, dict) and dep.get("hasData") and dep.get("variancePct") is not None:
        pct = float(dep.get("variancePct") or 0)
        threshold = float(dep.get("thresholdPct") or 8)
        if abs(pct) > threshold:
            tasks.append(
                {
                    "id": "deposit-recon",
                    "title": "Reconcile SoftDent collections vs QuickBooks deposits",
                    "priority": "high",
                    "detail": dep.get("summary") or f"Variance {pct:+.1f}% exceeds {threshold}%",
                    "source": "collection_deposit_variance",
                    "variancePct": pct,
                }
            )
            signals.append("deposit_variance")
        else:
            tasks.append(
                {
                    "id": "deposit-recon",
                    "title": "Confirm bank deposits balanced (analytics within threshold)",
                    "priority": "low",
                    "detail": dep.get("summary") or f"Variance {pct:+.1f}% within {threshold}%",
                    "source": "collection_deposit_variance",
                    "variancePct": pct,
                }
            )
    else:
        tasks.append(
            {
                "id": "deposit-recon",
                "title": "Reconcile bank deposits to ledger",
                "priority": "high",
                "detail": "Collections↔deposit analytics unavailable — verify SoftDent + QB deposit exports.",
                "source": "static",
            }
        )

    lag = analytics.get("collectionLag") if isinstance(analytics, dict) else None
    if isinstance(lag, dict) and lag.get("hasData") and lag.get("avgLagDays") is not None:
        days = float(lag.get("avgLagDays") or 0)
        if days > 45:
            tasks.append(
                {
                    "id": "ar-90",
                    "title": f"Review A/R / collection lag ({days:.0f} days)",
                    "priority": "high" if days > 60 else "medium",
                    "detail": lag.get("summary") or f"Weighted lag {days} days",
                    "source": "collection_lag",
                }
            )
            signals.append("collection_lag")
        else:
            tasks.append(
                {
                    "id": "ar-90",
                    "title": "Spot-check 90+ day A/R balances",
                    "priority": "low",
                    "detail": lag.get("summary") or f"Lag {days:.0f} days — routine review",
                    "source": "collection_lag",
                }
            )
    else:
        tasks.append(
            {
                "id": "ar-90",
                "title": "Review 90+ day A/R balances",
                "priority": "medium",
                "detail": "Build collections queue from SoftDent A/R aging.",
                "source": "static",
            }
        )

    # Claims denied / aging from SoftDent import
    denied = 0
    try:
        from import_loader import load_import_bundle

        bundle = load_import_bundle(sync=False, deep=False)
        sd = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
        claims = sd.get("claims") if isinstance(sd.get("claims"), dict) else {}
        rows = claims.get("rows") if isinstance(claims.get("rows"), list) else []
        for row in rows:
            status = str(row.get("ClaimStatus") or row.get("status") or "").lower()
            if "denied" in status:
                denied += 1
    except Exception:
        denied = 0
    if denied > 0:
        tasks.append(
            {
                "id": "denied-claims",
                "title": f"Triage {denied} denied claim(s) for appeal / resubmit",
                "priority": "high" if denied >= 3 else "medium",
                "detail": "Use build_appeal_packet + aging follow-up — local drafts only.",
                "source": "softdent_claims",
                "deniedCount": denied,
            }
        )
        signals.append("denied_claims")
    else:
        tasks.append(
            {
                "id": "denied-claims",
                "title": "Triage denied claims for resubmit",
                "priority": "low",
                "detail": "No denied claims in current SoftDent import snapshot.",
                "source": "softdent_claims",
            }
        )

    alerts = analytics.get("alertTicker") if isinstance(analytics, dict) else None
    alert_items = (alerts.get("items") if isinstance(alerts, dict) else None) or []
    for alert in list(alert_items)[:3]:
        if not isinstance(alert, dict):
            continue
        title = str(alert.get("title") or alert.get("message") or alert.get("label") or "").strip()
        if not title:
            continue
        tasks.append(
            {
                "id": f"alert-{len(tasks)}",
                "title": f"Analytics alert: {title[:80]}",
                "priority": "medium",
                "detail": str(alert.get("summary") or alert.get("detail") or "")[:240],
                "source": "alert_ticker",
            }
        )
        signals.append("alert_ticker")

    tasks.extend(
        [
            {
                "id": "posting-queue",
                "title": "Clear approved posting queue export",
                "priority": "high",
                "detail": "Export IIF / review queue before close.",
                "source": "static",
            },
            {
                "id": "month-end-adjustments",
                "title": "Draft month-end adjusting entries",
                "priority": "medium",
                "detail": "Local journal drafts only — staff posts in QuickBooks.",
                "source": "static",
            },
            {
                "id": "collections-queue",
                "title": "Build today's collections call list",
                "priority": "medium",
                "detail": "generate_collections_queue from SoftDent A/R aging.",
                "source": "static",
            },
        ]
    )

    # De-dupe by id keeping first (analytics-enriched) entry
    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for task in tasks:
        tid = str(task.get("id") or "")
        if tid in seen:
            continue
        seen.add(tid)
        uniq.append(task)

    # Priority sort: high → medium → low
    pri = {"high": 0, "medium": 1, "low": 2}
    uniq.sort(key=lambda t: (pri.get(str(t.get("priority") or "medium"), 1), str(t.get("title") or "")))

    if not acct_period and isinstance(dep, dict) and dep.get("period"):
        acct_period = str(dep.get("period"))

    return {
        "ok": True,
        "period": acct_period,
        "tasks": uniq,
        "count": len(uniq),
        "signals": signals,
        "analyticsGrounded": bool(signals),
        "summary": (
            f"Month-end {acct_period}: {len(uniq)} tasks"
            + (f" · signals: {', '.join(signals)}" if signals else " · mostly routine checklist")
            + "."
        ),
    }


def scrub_fee_vs_paid(
    payload: dict[str, Any] | None = None,
    store=None,
) -> dict[str, Any]:
    """Compare fee-schedule allowed vs EOB/ERA paid — flag CO-45 vs true underpay.

    Never invents dollars: requires a fee-schedule hit and a paid amount.
    When store is provided and classification is underpaid, seeds collections follow-up.
    """
    data = payload if isinstance(payload, dict) else {}
    cdt = str(data.get("cdt") or data.get("cdtCode") or data.get("code") or "").strip().upper()
    if not cdt:
        m = re.search(r"\b(D\d{4})\b", str(data.get("procedure") or data.get("query") or ""), re.I)
        cdt = m.group(1).upper() if m else ""
    payer = str(data.get("payer") or data.get("Payer") or data.get("schedule") or "").strip()
    paid = _parse_money(data.get("paidAmount") or data.get("paid_amount") or data.get("paid"))
    billed = _parse_money(data.get("billedAmount") or data.get("billed") or data.get("ClaimAmount"))
    remark = str(data.get("remark") or data.get("remarkCode") or data.get("carc") or "").strip().upper()
    query = str(data.get("query") or f"{cdt} {payer}").strip()

    if not cdt:
        return {"ok": False, "error": "cdt_required", "summary": "Need a CDT code (e.g. D2740) for fee vs paid scrub."}
    if paid <= 0 and not data.get("allowZeroPaid"):
        return {
            "ok": False,
            "error": "paid_amount_required",
            "summary": "Need paid amount from EOB/ERA to scrub underpayment.",
            "cdt": cdt,
            "payer": payer or None,
        }

    fee_hit: dict[str, Any] = {}
    try:
        from fee_schedule_store import lookup_cdt

        fee_hit = lookup_cdt(cdt, payer or query)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "cdt": cdt}

    amounts = fee_hit.get("amounts") if isinstance(fee_hit, dict) else None
    if not fee_hit.get("ok") or not amounts:
        return {
            "ok": False,
            "error": "fee_schedule_miss",
            "cdt": cdt,
            "payer": payer or None,
            "paidAmount": paid,
            "summary": f"No fee-schedule amount for {cdt}"
            + (f" / {payer}" if payer else "")
            + " — cannot scrub underpay without a schedule hit.",
        }

    top = amounts[0] if isinstance(amounts[0], dict) else {}
    allowed = _parse_money(top.get("amount"))
    schedule_name = str(top.get("scheduleName") or top.get("scheduleId") or "")
    if allowed <= 0:
        return {
            "ok": False,
            "error": "allowed_zero",
            "cdt": cdt,
            "summary": f"Fee schedule returned $0 for {cdt} on {schedule_name or 'schedule'} — verify schedule mapping.",
        }

    delta = round(paid - allowed, 2)
    abs_delta = abs(delta)
    # Contractual write-off / CO-45: paid near allowed (within $1 or 2%)
    near_allowed = abs_delta <= max(1.0, allowed * 0.02)
    co45_hint = bool(re.search(r"\bCO[\s-]?45\b", remark, re.I)) or bool(
        re.search(r"\bco-?45\b", str(data.get("query") or ""), re.I)
    )

    if near_allowed or (co45_hint and paid <= allowed + 1):
        classification = "contractual_ok"
        label = "CO-45 / contractual — paid aligns with fee schedule allowed"
    elif paid < allowed - max(1.0, allowed * 0.02):
        classification = "underpaid"
        label = "True underpayment vs fee schedule allowed — review EOB before write-off"
    else:
        classification = "overpaid_or_misc"
        label = "Paid above schedule allowed — verify coordination of benefits / posting"

    billed_note = None
    if billed > 0 and allowed > 0 and billed > allowed:
        billed_note = round(billed - allowed, 2)

    summary_lines = [
        f"Fee vs paid scrub ({cdt}" + (f" · {payer}" if payer else "") + "):",
        f"- Schedule: {schedule_name} allowed ${allowed:,.2f}",
        f"- Paid: ${paid:,.2f} · delta ${delta:+,.2f}",
        f"- Classification: {label}",
    ]
    if billed_note is not None:
        summary_lines.append(f"- Billed ${billed:,.2f} (−${billed_note:,.2f} vs allowed = expected contractual adj)")
    if co45_hint:
        summary_lines.append("- Remark mentions CO-45 — treat as contractual unless paid << allowed.")
    summary_lines.append("- Local guidance only — staff confirms before patient balance or appeal.")

    collections_seed = None
    shortfall = round(allowed - paid, 2) if classification == "underpaid" else 0.0
    if store and classification == "underpaid" and shortfall > 0 and data.get("skipCollectionsSeed") not in (
        True,
        "true",
        "1",
    ):
        try:
            collections_seed = seed_underpay_to_collections(
                store,
                {
                    "shortfall": shortfall,
                    "patientName": data.get("patientName") or data.get("patient") or payer or "Insurance underpay",
                    "patientId": data.get("patientId") or "",
                    "claimId": data.get("claimId") or data.get("claim_id") or "",
                    "cdt": cdt,
                    "payer": payer,
                },
            )
            if collections_seed.get("seeded"):
                summary_lines.append(f"- Seeded collections follow-up ${shortfall:,.2f} (staff contact).")
            elif collections_seed.get("duplicate"):
                summary_lines.append("- Underpay already on collections queue.")
        except Exception as exc:
            collections_seed = {"ok": False, "error": str(exc)}

    return {
        "ok": True,
        "cdt": cdt,
        "payer": payer or None,
        "scheduleName": schedule_name,
        "allowedAmount": allowed,
        "paidAmount": paid,
        "billedAmount": billed if billed > 0 else None,
        "delta": delta,
        "shortfall": shortfall if classification == "underpaid" else None,
        "classification": classification,
        "contractualOk": classification == "contractual_ok",
        "underpaid": classification == "underpaid",
        "feeHit": {"code": cdt, "amounts": amounts[:3], "sourceSheet": fee_hit.get("sourceSheet")},
        "collectionsSeed": collections_seed,
        "summary": "\n".join(summary_lines),
    }
