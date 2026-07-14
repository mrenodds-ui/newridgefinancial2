"""Full InsCo × ADA catalog matrix (HAL-10599 staff export).

Surfaces **every** spine cell — including honest ``insufficient`` — so
"every code analyzed" is visible. Joins $ and %+/- tables from the unified
spine; also lists the 5yr ledger CDT universe.

HAL-10596: full-cell CSV export + stable inbox copy + bijective cents fields.
HAL-10599: expand staff CSV to SoftDent company master (likely_active) × ADA
universe. Companies/ADAs with no ledger settlements stay ``no_settlement``
(null $, null %) — empty != $0; never invent dollars.

No SoftDent write-back. Gold path unchanged (still GOLD_CSV_MISSING until CSV).
"""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from money_cents import money_to_api_bijective
from softdent_insco_ada_spine import (
    CREDIBILITY,
    DEFAULT_YEARS,
    normalize_cdt,
    _table_exists,
    _utc_now,
)
from softdent_treatment_planning import resolve_analytics_db, resolve_exports_dir

DEF_ID = "HAL-10599"
PACKAGE_BUILD_ID = "hal-10599"
PRIOR_DEF_ID = "HAL-10596"
COMPANY_MASTER_DEF = "HAL-10598"

CSV_COLUMNS = (
    "insuranceCompany",
    "adaCode",
    "tier",
    "sampleSize",
    "credibility",
    "paidMedian",
    "paidMedianCents",
    "writeOffMedian",
    "writeOffMedianCents",
    "billedAvg",
    "billedAvgCents",
    "paidPctMedian",
    "paidPctStdev",
    "paidPctMinus",
    "paidPctPlus",
    "writeOffPctMedian",
    "writeOffPctStdev",
    "periodStart",
    "periodEnd",
    "source",
    "masterCompanyId",
    "spineCarrierName",
    "emptyIsNotZero",
    "floatMoneyDeprecated",
)


def _cents(value: Any) -> int | None:
    return money_to_api_bijective(value, format="cents_int")  # type: ignore[arg-type]


def _enrich_money_cents(row: dict[str, Any]) -> dict[str, Any]:
    """Attach bijective cents; keep legacy floats (deprecated for exact math)."""
    out = dict(row)
    out["paidMedianCents"] = _cents(row.get("paidMedian"))
    out["writeOffMedianCents"] = _cents(row.get("writeOffMedian"))
    out["billedAvgCents"] = _cents(row.get("billedAvg"))
    out["floatMoneyDeprecated"] = True
    return out


def catalog_matrix_status(*, db_path: Path | None = None) -> dict[str, Any]:
    target = Path(db_path) if db_path else resolve_analytics_db()
    out: dict[str, Any] = {
        "ok": False,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "dbPath": str(target) if target else None,
    }
    if not target or not target.is_file():
        out["error"] = "analytics_db_missing"
        return out
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        if not _table_exists(conn, "insco_ada_probabilistic_estimates"):
            out["error"] = "spine_tables_missing"
            return out
        total = int(
            conn.execute("SELECT COUNT(*) FROM insco_ada_probabilistic_estimates").fetchone()[0]
            or 0
        )
        exact_usable = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM insco_ada_probabilistic_estimates
                WHERE tier='exact' AND credibility IN ('high','usable')
                """
            ).fetchone()[0]
            or 0
        )
        published = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM insco_ada_probabilistic_estimates
                WHERE credibility != 'insufficient'
                """
            ).fetchone()[0]
            or 0
        )
        insufficient = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM insco_ada_probabilistic_estimates
                WHERE credibility = 'insufficient'
                """
            ).fetchone()[0]
            or 0
        )
        distinct_ada = int(
            conn.execute(
                "SELECT COUNT(DISTINCT ada_code) FROM insco_ada_probabilistic_estimates"
            ).fetchone()[0]
            or 0
        )
        carriers = int(
            conn.execute(
                "SELECT COUNT(DISTINCT insurance_company) FROM insco_ada_probabilistic_estimates"
            ).fetchone()[0]
            or 0
        )
        meta = {}
        if _table_exists(conn, "insco_ada_probabilistic_meta"):
            meta = {
                str(k): str(v)
                for k, v in conn.execute(
                    "SELECT key, value FROM insco_ada_probabilistic_meta"
                ).fetchall()
            }
    finally:
        conn.close()

    universe = list_ledger_cdt_universe(db_path=target)
    uncovered = uncovered_ledger_cdts(db_path=target)
    company_ref: dict[str, Any] = {}
    try:
        from softdent_insurance_company_reference import insurance_company_reference_status

        company_ref = insurance_company_reference_status(db_path=target)
    except Exception as exc:  # noqa: BLE001
        company_ref = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
    master_expanded = estimate_master_expanded_cell_count(
        db_path=target,
        spine_cells=total,
    )
    out.update(
        {
            "ok": True,
            "totalCells": total,
            "spineCells": total,
            "publishedCells": published,
            "insufficientCells": insufficient,
            "exactUsableCells": exact_usable,
            "distinctAdaInSpine": distinct_ada,
            "carriers": carriers,
            "ledgerCdtUniverse": len(universe),
            "uncoveredCount": len(uncovered),
            "masterExpandedCells": master_expanded.get("masterExpandedCells"),
            "masterAdaUniverse": master_expanded.get("adaUniverse"),
            "masterCompanyUniverse": master_expanded.get("companyUniverse"),
            "noSettlementPadCells": master_expanded.get("noSettlementPadCells"),
            "companyReference": {
                "total": company_ref.get("total"),
                "likelyActive": company_ref.get("likelyActive"),
                "discontinued": company_ref.get("discontinued"),
                "spineOverlapLikelyActive": company_ref.get("spineOverlapLikelyActive"),
                "likelyActiveNotInSpine": company_ref.get("likelyActiveNotInSpine"),
                "likelyActiveNotInSpineExact": company_ref.get("likelyActiveNotInSpineExact"),
                "carrierAlias": company_ref.get("carrierAlias"),
                "ok": company_ref.get("ok"),
            },
            "periodStart": meta.get("period_start"),
            "periodEnd": meta.get("period_end"),
            "spineEpisodes": int(meta.get("spine_episodes") or 0),
            "updatedAt": meta.get("updated_at"),
            "honesty": (
                "Spine dollars only from ledger 2/51. Company-master pad cells are "
                "no_settlement (null $, null %) — empty != $0; no gold invent."
            ),
            "emptyIsNotZero": True,
            "floatMoneyDeprecated": True,
            "companyMasterDef": COMPANY_MASTER_DEF,
        }
    )
    return out


def estimate_master_expanded_cell_count(
    *,
    db_path: Path | None = None,
    spine_cells: int = 0,
) -> dict[str, int]:
    """Exact cartesian size for status (keys only — no full row materialization)."""
    target = Path(db_path) if db_path else resolve_analytics_db()
    companies = list_catalog_company_universe(db_path=target)
    adas = list_catalog_ada_universe(db_path=target)
    company_u = len(companies)
    ada_u = len(adas)
    if company_u == 0 or ada_u == 0:
        return {
            "adaUniverse": ada_u,
            "companyUniverse": company_u,
            "noSettlementPadCells": 0,
            "masterExpandedCells": int(spine_cells or 0),
        }
    existing: set[str] = set()
    if target and target.is_file():
        conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
        try:
            if _table_exists(conn, "insco_ada_probabilistic_estimates"):
                for company, ada in conn.execute(
                    "SELECT insurance_company, ada_code FROM insco_ada_probabilistic_estimates"
                ):
                    c = str(company or "").strip().upper()
                    a = str(ada or "").strip().upper()
                    if c and a:
                        existing.add(f"{c}|{a}")
        finally:
            conn.close()
    pad = 0
    for company in companies:
        cu = company.upper()
        for ada in adas:
            if f"{cu}|{ada}" not in existing:
                pad += 1
    return {
        "adaUniverse": ada_u,
        "companyUniverse": company_u,
        "noSettlementPadCells": pad,
        "masterExpandedCells": company_u * ada_u,
    }


def list_ledger_cdt_universe(*, db_path: Path | None = None) -> list[str]:
    target = Path(db_path) if db_path else resolve_analytics_db()
    if not target or not target.is_file():
        return []
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        if not _table_exists(conn, "sd_account_transactions"):
            return []
        rows = conn.execute(
            """
            SELECT DISTINCT procedure FROM sd_account_transactions
            WHERE service_date >= date('now', ?)
            """,
            (f"-{DEFAULT_YEARS * 365} days",),
        ).fetchall()
    finally:
        conn.close()
    out: set[str] = set()
    for (proc,) in rows:
        cdt = normalize_cdt(proc)
        if cdt:
            out.add(cdt)
    return sorted(out)


def list_catalog_matrix_rows(
    *,
    db_path: Path | None = None,
    include_insufficient: bool = True,
    include_inferred: bool = True,
    credibility: str | None = None,
    payer: str | None = None,
    ada: str | None = None,
    limit: int = 5000,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """All spine InsCo×ADA cells with $ + % (insufficient included by default)."""
    target = Path(db_path) if db_path else resolve_analytics_db()
    if not target or not target.is_file():
        return []
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        if not _table_exists(conn, "insco_ada_probabilistic_estimates"):
            return []
        has_pct = _table_exists(conn, "insco_ada_pct_variance")
        where = ["1=1"]
        params: list[Any] = []
        if not include_insufficient:
            where.append("d.credibility != 'insufficient'")
        if not include_inferred:
            where.append("d.tier = 'exact'")
        if credibility:
            where.append("d.credibility = ?")
            params.append(str(credibility).strip())
        if payer:
            where.append("lower(d.insurance_company) LIKE ?")
            params.append(f"%{str(payer).strip().lower()}%")
        if ada:
            cdt = normalize_cdt(ada) or str(ada).strip().upper()
            where.append("d.ada_code = ?")
            params.append(cdt)
        params.extend([max(1, int(limit)), max(0, int(offset))])

        if has_pct:
            sql = f"""
                SELECT
                  d.insurance_company, d.ada_code, d.tier, d.sample_size, d.credibility,
                  d.paid_median, d.paid_avg, d.write_off_median, d.write_off_avg, d.billed_avg,
                  d.period_start, d.period_end, d.updated_at,
                  p.paid_pct_median, p.paid_pct_stdev, p.paid_pct_minus, p.paid_pct_plus,
                  p.write_off_pct_median, p.write_off_pct_stdev,
                  p.write_off_pct_minus, p.write_off_pct_plus
                FROM insco_ada_probabilistic_estimates d
                LEFT JOIN insco_ada_pct_variance p
                  ON p.insurance_company = d.insurance_company
                 AND p.ada_code = d.ada_code
                 AND p.tier = d.tier
                WHERE {" AND ".join(where)}
                ORDER BY
                  CASE d.credibility
                    WHEN 'high' THEN 0 WHEN 'usable' THEN 1
                    WHEN 'usable_inferred' THEN 2 WHEN 'weak_inferred' THEN 3
                    ELSE 4 END,
                  d.sample_size DESC,
                  d.insurance_company, d.ada_code
                LIMIT ? OFFSET ?
            """
        else:
            sql = f"""
                SELECT
                  d.insurance_company, d.ada_code, d.tier, d.sample_size, d.credibility,
                  d.paid_median, d.paid_avg, d.write_off_median, d.write_off_avg, d.billed_avg,
                  d.period_start, d.period_end, d.updated_at,
                  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
                FROM insco_ada_probabilistic_estimates d
                WHERE {" AND ".join(where)}
                ORDER BY d.sample_size DESC
                LIMIT ? OFFSET ?
            """
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    out: list[dict[str, Any]] = []
    for r in rows:
        cred = str(r[4] or "")
        paid = r[5] if r[5] is not None else r[6]
        wo = r[7] if r[7] is not None else r[8]
        # Honesty: insufficient with n<=0 → null dollars, never coerce to 0
        if cred == "insufficient" and int(r[3] or 0) <= 0:
            paid_out = None
            wo_out = None
        else:
            paid_out = paid
            wo_out = wo
        out.append(
            _enrich_money_cents(
                {
                    "insuranceCompany": r[0],
                    "adaCode": r[1],
                    "tier": r[2],
                    "sampleSize": r[3],
                    "credibility": cred,
                    "badge": _badge(cred, str(r[2] or "")),
                    "paidMedian": paid_out,
                    "writeOffMedian": wo_out,
                    "billedAvg": r[9],
                    "periodStart": r[10],
                    "periodEnd": r[11],
                    "updatedAt": r[12],
                    "paidPctMedian": r[13],
                    "paidPctStdev": r[14],
                    "paidPctMinus": r[15],
                    "paidPctPlus": r[16],
                    "writeOffPctMedian": r[17],
                    "writeOffPctStdev": r[18],
                    "writeOffPctMinus": r[19],
                    "writeOffPctPlus": r[20],
                    "source": "ledger_episode_5yr",
                    "emptyIsNotZero": True,
                }
            )
        )
    return out


def _badge(cred: str, tier: str) -> dict[str, str]:
    if cred == "high":
        return {"badge": "high", "label": "High (n≥30 exact)", "tone": "ok"}
    if cred == "usable":
        return {"badge": "usable", "label": "Usable (n≥10 exact)", "tone": "warn"}
    if "inferred" in cred:
        return {"badge": "inferred", "label": f"Inferred ({tier})", "tone": "danger"}
    if cred == "no_settlement":
        return {
            "badge": "no_settlement",
            "label": "No settlement (master only; empty != $0)",
            "tone": "muted",
        }
    return {"badge": "insufficient", "label": "Insufficient (empty != $0)", "tone": "muted"}


def _no_settlement_row(*, company: str, ada: str) -> dict[str, Any]:
    return _enrich_money_cents(
        {
            "insuranceCompany": company,
            "adaCode": ada,
            "tier": "exact",
            "sampleSize": 0,
            "credibility": "no_settlement",
            "badge": _badge("no_settlement", "exact"),
            "paidMedian": None,
            "writeOffMedian": None,
            "billedAvg": None,
            "periodStart": None,
            "periodEnd": None,
            "updatedAt": None,
            "paidPctMedian": None,
            "paidPctStdev": None,
            "paidPctMinus": None,
            "paidPctPlus": None,
            "writeOffPctMedian": None,
            "writeOffPctStdev": None,
            "writeOffPctMinus": None,
            "writeOffPctPlus": None,
            "source": "company_master_no_spine",
            "masterCompanyId": None,
            "spineCarrierName": None,
            "emptyIsNotZero": True,
        }
    )


def list_catalog_ada_universe(*, db_path: Path | None = None) -> list[str]:
    """ADA codes for staff master grid: ledger CDTs ∪ spine estimate ADAs."""
    target = Path(db_path) if db_path else resolve_analytics_db()
    adas = set(list_ledger_cdt_universe(db_path=target))
    if not target or not target.is_file():
        return sorted(adas)
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        if _table_exists(conn, "insco_ada_probabilistic_estimates"):
            for (code,) in conn.execute(
                "SELECT DISTINCT ada_code FROM insco_ada_probabilistic_estimates"
            ):
                cdt = normalize_cdt(code) or str(code or "").strip().upper()
                if cdt:
                    adas.add(cdt)
    finally:
        conn.close()
    return sorted(adas)


def list_catalog_company_universe(*, db_path: Path | None = None) -> list[str]:
    """Companies for staff master grid: likely_active ∪ spine carriers."""
    target = Path(db_path) if db_path else resolve_analytics_db()
    by_upper: dict[str, str] = {}
    try:
        from softdent_insurance_company_reference import list_likely_active_companies

        for name in list_likely_active_companies(db_path=target, limit=2000):
            key = str(name).strip().upper()
            if key and key not in by_upper:
                by_upper[key] = str(name).strip()
    except Exception:
        pass
    if target and target.is_file():
        conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
        try:
            if _table_exists(conn, "insco_ada_probabilistic_estimates"):
                for (name,) in conn.execute(
                    "SELECT DISTINCT insurance_company FROM insco_ada_probabilistic_estimates"
                ):
                    raw = str(name or "").strip()
                    key = raw.upper()
                    if key and key not in by_upper:
                        by_upper[key] = raw
        finally:
            conn.close()
    return sorted(by_upper.values(), key=lambda s: s.upper())


def expand_catalog_rows_with_company_master(
    spine_rows: list[dict[str, Any]],
    *,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Cartesian pad: company master × ADA universe; keep spine $/%% where present.

    HAL-10600: accepted carrier aliases join master names to spine settlements
    (masterCompanyId + spineCarrierName). Missing pairs stay no_settlement with
    null dollars (empty != $0). Does not invent payment lines.
    """
    target = Path(db_path) if db_path else resolve_analytics_db()
    companies = list_catalog_company_universe(db_path=target)
    adas = list_catalog_ada_universe(db_path=target)
    if not companies or not adas:
        return list(spine_rows)

    master_to_spine: dict[str, str] = {}
    master_to_id: dict[str, str] = {}
    try:
        from softdent_carrier_alias import load_accepted_alias_maps

        maps = load_accepted_alias_maps(db_path=target)
        master_to_spine = dict(maps.get("masterToSpine") or {})
        master_to_id = dict(maps.get("masterToId") or {})
    except Exception:
        pass

    # Prefer spine row when present; key by upper(spineCarrier)|ada
    by_key: dict[str, dict[str, Any]] = {}
    for row in spine_rows:
        company = str(row.get("insuranceCompany") or "").strip()
        ada = str(row.get("adaCode") or "").strip().upper()
        if not company or not ada:
            continue
        key = f"{company.upper()}|{ada}"
        enriched = dict(row)
        enriched.setdefault("source", "ledger_episode_5yr")
        enriched.setdefault("spineCarrierName", company)
        enriched.setdefault("masterCompanyId", master_to_id.get(company.upper()))
        by_key[key] = enriched

    out: list[dict[str, Any]] = []
    for company in companies:
        cu = company.upper()
        spine_name = master_to_spine.get(cu, company)
        mid = master_to_id.get(cu)
        for ada in adas:
            key = f"{spine_name.upper()}|{ada}"
            if key in by_key:
                base = dict(by_key[key])
                base["insuranceCompany"] = company
                base["spineCarrierName"] = spine_name
                if mid:
                    base["masterCompanyId"] = mid
                elif not base.get("masterCompanyId"):
                    base["masterCompanyId"] = master_to_id.get(spine_name.upper())
                if spine_name.upper() != cu:
                    base["source"] = "alias_spine_settlement"
                out.append(base)
            else:
                pad = _no_settlement_row(company=company, ada=ada)
                pad["spineCarrierName"] = None
                pad["masterCompanyId"] = mid
                out.append(pad)

    # Keep any spine-only rows that somehow fell outside universe (safety)
    seen = {
        f"{str(r.get('insuranceCompany') or '').strip().upper()}|"
        f"{str(r.get('adaCode') or '').strip().upper()}"
        for r in out
    }
    for row in spine_rows:
        company = str(row.get("insuranceCompany") or "").strip()
        ada = str(row.get("adaCode") or "").strip().upper()
        key = f"{company.upper()}|{ada}"
        if key not in seen:
            enriched = dict(row)
            enriched.setdefault("source", "ledger_episode_5yr")
            enriched.setdefault("spineCarrierName", company)
            enriched.setdefault("masterCompanyId", master_to_id.get(company.upper()))
            out.append(enriched)
    return out


def uncovered_ledger_cdts(*, db_path: Path | None = None) -> list[str]:
    """CDTs seen in 5yr ledger with zero spine cells (analyzed as production but no 2/51)."""
    target = Path(db_path) if db_path else resolve_analytics_db()
    universe = set(list_ledger_cdt_universe(db_path=target))
    if not universe or not target or not target.is_file():
        return []
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        if not _table_exists(conn, "insco_ada_probabilistic_estimates"):
            return sorted(universe)
        present = {
            str(r[0])
            for r in conn.execute(
                "SELECT DISTINCT ada_code FROM insco_ada_probabilistic_estimates"
            ).fetchall()
        }
    finally:
        conn.close()
    return sorted(universe - present)


def _write_catalog_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in CSV_COLUMNS})


def export_catalog_matrix_report(
    *,
    db_path: Path | None = None,
    dest: Path | None = None,
) -> dict[str, Any]:
    target = Path(db_path) if db_path else resolve_analytics_db()
    out_dir = Path(dest) if dest else resolve_exports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    st = catalog_matrix_status(db_path=target)
    spine_rows = list_catalog_matrix_rows(
        db_path=target, include_insufficient=True, include_inferred=True, limit=100000
    )
    rows = expand_catalog_rows_with_company_master(spine_rows, db_path=target)
    universe = list_ledger_cdt_universe(db_path=target)
    ada_universe = list_catalog_ada_universe(db_path=target)
    company_universe = list_catalog_company_universe(db_path=target)
    uncovered = uncovered_ledger_cdts(db_path=target)
    no_settlement = sum(1 for r in rows if r.get("credibility") == "no_settlement")
    payload = {
        "ok": bool(st.get("ok")),
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "checkedAt": _utc_now(),
        "status": st,
        "method": {
            "spine": "softdent_insco_ada_spine (HAL-10585)",
            "companyMaster": "insurance_company_reference (HAL-10598)",
            "includesInsufficient": True,
            "includesNoSettlementPad": True,
            "emptyIsNotZero": True,
            "joins": "insco_ada_probabilistic_estimates LEFT JOIN insco_ada_pct_variance",
            "expand": "likely_active ∪ spine carriers × ledger∪spine ADA",
            "floatMoneyDeprecated": True,
            "centsFields": True,
        },
        "spineCellCount": len(spine_rows),
        "cellCount": len(rows),
        "noSettlementPadCells": no_settlement,
        "companyUniverse": company_universe,
        "companyUniverseCount": len(company_universe),
        "adaUniverse": ada_universe,
        "adaUniverseCount": len(ada_universe),
        "ledgerCdtUniverse": universe,
        "ledgerCdtUniverseCount": len(universe),
        "uncoveredLedgerCdts": uncovered,
        "uncoveredCount": len(uncovered),
        # Full grid lives in CSV (staff source of truth); JSON stays slim.
        "cellsInCsvOnly": True,
        "exactSample": [
            r
            for r in rows
            if r.get("tier") == "exact" and r.get("credibility") in {"high", "usable"}
        ][:40],
        "noSettlementSample": [r for r in rows if r.get("credibility") == "no_settlement"][:25],
        "honesty": st.get("honesty"),
    }
    stamp = date.today().isoformat()
    json_path = out_dir / f"insco_ada_catalog_matrix_{stamp}.json"
    md_path = out_dir / f"insco_ada_catalog_matrix_{stamp}.md"
    csv_path = out_dir / f"insco_ada_catalog_matrix_{stamp}.csv"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_catalog_csv(csv_path, rows)

    lines = [
        f"# InsCo × ADA Full Catalog Matrix ({stamp})",
        "",
        f"**{DEF_ID}** · staff cells **{len(rows)}** (spine **{len(spine_rows)}** + "
        f"no_settlement pad **{no_settlement}**) · companies **{len(company_universe)}** · "
        f"ADA universe **{len(ada_universe)}** · exact usable **{st.get('exactUsableCells')}** · "
        f"ledger CDT universe **{len(universe)}** · uncovered (no 2/51 yet) **{len(uncovered)}**.",
        "",
        f"Staff CSV (all companies we take × ADA codes): `{csv_path}`",
        "",
        "no_settlement / insufficient cells are listed honestly — empty != $0. "
        "Float $ columns deprecated; prefer *Cents. Dollars only where ledger settlements exist.",
        "",
        "## Top exact usable+",
        "",
        "| Carrier | ADA | n | Pay$ | Pay¢ | WO$ | Pay% +/- | Cred |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    exact = [
        r for r in rows if r.get("tier") == "exact" and r.get("credibility") in {"high", "usable"}
    ]
    for row in exact[:40]:
        pct = row.get("paidPctMedian")
        sd = row.get("paidPctStdev")
        pct_s = f"{pct} +/-{sd}" if pct is not None else "—"
        lines.append(
            f"| {row['insuranceCompany']} | {row['adaCode']} | {row['sampleSize']} | "
            f"{row.get('paidMedian')} | {row.get('paidMedianCents')} | "
            f"{row.get('writeOffMedian')} | {pct_s} | {row['credibility']} |"
        )
    lines.extend(
        [
            "",
            "## Uncovered ledger CDTs (seen in TX, no spine settlement cell)",
            "",
            ", ".join(uncovered[:80]) + (" …" if len(uncovered) > 80 else ""),
            "",
            "## Company master coverage",
            "",
            f"likely_active / company universe: **{len(company_universe)}** · "
            f"spine carriers: **{st.get('carriers')}** · "
            f"overlap: **{(st.get('companyReference') or {}).get('spineOverlapLikelyActive')}** · "
            f"pad cells (null $): **{no_settlement}**",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")

    result: dict[str, Any] = {
        "ok": True,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "jsonPath": str(json_path),
        "mdPath": str(md_path),
        "csvPath": str(csv_path),
        "cellCount": len(rows),
        "spineCellCount": len(spine_rows),
        "noSettlementPadCells": no_settlement,
        "companyUniverseCount": len(company_universe),
        "adaUniverseCount": len(ada_universe),
        "exactUsable": st.get("exactUsableCells"),
        "insufficient": st.get("insufficientCells"),
        "ledgerCdtUniverse": len(universe),
        "uncovered": len(uncovered),
        "uncoveredCount": len(uncovered),
        "floatMoneyDeprecated": True,
    }
    try:
        from import_loader import softdent_import_dir

        inbox = softdent_import_dir()
        inbox.mkdir(parents=True, exist_ok=True)
        stable_json = inbox / "softdent_insco_ada_catalog_matrix.json"
        stable_csv = inbox / "softdent_insco_ada_catalog_matrix.csv"
        # Slim inbox JSON — status + samples; full cells live in stamped CSV/JSON
        slim = {
            "ok": True,
            "def": DEF_ID,
            "packageBuildId": PACKAGE_BUILD_ID,
            "status": st,
            "spineCellCount": len(spine_rows),
            "cellCount": len(rows),
            "noSettlementPadCells": no_settlement,
            "companyUniverseCount": len(company_universe),
            "adaUniverseCount": len(ada_universe),
            "exactSample": exact[:25],
            "insufficientSample": [r for r in rows if r.get("credibility") == "insufficient"][:15],
            "noSettlementSample": [r for r in rows if r.get("credibility") == "no_settlement"][:15],
            "uncoveredLedgerCdts": uncovered[:60],
            "uncoveredCount": len(uncovered),
            "fullReport": str(json_path),
            "csvPath": str(csv_path),
            "inboxCsvPath": str(stable_csv),
            "honesty": st.get("honesty"),
            "floatMoneyDeprecated": True,
        }
        stable_json.write_text(json.dumps(slim, indent=2, default=str), encoding="utf-8")
        _write_catalog_csv(stable_csv, rows)
        result["inboxPath"] = str(stable_json)
        result["inboxCsvPath"] = str(stable_csv)
    except Exception as exc:  # noqa: BLE001
        result["inboxError"] = f"{type(exc).__name__}:{exc}"
    return result


def run_insco_ada_catalog_matrix_report(*, db_path: Path | None = None) -> dict[str, Any]:
    target = Path(db_path) if db_path else resolve_analytics_db()
    st = catalog_matrix_status(db_path=target)
    export = export_catalog_matrix_report(db_path=target)
    return {
        "ok": bool(st.get("ok")) and bool(export.get("ok")),
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "status": st,
        "export": export,
    }


def format_catalog_status_reply(st: dict[str, Any] | None = None) -> str:
    s = st if isinstance(st, dict) else catalog_matrix_status()
    if not s.get("ok"):
        return f"InsCo×ADA catalog unavailable ({s.get('error') or 'unknown'})."
    export_hint = (
        "Open staff CSV at SoftDentFinancialExports "
        "(insco_ada_catalog_matrix_*.csv or inbox/softdent_insco_ada_catalog_matrix.csv)."
    )
    return (
        f"InsCo×ADA full catalog ({DEF_ID}): spine cells={s.get('spineCells') or s.get('totalCells')} "
        f"(exact usable={s.get('exactUsableCells')}, published={s.get('publishedCells')}, "
        f"insufficient={s.get('insufficientCells')}); "
        f"staff master grid={s.get('masterExpandedCells')} "
        f"({s.get('masterCompanyUniverse')} companies × {s.get('masterAdaUniverse')} ADAs; "
        f"no_settlement pad={s.get('noSettlementPadCells')}); "
        f"company master likely_active="
        f"{(s.get('companyReference') or {}).get('likelyActive')}; "
        f"ledger CDT universe={s.get('ledgerCdtUniverse')}; "
        f"uncovered={s.get('uncoveredCount')}; "
        f"episodes={s.get('spineEpisodes')}. "
        f"Pad cells are null $ — empty != $0. {export_hint}"
    )


def insco_ada_catalog_widget() -> dict[str, Any]:
    st = catalog_matrix_status()
    exact = list_catalog_matrix_rows(
        include_insufficient=False, include_inferred=False, limit=8
    )
    insuff = list_catalog_matrix_rows(
        include_insufficient=True,
        include_inferred=True,
        credibility="insufficient",
        limit=5,
    )
    uncovered_all = uncovered_ledger_cdts()
    uncovered = uncovered_all[:12]
    total = int(st.get("totalCells") or 0)
    master_cells = int(st.get("masterExpandedCells") or total)
    # Prefer stable inbox CSV when present
    csv_path = None
    inbox_csv = None
    try:
        from import_loader import softdent_import_dir

        cand = softdent_import_dir() / "softdent_insco_ada_catalog_matrix.csv"
        if cand.is_file():
            inbox_csv = str(cand)
            csv_path = str(cand)
    except Exception:
        pass
    if csv_path is None:
        exports = resolve_exports_dir()
        stamped = sorted(exports.glob("insco_ada_catalog_matrix_*.csv"), reverse=True)
        if stamped:
            csv_path = str(stamped[0])

    if total <= 0:
        status = "empty"
        message = "Catalog empty — run scripts/rebuild_insco_ada_catalog.py or Sync."
    else:
        status = "ok"
        message = (
            f"Catalog · staff grid={master_cells} "
            f"({st.get('masterCompanyUniverse')} cos × {st.get('masterAdaUniverse')} ADAs) · "
            f"spine={total} · exact usable={st.get('exactUsableCells')} · "
            f"no_settlement pad={st.get('noSettlementPadCells')} · "
            f"company master likely_active="
            f"{(st.get('companyReference') or {}).get('likelyActive')}"
        )
    return {
        "id": "softdent-insco-ada-catalog",
        "type": "status",
        "label": "InsCo × ADA Full Catalog (HAL-10599)",
        "size": "full",
        "status": status,
        "message": message,
        "hint": (
            "Staff CSV = all SoftDent companies we take × ADA universe. "
            "Dollars only where ledger settlements exist; no_settlement = null $ "
            "(empty != $0). Gold CSV still separate."
        ),
        "totalCells": total,
        "spineCells": st.get("spineCells") or total,
        "masterExpandedCells": master_cells,
        "noSettlementPadCells": st.get("noSettlementPadCells"),
        "masterCompanyUniverse": st.get("masterCompanyUniverse"),
        "masterAdaUniverse": st.get("masterAdaUniverse"),
        "exactUsableCells": st.get("exactUsableCells"),
        "insufficientCells": st.get("insufficientCells"),
        "ledgerCdtUniverse": st.get("ledgerCdtUniverse"),
        "uncoveredCount": st.get("uncoveredCount") or len(uncovered_all),
        "companyReference": st.get("companyReference") or {},
        "csvPath": csv_path,
        "inboxCsvPath": inbox_csv,
        "topExact": exact,
        "insufficientSample": [
            {
                "insuranceCompany": r["insuranceCompany"],
                "adaCode": r["adaCode"],
                "sampleSize": r["sampleSize"],
                "credibility": r["credibility"],
                "paidMedianCents": r.get("paidMedianCents"),
            }
            for r in insuff
        ],
        "uncoveredCdts": uncovered,
        "halChips": [
            {"label": "InsCo ADA catalog status", "query": "InsCo ADA catalog matrix status"},
            {
                "label": "Show insufficient cells",
                "query": "Show InsCo ADA catalog insufficient cells",
            },
            {
                "label": "Pending carrier aliases?",
                "query": "Show pending carrier alias reconciliations for HAL confirmation",
            },
            {
                "label": "Uncovered ledger CDTs?",
                "query": "Which ledger CDTs have no InsCo ADA spine settlement?",
            },
            {
                "label": "Where is the catalog CSV?",
                "query": "Where is the InsCo ADA catalog CSV export?",
            },
        ],
        "carrierAlias": (st.get("companyReference") or {}).get("carrierAlias") or {},
        "honesty": st.get("honesty") or CREDIBILITY.get("honesty"),
        "emptyIsNotZero": True,
        "floatMoneyDeprecated": True,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "priorDef": PRIOR_DEF_ID,
        "companyMasterDef": COMPANY_MASTER_DEF,
        "carrierAliasDef": "HAL-10600",
    }


if __name__ == "__main__":
    print(json.dumps(run_insco_ada_catalog_matrix_report(), indent=2, default=str)[:4000])
