"""Assemble unified patient dossier from SoftDent stores. READ-ONLY. Empty≠$0.

Moonshot HAL Patient Full Summary consult 2026-07-11 — adapted to real sd_* schema
(softdent_odbc_extract.ensure_sd_schema). No SoftDent writes. Claims join via
patient_name (sd_claims has no patient_id). Clinical notes via nr2_clinical_bridge.
"""

from __future__ import annotations

import hashlib
import os
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


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return {str(row[1]) for row in cur.fetchall()}


def _dossier_eligibility_enabled() -> bool:
    return os.environ.get("DOSSIER_ELIGIBILITY_ENABLED", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _empty_eligibility(*, error: str | None = None) -> dict[str, Any]:
    return {
        "queriedAt": datetime.now(timezone.utc).isoformat(),
        "source": "availity_271",
        "live": False,
        "demo": False,
        "scope": None,
        "gaps": [],
        "benefits": None,
        "error": error,
        "cacheHit": False,
    }


def _normalize_money_field(val: Any) -> str | float:
    if val in (None, "", 0, 0.0):
        return "unknown"
    return val


def _normalize_eligibility_benefits(entry: dict[str, Any]) -> dict[str, Any]:
    """Map cache/271 entry to dossier benefits; empty money → 'unknown'."""
    preventive = entry.get("preventive")
    if preventive in (None, ""):
        preventive = entry.get("coinsurancePreventive")
    basic = entry.get("basic")
    if basic in (None, ""):
        basic = entry.get("coinsuranceBasic")
    major = entry.get("major")
    if major in (None, ""):
        major = entry.get("coinsuranceMajor")

    limits_raw = entry.get("limitations")
    if isinstance(limits_raw, list):
        limitations = [str(x).strip() for x in limits_raw if str(x).strip()][:5]
    elif isinstance(limits_raw, str) and limits_raw.strip():
        limitations = [x.strip() for x in limits_raw.split(";") if x.strip()][:5]
    else:
        limitations = []

    return {
        "planName": str(entry.get("planName") or entry.get("planDescription") or "unknown").strip() or "unknown",
        "payerName": str(entry.get("payerName") or entry.get("payer") or "unknown").strip() or "unknown",
        "memberIdRedacted": str(entry.get("memberIdRedacted") or "unknown").strip() or "unknown",
        "deductibleRemaining": _normalize_money_field(entry.get("deductibleRemaining")),
        "annualMaxRemaining": _normalize_money_field(entry.get("annualMaxRemaining")),
        "annualMax": _normalize_money_field(entry.get("annualMax")),
        "preventive": str(preventive) if preventive not in (None, "") else "unknown",
        "basic": str(basic) if basic not in (None, "") else "unknown",
        "major": str(major) if major not in (None, "") else "unknown",
        "limitations": limitations,
        "planYear": str(entry.get("planYear") or "unknown"),
        "serviceDate": str(
            entry.get("serviceDate") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        ),
    }


def _resolve_eligibility_for_patient(
    conn: sqlite3.Connection | None,
    patient_id: str,
    practice_id: str,
    *,
    eligibility_overrides: dict[str, Any] | None = None,
    force_fetch: bool = False,
) -> dict[str, Any]:
    """Build eligibility from SoftDent (read-only) + Availity cache; honest gaps, no invention."""
    if not _dossier_eligibility_enabled():
        return _empty_eligibility(error="Eligibility disabled (DOSSIER_ELIGIBILITY_ENABLED=0)")

    eligibility: dict[str, Any] = _empty_eligibility()
    overrides = eligibility_overrides if isinstance(eligibility_overrides, dict) else {}

    member_id = str(overrides.get("memberId") or overrides.get("member_id") or "").strip() or None
    payer_id = str(overrides.get("payerId") or overrides.get("payer_id") or "").strip() or None
    payer_name = str(overrides.get("payerName") or overrides.get("payer_name") or "").strip() or None
    provider_npi = str(
        overrides.get("providerNpi") or overrides.get("provider_npi") or os.environ.get("NR2_PROVIDER_NPI", "")
    ).strip() or None

    if conn and not member_id and _table_exists(conn, "sd_patient_insurance"):
        cols = _column_names(conn, "sd_patient_insurance")
        select_cols = [c for c in ("member_id", "subscriber_id", "insurance_name", "payer_id") if c in cols]
        if select_cols:
            order = " ORDER BY priority ASC" if "priority" in cols else ""
            cur = conn.cursor()
            cur.execute(
                f"SELECT {', '.join(select_cols)} FROM sd_patient_insurance "
                f"WHERE patient_id = ?{order} LIMIT 1",
                (patient_id,),
            )
            row = cur.fetchone()
            if row:
                row_d = dict(row)
                if not member_id:
                    member_id = (
                        str(row_d.get("member_id") or row_d.get("subscriber_id") or "").strip() or None
                    )
                if not payer_name:
                    payer_name = str(row_d.get("insurance_name") or "").strip() or None
                if not payer_id:
                    payer_id = str(row_d.get("payer_id") or "").strip() or None

    if not provider_npi:
        provider_npi = os.environ.get("NR2_PROVIDER_NPI", "").strip() or None

    if not member_id:
        eligibility["gaps"].append("memberId")
    if not payer_id and not payer_name:
        eligibility["gaps"].append("payerId")
    if not provider_npi:
        eligibility["gaps"].append("providerNPI")

    if eligibility["gaps"]:
        if payer_name and "memberId" in eligibility["gaps"]:
            eligibility["error"] = (
                f"Primary insurance on file ({payer_name}) but Member ID missing from SoftDent. "
                f"Gaps: {', '.join(eligibility['gaps'])}"
            )
        else:
            eligibility["error"] = f"SoftDent missing: {', '.join(eligibility['gaps'])}"
        return eligibility

    cache_seed = f"{patient_id}:{member_id}:{payer_id or payer_name}:{provider_npi}"
    cache_key = patient_hash(cache_seed)

    try:
        from eligibility_cache_store import get_cached_eligibility, store_eligibility_snapshot
        from clearinghouse_eligibility_adapter import fetch_eligibility_271

        cached = get_cached_eligibility(cache_key)
        if cached:
            benefits = _normalize_eligibility_benefits(cached)
            eligibility["benefits"] = benefits
            eligibility["demo"] = bool(cached.get("demo"))
            eligibility["live"] = not eligibility["demo"]
            eligibility["scope"] = "demo" if eligibility["demo"] else "live"
            eligibility["cacheHit"] = True
            return eligibility

        if not force_fetch:
            eligibility["error"] = (
                "Eligibility not queried — use HAL fetch_eligibility_271 with member/payer details, "
                "or pass fetchEligibility=1 with overrides."
            )
            return eligibility

        req = {
            "memberId": member_id,
            "payerId": payer_id or "",
            "payerName": payer_name or "",
            "providerNpi": provider_npi,
            "vendor": "availity",
        }
        result = fetch_eligibility_271(req)
        if result.get("ok") and result.get("entry"):
            entry = dict(result["entry"])
            benefits = _normalize_eligibility_benefits(entry)
            eligibility["benefits"] = benefits
            eligibility["demo"] = bool(result.get("demo"))
            eligibility["live"] = not eligibility["demo"] and not result.get("demo")
            eligibility["scope"] = "demo" if eligibility["demo"] else "live"
            store_payload = dict(entry)
            store_payload.update(benefits)
            store_payload["demo"] = eligibility["demo"]
            store_eligibility_snapshot(cache_key, store_payload, ttl_sec=300)
        else:
            eligibility["error"] = result.get("message") or result.get("error") or "Eligibility unavailable"
            eligibility["demo"] = bool(result.get("demo"))
    except Exception as exc:  # noqa: BLE001
        eligibility["error"] = f"Eligibility fetch failed: {exc}"

    return eligibility


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
    eligibility_overrides: dict[str, Any] | None = None,
    force_eligibility_fetch: bool = False,
) -> dict[str, Any]:
    """Build PHI-safe dossier JSON from local SoftDent extract + clinical bridge.

    Financial fields use _safe_money (empty≠$0). SoftDent SELECT only.
    """
    pid = str(patient_id or "").strip()
    practice = str(practice_id or "").strip()
    has_elig_overrides = bool(eligibility_overrides)
    skip_dossier_cache = has_elig_overrides or force_eligibility_fetch
    cache_key = f"{practice}|{pid}"
    if use_cache and not skip_dossier_cache and cache_key in _CACHE:
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
        "eligibility": _empty_eligibility(),
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
        dossier["eligibility"] = _resolve_eligibility_for_patient(
            None,
            pid,
            practice,
            eligibility_overrides=eligibility_overrides,
            force_fetch=force_eligibility_fetch,
        )
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

        dossier["eligibility"] = _resolve_eligibility_for_patient(
            conn,
            pid,
            practice,
            eligibility_overrides=eligibility_overrides,
            force_fetch=force_eligibility_fetch,
        )

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
    if use_cache and not skip_dossier_cache:
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

    elig = d.get("eligibility") if isinstance(d.get("eligibility"), dict) else {}
    lines.extend(["", "### Eligibility"])
    demo_prefix = "[DEMO DATA] " if elig.get("demo") else ""
    if elig.get("gaps"):
        lines.append(
            f"- {demo_prefix}Insurance details incomplete in SoftDent: missing {', '.join(elig['gaps'])}. "
            "Use HAL fetch_eligibility_271 tool to query manually."
        )
    elif elig.get("error") and not elig.get("benefits"):
        lines.append(f"- {demo_prefix}{elig.get('error')}")
    elif elig.get("benefits"):
        ben = elig["benefits"]
        lines.append(f"- {demo_prefix}Plan: {ben.get('planName') or 'unknown'} · Payer: {ben.get('payerName') or 'unknown'}")
        ded = ben.get("deductibleRemaining")
        if ded == "unknown":
            lines.append(f"- {demo_prefix}Deductible remaining: unknown")
        else:
            lines.append(f"- {demo_prefix}Deductible remaining: {ded}")
        amax = ben.get("annualMaxRemaining")
        if amax == "unknown":
            lines.append(f"- {demo_prefix}Annual max remaining: unknown")
        else:
            lines.append(f"- {demo_prefix}Annual max remaining: {amax}")
        lines.append(
            f"- {demo_prefix}Preventive: {ben.get('preventive') or 'unknown'} · "
            f"Basic: {ben.get('basic') or 'unknown'} · Major: {ben.get('major') or 'unknown'}"
        )
        if elig.get("cacheHit"):
            lines.append("- (cached eligibility snapshot)")
    else:
        lines.append("- No eligibility data on file")

    gaps = d.get("gaps") or []
    if gaps:
        lines.extend(["", "### Gaps / honesty"])
        for g in gaps[:8]:
            lines.append(f"- {g}")

    lines.append("")
    lines.append("_SoftDent read-only · empty≠$0 · local PHI only_")
    return "\n".join(lines)


def summarize_dossier_with_local_ai(dossier: dict[str, Any]) -> dict[str, Any]:
    """Prompt local hal-local:30b-a3b with DOSSIER_SUMMARY_PROMPT. Falls back to markdown."""
    from patient_dossier_prompts import DOSSIER_SUMMARY_PROMPT

    import json

    dossier_json = json.dumps(dossier, indent=2, default=str)[:12000]
    prompt = DOSSIER_SUMMARY_PROMPT.format(dossier_json=dossier_json)
    deterministic = format_dossier_markdown(dossier)

    try:
        from nr2_hal_gateway import call_ollama_chat

        result = call_ollama_chat(
            model="hal-local:30b-a3b",
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
                        "model": "hal-local:30b-a3b",
                    }
                return {
                    "ok": True,
                    "summary": cleaned[:4000],
                    "source": "hal-local:30b-a3b",
                    "model": "hal-local:30b-a3b",
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
