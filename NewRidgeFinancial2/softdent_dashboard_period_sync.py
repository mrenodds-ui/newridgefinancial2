"""Build SoftDent dashboard rows from analytics DB for current + prior month."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from import_cache_ttl import relevant_period_labels
from import_loader import softdent_import_dir
from import_sync import BRIDGE_AGGREGATE_JSON, _build_dashboard_from_bridge, _read_json
from quickbooks_monthly_sync import resolve_analytics_db

PRACTICE_NAME = "New Ridge Family Dental"


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return {str(row[1]) for row in cur.fetchall()}


def _aggregate_daysheet(db_path: Path, periods: list[str]) -> dict[str, dict[str, float]]:
    if not db_path.is_file() or not periods:
        return {}
    conn = sqlite3.connect(db_path)
    columns = _table_columns(conn, "daysheet_totals")
    if "year_month" not in columns:
        conn.close()
        return {}
    insurance_sql = "SUM(COALESCE(insurance_payment_total, 0))" if "insurance_payment_total" in columns else "0"
    placeholders = ",".join("?" for _ in periods)
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT year_month,
               SUM(COALESCE(gross_production, 0)),
               SUM(COALESCE(net_production, 0)),
               SUM(COALESCE(collections, 0)),
               {insurance_sql}
        FROM daysheet_totals
        WHERE year_month IN ({placeholders})
        GROUP BY year_month
        """,
        periods,
    )
    out: dict[str, dict[str, float]] = {}
    for year_month, gross, net, collections, insurance in cur.fetchall():
        production = float(gross or net or 0)
        coll = float(collections or 0)
        ins = float(insurance or 0)
        out[str(year_month)] = {
            "production": production,
            "collections": coll,
            "insurance": ins,
            "patient": max(0.0, coll - ins),
        }
    conn.close()
    return out


def _aggregate_production_by_provider(db_path: Path, periods: list[str]) -> dict[str, float]:
    if not db_path.is_file() or not periods:
        return {}
    conn = sqlite3.connect(db_path)
    columns = _table_columns(conn, "production_by_provider")
    if "year_month" not in columns:
        conn.close()
        return {}
    placeholders = ",".join("?" for _ in periods)
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT year_month, SUM(COALESCE(gross_production, 0))
        FROM production_by_provider
        WHERE year_month IN ({placeholders})
        GROUP BY year_month
        """,
        periods,
    )
    out = {str(row[0]): float(row[1] or 0) for row in cur.fetchall()}
    conn.close()
    return out


def _bridge_rows_by_period() -> dict[str, dict[str, float]]:
    bridge_path = BRIDGE_AGGREGATE_JSON
    if not bridge_path.is_file():
        cache = softdent_import_dir() / "softdent_bridge_latest.json"
        bridge_path = cache if cache.is_file() else None
    if not bridge_path or not bridge_path.is_file():
        return {}
    rows = _build_dashboard_from_bridge(bridge_path) or []
    out: dict[str, dict[str, float]] = {}
    for row in rows:
        period = str(row.get("period") or "").strip()
        if not period:
            continue
        production = float(row.get("production") or 0)
        collections = float(row.get("collections") or 0)
        insurance = float(row.get("insurance") or 0)
        patient = float(row.get("patient") or max(0.0, collections - insurance))
        out[period] = {
            "production": production,
            "collections": collections,
            "insurance": insurance,
            "patient": patient,
        }
    return out


def _merge_metric(existing: float, candidate: float) -> float:
    if candidate <= 0:
        return existing
    if existing <= 0:
        return candidate
    return max(existing, candidate)


def _build_period_row(period: str, sources: list[dict[str, float]]) -> dict[str, Any]:
    production = 0.0
    collections = 0.0
    insurance = 0.0
    patient = 0.0
    for source in sources:
        production = _merge_metric(production, float(source.get("production") or 0))
        collections = _merge_metric(collections, float(source.get("collections") or 0))
        insurance = _merge_metric(insurance, float(source.get("insurance") or 0))
        patient = _merge_metric(patient, float(source.get("patient") or 0))
    if patient <= 0 and collections > 0:
        patient = max(0.0, collections - insurance)
    return {
        "provider": PRACTICE_NAME,
        "period": period,
        "production": production,
        "collections": collections,
        "insurance": insurance,
        "patient": patient,
    }


def _month_rows(db_path: Path | None, periods: list[str]) -> list[dict[str, Any]]:
    daysheet = _aggregate_daysheet(db_path, periods) if db_path else {}
    provider_prod = _aggregate_production_by_provider(db_path, periods) if db_path else {}
    bridge = _bridge_rows_by_period()
    rows: list[dict[str, Any]] = []
    for period in periods:
        sources: list[dict[str, float]] = []
        if period in daysheet:
            sources.append(daysheet[period])
        if period in provider_prod:
            sources.append({"production": provider_prod[period], "collections": 0.0, "insurance": 0.0, "patient": 0.0})
        if period in bridge:
            sources.append(bridge[period])
        if not sources:
            continue
        rows.append(_build_period_row(period, sources))
    return rows


def sync_dashboard_period_rows() -> dict[str, Any]:
    periods = relevant_period_labels()
    db_path = resolve_analytics_db()
    generated = _month_rows(db_path, periods)
    dest = softdent_import_dir()
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "softdent_dashboard_data.json"
    existing: list[dict[str, Any]] = []
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(payload, list):
                existing = payload
        except json.JSONDecodeError:
            existing = []
    by_period = {str(row.get("period")): row for row in existing if isinstance(row, dict) and row.get("period")}
    for row in generated:
        period = str(row["period"])
        prior = by_period.get(period)
        if prior:
            by_period[period] = _build_period_row(
                period,
                [
                    {
                        "production": float(prior.get("production") or 0),
                        "collections": float(prior.get("collections") or 0),
                        "insurance": float(prior.get("insurance") or 0),
                        "patient": float(prior.get("patient") or 0),
                    },
                    row,
                ],
            )
        else:
            by_period[period] = row
    merged = [by_period[p] for p in sorted(by_period.keys()) if p in periods] + [
        by_period[p] for p in sorted(by_period.keys()) if p not in periods
    ]
    if not merged:
        merged = list(by_period.values())
    path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return {
        "ok": bool(merged),
        "path": str(path),
        "periods": [row.get("period") for row in merged if row.get("period") in periods],
        "rowCount": len(merged),
        "source": str(db_path) if db_path else None,
    }


if __name__ == "__main__":
    import json as _json

    print(_json.dumps(sync_dashboard_period_rows(), indent=2))
