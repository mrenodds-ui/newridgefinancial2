"""Shared InsCo × ADA analysis spine (HAL-10585).

One episode-pairing pipeline for every production CDT:
- SoftDent code ``2`` = insurance payment
- SoftDent codes ``51``/``52`` = insurance write-off
- History window: 5 years (same for $ and %)
- Exact = single ADA in production cluster; inferred = 2–3; low = 4+
- Multi-ADA allocates 2/51 by billed share (labeled inferred/low)
- Non-CDT SoftDent internals excluded from the ADA matrix (empty != invent)

Consumed by probabilistic $, pct variance, and treatment-planning fallback.
No SoftDent write-back.
"""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterator

from softdent_treatment_planning import normalize_ada_code

# SoftDent transactional codes
INS_PAYMENT_CODES = frozenset({"2"})
INS_WRITEOFF_CODES = frozenset({"51", "52"})
NON_PRODUCTION_CODES = frozenset(
    {
        "2",
        "3",
        "11",
        "12",
        "17",
        "48",
        "51",
        "52",
        "60",
        "61",
        "99",
        "8888",
    }
)

GENERIC_PAYERS = frozenset({"", "insurance", "ins", "payer", "carrier", "unknown", "n/a", "-"})

DEFAULT_YEARS = 5
FORWARD_DAYS = 60
CLUSTER_GAP_DAYS = 1
OVERPAY_RATIO = 1.25

CREDIBILITY = {
    "exact_publish_n": 10,
    "exact_high_n": 30,
    "inferred_publish_n": 30,
    "inferred_high_n": 75,
    "low_never_publish": True,
    "forward_days": FORWARD_DAYS,
    "recommended_history_years": DEFAULT_YEARS,
    # legacy key kept for older callers expecting months
    "recommended_history_months": DEFAULT_YEARS * 12,
    "lookback_days": FORWARD_DAYS,  # spine is forward-pairing; alias for UI
    "target_exact_cells_n10": 50,
    "target_exact_cells_n30": 20,
    "honesty": (
        "Unified spine: production CDT → SoftDent 2/51 within forward window. "
        "Exact = single ADA; inferred = multi-ADA billed-share split. "
        "Gold path remains SoftDent payment-line / ERA when available. empty != $0."
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# Back-compat alias used by older modules
_utc_now = utc_now


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return bool(row)


_table_exists = table_exists


def normalize_cdt(raw: Any) -> str:
    """Canonical D#### for matrix rows; empty string = exclude (not a CDT)."""
    text = str(raw or "").strip().upper().replace(" ", "")
    if not text or text in NON_PRODUCTION_CODES:
        return ""
    # SoftDent decimal internals (11.93, 50.9) — only keep if base maps to CDT
    if "." in text:
        base = text.split(".", 1)[0]
        if re.fullmatch(r"D\d{4}", base):
            return base
        if base.isdigit() and len(base) == 4:
            return f"D{base}"
        if base.isdigit() and len(base) == 3:
            return f"D{int(base):04d}"
        return ""
    # SoftDent 3-digit CDTs (220 → D0220)
    if text.isdigit() and len(text) == 3:
        return f"D{int(text):04d}"
    out = normalize_ada_code(text)
    if out and re.fullmatch(r"D\d{4}", out):
        return out
    return ""


def load_primary_insurance_map(conn: sqlite3.Connection) -> dict[str, str]:
    out: dict[str, str] = {}
    if not table_exists(conn, "sd_patient_insurance"):
        return out
    rows = conn.execute(
        """
        SELECT patient_id, insurance_name, priority
        FROM sd_patient_insurance
        WHERE insurance_name IS NOT NULL AND TRIM(insurance_name) != ''
        ORDER BY priority ASC
        """
    ).fetchall()
    for patient_id, name, _priority in rows:
        pid = str(patient_id or "").strip()
        carrier = str(name or "").strip()
        if not pid or not carrier:
            continue
        if carrier.lower() in GENERIC_PAYERS:
            continue
        if pid not in out:
            out[pid] = carrier
    return out


_load_primary_insurance_map = load_primary_insurance_map


def carrier_for_account(account_num: str, ins_map: dict[str, str]) -> str | None:
    acct = str(account_num or "").strip()
    if not acct:
        return None
    if acct in ins_map:
        return ins_map[acct]
    if len(acct) > 1:
        family = acct[:-1] + "0"
        if family in ins_map:
            return ins_map[family]
        if acct[:-1] in ins_map:
            return ins_map[acct[:-1]]
    return None


_carrier_for_account = carrier_for_account


def event_tier(ada_count: int) -> str:
    if ada_count <= 0:
        return "none"
    if ada_count == 1:
        return "exact"
    if ada_count <= 3:
        return "inferred"
    return "low"


def credibility_label(tier: str, n: int) -> str:
    if tier == "exact":
        if n >= int(CREDIBILITY["exact_high_n"]):
            return "high"
        if n >= int(CREDIBILITY["exact_publish_n"]):
            return "usable"
        return "insufficient"
    if tier == "inferred":
        if n >= int(CREDIBILITY["inferred_high_n"]):
            return "usable_inferred"
        if n >= int(CREDIBILITY["inferred_publish_n"]):
            return "weak_inferred"
        return "insufficient"
    # low never published as credible
    return "insufficient"


def period_bounds(
    *,
    years: int = DEFAULT_YEARS,
    period_end: str | None = None,
) -> tuple[str, str]:
    end = period_end or date.today().isoformat()
    end_d = date.fromisoformat(end[:10])
    start_d = end_d - timedelta(days=365 * max(1, int(years)))
    return start_d.isoformat(), end


def _parse_day(raw: str) -> date | None:
    try:
        return date.fromisoformat(str(raw or "")[:10])
    except ValueError:
        return None


@dataclass(frozen=True)
class SpineAllocation:
    episode_id: str
    carrier: str
    ada: str
    tier: str
    billed: float
    paid: float
    write_off: float


def iter_spine_allocations(
    conn: sqlite3.Connection,
    *,
    years: int = DEFAULT_YEARS,
    period_end: str | None = None,
    forward_days: int = FORWARD_DAYS,
) -> Iterator[SpineAllocation]:
    """Yield per-ADA allocations from unified production→2/51 episodes."""
    start, end = period_bounds(years=years, period_end=period_end)
    fwd = max(1, int(forward_days))
    if not table_exists(conn, "sd_account_transactions"):
        return

    ins_map = load_primary_insurance_map(conn)
    if not ins_map:
        return

    rows = conn.execute(
        """
        SELECT account_num, service_date, procedure, row_number,
               COALESCE(prod, 0) + COALESCE(charges, 0),
               COALESCE(prod_adj, 0) + COALESCE(pay_adj, 0),
               COALESCE(cash, 0) + COALESCE("check", 0) + COALESCE(credit, 0)
        FROM sd_account_transactions
        WHERE service_date >= ? AND service_date <= ?
        ORDER BY account_num, service_date, row_number
        """,
        (start, end),
    ).fetchall()

    by_acct: dict[str, list[tuple[str, str, int, float, float, float]]] = defaultdict(list)
    for account_num, service_date, procedure, row_number, billed, adj, paid in rows:
        by_acct[str(account_num or "").strip()].append(
            (
                str(service_date or "")[:10],
                str(procedure or "").strip(),
                int(row_number or 0),
                float(billed or 0),
                float(adj or 0),
                float(paid or 0),
            )
        )

    ep_seq = 0
    for acct, txs in by_acct.items():
        carrier = carrier_for_account(acct, ins_map)
        if not carrier or carrier.lower() in GENERIC_PAYERS:
            continue

        i = 0
        n = len(txs)
        while i < n:
            d, proc, _rn, billed, _adj, _paid = txs[i]
            day = _parse_day(d)
            if day is None or proc in NON_PRODUCTION_CODES or billed <= 0:
                i += 1
                continue
            if not normalize_cdt(proc):
                # non-CDT production-looking row — skip as matrix production
                i += 1
                continue

            prods: list[tuple[str, float]] = []
            j = i
            cluster_end = day
            while j < n:
                d2, p2, _r2, b2, _a2, _pay2 = txs[j]
                day2 = _parse_day(d2)
                if day2 is None:
                    break
                if p2 in NON_PRODUCTION_CODES:
                    if p2 in INS_PAYMENT_CODES or p2 in INS_WRITEOFF_CODES:
                        break
                    j += 1
                    continue
                if b2 <= 0:
                    j += 1
                    continue
                if (day2 - cluster_end).days > CLUSTER_GAP_DAYS and prods:
                    break
                if (day2 - day).days > CLUSTER_GAP_DAYS and not prods:
                    break
                ada = normalize_cdt(p2)
                if not ada:
                    j += 1
                    continue
                prods.append((ada, b2))
                cluster_end = day2
                j += 1

            if not prods:
                i += 1
                continue

            paid_amt = 0.0
            wo_amt = 0.0
            k = j
            window_end = cluster_end + timedelta(days=fwd)
            while k < n:
                d3, p3, _r3, b3, a3, pay3 = txs[k]
                day3 = _parse_day(d3)
                if day3 is None or day3 > window_end:
                    break
                if p3 not in NON_PRODUCTION_CODES and b3 > 0 and normalize_cdt(p3):
                    break
                if p3 in INS_PAYMENT_CODES and pay3:
                    paid_amt += float(pay3)
                if p3 in INS_WRITEOFF_CODES and a3:
                    wo_amt += abs(float(a3))
                k += 1

            if paid_amt <= 0 and wo_amt <= 0:
                i = j
                continue

            by_ada: dict[str, float] = defaultdict(float)
            for ada, b in prods:
                by_ada[ada] += b
            ada_list = list(by_ada.items())
            total_b = sum(b for _, b in ada_list)
            if total_b <= 0:
                i = j
                continue
            if (paid_amt + wo_amt) > total_b * OVERPAY_RATIO:
                i = max(j, k if k > j else j)
                continue

            tier = event_tier(len(ada_list))
            if tier == "none":
                i = max(j, k if k > j else j)
                continue

            ep_seq += 1
            episode_id = f"{acct}:{cluster_end.isoformat()}:{ep_seq}"
            for ada, b in ada_list:
                share = b / total_b
                yield SpineAllocation(
                    episode_id=episode_id,
                    carrier=carrier,
                    ada=ada,
                    tier=tier,
                    billed=b,
                    paid=paid_amt * share,
                    write_off=wo_amt * share,
                )

            i = max(j, k if k > j else j)


def collect_spine_samples(
    conn: sqlite3.Connection,
    *,
    years: int = DEFAULT_YEARS,
    period_end: str | None = None,
    forward_days: int = FORWARD_DAYS,
) -> dict[str, Any]:
    """Aggregate spine allocations into sample lists for $ and % builders."""
    start, end = period_bounds(years=years, period_end=period_end)
    billed_s: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    paid_s: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    wo_s: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    pay_pct_s: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    wo_pct_s: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    warnings: list[str] = []

    if not table_exists(conn, "sd_account_transactions"):
        warnings.append("sd_account_transactions missing")
        return _empty_samples(start, end, years, forward_days, warnings)

    ins_map = load_primary_insurance_map(conn)
    if not ins_map:
        warnings.append("sd_patient_insurance empty — run Sensei insurance populate first")
        return _empty_samples(start, end, years, forward_days, warnings)

    ep_tier: dict[str, str] = {}
    for alloc in iter_spine_allocations(
        conn, years=years, period_end=period_end, forward_days=forward_days
    ):
        key = (alloc.carrier, alloc.ada, alloc.tier)
        ep_tier[alloc.episode_id] = alloc.tier
        billed_s[key].append(alloc.billed)
        if alloc.paid:
            paid_s[key].append(alloc.paid)
            if alloc.billed > 0:
                pay_pct_s[key].append(round(100.0 * alloc.paid / alloc.billed, 4))
        if alloc.write_off:
            wo_s[key].append(alloc.write_off)
            if alloc.billed > 0:
                wo_pct_s[key].append(round(100.0 * alloc.write_off / alloc.billed, 4))

    episode_tier_counts: dict[str, int] = defaultdict(int)
    for t in ep_tier.values():
        episode_tier_counts[t] += 1

    return {
        "ok": True,
        "periodStart": start,
        "periodEnd": end,
        "years": years,
        "forwardDays": max(1, int(forward_days)),
        "billed": billed_s,
        "paid": paid_s,
        "writeOff": wo_s,
        "paidPct": pay_pct_s,
        "writeOffPct": wo_pct_s,
        "episodeCount": len(ep_tier),
        "episodeTiers": dict(episode_tier_counts),
        "allocationCount": sum(len(v) for v in billed_s.values()),
        "insuranceMapSize": len(ins_map),
        "warnings": warnings,
        "credibilityRules": dict(CREDIBILITY),
        "source": "ledger_episode_5yr",
    }


def _empty_samples(
    start: str, end: str, years: int, forward_days: int, warnings: list[str]
) -> dict[str, Any]:
    return {
        "ok": False,
        "periodStart": start,
        "periodEnd": end,
        "years": years,
        "forwardDays": max(1, int(forward_days)),
        "billed": {},
        "paid": {},
        "writeOff": {},
        "paidPct": {},
        "writeOffPct": {},
        "episodeCount": 0,
        "episodeTiers": {},
        "allocationCount": 0,
        "insuranceMapSize": 0,
        "warnings": warnings,
        "credibilityRules": dict(CREDIBILITY),
        "source": "ledger_episode_5yr",
    }


def publishable_pct(paid_pct: float | None, wo_pct: float | None) -> bool:
    for val in (paid_pct, wo_pct):
        if val is None:
            continue
        if val < -5 or val > 120:
            return False
    return True
