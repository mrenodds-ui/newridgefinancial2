"""QB payroll/AP export-to-inbox pack tests."""

from __future__ import annotations

from pathlib import Path

from nr2_contracts.qb_export_inbox import (
    batch_empty_status,
    write_ap_export,
    write_payroll_export,
    write_qb_payroll_ap_exports,
)
import nr2_contracts.qb_payroll as payroll_pack


def test_write_payroll_and_ap_rows(tmp_path: Path):
    payroll = write_payroll_export(
        [{"Period": "2026-07", "Employee": "Staff A", "GrossPay": "100.00", "NetPay": "80.00"}],
        destination=tmp_path,
    )
    assert payroll["ok"] is True
    assert payroll["rowCount"] == 1
    path = tmp_path / "quickbooks_payroll_detail.csv"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "Staff A" in text
    assert "100.00" in text

    ap = write_ap_export(
        [{"Vendor": "Supply Co", "Balance": "55.25", "DueDate": "2026-07-20"}],
        destination=tmp_path,
    )
    assert ap["ok"] is True
    assert (tmp_path / "quickbooks_ap_aging.csv").is_file()


def test_empty_batch_honesty(tmp_path: Path, monkeypatch):
    out = write_qb_payroll_ap_exports(
        empty_payroll=True,
        empty_ap=True,
        destination=tmp_path,
        period="2026-07",
    )
    assert out["ok"] is True
    assert out["payroll"]["emptyBatch"] is True
    assert out["ap"]["emptyBatch"] is True
    assert (tmp_path / "quickbooks_payroll.batch_empty.json").is_file()
    payroll_csv = (tmp_path / "quickbooks_payroll_detail.csv").read_text(encoding="utf-8")
    assert "Period" in payroll_csv
    assert "Staff" not in payroll_csv

    monkeypatch.setattr(
        "nr2_contracts.qb_export_inbox.quickbooks_import_dir",
        lambda: tmp_path,
    )
    monkeypatch.setattr(payroll_pack, "_section_rows", lambda bundle, key: [])

    gap = payroll_pack.assess_payroll_ap_gap({})
    assert gap["payrollPending"] is False
    assert gap["apPending"] is False
    assert gap["payrollEmptyBatch"] is True
    assert gap["apEmptyBatch"] is True
    assert gap["honesty"] == "empty_not_zero"
    status = batch_empty_status(tmp_path)
    assert status["payroll"]["batchEmpty"] is True


def test_reject_invented_empty_without_flag(tmp_path: Path):
    bad = write_payroll_export([], destination=tmp_path, empty_batch=False)
    assert bad["ok"] is False
    assert bad["error"] == "no_payroll_rows"
