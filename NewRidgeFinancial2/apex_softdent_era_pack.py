"""
Phase S1 — ERA 835 harden into unified DB + Collections gap (SHOULD wave).

Extends existing ingest_era_835 / era835_parser. Aggregates only (no patient
detail in nr2_unified). Proposals only — never SoftDent write-back.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GAP_ERA_835_AVAILABLE = "ERA_835_AVAILABLE"

FIX_HINT_ERA = (
    "ERA 835 payments detected while SoftDent collections/daysheet still pending. "
    "Review EOB backlog and post in SoftDent manually — Apex never write-backs. "
    "Empty collections ≠ $0."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def era_aggregate_from_ingest_result(result: dict[str, Any] | None) -> dict[str, Any]:
    """Build period aggregate from ingest_era_835 result (totals only)."""
    r = result if isinstance(result, dict) else {}
    matches = r.get("matches") if isinstance(r.get("matches"), list) else []
    total = 0.0
    n = 0
    for m in matches:
        if not isinstance(m, dict):
            continue
        try:
            amt = float(m.get("paidAmount") or 0)
        except (TypeError, ValueError):
            amt = 0.0
        if amt:
            total += amt
            n += 1
    # Fallback: segment count with unknown dollars stays count-only
    if n == 0:
        n = int(r.get("matchedCount") or r.get("segmentCount") or 0)
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    return {
        "period": period,
        "payment_total": total if total else None,
        "claim_count": n,
        "source_file": None,
    }


def record_era_aggregate(
    *,
    payment_total: float | None,
    claim_count: int,
    period: str | None = None,
    source_file: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Store aggregate ERA totals in nr2_unified (no patient identifiers)."""
    from apex_unified_db_pack import open_unified, unified_db_path

    period_key = (period or datetime.now(timezone.utc).strftime("%Y-%m")).strip()[:32]
    now = _utc_now()
    with open_unified(path=db_path) as conn:
        conn.execute(
            """
            INSERT INTO softdent_era_aggregates (
                period, payment_total, claim_count, source_file, source, imported_at
            ) VALUES (?,?,?,?,?,?)
            """,
            (
                period_key,
                payment_total,
                int(claim_count or 0),
                (source_file or "")[:200] or None,
                "era_ingest",
                now,
            ),
        )
        conn.commit()
    return {
        "ok": True,
        "period": period_key,
        "paymentTotal": payment_total,
        "claimCount": claim_count,
        "dbPath": str(db_path or unified_db_path()),
        "localOnly": True,
        "detailNote": "Aggregates only — claim/patient detail stays in ERA match store / secure path.",
    }


def attach_era_to_ingest(result: dict[str, Any], *, filename: str | None = None) -> dict[str, Any]:
    """Hook after ingest_era_835 — additive unified aggregate."""
    out = dict(result) if isinstance(result, dict) else {"ok": False}
    if not out.get("ok"):
        return out
    agg = era_aggregate_from_ingest_result(out)
    try:
        recorded = record_era_aggregate(
            payment_total=agg.get("payment_total"),
            claim_count=int(agg.get("claim_count") or 0),
            period=str(agg.get("period") or ""),
            source_file=filename,
        )
        out["unifiedEraAggregate"] = recorded
    except Exception as exc:  # noqa: BLE001
        out["unifiedEraAggregate"] = {"ok": False, "error": str(exc)}
    return out


def list_era_aggregates(*, limit: int = 12, db_path: Path | None = None) -> list[dict[str, Any]]:
    from apex_unified_db_pack import open_unified

    with open_unified(path=db_path) as conn:
        rows = conn.execute(
            """
            SELECT period, payment_total, claim_count, source_file, imported_at
            FROM softdent_era_aggregates
            ORDER BY imported_at DESC
            LIMIT ?
            """,
            (max(1, min(int(limit), 50)),),
        ).fetchall()
        return [
            {
                "period": r["period"],
                "paymentTotal": r["payment_total"],
                "claimCount": r["claim_count"],
                "sourceFile": r["source_file"],
                "importedAt": r["imported_at"],
            }
            for r in rows
        ]


def era_available_for_period(period: str | None, *, db_path: Path | None = None) -> dict[str, Any]:
    if not period:
        return {"ok": True, "available": False, "paymentTotal": None, "claimCount": 0}
    from apex_unified_db_pack import open_unified

    with open_unified(path=db_path) as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(payment_total), 0) AS total,
                   COALESCE(SUM(claim_count), 0) AS claims
            FROM softdent_era_aggregates
            WHERE period = ?
            """,
            (str(period)[:32],),
        ).fetchone()
        total = float(row["total"] or 0) if row else 0.0
        claims = int(row["claims"] or 0) if row else 0
        return {
            "ok": True,
            "available": claims > 0 or total > 0,
            "paymentTotal": total if total else None,
            "claimCount": claims,
            "period": period,
        }


def enrich_collections_gap_with_era(
    gap: dict[str, Any],
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """
    If collections pending/unreported and ERA aggregates exist for period,
    stamp ERA_835_AVAILABLE proposal (still empty ≠ $0; no SoftDent post).
    """
    out = dict(gap) if isinstance(gap, dict) else {}
    code = str(out.get("gapCode") or "")
    if code not in {
        "COLLECTIONS_PENDING",
        "COLLECTIONS_UNREPORTED",
        "REGISTER_ONLY",
        "NO_PERIOD_ROW",
        "COLLECTIONS_FORMAT_REQUIRED",
        "ERA_835_REQUIRED",
        "COLLECTIONS_EXPORT_REQUIRED",
    }:
        return out
    period = out.get("period")
    era = era_available_for_period(str(period) if period else None, db_path=db_path)
    if not era.get("available"):
        return out
    out["eraAvailable"] = True
    out["eraPaymentTotal"] = era.get("paymentTotal")
    out["eraClaimCount"] = era.get("claimCount")
    out["eraGapCode"] = GAP_ERA_835_AVAILABLE
    # Moonshot hal-10572 — Register Ins Plan $0: keep visible gapCode as REQUIRED
    # (ERA aggregate presence is eraGapCode=AVAILABLE / eraAvailable only).
    if out.get("registerInsPlanZero") or str(out.get("collectionsGapCode") or "") == "ERA_835_REQUIRED":
        out["collectionsGapCode"] = "ERA_835_REQUIRED"
        out["gapCode"] = "ERA_835_REQUIRED"
    else:
        out["gapCode"] = GAP_ERA_835_AVAILABLE
    issues = list(out.get("issues") or [])
    issues.insert(
        0,
        f"{period or 'period'}: ERA 835 aggregate present "
        f"(claims={era.get('claimCount')}, total={era.get('paymentTotal')}) — "
        "proposal only; post in SoftDent.",
    )
    out["issues"] = issues[:12]
    if out.get("registerInsPlanZero"):
        out["fixHint"] = (
            "SoftDent Register reports Ins Plan Collections $0.00 is SoftDent truth — "
            "proceed with ERA-835 for insurance detail. Do not re-export Register hoping Ins Plan > 0. "
            "ERA aggregate is proposal-only — staff post in SoftDent. Empty ≠ $0; no SoftDent write-back."
        )
        # Moonshot hal-10576 — attach empty-inbox scaffold status (never invents $)
        try:
            from apex_era835_pack import scan_era_inbox

            inbox = scan_era_inbox(ensure_dirs=True)
            out["eraInbox"] = {
                "empty": inbox.get("empty"),
                "chipStatus": inbox.get("chipStatus"),
                "chipLabel": inbox.get("chipLabel"),
                "fileCount": inbox.get("fileCount") or 0,
                "honesty": "empty_not_zero",
                "existingRoots": inbox.get("existingRoots") or [],
            }
            # Empty drop-box must not flip REQUIRED → AVAILABLE
            if inbox.get("empty"):
                out["gapCode"] = "ERA_835_REQUIRED"
                out["collectionsGapCode"] = "ERA_835_REQUIRED"
        except Exception:
            pass
    else:
        out["fixHint"] = FIX_HINT_ERA
    out["honesty"] = "empty_not_zero"
    out["healthy"] = False
    # Never invent SoftDent collections from ERA
    out["collections"] = None
    return out


def format_era_gap_reply(gap: dict[str, Any] | None = None) -> str:
    g = gap or {}
    code = g.get("collectionsGapCode") or g.get("gapCode")
    if g.get("registerInsPlanZero"):
        code = "ERA_835_REQUIRED"
    lines = [
        f"Collections/ERA status: `{code}` — empty ≠ $0; no SoftDent write-back.",
    ]
    if g.get("eraAvailable"):
        lines.append(
            f"ERA aggregate: claims={g.get('eraClaimCount')} total={g.get('eraPaymentTotal')} "
            "(proposal — staff must post in SoftDent)."
        )
    if g.get("fixHint"):
        lines.append(str(g["fixHint"]))
    return "\n".join(lines)
