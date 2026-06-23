from __future__ import annotations

from datetime import datetime, timezone
import os
import sqlite3
from pathlib import Path

import pytest

from app import services


def _seed_local_accounting_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE local_accounting_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                source_name TEXT NOT NULL,
                sha256 TEXT NOT NULL UNIQUE,
                processed_at_utc TEXT NOT NULL,
                extractor TEXT NOT NULL,
                document_type TEXT NOT NULL,
                vendor_name TEXT,
                invoice_number TEXT,
                document_date TEXT,
                total_amount REAL,
                subtotal_amount REAL,
                tax_amount REAL,
                currency TEXT NOT NULL,
                text_preview TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                correction_flags_json TEXT NOT NULL DEFAULT '[]',
                confidence_label TEXT NOT NULL DEFAULT 'manual review',
                review_required INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO local_accounting_documents (
                source_path,
                source_name,
                sha256,
                processed_at_utc,
                extractor,
                document_type,
                vendor_name,
                invoice_number,
                document_date,
                total_amount,
                subtotal_amount,
                tax_amount,
                currency,
                text_preview,
                raw_text,
                correction_flags_json,
                confidence_label,
                review_required
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "C:/docs/review-invoice.pdf",
                    "review-invoice.pdf",
                    "sha-review",
                    "2026-06-16T18:00:00+00:00",
                    "plain_text",
                    "invoice",
                    "Glidewell",
                    "GL-2026-0616",
                    "06/16/2026",
                    221.40,
                    205.00,
                    16.40,
                    "USD",
                    "Glidewell invoice preview",
                    "GLlDEWELL LABORATORIES Invoice GL2026:0616",
                    '["vendor_normalized","invoice_corrected"]',
                    "manual review",
                    1,
                ),
                (
                    "C:/docs/receipt.pdf",
                    "receipt.pdf",
                    "sha-receipt",
                    "2026-06-16T17:00:00+00:00",
                    "plain_text",
                    "receipt",
                    "Safco Dental",
                    "RCPT-1001",
                    "06/15/2026",
                    45.00,
                    41.00,
                    4.00,
                    "USD",
                    "Safco receipt preview",
                    "SAFCO DENTAL Receipt RCPT-1001",
                    '[]',
                    "high confidence",
                    0,
                ),
            ],
        )
        connection.commit()


def test_list_local_accounting_documents_filters_review_only_and_document_type(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "hal_local.sqlite3"
    _seed_local_accounting_db(db_path)
    monkeypatch.setattr(services, "_local_accounting_db_path", lambda: db_path)

    payload = services.list_local_accounting_documents(limit=10, document_type="invoice", review_only=True)

    assert payload["count"] == 1
    assert payload["review_only"] is True
    assert payload["document_type"] == "invoice"
    assert payload["items"][0]["source_name"] == "review-invoice.pdf"
    assert payload["items"][0]["review_required"] is True
    assert payload["items"][0]["correction_flags"] == ["vendor_normalized", "invoice_corrected"]


def test_list_local_accounting_documents_excludes_non_review_receipts_when_review_only_enabled(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "hal_local.sqlite3"
    _seed_local_accounting_db(db_path)
    monkeypatch.setattr(services, "_local_accounting_db_path", lambda: db_path)

    payload = services.list_local_accounting_documents(limit=10, document_type="receipt", review_only=True)

    assert payload["count"] == 0
    assert payload["items"] == []


def test_get_local_accounting_documents_status_reports_latest_processed_at(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "hal_local.sqlite3"
    _seed_local_accounting_db(db_path)
    monkeypatch.setattr(services, "_local_accounting_db_path", lambda: db_path)

    payload = services.get_local_accounting_documents_status()

    assert payload["available"] is True
    assert payload["source_backend"] == "sqlite"
    assert payload["source_file"] == "hal_local.sqlite3"
    assert payload["document_count"] == 2
    assert payload["modified_at_utc"] == "2026-06-16T18:00:00+00:00"


def test_get_quickbooks_source_status_prefers_matching_import_file(tmp_path: Path, monkeypatch) -> None:
    import_dir = tmp_path / "quickbooks-imports"
    import_dir.mkdir(parents=True, exist_ok=True)
    revenue_file = import_dir / "quickbooks_revenue.csv"
    revenue_file.write_text("TotalIncome\n2000\n", encoding="utf-8")
    expected_timestamp = datetime(2026, 6, 18, 13, 45, tzinfo=timezone.utc).timestamp()
    os.utime(revenue_file, (expected_timestamp, expected_timestamp))

    monkeypatch.setenv("QUICKBOOKS_IMPORT_DIR", str(import_dir))
    monkeypatch.delenv("QUICKBOOKS_REVENUE_EXPORT_PATH", raising=False)

    payload = services.get_quickbooks_source_status("revenue")

    assert payload["available"] is True
    assert payload["source_backend"] == "csv"
    assert payload["source_file"] == "quickbooks_revenue.csv"
    assert payload["modified_at_utc"] == "2026-06-18T13:45:00+00:00"


def test_local_accounting_db_path_rejects_out_of_bounds_override(tmp_path: Path, monkeypatch) -> None:
    outside_db_path = tmp_path.parent / f"{tmp_path.name}-outside.sqlite3"
    monkeypatch.setenv("HAL_ALLOWED_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("LOCAL_AI_ACCOUNTING_DB_PATH", str(outside_db_path))

    with pytest.raises(ValueError, match="Local accounting database path is outside HAL allowed base path"):
        services._local_accounting_db_path()