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
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MIN_SAMPLE_SIZE = 10
GENERIC_PAYERS = frozenset({"insurance", "ins", "payer", "carrier", "unknown", ""})

_PAYMENT_GLOBS = (
    "insurance_payments*.csv",
    "insurance_payment_analysis*.csv",
    "insurance_payment_distribution*.csv",
    "InsurancePayment*.csv",
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
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
    if not text or text in {"-", "—", "N/A", "n/a"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


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
        """
    )


def ingest_insurance_payment_csv(
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
        for idx, raw in enumerate(reader):
            company = _pick(raw, field_lookup, _PAYMENT_COLMAP["insurance_company"])
            ada_raw = _pick(raw, field_lookup, _PAYMENT_COLMAP["ada_code"])
            ada = normalize_ada_code(ada_raw)
            submitted = parse_money(_pick(raw, field_lookup, _PAYMENT_COLMAP["submitted_fee"]))
            allowed = parse_money(_pick(raw, field_lookup, _PAYMENT_COLMAP["allowed_amount"]))
            paid = parse_money(_pick(raw, field_lookup, _PAYMENT_COLMAP["paid_amount"]))
            write_off = parse_money(_pick(raw, field_lookup, _PAYMENT_COLMAP["write_off_amount"]))
            patient = parse_money(_pick(raw, field_lookup, _PAYMENT_COLMAP["patient_portion"]))
            claim = _pick(raw, field_lookup, _PAYMENT_COLMAP["claim_number"])
            check = _pick(raw, field_lookup, _PAYMENT_COLMAP["check_number"])
            pay_date = _pick(raw, field_lookup, _PAYMENT_COLMAP["payment_date"])
            desc = _pick(raw, field_lookup, _PAYMENT_COLMAP["description"])
            if not company and not ada and paid is None and submitted is None:
                continue
            # Derive patient portion when missing but allowed+paid present
            if patient is None and allowed is not None and paid is not None:
                patient = round(allowed - paid, 2)
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
    conn.execute("DELETE FROM sd_insurance_payment_lines WHERE source_file = ?", (path.name,))
    # Full replace when ingesting newest file of this type
    conn.execute("DELETE FROM sd_insurance_payment_lines")
    conn.executemany(
        """
        INSERT OR REPLACE INTO sd_insurance_payment_lines (
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
    _rollup_into_importer_aggregate(conn, rows, path.name, extracted_at)
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
            # Any payer for this ADA (informational)
            any_row = conn.execute(
                """
                SELECT insurance_company, sample_size FROM treatment_planning_estimates
                WHERE upper(ada_code) = upper(?)
                ORDER BY sample_size DESC LIMIT 3
                """,
                (ada,),
            ).fetchall()
            out["ok"] = True
            out["message"] = (
                f"No historical payment lines for {payer.strip()} × {ada}. "
                + (
                    "Other payers with data: "
                    + ", ".join(f"{r['insurance_company']} (n={r['sample_size']})" for r in any_row)
                    if any_row
                    else "Export SoftDent Insurance Payment Analysis CSV to build estimates."
                )
            )
            return out

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
        }
        out["ok"] = True
        out["found"] = True
        out["sampleSize"] = sample
        out["estimate"] = estimate
        out["sufficient"] = sample >= min_sample
        if not out["sufficient"]:
            out["message"] = (
                f"Only {sample} historical line(s) for {estimate['insuranceCompany']} × {ada} "
                f"(need >={min_sample} for a reliable estimate). Contact payer for pre-auth / benefits."
            )
        return out
    finally:
        conn.close()


def _fmt_money(value: Any) -> str:
    if value is None:
        return "unknown"
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "unknown"


def format_treatment_estimate_reply(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        return str(result.get("message") or "Treatment estimate lookup failed.")
    if not result.get("found"):
        return str(result.get("message") or "No estimate found.")
    if not result.get("sufficient"):
        return str(result.get("message") or "Insufficient sample size.")
    est = result.get("estimate") if isinstance(result.get("estimate"), dict) else {}
    co = est.get("insuranceCompany") or result.get("payer")
    ada = est.get("adaCode") or result.get("adaCode")
    n = est.get("sampleSize") or result.get("sampleSize")
    lines = [
        f"Based on {n} historical SoftDent insurance payment line(s), "
        f"{co} typically allows {_fmt_money(est.get('allowedAmountAvg'))} for {ada}, "
        f"paying {_fmt_money(est.get('paidAmountAvg'))} after contractual write-off "
        f"of {_fmt_money(est.get('writeOffAvg'))}. "
        f"Patient portion averages {_fmt_money(est.get('patientPortionAvg'))} "
        f"(submitted avg {_fmt_money(est.get('submittedFeeAvg'))}).",
        str(result.get("honesty") or ""),
    ]
    if est.get("allowedAmountAvg") is None:
        lines.append("Allowed amount unknown in historical data — verify with payer before quoting the patient.")
    return " ".join(x for x in lines if x).strip()


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
