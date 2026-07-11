"""Assemble unified patient dossier from SoftDent stores. READ-ONLY. Empty≠$0.

Moonshot HAL Patient Full Summary consult 2026-07-11 — adapted to real sd_* schema
(softdent_odbc_extract.ensure_sd_schema). No SoftDent writes. Claims join via
patient_name (sd_claims has no patient_id). Clinical notes via nr2_clinical_bridge.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from softdent_odbc_extract import resolve_sd_sqlite_db

# NICE: 5-minute server-side cache
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_TTL_SEC = 300.0

# Rate limit: 1 dossier request per 10 seconds per staff session
_RATE: dict[str, float] = {}
_RATE_WINDOW_SEC = 10.0


def _safe_money(val: Any) -> str:
    """Honesty: NULL, empty, or 0 → 'unknown'. Never invent $0.00."""
    if val is None or val == "":
        return "unknown"
    try:
        num = float(val)
    except (TypeError, ValueError):
        return "unknown"
    if num == 0:
        return "unknown"
    return f"${num:.2f}"


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def _open_db() -> tuple[sqlite3.Connection | None, Any]:
    db_path = resolve_sd_sqlite_db()
    if not db_path or not db_path.is_file():
        return None, db_path
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn, db_path


def patient_hash(patient_id: str) -> str:
    raw = str(patient_id or "").strip()
    if not raw:
        return "——"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:4].upper()


def name_hash(name: str) -> str:
    raw = str(name or "").strip()
    if not raw:
        return "——"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:4].upper()


def _initials(raw_name: str) -> str:
    parts = [x for x in str(raw_name or "").split() if x]
    letters = "".join(p[0] for p in parts[:2] if p).upper()
    return f"{letters or 'P'}—"


def check_rate_limit(session_key: str) -> tuple[bool, float]:
    """Return (allowed, retry_after_sec)."""
    key = str(session_key or "anon").strip() or "anon"
    now = time.time()
    last = _RATE.get(key, 0.0)
    elapsed = now - last
    if elapsed < _RATE_WINDOW_SEC:
        return False, round(_RATE_WINDOW_SEC - elapsed, 1)
    _RATE[key] = now
    return True, 0.0


def clear_dossier_cache() -> None:
    _CACHE.clear()


def build_patient_dossier(
    patient_id: str,
    practice_id: str = "",
    *,
    use_cache: bool = True,
    include_clinical: bool = True,
    include_estimates: bool = True,
) -> dict[str, Any]:
    """Build PHI-safe dossier JSON from local SoftDent extract + clinical bridge.

    Financial fields use _safe_money (empty≠$0). SoftDent SELECT only.
    """
    pid = str(patient_id or "").strip()
    practice = str(practice_id or "").strip()
    cache_key = f"{practice}|{pid}"
    if use_cache and cache_key in _CACHE:
        ts, cached = _CACHE[cache_key]
        if time.time() - ts < _CACHE_TTL_SEC:
            out = dict(cached)
            out["cached"] = True
            return out

    dossier: dict[str, Any] = {
        "patientId": pid,
        "patientHash": patient_hash(pid),
        "practiceId": practice or "default",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "demographics": {},
        "appointments": [],
        "procedures": [],
        "transactions": {"payments": [], "adjustments": []},
        "claims": [],
        "clinicalNotes": [],
        "treatmentEstimates": [],
        "gaps": [],
        "source": "sd_*",
        "readOnly": True,
        "honesty": "Empty financial fields render as 'unknown', never $0. SoftDent is read-only.",
    }
    if not pid:
        dossier["gaps"].append("patient_id required")
        dossier["ok"] = False
        return dossier

    conn, db_path = _open_db()
    dossier["dbPath"] = str(db_path) if db_path else None
    if not conn:
        dossier["gaps"].append("SoftDent analytics DB unavailable — run SoftDent extract.")
        dossier["ok"] = False
        return dossier

    patient_name = ""
    try:
        cur = conn.cursor()

        # Demographics — real columns: patient_id, patient_name, first/last_visit_date
        if _table_exists(conn, "sd_patients"):
            if practice:
                cur.execute(
                    """
                    SELECT patient_name, first_visit_date, last_visit_date, practice_id
                    FROM sd_patients WHERE patient_id=? AND practice_id=?
                    LIMIT 1
                    """,
                    (pid, practice),
                )
            else:
                cur.execute(
                    """
                    SELECT patient_name, first_visit_date, last_visit_date, practice_id
                    FROM sd_patients WHERE patient_id=?
                    LIMIT 1
                    """,
                    (pid,),
                )
            row = cur.fetchone()
            if row:
                patient_name = str(row["patient_name"] or "")
                practice = practice or str(row["practice_id"] or "")
                dossier["practiceId"] = practice or "default"
                dossier["demographics"] = {
                    "nameHash": name_hash(patient_name),
                    "initials": _initials(patient_name),
                    "firstVisit": row["first_visit_date"] or "unknown",
                    "lastVisit": row["last_visit_date"] or "unknown",
                }
            else:
                dossier["gaps"].append("Patient not found in sd_patients")
        else:
            dossier["gaps"].append("sd_patients table missing")

        # Appointments (last 3 past-ish + recent 5 total — schema has no appt_time)
        if _table_exists(conn, "sd_appointments"):
            cur.execute(
                """
                SELECT appt_date, provider_code, status
                FROM sd_appointments
                WHERE patient_id=?
                ORDER BY appt_date DESC
                LIMIT 5
                """,
                (pid,),
            )
            for r in cur.fetchall():
                dossier["appointments"].append(
                    {
                        "date": r["appt_date"] or "unknown",
                        "provider": r["provider_code"] or "unknown",
                        "status": r["status"] or "unknown",
                        "time": "—",  # SoftDent schema lacks appt_time
                    }
                )
        else:
            dossier["gaps"].append("sd_appointments table missing")

        # Procedures (last 5)
        recent_adas: list[str] = []
        if _table_exists(conn, "sd_procedures"):
            cur.execute(
                """
                SELECT proc_date, ada_code, tooth, surface, provider_code, description, production
                FROM sd_procedures
                WHERE patient_id=?
                ORDER BY proc_date DESC
                LIMIT 5
                """,
                (pid,),
            )
            for r in cur.fetchall():
                ada = str(r["ada_code"] or "").strip()
                if ada:
                    recent_adas.append(ada)
                dossier["procedures"].append(
                    {
                        "date": r["proc_date"] or "unknown",
                        "ada": ada or "unknown",
                        "tooth": r["tooth"] or "—",
                        "surface": r["surface"] or "—",
                        "provider": r["provider_code"] or "unknown",
                        "description": (r["description"] or "")[:120] or "—",
                        "production": _safe_money(r["production"]),
                    }
                )
        else:
            dossier["gaps"].append("sd_procedures table missing")

        # Transactions — payments + adjustments last 12 months
        since = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
        payer_hint = ""
        if _table_exists(conn, "sd_payments"):
            cur.execute(
                """
                SELECT payment_date, amount, payer, method
                FROM sd_payments
                WHERE patient_id=? AND payment_date >= ?
                ORDER BY payment_date DESC
                LIMIT 10
                """,
                (pid, since),
            )
            for r in cur.fetchall():
                if not payer_hint and r["payer"]:
                    payer_hint = str(r["payer"])
                dossier["transactions"]["payments"].append(
                    {
                        "date": r["payment_date"] or "unknown",
                        "amount": _safe_money(r["amount"]),
                        "payer": r["payer"] or "unknown",
                        "method": r["method"] or "unknown",
                    }
                )
        else:
            dossier["gaps"].append("sd_payments table missing")

        if _table_exists(conn, "sd_adjustments"):
            cur.execute(
                """
                SELECT adj_date, ada_code, amount, description
                FROM sd_adjustments
                WHERE patient_id=? AND adj_date >= ?
                ORDER BY adj_date DESC
                LIMIT 10
                """,
                (pid, since),
            )
            for r in cur.fetchall():
                dossier["transactions"]["adjustments"].append(
                    {
                        "date": r["adj_date"] or "unknown",
                        "ada": r["ada_code"] or "—",
                        "amount": _safe_money(r["amount"]),
                        "description": (r["description"] or "")[:80] or "—",
                    }
                )
        else:
            dossier["gaps"].append("sd_adjustments table missing")

        # Claims — sd_claims uses patient_name, NOT patient_id (schema honesty)
        if _table_exists(conn, "sd_claims"):
            if patient_name:
                cur.execute(
                    """
                    SELECT claim_id, payer, service_date, claim_amount, claim_status
                    FROM sd_claims
                    WHERE patient_name=?
                    ORDER BY service_date DESC
                    LIMIT 10
                    """,
                    (patient_name,),
                )
                for r in cur.fetchall():
                    if not payer_hint and r["payer"]:
                        payer_hint = str(r["payer"])
                    dossier["claims"].append(
                        {
                            "claimId": r["claim_id"] or "unknown",
                            "payer": r["payer"] or "unknown",
                            "serviceDate": r["service_date"] or "unknown",
                            "amount": _safe_money(r["claim_amount"]),
                            "status": r["claim_status"] or "unknown",
                        }
                    )
            else:
                dossier["gaps"].append(
                    "Claims skipped: sd_claims has no patient_id; patient_name unavailable for join"
                )
        else:
            dossier["gaps"].append("sd_claims table missing")

        # Treatment estimates — aggregate lookup for recent ADAs × payer hint (no invented $)
        if include_estimates and recent_adas:
            try:
                from softdent_treatment_planning import lookup_treatment_estimate

                seen: set[str] = set()
                for ada in recent_adas:
                    if ada in seen:
                        continue
                    seen.add(ada)
                    if not payer_hint:
                        dossier["treatmentEstimates"].append(
                            {
                                "ada": ada,
                                "estimate": "unknown",
                                "reason": "No payer on file for estimate lookup",
                            }
                        )
                        continue
                    est = lookup_treatment_estimate(payer=payer_hint, ada_code=ada)
                    if est.get("found") and est.get("sufficient") and est.get("estimate") is not None:
                        dossier["treatmentEstimates"].append(
                            {
                                "ada": ada,
                                "payer": payer_hint,
                                "estimate": _safe_money(est.get("estimate")),
                                "sampleSize": est.get("sampleSize"),
                                "honesty": est.get("honesty"),
                            }
                        )
                    else:
                        dossier["treatmentEstimates"].append(
                            {
                                "ada": ada,
                                "payer": payer_hint or "unknown",
                                "estimate": "unknown",
                                "reason": est.get("message")
                                or "Insufficient sample or no estimate row",
                            }
                        )
            except Exception as exc:  # noqa: BLE001
                dossier["gaps"].append(f"treatment estimate lookup failed: {exc}")

    finally:
        conn.close()

    # Clinical notes — no clinical_note_imports table; use SideNotes/clinical bridge
    if include_clinical:
        try:
            from nr2_clinical_bridge import load_clinical_context

            ctx = load_clinical_context(
                None,
                patient_id=pid,
                patient_name=patient_name,
                limit=5,
            )
            for item in (ctx.get("items") or [])[:5]:
                if not isinstance(item, dict):
                    continue
                dossier["clinicalNotes"].append(
                    {
                        "summary": str(item.get("summary") or item.get("text") or "")[:400],
                        "source": item.get("source") or "clinical",
                        "station": item.get("station") or "",
                    }
                )
            if not dossier["clinicalNotes"]:
                dossier["gaps"].append("No clinical note summaries for this patient (SideNotes/inbox empty)")
        except Exception as exc:  # noqa: BLE001
            dossier["gaps"].append(f"clinical context unavailable: {exc}")

    dossier["ok"] = True
    if use_cache:
        _CACHE[cache_key] = (time.time(), dict(dossier))
    return dossier


def format_dossier_markdown(dossier: dict[str, Any]) -> str:
    """Deterministic staff summary (honesty rules; no invented dollars)."""
    d = dossier or {}
    demo = d.get("demographics") if isinstance(d.get("demographics"), dict) else {}
    lines = [
        f"**Patient {d.get('patientHash') or '——'} — Dossier Summary**",
        "",
        "### Demographics",
        f"- Initials: {demo.get('initials') or '—'}",
        f"- First visit: {demo.get('firstVisit') or 'unknown'}",
        f"- Last visit: {demo.get('lastVisit') or 'unknown'}",
        "",
        "### Appointments",
    ]
    appts = d.get("appointments") or []
    if not appts:
        lines.append("- No SoftDent appointments on file")
    else:
        for a in appts[:5]:
            lines.append(
                f"- {a.get('date')} · {a.get('provider')} · {a.get('status')} · time {a.get('time') or '—'}"
            )

    lines.extend(["", "### Procedures"])
    procs = d.get("procedures") or []
    if not procs:
        lines.append("- No SoftDent procedures on file")
    else:
        for p in procs[:5]:
            lines.append(
                f"- {p.get('date')} · {p.get('ada')} · tooth {p.get('tooth')} · "
                f"prod {p.get('production')} · {p.get('provider')}"
            )

    txn = d.get("transactions") if isinstance(d.get("transactions"), dict) else {}
    lines.extend(["", "### Transactions (12 mo)"])
    pays = txn.get("payments") or []
    adjs = txn.get("adjustments") or []
    if not pays and not adjs:
        lines.append("- No SoftDent payments/adjustments in window (empty ≠ $0)")
    for p in pays[:5]:
        lines.append(f"- Payment {p.get('date')}: {p.get('amount')} · {p.get('payer')} · {p.get('method')}")
    for a in adjs[:5]:
        lines.append(f"- Adj {a.get('date')}: {a.get('amount')} · {a.get('ada')} · {a.get('description')}")

    lines.extend(["", "### Claims"])
    claims = d.get("claims") or []
    if not claims:
        lines.append("- No SoftDent claims matched (join via patient_name when available)")
    else:
        for c in claims[:5]:
            lines.append(
                f"- {c.get('claimId')} · {c.get('payer')} · {c.get('serviceDate')} · "
                f"{c.get('amount')} · {c.get('status')}"
            )

    lines.extend(["", "### Treatment Estimates"])
    ests = d.get("treatmentEstimates") or []
    if not ests:
        lines.append("- No treatment estimates (need payer × ADA sample)")
    else:
        for e in ests[:5]:
            reason = e.get("reason")
            extra = f" ({reason})" if reason else ""
            lines.append(f"- {e.get('ada')}: {e.get('estimate')}{extra}")

    lines.extend(["", "### Clinical Notes"])
    notes = d.get("clinicalNotes") or []
    if not notes:
        lines.append("- No clinical summaries on file")
    else:
        for n in notes[:5]:
            lines.append(f"- {str(n.get('summary') or '')[:200]}")

    gaps = d.get("gaps") or []
    if gaps:
        lines.extend(["", "### Gaps / honesty"])
        for g in gaps[:8]:
            lines.append(f"- {g}")

    lines.append("")
    lines.append("_SoftDent read-only · empty≠$0 · local PHI only_")
    return "\n".join(lines)


def summarize_dossier_with_local_ai(dossier: dict[str, Any]) -> dict[str, Any]:
    """Prompt local hal-local:24b with DOSSIER_SUMMARY_PROMPT. Falls back to markdown."""
    from patient_dossier_prompts import DOSSIER_SUMMARY_PROMPT

    import json

    dossier_json = json.dumps(dossier, indent=2, default=str)[:12000]
    prompt = DOSSIER_SUMMARY_PROMPT.format(dossier_json=dossier_json)
    deterministic = format_dossier_markdown(dossier)

    try:
        from nr2_hal_gateway import call_ollama_chat

        result = call_ollama_chat(
            model="hal-local:24b",
            messages=[
                {"role": "system", "content": "You are NR2-HAL. Follow the user rules exactly."},
                {"role": "user", "content": prompt},
            ],
            stream=False,
            options={"temperature": 0.1, "num_predict": 400},
        )
        if result.get("ok"):
            from nr2_hal_gateway import extract_ollama_message_text

            message = (result.get("body") or {}).get("message") or result.get("message") or {}
            text = extract_ollama_message_text(message)
            if text and text.strip():
                # Guard: never allow $0.00 hallucination for zero/empty
                cleaned = text.strip()
                if "$0.00" in cleaned or "$0" in cleaned:
                    # Prefer deterministic when model invents zeros
                    return {
                        "ok": True,
                        "summary": deterministic,
                        "source": "deterministic_after_zero_guard",
                        "model": "hal-local:24b",
                    }
                return {
                    "ok": True,
                    "summary": cleaned[:4000],
                    "source": "hal-local:24b",
                    "model": "hal-local:24b",
                }
        return {
            "ok": True,
            "summary": deterministic,
            "source": "deterministic_fallback",
            "error": result.get("error") or result.get("detail") or "ollama unavailable",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "summary": deterministic,
            "source": "deterministic_fallback",
            "error": str(exc),
        }
