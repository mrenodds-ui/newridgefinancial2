"""
NR2 Apex Program Improvements IMP-001..010 (Moonshot PROGRAM_IMPROVE consult).
Import-backed / NR2-local only — never invents dollars or SoftDent write-back.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORE_KEY_CLAIM_ACTIONS = "nr2:v2:claims:actions"
STORE_KEY_ERA_MATCHES = "nr2:v2:claims:era-matches"
STORE_KEY_CLAIM_ATTACHMENTS = "nr2:v2:claims:attachments"
STORE_KEY_EBITDA_TREND = "nr2:v2:financial:ebitda-trend"
STORE_KEY_IMPORT_HEALTH = "nr2:v2:imports:health-alerts"

ACTION_TYPES = ("generate-narrative", "follow-up-note", "schedule-callback", "mark-appealed")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _store():
    from document_sync import NR2_DATA_DIR
    from local_store import LocalStore

    return LocalStore(NR2_DATA_DIR)


def _fallback_path(key: str) -> Path:
    from document_sync import NR2_DATA_DIR

    safe = re.sub(r"[^\w.\-]+", "_", key)
    path = Path(NR2_DATA_DIR) / "improve_pack"
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
    try:
        from apex_claims_narratives_pack import append_narrative_audit

        append_narrative_audit(event, detail if isinstance(detail, dict) else {})
    except Exception:
        pass


# ——— IMP-001 Claim card actions (NR2-local, not SoftDent) ———


def list_claim_actions(claim_id: str | None = None, *, limit: int = 80) -> list[dict[str, Any]]:
    data = _load_json(STORE_KEY_CLAIM_ACTIONS)
    entries = data.get("entries") if isinstance(data.get("entries"), list) else []
    out = [e for e in entries if isinstance(e, dict)]
    if claim_id:
        want = str(claim_id).strip()
        out = [e for e in out if str(e.get("claimId") or "") == want]
    return list(reversed(out[-max(1, min(limit, 200)) :]))


def record_claim_action(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or payload.get("type") or "").strip().lower()
    if action not in ACTION_TYPES:
        return {"ok": False, "error": f"Unknown action. Use one of: {', '.join(ACTION_TYPES)}"}
    claim_id = str(payload.get("claimId") or "").strip()
    if not claim_id:
        return {"ok": False, "error": "claimId required"}
    note = str(payload.get("note") or payload.get("text") or "").strip()
    entry = {
        "id": str(uuid.uuid4())[:10],
        "at": _utc_now(),
        "claimId": claim_id,
        "action": action,
        "note": note[:2000],
        "patientName": str(payload.get("patientName") or "").strip() or None,
        "source": "nr2-local",
        "softDentWriteBack": False,
    }
    data = _load_json(STORE_KEY_CLAIM_ACTIONS)
    entries = data.get("entries") if isinstance(data.get("entries"), list) else []
    entries.append(entry)
    data["entries"] = entries[-400:]
    _save_json(STORE_KEY_CLAIM_ACTIONS, data)
    _audit(f"claim-action:{action}", {"claimId": claim_id, "id": entry["id"]})
    return {"ok": True, "entry": entry, "message": "NR2 action recorded (does not write to SoftDent)."}


def actions_by_claim(claim_ids: list[str] | None = None) -> dict[str, list[dict[str, Any]]]:
    data = _load_json(STORE_KEY_CLAIM_ACTIONS)
    entries = data.get("entries") if isinstance(data.get("entries"), list) else []
    want = {str(x) for x in (claim_ids or []) if str(x).strip()} if claim_ids else None
    out: dict[str, list[dict[str, Any]]] = {}
    for e in entries:
        if not isinstance(e, dict):
            continue
        cid = str(e.get("claimId") or "")
        if not cid:
            continue
        if want is not None and cid not in want:
            continue
        out.setdefault(cid, []).append(e)
    return out


# ——— IMP-002 / IMP-003 Import health ———


def assess_import_health(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    """Proactive import health — freshness + SoftDent period gaps. Never invents $."""
    b = bundle if isinstance(bundle, dict) else {}
    diag = b.get("diagnostics") if isinstance(b.get("diagnostics"), dict) else {}
    summary = diag.get("summary") if isinstance(diag.get("summary"), dict) else {}
    loaded = str(b.get("loadedAt") or "").strip()
    alerts: list[dict[str, Any]] = []
    stale_days = None
    if loaded:
        try:
            ts = datetime.fromisoformat(loaded.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            stale_days = max(0, int((datetime.now(timezone.utc) - ts).total_seconds() // 86400))
            if stale_days >= 7:
                alerts.append(
                    {
                        "id": "import-stale",
                        "severity": "warn",
                        "message": f"Imports last loaded {stale_days} day(s) ago",
                        "hint": "Sync SoftDent + QuickBooks exports (weekly Register/Daysheet task).",
                        "halQuery": "Verify SoftDent and QuickBooks import status",
                    }
                )
        except Exception:
            stale_days = None

    missing = int(summary.get("missing") or 0) if summary.get("missing") is not None else None
    stale_n = int(summary.get("stale") or 0) if summary.get("stale") is not None else None
    if missing and missing > 0:
        alerts.append(
            {
                "id": "import-missing",
                "severity": "warn",
                "message": f"{missing} import dataset(s) missing",
                "hint": "Run Apex Sync / SoftDent period refresh.",
                "halQuery": "Sync imports and populate the widgets",
            }
        )
    if stale_n and stale_n > 0:
        alerts.append(
            {
                "id": "import-partial-stale",
                "severity": "info",
                "message": f"{stale_n} dataset(s) marked stale",
                "hint": "Re-export SoftDent Register and QuickBooks P&L.",
                "halQuery": "Refresh SoftDent period imports",
            }
        )

    # Period gap signal from CPA C0 guidance when available
    try:
        from apex_cpa_pack import build_c0_import_guidance

        c0 = build_c0_import_guidance(b) or {}
        pending = c0.get("collectionsPending") if isinstance(c0.get("collectionsPending"), list) else []
        if pending:
            alerts.append(
                {
                    "id": "period-gap",
                    "severity": "warn",
                    "message": f"Period import gap: {len(pending)} pending item(s)",
                    "hint": "Export SoftDent Register/Daysheet for missing periods (see SoftDent weekly task doc).",
                    "halQuery": "Focus C0 import guidance",
                    "pending": pending[:8],
                }
            )
    except Exception:
        pass

    tone = "ok"
    if any(a.get("severity") == "warn" for a in alerts):
        tone = "warn"
    elif alerts:
        tone = "info"

    result = {
        "ok": True,
        "tone": tone,
        "loadedAt": loaded,
        "staleDays": stale_days,
        "summary": {
            "connected": summary.get("connected"),
            "total": summary.get("total"),
            "missing": missing,
            "stale": stale_n,
        },
        "alerts": alerts,
        "checkedAt": _utc_now(),
    }
    try:
        _save_json(STORE_KEY_IMPORT_HEALTH, {"latest": result})
    except Exception:
        pass
    return result


def import_health_widget(bundle: dict[str, Any]) -> dict[str, Any]:
    health = assess_import_health(bundle)
    alerts = health.get("alerts") if isinstance(health.get("alerts"), list) else []
    if not alerts:
        msg = "Imports healthy"
        status = "ok"
        hint = f"Last loaded {health.get('loadedAt') or '—'} · proactive monitor clear."
    else:
        msg = alerts[0].get("message") or "Import attention needed"
        status = "empty" if health.get("tone") == "warn" else "ok"
        hint = " · ".join(str(a.get("hint") or a.get("message") or "") for a in alerts[:3])
    return {
        "id": "import-health-monitor",
        "type": "status",
        "label": "Import Health Monitor",
        "size": "full",
        "message": msg,
        "status": status,
        "hint": hint,
        "alerts": alerts,
        "halChips": [
            {"label": "Import status", "query": "Verify SoftDent and QuickBooks import status"},
            {"label": "Sync & refill", "query": "Sync imports and populate the widgets"},
            {"label": "Refresh SoftDent period", "query": "Refresh SoftDent period imports"},
        ],
    }


# ——— IMP-004 ERA 835 ingest ———


def ingest_era_835(
    content: str,
    claim_rows: list[dict[str, Any]] | None = None,
    *,
    filename: str | None = None,
) -> dict[str, Any]:
    from era835_parser import fuzzy_match_claims, parse_835_text

    parsed = parse_835_text(content)
    if not parsed.get("ok"):
        return {"ok": False, "error": "ERA parse failed"}
    segments = parsed.get("segments") if isinstance(parsed.get("segments"), list) else []
    rows = claim_rows if isinstance(claim_rows, list) else []
    matches = fuzzy_match_claims(segments, rows) if rows else []
    matched = [m for m in matches if m.get("claimId") and float(m.get("confidence") or 0) >= 0.55]
    data = _load_json(STORE_KEY_ERA_MATCHES)
    by_claim = data.get("byClaim") if isinstance(data.get("byClaim"), dict) else {}
    for m in matched:
        cid = str(m.get("claimId") or "")
        if not cid:
            continue
        by_claim[cid] = {
            "claimId": cid,
            "patientName": m.get("patientName"),
            "confidence": m.get("confidence"),
            "paidAmount": m.get("paidAmount"),
            "denialCode": (m.get("segment") or {}).get("status") if isinstance(m.get("segment"), dict) else None,
            "matchedAt": _utc_now(),
            "sourceFile": filename or None,
            "source": "era-835",
        }
    history = data.get("history") if isinstance(data.get("history"), list) else []
    history.append(
        {
            "id": str(uuid.uuid4())[:8],
            "at": _utc_now(),
            "filename": filename,
            "segmentCount": len(segments),
            "matchedCount": len(matched),
        }
    )
    data["byClaim"] = by_claim
    data["history"] = history[-50:]
    data["updatedAt"] = _utc_now()
    _save_json(STORE_KEY_ERA_MATCHES, data)
    _audit("era:ingest", {"segments": len(segments), "matched": len(matched), "file": filename})
    result = {
        "ok": True,
        "segmentCount": len(segments),
        "matchedCount": len(matched),
        "matches": matched[:40],
        "byClaimCount": len(by_claim),
    }
    # HAL-said improve: denial→Steve + EOB backlog (NR2-local only)
    try:
        from apex_hal_said_improve_pack import process_era_workflow

        result["halSaidWorkflow"] = process_era_workflow(result, filename=filename)
    except Exception as exc:  # noqa: BLE001
        result["halSaidWorkflow"] = {"ok": False, "error": str(exc)}
    return result


def era_matches_map() -> dict[str, dict[str, Any]]:
    data = _load_json(STORE_KEY_ERA_MATCHES)
    by_claim = data.get("byClaim") if isinstance(data.get("byClaim"), dict) else {}
    return {str(k): v for k, v in by_claim.items() if isinstance(v, dict)}


def apply_era_to_kanban_columns(columns: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """Promote matched claims into eraMatched when SoftDent status didn't already."""
    matches = era_matches_map()
    if not matches or not isinstance(columns, dict):
        return columns
    out = {k: list(v) if isinstance(v, list) else [] for k, v in columns.items()}
    moved: list[dict[str, Any]] = []
    for col in ("submitted", "pendingReview", "denied"):
        keep: list[dict[str, Any]] = []
        for card in out.get(col) or []:
            if not isinstance(card, dict):
                continue
            cid = str(card.get("claimId") or "")
            if cid in matches:
                enriched = dict(card)
                m = matches[cid]
                enriched["eraStatus"] = "ERA Matched"
                if m.get("denialCode") and str(m.get("denialCode")) not in {"1", "2", "3", "4", "19", "20", "21", "22"}:
                    # Keep SoftDent denial column if already denied; else mark matched
                    pass
                if col != "denied":
                    enriched["column"] = "eraMatched"
                    moved.append(enriched)
                    continue
            keep.append(card)
        out[col] = keep
    # Don't duplicate if already in eraMatched/paid
    existing = {str(c.get("claimId")) for c in (out.get("eraMatched") or []) + (out.get("paid") or []) if isinstance(c, dict)}
    for card in moved:
        if str(card.get("claimId")) not in existing:
            out.setdefault("eraMatched", []).append(card)
            existing.add(str(card.get("claimId")))
    return out


# ——— IMP-005 A/R forecast ———


def build_ar_forecast_widget(reports: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    """Forward-looking A/R buckets from current aging + optional ERA payer velocity. Honest labels."""
    del bundle
    ar = reports.get("arAging") if isinstance(reports.get("arAging"), dict) else {}
    buckets = reports.get("arAgingBuckets") if isinstance(reports.get("arAgingBuckets"), list) else []
    current: list[dict[str, Any]] = []
    for b in buckets:
        if not isinstance(b, dict):
            continue
        amt = b.get("amount")
        if isinstance(amt, (int, float)):
            current.append({"label": str(b.get("bucket") or ""), "value": float(amt)})
    if not current:
        return {
            "id": "ar-aging-forecast",
            "type": "stacked-bar",
            "label": "A/R Aging Forecast",
            "size": "l",
            "segments": [],
            "status": "empty",
            "emptyMessage": "No A/R buckets for forecast",
            "hint": "Import SoftDent A/R aging. Forecast is illustrative — not a cash guarantee.",
        }
    # Simple roll-forward: 30% of current 0-30 → stays collectible next period; 60/90 decay slower
    forecast: list[dict[str, Any]] = []
    for item in current:
        lab = item["label"].lower()
        v = float(item["value"])
        if "90" in lab or "120" in lab:
            nxt = round(v * 0.85, 2)  # slow decay assumption — labeled illustrative
        elif "60" in lab:
            nxt = round(v * 0.7, 2)
        elif "30" in lab:
            nxt = round(v * 0.55, 2)
        else:
            nxt = round(v * 0.6, 2)
        forecast.append({"label": item["label"], "value": nxt})
    era = era_matches_map()
    hint = (
        "Illustrative next-period A/R by aging bucket (decay heuristic). "
        "Not a cash forecast. Verify with collections."
    )
    if era:
        hint += f" · {len(era)} ERA match(es) on file may accelerate collections."
    return {
        "id": "ar-aging-forecast",
        "type": "stacked-bar",
        "label": "A/R Aging Forecast",
        "size": "l",
        "segments": forecast,
        "current": current,
        "status": "ok",
        "hint": hint,
        "illustrative": True,
    }


# ——— IMP-006 Claim attachments ———


def list_claim_attachments(claim_id: str | None = None) -> list[dict[str, Any]]:
    data = _load_json(STORE_KEY_CLAIM_ATTACHMENTS)
    items = data.get("items") if isinstance(data.get("items"), list) else []
    out = [i for i in items if isinstance(i, dict)]
    if claim_id:
        want = str(claim_id).strip()
        out = [i for i in out if str(i.get("claimId") or "") == want]
    return list(reversed(out))


def save_claim_attachment(
    *,
    claim_id: str,
    filename: str,
    raw: bytes,
    note: str | None = None,
) -> dict[str, Any]:
    from document_sync import NR2_DATA_DIR

    cid = str(claim_id or "").strip()
    if not cid:
        return {"ok": False, "error": "claimId required"}
    safe_name = re.sub(r"[^\w.\-]+", "_", Path(filename or "attachment.bin").name)[:120]
    ext = Path(safe_name).suffix.lower()
    allowed = {".pdf", ".png", ".jpg", ".jpeg"}
    if ext not in allowed:
        return {
            "ok": False,
            "error": f"File type not allowed ({ext or 'none'}). Allowed: PDF, PNG, JPG (max 10MB).",
        }
    if len(raw) > 10 * 1024 * 1024:
        return {"ok": False, "error": "File exceeds 10MB limit"}
    # Lightweight content sniff (not a full AV scan — operator-approved gate)
    head = raw[:8]
    if ext == ".pdf" and not head.startswith(b"%PDF"):
        return {"ok": False, "error": "File content does not look like a PDF"}
    if ext in {".png"} and not head.startswith(b"\x89PNG\r\n\x1a\n"):
        return {"ok": False, "error": "File content does not look like a PNG"}
    if ext in {".jpg", ".jpeg"} and not head.startswith(b"\xff\xd8"):
        return {"ok": False, "error": "File content does not look like a JPEG"}
    dest_dir = Path(NR2_DATA_DIR) / "claim_attachments" / re.sub(r"[^\w\-]+", "_", cid)[:80]
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4().hex[:8]}_{safe_name}"
    dest.write_bytes(raw)
    entry = {
        "id": str(uuid.uuid4())[:10],
        "claimId": cid,
        "filename": safe_name,
        "relPath": str(dest.relative_to(NR2_DATA_DIR)).replace("\\", "/"),
        "bytes": len(raw),
        "note": (note or "")[:500],
        "at": _utc_now(),
        "storageRoot": str(Path(NR2_DATA_DIR) / "claim_attachments").replace("\\", "/"),
    }
    data = _load_json(STORE_KEY_CLAIM_ATTACHMENTS)
    items = data.get("items") if isinstance(data.get("items"), list) else []
    items.append(entry)
    data["items"] = items[-500:]
    _save_json(STORE_KEY_CLAIM_ATTACHMENTS, data)
    _audit("claim:attachment", {"claimId": cid, "file": safe_name})
    return {"ok": True, "attachment": entry}


def attachment_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in list_claim_attachments():
        cid = str(item.get("claimId") or "")
        if cid:
            counts[cid] = counts.get(cid, 0) + 1
    return counts


def claim_attachments_widget() -> dict[str, Any]:
    items = list_claim_attachments()
    n = len(items)
    return {
        "id": "claim-attachments-bridge",
        "type": "claim-attachments",
        "label": "Claim Attachments",
        "size": "l",
        "count": n,
        "items": items[:30],
        "status": "ok" if n else "empty",
        "emptyMessage": "No claim attachments uploaded yet",
        "hint": "Upload EOB / pre-auth / x-ray PDFs linked to a SoftDent claim ID. Stored under app_data/nr2/claim_attachments.",
    }


# ——— IMP-007 Daily huddle ———


def build_daily_huddle_widget(reports: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    priorities: list[str] = []
    health = assess_import_health(bundle)
    for a in health.get("alerts") or []:
        if isinstance(a, dict) and a.get("message"):
            priorities.append(str(a["message"]))
    try:
        from apex_hal_said_improve_pack import huddle_extra_priorities

        for extra in huddle_extra_priorities():
            if extra not in priorities:
                priorities.append(extra)
    except Exception:
        pass

    # Claims 90+
    try:
        from apex_claims_narratives_pack import build_aging_buckets

        rows = []
        softdent = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
        for key in ("claims", "claimStatus"):
            sec = softdent.get(key)
            if isinstance(sec, dict) and isinstance(sec.get("rows"), list):
                rows = sec["rows"]
                break
            if isinstance(sec, list):
                rows = sec
                break
        aging = build_aging_buckets(rows)
        c90 = int((aging.get("counts") or {}).get("90") or 0)
        if c90:
            priorities.append(f"{c90} claim(s) aged 90+ days")
    except Exception:
        pass

    ar = reports.get("arAging") if isinstance(reports.get("arAging"), dict) else {}
    ninety = ar.get("ninetyPlusOutstanding")
    if isinstance(ninety, (int, float)) and float(ninety) >= 5000:
        priorities.append(f"A/R 90+ outstanding ${float(ninety):,.0f}")

    # Operatory utilization signal (chair-shaped import)
    op_count = 0
    chair_n = 0
    slot_n = 0
    try:
        softdent = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
        chairs: list[Any] = []
        for key in ("operatory", "operatorySchedule", "schedule"):
            sec = softdent.get(key)
            if isinstance(sec, dict) and isinstance(sec.get("operatoryChairs"), list):
                chairs = sec["operatoryChairs"]
                break
            if isinstance(sec, dict) and isinstance(sec.get("rows"), list):
                op_count = len(sec["rows"])
                break
            if isinstance(sec, list):
                op_count = len(sec)
                break
        if chairs:
            chair_n = len(chairs)
            for chair in chairs:
                if isinstance(chair, dict) and isinstance(chair.get("slots"), list):
                    slot_n += len(chair["slots"])
            op_count = slot_n
    except Exception:
        op_count = 0
    if chair_n:
        priorities.append(f"Operatory: {chair_n} chair(s), {slot_n} scheduled slot(s)")
    elif op_count:
        priorities.append(f"Operatory schedule rows on import: {op_count}")

    if not priorities:
        priorities.append("No urgent flags — verify imports and review Claims Workbench.")

    return {
        "id": "om-daily-huddle",
        "type": "daily-huddle",
        "label": "Daily Huddle",
        "size": "full",
        "priorities": priorities[:8],
        "status": "ok",
        "hint": "Morning priorities from import health, claims aging, and A/R — import-backed only.",
        "halChips": [
            {"label": "Morning briefing", "query": "Morning briefing"},
            {"label": "Focus 90-day claims", "query": "Focus 90-day claims"},
            {"label": "Import health", "query": "Import health status"},
        ],
    }


# ——— IMP-008 Batch narratives ———


def batch_narrative_seed(claim_ids: list[str], *, payer: str | None = None) -> dict[str, Any]:
    ids = [str(x).strip() for x in claim_ids if str(x).strip()]
    if not ids:
        return {"ok": False, "error": "Select at least one claim ID"}
    return {
        "ok": True,
        "seed": {
            "claimIds": ids,
            "claimId": ids[0],
            "payer": payer or "",
            "bulkAppeal": True,
            "batchNarrative": True,
        },
        "count": len(ids),
    }


# ——— IMP-010 EBITDA trend ———


def record_ebitda_snapshot(value: float | None, *, label: str | None = None) -> None:
    if value is None:
        return
    data = _load_json(STORE_KEY_EBITDA_TREND)
    points = data.get("points") if isinstance(data.get("points"), list) else []
    points.append({"at": _utc_now(), "value": float(value), "label": label or _utc_now()[:7]})
    data["points"] = points[-24:]
    _save_json(STORE_KEY_EBITDA_TREND, data)


def build_ebitda_trend_widget(bundle: dict[str, Any]) -> dict[str, Any]:
    # Capture current walk if available
    current = None
    try:
        from tax_engine import compute_ebitda_walk

        walk = compute_ebitda_walk(bundle) or {}
        if isinstance(walk.get("ebitda"), (int, float)):
            current = float(walk["ebitda"])
            record_ebitda_snapshot(current)
    except Exception:
        pass
    data = _load_json(STORE_KEY_EBITDA_TREND)
    points = data.get("points") if isinstance(data.get("points"), list) else []
    series = []
    for p in points:
        if isinstance(p, dict) and isinstance(p.get("value"), (int, float)):
            series.append({"label": str(p.get("label") or p.get("at") or "")[:10], "value": float(p["value"])})
    if not series and current is not None:
        series = [{"label": "now", "value": current}]
    if not series:
        return {
            "id": "ebitda-trend",
            "type": "chart",
            "chartType": "line",
            "label": "EBITDA Trend",
            "size": "l",
            "series": [],
            "status": "empty",
            "emptyMessage": "No EBITDA snapshots yet",
            "hint": "Import QuickBooks P&L. Snapshots accumulate as you open Financial/Taxes.",
        }
    return {
        "id": "ebitda-trend",
        "type": "chart",
        "chartType": "line",
        "label": "EBITDA Trend",
        "size": "l",
        "series": series[-12:],
        "status": "ok",
        "hint": "Rolling snapshots of management EBITDA from tax_engine — advisory only; verify with CPA.",
    }
