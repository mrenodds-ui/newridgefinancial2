from pathlib import Path

from local_ai_finance import main as local_ai_finance


def test_normalize_invoice_extraction_result_fills_pdf_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(local_ai_finance, "WORKSPACE_DIR", tmp_path)
    pdf_path = tmp_path / "invoice.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")
    monkeypatch.setattr(
        local_ai_finance,
        "_extract_pdf_sidecar_text",
        lambda path: "Prairie Dental Supply\nDate 08/16/2028\nSubtotal 410.00\nSales Tax 33.00\nTotal 443.00\n",
    )
    payload = {
        "vendor_name": "",
        "invoice_total": 0,
        "invoice_date": "",
        "due_date": "",
        "currency": "",
        "flag_for_review": False,
        "review_reason": "",
    }

    normalized = local_ai_finance.normalize_invoice_extraction_result(payload, filename="invoice.pdf")

    assert normalized["vendor_name"] == "Prairie Dental Supply"
    assert normalized["invoice_total"] == 443.0
    assert normalized["invoice_date"] == "2028-08-16"
    assert normalized["due_date"] == "2028-08-16"
    assert normalized["currency"] == "USD"


def test_apply_invoice_extraction_guardrails_flags_future_dates() -> None:
    payload = {
        "vendor_name": "Prairie Dental Supply",
        "invoice_total": 443.0,
        "invoice_date": "2028-08-16",
        "due_date": "2028-08-16",
        "currency": "USD",
        "flag_for_review": False,
        "review_reason": "",
    }

    guarded = local_ai_finance.apply_invoice_extraction_guardrails(payload)

    assert guarded["flag_for_review"] is True
    assert "invoice_date is in the future" in guarded["review_reason"]
    assert "due_date is in the future" in guarded["review_reason"]