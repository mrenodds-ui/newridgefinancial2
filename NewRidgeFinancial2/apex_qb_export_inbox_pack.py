"""
QB payroll/AP export → document-inbox (closes optional quickbooks.payroll / .ap gap).

Writes atomic CSVs matching import-manifest filenames into quickbooks_import_dir().
Does not invent live practice dollars. Empty batches write header-only CSV +
batch_empty sidecar (empty ≠ $0). No SoftDent write-back.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from import_contract import QUICKBOOKS_AP_NAMES, QUICKBOOKS_PAYROLL_NAMES
from import_loader import quickbooks_import_dir

PAYROLL_FIELDS = ["Period", "Employee", "GrossPay", "NetPay", "Amount", "Department"]
AP_FIELDS = ["Vendor", "Balance", "Amount", "DueDate", "BillDate", "Bucket"]

PAYROLL_FILENAME = "quickbooks_payroll_detail.csv"
AP_FILENAME = "quickbooks_ap_aging.csv"
PAYROLL_EMPTY_META = "quickbooks_payroll.batch_empty.json"
AP_EMPTY_META = "quickbooks_ap.batch_empty.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _atomic_write_text(path: Path, text: str) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(tmp_path, path)
    except Exception:
        try:
            if tmp_path.is_file():
                tmp_path.unlink()
        except OSError:
            pass
        raise
    return {
        "path": str(path),
        "filename": path.name,
        "bytes": len(text.encode("utf-8")),
        "sha256": _sha256_text(text),
    }


def _rows_to_csv(fieldnames: list[str], rows: list[dict[str, Any]]) -> str:
    from io import StringIO

    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        if not isinstance(row, dict):
            continue
        out = {k: row.get(k, "") for k in fieldnames}
        writer.writerow(out)
    return buf.getvalue()


def _normalize_payroll_input(row: dict[str, Any], *, period_default: str) -> dict[str, Any] | None:
    period = str(row.get("Period") or row.get("period") or row.get("PayPeriod") or period_default).strip()
    employee = str(row.get("Employee") or row.get("employee") or row.get("Name") or "").strip()
    amount = row.get("Amount") or row.get("GrossPay") or row.get("gross") or row.get("Wages")
    net = row.get("NetPay") or row.get("net_pay") or row.get("Net")
    if not period:
        return None
    # Allow period-only rows only when explicitly marked empty_period (honesty marker).
    if not employee and not amount and not net and not row.get("empty_period"):
        return None
    return {
        "Period": period[:32],
        "Employee": employee[:120],
        "GrossPay": "" if amount is None else str(amount),
        "NetPay": "" if net is None else str(net),
        "Amount": "" if amount is None else str(amount),
        "Department": str(row.get("Department") or row.get("department") or "")[:80],
    }


def _normalize_ap_input(row: dict[str, Any], *, period_default: str) -> dict[str, Any] | None:
    vendor = str(row.get("Vendor") or row.get("vendor") or row.get("Name") or row.get("Payee") or "").strip()
    balance = row.get("Balance") or row.get("Amount") or row.get("OpenBalance") or row.get("amount_due")
    if not vendor:
        return None
    if balance is None and not row.get("empty_period"):
        return None
    return {
        "Vendor": vendor[:120],
        "Balance": "" if balance is None else str(balance),
        "Amount": "" if balance is None else str(balance),
        "DueDate": str(row.get("DueDate") or row.get("due_date") or "")[:32],
        "BillDate": str(row.get("BillDate") or row.get("bill_date") or "")[:32],
        "Bucket": str(row.get("Bucket") or row.get("aging_bucket") or "Current")[:32],
    }


def write_payroll_export(
    rows: list[dict[str, Any]] | None = None,
    *,
    destination: Path | None = None,
    period: str | None = None,
    empty_batch: bool = False,
    filename: str = PAYROLL_FILENAME,
) -> dict[str, Any]:
    dest = Path(destination) if destination else quickbooks_import_dir()
    period_default = str(period or datetime.now(timezone.utc).strftime("%Y-%m")).strip()
    normalized: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        norm = _normalize_payroll_input(row, period_default=period_default)
        if norm:
            normalized.append(norm)

    if empty_batch and not normalized:
        text = _rows_to_csv(PAYROLL_FIELDS, [])
        written = _atomic_write_text(dest / filename, text)
        meta = {
            "batchEmpty": True,
            "datasetKey": "quickbooks.payroll",
            "period": period_default,
            "at": _utc_now(),
            "honesty": "empty_not_zero",
            "note": "Header-only payroll export — no invented wages.",
            "sha256": written["sha256"],
        }
        meta_written = _atomic_write_text(dest / PAYROLL_EMPTY_META, json.dumps(meta, indent=2) + "\n")
        return {
            "ok": True,
            "datasetKey": "quickbooks.payroll",
            "emptyBatch": True,
            "rowCount": 0,
            "file": written,
            "meta": meta_written,
            "acceptedFilenames": list(QUICKBOOKS_PAYROLL_NAMES),
        }

    if not normalized:
        return {
            "ok": False,
            "error": "no_payroll_rows",
            "hint": "Pass payroll rows or emptyBatch=true. Do not invent wages.",
        }

    # Clear empty marker when real rows land
    empty_meta = dest / PAYROLL_EMPTY_META
    if empty_meta.is_file():
        try:
            empty_meta.unlink()
        except OSError:
            pass

    text = _rows_to_csv(PAYROLL_FIELDS, normalized)
    written = _atomic_write_text(dest / filename, text)
    return {
        "ok": True,
        "datasetKey": "quickbooks.payroll",
        "emptyBatch": False,
        "rowCount": len(normalized),
        "file": written,
        "acceptedFilenames": list(QUICKBOOKS_PAYROLL_NAMES),
    }


def write_ap_export(
    rows: list[dict[str, Any]] | None = None,
    *,
    destination: Path | None = None,
    period: str | None = None,
    empty_batch: bool = False,
    filename: str = AP_FILENAME,
) -> dict[str, Any]:
    dest = Path(destination) if destination else quickbooks_import_dir()
    period_default = str(period or datetime.now(timezone.utc).strftime("%Y-%m")).strip()
    normalized: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        norm = _normalize_ap_input(row, period_default=period_default)
        if norm:
            normalized.append(norm)

    if empty_batch and not normalized:
        text = _rows_to_csv(AP_FIELDS, [])
        written = _atomic_write_text(dest / filename, text)
        meta = {
            "batchEmpty": True,
            "datasetKey": "quickbooks.ap",
            "period": period_default,
            "at": _utc_now(),
            "honesty": "empty_not_zero",
            "note": "Header-only AP export — no invented balances.",
            "sha256": written["sha256"],
        }
        meta_written = _atomic_write_text(dest / AP_EMPTY_META, json.dumps(meta, indent=2) + "\n")
        return {
            "ok": True,
            "datasetKey": "quickbooks.ap",
            "emptyBatch": True,
            "rowCount": 0,
            "file": written,
            "meta": meta_written,
            "acceptedFilenames": list(QUICKBOOKS_AP_NAMES),
        }

    if not normalized:
        return {
            "ok": False,
            "error": "no_ap_rows",
            "hint": "Pass AP rows or emptyBatch=true. Do not invent balances.",
        }

    empty_meta = dest / AP_EMPTY_META
    if empty_meta.is_file():
        try:
            empty_meta.unlink()
        except OSError:
            pass

    text = _rows_to_csv(AP_FIELDS, normalized)
    written = _atomic_write_text(dest / filename, text)
    return {
        "ok": True,
        "datasetKey": "quickbooks.ap",
        "emptyBatch": False,
        "rowCount": len(normalized),
        "file": written,
        "acceptedFilenames": list(QUICKBOOKS_AP_NAMES),
    }


def write_qb_payroll_ap_exports(
    *,
    payroll_rows: list[dict[str, Any]] | None = None,
    ap_rows: list[dict[str, Any]] | None = None,
    empty_payroll: bool = False,
    empty_ap: bool = False,
    destination: Path | None = None,
    period: str | None = None,
) -> dict[str, Any]:
    payroll = write_payroll_export(
        payroll_rows, destination=destination, period=period, empty_batch=empty_payroll
    )
    ap = write_ap_export(ap_rows, destination=destination, period=period, empty_batch=empty_ap)
    return {
        "ok": bool(payroll.get("ok") or ap.get("ok")),
        "payroll": payroll,
        "ap": ap,
        "inbox": str(destination or quickbooks_import_dir()),
        "at": _utc_now(),
    }


def batch_empty_status(destination: Path | None = None) -> dict[str, Any]:
    dest = Path(destination) if destination else quickbooks_import_dir()
    out: dict[str, Any] = {"ok": True, "payroll": None, "ap": None}
    for key, name in (("payroll", PAYROLL_EMPTY_META), ("ap", AP_EMPTY_META)):
        path = dest / name
        if not path.is_file():
            continue
        try:
            out[key] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            out[key] = {"batchEmpty": True, "unreadable": True}
    return out
