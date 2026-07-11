"""
HAL-said improve-fix pack (Moonshot consult 2026-07-11, approve-all).

NR2-local only — never SoftDent write-back, never invent dollars/PHI.
Covers: denial→Steve tasks, Dr. Reno clinical sign-off, EOB backlog,
carrier normalize/contact update, structured Remember, policy changelog,
payer change alerts.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

STORE_KEY_EOB_BACKLOG = "nr2:v2:eob:backlog"
STORE_KEY_CLINICAL_SIGNOFF = "nr2:v2:narratives:clinical-signoff"
STORE_KEY_POLICY_UPDATES = "nr2:v2:policy:updates"
STORE_KEY_PAYER_ALERTS = "nr2:v2:payer:alerts"

# X12 835 CLP02 — 4 = denied; 22 = reversal (treat as follow-up)
DENIAL_CLP_STATUSES = {"4", "22"}

STRUCTURED_CATEGORY_MAP = {
    "payer_policy": "insurance_narratives",
    "workflow_quirk": "operator_playbooks",
    "denial_template": "insurance_narratives",
    "carrier_contact": "insurance_narratives",
    "office_policy": "operator_playbooks",
}

PHI_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHI_DOB_RE = re.compile(r"\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _store():
    from document_sync import NR2_DATA_DIR
    from local_store import LocalStore

    return LocalStore(NR2_DATA_DIR)


def _fallback_path(key: str) -> Path:
    from document_sync import NR2_DATA_DIR

    safe = re.sub(r"[^\w.\-]+", "_", key)
    path = Path(NR2_DATA_DIR) / "hal_said_improve"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{safe}.json"


def _load_json(key: str) -> dict[str, Any]:
    try:
        store = _store()
        raw = store.get(key)
        if not raw:
            raise RuntimeError("empty")
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            return json.loads(raw) if raw.strip() else {}
    except Exception:
        try:
            p = _fallback_path(key)
            if p.is_file():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_json(key: str, payload: dict[str, Any]) -> None:
    try:
        store = _store()
        store.set(key, json.dumps(payload))
        return
    except Exception:
        pass
    p = _fallback_path(key)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _audit(event: str, detail: dict[str, Any] | None = None) -> None:
    try:
        from apex_cpa_pack import append_audit

        append_audit(event, detail if isinstance(detail, dict) else {})
    except Exception:
        pass


def _safe_claim_token(claim_id: str) -> str:
    """Claim ID only — never embed patient names in task titles."""
    return re.sub(r"[^\w\-]+", "", str(claim_id or "").strip())[:40] or "unknown"


# ——— 1.1 Denial → Steve ———


def _denial_code_from_match(m: dict[str, Any]) -> str | None:
    seg = m.get("segment") if isinstance(m.get("segment"), dict) else {}
    status = str(seg.get("status") or m.get("denialCode") or "").strip()
    if status in DENIAL_CLP_STATUSES:
        return f"CLP-{status}"
    # Zero paid with charged > 0 often needs review (not always denial)
    try:
        paid = float(m.get("paidAmount") or seg.get("paid") or 0)
        charged = float(seg.get("charged") or 0)
    except (TypeError, ValueError):
        paid, charged = 0.0, 0.0
    if status == "4" or (charged > 0 and paid <= 0 and status in {"4", "22", "denied", "Denied"}):
        return f"CLP-{status or '4'}"
    if status.lower() in {"denied", "deny", "rejection"}:
        return "DENIED"
    return None


def _task_title_for_denial(claim_id: str, code: str) -> str:
    return f"Denial follow-up: {code} · claim {_safe_claim_token(claim_id)}"


def _existing_open_denial_titles() -> set[str]:
    try:
        from nr2_local_db import list_tasks

        titles = set()
        for t in list_tasks(include_done=False, limit=200):
            title = str(t.get("title") or "")
            if title.startswith("Denial follow-up:"):
                titles.add(title)
        return titles
    except Exception:
        return set()


def auto_create_denial_tasks(
    matches: list[dict[str, Any]],
    *,
    dry_run: bool = False,
    assignee: str = "Steve",
) -> dict[str, Any]:
    """Create NR2 office_tasks for ERA denial-like matches. Idempotent by title."""
    from nr2_local_db import upsert_task

    existing = _existing_open_denial_titles()
    created: list[dict[str, Any]] = []
    skipped = 0
    due = (datetime.now(timezone.utc) + timedelta(days=3)).date().isoformat()

    for m in matches or []:
        if not isinstance(m, dict):
            continue
        cid = str(m.get("claimId") or "").strip()
        if not cid:
            continue
        code = _denial_code_from_match(m)
        if not code:
            continue
        title = _task_title_for_denial(cid, code)
        if title in existing:
            skipped += 1
            continue
        task_body = {
            "title": title,
            "assignee": assignee,
            "dueDate": due,
            "done": False,
        }
        if dry_run:
            created.append(task_body)
            continue
        result = upsert_task(task_body)
        if result.get("ok"):
            created.append(result.get("task") or task_body)
            existing.add(title)
    if created and not dry_run:
        _audit("hal_said:denial_tasks", {"created": len(created), "skipped": skipped})
    return {
        "ok": True,
        "created": len(created),
        "skipped": skipped,
        "tasks": created[:40],
        "dryRun": dry_run,
        "localOnly": True,
    }


def assign_softdent_denials_to_steve(
    claim_rows: list[dict[str, Any]] | None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Scan SoftDent claim rows with denied-like status → Steve tasks."""
    matches: list[dict[str, Any]] = []
    for row in claim_rows or []:
        if not isinstance(row, dict):
            continue
        status = str(
            row.get("ClaimStatus") or row.get("Status") or row.get("status") or ""
        ).strip().lower()
        if not any(tok in status for tok in ("den", "reject", "appeal")):
            continue
        cid = str(
            row.get("Claim") or row.get("claim") or row.get("ClaimId") or row.get("id") or ""
        ).strip()
        if not cid:
            continue
        matches.append({"claimId": cid, "denialCode": "DENIED", "segment": {"status": "4"}})
    return auto_create_denial_tasks(matches, dry_run=dry_run)


# ——— 1.2 Clinical sign-off (Dr. Reno) ———


def list_clinical_signoffs(*, status: str | None = None, limit: int = 80) -> list[dict[str, Any]]:
    data = _load_json(STORE_KEY_CLINICAL_SIGNOFF)
    entries = data.get("entries") if isinstance(data.get("entries"), list) else []
    out = [e for e in entries if isinstance(e, dict)]
    if status:
        want = str(status).strip()
        out = [e for e in out if str(e.get("status") or "") == want]
    return list(reversed(out[-max(1, min(limit, 200)) :]))


def submit_clinical_signoff(payload: dict[str, Any] | None) -> dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    narrative_id = str(body.get("narrativeId") or body.get("narrative_id") or "").strip()[:80]
    claim_id = str(body.get("claimId") or body.get("claim_id") or "").strip()[:80]
    note = str(body.get("note") or "").strip()[:400]
    if not narrative_id and not claim_id:
        return {"ok": False, "error": "narrativeId or claimId required"}

    entry = {
        "id": str(uuid.uuid4())[:10],
        "narrativeId": narrative_id or f"claim-{_safe_claim_token(claim_id)}",
        "claimId": claim_id,
        "status": "pending_clinical_review",
        "assignee": "Dr. Reno",
        "note": note,
        "requestedAt": _utc_now(),
        "resolvedAt": None,
    }
    data = _load_json(STORE_KEY_CLINICAL_SIGNOFF)
    entries = data.get("entries") if isinstance(data.get("entries"), list) else []
    entries.append(entry)
    data["entries"] = entries[-300:]
    data["updatedAt"] = _utc_now()
    _save_json(STORE_KEY_CLINICAL_SIGNOFF, data)

    # Office task for Dr. Reno (claim id only — no patient name)
    try:
        from nr2_local_db import upsert_task

        upsert_task(
            {
                "title": f"Clinical sign-off: narrative · claim {_safe_claim_token(claim_id or narrative_id)}",
                "assignee": "Dr. Reno",
                "dueDate": (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat(),
                "done": False,
            }
        )
    except Exception:
        pass

    _audit("hal_said:clinical_signoff_request", {"id": entry["id"], "claimId": claim_id})
    return {"ok": True, "entry": entry, "localOnly": True}


def resolve_clinical_signoff(payload: dict[str, Any] | None) -> dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    entry_id = str(body.get("id") or "").strip()
    decision = str(body.get("status") or body.get("decision") or "").strip().lower()
    if decision in {"approve", "approved", "yes"}:
        decision = "approved"
    elif decision in {"reject", "rejected", "no"}:
        decision = "rejected"
    else:
        return {"ok": False, "error": "status must be approved or rejected"}
    if not entry_id:
        return {"ok": False, "error": "id required"}

    data = _load_json(STORE_KEY_CLINICAL_SIGNOFF)
    entries = data.get("entries") if isinstance(data.get("entries"), list) else []
    found = None
    for e in entries:
        if isinstance(e, dict) and str(e.get("id")) == entry_id:
            e["status"] = decision
            e["resolvedAt"] = _utc_now()
            found = e
            break
    if not found:
        return {"ok": False, "error": "sign-off entry not found"}
    data["entries"] = entries
    data["updatedAt"] = _utc_now()
    _save_json(STORE_KEY_CLINICAL_SIGNOFF, data)
    _audit("hal_said:clinical_signoff_resolve", {"id": entry_id, "status": decision})
    return {"ok": True, "entry": found, "localOnly": True}


def clinical_signoff_widget() -> dict[str, Any]:
    pending = list_clinical_signoffs(status="pending_clinical_review", limit=40)
    items = [
        {
            "id": e.get("id"),
            "claimId": e.get("claimId") or "",
            "narrativeId": e.get("narrativeId") or "",
            "at": e.get("requestedAt") or "",
            "filename": f"Dr. Reno · {e.get('status')}",
        }
        for e in pending
    ]
    n = len(pending)
    return {
        "id": "clinical-signoff-queue",
        "type": "claim-attachments",
        "label": "Clinical Sign-off (Dr. Reno)",
        "size": "l",
        "count": n,
        "items": items,
        "status": "ok" if n else "empty",
        "emptyMessage": "No narratives pending Dr. Reno clinical review",
        "hint": (
            "Request sign-off via API or HAL. HAL drafts only — never submits to payer. "
            "Tasks assign to Dr. Reno (NR2-local)."
        ),
        "signoffForm": True,
    }


# ——— 1.3 EOB backlog ———


def list_eob_backlog(*, include_posted: bool = False, older_than_days: int = 0) -> list[dict[str, Any]]:
    data = _load_json(STORE_KEY_EOB_BACKLOG)
    items = data.get("items") if isinstance(data.get("items"), list) else []
    out: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for it in items:
        if not isinstance(it, dict):
            continue
        if not include_posted and it.get("posted"):
            continue
        if older_than_days > 0:
            recv = str(it.get("receivedAt") or "")
            try:
                dt = datetime.fromisoformat(recv.replace("Z", "+00:00"))
                age = (now - dt).days
            except Exception:
                age = 0
            if age < older_than_days:
                continue
            it = dict(it)
            it["ageDays"] = age
        out.append(it)
    return list(reversed(out))


def record_eob_from_era_matches(matches: list[dict[str, Any]], *, filename: str | None = None) -> int:
    data = _load_json(STORE_KEY_EOB_BACKLOG)
    items = data.get("items") if isinstance(data.get("items"), list) else []
    by_claim = {
        str(i.get("claimId")): i
        for i in items
        if isinstance(i, dict) and i.get("claimId") and not i.get("posted")
    }
    added = 0
    for m in matches or []:
        if not isinstance(m, dict):
            continue
        cid = str(m.get("claimId") or "").strip()
        if not cid:
            continue
        if cid in by_claim:
            continue
        entry = {
            "id": str(uuid.uuid4())[:10],
            "claimId": cid,
            "receivedAt": _utc_now(),
            "payer": None,
            "paidAmount": m.get("paidAmount"),
            "sourceFile": filename,
            "posted": False,
            "postedAt": None,
        }
        items.append(entry)
        by_claim[cid] = entry
        added += 1
    data["items"] = items[-500:]
    data["updatedAt"] = _utc_now()
    _save_json(STORE_KEY_EOB_BACKLOG, data)
    return added


def mark_eob_posted(claim_id: str) -> dict[str, Any]:
    cid = str(claim_id or "").strip()
    if not cid:
        return {"ok": False, "error": "claimId required"}
    data = _load_json(STORE_KEY_EOB_BACKLOG)
    items = data.get("items") if isinstance(data.get("items"), list) else []
    found = False
    for it in items:
        if isinstance(it, dict) and str(it.get("claimId")) == cid and not it.get("posted"):
            it["posted"] = True
            it["postedAt"] = _utc_now()
            found = True
    if not found:
        return {"ok": False, "error": "open backlog item not found"}
    data["items"] = items
    data["updatedAt"] = _utc_now()
    _save_json(STORE_KEY_EOB_BACKLOG, data)
    return {"ok": True, "claimId": cid, "localOnly": True}


def eob_backlog_widget() -> dict[str, Any]:
    items = list_eob_backlog(include_posted=False)
    stale = list_eob_backlog(include_posted=False, older_than_days=3)
    rows = [
        {
            "claimId": it.get("claimId"),
            "filename": f"ERA · age {it.get('ageDays', '?')}d" if it.get("ageDays") is not None else "ERA pending SoftDent post",
            "at": it.get("receivedAt") or "",
        }
        for it in items[:30]
    ]
    # attach age for display
    aged = {str(s.get("claimId")): s.get("ageDays") for s in stale}
    for r in rows:
        if str(r.get("claimId")) in aged:
            r["filename"] = f"ERA · {aged[str(r['claimId'])]}d unposted"

    n = len(items)
    return {
        "id": "eob-posting-backlog",
        "type": "claim-attachments",
        "label": "EOB Posting Backlog",
        "size": "l",
        "count": n,
        "items": rows,
        "status": "ok" if n else "empty",
        "emptyMessage": "No unposted ERA/EOB matches on file",
        "hint": (
            f"{len(stale)} item(s) older than 3 days. Mark posted after SoftDent posting "
            "(NR2 tracks backlog only — does not post to SoftDent)."
        ),
        "staleCount": len(stale),
    }


# ——— ERA post-process hook ———


def process_era_workflow(era_result: dict[str, Any], *, filename: str | None = None) -> dict[str, Any]:
    """Call after successful ingest_era_835 — denial tasks + EOB backlog."""
    if not isinstance(era_result, dict) or not era_result.get("ok"):
        return {"ok": False, "skipped": True}
    matches = era_result.get("matches") if isinstance(era_result.get("matches"), list) else []
    denial = auto_create_denial_tasks(matches)
    eob_added = record_eob_from_era_matches(matches, filename=filename)
    return {
        "ok": True,
        "denialTasks": denial,
        "eobBacklogAdded": eob_added,
        "localOnly": True,
    }


# ——— 2.2 Carrier label normalize ———


def normalize_softdent_label(sd_label: str) -> dict[str, Any]:
    from payer_reference_store import search_payers

    label = str(sd_label or "").strip()
    if not label:
        return {"matched": False, "canonical_id": "unknown", "raw": ""}
    hits = search_payers(label, limit=1)
    if hits:
        hit = hits[0]
        return {
            "matched": True,
            "canonical_id": hit.get("id"),
            "name": hit.get("name"),
            "payerIds": hit.get("payerIds") or [],
            "eligibilityNotes": hit.get("eligibilityNotes"),
            "narrativeNotes": hit.get("narrativeNotes"),
            "raw": label,
        }
    return {"matched": False, "canonical_id": "unknown", "raw": label, "needs_mapping": True}


# ——— 2.3 Payer contact update ———


def update_payer_field(payer_id: str, field: str, value: str) -> dict[str, Any]:
    from payer_reference_store import PAYER_REFERENCE_PATH, load_payer_reference

    allowed = {
        "eligibilityNotes",
        "narrativeNotes",
        "name",
        "commonDenialCodes",
    }
    pid = str(payer_id or "").strip()
    fname = str(field or "").strip()
    if fname not in allowed:
        return {"ok": False, "error": f"field not allowed ({fname})"}
    if not pid:
        return {"ok": False, "error": "payer_id required"}

    ref = load_payer_reference()
    payers = ref.get("payers") if isinstance(ref.get("payers"), list) else []
    found = None
    for p in payers:
        if isinstance(p, dict) and str(p.get("id")) == pid:
            if fname == "commonDenialCodes":
                codes = [c.strip() for c in str(value or "").split(",") if c.strip()]
                p[fname] = codes[:20]
            else:
                p[fname] = str(value or "")[:800]
            p["updatedAt"] = _utc_now()
            found = p
            break
    if not found:
        return {"ok": False, "error": "payer not found"}

    ref["payers"] = payers
    ref["updatedAt"] = _utc_now()
    PAYER_REFERENCE_PATH.write_text(json.dumps(ref, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        load_payer_reference.cache_clear()
    except Exception:
        pass

    broadcast_payer_change(pid, f"Updated {fname} for {found.get('name') or pid}")
    _audit("hal_said:payer_field_update", {"payerId": pid, "field": fname})
    return {"ok": True, "payer": found, "localOnly": True}


def payer_contact_admin_widget() -> dict[str, Any]:
    try:
        from payer_reference_store import list_payers

        payers = list_payers(limit=40)
    except Exception:
        payers = []
    cards = []
    for p in payers[:20]:
        if not isinstance(p, dict):
            continue
        cards.append(
            {
                "payerName": p.get("name") or p.get("id"),
                "appealDeadlineDays": None,
                "contact": (p.get("eligibilityNotes") or "")[:120],
                "guidelines": (p.get("narrativeNotes") or "")[:200],
                "payerId": p.get("id"),
            }
        )
    return {
        "id": "payer-contact-admin",
        "type": "payer-reference-card",
        "label": "Payer Contacts (HAL reference)",
        "size": "l",
        "payers": cards,
        "status": "ok" if cards else "empty",
        "emptyMessage": "No payers in payer_reference.json",
        "hint": (
            "Central eligibility/claim phones from Office Insurance.xlsx + SoftDent InsCo. "
            "Use sync script or PATCH API to update — not SoftDent write-back."
        ),
        "halSaidAdmin": True,
    }


# ——— 3.1 Structured Remember ———


def remember_structured(payload: dict[str, Any] | None) -> dict[str, Any]:
    from knowledge_memory_store import VALID_CATEGORIES, remember_fact

    body = payload if isinstance(payload, dict) else {}
    fact = str(body.get("fact") or body.get("text") or "").strip()
    category_in = str(body.get("category") or "").strip().lower()
    payer_id = str(body.get("payerId") or body.get("payer_id") or "").strip()[:80]

    if len(fact) < 10:
        return {"ok": False, "error": "fact must be at least 10 characters"}
    if PHI_SSN_RE.search(fact) or PHI_DOB_RE.search(fact):
        return {"ok": False, "error": "Potential PHI detected (SSN/DOB pattern) — not saved"}

    mapped = STRUCTURED_CATEGORY_MAP.get(category_in)
    if mapped:
        category = mapped
    elif category_in in VALID_CATEGORIES:
        category = category_in
    else:
        category = None

    if payer_id and "payer" not in fact.lower():
        fact = f"[payer:{payer_id}] {fact}"

    try:
        result = remember_fact(
            fact,
            source=f"staff:remember_structured:{category_in or 'general'}",
            category=category,
            actor="Staff",
        )
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    # Optional: also log as policy change when category is payer_policy
    if category_in == "payer_policy" and payer_id:
        record_policy_change(
            {
                "payerId": payer_id,
                "description": fact[:500],
                "effectiveDate": body.get("effectiveDate") or _utc_now()[:10],
                "recordedBy": "Staff",
            }
        )

    result["structuredCategory"] = category_in or "general"
    result["mappedCategory"] = category
    return result


def structured_remember_widget() -> dict[str, Any]:
    return {
        "id": "hal-structured-remember",
        "type": "status",
        "label": "Teach HAL (structured)",
        "message": "Remember with category",
        "status": "ok",
        "hint": (
            "Categories: payer_policy · workflow_quirk · denial_template · office_policy. "
            "POST /api/apex/hal/remember-structured — no PHI/secrets."
        ),
        "rememberForm": True,
        "categories": list(STRUCTURED_CATEGORY_MAP.keys()),
    }


# ——— 3.2 Policy changelog ———


def record_policy_change(payload: dict[str, Any] | None) -> dict[str, Any]:
    body = payload if isinstance(payload, dict) else {}
    payer_id = str(body.get("payerId") or body.get("payer_id") or "").strip()[:80]
    description = str(body.get("description") or body.get("text") or "").strip()[:800]
    if not description:
        return {"ok": False, "error": "description required"}
    if PHI_SSN_RE.search(description):
        return {"ok": False, "error": "Potential PHI detected — not saved"}

    entry = {
        "id": str(uuid.uuid4())[:10],
        "payerId": payer_id or "general",
        "description": description,
        "effectiveDate": str(body.get("effectiveDate") or body.get("effective_date") or "")[:40],
        "recordedBy": str(body.get("recordedBy") or body.get("recorded_by") or "Staff")[:80],
        "recordedAt": _utc_now(),
    }
    data = _load_json(STORE_KEY_POLICY_UPDATES)
    entries = data.get("entries") if isinstance(data.get("entries"), list) else []
    entries.append(entry)
    data["entries"] = entries[-400:]
    data["updatedAt"] = _utc_now()
    _save_json(STORE_KEY_POLICY_UPDATES, data)
    _audit("hal_said:policy_change", {"id": entry["id"], "payerId": payer_id})
    return {"ok": True, "entry": entry, "localOnly": True}


def list_policy_changes(*, payer_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    data = _load_json(STORE_KEY_POLICY_UPDATES)
    entries = [e for e in (data.get("entries") or []) if isinstance(e, dict)]
    if payer_id:
        want = str(payer_id).strip()
        entries = [e for e in entries if str(e.get("payerId") or "") == want]
    return list(reversed(entries[-max(1, min(limit, 100)) :]))


def policy_changelog_widget() -> dict[str, Any]:
    entries = list_policy_changes(limit=15)
    items = [
        {
            "claimId": e.get("payerId") or "general",
            "filename": (e.get("description") or "")[:80],
            "at": e.get("recordedAt") or "",
        }
        for e in entries
    ]
    n = len(entries)
    return {
        "id": "policy-changelog",
        "type": "claim-attachments",
        "label": "Payer Policy Changelog",
        "size": "m",
        "count": n,
        "items": items,
        "status": "ok" if n else "empty",
        "emptyMessage": "No structured policy changes recorded yet",
        "hint": "Staff policy updates for HAL context — not SoftDent write-back.",
    }


# ——— 4.1 Payer change alerts ———


def broadcast_payer_change(payer_id: str, change_summary: str, *, notify_steve: bool = False) -> dict[str, Any]:
    summary = str(change_summary or "").strip()[:400]
    pid = str(payer_id or "").strip()[:80] or "unknown"
    if not summary:
        return {"ok": False, "error": "summary required"}

    memo = {
        "id": str(uuid.uuid4())[:10],
        "type": "payer_reference_update",
        "payerId": pid,
        "summary": summary,
        "timestamp": _utc_now(),
    }
    data = _load_json(STORE_KEY_PAYER_ALERTS)
    items = data.get("items") if isinstance(data.get("items"), list) else []
    items.append(memo)
    data["items"] = items[-100:]
    data["updatedAt"] = _utc_now()
    _save_json(STORE_KEY_PAYER_ALERTS, data)

    task = None
    lower = summary.lower()
    if notify_steve or "fee schedule" in lower or "eligibility" in lower:
        try:
            from nr2_local_db import upsert_task

            result = upsert_task(
                {
                    "title": f"Review payer update: {pid}",
                    "assignee": "Steve",
                    "dueDate": (datetime.now(timezone.utc) + timedelta(days=2)).date().isoformat(),
                    "done": False,
                }
            )
            task = result.get("task")
        except Exception:
            pass

    return {"ok": True, "alert": memo, "task": task, "localOnly": True}


def list_payer_alerts(*, limit: int = 20) -> list[dict[str, Any]]:
    data = _load_json(STORE_KEY_PAYER_ALERTS)
    items = [i for i in (data.get("items") or []) if isinstance(i, dict)]
    return list(reversed(items[-max(1, min(limit, 50)) :]))


def payer_alerts_widget() -> dict[str, Any]:
    alerts = list_payer_alerts(limit=15)
    items = [
        {
            "claimId": a.get("payerId") or "",
            "filename": (a.get("summary") or "")[:100],
            "at": a.get("timestamp") or "",
        }
        for a in alerts
    ]
    n = len(alerts)
    return {
        "id": "payer-change-alerts",
        "type": "claim-attachments",
        "label": "Payer Change Alerts",
        "size": "m",
        "count": n,
        "items": items,
        "status": "ok" if n else "empty",
        "emptyMessage": "No payer reference change alerts yet",
        "hint": "Fired when payer_reference contacts/sync updates. Steve notified for fee/eligibility changes.",
    }


# ——— Huddle enrichment + page append ———


def huddle_extra_priorities() -> list[str]:
    extras: list[str] = []
    try:
        stale = list_eob_backlog(include_posted=False, older_than_days=3)
        if stale:
            extras.append(f"EOB posting backlog: {len(stale)} unposted >3 days")
    except Exception:
        pass
    try:
        pending = list_clinical_signoffs(status="pending_clinical_review", limit=50)
        if pending:
            extras.append(f"Dr. Reno clinical sign-off: {len(pending)} narrative(s) waiting")
    except Exception:
        pass
    try:
        from nr2_local_db import list_tasks

        steve = [
            t
            for t in list_tasks(include_done=False, limit=100)
            if str(t.get("assignee") or "").lower() == "steve"
            and str(t.get("title") or "").startswith("Denial follow-up:")
        ]
        if steve:
            extras.append(f"Steve denial follow-ups: {len(steve)} open")
    except Exception:
        pass
    return extras[:6]


def append_office_manager_hal_said(widgets: list[dict[str, Any]]) -> None:
    widgets.append(eob_backlog_widget())
    widgets.append(clinical_signoff_widget())
    widgets.append(payer_alerts_widget())
    widgets.append(policy_changelog_widget())
    widgets.append(payer_contact_admin_widget())
    widgets.append(structured_remember_widget())


def append_claims_hal_said(widgets: list[dict[str, Any]]) -> None:
    widgets.append(eob_backlog_widget())
    widgets.append(clinical_signoff_widget())


def append_hal_page_hal_said(widgets: list[dict[str, Any]]) -> None:
    widgets.append(structured_remember_widget())
    widgets.append(payer_alerts_widget())


def enrich_daily_huddle_widget(widget: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(widget, dict):
        return widget
    extras = huddle_extra_priorities()
    if not extras:
        return widget
    out = dict(widget)
    pri = list(out.get("priorities") or [])
    for e in extras:
        if e not in pri:
            pri.append(e)
    out["priorities"] = pri[:16]
    hint = str(out.get("hint") or "")
    if "EOB" not in hint and "sign-off" not in hint:
        out["hint"] = (hint + " · HAL-said: denials→Steve, sign-off→Dr. Reno, EOB backlog.").strip(" ·")
    return out
