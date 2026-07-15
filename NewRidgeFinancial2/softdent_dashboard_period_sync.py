"""Build SoftDent dashboard rows from analytics DB for current + prior month."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from import_cache_ttl import relevant_period_labels
from import_loader import softdent_import_dir
from import_sync import BRIDGE_AGGREGATE_JSON, _build_dashboard_from_bridge, _read_json
from quickbooks_monthly_sync import resolve_analytics_db

logger = logging.getLogger(__name__)

PRACTICE_NAME = "New Ridge Family Dental"


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return {str(row[1]) for row in cur.fetchall()}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def _aggregate_daysheet(db_path: Path, periods: list[str]) -> dict[str, dict[str, float]]:
    if not db_path.is_file() or not periods:
        return {}
    conn = sqlite3.connect(db_path)
    columns = _table_columns(conn, "daysheet_totals")
    if "year_month" not in columns and "report_date" not in columns:
        conn.close()
        return {}
    insurance_sql = "SUM(COALESCE(insurance_payment_total, 0))" if "insurance_payment_total" in columns else "0"
    # Backfill year_month from report_date when null (aggregation fix — not inventing amounts)
    if "report_date" in columns:
        ym_expr = "COALESCE(NULLIF(year_month, ''), substr(replace(report_date, '/', '-'), 1, 7))"
    else:
        ym_expr = "year_month"
    placeholders = ",".join("?" for _ in periods)
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT {ym_expr} AS ym,
               SUM(COALESCE(gross_production, 0)),
               SUM(COALESCE(net_production, 0)),
               SUM(COALESCE(collections, 0)),
               {insurance_sql}
        FROM daysheet_totals
        WHERE {ym_expr} IN ({placeholders})
        GROUP BY ym
        """,
        periods,
    )
    out: dict[str, dict[str, float]] = {}
    for year_month, gross, net, collections, insurance in cur.fetchall():
        if not year_month:
            continue
        production = float(gross or net or 0)
        coll = float(collections or 0)
        ins = float(insurance or 0)
        # Honesty: do not invent patient = collections when insurance is 0/null
        # (that paints a false 0/100 all-patient mix). Split stays empty until
        # insurance_payment_total or sd_payments remap provides a real side.
        split_ok = ins > 0
        out[str(year_month)] = {
            "production": production,
            "collections": coll,
            "insurance": ins if split_ok else 0.0,
            "patient": max(0.0, coll - ins) if split_ok else 0.0,
            "insuranceSplitReported": split_ok,
        }
    # Honest insurance remap: when daysheet footer insurance is 0/null but sd_payments
    # has Insurance Check Payment rows for that month, use those (never invent).
    if _table_exists(conn, "sd_payments"):
        pay_cols = _table_columns(conn, "sd_payments")
        if "method" in pay_cols and "amount" in pay_cols and "payment_date" in pay_cols:
            cur.execute(
                f"""
                SELECT substr(replace(payment_date, '/', '-'), 1, 7) AS ym,
                       SUM(COALESCE(amount, 0))
                FROM sd_payments
                WHERE lower(method) LIKE '%insurance%check%'
                  AND substr(replace(payment_date, '/', '-'), 1, 7) IN ({placeholders})
                GROUP BY ym
                """,
                periods,
            )
            for ym, amt in cur.fetchall():
                if not ym or ym not in out:
                    continue
                try:
                    ins_amt = float(amt or 0)
                except (TypeError, ValueError):
                    continue
                if ins_amt <= 0:
                    continue
                if float(out[ym].get("insurance") or 0) <= 0:
                    coll = float(out[ym].get("collections") or 0)
                    out[ym]["insurance"] = ins_amt
                    out[ym]["patient"] = max(0.0, coll - ins_amt)
                    out[ym]["insuranceSplitReported"] = True
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


def _is_register_production_authority(source: dict[str, Any]) -> bool:
    """True when SoftDent Register / daysheet / bridge should beat provider_prod max-merge."""
    auth = str(source.get("productionAuthority") or "").strip().lower()
    if auth in {"register", "softdent_period"}:
        return True
    kind = str(source.get("_source") or "").strip().lower()
    if kind in {"daysheet", "bridge", "inbox_export"}:
        return True
    if source.get("regularCollectionsReported") is True or source.get("registerInsPlanZero") is True:
        return True
    sk = str(source.get("sourceKind") or "").strip().lower()
    return sk.startswith("register")


def _merge_production(sources: list[dict[str, Any]]) -> float:
    """Prefer SoftDent Register/period production over provider_prod inflation (hal-10579)."""
    auth = 0.0
    other = 0.0
    for source in sources:
        try:
            prod = float(source.get("production") or 0)
        except (TypeError, ValueError):
            prod = 0.0
        if prod <= 0:
            continue
        if _is_register_production_authority(source):
            auth = _merge_metric(auth, prod)
        else:
            other = _merge_metric(other, prod)
    return auth if auth > 0 else other


def _merge_collections(existing: float | None, candidate: float | None, *, reported: bool) -> tuple[float | None, bool]:
    if not reported:
        return existing, existing is not None
    if candidate is None:
        return existing, existing is not None
    if existing is None:
        return float(candidate), True
    return _merge_metric(existing, float(candidate)), True


def _include_collections_from_source(source: dict[str, Any]) -> tuple[float | None, bool]:
    kind = str(source.get("_source") or "")
    if source.get("collectionsPending") is True:
        return None, False
    if source.get("collectionsReported") is False:
        return None, False
    if "collections" not in source:
        return None, False
    value = float(source.get("collections") or 0)
    production = float(source.get("production") or 0)
    if value > 0:
        return value, True
    if kind == "daysheet":
        if production > 0:
            return None, False
        return value, True
    if production > 0 and kind == "bridge":
        return None, False
    return value, True


def _prior_source_dict(prior: dict[str, Any]) -> dict[str, Any]:
    production = float(prior.get("production") or 0)
    collections = float(prior.get("collections") or 0)
    reported = prior.get("collectionsReported")
    pending = prior.get("collectionsPending")
    payload = {
        "_source": "prior",
        "production": production,
        "insurance": float(prior.get("insurance") or 0),
        "patient": float(prior.get("patient") or 0),
    }
    # Preserve Register Regular / Ins Plan honesty flags so a later stale CSV
    # cannot drop an earlier SoftDent-labeled Regular Collections truth.
    if prior.get("insuranceSplitReported") is True or (
        float(prior.get("patient") or 0) > 0 and float(prior.get("collections") or 0) > 0
    ):
        payload["insuranceSplitReported"] = True
    if prior.get("regularCollectionsReported") is True:
        payload["regularCollectionsReported"] = True
    if prior.get("registerInsPlanZero") is True:
        payload["registerInsPlanZero"] = True
    if prior.get("regularCollections") is not None:
        try:
            payload["regularCollections"] = float(prior.get("regularCollections") or 0)
        except (TypeError, ValueError):
            pass
    if prior.get("insPlanCollections") is not None:
        try:
            payload["insPlanCollections"] = float(prior.get("insPlanCollections") or 0)
        except (TypeError, ValueError):
            pass
    if prior.get("productionAuthority"):
        payload["productionAuthority"] = str(prior.get("productionAuthority"))
    elif prior.get("regularCollectionsReported") or prior.get("registerInsPlanZero"):
        payload["productionAuthority"] = "register"
    if pending is True:
        payload["collectionsPending"] = True
    elif reported is False:
        payload["collectionsReported"] = False
        payload["collections"] = collections
    elif "collections" in prior and prior.get("collections") not in (None, ""):
        payload["collectionsReported"] = True
        payload["collections"] = collections
    return payload


def _collections_source_kind(source: dict[str, Any]) -> str:
    return str(source.get("_source") or "")


def _explicit_collections_failure(sources: list[dict[str, Any]]) -> bool:
    """True when a collections-bearing source reports missing/zero collections with production."""
    for source in sources:
        kind = _collections_source_kind(source)
        if source.get("collectionsReported") is False:
            return True
        if kind not in {"daysheet", "bridge", "prior"}:
            continue
        if "collections" not in source:
            continue
        production = float(source.get("production") or 0)
        collections = float(source.get("collections") or 0)
        if production > 0 and collections <= 0:
            return True
    return False


def _is_current_month(period: str) -> bool:
    return str(period or "").strip()[:7] == datetime.now(timezone.utc).strftime("%Y-%m")


def _build_period_row(period: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
    production = _merge_production(sources)
    collections: float | None = None
    collections_reported = False
    insurance = 0.0
    patient = 0.0
    split_reported = False
    for source in sources:
        candidate, reported = _include_collections_from_source(source)
        collections, collections_reported = _merge_collections(collections, candidate, reported=reported)
        src_ins = float(source.get("insurance") or 0)
        src_pat = float(source.get("patient") or 0)
        src_split = (
            source.get("insuranceSplitReported") is True
            or source.get("regularCollectionsReported") is True
            or source.get("registerInsPlanZero") is True
            or (src_ins > 0 and src_pat >= 0)
        )
        if src_split:
            split_reported = True
            insurance = _merge_metric(insurance, src_ins)
            patient = _merge_metric(patient, src_pat)
        elif src_ins > 0:
            split_reported = True
            insurance = _merge_metric(insurance, src_ins)
            if src_pat > 0:
                patient = _merge_metric(patient, src_pat)
    # Only derive patient from collections−insurance when insurance side is real (>0).
    # Never invent all-patient dumps (ins=0, patient=collections) unless SoftDent
    # labeled Regular Collections on the Register (regularCollectionsReported).
    if split_reported and patient <= 0 and collections is not None and collections > 0 and insurance > 0:
        patient = max(0.0, collections - insurance)
    explicit_regular = any(
        bool(source.get("regularCollectionsReported") or source.get("registerInsPlanZero"))
        for source in sources
    )
    # Collapse false prior dumps: collections≈patient with insurance=0 is not a mix
    # — unless SoftDent Register explicitly reported Regular Collections / Ins Plan $0.
    if (
        not explicit_regular
        and collections is not None
        and collections > 0
        and insurance <= 0
        and patient > 0
        and abs(patient - collections) < 0.02
    ):
        patient = 0.0
        split_reported = False
    row: dict[str, Any] = {
        "provider": PRACTICE_NAME,
        "period": period,
        "production": production,
        "insurance": insurance if split_reported else 0.0,
        "patient": patient if split_reported else 0.0,
    }
    if any(_is_register_production_authority(s) for s in sources) and production > 0:
        row["productionAuthority"] = "register"
    if split_reported:
        row["insuranceSplitReported"] = True
    if explicit_regular:
        row["regularCollectionsReported"] = True
        if insurance <= 0 and collections is not None and float(collections or 0) > 0:
            row["registerInsPlanZero"] = True
    # Prefer the highest SoftDent-labeled Regular / Ins Plan figures across sources
    # (stale CSV must not clobber a newer Register XLS truth).
    for source in sources:
        if source.get("regularCollections") is None:
            continue
        try:
            cand = float(source.get("regularCollections") or 0)
        except (TypeError, ValueError):
            continue
        prev = row.get("regularCollections")
        if prev is None or cand > float(prev):
            row["regularCollections"] = cand
    for source in sources:
        if source.get("insPlanCollections") is None:
            continue
        try:
            cand = float(source.get("insPlanCollections") or 0)
        except (TypeError, ValueError):
            continue
        prev = row.get("insPlanCollections")
        if prev is None or cand > float(prev):
            row["insPlanCollections"] = cand
    # SoftDent Regular label is the patient-side truth when present.
    if explicit_regular and row.get("regularCollections") is not None:
        try:
            reg = float(row.get("regularCollections") or 0)
        except (TypeError, ValueError):
            reg = 0.0
        if reg > float(row.get("patient") or 0):
            row["patient"] = reg
            split_reported = True
            row["insuranceSplitReported"] = True
            row["insurance"] = insurance if split_reported else 0.0
    if collections is not None:
        row["collections"] = collections
        row["collectionsReported"] = True
    if collections_reported and collections is not None and collections > 0 and not split_reported:
        row["collectionsFormatRequired"] = True
    if production > 0 and not collections_reported:
        has_daysheet = any(_collections_source_kind(source) == "daysheet" for source in sources)
        if _explicit_collections_failure(sources):
            if _is_current_month(period) and not has_daysheet:
                row["collectionsPending"] = True
                row.pop("collectionsReported", None)
                row.pop("collections", None)
            else:
                row["collectionsReported"] = False
                if "collections" not in row:
                    row["collections"] = 0.0
        else:
            row["collectionsPending"] = True
            row.pop("collectionsReported", None)
            row.pop("collections", None)
    return row


def _ym_from_date(raw: str) -> str:
    text = str(raw or "").strip().replace("/", "-")
    if len(text) >= 7 and text[4] == "-" and text[:4].isdigit():
        return text[:7]
    return ""


def _aggregate_inbox_daysheet(periods: list[str]) -> dict[str, dict[str, Any]]:
    """Bootstrap open-month totals from SoftDentReportExports daysheet.jsonl.

    Used when analytics DB has no daysheet_totals row (NO_PERIOD_ROW gap).
    Never invents insurance/patient dollars — only sums present in the file.
    """
    if not periods:
        return {}
    period_set = {str(p).strip()[:7] for p in periods if str(p).strip()}
    out: dict[str, dict[str, Any]] = {}

    try:
        from softdent_operational_pipeline import (
            INSURANCE_PAYMENT_CODES,
            PATIENT_PAYMENT_CODES,
            _load_daysheet_transactions,
            resolve_daysheet_jsonl_path,
        )
    except ImportError:
        return {}

    jsonl = resolve_daysheet_jsonl_path()
    if jsonl and jsonl.is_file():
        try:
            txs = _load_daysheet_transactions(jsonl)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Inbox daysheet JSONL parse failed: %s", exc)
            txs = []
        buckets: dict[str, dict[str, float]] = {}
        for tx in txs or []:
            if not isinstance(tx, dict):
                continue
            ym = _ym_from_date(str(tx.get("reportDate") or ""))
            if not ym or ym not in period_set:
                continue
            bucket = buckets.setdefault(ym, {"production": 0.0, "insurance": 0.0, "patient": 0.0})
            code = str(tx.get("code") or "").strip()
            try:
                amt = float(tx.get("production")) if tx.get("production") is not None else 0.0
            except (TypeError, ValueError):
                amt = 0.0
            if amt == 0:
                continue
            if code in INSURANCE_PAYMENT_CODES:
                bucket["insurance"] += abs(amt)
            elif code in PATIENT_PAYMENT_CODES:
                bucket["patient"] += abs(amt)
            else:
                # Procedure / production lines (exclude write-offs handled as payment codes above)
                if amt > 0:
                    bucket["production"] += amt
        for ym, bucket in buckets.items():
            prod = float(bucket.get("production") or 0)
            ins = float(bucket.get("insurance") or 0)
            pat = float(bucket.get("patient") or 0)
            coll = ins + pat
            split_ok = ins > 0
            if prod <= 0 and coll <= 0:
                continue
            out[ym] = {
                "production": prod,
                "collections": coll if coll > 0 else 0.0,
                "insurance": ins if split_ok else 0.0,
                "patient": pat if split_ok else 0.0,
                "insuranceSplitReported": split_ok,
                "_inboxPath": str(jsonl),
            }

    # Presence-only stub: inbox classifies open periods but JSONL had no usable totals.
    try:
        from nr2_contracts.softdent_hardening import classify_daysheet_inbox_periods, scan_collections_export_inbox

        inbox = scan_collections_export_inbox()
        classified = classify_daysheet_inbox_periods(inbox.get("matches") if isinstance(inbox, dict) else None)
        for ym in classified.get("periods") or []:
            label = str(ym).strip()[:7]
            if label not in period_set or label in out:
                continue
            # File present for period — create honesty stub (no invented production $).
            out[label] = {
                "production": 0.0,
                "collections": 0.0,
                "insurance": 0.0,
                "patient": 0.0,
                "insuranceSplitReported": False,
                "inboxPresenceOnly": True,
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Inbox daysheet period classify failed: %s", exc)

    return out


def _month_rows(db_path: Path | None, periods: list[str]) -> list[dict[str, Any]]:
    daysheet = _aggregate_daysheet(db_path, periods) if db_path else {}
    provider_prod = _aggregate_production_by_provider(db_path, periods) if db_path else {}
    bridge = _bridge_rows_by_period()
    inbox_daysheet = _aggregate_inbox_daysheet(periods)
    rows: list[dict[str, Any]] = []
    for period in periods:
        sources: list[dict[str, Any]] = []
        if period in daysheet:
            sources.append(
                {
                    "_source": "daysheet",
                    "productionAuthority": "softdent_period",
                    **daysheet[period],
                }
            )
        if period in provider_prod:
            sources.append({"_source": "provider_prod", "production": provider_prod[period]})
        if period in bridge:
            sources.append(
                {
                    "_source": "bridge",
                    "productionAuthority": "softdent_period",
                    **bridge[period],
                }
            )
        # DEF-001: SoftDentReportExports daysheet when analytics DB has no period row.
        if period in inbox_daysheet and not any(
            _collections_source_kind(s) == "daysheet" for s in sources
        ):
            sources.append(
                {
                    "_source": "daysheet",
                    "productionAuthority": "softdent_period",
                    **inbox_daysheet[period],
                }
            )
        if not sources:
            continue
        row = _build_period_row(period, sources)
        # Inbox presence without parsed production: still escape NO_PERIOD_ROW with honest flags.
        if any(s.get("inboxPresenceOnly") for s in sources) and float(row.get("production") or 0) <= 0:
            row["collectionsPending"] = True
            row["collectionsFormatRequired"] = True
            row.pop("collectionsReported", None)
            row.pop("collections", None)
        rows.append(row)
    return rows


def diagnose_collections_gap(db_path: Path | None, periods: list[str] | None = None) -> dict[str, Any]:
    periods = periods or relevant_period_labels()
    daysheet = _aggregate_daysheet(db_path, periods) if db_path and db_path.is_file() else {}
    bridge = _bridge_rows_by_period()
    issues: list[str] = []
    for period in periods:
        ds = daysheet.get(period)
        br = bridge.get(period)
        if ds and float(ds.get("collections") or 0) > 0:
            continue
        if ds and float(ds.get("production") or 0) > 0:
            issues.append(f"{period}: daysheet row exists but collections are zero — rerun final daysheet in SoftDent.")
            continue
        if br and float(br.get("production") or 0) > 0:
            if _is_current_month(period):
                continue
            if db_path and db_path.is_file():
                issues.append(
                    f"{period}: production without daysheet_totals row in {db_path.name} — export daysheet before period close."
                )
            else:
                issues.append(
                    f"{period}: bridge production without daysheet collections — configure NR2_FINANCIAL_ANALYTICS_DB."
                )
    return {
        "periods": periods,
        "daysheetPeriods": sorted(daysheet.keys()),
        "bridgePeriods": sorted(bridge.keys()),
        "analyticsDb": str(db_path) if db_path else None,
        "issues": issues,
    }


def _stub_source_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Convert export summary into a period-row source (no invented $)."""
    production = float(summary.get("production") or 0)
    source_kind = str(summary.get("sourceKind") or "")
    source: dict[str, Any] = {
        "_source": "inbox_export",
        "production": production,
        "insurance": float(summary.get("insurance") or 0),
        "patient": float(summary.get("patient") or 0),
        "sourceKind": source_kind,
    }
    if source_kind.startswith("register") or summary.get("regularCollectionsReported") is True:
        source["productionAuthority"] = "register"
    elif production > 0:
        source["productionAuthority"] = "softdent_period"
    if summary.get("insuranceSplitReported") is True:
        source["insuranceSplitReported"] = True
    if summary.get("regularCollectionsReported") is True:
        source["regularCollectionsReported"] = True
    if summary.get("registerInsPlanZero") is True:
        source["registerInsPlanZero"] = True
    if summary.get("regularCollections") is not None:
        try:
            source["regularCollections"] = float(summary.get("regularCollections"))
        except (TypeError, ValueError):
            pass
    if summary.get("insPlanCollections") is not None:
        try:
            source["insPlanCollections"] = float(summary.get("insPlanCollections"))
        except (TypeError, ValueError):
            pass
    collections = summary.get("collections")
    if collections is not None:
        try:
            coll = float(collections)
        except (TypeError, ValueError):
            coll = None
        if coll is not None and coll > 0:
            source["collections"] = coll
            source["collectionsReported"] = True
    if summary.get("daysheetWithoutSplit") and production > 0 and "collections" not in source:
        # Production-only daysheet → honest pending, never $0 collections.
        source.pop("collections", None)
        source.pop("collectionsReported", None)
    return source


def ingest_daysheet_to_period(*, force_reimport: bool = False) -> dict[str, Any]:
    """Create/update dashboard period stubs from SoftDent export inbox CSV/JSONL.

    Triggered when inbox has daysheet/register files. Never invents insurance/patient
    dollars. Production-only daysheet → collectionsPending / daysheetWithoutSplit.
    """
    from nr2_contracts.softdent_hardening import scan_collections_export_inbox
    from softdent_practice_exports import summarize_daysheet_export

    periods = relevant_period_labels()
    inbox = scan_collections_export_inbox(limit=20)
    matches = inbox.get("matches") if isinstance(inbox.get("matches"), list) else []
    summaries: list[dict[str, Any]] = []
    for item in matches:
        if not isinstance(item, dict):
            continue
        path = Path(str(item.get("path") or ""))
        if not path.is_file():
            continue
        try:
            summary = summarize_daysheet_export(path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("inbox export summarize failed for %s: %s", path, exc)
            continue
        if not summary or not summary.get("period"):
            continue
        # Skip empty/unknown parses — do not create blank period stubs.
        try:
            prod = float(summary.get("production") or 0)
        except (TypeError, ValueError):
            prod = 0.0
        try:
            coll = float(summary.get("collections") or 0) if summary.get("collections") is not None else 0.0
        except (TypeError, ValueError):
            coll = 0.0
        if prod <= 0 and coll <= 0:
            continue
        summaries.append(summary)

    dest = softdent_import_dir()
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "softdent_dashboard_data.json"
    existing: list[dict[str, Any]] = []
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(payload, list):
                existing = [row for row in payload if isinstance(row, dict)]
        except json.JSONDecodeError:
            existing = []
    by_period = {str(row.get("period")): row for row in existing if row.get("period")}
    had_any_period = bool(by_period)
    created: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []

    for summary in summaries:
        period = str(summary["period"])[:7]
        # Prefer relevant open/prior months; when dashboard is empty, still ingest
        # any parseable period so gap assess is never stuck on NO_PERIOD_ROW.
        if period not in periods and had_any_period and not force_reimport:
            skipped.append(period)
            continue
        prior = by_period.get(period)
        if prior and not force_reimport and not (
            prior.get("collectionsPending") is True and float(prior.get("production") or 0) <= 0
        ):
            # Keep richer existing rows unless force or empty pending stub.
            if float(prior.get("production") or 0) > 0 or prior.get("collectionsReported") is True:
                skipped.append(period)
                continue
        source = _stub_source_from_summary(summary)
        row = _build_period_row(period, [source] if not prior else [_prior_source_dict(prior), source])
        if summary.get("daysheetWithoutSplit") and not summary.get("hasInsurancePatientSplit"):
            if float(row.get("production") or 0) > 0 and row.get("collectionsReported") is not True:
                row["collectionsPending"] = True
                row.pop("collections", None)
                row.pop("collectionsReported", None)
            row["daysheetWithoutSplit"] = True
            if row.get("collectionsReported") is True and not (
                float(row.get("insurance") or 0) > 0
            ):
                row["collectionsFormatRequired"] = True
        # Register with collections total but Ins Plan = $0 → honest format/export required.
        if summary.get("collectionsFormatRequired") and float(row.get("insurance") or 0) <= 0:
            row["collectionsFormatRequired"] = True
        if prior:
            updated.append(period)
        else:
            created.append(period)
        by_period[period] = row
        had_any_period = True

    merged = [by_period[p] for p in sorted(by_period.keys())]
    from import_cache_ttl import write_text_if_changed

    changed = False
    if created or updated:
        changed = write_text_if_changed(path, json.dumps(merged, indent=2))
    return {
        "ok": True,
        "forceReimport": force_reimport,
        "path": str(path),
        "changed": changed,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "summaries": [
            {
                "period": s.get("period"),
                "sourceKind": s.get("sourceKind"),
                "production": s.get("production"),
                "hasInsurancePatientSplit": s.get("hasInsurancePatientSplit"),
                "daysheetWithoutSplit": s.get("daysheetWithoutSplit"),
                "collectionsFormatRequired": s.get("collectionsFormatRequired"),
            }
            for s in summaries
        ],
        "inboxMatchCount": inbox.get("matchCount"),
    }


def sync_dashboard_period_rows(*, force_reimport: bool = False) -> dict[str, Any]:
    inbox_ingest = ingest_daysheet_to_period(force_reimport=force_reimport)
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
    merge_log: list[dict[str, Any]] = []
    for row in generated:
        period = str(row["period"])
        prior = by_period.get(period)
        if prior:
            merged = _build_period_row(period, [_prior_source_dict(prior), row])
            # Preserve honesty flags from inbox stubs when DB still lacks split.
            if prior.get("daysheetWithoutSplit") and not (
                float(merged.get("insurance") or 0) > 0
            ):
                merged["daysheetWithoutSplit"] = True
            if prior.get("collectionsFormatRequired") and not (
                float(merged.get("insurance") or 0) > 0
            ):
                merged["collectionsFormatRequired"] = True
            # Keep Register Regular / Ins Plan honesty when analytics merge lacks labels.
            if prior.get("regularCollectionsReported") is True:
                merged["regularCollectionsReported"] = True
            if prior.get("registerInsPlanZero") is True:
                merged["registerInsPlanZero"] = True
            if prior.get("regularCollections") is not None and merged.get("regularCollections") is None:
                try:
                    merged["regularCollections"] = float(prior.get("regularCollections") or 0)
                except (TypeError, ValueError):
                    pass
            if prior.get("productionAuthority"):
                merged["productionAuthority"] = prior.get("productionAuthority")
            elif float(merged.get("production") or 0) > 0 and (
                prior.get("regularCollectionsReported") or prior.get("registerInsPlanZero")
            ):
                merged["productionAuthority"] = "register"
            merge_log.append(
                {
                    "period": period,
                    "action": "upsert",
                    "priorProduction": prior.get("production"),
                    "priorCollections": prior.get("collections"),
                    "priorCollectionsPending": prior.get("collectionsPending"),
                    "mergedProduction": merged.get("production"),
                    "mergedCollections": merged.get("collections"),
                    "mergedCollectionsPending": merged.get("collectionsPending"),
                }
            )
            by_period[period] = merged
        else:
            merge_log.append({"period": period, "action": "insert", "mergedProduction": row.get("production")})
            by_period[period] = row
    if merge_log:
        logger.info("SoftDent dashboard period upsert merge: %s", merge_log)
    merged = [by_period[p] for p in sorted(by_period.keys()) if p in periods] + [
        by_period[p] for p in sorted(by_period.keys()) if p not in periods
    ]
    if not merged:
        merged = list(by_period.values())
    from import_cache_ttl import write_text_if_changed

    changed = write_text_if_changed(path, json.dumps(merged, indent=2))
    diagnostic = diagnose_collections_gap(db_path, periods)
    return {
        "ok": bool(merged),
        "path": str(path),
        "changed": changed,
        "forceReimport": force_reimport,
        "periods": [row.get("period") for row in merged if row.get("period") in periods],
        "rowCount": len(merged),
        "source": str(db_path) if db_path else None,
        "mergeLog": merge_log,
        "collectionsDiagnostic": diagnostic,
        "inboxIngest": inbox_ingest,
    }


if __name__ == "__main__":
    import json as _json

    print(_json.dumps(sync_dashboard_period_rows(), indent=2))
