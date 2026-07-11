"""
Phase I3 — Additive unified SQLite data plane (nr2_unified.db).

Mirrors SoftDent period metrics + QB expense rows from the import bundle
for cross-reference queries. Does not replace existing nr2_local.sqlite3
or invent dollars. Rollback = delete nr2_unified.db.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def unified_db_path() -> Path:
    try:
        from document_sync import NR2_DATA_DIR

        root = Path(NR2_DATA_DIR)
    except Exception:
        root = Path(__file__).resolve().parent / "app_data" / "nr2"
    root.mkdir(parents=True, exist_ok=True)
    return root / "nr2_unified.db"


def connect(*, path: Path | None = None) -> sqlite3.Connection:
    p = path or unified_db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), timeout=10)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


class _ConnCM:
    """Ensure Windows releases the DB file handle on exit."""

    def __init__(self, path: Path | None = None):
        self._path = path
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        self._conn = connect(path=self._path)
        return self._conn

    def __exit__(self, *exc: object) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None


def open_unified(*, path: Path | None = None) -> _ConnCM:
    return _ConnCM(path)


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS softdent_period_metrics (
            period TEXT NOT NULL,
            provider TEXT,
            production REAL,
            collections REAL,
            insurance REAL,
            patient REAL,
            collections_pending INTEGER NOT NULL DEFAULT 0,
            collections_reported INTEGER,
            gap_code TEXT,
            source TEXT,
            imported_at TEXT NOT NULL,
            PRIMARY KEY (period)
        );

        CREATE TABLE IF NOT EXISTS qb_expense_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL,
            qb_account TEXT,
            source TEXT,
            imported_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_qb_exp_period ON qb_expense_rows(period);

        CREATE TABLE IF NOT EXISTS qb_payroll_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period TEXT NOT NULL,
            employee TEXT NOT NULL,
            gross_wages REAL,
            employee_taxes REAL,
            employer_taxes REAL,
            net_pay REAL,
            source TEXT,
            imported_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_qb_payroll_period ON qb_payroll_rows(period);

        CREATE TABLE IF NOT EXISTS qb_ap_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period TEXT NOT NULL,
            vendor TEXT NOT NULL,
            bill_date TEXT,
            due_date TEXT,
            amount_due REAL,
            aging_bucket TEXT,
            source TEXT,
            imported_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_qb_ap_period ON qb_ap_rows(period);

        CREATE TABLE IF NOT EXISTS softdent_era_aggregates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period TEXT NOT NULL,
            payment_total REAL,
            claim_count INTEGER,
            source_file TEXT,
            source TEXT,
            imported_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_era_agg_period ON softdent_era_aggregates(period);

        CREATE TABLE IF NOT EXISTS era_835_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period TEXT NOT NULL,
            payer_name TEXT,
            procedure_code TEXT,
            total_paid REAL,
            claim_count INTEGER,
            adjustment_reasons TEXT,
            source_file TEXT,
            source TEXT,
            ingested_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_era835_period ON era_835_payments(period);
        CREATE INDEX IF NOT EXISTS idx_era835_payer ON era_835_payments(payer_name);

        CREATE TABLE IF NOT EXISTS softdent_production (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period TEXT NOT NULL,
            provider_id TEXT,
            procedure_code TEXT,
            procedure_description TEXT,
            production_amount REAL,
            quantity INTEGER,
            posted_date TEXT,
            source_file TEXT,
            source TEXT,
            ingested_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sd_prod_period ON softdent_production(period);

        CREATE TABLE IF NOT EXISTS softdent_case_acceptance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period TEXT NOT NULL,
            provider_id TEXT,
            treatment_planned_amount REAL,
            accepted_amount REAL,
            acceptance_rate REAL,
            source_file TEXT,
            source TEXT,
            ingested_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS softdent_patient_aging (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period TEXT NOT NULL,
            bucket_0_30 REAL,
            bucket_31_60 REAL,
            bucket_61_90 REAL,
            bucket_90_plus REAL,
            total_ar REAL,
            insurance_pending REAL,
            source_file TEXT,
            source TEXT,
            ingested_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS softdent_scheduling (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period TEXT NOT NULL,
            total_appointments INTEGER,
            broken_appointments INTEGER,
            fill_rate REAL,
            capacity_hours REAL,
            used_hours REAL,
            scheduled_production REAL,
            source_file TEXT,
            source TEXT,
            ingested_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS qb_net_profit (
            period TEXT NOT NULL PRIMARY KEY,
            total_income REAL,
            total_expenses REAL,
            total_payroll REAL,
            net_profit REAL,
            source_file TEXT,
            source TEXT,
            ingested_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS import_health_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            export_type TEXT NOT NULL,
            row_count INTEGER,
            staleness_hours REAL,
            gap_flags TEXT,
            detected_at TEXT NOT NULL
        );

        DROP VIEW IF EXISTS practice_health_snapshot;
        CREATE VIEW practice_health_snapshot AS
        SELECT
            p.period AS period,
            p.production AS production_amount,
            p.collections AS collection_amount,
            p.collections_pending AS collections_pending,
            p.gap_code AS gap_code,
            COALESCE((SELECT SUM(e.amount) FROM qb_expense_rows e WHERE e.period = p.period), 0) AS total_expenses,
            (SELECT SUM(COALESCE(pr.gross_wages, 0) + COALESCE(pr.employer_taxes, 0))
             FROM qb_payroll_rows pr WHERE pr.period = p.period) AS total_payroll,
            (SELECT SUM(ap.amount_due) FROM qb_ap_rows ap WHERE ap.period = p.period) AS total_ap,
            (SELECT SUM(era.payment_total) FROM softdent_era_aggregates era WHERE era.period = p.period) AS era_payment_total,
            (SELECT np.net_profit FROM qb_net_profit np WHERE np.period = p.period) AS qb_net_profit,
            CASE
                WHEN p.collections IS NOT NULL
                THEN p.collections
                     - COALESCE((SELECT SUM(e.amount) FROM qb_expense_rows e WHERE e.period = p.period), 0)
                     - COALESCE(
                         (SELECT SUM(COALESCE(pr.gross_wages, 0) + COALESCE(pr.employer_taxes, 0))
                          FROM qb_payroll_rows pr WHERE pr.period = p.period),
                         0
                       )
                ELSE NULL
            END AS net_operating
        FROM softdent_period_metrics p;

        DROP VIEW IF EXISTS v_production_vs_payroll;
        CREATE VIEW v_production_vs_payroll AS
        SELECT
            p.period AS period,
            COALESCE(SUM(p.production_amount), 0) AS total_production,
            COALESCE((
                SELECT SUM(COALESCE(py.gross_wages, 0) + COALESCE(py.employer_taxes, 0))
                FROM qb_payroll_rows py WHERE py.period = p.period
            ), 0) AS total_payroll,
            CASE
                WHEN COALESCE(SUM(p.production_amount), 0) > 0
                THEN ROUND(
                    COALESCE((
                        SELECT SUM(COALESCE(py.gross_wages, 0) + COALESCE(py.employer_taxes, 0))
                        FROM qb_payroll_rows py WHERE py.period = p.period
                    ), 0) / SUM(p.production_amount),
                    4
                )
                ELSE NULL
            END AS payroll_to_production_ratio
        FROM softdent_production p
        GROUP BY p.period;

        DROP VIEW IF EXISTS v_collection_vs_ap;
        CREATE VIEW v_collection_vs_ap AS
        SELECT
            m.period AS period,
            m.collections AS collections,
            (SELECT SUM(ap.amount_due) FROM qb_ap_rows ap WHERE ap.period = m.period) AS total_ap,
            (SELECT np.net_profit FROM qb_net_profit np WHERE np.period = m.period) AS net_profit
        FROM softdent_period_metrics m;

        DROP VIEW IF EXISTS v_case_acceptance;
        CREATE VIEW v_case_acceptance AS
        SELECT
            period AS period,
            SUM(COALESCE(treatment_planned_amount, 0)) AS treatment_planned,
            SUM(COALESCE(accepted_amount, 0)) AS treatment_accepted,
            CASE
                WHEN SUM(COALESCE(treatment_planned_amount, 0)) > 0
                THEN ROUND(SUM(COALESCE(accepted_amount, 0)) / SUM(treatment_planned_amount), 4)
                ELSE NULL
            END AS acceptance_rate,
            CASE
                WHEN COUNT(*) < 1 THEN 'none'
                WHEN SUM(COALESCE(treatment_planned_amount, 0)) <= 0 THEN 'low'
                WHEN SUM(COALESCE(treatment_planned_amount, 0)) < 5000 THEN 'low'
                ELSE 'high'
            END AS confidence
        FROM softdent_case_acceptance
        GROUP BY period;

        DROP VIEW IF EXISTS v_patient_aging;
        CREATE VIEW v_patient_aging AS
        SELECT
            period AS period,
            bucket_0_30 AS bucket_0_30,
            bucket_31_60 AS bucket_31_60,
            bucket_61_90 AS bucket_61_90,
            bucket_90_plus AS bucket_90_plus,
            insurance_pending AS insurance_pending,
            COALESCE(
                total_ar,
                COALESCE(bucket_0_30, 0) + COALESCE(bucket_31_60, 0)
                + COALESCE(bucket_61_90, 0) + COALESCE(bucket_90_plus, 0)
            ) AS total_ar
        FROM softdent_patient_aging;

        DROP VIEW IF EXISTS v_scheduling_efficiency;
        CREATE VIEW v_scheduling_efficiency AS
        SELECT
            s.period AS period,
            s.total_appointments AS total_appointments,
            s.broken_appointments AS broken_appointments,
            s.fill_rate AS fill_rate,
            s.scheduled_production AS scheduled_production,
            COALESCE(
                (SELECT m.production FROM softdent_period_metrics m WHERE m.period = s.period),
                (SELECT SUM(p.production_amount) FROM softdent_production p WHERE p.period = s.period)
            ) AS actual_production,
            CASE
                WHEN s.scheduled_production IS NOT NULL AND s.scheduled_production > 0
                     AND COALESCE(
                         (SELECT m.production FROM softdent_period_metrics m WHERE m.period = s.period),
                         (SELECT SUM(p.production_amount) FROM softdent_production p WHERE p.period = s.period)
                     ) IS NOT NULL
                THEN ROUND(
                    COALESCE(
                        (SELECT m.production FROM softdent_period_metrics m WHERE m.period = s.period),
                        (SELECT SUM(p.production_amount) FROM softdent_production p WHERE p.period = s.period)
                    ) / s.scheduled_production,
                    4
                )
                ELSE NULL
            END AS schedule_accuracy
        FROM softdent_scheduling s;
        """
    )
    _ensure_optional_columns(conn)
    conn.commit()


def _ensure_optional_columns(conn: sqlite3.Connection) -> None:
    """Additive columns for W0 (safe on older DBs created before insurance/scheduled fields)."""
    specs = (
        ("softdent_patient_aging", "insurance_pending", "REAL"),
        ("softdent_scheduling", "scheduled_production", "REAL"),
    )
    for table, col, typedef in specs:
        cols = {str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if col not in cols:
            # table/col/typedef are fixed literals in specs above (not user input).
            conn.execute("ALTER TABLE " + table + " ADD COLUMN " + col + " " + typedef)

def _parse_money(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).replace("$", "").replace(",", "").strip()
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


def _period_key(row: dict[str, Any]) -> str:
    return str(row.get("period") or row.get("year_month") or row.get("Period") or "").strip()[:32]


def ingest_from_bundle(
    bundle: dict[str, Any] | None,
    *,
    db_path: Path | None = None,
    skip_dq: bool = False,
) -> dict[str, Any]:
    """Upsert SoftDent periods + QB expenses from import bundle. Additive only."""
    b = bundle if isinstance(bundle, dict) else {}
    now = _utc_now()
    softdent_n = 0
    qb_n = 0
    gap_code = None
    payroll_meta: dict[str, Any] = {}
    t0_meta: dict[str, Any] = {}
    t1_meta: dict[str, Any] = {}
    t2_meta: dict[str, Any] = {}

    # W1 — reject-only DQ before merge (no imputation)
    dq_meta: dict[str, Any] | None = None
    if not skip_dq:
        try:
            from apex_import_dq_pack import dq_enabled, validate_bundle_dq

            if dq_enabled():
                dq_meta = validate_bundle_dq(b)
                if not dq_meta.get("ok"):
                    return {
                        "ok": False,
                        "reason": "dq_blocked",
                        "gapCode": dq_meta.get("gapCode"),
                        "dq": dq_meta,
                        "phase": "W1",
                        "softDentWriteBack": False,
                        "importedAt": now,
                    }
        except Exception as exc:  # noqa: BLE001
            dq_meta = {"ok": False, "error": str(exc), "bypassed": True}

    try:
        from apex_softdent_hardening_pack import assess_collections_gap

        gap_code = assess_collections_gap(b).get("gapCode")
    except Exception:
        gap_code = None

    with open_unified(path=db_path) as conn:
        # SoftDent dashboard periods
        try:
            from apex_backend import _dashboard_rows

            rows = _dashboard_rows(b)
        except Exception:
            softdent = b.get("softdent") if isinstance(b.get("softdent"), dict) else {}
            dash = softdent.get("dashboard") if isinstance(softdent.get("dashboard"), dict) else {}
            rows = dash.get("rows") if isinstance(dash.get("rows"), list) else []

        for row in rows:
            if not isinstance(row, dict):
                continue
            period = _period_key(row)
            if not period:
                continue
            pending = 1 if row.get("collectionsPending") else 0
            reported = row.get("collectionsReported")
            reported_i = None if reported is None else (1 if reported else 0)
            coll = None
            if not pending and "collections" in row:
                coll = _parse_money(row.get("collections"))
            conn.execute(
                """
                INSERT INTO softdent_period_metrics (
                    period, provider, production, collections, insurance, patient,
                    collections_pending, collections_reported, gap_code, source, imported_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(period) DO UPDATE SET
                    provider=excluded.provider,
                    production=excluded.production,
                    collections=excluded.collections,
                    insurance=excluded.insurance,
                    patient=excluded.patient,
                    collections_pending=excluded.collections_pending,
                    collections_reported=excluded.collections_reported,
                    gap_code=excluded.gap_code,
                    source=excluded.source,
                    imported_at=excluded.imported_at
                """,
                (
                    period,
                    str(row.get("provider") or "")[:80] or None,
                    _parse_money(row.get("production")),
                    coll,
                    _parse_money(row.get("insurance") or row.get("Insurance")),
                    _parse_money(row.get("patient") or row.get("Patient")),
                    pending,
                    reported_i,
                    gap_code if pending else ("OK" if coll is not None else gap_code),
                    "import_bundle",
                    now,
                ),
            )
            softdent_n += 1

        # QuickBooks expense categories / rows (replace period slices lightly)
        try:
            from apex_backend import _section_rows

            cat_rows = _section_rows(b, "quickbooks", "expenseCategories") or []
            exp_rows = _section_rows(b, "quickbooks", "expenses") or []
        except Exception:
            qb = b.get("quickbooks") if isinstance(b.get("quickbooks"), dict) else {}
            cat = qb.get("expenseCategories") if isinstance(qb.get("expenseCategories"), dict) else {}
            cat_rows = cat.get("rows") if isinstance(cat.get("rows"), list) else []
            exp = qb.get("expenses") if isinstance(qb.get("expenses"), dict) else {}
            exp_rows = exp.get("rows") if isinstance(exp.get("rows"), list) else []

        # Derive a period label from P&L if present
        period_qb = "current"
        try:
            from apex_backend import _section_rows, _latest_period_row

            pl = _section_rows(b, "quickbooks", "profitAndLoss") or []
            latest_pl = _latest_period_row(pl) if pl else None
            if latest_pl:
                period_qb = _period_key(latest_pl) or period_qb
        except Exception:
            pass

        # Clear and re-insert expense category rollup for this period (idempotent)
        if cat_rows or exp_rows:
            conn.execute("DELETE FROM qb_expense_rows WHERE period = ? AND source = ?", (period_qb, "import_bundle"))

        for row in cat_rows:
            if not isinstance(row, dict):
                continue
            cat_name = str(
                row.get("Category") or row.get("category") or row.get("Account") or row.get("Name") or ""
            ).strip()[:120]
            amt = _parse_money(row.get("Amount") or row.get("amount") or row.get("Total"))
            if not cat_name or amt is None:
                continue
            conn.execute(
                """
                INSERT INTO qb_expense_rows (period, category, amount, qb_account, source, imported_at)
                VALUES (?,?,?,?,?,?)
                """,
                (period_qb, cat_name, amt, cat_name, "import_bundle", now),
            )
            qb_n += 1

        if not cat_rows:
            for row in exp_rows[:200]:
                if not isinstance(row, dict):
                    continue
                cat_name = str(
                    row.get("Category") or row.get("Account") or row.get("Name") or "Expense"
                ).strip()[:120]
                amt = _parse_money(row.get("Amount") or row.get("amount"))
                if amt is None:
                    continue
                conn.execute(
                    """
                    INSERT INTO qb_expense_rows (period, category, amount, qb_account, source, imported_at)
                    VALUES (?,?,?,?,?,?)
                    """,
                    (period_qb, cat_name or "Expense", amt, cat_name, "import_bundle", now),
                )
                qb_n += 1

        # Phase S0 — payroll + AP (SSN redacted in pack)
        try:
            from apex_qb_payroll_pack import ingest_payroll_ap_into_conn

            payroll_meta = ingest_payroll_ap_into_conn(
                conn, b, period_qb=period_qb, now=now
            )
        except Exception as exc:  # noqa: BLE001
            payroll_meta = {"ok": False, "error": str(exc)}

        # Phase T0 — SoftDent production + case acceptance
        try:
            from apex_softdent_production_pack import ingest_softdent_production_into_conn

            t0_meta = ingest_softdent_production_into_conn(conn, b, now=now)
        except Exception as exc:  # noqa: BLE001
            t0_meta = {"ok": False, "error": str(exc)}

        # Phase T1 — aging + scheduling
        try:
            from apex_softdent_aging_schedule_pack import ingest_aging_schedule_into_conn

            t1_meta = ingest_aging_schedule_into_conn(conn, b, now=now)
        except Exception as exc:  # noqa: BLE001
            t1_meta = {"ok": False, "error": str(exc)}

        # Phase T2 — QB net profit
        try:
            from apex_qb_net_profit_pack import ingest_net_profit_into_conn

            t2_meta = ingest_net_profit_into_conn(conn, b, now=now)
        except Exception as exc:  # noqa: BLE001
            t2_meta = {"ok": False, "error": str(exc)}

        # Import health log
        diag = b.get("diagnostics") if isinstance(b.get("diagnostics"), dict) else {}
        summary = diag.get("summary") if isinstance(diag.get("summary"), dict) else {}
        flags: list[str] = []
        if gap_code and gap_code != "OK":
            flags.append(str(gap_code))
        for meta in (payroll_meta, t0_meta, t1_meta, t2_meta):
            if isinstance(meta, dict) and meta.get("gapCode") and meta.get("gapCode") != "OK":
                flags.append(str(meta["gapCode"]))
        gap_flags = json.dumps(flags)
        conn.execute(
            """
            INSERT INTO import_health_log (source, export_type, row_count, staleness_hours, gap_flags, detected_at)
            VALUES (?,?,?,?,?,?)
            """,
            (
                "bundle",
                "apex_sync",
                int(summary.get("connected") or 0),
                None,
                gap_flags,
                now,
            ),
        )
        conn.commit()

    return {
        "ok": True,
        "softdentPeriods": softdent_n,
        "qbExpenseRows": qb_n,
        "qbPayrollRows": int(payroll_meta.get("payrollRows") or 0) if isinstance(payroll_meta, dict) else 0,
        "qbApRows": int(payroll_meta.get("apRows") or 0) if isinstance(payroll_meta, dict) else 0,
        "productionRows": int(t0_meta.get("productionRows") or 0) if isinstance(t0_meta, dict) else 0,
        "caseAcceptanceRows": int(t0_meta.get("caseAcceptanceRows") or 0) if isinstance(t0_meta, dict) else 0,
        "agingPeriods": int(t1_meta.get("agingPeriods") or 0) if isinstance(t1_meta, dict) else 0,
        "schedulingPeriods": int(t1_meta.get("schedulingPeriods") or 0) if isinstance(t1_meta, dict) else 0,
        "netProfitRows": int(t2_meta.get("netProfitRows") or 0) if isinstance(t2_meta, dict) else 0,
        "gapCode": gap_code,
        "payrollGapCode": payroll_meta.get("gapCode") if isinstance(payroll_meta, dict) else None,
        "dq": dq_meta,
        "dbPath": str(db_path or unified_db_path()),
        "importedAt": now,
        "localOnly": True,
    }


def list_practice_health_snapshots(*, limit: int = 12, db_path: Path | None = None) -> list[dict[str, Any]]:
    with open_unified(path=db_path) as conn:
        rows = conn.execute(
            """
            SELECT period, production_amount, collection_amount, collections_pending, gap_code,
                   total_expenses, total_payroll, total_ap, era_payment_total, net_operating
            FROM practice_health_snapshot
            ORDER BY period DESC
            LIMIT ?
            """,
            (max(1, min(int(limit), 36)),),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            payroll = r["total_payroll"]
            out.append(
                {
                    "period": r["period"],
                    "production": r["production_amount"],
                    "collections": r["collection_amount"],
                    "collectionsPending": bool(r["collections_pending"]),
                    "gapCode": r["gap_code"],
                    "totalExpenses": r["total_expenses"],
                    "totalPayroll": payroll,
                    "payrollPending": payroll is None,
                    "totalAp": r["total_ap"],
                    "eraPaymentTotal": r["era_payment_total"],
                    "netOperating": r["net_operating"],
                }
            )
    return out


def orchestrator_context_snapshot(*, limit: int = 6, db_path: Path | None = None) -> dict[str, Any]:
    """Compact snapshot for 30B audits — no patient PHI."""
    snaps = list_practice_health_snapshots(limit=limit, db_path=db_path)
    path = db_path or unified_db_path()
    return {
        "ok": True,
        "unifiedDb": str(path),
        "exists": path.is_file(),
        "periods": snaps,
        "stalenessNote": "Values mirrored from last Apex Sync ingest — verify import health if stale.",
        "refreshedAt": _utc_now(),
    }


def list_production_vs_payroll(*, limit: int = 12, db_path: Path | None = None) -> list[dict[str, Any]]:
    with open_unified(path=db_path) as conn:
        rows = conn.execute(
            """
            SELECT period, total_production, total_payroll, payroll_to_production_ratio
            FROM v_production_vs_payroll
            ORDER BY period DESC
            LIMIT ?
            """,
            (max(1, min(int(limit), 36)),),
        ).fetchall()
        return [
            {
                "period": r["period"],
                "totalProduction": r["total_production"],
                "totalPayroll": r["total_payroll"],
                "payrollToProductionRatio": r["payroll_to_production_ratio"],
            }
            for r in rows
        ]


def list_collection_vs_ap(*, limit: int = 12, db_path: Path | None = None) -> list[dict[str, Any]]:
    with open_unified(path=db_path) as conn:
        rows = conn.execute(
            """
            SELECT period, collections, total_ap, net_profit
            FROM v_collection_vs_ap
            ORDER BY period DESC
            LIMIT ?
            """,
            (max(1, min(int(limit), 36)),),
        ).fetchall()
        return [
            {
                "period": r["period"],
                "collections": r["collections"],
                "totalAp": r["total_ap"],
                "netProfit": r["net_profit"],
            }
            for r in rows
        ]


def list_case_acceptance(*, limit: int = 12, db_path: Path | None = None) -> list[dict[str, Any]]:
    with open_unified(path=db_path) as conn:
        rows = conn.execute(
            """
            SELECT period, treatment_planned, treatment_accepted, acceptance_rate, confidence
            FROM v_case_acceptance
            ORDER BY period DESC
            LIMIT ?
            """,
            (max(1, min(int(limit), 36)),),
        ).fetchall()
        return [
            {
                "period": r["period"],
                "treatmentPlanned": r["treatment_planned"],
                "treatmentAccepted": r["treatment_accepted"],
                "acceptanceRate": r["acceptance_rate"],
                "confidence": r["confidence"],
            }
            for r in rows
        ]


def list_patient_aging(*, limit: int = 12, db_path: Path | None = None) -> list[dict[str, Any]]:
    with open_unified(path=db_path) as conn:
        rows = conn.execute(
            """
            SELECT period, bucket_0_30, bucket_31_60, bucket_61_90, bucket_90_plus,
                   insurance_pending, total_ar
            FROM v_patient_aging
            ORDER BY period DESC
            LIMIT ?
            """,
            (max(1, min(int(limit), 36)),),
        ).fetchall()
        return [
            {
                "period": r["period"],
                "bucket0_30": r["bucket_0_30"],
                "bucket31_60": r["bucket_31_60"],
                "bucket61_90": r["bucket_61_90"],
                "bucket90Plus": r["bucket_90_plus"],
                "insurancePending": r["insurance_pending"],
                "totalAr": r["total_ar"],
            }
            for r in rows
        ]


def list_scheduling_efficiency(*, limit: int = 12, db_path: Path | None = None) -> list[dict[str, Any]]:
    with open_unified(path=db_path) as conn:
        rows = conn.execute(
            """
            SELECT period, total_appointments, broken_appointments, fill_rate,
                   scheduled_production, actual_production, schedule_accuracy
            FROM v_scheduling_efficiency
            ORDER BY period DESC
            LIMIT ?
            """,
            (max(1, min(int(limit), 36)),),
        ).fetchall()
        return [
            {
                "period": r["period"],
                "totalAppointments": r["total_appointments"],
                "brokenAppointments": r["broken_appointments"],
                "fillRate": r["fill_rate"],
                "scheduledProduction": r["scheduled_production"],
                "actualProduction": r["actual_production"],
                "scheduleAccuracy": r["schedule_accuracy"],
            }
            for r in rows
        ]


def production_vs_payroll_widget(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    del bundle
    rows = list_production_vs_payroll(limit=5)
    if not rows:
        return {
            "id": "production-vs-payroll",
            "type": "status",
            "label": "Production vs Payroll (T4)",
            "size": "full",
            "status": "empty",
            "message": "No production×payroll join yet",
            "emptyMessage": "Import SoftDent production + QB payroll, then Sync.",
            "hint": "View v_production_vs_payroll — empty ≠ $0.",
        }
    latest = rows[0]
    ratio = latest.get("payrollToProductionRatio")
    return {
        "id": "production-vs-payroll",
        "type": "status",
        "label": "Production vs Payroll (T4)",
        "size": "full",
        "status": "ok",
        "message": (
            f"{latest.get('period')}: prod={latest.get('totalProduction')} "
            f"payroll={latest.get('totalPayroll')} ratio={ratio}"
        ),
        "hint": "From v_production_vs_payroll (import-mirrored).",
        "rows": rows,
    }


def unified_db_widget(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    del bundle
    snaps = list_practice_health_snapshots(limit=5)
    path = unified_db_path()
    if not snaps:
        return {
            "id": "unified-db-snapshot",
            "type": "status",
            "label": "Unified DB (I3)",
            "size": "full",
            "status": "empty",
            "message": "No unified rows yet",
            "emptyMessage": "Run Apex Sync to ingest SoftDent/QB into nr2_unified.db",
            "hint": f"Additive DB: {path.name} — does not replace import bundles.",
        }
    latest = snaps[0]
    prod = latest.get("production")
    coll = latest.get("collections")
    exp = latest.get("totalExpenses")
    msg = f"{latest.get('period')}: prod={prod if prod is not None else '—'} coll={coll if coll is not None else '—'}"
    if exp is not None:
        msg += f" qbExp={exp}"
    return {
        "id": "unified-db-snapshot",
        "type": "status",
        "label": "Unified DB (I3)",
        "size": "full",
        "status": "ok",
        "message": msg,
        "hint": f"{len(snaps)} period(s) in {path.name}. SoftDent×QB join view — never invents $.",
        "snapshots": snaps,
        "gapCode": latest.get("gapCode"),
    }
