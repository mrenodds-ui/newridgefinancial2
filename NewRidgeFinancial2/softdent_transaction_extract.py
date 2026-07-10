"""Deep SoftDent transaction + register extract (Moonshot full-extract pack).

Reads live ``transactions_for_period.jsonl`` / ``register_for_period.jsonl`` from
``C:\\SoftDentFinancialExports`` (normalized JSONL wrapper shape) into:

- ``sd_transactions_full`` — every line-item transaction
- ``sd_register_detail`` — register summary / method rows
- ``sd_operatory_schedule`` — chairs/slots from ``operatory_schedule.json``
- refreshes ``sd_payments`` / ``sd_adjustments`` from typed transaction rows

Also upserts into legacy ``transactions`` when that table already exists so the
analytics DB stays in parity with the external SoftDent financial importer.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXPORTS = Path(r"C:\SoftDentFinancialExports")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_exports_dir() -> Path:
    configured = os.environ.get("SOFTDENT_FINANCIAL_EXPORTS", "").strip()
    if configured:
        return Path(configured).expanduser()
    return DEFAULT_EXPORTS


def resolve_analytics_db() -> Path | None:
    try:
        from quickbooks_monthly_sync import resolve_analytics_db as _resolve

        path = _resolve()
        if path and path.is_file():
            return path
    except Exception:
        pass
    env = os.environ.get("NR2_FINANCIAL_ANALYTICS_DB", "").strip()
    if env:
        candidate = Path(env).expanduser()
        if candidate.is_file():
            return candidate
    default = resolve_exports_dir() / "softdent_financial_analytics.db"
    return default if default.is_file() else None


def parse_money(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
    if not text or text in {"-", "—"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_code(code: Any) -> str:
    text = str(code or "").strip()
    if not text:
        return ""
    # SoftDent sometimes emits "2.00" for code 2
    if text.replace(".", "", 1).isdigit() and "." in text:
        try:
            as_float = float(text)
            if as_float == int(as_float) and as_float < 1000:
                return str(int(as_float))
        except ValueError:
            pass
    return text


def _stable_id(*parts: Any) -> str:
    payload = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()[:32]


def ensure_transactions_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sd_transactions_full (
            transaction_id TEXT PRIMARY KEY,
            patient_id TEXT,
            patient_name TEXT,
            provider_code TEXT,
            service_date TEXT,
            entry_date TEXT,
            ada_code TEXT,
            description TEXT,
            amount REAL,
            transaction_type TEXT,
            payment_method TEXT,
            payment_amount REAL,
            adjustment_code TEXT,
            adjustment_amount REAL,
            payer TEXT,
            claim_id TEXT,
            tooth TEXT,
            surface TEXT,
            quantity INTEGER DEFAULT 1,
            original_transaction_id TEXT,
            account_id TEXT,
            guarantor_id TEXT,
            source_file TEXT,
            row_number INTEGER,
            extracted_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_sd_trans_patient ON sd_transactions_full(patient_id);
        CREATE INDEX IF NOT EXISTS idx_sd_trans_date ON sd_transactions_full(service_date);
        CREATE INDEX IF NOT EXISTS idx_sd_trans_type ON sd_transactions_full(transaction_type);
        CREATE INDEX IF NOT EXISTS idx_sd_trans_code ON sd_transactions_full(ada_code);

        CREATE TABLE IF NOT EXISTS sd_register_detail (
            register_id TEXT PRIMARY KEY,
            transaction_id TEXT,
            patient_id TEXT,
            payment_date TEXT,
            payment_method TEXT,
            payment_amount REAL,
            check_number TEXT,
            batch_number TEXT,
            label TEXT,
            deposited INTEGER DEFAULT 0,
            source_file TEXT,
            extracted_at TEXT
        );

        CREATE TABLE IF NOT EXISTS sd_operatory_schedule (
            appointment_id TEXT PRIMARY KEY,
            operatory TEXT,
            patient_id TEXT,
            patient_name TEXT,
            provider_code TEXT,
            appt_date TEXT,
            start_time TEXT,
            end_time TEXT,
            status TEXT,
            appointment_type TEXT,
            extracted_at TEXT
        );

        CREATE TABLE IF NOT EXISTS sd_extract_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )


def _unwrap_normalized(payload: dict[str, Any]) -> dict[str, Any]:
    norm = payload.get("normalized")
    if isinstance(norm, dict):
        return norm
    return payload


def normalize_transaction(
    payload: dict[str, Any],
    *,
    source_file: str,
    extracted_at: str,
) -> dict[str, Any] | None:
    """Map SoftDentFinancialExports JSONL row → sd_transactions_full."""
    if not isinstance(payload, dict):
        return None
    raw = _unwrap_normalized(payload)
    if raw.get("source_summary_type"):
        return None  # period totals header — not a line item

    row_number = payload.get("row_number")
    tx_date = str(raw.get("transaction_date") or raw.get("serviceDate") or raw.get("date") or "")[:10]
    post_date = str(raw.get("posting_date") or raw.get("entryDate") or "")[:10]
    service_date = str(raw.get("service_date") or tx_date or "")[:10]
    code = _normalize_code(raw.get("transaction_code") or raw.get("code") or raw.get("adaCode"))
    description = str(raw.get("transaction_description") or raw.get("description") or "")
    tx_type = str(raw.get("transaction_type") or raw.get("type") or "transaction").strip().lower()
    amount = parse_money(raw.get("amount") or raw.get("production") or raw.get("chargeAmount"))
    patient_id = str(raw.get("patient_id") or raw.get("patientId") or "")
    provider_code = str(raw.get("provider_id") or raw.get("provider_code") or raw.get("providerId") or "")
    account_id = str(raw.get("account_id") or "")
    guarantor_id = str(raw.get("guarantor_id") or "")

    explicit_id = str(raw.get("transactionId") or raw.get("id") or "").strip()
    transaction_id = explicit_id or _stable_id(
        source_file,
        row_number,
        tx_date,
        post_date,
        code,
        amount,
        patient_id,
        provider_code,
        tx_type,
        description,
    )

    payment_amount = None
    adjustment_amount = None
    adjustment_code = ""
    if tx_type in {"payment", "credit", "refund"}:
        payment_amount = abs(amount) if amount is not None else None
    if tx_type in {"adjustment", "writeoff", "write-off"} or code in {"51", "52"}:
        adjustment_code = code
        adjustment_amount = abs(amount) if amount is not None else None

    return {
        "transaction_id": transaction_id,
        "patient_id": patient_id,
        "patient_name": str(raw.get("patient_name") or raw.get("patientName") or ""),
        "provider_code": provider_code,
        "service_date": service_date,
        "entry_date": post_date or tx_date,
        "ada_code": code,
        "description": description,
        "amount": amount,
        "transaction_type": tx_type or "transaction",
        "payment_method": str(raw.get("paymentMethod") or raw.get("payment_method") or ""),
        "payment_amount": payment_amount,
        "adjustment_code": adjustment_code,
        "adjustment_amount": adjustment_amount,
        "payer": str(raw.get("payer") or ""),
        "claim_id": str(raw.get("claimId") or raw.get("claim_id") or ""),
        "tooth": str(raw.get("toothNumber") or raw.get("tooth") or ""),
        "surface": str(raw.get("surface") or ""),
        "quantity": int(raw.get("unitQuantity") or raw.get("quantity") or 1),
        "original_transaction_id": str(raw.get("originalTransactionId") or ""),
        "account_id": account_id,
        "guarantor_id": guarantor_id,
        "source_file": str(payload.get("source_file") or source_file),
        "row_number": int(row_number) if str(row_number or "").isdigit() else None,
        "extracted_at": extracted_at,
        # legacy transactions table helpers
        "_provider_name": str(raw.get("provider_name") or ""),
        "_collecting_provider_id": str(raw.get("collecting_provider_id") or ""),
        "_transaction_date": tx_date,
        "_posting_date": post_date,
    }


def load_transactions_jsonl(path: Path) -> list[dict[str, Any]]:
    transactions: list[dict[str, Any]] = []
    if not path.is_file():
        return transactions
    extracted_at = _utc_now()
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            items = payload if isinstance(payload, list) else [payload]
            for item in items:
                if not isinstance(item, dict):
                    continue
                details = item.get("transactionDetails") or item.get("details") or item.get("transactions")
                if isinstance(details, list):
                    for detail in details:
                        if isinstance(detail, dict):
                            wrapped = {"normalized": detail, "source_file": item.get("source_file"), "row_number": item.get("row_number")}
                            tx = normalize_transaction(wrapped, source_file=path.name, extracted_at=extracted_at)
                            if tx:
                                transactions.append(tx)
                    continue
                tx = normalize_transaction(item, source_file=path.name, extracted_at=extracted_at)
                if tx:
                    transactions.append(tx)
    return transactions


def load_register_jsonl(path: Path) -> list[dict[str, Any]]:
    registers: list[dict[str, Any]] = []
    if not path.is_file():
        return registers
    extracted_at = _utc_now()
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            if str(payload.get("dataset_name") or "") not in {"", "register_for_period"}:
                # still accept unlabeled rows
                if payload.get("dataset_name") and payload.get("dataset_name") != "register_for_period":
                    continue
            raw_row = payload.get("raw_row")
            norm = payload.get("normalized") if isinstance(payload.get("normalized"), dict) else {}
            cells = [str(c or "").strip() for c in raw_row] if isinstance(raw_row, list) else []
            while len(cells) < 4:
                cells.append("")
            label = (cells[0] or cells[1] or str(norm.get("adjustments_to_prod") or "")).strip()
            method = cells[1].strip() if cells[0] else ""
            amount = parse_money(cells[2]) or parse_money(cells[3])
            if amount is None:
                # try odd normalized money keys
                for key, value in norm.items():
                    if key in {"adjustments_to_prod", "calendar_year", "calendar_month", "year_month"}:
                        continue
                    amount = parse_money(value)
                    if amount is not None:
                        break
            if not label and amount is None:
                continue
            row_number = payload.get("row_number")
            register_id = _stable_id(path.name, row_number, label, method, amount)
            registers.append(
                {
                    "register_id": register_id,
                    "transaction_id": "",
                    "patient_id": "",
                    "payment_date": "",
                    "payment_method": method or label,
                    "payment_amount": amount,
                    "check_number": "",
                    "batch_number": "",
                    "label": label,
                    "deposited": 0,
                    "source_file": str(payload.get("source_file") or path.name),
                    "extracted_at": extracted_at,
                }
            )
    return registers


def persist_transactions(conn: sqlite3.Connection, transactions: list[dict[str, Any]]) -> int:
    if not transactions:
        return 0
    rows = [
        {
            k: v
            for k, v in tx.items()
            if not str(k).startswith("_")
        }
        for tx in transactions
    ]
    conn.executemany(
        """
        INSERT INTO sd_transactions_full (
            transaction_id, patient_id, patient_name, provider_code, service_date, entry_date,
            ada_code, description, amount, transaction_type, payment_method, payment_amount,
            adjustment_code, adjustment_amount, payer, claim_id, tooth, surface, quantity,
            original_transaction_id, account_id, guarantor_id, source_file, row_number, extracted_at
        ) VALUES (
            :transaction_id, :patient_id, :patient_name, :provider_code, :service_date, :entry_date,
            :ada_code, :description, :amount, :transaction_type, :payment_method, :payment_amount,
            :adjustment_code, :adjustment_amount, :payer, :claim_id, :tooth, :surface, :quantity,
            :original_transaction_id, :account_id, :guarantor_id, :source_file, :row_number, :extracted_at
        )
        ON CONFLICT(transaction_id) DO UPDATE SET
            patient_id=excluded.patient_id,
            patient_name=excluded.patient_name,
            provider_code=excluded.provider_code,
            service_date=excluded.service_date,
            entry_date=excluded.entry_date,
            ada_code=excluded.ada_code,
            description=excluded.description,
            amount=excluded.amount,
            transaction_type=excluded.transaction_type,
            payment_method=excluded.payment_method,
            payment_amount=excluded.payment_amount,
            adjustment_code=excluded.adjustment_code,
            adjustment_amount=excluded.adjustment_amount,
            payer=excluded.payer,
            account_id=excluded.account_id,
            guarantor_id=excluded.guarantor_id,
            extracted_at=excluded.extracted_at
        """,
        rows,
    )
    # Do not upsert into legacy `transactions` — that table is owned by the
    # SoftDent financial importer (different business_key scheme). NR2 depth
    # lives in sd_transactions_full; payments/adjustments are refreshed below.
    _upsert_payments_adjustments_from_transactions(conn, transactions)
    conn.commit()
    return len(rows)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,),
    )
    return cur.fetchone() is not None


def _ensure_sd_pay_adj(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sd_payments (
            practice_id TEXT NOT NULL DEFAULT '',
            patient_id TEXT NOT NULL DEFAULT '',
            payment_date TEXT NOT NULL DEFAULT '',
            amount REAL,
            payer TEXT,
            method TEXT,
            extracted_at TEXT,
            PRIMARY KEY (practice_id, patient_id, payment_date, amount, method)
        );
        CREATE TABLE IF NOT EXISTS sd_adjustments (
            practice_id TEXT NOT NULL DEFAULT '',
            patient_id TEXT NOT NULL DEFAULT '',
            adj_date TEXT NOT NULL DEFAULT '',
            ada_code TEXT NOT NULL DEFAULT '',
            amount REAL,
            description TEXT,
            extracted_at TEXT,
            PRIMARY KEY (practice_id, patient_id, adj_date, ada_code, amount)
        );
        """
    )


def _upsert_payments_adjustments_from_transactions(
    conn: sqlite3.Connection,
    transactions: list[dict[str, Any]],
) -> dict[str, int]:
    _ensure_sd_pay_adj(conn)
    counts = {"sd_payments": 0, "sd_adjustments": 0}
    for tx in transactions:
        tx_type = str(tx.get("transaction_type") or "").lower()
        patient_id = str(tx.get("patient_id") or "").strip() or f"tx:{tx.get('transaction_id')}"
        date = str(tx.get("service_date") or tx.get("entry_date") or "").strip()
        amount = tx.get("amount")
        if amount is None:
            continue
        if tx_type == "payment" or (tx.get("payment_amount") is not None and tx_type in {"payment", "credit", "refund"}):
            if not date:
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO sd_payments
                (practice_id, patient_id, payment_date, amount, payer, method, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "",
                    patient_id,
                    date,
                    abs(float(amount)),
                    tx.get("payer") or "",
                    tx.get("payment_method") or tx.get("description") or tx.get("ada_code") or "payment",
                    tx.get("extracted_at"),
                ),
            )
            counts["sd_payments"] += 1
        elif tx_type in {"adjustment", "writeoff", "write-off"} or str(tx.get("adjustment_code") or "") in {"51", "52"}:
            if not date:
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO sd_adjustments
                (practice_id, patient_id, adj_date, ada_code, amount, description, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "",
                    patient_id,
                    date,
                    tx.get("adjustment_code") or tx.get("ada_code") or "adj",
                    abs(float(amount)),
                    tx.get("description") or "adjustment",
                    tx.get("extracted_at"),
                ),
            )
            counts["sd_adjustments"] += 1
    return counts


def persist_register(conn: sqlite3.Connection, registers: list[dict[str, Any]]) -> int:
    if not registers:
        return 0
    conn.executemany(
        """
        INSERT INTO sd_register_detail (
            register_id, transaction_id, patient_id, payment_date, payment_method,
            payment_amount, check_number, batch_number, label, deposited, source_file, extracted_at
        ) VALUES (
            :register_id, :transaction_id, :patient_id, :payment_date, :payment_method,
            :payment_amount, :check_number, :batch_number, :label, :deposited, :source_file, :extracted_at
        )
        ON CONFLICT(register_id) DO UPDATE SET
            payment_amount=excluded.payment_amount,
            payment_method=excluded.payment_method,
            label=excluded.label,
            extracted_at=excluded.extracted_at
        """,
        registers,
    )
    conn.commit()
    return len(registers)


def load_operatory_schedule(path: Path | None = None) -> list[dict[str, Any]]:
    """Parse operatory_schedule.json (operatoryChairs[] NR2 shape or operatories[])."""
    if path is None:
        exports = resolve_exports_dir()
        candidates = [
            exports / "operatory_schedule.json",
        ]
        try:
            from import_loader import softdent_import_dir

            candidates.insert(0, softdent_import_dir() / "operatory_schedule.json")
        except Exception:
            pass
        path = next((p for p in candidates if p.is_file()), None)
    if not path or not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    extracted_at = _utc_now()
    slots: list[dict[str, Any]] = []

    chairs = data.get("operatoryChairs")
    if isinstance(chairs, list):
        for chair in chairs:
            if not isinstance(chair, dict):
                continue
            op_name = str(chair.get("name") or chair.get("operatory") or "")
            for idx, appt in enumerate(chair.get("slots") or []):
                if not isinstance(appt, dict):
                    continue
                time_label = str(appt.get("time") or "")
                patient = str(appt.get("patient") or "")
                status = str(appt.get("procedure") or appt.get("status") or "")
                appt_id = _stable_id(op_name, time_label, patient, idx, status)
                slots.append(
                    {
                        "appointment_id": appt_id,
                        "operatory": op_name,
                        "patient_id": str(appt.get("patientId") or ""),
                        "patient_name": patient,
                        "provider_code": str(appt.get("provider") or appt.get("providerCode") or ""),
                        "appt_date": time_label[:10],
                        "start_time": time_label,
                        "end_time": "",
                        "status": status,
                        "appointment_type": str(appt.get("type") or ""),
                        "extracted_at": extracted_at,
                    }
                )
        return slots

    for op in data.get("operatories") or []:
        if not isinstance(op, dict):
            continue
        op_name = str(op.get("operatoryName") or op.get("name") or "")
        for appt in op.get("appointments") or []:
            if not isinstance(appt, dict):
                continue
            appt_id = str(appt.get("id") or _stable_id(op_name, appt.get("patientId"), appt.get("startTime")))
            slots.append(
                {
                    "appointment_id": appt_id,
                    "operatory": op_name,
                    "patient_id": str(appt.get("patientId") or ""),
                    "patient_name": str(appt.get("patientName") or ""),
                    "provider_code": str(appt.get("providerCode") or ""),
                    "appt_date": str(appt.get("date") or "")[:10],
                    "start_time": str(appt.get("startTime") or ""),
                    "end_time": str(appt.get("endTime") or ""),
                    "status": str(appt.get("status") or ""),
                    "appointment_type": str(appt.get("type") or ""),
                    "extracted_at": extracted_at,
                }
            )
    return slots


def persist_operatory_schedule(conn: sqlite3.Connection, slots: list[dict[str, Any]]) -> int:
    if not slots:
        return 0
    conn.executemany(
        """
        INSERT INTO sd_operatory_schedule (
            appointment_id, operatory, patient_id, patient_name, provider_code,
            appt_date, start_time, end_time, status, appointment_type, extracted_at
        ) VALUES (
            :appointment_id, :operatory, :patient_id, :patient_name, :provider_code,
            :appt_date, :start_time, :end_time, :status, :appointment_type, :extracted_at
        )
        ON CONFLICT(appointment_id) DO UPDATE SET
            operatory=excluded.operatory,
            patient_name=excluded.patient_name,
            status=excluded.status,
            extracted_at=excluded.extracted_at
        """,
        slots,
    )
    conn.commit()
    return len(slots)


def verify_completeness(conn: sqlite3.Connection, trans_path: Path) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "file_bytes": trans_path.stat().st_size if trans_path.is_file() else 0,
        "jsonl_rows": 0,
        "db_rows": 0,
        "date_range": {"min": None, "max": None},
        "amount_sum": 0.0,
        "by_type": {},
        "parity_ratio": None,
    }
    if trans_path.is_file():
        with trans_path.open("r", encoding="utf-8", errors="replace") as handle:
            stats["jsonl_rows"] = sum(1 for line in handle if line.strip())
    cur = conn.execute(
        "SELECT COUNT(*), MIN(service_date), MAX(service_date), SUM(amount) FROM sd_transactions_full"
    )
    row = cur.fetchone()
    if row:
        stats["db_rows"] = int(row[0] or 0)
        stats["date_range"]["min"] = row[1]
        stats["date_range"]["max"] = row[2]
        stats["amount_sum"] = float(row[3] or 0.0)
    for tx_type, count in conn.execute(
        "SELECT transaction_type, COUNT(*) FROM sd_transactions_full GROUP BY transaction_type"
    ):
        stats["by_type"][str(tx_type)] = int(count)
    # Exclude 1 summary header line when present
    expected = max(0, int(stats["jsonl_rows"]) - 1)
    if expected > 0:
        stats["parity_ratio"] = round(stats["db_rows"] / expected, 4)
    return stats


def extract_all_transactions(
    db_path: Path | None = None,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Main entry — full transaction / register / operatory extract."""
    del force  # always re-read source files; upserts are idempotent
    result: dict[str, Any] = {
        "ok": False,
        "transactions": 0,
        "register": 0,
        "operatory": 0,
        "warnings": [],
        "mode": "jsonl-financial-exports",
    }
    db_path = db_path or resolve_analytics_db()
    if not db_path:
        result["warnings"].append("No analytics DB found")
        return result

    exports = resolve_exports_dir()
    trans_path = exports / "transactions_for_period.jsonl"
    register_path = exports / "register_for_period.jsonl"

    conn = sqlite3.connect(str(db_path))
    try:
        ensure_transactions_schema(conn)
        if trans_path.is_file():
            txs = load_transactions_jsonl(trans_path)
            result["transactions"] = persist_transactions(conn, txs)
        else:
            result["warnings"].append(f"Missing {trans_path}")

        if register_path.is_file():
            regs = load_register_jsonl(register_path)
            result["register"] = persist_register(conn, regs)
        else:
            result["warnings"].append(f"Missing {register_path}")

        slots = load_operatory_schedule()
        if slots:
            result["operatory"] = persist_operatory_schedule(conn, slots)

        result["verification"] = verify_completeness(conn, trans_path)
        conn.execute(
            "INSERT OR REPLACE INTO sd_extract_meta (key, value) VALUES (?, ?)",
            ("last_transaction_extract", _utc_now()),
        )
        conn.commit()
        parity = (result.get("verification") or {}).get("parity_ratio")
        result["ok"] = bool(result["transactions"] > 0 and (parity is None or parity >= 0.9))
        if parity is not None and parity < 0.9:
            result["warnings"].append(
                f"Transaction parity {parity} below 0.9 (jsonl vs sd_transactions_full)"
            )
    finally:
        conn.close()
    return result


def sync_softdent_transactions() -> dict[str, Any]:
    """Import-sync hook."""
    return extract_all_transactions(force=True)


if __name__ == "__main__":
    import sys

    db = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    print(json.dumps(extract_all_transactions(db_path=db, force=True), indent=2, default=str))
