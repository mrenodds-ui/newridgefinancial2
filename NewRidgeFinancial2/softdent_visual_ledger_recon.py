"""HAL-10595 / money-bridge-bijection — exact cents at API/history boundary.

Builds on HAL-10594: NULL-preserving ledger aggregates + inputs-only fingerprint.
HAL-10595: dual-write integer cents alongside legacy REAL floats; bijective
money_to_api_bijective for audit consumers. Flag only — never invent gold lines,
never SoftDent write-back. empty != $0 (HAL-10591 honesty gate).
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import warnings
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from money_cents import (
    money_abs,
    money_sub,
    money_to_api,
    money_to_api_bijective,
    to_money,
)
from softdent_gold_payment_pipeline import audit_gold_payment_pipeline
from softdent_insco_ada_spine import (
    INS_PAYMENT_CODES,
    carrier_for_account,
    load_primary_insurance_map,
    table_exists,
)
from softdent_print_preview_audit import list_print_preview_audits
from softdent_treatment_planning import resolve_analytics_db, resolve_exports_dir
from ui_honesty_policy import (
    SOURCE_LEDGER_SPINE,
    SOURCE_PRINT_PREVIEW_VISUAL,
    enforce_empty_not_zero,
    is_empty_money,
)

DEF_ID = "HAL-10595"
PACKAGE_BUILD_ID = "hal-10595"
PRIOR_DEF_ID = "HAL-10594"


def _api_float(value: Any) -> float | None:
    """Legacy float bridge without repeating DeprecationWarning per call site."""
    money = value if isinstance(value, Decimal) else to_money(value)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return money_to_api(money)


def _cents(value: Any) -> int | None:
    return money_to_api_bijective(value, format="cents_int")  # type: ignore[arg-type]


def _exact_str(value: Any) -> str | None:
    return money_to_api_bijective(value, format="string_decimal")  # type: ignore[arg-type]

VARIANCE_THRESHOLD_ABSOLUTE = 5.00
VARIANCE_THRESHOLD_PERCENT = 5.0
SOURCE_LEDGER_CODE2 = "ledger_code2_period_sum"
HISTORY_TABLE = "recon_variance_history"
UNMAPPED_CARRIER = "(unmapped)"


class ReconciliationResult(str, Enum):
    MATCH = "MATCH"
    VARIANCE_WITHIN_TOLERANCE = "VARIANCE_WITHIN_TOLERANCE"
    VARIANCE_EXCEEDS_THRESHOLD = "VARIANCE_EXCEEDS_THRESHOLD"
    INSUFFICIENT_VISUAL = "INSUFFICIENT_VISUAL"
    INSUFFICIENT_LEDGER = "INSUFFICIENT_LEDGER"
    HONESTY_HALT = "HONESTY_HALT"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _valid_iso_day(raw: str) -> str | None:
    """Return canonical ISO day or None if calendar-invalid."""
    try:
        return date.fromisoformat(str(raw).strip()).isoformat()
    except ValueError:
        return None


def parse_date_range(raw: str | None) -> tuple[str | None, str | None]:
    """Parse visual-audit dateRange into (start, end) ISO dates (inclusive)."""
    text = str(raw or "").strip()
    if not text:
        return None, None

    m = re.fullmatch(r"(\d{4})-(\d{2})", text)
    if m:
        try:
            y, mo = int(m.group(1)), int(m.group(2))
            start = date(y, mo, 1)
            end = date(y, mo, monthrange(y, mo)[1])
            return start.isoformat(), end.isoformat()
        except ValueError:
            return None, None

    m2 = re.search(
        r"(\d{4}-\d{2}-\d{2})\s*(?:\.\.|/|–|—|to)\s*(\d{4}-\d{2}-\d{2})",
        text,
        re.I,
    )
    if m2:
        start = _valid_iso_day(m2.group(1))
        end = _valid_iso_day(m2.group(2))
        if start is None or end is None:
            return None, None
        return start, end

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        day = _valid_iso_day(text)
        if day is None:
            return None, None
        return day, day

    return None, None


def ensure_recon_variance_history_schema(conn: sqlite3.Connection) -> None:
    """PHI-safe aggregate history only (no patient/account columns)."""
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {HISTORY_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_start TEXT,
            period_end TEXT,
            visual_total REAL,
            ledger_total REAL,
            clamped_ledger_total REAL,
            variance_dollars REAL,
            top_carrier_code TEXT,
            scope_mismatch INTEGER NOT NULL DEFAULT 0,
            result_code TEXT,
            created_at TEXT NOT NULL,
            package_build_id TEXT,
            triggers_gold_ingest INTEGER NOT NULL DEFAULT 0,
            record_fingerprint TEXT,
            money_scale TEXT DEFAULT '0.01',
            visual_total_cents INTEGER,
            ledger_total_cents INTEGER,
            clamped_ledger_total_cents INTEGER,
            variance_cents INTEGER,
            money_cents_exact INTEGER
        )
        """
    )
    cols = {str(r[1]) for r in conn.execute(f"PRAGMA table_info({HISTORY_TABLE})").fetchall()}
    # HAL-10594: record_fingerprint = inputs-only hash (legacy input_fingerprint kept if present)
    if "record_fingerprint" not in cols:
        conn.execute(f"ALTER TABLE {HISTORY_TABLE} ADD COLUMN record_fingerprint TEXT")
        if "input_fingerprint" in cols:
            conn.execute(
                f"""
                UPDATE {HISTORY_TABLE}
                SET record_fingerprint = input_fingerprint
                WHERE record_fingerprint IS NULL AND input_fingerprint IS NOT NULL
                """
            )
    if "money_scale" not in cols:
        conn.execute(
            f"ALTER TABLE {HISTORY_TABLE} ADD COLUMN money_scale TEXT DEFAULT '0.01'"
        )
    # HAL-10595: exact integer cents (dual-write; REAL floats retained, deprecated for math)
    for col in (
        "visual_total_cents",
        "ledger_total_cents",
        "clamped_ledger_total_cents",
        "variance_cents",
        "money_cents_exact",
    ):
        if col not in cols:
            conn.execute(f"ALTER TABLE {HISTORY_TABLE} ADD COLUMN {col} INTEGER")
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{HISTORY_TABLE}_created "
        f"ON {HISTORY_TABLE}(created_at DESC)"
    )
    # Fail-fast on duplicate inputs (same record_fingerprint) — no silent overwrite
    conn.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{HISTORY_TABLE}_record_fp "
        f"ON {HISTORY_TABLE}(record_fingerprint) "
        f"WHERE record_fingerprint IS NOT NULL"
    )


def sum_ledger_code2_payments(
    *,
    period_start: str,
    period_end: str,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Sum SoftDent code-2 insurance payment amounts in period (not gold lines)."""
    out: dict[str, Any] = {
        "ok": False,
        "ledgerTotal": None,
        "rowCount": 0,
        "periodStart": period_start,
        "periodEnd": period_end,
        "sourceTag": SOURCE_LEDGER_CODE2,
        "emptyIsNotZero": True,
        "moneyScale": "0.01",
        "message": None,
    }
    path = Path(db_path) if db_path else resolve_analytics_db()
    if path is None or not Path(path).is_file():
        out["message"] = "Analytics DB missing — ledger sum unavailable (empty != $0)"
        return out
    conn = sqlite3.connect(str(path))
    try:
        if not table_exists(conn, "sd_account_transactions"):
            out["message"] = "sd_account_transactions missing — empty != $0"
            return out
        codes = sorted(INS_PAYMENT_CODES)
        placeholders = ",".join("?" for _ in codes)
        # HAL-10594: NULL-preserving aggregate — all-null amount rows must NOT become $0.00
        sql = (
            "SELECT COUNT(*), "
            "CASE "
            'WHEN COUNT(cash) + COUNT("check") + COUNT(credit) > 0 '
            'THEN SUM(COALESCE(cash, 0) + COALESCE("check", 0) + COALESCE(credit, 0)) '
            "ELSE NULL "
            "END "
            "FROM sd_account_transactions "
            "WHERE service_date >= ? AND service_date <= ? "
            "AND procedure IN (" + placeholders + ")"
        )
        rows = conn.execute(sql, (period_start, period_end, *codes)).fetchone()
        count = int((rows or (0, None))[0] or 0)
        total_raw = (rows or (0, None))[1]
        out["rowCount"] = count
        if count == 0 or total_raw is None:
            out["ledgerTotal"] = None
            out["message"] = (
                f"No usable SoftDent code-2 payment amounts in {period_start}..{period_end} "
                f"(rows={count}; empty != $0)"
            )
            out["ok"] = True
            return out
        total_m = to_money(total_raw)
        out["ledgerTotal"] = _api_float(total_m)
        out["ledgerTotalCents"] = _cents(total_m)
        out["ledgerTotalExact"] = _exact_str(total_m)
        out["totalCents"] = out["ledgerTotalCents"]
        out["ok"] = True
        out["message"] = (
            f"Ledger code-2 sum {out['ledgerTotal']:,.2f} from {count} row(s) "
            f"({period_start}..{period_end})"
        )
        return out
    finally:
        conn.close()


def sum_ledger_code2_by_carrier(
    *,
    period_start: str,
    period_end: str,
    db_path: Path | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Carrier breakdown of SoftDent code-2 payments (primary InsCo map; no PHI)."""
    out: dict[str, Any] = {
        "ok": False,
        "periodStart": period_start,
        "periodEnd": period_end,
        "carrierBreakdown": [],
        "breakdownTotal": None,
        "topCarrierCode": None,
        "emptyIsNotZero": True,
        "moneyScale": "0.01",
        "sourceTag": SOURCE_LEDGER_CODE2,
        "message": None,
    }
    path = Path(db_path) if db_path else resolve_analytics_db()
    if path is None or not Path(path).is_file():
        out["message"] = "Analytics DB missing — carrier breakdown unavailable (empty != $0)"
        return out
    conn = sqlite3.connect(str(path))
    try:
        if not table_exists(conn, "sd_account_transactions"):
            out["message"] = "sd_account_transactions missing — empty != $0"
            return out
        codes = sorted(INS_PAYMENT_CODES)
        placeholders = ",".join("?" for _ in codes)
        # HAL-10594: per-row NULL-preserving CASE (all-null → NULL, not $0.00)
        sql = (
            "SELECT account_num, "
            "CASE "
            'WHEN cash IS NOT NULL OR "check" IS NOT NULL OR credit IS NOT NULL '
            'THEN COALESCE(cash, 0) + COALESCE("check", 0) + COALESCE(credit, 0) '
            "ELSE NULL "
            "END "
            "FROM sd_account_transactions "
            "WHERE service_date >= ? AND service_date <= ? "
            "AND procedure IN (" + placeholders + ")"
        )
        rows = conn.execute(sql, (period_start, period_end, *codes)).fetchall()
        if not rows:
            out["ok"] = True
            out["message"] = (
                f"No code-2 rows for carrier breakdown in {period_start}..{period_end} "
                "(empty != $0)"
            )
            return out

        ins_map = load_primary_insurance_map(conn)
        by_carrier: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        skipped_null = 0
        has_negative = False
        for account_num, amt in rows:
            # Honesty: never coerce null amount to 0.0; no zero "(unmapped)" from NULL
            if amt is None:
                skipped_null += 1
                continue
            amount = to_money(amt)
            if amount is None:
                skipped_null += 1
                continue
            if amount < 0:
                has_negative = True
            if amount == 0:
                continue
            carrier = carrier_for_account(str(account_num or ""), ins_map) or UNMAPPED_CARRIER
            by_carrier[str(carrier)] += amount

        out["skippedNullAmounts"] = skipped_null
        out["hasNegative"] = has_negative
        if not by_carrier:
            out["ok"] = True
            out["message"] = "Carrier amounts empty after map (empty != $0)"
            return out

        ranked = sorted(by_carrier.items(), key=lambda kv: kv[1], reverse=True)
        total = to_money(sum((v for _, v in ranked), start=Decimal("0.00"))) or Decimal("0.00")
        top_n = [
            {
                "carrierCode": c,
                "amount": _api_float(to_money(a)),
                "amountCents": _cents(a),
            }
            for c, a in ranked[: max(1, int(limit))]
        ]
        out["carrierBreakdown"] = top_n
        out["breakdownTotal"] = _api_float(total)
        out["breakdownTotalCents"] = _cents(total)
        out["topCarrierCode"] = ranked[0][0]
        out["ok"] = True
        out["message"] = (
            f"Top carriers by code-2 amount (n={len(top_n)}); "
            f"breakdownTotal={out['breakdownTotal']}"
        )
        return out
    finally:
        conn.close()


def clamp_ledger_to_audit_period(
    *,
    audit_start: str,
    audit_end: str,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Re-query ledger on audit date bounds (distinguishes period drift vs $ drift)."""
    clamped = sum_ledger_code2_payments(
        period_start=audit_start, period_end=audit_end, db_path=db_path
    )
    return {
        "ok": bool(clamped.get("ok")),
        "clampedLedgerTotal": clamped.get("ledgerTotal"),
        "clampedLedgerTotalCents": clamped.get("ledgerTotalCents"),
        "totalCents": clamped.get("ledgerTotalCents"),
        "clampedPeriodStart": audit_start,
        "clampedPeriodEnd": audit_end,
        "rowCount": clamped.get("rowCount"),
        "emptyIsNotZero": True,
        "message": clamped.get("message"),
        "sourceTag": SOURCE_LEDGER_CODE2,
    }


def classify_variance(
    visual: float | None,
    ledger: float | None,
    *,
    abs_threshold: float = VARIANCE_THRESHOLD_ABSOLUTE,
    pct_threshold: float = VARIANCE_THRESHOLD_PERCENT,
) -> dict[str, Any]:
    """Classify visual vs ledger delta with HON-001 honesty gates."""
    result: dict[str, Any] = {
        "visualTotal": visual,
        "ledgerTotal": ledger,
        "delta": None,
        "deltaAbs": None,
        "deltaPct": None,
        "thresholdAbsolute": abs_threshold,
        "thresholdPercent": pct_threshold,
        "thresholdViolated": False,
        "honestyCheckPassed": True,
        "result": ReconciliationResult.HONESTY_HALT.value,
        "emptyIsNotZero": True,
        "triggersGoldIngest": False,
        "def": DEF_ID,
    }

    if is_empty_money(visual):
        result["result"] = ReconciliationResult.INSUFFICIENT_VISUAL.value
        result["honestyCheckPassed"] = True
        result["message"] = "Visual audit total missing — exclude from compare (empty != $0)"
        return result
    if is_empty_money(ledger):
        result["result"] = ReconciliationResult.INSUFFICIENT_LEDGER.value
        result["honestyCheckPassed"] = True
        result["message"] = "Ledger code-2 sum missing — exclude from compare (empty != $0)"
        return result

    v = to_money(visual)
    l = to_money(ledger)
    if v is None or l is None:
        result["result"] = ReconciliationResult.HONESTY_HALT.value
        result["honestyCheckPassed"] = False
        result["message"] = "Honesty halt — refused to coerce empty to $0.00 for reconciliation"
        return result

    delta = money_sub(v, l)
    delta_abs = money_abs(delta)
    assert delta is not None and delta_abs is not None
    base = max(abs(v), abs(l), Decimal("0.01"))
    delta_pct = (delta_abs / base) * Decimal("100")
    result["delta"] = _api_float(delta)
    result["deltaAbs"] = _api_float(delta_abs)
    result["deltaPct"] = float(delta_pct.quantize(Decimal("0.0001")))
    result["deltaCents"] = _cents(delta)
    result["visualTotal"] = _api_float(v)
    result["ledgerTotal"] = _api_float(l)
    result["visualTotalCents"] = _cents(v)
    result["ledgerTotalCents"] = _cents(l)
    result["totalCents"] = result["ledgerTotalCents"]
    result["moneyScale"] = "0.01"
    result["floatMoneyDeprecated"] = True

    abs_thr = to_money(abs_threshold) or Decimal(str(VARIANCE_THRESHOLD_ABSOLUTE))
    pct_thr = Decimal(str(pct_threshold))
    within_abs = delta_abs <= abs_thr
    within_pct = delta_pct <= pct_thr
    if v == l:
        result["result"] = ReconciliationResult.MATCH.value
        result["thresholdViolated"] = False
        result["message"] = "Visual audit matches ledger code-2 sum (cent-exact)"
    elif within_abs or within_pct:
        result["result"] = ReconciliationResult.VARIANCE_WITHIN_TOLERANCE.value
        result["thresholdViolated"] = False
        result["message"] = (
            f"Variance ${delta_abs:,.2f} ({float(delta_pct):.2f}%) within tolerance "
            f"(${abs_thr:,.2f} or {pct_threshold}%)"
        )
    else:
        result["result"] = ReconciliationResult.VARIANCE_EXCEEDS_THRESHOLD.value
        result["thresholdViolated"] = True
        result["message"] = (
            f"Variance ${delta_abs:,.2f} ({float(delta_pct):.2f}%) exceeds threshold — "
            "flag only; do not invent gold lines"
        )
    return result


def _select_visual_audit(
    *,
    period: str | None,
    dest: Path | None,
) -> tuple[dict[str, Any] | None, str | None, str | None, str | None]:
    audits = list_print_preview_audits(dest=dest, limit=50)
    rows = list(audits.get("rows") or [])
    candidates = [
        r
        for r in rows
        if isinstance(r, dict)
        and str(r.get("reportType") or "") in {"InsuranceIncome", ""}
    ] or [r for r in rows if isinstance(r, dict)]

    selected: dict[str, Any] | None = None
    audit_start = audit_end = None
    period_key = str(period or "").strip() or None

    for row in reversed(candidates):
        dr = str(row.get("dateRange") or "")
        start, end = parse_date_range(dr)
        if period_key:
            if period_key in {dr, (start or "")[:7], start, f"{start}..{end}"}:
                selected = row
                audit_start, audit_end = start, end
                break
            if start and end and len(period_key) == 7 and start.startswith(period_key):
                selected = row
                audit_start, audit_end = start, end
                break
        else:
            if start and end:
                selected = row
                audit_start, audit_end = start, end
                break
            if selected is None:
                selected = row
                audit_start, audit_end = start, end
    return selected, audit_start, audit_end, period_key


def append_recon_variance_history(
    recon: dict[str, Any],
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Persist PHI-safe variance snapshot. Never touches SoftDent or gold tables."""
    path = Path(db_path) if db_path else resolve_analytics_db()
    result: dict[str, Any] = {"ok": False, "triggersGoldIngest": False}
    if path is None or not Path(path).is_file():
        result["error"] = "analytics_db_missing"
        return result
    cmp_ = recon.get("comparison") if isinstance(recon.get("comparison"), dict) else {}
    carriers = recon.get("carrierBreakdown") if isinstance(recon.get("carrierBreakdown"), list) else []
    top = None
    if carriers and isinstance(carriers[0], dict):
        top = carriers[0].get("carrierCode")
    top = top or recon.get("topCarrierCode")
    # HAL-10594/10595: record_fingerprint hashes INPUTS only (bijective string money)
    visual_m = to_money(recon.get("visualTotal"))
    ledger_m = to_money(recon.get("ledgerTotal"))
    clamped_m = to_money(recon.get("clampedLedgerTotal"))
    delta_m = to_money(cmp_.get("delta"))
    payload = {
        "periodStart": recon.get("periodStart") or recon.get("requestedPeriodStart"),
        "periodEnd": recon.get("periodEnd") or recon.get("requestedPeriodEnd"),
        "auditPeriodStart": recon.get("auditPeriodStart"),
        "auditPeriodEnd": recon.get("auditPeriodEnd"),
        "visual": _exact_str(visual_m),
        "ledger": _exact_str(ledger_m),
        "scopeMismatch": bool(recon.get("scopeMismatch")),
        "build": PACKAGE_BUILD_ID,
        "scale": "0.01",
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    visual_cents = _cents(visual_m)
    ledger_cents = _cents(ledger_m)
    clamped_cents = _cents(clamped_m)
    variance_cents = _cents(delta_m)
    conn = sqlite3.connect(str(path), timeout=30.0)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        ensure_recon_variance_history_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        # Fail-fast on duplicate inputs (unique record_fingerprint)
        existing = conn.execute(
            f"SELECT id FROM {HISTORY_TABLE} WHERE record_fingerprint = ? LIMIT 1",
            (fingerprint,),
        ).fetchone()
        if existing:
            conn.rollback()
            result["ok"] = False
            result["error"] = "record_fingerprint_collision"
            result["existingId"] = int(existing[0])
            result["recordFingerprint"] = fingerprint
            return result
        conn.execute(
            f"""
            INSERT INTO {HISTORY_TABLE} (
                period_start, period_end, visual_total, ledger_total,
                clamped_ledger_total, variance_dollars, top_carrier_code,
                scope_mismatch, result_code, created_at, package_build_id,
                triggers_gold_ingest, record_fingerprint, money_scale,
                visual_total_cents, ledger_total_cents, clamped_ledger_total_cents,
                variance_cents, money_cents_exact
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, '0.01', ?, ?, ?, ?, ?)
            """,
            (
                payload["periodStart"],
                payload["periodEnd"],
                _api_float(visual_m),
                _api_float(ledger_m),
                _api_float(clamped_m),
                _api_float(delta_m),
                top,
                1 if recon.get("scopeMismatch") else 0,
                recon.get("result") or cmp_.get("result"),
                _utc_now(),
                PACKAGE_BUILD_ID,
                fingerprint,
                visual_cents,
                ledger_cents,
                clamped_cents,
                variance_cents,
                ledger_cents,  # money_cents_exact = ledger total cents
            ),
        )
        conn.commit()
        result["ok"] = True
        result["id"] = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        result["recordFingerprint"] = fingerprint
        result["totalCents"] = ledger_cents
        result["ledgerTotalCents"] = ledger_cents
        return result
    except sqlite3.IntegrityError as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        result["error"] = f"record_fingerprint_collision:{exc}"
        result["recordFingerprint"] = fingerprint
        return result
    except Exception as exc:  # noqa: BLE001
        try:
            conn.rollback()
        except Exception:
            pass
        result["error"] = f"{type(exc).__name__}:{exc}"
        return result
    finally:
        conn.close()


def list_recon_variance_history(
    *,
    months: int = 3,
    db_path: Path | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Read-only variance history (aggregates only)."""
    path = Path(db_path) if db_path else resolve_analytics_db()
    out: dict[str, Any] = {
        "ok": True,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "months": int(months),
        "rows": [],
        "triggersGoldIngest": False,
        "emptyIsNotZero": True,
    }
    if path is None or not Path(path).is_file():
        out["ok"] = False
        out["message"] = "Analytics DB missing (empty != $0)"
        return out
    conn = sqlite3.connect(str(path))
    try:
        ensure_recon_variance_history_schema(conn)
        # Approximate months via created_at ISO string compare
        cutoff = date.today().replace(day=1)
        y, m = cutoff.year, cutoff.month
        for _ in range(max(0, int(months) - 1)):
            m -= 1
            if m < 1:
                m = 12
                y -= 1
        cutoff_s = f"{y:04d}-{m:02d}-01"
        rows = conn.execute(
            f"""
            SELECT period_start, period_end, visual_total, ledger_total,
                   clamped_ledger_total, variance_dollars, top_carrier_code,
                   scope_mismatch, result_code, created_at, package_build_id,
                   visual_total_cents, ledger_total_cents, clamped_ledger_total_cents,
                   variance_cents, money_cents_exact
            FROM {HISTORY_TABLE}
            WHERE created_at >= ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (cutoff_s, max(1, int(limit))),
        ).fetchall()
        out["rows"] = [
            {
                "periodStart": r[0],
                "periodEnd": r[1],
                # Legacy floats (deprecated for exact math)
                "visualTotal": r[2],
                "ledgerTotal": r[3],
                "clampedLedgerTotal": r[4],
                "varianceDollars": r[5],
                "topCarrierCode": r[6],
                "scopeMismatch": bool(r[7]),
                "resultCode": r[8],
                "createdAt": r[9],
                "packageBuildId": r[10],
                # HAL-10595 bijective cents
                "visualTotalCents": r[11],
                "ledgerTotalCents": r[12],
                "clampedLedgerTotalCents": r[13],
                "varianceCents": r[14],
                "moneyCentsExact": r[15],
                "totalCents": r[15] if r[15] is not None else r[12],
                "floatMoneyDeprecated": True,
            }
            for r in rows
        ]
        out["count"] = len(out["rows"])
        out["floatMoneyDeprecated"] = True
        return out
    finally:
        conn.close()


def reconcile_visual_vs_ledger(
    *,
    period: str | None = None,
    dest: Path | None = None,
    db_path: Path | None = None,
    abs_threshold: float = VARIANCE_THRESHOLD_ABSOLUTE,
    pct_threshold: float = VARIANCE_THRESHOLD_PERCENT,
    include_carrier_breakdown: bool = True,
) -> dict[str, Any]:
    """Reconcile visual audit to ledger; carrier breakdown + clamp on mismatch."""
    gold = audit_gold_payment_pipeline()
    selected, audit_start, audit_end, period_key = _select_visual_audit(
        period=period, dest=dest
    )
    requested_start, requested_end = (
        parse_date_range(period_key) if period_key else (None, None)
    )

    # Primary ledger window: requested period when provided, else audit bounds
    if requested_start and requested_end:
        ledger_start, ledger_end = requested_start, requested_end
    else:
        ledger_start, ledger_end = audit_start, audit_end

    scope_mismatch = False
    if (
        requested_start
        and requested_end
        and audit_start
        and audit_end
        and (audit_start, audit_end) != (requested_start, requested_end)
    ):
        scope_mismatch = True

    visual_raw = (selected or {}).get("lastPageAggregateTotal") if selected else None
    visual_honesty = enforce_empty_not_zero(
        visual_raw, source_tag=SOURCE_PRINT_PREVIEW_VISUAL
    )

    out: dict[str, Any] = {
        "ok": True,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "priorDef": PRIOR_DEF_ID,
        "period": period_key or (f"{audit_start}..{audit_end}" if audit_start else None),
        "periodStart": ledger_start,
        "periodEnd": ledger_end,
        "auditPeriodStart": audit_start,
        "auditPeriodEnd": audit_end,
        "requestedPeriodStart": requested_start,
        "requestedPeriodEnd": requested_end,
        "scopeMismatch": scope_mismatch,
        "visualAudit": selected,
        "visualTotal": visual_honesty.get("value"),
        "visualDisplay": visual_honesty.get("display"),
        "visualBadge": visual_honesty.get("badge"),
        "ledger": None,
        "ledgerTotal": None,
        "ledgerDisplay": "—",
        "clampedLedgerTotal": None,
        "clampedLedgerDisplay": "—",
        "carrierBreakdown": [],
        "topCarrierCode": None,
        "comparison": None,
        "gapCode": gold.get("gapCode"),
        "paymentLines": int(gold.get("paymentLines") or 0),
        "triggersGoldIngest": False,
        "emptyIsNotZero": True,
        "honesty": (
            "Visual audit vs ledger code-2 sum — flag variance; carrier codes only; "
            "never invent gold payment lines; empty != $0"
        ),
        "checkedAt": _utc_now(),
    }

    if not selected:
        out["comparison"] = classify_variance(None, None)
        out["comparison"]["result"] = ReconciliationResult.INSUFFICIENT_VISUAL.value
        out["comparison"]["message"] = "No Print Preview visual audit recorded yet"
        return out

    if not ledger_start or not ledger_end:
        out["comparison"] = classify_variance(
            visual_honesty.get("value"),
            None,
            abs_threshold=abs_threshold,
            pct_threshold=pct_threshold,
        )
        out["comparison"]["result"] = ReconciliationResult.INSUFFICIENT_VISUAL.value
        out["comparison"]["message"] = (
            "Cannot align ledger period — empty != $0"
        )
        return out

    if is_empty_money(visual_raw):
        out["comparison"] = classify_variance(
            None, None, abs_threshold=abs_threshold, pct_threshold=pct_threshold
        )
        return out

    ledger = sum_ledger_code2_payments(
        period_start=ledger_start, period_end=ledger_end, db_path=db_path
    )
    out["ledger"] = ledger
    ledger_honesty = enforce_empty_not_zero(
        ledger.get("ledgerTotal"), source_tag=SOURCE_LEDGER_SPINE
    )
    out["ledgerTotal"] = ledger_honesty.get("value")
    out["ledgerDisplay"] = ledger_honesty.get("display")

    # Clamp to audit bounds when scopes differ (narrower diagnostic window)
    if scope_mismatch and audit_start and audit_end:
        clamped = clamp_ledger_to_audit_period(
            audit_start=audit_start, audit_end=audit_end, db_path=db_path
        )
        out["clamp"] = clamped
        clamped_honesty = enforce_empty_not_zero(
            clamped.get("clampedLedgerTotal"), source_tag=SOURCE_LEDGER_SPINE
        )
        out["clampedLedgerTotal"] = clamped_honesty.get("value")
        out["clampedLedgerDisplay"] = clamped_honesty.get("display")

    if include_carrier_breakdown:
        carriers = sum_ledger_code2_by_carrier(
            period_start=ledger_start, period_end=ledger_end, db_path=db_path, limit=5
        )
        out["carrierBreakdown"] = carriers.get("carrierBreakdown") or []
        out["topCarrierCode"] = carriers.get("topCarrierCode")
        out["carrierBreakdownMeta"] = {
            "breakdownTotal": carriers.get("breakdownTotal"),
            "message": carriers.get("message"),
            "ok": carriers.get("ok"),
        }

    comparison = classify_variance(
        visual_honesty.get("value"),
        ledger_honesty.get("value"),
        abs_threshold=abs_threshold,
        pct_threshold=pct_threshold,
    )
    if scope_mismatch:
        comparison["scopeMismatch"] = True
        comparison["message"] = (
            str(comparison.get("message") or "")
            + " [scopeMismatch: clampedLedgerTotal uses audit dateRange]"
        ).strip()
    out["comparison"] = comparison
    out["thresholdViolated"] = bool(comparison.get("thresholdViolated"))
    out["result"] = comparison.get("result")
    # HAL-10595: bijective cents alongside deprecated floats
    out["visualTotalCents"] = _cents(out.get("visualTotal"))
    out["ledgerTotalCents"] = _cents(out.get("ledgerTotal"))
    out["clampedLedgerTotalCents"] = _cents(out.get("clampedLedgerTotal"))
    out["totalCents"] = out["ledgerTotalCents"]
    out["floatMoneyDeprecated"] = True
    return out


def migrate_history_to_exact(
    *,
    db_path: Path | None = None,
    dest: Path | None = None,
) -> dict[str, Any]:
    """Backfill *_cents / money_cents_exact from source Decimal — never from REAL.

    Recomputes ledger from sd_account_transactions for stored period bounds.
    Visual cents from matching Print Preview audits when available.
    PHI-safe; no SoftDent write-back; no gold invent.
    """
    path = Path(db_path) if db_path else resolve_analytics_db()
    out: dict[str, Any] = {
        "ok": False,
        "updated": 0,
        "skipped": 0,
        "errors": [],
        "triggersGoldIngest": False,
        "packageBuildId": PACKAGE_BUILD_ID,
        "def": DEF_ID,
    }
    if path is None or not Path(path).is_file():
        out["error"] = "analytics_db_missing"
        return out
    conn = sqlite3.connect(str(path), timeout=30.0)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        ensure_recon_variance_history_schema(conn)
        rows = conn.execute(
            f"""
            SELECT id, period_start, period_end, scope_mismatch,
                   visual_total_cents, ledger_total_cents
            FROM {HISTORY_TABLE}
            ORDER BY id ASC
            """
        ).fetchall()
        audits = list_print_preview_audits(dest=dest, limit=200)
        audit_rows = [r for r in (audits.get("rows") or []) if isinstance(r, dict)]
        conn.execute("BEGIN IMMEDIATE")
        updated = 0
        skipped = 0
        for row in rows:
            rid, p_start, p_end, scope_mm, vis_c, led_c = row
            if vis_c is not None and led_c is not None:
                skipped += 1
                continue
            if not p_start or not p_end:
                skipped += 1
                out["errors"].append(f"id={rid}:missing_period")
                continue
            ledger = sum_ledger_code2_payments(
                period_start=str(p_start), period_end=str(p_end), db_path=path
            )
            ledger_cents = ledger.get("ledgerTotalCents")
            visual_cents = None
            for ar in reversed(audit_rows):
                a_start, a_end = parse_date_range(str(ar.get("dateRange") or ""))
                if a_start == p_start and a_end == p_end:
                    visual_cents = _cents(ar.get("lastPageAggregateTotal"))
                    break
                if a_start and str(a_start)[:7] == str(p_start)[:7] and visual_cents is None:
                    visual_cents = _cents(ar.get("lastPageAggregateTotal"))
            clamped_cents = None
            if int(scope_mm or 0) == 1:
                # Clamp needs audit bounds; use matching audit if found
                for ar in reversed(audit_rows):
                    a_start, a_end = parse_date_range(str(ar.get("dateRange") or ""))
                    if a_start and a_end:
                        clamped = clamp_ledger_to_audit_period(
                            audit_start=a_start, audit_end=a_end, db_path=path
                        )
                        clamped_cents = clamped.get("clampedLedgerTotalCents")
                        break
            else:
                clamped_cents = ledger_cents
            variance_cents = None
            if visual_cents is not None and ledger_cents is not None:
                variance_cents = int(visual_cents) - int(ledger_cents)
            conn.execute(
                f"""
                UPDATE {HISTORY_TABLE}
                SET visual_total_cents = COALESCE(?, visual_total_cents),
                    ledger_total_cents = COALESCE(?, ledger_total_cents),
                    clamped_ledger_total_cents = COALESCE(?, clamped_ledger_total_cents),
                    variance_cents = COALESCE(?, variance_cents),
                    money_cents_exact = COALESCE(?, money_cents_exact)
                WHERE id = ?
                """,
                (
                    visual_cents,
                    ledger_cents,
                    clamped_cents,
                    variance_cents,
                    ledger_cents,
                    rid,
                ),
            )
            updated += 1
        conn.commit()
        out["ok"] = True
        out["updated"] = updated
        out["skipped"] = skipped
        return out
    except Exception as exc:  # noqa: BLE001
        try:
            conn.rollback()
        except Exception:
            pass
        out["error"] = f"{type(exc).__name__}:{exc}"
        return out
    finally:
        conn.close()


def run_ops_10593_visual_ledger_recon(
    *,
    period: str | None = None,
    dest: Path | None = None,
    db_path: Path | None = None,
    persist_history: bool = True,
    include_carrier_breakdown: bool = True,
) -> dict[str, Any]:
    """OPS runner: snapshot + optional history — never mutates SoftDent/gold."""
    recon = reconcile_visual_vs_ledger(
        period=period,
        dest=dest,
        db_path=db_path,
        include_carrier_breakdown=include_carrier_breakdown,
    )
    if persist_history and recon.get("visualTotal") is not None:
        recon["historyAppend"] = append_recon_variance_history(recon, db_path=db_path)
    try:
        exports = Path(dest) if dest else resolve_exports_dir()
        exports.mkdir(parents=True, exist_ok=True)
        path = exports / f"visual_ledger_recon_{datetime.now(timezone.utc).date().isoformat()}.json"
        path.write_text(json.dumps(recon, indent=2, default=str), encoding="utf-8")
        recon["jsonPath"] = str(path)
    except Exception as exc:  # noqa: BLE001
        recon["exportError"] = f"{type(exc).__name__}:{exc}"
    return recon


# Back-compat alias
run_ops_10592_visual_ledger_recon = run_ops_10593_visual_ledger_recon


def format_visual_ledger_recon_reply(result: dict[str, Any] | None = None) -> str:
    r = result if isinstance(result, dict) else reconcile_visual_vs_ledger()
    cmp_ = r.get("comparison") if isinstance(r.get("comparison"), dict) else {}
    v_disp = r.get("visualDisplay") or "—"
    if r.get("visualBadge") == "visual" and r.get("visualTotal") is not None:
        v_disp = f"[visual] {v_disp}"
    l_disp = r.get("ledgerDisplay") or "—"
    clamped = r.get("clampedLedgerDisplay") or "—"
    top = r.get("topCarrierCode") or "—"
    return (
        f"Visual×ledger recon ({DEF_ID}): result={cmp_.get('result') or r.get('result')}; "
        f"period={r.get('period')}; visual={v_disp}; ledger={l_disp}; "
        f"clamped={clamped}; topCarrier={top}; "
        f"delta={cmp_.get('delta')}; scopeMismatch={r.get('scopeMismatch')}; "
        f"thresholdViolated={cmp_.get('thresholdViolated')}; "
        f"gapCode={r.get('gapCode')}; paymentLines={r.get('paymentLines')}. "
        "Flag only — does not create gold lines. empty != $0."
    )


def visual_ledger_recon_widget() -> dict[str, Any]:
    r = reconcile_visual_vs_ledger()
    cmp_ = r.get("comparison") if isinstance(r.get("comparison"), dict) else {}
    result_code = str(cmp_.get("result") or r.get("result") or "")
    if result_code == ReconciliationResult.MATCH.value:
        status, tone = "ok", "ok"
    elif result_code == ReconciliationResult.VARIANCE_WITHIN_TOLERANCE.value:
        status, tone = "ok", "warn"
    elif result_code == ReconciliationResult.VARIANCE_EXCEEDS_THRESHOLD.value:
        status, tone = "warn", "danger"
    else:
        status, tone = "empty", "warn"
    message = str(cmp_.get("message") or r.get("honesty") or "No comparison yet")
    return {
        "id": "softdent-visual-ledger-recon",
        "type": "status",
        "label": "Visual×Ledger Variance (HAL-10595)",
        "size": "full",
        "status": status,
        "tone": tone,
        "message": message,
        "hint": (
            "Compares Print Preview Insurance Income to SoftDent code-2 ledger sum; "
            "exposes totalCents (exact) alongside deprecated float totals. Alert only."
        ),
        "result": result_code,
        "period": r.get("period"),
        "visualTotal": r.get("visualTotal"),
        "visualTotalCents": r.get("visualTotalCents"),
        "visualDisplay": r.get("visualDisplay"),
        "visualBadge": r.get("visualBadge"),
        "ledgerTotal": r.get("ledgerTotal"),
        "ledgerTotalCents": r.get("ledgerTotalCents"),
        "ledgerDisplay": r.get("ledgerDisplay"),
        "clampedLedgerTotal": r.get("clampedLedgerTotal"),
        "clampedLedgerTotalCents": r.get("clampedLedgerTotalCents"),
        "clampedLedgerDisplay": r.get("clampedLedgerDisplay"),
        "totalCents": r.get("totalCents"),
        "floatMoneyDeprecated": True,
        "carrierBreakdown": r.get("carrierBreakdown") or [],
        "topCarrierCode": r.get("topCarrierCode"),
        "delta": cmp_.get("delta"),
        "deltaCents": cmp_.get("deltaCents"),
        "thresholdViolated": cmp_.get("thresholdViolated"),
        "scopeMismatch": bool(r.get("scopeMismatch")),
        "gapCode": r.get("gapCode"),
        "paymentLines": r.get("paymentLines"),
        "confirmation": (
            "Variance flag only; no payment lines will be created"
        ),
        "halChips": [
            {"label": "Visual ledger recon status", "query": "visual ledger reconciliation status"},
            {
                "label": "What is visual vs ledger variance?",
                "query": "What does visual audit vs ledger reconciliation mean?",
            },
        ],
        "honesty": r.get("honesty"),
        "emptyIsNotZero": True,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "triggersGoldIngest": False,
        "ok": True,
    }


if __name__ == "__main__":
    print(json.dumps(run_ops_10593_visual_ledger_recon(), indent=2, default=str)[:6000])
