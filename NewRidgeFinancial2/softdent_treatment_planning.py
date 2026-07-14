"""SoftDent insurance payment lines + ADA crosswalk → PHI-safe treatment planning estimates.

Moonshot consult: MOONSHOT_SOFTDENT_ADA_PAYER_TX_CONSULT_2026-07-10.md

- Ingests ``insurance_payments*.csv`` → ``sd_insurance_payment_lines``
- Ingests ``procedure_codes*.csv`` → ``sd_procedure_code_reference``
- Rebuilds ``treatment_planning_estimates`` (InsCo × ADA averages, no PHI)
- HAL queries via ``lookup_treatment_estimate`` / ``format_treatment_estimate_reply``

Does not invent dollars. Missing CSVs → empty ingest, honest HAL replies.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

MIN_SAMPLE_SIZE = 10
GENERIC_PAYERS = frozenset({"insurance", "ins", "payer", "carrier", "unknown", ""})

_PAYMENT_GLOBS = (
    "insurance_payments*.csv",
    "insurance_payment_analysis*.csv",
    "insurance_payment_distribution*.csv",
    "InsurancePayment*.csv",
    "Insurance*Payment*Analysis*.csv",
    "*Payment*Analysis*.csv",
)
_CODE_GLOBS = (
    "procedure_codes*.csv",
    "procedure_code*.csv",
    "procedure_code_listing*.csv",
    "ProcedureCode*.csv",
    "ada_codes*.csv",
)

_PAYMENT_COLMAP: dict[str, tuple[str, ...]] = {
    "insurance_company": (
        "Insurance Company",
        "InsuranceCompany",
        "InsCo",
        "Payer",
        "Carrier",
        "Company",
        "insurance_company",
    ),
    "ada_code": (
        "Procedure Code",
        "ProcedureCode",
        "ADA Code",
        "ADACode",
        "CDT",
        "Code",
        "ProcCode",
        "ada_code",
    ),
    "description": (
        "Procedure Description",
        "Description",
        "ProcDesc",
        "ADA Description",
    ),
    "submitted_fee": (
        "Submitted Fee",
        "Submitted",
        "Fee",
        "Billed",
        "Charge",
        "SubmittedAmount",
        "Service Amount",
    ),
    "allowed_amount": (
        "Allowed Amount",
        "Allowed",
        "Allowable",
        "AllowedFee",
        "Contracted",
    ),
    "paid_amount": (
        "Paid Amount",
        "Paid",
        "Payment",
        "Ins Paid",
        "Insurance Paid",
        "PaymentAmount",
        "InsPayment",
    ),
    "write_off_amount": (
        "Write-Off Amount",
        "Write-Off",
        "WriteOff",
        "Write Off",
        "Adjustment",
        "CO-45",
        "CO45",
        "Contractual Adjustment",
    ),
    "patient_portion": (
        "Patient Portion",
        "Patient Resp",
        "Patient Responsibility",
        "PatientBalance",
        "Balance",
        "Patient Amount",
    ),
    "claim_number": (
        "Claim Number",
        "ClaimNumber",
        "Claim #",
        "ClaimId",
        "Claim ID",
        "claim_id",
    ),
    "check_number": (
        "Check Number",
        "CheckNumber",
        "Check #",
        "Check",
        "EFT",
        "Reference",
    ),
    "payment_date": (
        "Payment Date",
        "Deposit Date",
        "Date",
        "Posting Date",
        "Service Date",
    ),
}

_CODE_COLMAP: dict[str, tuple[str, ...]] = {
    "internal_code": (
        "Internal Code",
        "InternalCode",
        "SoftDent Code",
        "SD Code",
        "Code",
        "ProcCode",
        "Procedure Code",
    ),
    "ada_cdt_code": (
        "ADA Code",
        "ADACode",
        "CDT",
        "CDT Code",
        "ADA/CDT",
        "Official Code",
        "ada_code",
    ),
    "description": ("Description", "ProcDesc", "Procedure Description", "Name"),
    "ucr_fee": ("UCR Fee", "UCR", "Fee", "Office Fee", "Amount"),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_exports_dir() -> Path:
    configured = os.environ.get("SOFTDENT_FINANCIAL_EXPORTS", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path(r"C:\SoftDentFinancialExports")


def resolve_analytics_db() -> Path | None:
    try:
        from softdent_transaction_extract import resolve_analytics_db as _resolve

        return _resolve()
    except Exception:
        default = resolve_exports_dir() / "softdent_financial_analytics.db"
        return default if default.is_file() else None


def parse_money(value: Any) -> float | None:
    """Parse money via Decimal (cent-quantized); return float for SQLite REAL storage.

    Never invents 0 from blank. Rejects NaN/Inf. Accounting parentheses → negative.
    CSV string zeros (e.g. Paid Amount 0.00) are kept as 0.0 (observed zero).
    """
    from money_cents import money_as_sqlite_real, to_money_from_csv

    return money_as_sqlite_real(to_money_from_csv(value))


def normalize_ada_code(raw: Any) -> str:
    """Normalize to canonical D#### when possible; keep SoftDent internal otherwise."""
    text = str(raw or "").strip().upper().replace(" ", "")
    if not text:
        return ""
    if re.fullmatch(r"D\d{4}", text):
        return text
    if re.fullmatch(r"D\d{4}\.\d+", text):
        return text.split(".", 1)[0]
    # Bare 4-digit CDT
    if re.fullmatch(r"\d{4}", text):
        return f"D{text}"
    # SoftDent internal often = CDT * 100 (111000 → D1110, 12000 → D0120)
    if text.isdigit() and len(text) >= 4:
        try:
            n = int(text)
            if n % 100 == 0:
                cdt = n // 100
                if 0 < cdt < 10000:
                    return f"D{cdt:04d}"
        except ValueError:
            pass
    return text


def _pick(row: dict[str, Any], field_lookup: dict[str, str], aliases: tuple[str, ...]) -> str:
    for alias in aliases:
        src = field_lookup.get(alias.lower())
        if src and row.get(src) not in (None, ""):
            return str(row.get(src) or "").strip()
    return ""


def _sha(*parts: Any) -> str:
    payload = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()[:32]


def _search_roots(extra: Path | None = None) -> list[Path]:
    roots: list[Path] = []
    if extra is not None:
        roots.append(extra)
    roots.append(resolve_exports_dir())
    try:
        from softdent_practice_exports import softdent_import_dir

        roots.append(softdent_import_dir())
    except Exception:
        pass
    report = Path(r"C:\SoftDentReportExports")
    if report.is_dir():
        roots.append(report)
    # de-dupe preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for r in roots:
        key = str(r.resolve()) if r.exists() else str(r)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def find_newest_csv(globs: tuple[str, ...], *, search_dir: Path | None = None) -> Path | None:
    candidates: list[Path] = []
    for root in _search_roots(search_dir):
        if not root.is_dir():
            continue
        for pattern in globs:
            candidates.extend(root.glob(pattern))
            # HAL-10588: recursive drop folders / nested SoftDent exports
            candidates.extend(root.rglob(pattern))
    files = [p for p in candidates if p.is_file()]
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def ensure_treatment_planning_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sd_insurance_payment_lines (
            line_id TEXT PRIMARY KEY,
            insurance_company TEXT,
            ada_code TEXT,
            description TEXT,
            submitted_fee REAL,
            allowed_amount REAL,
            paid_amount REAL,
            write_off_amount REAL,
            patient_portion REAL,
            claim_number TEXT,
            check_number TEXT,
            payment_date TEXT,
            source_file TEXT,
            extracted_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_sd_ins_pay_payer ON sd_insurance_payment_lines(insurance_company);
        CREATE INDEX IF NOT EXISTS idx_sd_ins_pay_ada ON sd_insurance_payment_lines(ada_code);

        CREATE TABLE IF NOT EXISTS sd_procedure_code_reference (
            internal_code TEXT PRIMARY KEY,
            ada_cdt_code TEXT,
            description TEXT,
            ucr_fee REAL,
            source_file TEXT,
            extracted_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_sd_proc_ref_ada ON sd_procedure_code_reference(ada_cdt_code);

        CREATE TABLE IF NOT EXISTS treatment_planning_estimates (
            insurance_company TEXT NOT NULL,
            ada_code TEXT NOT NULL,
            submitted_fee_avg REAL,
            allowed_amount_avg REAL,
            paid_amount_avg REAL,
            write_off_avg REAL,
            patient_portion_avg REAL,
            sample_size INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT,
            PRIMARY KEY (insurance_company, ada_code)
        );

        CREATE TABLE IF NOT EXISTS sd_insurance_payment_ingest_audit (
            ingest_id TEXT PRIMARY KEY,
            source_file TEXT NOT NULL,
            extracted_at TEXT NOT NULL,
            rows_accepted INTEGER NOT NULL DEFAULT 0,
            rows_skipped_incomplete INTEGER NOT NULL DEFAULT 0,
            paid_sum REAL,
            prior_row_count INTEGER,
            note TEXT
        );
        """
    )


def ingest_insurance_payment_csv(
    path: Path,
    conn: sqlite3.Connection,
    *,
    extracted_at: str | None = None,
) -> int:
    from decimal import Decimal

    from money_cents import money_as_sqlite_real, money_sub, to_money_from_csv

    extracted_at = extracted_at or _utc_now()
    ensure_treatment_planning_schema(conn)
    rows: list[dict[str, Any]] = []
    skipped_incomplete = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return 0
        field_lookup = {str(f).strip().lower(): str(f) for f in reader.fieldnames if f}
        for idx, raw in enumerate(reader):
            company = _pick(raw, field_lookup, _PAYMENT_COLMAP["insurance_company"])
            ada_raw = _pick(raw, field_lookup, _PAYMENT_COLMAP["ada_code"])
            ada = normalize_ada_code(ada_raw)
            submitted_d = to_money_from_csv(_pick(raw, field_lookup, _PAYMENT_COLMAP["submitted_fee"]))
            allowed_d = to_money_from_csv(_pick(raw, field_lookup, _PAYMENT_COLMAP["allowed_amount"]))
            paid_d = to_money_from_csv(_pick(raw, field_lookup, _PAYMENT_COLMAP["paid_amount"]))
            write_off_d = to_money_from_csv(
                _pick(raw, field_lookup, _PAYMENT_COLMAP["write_off_amount"])
            )
            patient_d = to_money_from_csv(_pick(raw, field_lookup, _PAYMENT_COLMAP["patient_portion"]))
            claim = _pick(raw, field_lookup, _PAYMENT_COLMAP["claim_number"])
            check = _pick(raw, field_lookup, _PAYMENT_COLMAP["check_number"])
            pay_date = _pick(raw, field_lookup, _PAYMENT_COLMAP["payment_date"])
            desc = _pick(raw, field_lookup, _PAYMENT_COLMAP["description"])
            # Skip blank CSV noise
            if not company and not ada and paid_d is None and submitted_d is None:
                continue
            # Gold line requires InsCo + ADA + Paid (observed; may be 0.00)
            if not company or not ada or paid_d is None:
                skipped_incomplete += 1
                continue
            # Derive patient portion when missing but allowed+paid present (cent-exact)
            if patient_d is None and allowed_d is not None and paid_d is not None:
                patient_d = money_sub(allowed_d, paid_d)
            submitted = money_as_sqlite_real(submitted_d)
            allowed = money_as_sqlite_real(allowed_d)
            paid = money_as_sqlite_real(paid_d)
            write_off = money_as_sqlite_real(write_off_d)
            patient = money_as_sqlite_real(patient_d)
            line_id = _sha(company, ada, claim, check, pay_date, paid, submitted, path.name, idx)
            rows.append(
                {
                    "line_id": line_id,
                    "insurance_company": company,
                    "ada_code": ada,
                    "description": desc,
                    "submitted_fee": submitted,
                    "allowed_amount": allowed,
                    "paid_amount": paid,
                    "write_off_amount": write_off,
                    "patient_portion": patient,
                    "claim_number": claim,
                    "check_number": check,
                    "payment_date": pay_date,
                    "source_file": path.name,
                    "extracted_at": extracted_at,
                }
            )
    if not rows:
        return 0

    # Atomic replace: avoid empty-table window for concurrent Sync/readers
    prior_count = 0
    try:
        prior_count = int(
            conn.execute("SELECT COUNT(*) FROM sd_insurance_payment_lines").fetchone()[0] or 0
        )
    except sqlite3.Error:
        prior_count = 0

    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("DELETE FROM sd_insurance_payment_lines")
        conn.executemany(
            """
            INSERT INTO sd_insurance_payment_lines (
                line_id, insurance_company, ada_code, description, submitted_fee, allowed_amount,
                paid_amount, write_off_amount, patient_portion, claim_number, check_number,
                payment_date, source_file, extracted_at
            ) VALUES (
                :line_id, :insurance_company, :ada_code, :description, :submitted_fee, :allowed_amount,
                :paid_amount, :write_off_amount, :patient_portion, :claim_number, :check_number,
                :payment_date, :source_file, :extracted_at
            )
            """,
            rows,
        )
        paid_sum = sum(
            (to_money_from_csv(r["paid_amount"]) or Decimal("0.00") for r in rows),
            Decimal("0.00"),
        )
        conn.execute(
            """
            INSERT INTO sd_insurance_payment_ingest_audit (
                ingest_id, source_file, extracted_at, rows_accepted, rows_skipped_incomplete,
                paid_sum, prior_row_count, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _sha("ingest", path.name, extracted_at, len(rows)),
                path.name,
                extracted_at,
                len(rows),
                skipped_incomplete,
                float(paid_sum),
                prior_count,
                "full replace of sd_insurance_payment_lines; empty != invent",
            ),
        )
        _rollup_into_importer_aggregate(conn, rows, path.name, extracted_at)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return len(rows)


def _rollup_into_importer_aggregate(
    conn: sqlite3.Connection,
    rows: list[dict[str, Any]],
    source_file: str,
    extracted_at: str,
) -> None:
    """Optionally hydrate empty importer-owned insurance_payment_distribution from line rollups."""
    try:
        cols = {r[1] for r in conn.execute("pragma table_info(insurance_payment_distribution)")}
    except sqlite3.Error:
        return
    required = {"business_key", "insurance_company", "payment_amount", "source_file", "imported_at_utc"}
    if not required.issubset(cols):
        return
    cur = conn.execute("SELECT COUNT(*) FROM insurance_payment_distribution")
    if int(cur.fetchone()[0] or 0) > 0:
        return  # do not overwrite existing importer data
    by_co: dict[str, dict[str, float | int]] = {}
    for row in rows:
        co = str(row.get("insurance_company") or "").strip() or "Unknown"
        bucket = by_co.setdefault(co, {"payment_amount": 0.0, "claim_count": 0})
        paid = row.get("paid_amount")
        if paid is not None:
            bucket["payment_amount"] = float(bucket["payment_amount"]) + float(paid)
        bucket["claim_count"] = int(bucket["claim_count"]) + 1
    for co, stats in by_co.items():
        key = _sha("rollup", co, source_file)
        conn.execute(
            """
            INSERT INTO insurance_payment_distribution (
                row_sha256, business_key, report_date, payment_type, payment_amount,
                insurance_company, claim_count, deposit_date, source_file, imported_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                key,
                extracted_at[:10],
                "line_rollup",
                float(stats["payment_amount"]),
                co,
                int(stats["claim_count"]),
                None,
                source_file,
                extracted_at,
            ),
        )


def ingest_procedure_code_csv(
    path: Path,
    conn: sqlite3.Connection,
    *,
    extracted_at: str | None = None,
) -> int:
    extracted_at = extracted_at or _utc_now()
    ensure_treatment_planning_schema(conn)
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return 0
        field_lookup = {str(f).strip().lower(): str(f) for f in reader.fieldnames if f}
        for raw in reader:
            internal = _pick(raw, field_lookup, _CODE_COLMAP["internal_code"])
            ada = normalize_ada_code(_pick(raw, field_lookup, _CODE_COLMAP["ada_cdt_code"]))
            if not ada and internal:
                ada = normalize_ada_code(internal)
            if not internal and ada:
                internal = ada
            if not internal:
                continue
            rows.append(
                {
                    "internal_code": internal,
                    "ada_cdt_code": ada,
                    "description": _pick(raw, field_lookup, _CODE_COLMAP["description"]),
                    "ucr_fee": parse_money(_pick(raw, field_lookup, _CODE_COLMAP["ucr_fee"])),
                    "source_file": path.name,
                    "extracted_at": extracted_at,
                }
            )
    if not rows:
        return 0
    conn.execute("DELETE FROM sd_procedure_code_reference")
    conn.executemany(
        """
        INSERT OR REPLACE INTO sd_procedure_code_reference (
            internal_code, ada_cdt_code, description, ucr_fee, source_file, extracted_at
        ) VALUES (
            :internal_code, :ada_cdt_code, :description, :ucr_fee, :source_file, :extracted_at
        )
        """,
        rows,
    )
    return len(rows)


def rebuild_treatment_planning_estimates(conn: sqlite3.Connection) -> int:
    """Aggregate InsCo × ADA averages. Skips generic 'Insurance' payers. No PHI columns."""
    ensure_treatment_planning_schema(conn)
    updated_at = _utc_now()
    conn.execute("DELETE FROM treatment_planning_estimates")
    # Prefer crosswalk when line ada_code still looks internal
    sql = """
        INSERT INTO treatment_planning_estimates (
            insurance_company, ada_code,
            submitted_fee_avg, allowed_amount_avg, paid_amount_avg, write_off_avg,
            patient_portion_avg, sample_size, updated_at
        )
        SELECT
            trim(l.insurance_company) AS insurance_company,
            CASE
                WHEN upper(trim(l.ada_code)) LIKE 'D____' THEN upper(trim(l.ada_code))
                WHEN r.ada_cdt_code IS NOT NULL AND trim(r.ada_cdt_code) != '' THEN upper(trim(r.ada_cdt_code))
                ELSE upper(trim(l.ada_code))
            END AS ada_code,
            AVG(l.submitted_fee),
            AVG(l.allowed_amount),
            AVG(l.paid_amount),
            AVG(l.write_off_amount),
            AVG(l.patient_portion),
            COUNT(*),
            ?
        FROM sd_insurance_payment_lines l
        LEFT JOIN sd_procedure_code_reference r
            ON trim(r.internal_code) = trim(l.ada_code)
        WHERE trim(coalesce(l.insurance_company, '')) != ''
          AND lower(trim(l.insurance_company)) NOT IN ('insurance', 'ins', 'payer', 'carrier', 'unknown')
          AND trim(coalesce(l.ada_code, '')) != ''
        GROUP BY 1, 2
        HAVING COUNT(*) >= 1
    """
    conn.execute(sql, (updated_at,))
    cur = conn.execute("SELECT COUNT(*) FROM treatment_planning_estimates")
    return int(cur.fetchone()[0] or 0)


def run_treatment_planning_ingest(
    *,
    search_dir: Path | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Find newest payment + procedure CSVs, ingest, rebuild estimates."""
    db_path = db_path or resolve_analytics_db()
    result: dict[str, Any] = {
        "ok": False,
        "db": str(db_path) if db_path else None,
        "paymentFile": None,
        "procedureFile": None,
        "paymentLines": 0,
        "procedureCodes": 0,
        "estimates": 0,
        "warnings": [],
        "extractedAt": _utc_now(),
    }
    if not db_path or not Path(db_path).is_file():
        result["warnings"].append("Analytics DB missing — cannot ingest treatment-planning CSVs.")
        return result

    pay_path = find_newest_csv(_PAYMENT_GLOBS, search_dir=search_dir)
    code_path = find_newest_csv(_CODE_GLOBS, search_dir=search_dir)
    result["paymentFile"] = str(pay_path) if pay_path else None
    result["procedureFile"] = str(code_path) if code_path else None

    conn = sqlite3.connect(str(db_path))
    try:
        ensure_treatment_planning_schema(conn)
        if pay_path:
            result["paymentLines"] = ingest_insurance_payment_csv(pay_path, conn, extracted_at=result["extractedAt"])
        else:
            result["warnings"].append(
                "No insurance_payments*.csv found — export SoftDent Insurance Payment Analysis to "
                r"C:\SoftDentFinancialExports\insurance_payments_YYYYMMDD.csv"
            )
        if code_path:
            result["procedureCodes"] = ingest_procedure_code_csv(code_path, conn, extracted_at=result["extractedAt"])
        else:
            result["warnings"].append(
                "No procedure_codes*.csv found — optional SoftDent Procedure Code Listing crosswalk."
            )
        result["estimates"] = rebuild_treatment_planning_estimates(conn)
        try:
            from softdent_settlement_matrix import hydrate_settlement_matrix

            matrix = hydrate_settlement_matrix(db_path=Path(db_path), conn=conn)
            result["settlementMatrix"] = {
                "matrixCells": matrix.get("matrixCells"),
                "cellsNge10": matrix.get("cellsNge10"),
                "gapCode": matrix.get("gapCode"),
            }
        except Exception as mx_exc:  # noqa: BLE001
            result.setdefault("warnings", []).append(
                f"settlement_matrix hydrate: {type(mx_exc).__name__}:{mx_exc}"
            )
        conn.commit()
        result["ok"] = True
    except Exception as exc:  # noqa: BLE001
        result["warnings"].append(str(exc))
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()
    return result


def _normalize_payer_query(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def lookup_treatment_estimate(
    *,
    payer: str,
    ada_code: str,
    db_path: Path | None = None,
    min_sample: int = MIN_SAMPLE_SIZE,
) -> dict[str, Any]:
    """Lookup PHI-safe aggregate for payer × ADA. Never invents amounts."""
    ada = normalize_ada_code(ada_code)
    payer_q = _normalize_payer_query(payer)
    out: dict[str, Any] = {
        "ok": False,
        "found": False,
        "sufficient": False,
        "payer": payer.strip(),
        "adaCode": ada,
        "minSample": min_sample,
        "sampleSize": 0,
        "estimate": None,
        "honesty": (
            "Estimate from historical SoftDent insurance payment lines only — "
            "not a guarantee of benefits. Verify deductible, annual max, and plan limits."
        ),
    }
    db_path = db_path or resolve_analytics_db()
    if not db_path or not Path(db_path).is_file():
        out["message"] = "Analytics DB unavailable."
        return out
    if not ada or not payer_q or payer_q in GENERIC_PAYERS:
        out["message"] = "Need a specific insurance company and ADA/CDT code (e.g. Delta Dental + D0274)."
        return out

    # HAL-10605: viaGold (settlement_matrix) before gold estimates / alias / ledger
    try:
        from softdent_settlement_matrix import lookup_settlement_matrix

        gold_cell = lookup_settlement_matrix(
            payer=payer, ada_code=ada, db_path=Path(db_path), min_sample=min_sample
        )
    except Exception as exc:  # noqa: BLE001
        gold_cell = {"found": False, "error": f"{type(exc).__name__}:{exc}"}

    if gold_cell.get("blockedPending"):
        # Fall through to alias pending handler below via normal path
        pass
    elif gold_cell.get("found"):
        n = int(gold_cell.get("sampleSize") or 0)
        sufficient = bool(gold_cell.get("sufficient"))
        estimate = {
            "insuranceCompany": payer.strip(),
            "adaCode": ada,
            "submittedFeeAvg": None,
            "allowedAmountAvg": None,
            "paidAmountAvg": gold_cell.get("avgPaid"),
            "writeOffAvg": None,
            "patientPortionAvg": None,
            "sampleSize": n,
            "updatedAt": gold_cell.get("lastUpdated"),
            "source": "viaGold",
            "credibility": "gold" if sufficient else "insufficient",
            "tier": "exact",
            "isInferred": False,
            "goldAvailable": True,
            "spineCarrierName": gold_cell.get("spineCarrierName"),
            "stdDev": gold_cell.get("stdDev"),
            "viaAlias": bool(gold_cell.get("viaAlias")),
        }
        out.update(
            {
                "ok": True,
                "found": True,
                "sampleSize": n,
                "estimate": estimate,
                "source": "viaGold",
                "viaGold": True,
                "viaAlias": bool(gold_cell.get("viaAlias")),
                "spineCarrierName": gold_cell.get("spineCarrierName"),
                "sufficient": sufficient,
                "credibility": estimate["credibility"],
                "tier": "exact",
                "emptyIsNotZero": True,
                "def": "HAL-10605",
                "honesty": (
                    "Estimate from SoftDent gold payment lines (settlement_matrix). "
                    "Not a guarantee of benefits. empty != $0."
                ),
            }
        )
        if not sufficient:
            out["message"] = (
                f"Only {n} gold payment line(s) for "
                f"{gold_cell.get('spineCarrierName') or payer} × {ada} "
                f"(need >={min_sample}). empty != $0."
            )
        out["chip"] = build_tp_estimate_chip(out)
        return out

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        ensure_treatment_planning_schema(conn)
        # Exact then fuzzy payer match
        row = conn.execute(
            """
            SELECT * FROM treatment_planning_estimates
            WHERE upper(ada_code) = upper(?)
              AND lower(insurance_company) = ?
            LIMIT 1
            """,
            (ada, payer_q),
        ).fetchone()
        if row is None:
            row = conn.execute(
                """
                SELECT * FROM treatment_planning_estimates
                WHERE upper(ada_code) = upper(?)
                  AND lower(insurance_company) LIKE ?
                ORDER BY sample_size DESC
                LIMIT 1
                """,
                (ada, f"%{payer_q}%"),
            ).fetchone()
        if row is None:
            # Gold path empty for this InsCo×ADA — fall through to unified ledger spine
            pass
        else:
            sample = int(row["sample_size"] or 0)
            estimate = {
                "insuranceCompany": row["insurance_company"],
                "adaCode": row["ada_code"],
                "submittedFeeAvg": row["submitted_fee_avg"],
                "allowedAmountAvg": row["allowed_amount_avg"],
                "paidAmountAvg": row["paid_amount_avg"],
                "writeOffAvg": row["write_off_avg"],
                "patientPortionAvg": row["patient_portion_avg"],
                "sampleSize": sample,
                "updatedAt": row["updated_at"],
                "source": "viaGold",
                "credibility": "gold" if sample >= min_sample else "insufficient",
                "tier": "exact",
                "isInferred": False,
                "goldAvailable": True,
            }
            out["ok"] = True
            out["found"] = True
            out["sampleSize"] = sample
            out["estimate"] = estimate
            out["source"] = "viaGold"
            out["viaGold"] = True
            out["sufficient"] = sample >= min_sample
            out["credibility"] = estimate["credibility"]
            out["tier"] = "exact"
            out["emptyIsNotZero"] = True
            out["chip"] = build_tp_estimate_chip(out)
            out["def"] = "HAL-10605"
            if not out["sufficient"]:
                out["message"] = (
                    f"Only {sample} historical line(s) for {estimate['insuranceCompany']} × {ada} "
                    f"(need >={min_sample} for a reliable estimate). Contact payer for pre-auth / benefits."
                )
            return out
    finally:
        conn.close()

    # HAL-10601: resolve accepted carrier_alias before spine fallback.
    # Pending manuals never auto-resolve.
    alias_meta: dict[str, Any] = {}
    try:
        from softdent_carrier_alias import resolve_accepted_alias_for_tp

        alias_meta = resolve_accepted_alias_for_tp(payer, db_path=Path(db_path))
    except Exception as exc:  # noqa: BLE001
        alias_meta = {"viaAlias": False, "resolveError": f"{type(exc).__name__}:{exc}"}

    if alias_meta.get("blockedPending"):
        pend = alias_meta.get("pending") if isinstance(alias_meta.get("pending"), dict) else {}
        blocked = {
            "ok": True,
            "found": True,
            "sufficient": False,
            "payer": payer.strip(),
            "adaCode": ada,
            "minSample": min_sample,
            "sampleSize": 0,
            "estimate": {
                "insuranceCompany": payer.strip(),
                "adaCode": ada,
                "submittedFeeAvg": None,
                "allowedAmountAvg": None,
                "paidAmountAvg": None,
                "writeOffAvg": None,
                "patientPortionAvg": None,
                "sampleSize": 0,
                "credibility": "insufficient",
                "tier": None,
                "source": "carrier_alias_pending",
                "goldAvailable": False,
                "masterCompanyId": alias_meta.get("masterCompanyId"),
                "spineCarrierName": alias_meta.get("spineCarrierName"),
                "pendingAlias": True,
            },
            "credibility": "insufficient",
            "source": "carrier_alias_pending",
            "viaAlias": False,
            "blockedPending": True,
            "pendingAlias": pend,
            "tpCodeUsesCarrierAlias": True,
            "emptyIsNotZero": True,
            "message": (
                f"Carrier alias for {payer.strip()} is pending HAL review "
                f"(proposed spine={alias_meta.get('spineCarrierName') or '?'}). "
                "Not auto-resolved — empty != $0. "
                "Confirm with: python scripts/reconcile_carrier_aliases.py "
                f"--accept-pending \"{payer.strip()}\""
            ),
            "honesty": (
                "Pending carrier aliases never auto-resolve into treatment estimates. "
                "empty != $0."
            ),
            "def": "HAL-10601",
        }
        blocked["chip"] = build_tp_estimate_chip(blocked)
        return blocked

    spine_payer = str(alias_meta.get("spineCarrierName") or payer)
    result = _ledger_spine_treatment_fallback(
        payer=spine_payer,
        ada_code=ada,
        db_path=Path(db_path),
        include_inferred=False,
    )
    result["tpCodeUsesCarrierAlias"] = True
    result["emptyIsNotZero"] = True
    result["def"] = "HAL-10601"
    if alias_meta.get("viaAlias"):
        result["viaAlias"] = True
        result["masterCompanyId"] = alias_meta.get("masterCompanyId")
        result["spineCarrierName"] = alias_meta.get("spineCarrierName")
        result["payer"] = payer.strip()
        if result.get("found"):
            result["source"] = "ledger_episode_5yr_via_alias"
            est = result.get("estimate") if isinstance(result.get("estimate"), dict) else None
            if est is not None:
                est["source"] = "ledger_episode_5yr_via_alias"
                est["insuranceCompany"] = payer.strip()
                est["spineCarrierName"] = alias_meta.get("spineCarrierName")
                est["masterCompanyId"] = alias_meta.get("masterCompanyId")
                result["estimate"] = est
            result["honesty"] = (
                "Estimate from SoftDent ledger episodes via accepted carrier alias "
                f"({payer.strip()} → {alias_meta.get('spineCarrierName')}). "
                "Not a guarantee of benefits. empty != $0."
            )
    else:
        result["viaAlias"] = False
    result["chip"] = build_tp_estimate_chip(result)
    return result


def build_tp_estimate_chip(result: dict[str, Any] | None) -> dict[str, Any]:
    """Staff-facing TP estimate chip (HAL-10587). Never invents $0 for empty."""
    r = result if isinstance(result, dict) else {}
    est = r.get("estimate") if isinstance(r.get("estimate"), dict) else {}
    cred = str(est.get("credibility") or r.get("credibility") or "insufficient")
    tier = str(est.get("tier") or r.get("tier") or "")
    n = int(est.get("sampleSize") or r.get("sampleSize") or 0)
    source = str(est.get("source") or r.get("source") or "")
    ada = str(est.get("adaCode") or r.get("adaCode") or "")
    payer = str(est.get("insuranceCompany") or r.get("payer") or "")
    paid = est.get("paidAmountAvg")
    wo = est.get("writeOffAvg")
    pay_pct = est.get("paidPctMedian")
    pay_sd = est.get("paidPctStdev")

    if not r.get("ok"):
        return {
            "badge": "error",
            "label": "Unavailable",
            "tone": "danger",
            "display": str(r.get("message") or "Estimate unavailable"),
            "showDollars": False,
            "emptyIsNotZero": True,
        }
    if not r.get("found") or cred == "insufficient" or (
        not r.get("sufficient") and source in ("gold_payment_lines", "viaGold")
    ) or (
        not r.get("sufficient")
        and n < 10
        and tier == "exact"
        and source not in ("gold_payment_lines", "viaGold")
    ):
        # Honest insufficient — never show $0.00 as a fake estimate
        if source in ("gold_payment_lines", "viaGold") and r.get("found") and n > 0:
            display = str(
                r.get("message")
                or (
                    f"Only {n} historical line(s) for {payer or '?'} × {ada or '?'} "
                    f"(need >=10 for a reliable estimate). Contact payer for pre-auth / benefits."
                )
            )
        else:
            display = (
                f"No credible data for {payer or '?'} × {ada or '?'} "
                f"(n={n}). empty != $0 — verify with payer."
            )
        return {
            "badge": "insufficient",
            "label": "Insufficient data",
            "tone": "muted",
            "display": display,
            "showDollars": False,
            "paidMedian": None,
            "writeOffMedian": None,
            "sampleSize": n,
            "credibility": "insufficient" if cred != "gold" else "insufficient",
            "tier": tier or None,
            "source": source or None,
            "emptyIsNotZero": True,
            "adaCode": ada,
            "insuranceCompany": payer,
            "masterCompanyId": est.get("masterCompanyId") or r.get("masterCompanyId"),
            "spineCarrierName": est.get("spineCarrierName") or r.get("spineCarrierName"),
            "viaAlias": bool(r.get("viaAlias") or source == "ledger_episode_5yr_via_alias"),
        }

    if cred == "high":
        badge, label, tone = "high", "Exact high", "ok"
    elif cred == "usable":
        badge, label, tone = "usable", "Exact usable", "warn"
    elif "inferred" in cred or tier == "inferred":
        badge, label, tone = "inferred", "Inferred", "danger"
    elif cred == "gold":
        badge, label, tone = "gold", "Payment lines", "ok"
    else:
        badge, label, tone = cred or "published", "Published", "warn"

    variance = None
    if pay_pct is not None:
        variance = f"pay% {pay_pct}"
        if pay_sd is not None:
            variance += f" +/-{pay_sd}"

    # Never show dollars when paid avg is empty (HON-001)
    paid_txt = _fmt_money(paid, source_tag=source or "ledger_episode_5yr")
    if paid is None or paid_txt in {"unknown", "—", "No data"}:
        return {
            "badge": "insufficient",
            "label": "Insufficient data",
            "tone": "muted",
            "display": (
                f"No dollar estimate for {payer or '?'} × {ada or '?'} "
                f"(n={n}). empty != $0 — verify with payer."
            ),
            "showDollars": False,
            "paidMedian": None,
            "writeOffMedian": None,
            "sampleSize": n,
            "credibility": "insufficient",
            "tier": tier or None,
            "source": source or None,
            "emptyIsNotZero": True,
            "adaCode": ada,
            "insuranceCompany": payer,
            "masterCompanyId": est.get("masterCompanyId") or r.get("masterCompanyId"),
            "spineCarrierName": est.get("spineCarrierName") or r.get("spineCarrierName"),
            "viaAlias": bool(r.get("viaAlias") or source == "ledger_episode_5yr_via_alias"),
            "honestyDef": "HAL-10591",
        }

    display_bits = [paid_txt]
    if wo is not None:
        display_bits.append(f"WO {_fmt_money(wo, source_tag=source or 'ledger_episode_5yr')}")
    if variance:
        display_bits.append(f"({variance})")
    display_bits.append(f"n={n}")

    return {
        "badge": badge,
        "label": label,
        "tone": tone,
        "display": " · ".join(display_bits),
        "showDollars": True,
        "paidMedian": paid,
        "writeOffMedian": wo,
        "paidPctMedian": pay_pct,
        "paidPctStdev": pay_sd,
        "writeOffPctMedian": est.get("writeOffPctMedian"),
        "writeOffPctStdev": est.get("writeOffPctStdev"),
        "varianceBand": variance,
        "sampleSize": n,
        "credibility": cred,
        "tier": tier,
        "source": source,
        "adaCode": ada,
        "insuranceCompany": payer,
        "masterCompanyId": est.get("masterCompanyId") or r.get("masterCompanyId"),
        "spineCarrierName": est.get("spineCarrierName") or r.get("spineCarrierName"),
        "viaAlias": bool(r.get("viaAlias") or source == "ledger_episode_5yr_via_alias"),
        "emptyIsNotZero": True,
        "def": "HAL-10601" if (r.get("viaAlias") or source == "ledger_episode_5yr_via_alias") else "HAL-10587",
        "honestyDef": "HAL-10591",
    }


def _ledger_spine_treatment_fallback(
    *,
    payer: str,
    ada_code: str,
    db_path: Path,
    include_inferred: bool = False,
) -> dict[str, Any]:
    """When gold payment lines empty, use unified InsCo×ADA spine ($ + %)."""
    out: dict[str, Any] = {
        "ok": True,
        "found": False,
        "sufficient": False,
        "payer": payer.strip(),
        "adaCode": ada_code,
        "sampleSize": 0,
        "estimate": None,
        "source": "ledger_episode_5yr",
        "goldAvailable": False,
        "honesty": (
            "Estimate from SoftDent ledger episodes (code 2 pay / 51 write-off) over ~5 years — "
            "not a guarantee of benefits. Gold payment-line path empty. empty != $0. "
            "Verify deductible, annual max, and plan limits."
        ),
    }
    try:
        from softdent_insco_ada_probabilistic import lookup_probabilistic_estimate
        from softdent_insco_ada_pct_variance import lookup_pct_variance
        from softdent_insco_ada_spine import normalize_cdt

        ada = normalize_cdt(ada_code) or normalize_ada_code(ada_code)
        out["adaCode"] = ada
        if not ada:
            out["message"] = "Need a CDT/ADA code (D####)."
            return out

        dollar = lookup_probabilistic_estimate(
            payer=payer,
            ada_code=ada,
            db_path=db_path,
            include_inferred=include_inferred,
        )
        pct = lookup_pct_variance(
            payer=payer,
            ada_code=ada,
            include_inferred=include_inferred,
            db_path=db_path,
        )
        if not dollar and not pct:
            # Catalog may still have an insufficient cell — surface honest empty chip
            try:
                from softdent_insco_ada_catalog_matrix import list_catalog_matrix_rows

                cat_rows = list_catalog_matrix_rows(
                    db_path=db_path,
                    include_insufficient=True,
                    include_inferred=True,
                    payer=payer,
                    ada=ada,
                    limit=3,
                )
            except Exception:
                cat_rows = []
            if cat_rows:
                row0 = cat_rows[0]
                n0 = int(row0.get("sampleSize") or 0)
                out["found"] = True
                out["sampleSize"] = n0
                out["credibility"] = "insufficient"
                out["tier"] = str(row0.get("tier") or "")
                out["estimate"] = {
                    "insuranceCompany": row0.get("insuranceCompany") or payer.strip(),
                    "adaCode": ada,
                    "submittedFeeAvg": None,
                    "allowedAmountAvg": None,
                    "paidAmountAvg": None,  # never invent dollars for insufficient UX
                    "writeOffAvg": None,
                    "patientPortionAvg": None,
                    "sampleSize": n0,
                    "credibility": "insufficient",
                    "tier": row0.get("tier"),
                    "isInferred": str(row0.get("tier") or "") == "inferred",
                    "source": "ledger_episode_5yr",
                    "goldAvailable": False,
                }
                out["sufficient"] = False
                out["message"] = (
                    f"Insufficient catalog data for {payer.strip()} × {ada} (n={n0}). "
                    "empty != $0 — verify with payer / benefits."
                )
                return out
            out["message"] = (
                f"No publishable ledger estimate for {payer.strip()} × {ada}. "
                "empty != $0 — run Sync / InsCo×ADA rebuild, or export Insurance Payment Analysis."
            )
            return out

        n = int((dollar or {}).get("sample_size") or (pct or {}).get("sampleSize") or 0)
        cred = str(
            (dollar or {}).get("credibility")
            or (pct or {}).get("credibility")
            or "insufficient"
        )
        tier = str((dollar or {}).get("tier") or (pct or {}).get("tier") or "exact")
        billed = (dollar or {}).get("billed_avg") or (pct or {}).get("billedAvg")
        paid = (dollar or {}).get("paid_median") or (dollar or {}).get("paid_avg")
        wo = (dollar or {}).get("write_off_median") or (dollar or {}).get("write_off_avg")
        estimate = {
            "insuranceCompany": (dollar or {}).get("insurance_company")
            or (pct or {}).get("insuranceCompany")
            or payer.strip(),
            "adaCode": ada,
            "submittedFeeAvg": billed,
            "allowedAmountAvg": None,
            "paidAmountAvg": paid if paid is not None else (pct or {}).get("paidAvg"),
            "writeOffAvg": wo if wo is not None else (pct or {}).get("writeOffAvg"),
            "patientPortionAvg": None,
            "paidPctMedian": (pct or {}).get("paidPctMedian"),
            "paidPctStdev": (pct or {}).get("paidPctStdev"),
            "writeOffPctMedian": (pct or {}).get("writeOffPctMedian"),
            "writeOffPctStdev": (pct or {}).get("writeOffPctStdev"),
            "sampleSize": n,
            "credibility": cred,
            "tier": tier,
            "isInferred": tier == "inferred",
            "source": "ledger_episode_5yr",
            "goldAvailable": False,
            "updatedAt": (dollar or {}).get("period_end") or (pct or {}).get("periodEnd"),
        }
        out["found"] = True
        out["sampleSize"] = n
        out["estimate"] = estimate
        out["sufficient"] = cred in {"high", "usable"} and tier == "exact"
        out["credibility"] = cred
        out["tier"] = tier
        if not out["sufficient"]:
            out["message"] = (
                f"Ledger spine has {cred}/{tier} data for {estimate['insuranceCompany']} × {ada} "
                f"(n={n}). Prefer exact usable+ for treatment quotes; inferred needs opt-in."
            )
        return out
    except Exception as exc:  # noqa: BLE001
        out["ok"] = False
        out["message"] = f"Ledger spine fallback failed: {type(exc).__name__}:{exc}"
        return out


def _fmt_money(value: Any, *, source_tag: str = "ledger_episode_5yr") -> str:
    """Format money honestly — empty/null never becomes ``$0.00`` (HAL-10591)."""
    try:
        from ui_honesty_policy import format_display_money

        return format_display_money(value, source_tag=source_tag, empty_display="unknown")
    except Exception:  # noqa: BLE001
        if value is None:
            return "unknown"
        try:
            return f"${float(value):,.2f}"
        except (TypeError, ValueError):
            return "unknown"


def format_treatment_estimate_reply(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        return str(result.get("message") or "Treatment estimate lookup failed.")
    chip = result.get("chip") if isinstance(result.get("chip"), dict) else build_tp_estimate_chip(result)
    if not result.get("found") or not chip.get("showDollars"):
        return str(
            chip.get("display")
            or result.get("message")
            or "No credible treatment-plan estimate (empty != $0)."
        )
    est = result.get("estimate") if isinstance(result.get("estimate"), dict) else {}
    co = est.get("insuranceCompany") or result.get("payer")
    ada = est.get("adaCode") or result.get("adaCode")
    source = str(est.get("source") or result.get("source") or "")
    badge = f"[{chip.get('label') or chip.get('badge')}]"
    if source == "ledger_episode_5yr" or source.startswith("ledger"):
        lines = [
            f"Treatment plan estimate {badge}: {co} × {ada} — {chip.get('display')}.",
            f"Source={source}.",
            str(result.get("honesty") or ""),
        ]
        if not result.get("sufficient"):
            lines.insert(1, str(result.get("message") or "Below exact usable+ — verify with payer."))
        return " ".join(x for x in lines if x).strip()
    if not result.get("sufficient"):
        return str(result.get("message") or chip.get("display") or "Insufficient sample size.")
    n = est.get("sampleSize") or result.get("sampleSize")
    lines = [
        f"Treatment plan estimate {badge} from {n} SoftDent insurance payment line(s): "
        f"{co} typically allows {_fmt_money(est.get('allowedAmountAvg'))} for {ada}, "
        f"paying {_fmt_money(est.get('paidAmountAvg'))} after write-off "
        f"{_fmt_money(est.get('writeOffAvg'))}. "
        f"Patient portion averages {_fmt_money(est.get('patientPortionAvg'))}.",
        str(result.get("honesty") or ""),
    ]
    if est.get("allowedAmountAvg") is None:
        lines.append("Allowed amount unknown — verify with payer before quoting the patient.")
    return " ".join(x for x in lines if x).strip()


def treatment_plan_estimate_widget() -> dict[str, Any]:
    """SoftDent-page TP estimate surface (HAL-10587) — catalog/spine chips."""
    from softdent_insco_ada_catalog_matrix import catalog_matrix_status, list_catalog_matrix_rows

    st = treatment_planning_status()
    cat = catalog_matrix_status()
    exact_rows = list_catalog_matrix_rows(
        include_insufficient=False, include_inferred=False, limit=8
    )
    chips: list[dict[str, Any]] = []
    for row in exact_rows:
        est = lookup_treatment_estimate(
            payer=str(row.get("insuranceCompany") or ""),
            ada_code=str(row.get("adaCode") or ""),
        )
        chip = est.get("chip") if isinstance(est.get("chip"), dict) else build_tp_estimate_chip(est)
        chips.append(chip)

    exact_n = int(cat.get("exactUsableCells") or st.get("ledgerSpineExactUsable") or 0)
    gold_n = int(st.get("estimatesWithMinSample") or 0)
    if exact_n <= 0 and gold_n <= 0:
        status = "empty"
        message = "No credible treatment-plan estimates yet — run Sync / InsCo×ADA rebuild."
    else:
        status = "ok"
        message = (
            f"Tx plan estimates · spine exact usable={exact_n} · "
            f"gold ready={gold_n} · catalog cells={cat.get('totalCells') or 0}"
        )
    return {
        "id": "softdent-tp-estimate-chips",
        "type": "status",
        "label": "Treatment Plan Estimates (HAL-10587)",
        "size": "strip",
        "compact": True,
        "maxHeight": 80,
        "status": status,
        "message": message,
        "hint": (
            "Catalog-enriched InsCo×ADA chips (pay$/WO$ + % +/-). "
            "Gold payment lines win when present; else ledger_episode_5yr. "
            "Insufficient never shows $0.00. empty != $0."
        ),
        "chips": chips,
        "exactUsable": exact_n,
        "goldReady": gold_n,
        "fallbackSource": st.get("fallbackSource"),
        "halChips": [
            {
                "label": "Delta KS D1110 tx estimate?",
                "query": "How much will Delta Dental of KS typically pay for D1110?",
            },
            {
                "label": "Treatment planning status",
                "query": "treatment planning estimates status",
            },
            {
                "label": "InsCo ADA catalog status",
                "query": "InsCo ADA catalog matrix status",
            },
        ],
        "honesty": (
            "Historical SoftDent ledger / payment-line averages — not a benefits guarantee. empty != $0."
        ),
        "def": "HAL-10587",
    }


def log_tp_estimate_audit(result: dict[str, Any], *, source: str = "api") -> None:
    """Best-effort debug audit for TP estimate lookups."""
    try:
        root = resolve_exports_dir()
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"tp_estimate_audit_{date.today().isoformat()}.jsonl"
        chip = result.get("chip") if isinstance(result.get("chip"), dict) else {}
        line = json.dumps(
            {
                "at": _utc_now(),
                "source": source,
                "payer": result.get("payer"),
                "adaCode": result.get("adaCode"),
                "found": result.get("found"),
                "sufficient": result.get("sufficient"),
                "credibility": result.get("credibility") or chip.get("credibility"),
                "tier": result.get("tier") or chip.get("tier"),
                "estimateSource": result.get("source") or chip.get("source"),
                "showDollars": chip.get("showDollars"),
                "def": "HAL-10587",
            },
            ensure_ascii=True,
        )
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        pass


def parse_treatment_estimate_query(query: str) -> dict[str, str] | None:
    """Extract payer + ADA from natural language, or None if not an estimate ask."""
    q = str(query or "").strip()
    if not q:
        return None
    ada_m = re.search(r"\b(D\d{4})\b", q, re.I)
    if not ada_m:
        # also accept bare 4-digit after "code"
        ada_m = re.search(r"\b(?:code|cdt|ada)\s*#?\s*(\d{4})\b", q, re.I)
        if ada_m:
            ada = f"D{ada_m.group(1)}"
        else:
            return None
    else:
        ada = ada_m.group(1).upper()

    ql = q.lower()
    estimate_intent = bool(
        re.search(
            r"\b("
            r"how much|typically (pay|allow|cover)|what (does|will|would)|"
            r"pay(s|ment)? for|allow(s|ed)? for|estimate|treatment plan"
            r")\b",
            ql,
        )
    )
    if not estimate_intent and not re.search(r"\b(delta|cigna|metlife|aetna|guardian|sun life|bcbs|blue cross)\b", ql):
        return None

    payer = ""
    # "Delta Dental" / "for Delta" / "will Cigna pay"
    m = re.search(
        r"\b(?:for|from|with|does|will|would|can)\s+([A-Za-z][A-Za-z0-9 &./'-]{1,40}?)\s+"
        r"(?:typically |usually |normally )?(?:pay|allow|cover|reimburse)",
        q,
        re.I,
    )
    if m:
        payer = m.group(1).strip(" .,")
    if not payer:
        m = re.search(
            r"\b(delta(?:\s+dental)?(?:\s+ppo)?|cigna|metlife|aetna|guardian|sun\s*life|"
            r"blue\s*cross(?:\s*blue\s*shield)?|bcbs|united\s*concordia|humana|"
            r"principal|ameritas|geha|dentaquest)\b",
            q,
            re.I,
        )
        if m:
            payer = m.group(1)
    if not payer:
        # "how much will X pay for D0274"
        m = re.search(r"\b(?:will|does|would)\s+(.+?)\s+pay\s+for\b", q, re.I)
        if m:
            payer = m.group(1).strip(" .,")
    if not payer or _normalize_payer_query(payer) in GENERIC_PAYERS:
        return None
    return {"payer": payer, "adaCode": ada}


def treatment_planning_status(db_path: Path | None = None) -> dict[str, Any]:
    db_path = db_path or resolve_analytics_db()
    out: dict[str, Any] = {
        "ok": bool(db_path and Path(db_path).is_file()),
        "paymentLines": 0,
        "procedureCodes": 0,
        "estimates": 0,
        "estimatesWithMinSample": 0,
        "hint": (
            r"Drop insurance_payments_YYYYMMDD.csv (+ optional procedure_codes_YYYYMMDD.csv) "
            r"in C:\SoftDentFinancialExports then Sync imports."
        ),
    }
    if not out["ok"]:
        return out
    conn = sqlite3.connect(str(db_path))
    try:
        ensure_treatment_planning_schema(conn)
        out["paymentLines"] = int(conn.execute("SELECT COUNT(*) FROM sd_insurance_payment_lines").fetchone()[0] or 0)
        out["procedureCodes"] = int(conn.execute("SELECT COUNT(*) FROM sd_procedure_code_reference").fetchone()[0] or 0)
        out["estimates"] = int(conn.execute("SELECT COUNT(*) FROM treatment_planning_estimates").fetchone()[0] or 0)
        out["estimatesWithMinSample"] = int(
            conn.execute(
                "SELECT COUNT(*) FROM treatment_planning_estimates WHERE sample_size >= ?",
                (MIN_SAMPLE_SIZE,),
            ).fetchone()[0]
            or 0
        )
        # Spine fallback availability (HAL-10585) when gold path empty
        try:
            if out["estimates"] == 0:
                spine_n = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) FROM insco_ada_probabilistic_estimates
                        WHERE tier='exact' AND credibility IN ('high','usable')
                        """
                    ).fetchone()[0]
                    or 0
                )
                out["ledgerSpineExactUsable"] = spine_n
                out["fallbackSource"] = "ledger_episode_5yr" if spine_n else None
                if spine_n:
                    out["hint"] = (
                        "Gold payment lines empty — treatment estimates fall back to unified "
                        "InsCo×ADA ledger spine (code 2/51, 5yr), resolving accepted carrier "
                        "aliases (HAL-10601). Pending manuals never auto-resolve. empty != $0."
                    )
                    out["tpCodeUsesCarrierAlias"] = True
                    out["fallbackSource"] = "ledger_episode_5yr_via_alias"
        except Exception:
            pass
        out["tpCodeUsesCarrierAlias"] = True
        out["emptyIsNotZero"] = True
        out["def"] = "HAL-10601"
    finally:
        conn.close()
    return out

# Moonshot OM Phase 2 — HAL tool discovery metadata (handlers already implemented above).
HAL_TOOLS = {
    "lookup_treatment_estimate": {
        "description": "Look up estimated insurance payment for ADA code and payer",
        "parameters": {
            "ada_code": "str (e.g., D2740)",
            "payer_name": "str (insurance company name or 'unknown')",
        },
        "handler": "lookup_treatment_estimate",
    },
    "format_treatment_estimate_reply": {
        "description": "Format estimate for patient-friendly display",
        "parameters": {"estimate_dict": "dict from lookup_treatment_estimate"},
        "handler": "format_treatment_estimate_reply",
    },
}
