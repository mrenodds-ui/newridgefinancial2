"""InsCo x ADA pay/write-off % with +/- variance from 5yr ledger pairing.

Pairs SoftDent production ADA codes with nearby transaction codes:
- ``2``  = insurance payment
- ``51``/``52`` = insurance write-off

Uses ``sd_patient_insurance`` primary carrier. Episode model: production charge(s)
then following pay/write-off rows on the same account until the next production
cluster or the forward window expires.

Reports (per InsCo x ADA):
- paid_pct mean/median and +/- 1 SD
- write_off_pct mean/median and +/- 1 SD
- sample size + tier (exact vs inferred)

Honesty: empty != $0; proportional multi-ADA splits are labeled inferred;
not SoftDent contractual line truth; no SoftDent write-back.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from datetime import date
from pathlib import Path
from typing import Any

from softdent_insco_ada_spine import (
    CREDIBILITY,
    DEFAULT_YEARS,
    FORWARD_DAYS,
    collect_spine_samples,
    credibility_label,
    normalize_cdt,
    publishable_pct,
    _table_exists,
    _utc_now,
)
from softdent_treatment_planning import resolve_analytics_db, resolve_exports_dir

MIN_PUBLISH_N = int(CREDIBILITY["exact_publish_n"])
HIGH_N = int(CREDIBILITY["exact_high_n"])


def ensure_pct_variance_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS insco_ada_pct_variance (
            insurance_company TEXT NOT NULL,
            ada_code TEXT NOT NULL,
            tier TEXT NOT NULL,
            sample_size INTEGER NOT NULL DEFAULT 0,
            billed_avg REAL,
            paid_avg REAL,
            write_off_avg REAL,
            paid_pct_mean REAL,
            paid_pct_median REAL,
            paid_pct_stdev REAL,
            paid_pct_minus REAL,
            paid_pct_plus REAL,
            write_off_pct_mean REAL,
            write_off_pct_median REAL,
            write_off_pct_stdev REAL,
            write_off_pct_minus REAL,
            write_off_pct_plus REAL,
            credibility TEXT NOT NULL,
            period_start TEXT,
            period_end TEXT,
            forward_days INTEGER,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (insurance_company, ada_code, tier)
        );
        CREATE TABLE IF NOT EXISTS insco_ada_pct_variance_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )




def _mean(vals: list[float]) -> float | None:
    return round(statistics.fmean(vals), 4) if vals else None


def _median(vals: list[float]) -> float | None:
    return round(float(statistics.median(vals)), 4) if vals else None


def _stdev(vals: list[float]) -> float | None:
    if len(vals) < 2:
        return 0.0 if vals else None
    return round(statistics.pstdev(vals), 4)


def _pct(part: float, whole: float) -> float | None:
    if whole <= 0:
        return None
    return round(100.0 * part / whole, 4)


def build_insco_ada_pct_variance(
    conn: sqlite3.Connection,
    *,
    years: int = DEFAULT_YEARS,
    period_end: str | None = None,
    forward_days: int = FORWARD_DAYS,
) -> dict[str, Any]:
    """Rebuild InsCo x ADA pay%/write-off% with +/- stdev from shared spine."""
    ensure_pct_variance_schema(conn)
    samples = collect_spine_samples(
        conn, years=years, period_end=period_end, forward_days=forward_days
    )
    start = samples["periodStart"]
    end = samples["periodEnd"]
    fwd = int(samples["forwardDays"])

    out: dict[str, Any] = {
        "ok": False,
        "periodStart": start,
        "periodEnd": end,
        "years": years,
        "forwardDays": fwd,
        "warnings": list(samples.get("warnings") or []),
        "episodeTiers": samples.get("episodeTiers") or {},
        "publishedCells": 0,
        "totalCells": 0,
        "source": samples.get("source"),
        "spineEpisodes": samples.get("episodeCount") or 0,
    }
    if not samples.get("ok"):
        return out

    billed_s = samples["billed"]
    paid_s = samples["paid"]
    wo_s = samples["writeOff"]
    pay_pct_s = samples["paidPct"]
    wo_pct_s = samples["writeOffPct"]
    tier_counts = dict(samples.get("episodeTiers") or {})
    episodes = int(samples.get("episodeCount") or 0)

    updated_at = _utc_now()
    conn.execute("DELETE FROM insco_ada_pct_variance")
    keys = set(billed_s) | set(paid_s) | set(wo_s)
    published = 0
    total_cells = 0
    for carrier, ada, tier in sorted(keys):
        bills = billed_s.get((carrier, ada, tier), [])
        pays = paid_s.get((carrier, ada, tier), [])
        wos = wo_s.get((carrier, ada, tier), [])
        pps = pay_pct_s.get((carrier, ada, tier), [])
        wps = wo_pct_s.get((carrier, ada, tier), [])
        n = max(len(bills), len(pays), len(wos), len(pps), len(wps))
        if n <= 0:
            continue
        total_cells += 1
        pay_mean = _mean(pps)
        pay_sd = _stdev(pps) or 0.0
        wo_mean = _mean(wps)
        wo_sd = _stdev(wps) or 0.0
        pay_med = _median(pps)
        wo_med = _median(wps)
        cred = credibility_label(tier, n)
        if tier == "low":
            cred = "insufficient"
        if not publishable_pct(pay_med, wo_med):
            cred = "insufficient"
        if cred in {"high", "usable", "usable_inferred", "weak_inferred"}:
            published += 1
        conn.execute(
            """
            INSERT INTO insco_ada_pct_variance (
                insurance_company, ada_code, tier, sample_size,
                billed_avg, paid_avg, write_off_avg,
                paid_pct_mean, paid_pct_median, paid_pct_stdev, paid_pct_minus, paid_pct_plus,
                write_off_pct_mean, write_off_pct_median, write_off_pct_stdev,
                write_off_pct_minus, write_off_pct_plus,
                credibility, period_start, period_end, forward_days, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                carrier,
                ada,
                tier,
                n,
                _mean(bills),
                _mean(pays),
                _mean(wos),
                pay_mean,
                pay_med,
                pay_sd,
                None if pay_mean is None else round(pay_mean - pay_sd, 4),
                None if pay_mean is None else round(pay_mean + pay_sd, 4),
                wo_mean,
                wo_med,
                wo_sd,
                None if wo_mean is None else round(wo_mean - wo_sd, 4),
                None if wo_mean is None else round(wo_mean + wo_sd, 4),
                cred,
                start,
                end,
                fwd,
                updated_at,
            ),
        )

    meta = {
        "updated_at": updated_at,
        "period_start": start,
        "period_end": end,
        "years": str(years),
        "forward_days": str(fwd),
        "episodes": str(episodes),
        "episode_tiers": json.dumps(tier_counts),
        "spine_source": str(samples.get("source") or ""),
        "published_cells": str(published),
        "total_cells": str(total_cells),
        "min_publish_n": str(MIN_PUBLISH_N),
        "high_n": str(HIGH_N),
        "honesty": (
            "Unified spine: Code 2=Ins pay, 51=write-off after production CDTs. "
            "Multi-ADA episodes allocate 2/51 by billed share (inferred). "
            "+/- is 1 population stdev of percentages. empty != $0."
        ),
    }
    for key, value in meta.items():
        conn.execute(
            "INSERT OR REPLACE INTO insco_ada_pct_variance_meta (key, value) VALUES (?, ?)",
            (key, value),
        )
    conn.commit()
    out.update(
        {
            "ok": True,
            "episodeTiers": tier_counts,
            "episodes": episodes,
            "publishedCells": published,
            "totalCells": total_cells,
        }
    )
    return out



def list_pct_variance_rows(
    *,
    db_path: Path | None = None,
    include_inferred: bool = True,
    min_n: int = MIN_PUBLISH_N,
    limit: int = 200,
) -> list[dict[str, Any]]:
    target = Path(db_path) if db_path else resolve_analytics_db()
    if not target or not target.is_file():
        return []
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        ensure_pct_variance_schema(conn)
        if include_inferred:
            where = "sample_size >= ? AND credibility != 'insufficient'"
        else:
            where = "sample_size >= ? AND tier = 'exact' AND credibility IN ('high','usable')"
        rows = conn.execute(
            f"""
            SELECT insurance_company, ada_code, tier, sample_size,
                   billed_avg, paid_avg, write_off_avg,
                   paid_pct_mean, paid_pct_median, paid_pct_stdev, paid_pct_minus, paid_pct_plus,
                   write_off_pct_mean, write_off_pct_median, write_off_pct_stdev,
                   write_off_pct_minus, write_off_pct_plus, credibility
            FROM insco_ada_pct_variance
            WHERE {where}
            ORDER BY
              CASE credibility WHEN 'high' THEN 0 WHEN 'usable' THEN 1
                   WHEN 'usable_inferred' THEN 2 ELSE 3 END,
              sample_size DESC
            LIMIT ?
            """,
            (max(1, int(min_n)), max(1, int(limit))),
        ).fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "insuranceCompany": r[0],
                    "adaCode": r[1],
                    "tier": r[2],
                    "sampleSize": r[3],
                    "billedAvg": r[4],
                    "paidAvg": r[5],
                    "writeOffAvg": r[6],
                    "paidPctMean": r[7],
                    "paidPctMedian": r[8],
                    "paidPctStdev": r[9],
                    "paidPctMinus": r[10],
                    "paidPctPlus": r[11],
                    "writeOffPctMean": r[12],
                    "writeOffPctMedian": r[13],
                    "writeOffPctStdev": r[14],
                    "writeOffPctMinus": r[15],
                    "writeOffPctPlus": r[16],
                    "credibility": r[17],
                }
            )
        return out
    finally:
        conn.close()


def lookup_pct_variance(
    *,
    payer: str,
    ada_code: str,
    include_inferred: bool = False,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    target = Path(db_path) if db_path else resolve_analytics_db()
    if not target or not target.is_file():
        return None
    carrier = str(payer or "").strip().upper()
    ada = normalize_cdt(ada_code) or str(ada_code or "").strip().upper()
    if not carrier or not ada:
        return None
    rows = list_pct_variance_rows(
        db_path=target,
        include_inferred=include_inferred,
        min_n=1,
        limit=500,
    )
    hits = [
        r
        for r in rows
        if str(r.get("insuranceCompany") or "").upper() == carrier
        and str(r.get("adaCode") or "").upper() == ada.upper()
    ]
    if not hits and include_inferred:
        hits = [
            r
            for r in list_pct_variance_rows(
                db_path=target, include_inferred=True, min_n=1, limit=500
            )
            if str(r.get("insuranceCompany") or "").upper() == carrier
            and str(r.get("adaCode") or "").upper() == ada.upper()
        ]
    if not hits:
        return None
    # Prefer exact then high credibility
    hits.sort(
        key=lambda r: (
            0 if r.get("tier") == "exact" else 1,
            0 if r.get("credibility") == "high" else 1,
            -(int(r.get("sampleSize") or 0)),
        )
    )
    return hits[0]


def pct_variance_status(*, db_path: Path | None = None) -> dict[str, Any]:
    target = Path(db_path) if db_path else resolve_analytics_db()
    out: dict[str, Any] = {"ok": False, "dbPath": str(target) if target else None}
    if not target or not target.is_file():
        out["error"] = "analytics_db_missing"
        return out
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        ensure_pct_variance_schema(conn)
        meta = {
            str(k): str(v)
            for k, v in conn.execute("SELECT key, value FROM insco_ada_pct_variance_meta").fetchall()
        }
        exact_n = conn.execute(
            """
            SELECT COUNT(*) FROM insco_ada_pct_variance
            WHERE tier='exact' AND credibility IN ('high','usable') AND sample_size >= ?
            """,
            (MIN_PUBLISH_N,),
        ).fetchone()[0]
        all_n = conn.execute(
            """
            SELECT COUNT(*) FROM insco_ada_pct_variance
            WHERE credibility != 'insufficient' AND sample_size >= ?
            """,
            (MIN_PUBLISH_N,),
        ).fetchone()[0]
    finally:
        conn.close()
    out.update(
        {
            "ok": True,
            "def": "HAL-10584",
            "periodStart": meta.get("period_start"),
            "periodEnd": meta.get("period_end"),
            "years": meta.get("years"),
            "episodes": int(meta.get("episodes") or 0),
            "exactPublished": int(exact_n or 0),
            "allPublishedIncludingInferred": int(all_n or 0),
            "updatedAt": meta.get("updated_at"),
            "honesty": meta.get("honesty"),
        }
    )
    return out


def format_pct_variance_status_reply(st: dict[str, Any]) -> str:
    if not st.get("ok"):
        return f"InsCo×ADA % variance unavailable ({st.get('error') or 'unknown'})."
    return (
        f"InsCo×ADA pay/WO % (HAL-10584): {st.get('years')}yr "
        f"{st.get('periodStart')}..{st.get('periodEnd')}; "
        f"exact cells {st.get('exactPublished')}; "
        f"incl. inferred {st.get('allPublishedIncludingInferred')}; "
        f"episodes {st.get('episodes')}. "
        "Code 2=pay, 51=WO; +/- is 1 SD. empty≠$0."
    )


def format_pct_variance_reply(
    row: dict[str, Any] | None,
    *,
    payer: str = "",
    ada: str = "",
) -> str:
    if not row:
        return (
            f"No publishable pay/WO % for {payer or '?'} × {ada or '?'} "
            "(need n≥10 exact with sane ratios; empty≠$0)."
        )
    return (
        f"{row['insuranceCompany']} × {row['adaCode']} ({row['tier']}, {row['credibility']}, "
        f"n={row['sampleSize']}): "
        f"pay {row.get('paidPctMedian')}% +/-{row.get('paidPctStdev')} "
        f"(mean {row.get('paidPctMean')}% [{row.get('paidPctMinus')}..{row.get('paidPctPlus')}]); "
        f"write-off {row.get('writeOffPctMedian')}% +/-{row.get('writeOffPctStdev')} "
        f"(mean {row.get('writeOffPctMean')}% [{row.get('writeOffPctMinus')}..{row.get('writeOffPctPlus')}]). "
        "From SoftDent code 2/51 next to production ADAs over 5yr history."
    )


def export_pct_variance_report(
    *,
    db_path: Path | None = None,
    dest: Path | None = None,
) -> dict[str, Any]:
    target = Path(db_path) if db_path else resolve_analytics_db()
    out_dir = Path(dest) if dest else resolve_exports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {"ok": False}
    if not target or not target.is_file():
        result["error"] = "analytics_db_missing"
        return result

    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        ensure_pct_variance_schema(conn)
        meta = {
            str(k): str(v)
            for k, v in conn.execute("SELECT key, value FROM insco_ada_pct_variance_meta").fetchall()
        }
    finally:
        conn.close()

    exact_rows = list_pct_variance_rows(db_path=target, include_inferred=False, limit=500)
    all_rows = list_pct_variance_rows(db_path=target, include_inferred=True, limit=500)
    payload = {
        "ok": True,
        "def": "HAL-10584",
        "checkedAt": _utc_now(),
        "meta": meta,
        "method": {
            "historyYears": DEFAULT_YEARS,
            "softDentCodes": {"payment": "2", "writeOff": "51/52"},
            "pairing": (
                "Production ADA cluster, then forward codes 2 and 51 within "
                f"{FORWARD_DAYS} days (or until next production)."
            ),
            "percentages": "paid_pct = allocated_pay / billed * 100; write_off_pct = allocated_wo / billed * 100",
            "variance": "+/- 1 population stdev of per-episode percentages",
            "exact": "single ADA in production cluster",
            "inferred": "multi-ADA cluster: 2/51 allocated by billed share",
            "minN": MIN_PUBLISH_N,
        },
        "exactPublished": exact_rows,
        "exactCount": len(exact_rows),
        "allPublishedIncludingInferred": all_rows,
        "allCount": len(all_rows),
        "honesty": meta.get("honesty"),
    }
    stamp = date.today().isoformat()
    json_path = out_dir / f"insco_ada_pct_variance_report_{stamp}.json"
    md_path = out_dir / f"insco_ada_pct_variance_report_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        f"# InsCo x ADA Pay/Write-off % +/- Variance ({stamp})",
        "",
        f"History: **{meta.get('years', DEFAULT_YEARS)} years** "
        f"({meta.get('period_start')} .. {meta.get('period_end')}).",
        f"Episodes: {meta.get('episodes')} · exact published: **{len(exact_rows)}** · "
        f"incl. inferred: **{len(all_rows)}**.",
        "",
        "## Method",
        "",
        "- SoftDent code **2** = Ins payment; code **51** = write-off",
        "- Pair each production ADA with following 2/51 on same account (forward window)",
        "- Report pay% and write-off% of billed, with **+/- 1 SD**",
        "- Exact = one ADA in visit cluster; inferred = multi-ADA proportional split",
        "- empty != $0; not contractual guarantee",
        "",
        "## Top exact cells",
        "",
        "| Carrier | ADA | n | Pay% med | Pay% +/- | WO% med | WO% +/- | Cred |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in exact_rows[:50]:
        pay_pm = row.get("paidPctStdev")
        wo_pm = row.get("writeOffPctStdev")
        lines.append(
            f"| {row['insuranceCompany']} | {row['adaCode']} | {row['sampleSize']} | "
            f"{row.get('paidPctMedian')} | +/-{pay_pm} | "
            f"{row.get('writeOffPctMedian')} | +/-{wo_pm} | {row['credibility']} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    try:
        from import_loader import softdent_import_dir

        inbox = softdent_import_dir()
        inbox.mkdir(parents=True, exist_ok=True)
        stable = inbox / "softdent_insco_ada_pct_variance.json"
        stable.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        result["inboxPath"] = str(stable)
    except Exception as exc:  # noqa: BLE001
        result["inboxError"] = f"{type(exc).__name__}:{exc}"

    result.update(
        {
            "ok": True,
            "jsonPath": str(json_path),
            "mdPath": str(md_path),
            "exactCount": len(exact_rows),
            "allCount": len(all_rows),
        }
    )
    return result


def run_insco_ada_pct_variance_report(
    *,
    db_path: Path | None = None,
    years: int = DEFAULT_YEARS,
) -> dict[str, Any]:
    target = Path(db_path) if db_path else resolve_analytics_db()
    out: dict[str, Any] = {"ok": False, "dbPath": str(target) if target else None}
    if not target or not target.is_file():
        out["error"] = "analytics_db_missing"
        return out
    conn = sqlite3.connect(str(target))
    try:
        build = build_insco_ada_pct_variance(conn, years=years)
        out["build"] = build
    finally:
        conn.close()
    export = export_pct_variance_report(db_path=target)
    out["export"] = export
    out["ok"] = bool(build.get("ok")) and bool(export.get("ok"))
    return out


if __name__ == "__main__":
    print(json.dumps(run_insco_ada_pct_variance_report(), indent=2, default=str))
