from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "process_financial_document.py"
SPEC = importlib.util.spec_from_file_location("process_financial_document", MODULE_PATH)
assert SPEC and SPEC.loader
process_financial_document = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = process_financial_document
SPEC.loader.exec_module(process_financial_document)


def test_normalize_vendor_name_handles_lowercase_l_confusion() -> None:
    assert process_financial_document.normalize_vendor_name("GLlDEWELL LABORATORIES") == "Glidewell"


def test_normalize_vendor_name_handles_zero_to_letter_confusion() -> None:
    assert process_financial_document.normalize_vendor_name("BI0H0RIZ0NS") == "BioHorizons"


def test_normalize_vendor_name_handles_five_to_letter_confusion() -> None:
    assert process_financial_document.normalize_vendor_name("5TRAUMANN") == "Straumann"


def test_normalize_vendor_name_handles_alias_after_digit_cleanup() -> None:
    assert process_financial_document.normalize_vendor_name("ADEC") == "A-dec"


def test_normalize_invoice_number_reconciles_suffix_with_document_date() -> None:
    assert process_financial_document.normalize_invoice_number("INV2026:0618", document_date="06/16/2026") == "INV-2026-0616"


def test_normalize_invoice_number_applies_vendor_layout_rule() -> None:
    assert process_financial_document.normalize_invoice_number(
        "HS2026:0618",
        document_date="06/16/2026",
        vendor_name="Henry Schein Dental",
    ) == "HS-2026-0616"


def test_detect_invoice_number_uses_full_invoice_line_and_vendor_rule() -> None:
    assert process_financial_document.detect_invoice_number(
        ["Invoice SCANNED2026:0618"],
        "Invoice SCANNED2026:0618",
        document_date="06/16/2026",
        vendor_name="Prairie Dental Supply",
    ) == "SCANNED-2026-0616"