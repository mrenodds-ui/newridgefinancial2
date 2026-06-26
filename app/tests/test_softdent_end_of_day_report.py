from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

import app.hal.financial_tools as financial_tools
from app.hal.softdent_draft_models import SoftDentDraftArtifact, SoftDentDraftRequest
from app.hal.softdent_draft_service import create_softdent_draft
from app.hal.softdent_end_of_day_report import (
    MISSING_SOFTDENT_EOD_REPORT_DATE,
    SoftDentEndOfDayReportAdapter,
    _working_days_elapsed,
)
from app.hal.softdent_packet_models import (
    SoftDentLocalPacketRequest,
    SoftDentPacketApprovalAttestation,
)
from app.hal.softdent_packet_service import create_softdent_local_packet
from app.hal.softdent_read_broker import (
    SOFTDENT_CLINICAL_READ,
    SOFTDENT_LEDGER_READ,
    SOFTDENT_NARRATIVE_DRAFT,
    SOFTDENT_PATIENT_READ,
    SOFTDENT_READ,
    SoftDentReadBroker,
)
from app.hal.softdent_read_models import MISSING_SOFTDENT_AR
from app.services import get_softdent_data_coverage, get_softdent_end_of_day_ar_source_status


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "softdent_eod"
SUCCESS_REPORT = FIXTURE_DIR / "eod_success_last_page.txt"
STALE_REPORT = FIXTURE_DIR / "eod_stale_report.txt"
MISSING_AR_REPORT = FIXTURE_DIR / "eod_missing_ar.txt"
AMBIGUOUS_AR_REPORT = FIXTURE_DIR / "eod_ambiguous_ar.txt"
NEGATIVE_VALUES_REPORT = FIXTURE_DIR / "eod_negative_values.txt"
LIMITED_RECONCILE_REPORT = FIXTURE_DIR / "eod_limited_reconcile.txt"
DAYSHEET_REPORT = FIXTURE_DIR / "eod_daysheet_last_page.txt"


@pytest.fixture(autouse=True)
def _runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SOFTDENT_END_OF_DAY_REPORT_PATH", raising=False)
    monkeypatch.delenv("SOFTDENT_END_OF_DAY_REPORT_DIR", raising=False)
    monkeypatch.setenv("SOFTDENT_EOD_AR_MAX_AGE_DAYS", "2")
    runtime_dir = tmp_path / f"hal-{uuid4().hex}"
    monkeypatch.setenv("HAL_ALLOWED_BASE_PATH", str(runtime_dir))
    monkeypatch.setenv("HAL_SQLITE_PATH", str(runtime_dir / "hal_test.sqlite3"))


def _patch_patient_exports(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        financial_tools,
        "load_softdent_claim_rows",
        lambda: [
            {
                "PatientName": "John Doe",
                "MRN": "778899",
                "ClaimId": "CLM-1001",
                "ClaimStatus": "Denied",
                "Payer": "Delta Dental",
                "Procedure": "Crown buildup",
                "ServiceDate": "2026-06-01",
                "DenialReason": "Additional narrative requested",
                "ClaimAmount": 915.4,
            }
        ],
    )
    monkeypatch.setattr(
        financial_tools,
        "load_softdent_clinical_note_rows",
        lambda: [
            {
                "PatientName": "John Doe",
                "MRN": "778899",
                "NoteId": "NOTE-1",
                "NoteDate": "2026-06-01",
                "Procedure": "Crown buildup",
                "ClinicalNote": "Fractured cusp with recurrent decay.",
            }
        ],
    )
    monkeypatch.setattr(financial_tools, "load_softdent_ar_rows", lambda: [])
    monkeypatch.setattr(
        financial_tools,
        "get_softdent_claim_source_status",
        lambda: {"available": True, "source_backend": "exports", "source_file": "softdent_claims_export.csv"},
    )
    monkeypatch.setattr(
        financial_tools,
        "get_softdent_clinical_note_source_status",
        lambda: {"available": True, "source_backend": "exports", "source_file": "softdent_notes_export.csv"},
    )


def _ledger_roles() -> set[str]:
    return {
        SOFTDENT_READ,
        SOFTDENT_PATIENT_READ,
        SOFTDENT_CLINICAL_READ,
        SOFTDENT_NARRATIVE_DRAFT,
        SOFTDENT_LEDGER_READ,
    }


def _attestation() -> SoftDentPacketApprovalAttestation:
    return SoftDentPacketApprovalAttestation(
        approved_by="Office Manager",
        approval_note="Reviewed locally.",
        attestation_checked=True,
        acknowledged_local_only=True,
        acknowledged_not_submitted=True,
        acknowledged_no_softdent_writeback=True,
        acknowledged_no_external_delivery=True,
    )


def test_parser_extracts_last_page_ar_fields_without_raw_report_text() -> None:
    summary = SoftDentEndOfDayReportAdapter().parse_report(SUCCESS_REPORT)
    public_payload = summary.to_public_dict()

    assert summary.available is True
    assert summary.parse_status == "available"
    assert summary.report_date == "2026-06-26"
    assert summary.total_ar == Decimal("128450.75")
    assert summary.patient_ar == Decimal("42150.25")
    assert summary.insurance_ar == Decimal("86300.50")
    assert summary.aging_buckets["90+"] == Decimal("2500.00")
    assert summary.credits == Decimal("-1250.00")
    assert summary.collection_total == Decimal("3980.00")
    assert summary.production_total == Decimal("4250.00")
    assert summary.page_number == 2
    assert summary.source_refs == [
        "softdent_eod:2026-06-26:last_page:ar_summary",
        "softdent_eod:2026-06-26:last_page:aging_buckets",
    ]
    assert "Accounts Receivable Summary" not in str(public_payload)


def test_parser_labels_stale_and_preserves_missing_ar() -> None:
    summary = SoftDentEndOfDayReportAdapter().parse_report(STALE_REPORT)

    assert summary.available is False
    assert summary.parse_status == "stale"
    assert summary.freshness_status == "stale"
    assert summary.total_ar == Decimal("95000.00")
    assert MISSING_SOFTDENT_AR in summary.missing_data_codes
    assert summary.stale_reason


def test_parser_rejects_missing_ar_ambiguous_and_missing_date(tmp_path: Path) -> None:
    missing_ar = SoftDentEndOfDayReportAdapter().parse_report(MISSING_AR_REPORT)
    assert missing_ar.available is False
    assert MISSING_SOFTDENT_EOD_REPORT_DATE in missing_ar.missing_data_codes
    assert MISSING_SOFTDENT_AR in missing_ar.missing_data_codes

    ambiguous_path = tmp_path / "daily_end_of_day_2026-06-26.txt"
    ambiguous_path.write_text(AMBIGUOUS_AR_REPORT.read_text(encoding="utf-8"), encoding="utf-8")
    ambiguous = SoftDentEndOfDayReportAdapter().parse_report(ambiguous_path)
    assert ambiguous.available is False
    assert ambiguous.parse_status == "invalid"
    assert MISSING_SOFTDENT_AR in ambiguous.missing_data_codes

    no_date_path = tmp_path / "eod_no_date.txt"
    no_date_path.write_text(
        "SoftDent Daily End-of-Day Report\n\nPage 1 of 1\nAccounts Receivable Summary\nTotal A/R: $100.00\n",
        encoding="utf-8",
    )
    no_date = SoftDentEndOfDayReportAdapter().parse_report(no_date_path)
    assert no_date.available is False
    assert MISSING_SOFTDENT_EOD_REPORT_DATE in no_date.missing_data_codes


def test_parser_preserves_negative_values_and_limited_reconciliation() -> None:
    negative = SoftDentEndOfDayReportAdapter().parse_report(NEGATIVE_VALUES_REPORT)
    assert negative.available is True
    assert negative.total_ar == Decimal("-12345.67")
    assert negative.patient_ar == Decimal("-2345.67")
    assert negative.credits == Decimal("-500.00")

    limited = SoftDentEndOfDayReportAdapter().parse_report(LIMITED_RECONCILE_REPORT)
    assert limited.available is True
    assert limited.parse_status == "limited"
    assert any("reconcile" in limitation.lower() for limitation in limited.limitations)


def test_parser_extracts_daysheet_new_receivables_total_from_last_page() -> None:
    summary = SoftDentEndOfDayReportAdapter().parse_report(DAYSHEET_REPORT)

    assert summary.available is True
    assert summary.report_date == "2026-06-26"
    assert summary.total_ar == Decimal("73143.91")
    assert summary.patient_ar is None
    assert summary.insurance_ar is None
    assert summary.page_number == 2
    assert summary.page_count == 2
    assert "Previous Receivables Total" not in str(summary.to_public_dict())


def test_inventory_and_source_status_use_explicit_path_and_latest_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SOFTDENT_END_OF_DAY_REPORT_PATH", str(SUCCESS_REPORT))
    inventory = SoftDentEndOfDayReportAdapter().inventory_reports()
    assert inventory[0].source_file == SUCCESS_REPORT.name
    assert str(SUCCESS_REPORT.parent) not in inventory[0].source_file

    source_status = get_softdent_end_of_day_ar_source_status()
    assert source_status["available"] is True
    assert source_status["source_file"] == SUCCESS_REPORT.name
    assert source_status["report_date"] == "2026-06-26"

    monkeypatch.delenv("SOFTDENT_END_OF_DAY_REPORT_PATH", raising=False)
    report_dir = tmp_path / "eod"
    report_dir.mkdir()
    (report_dir / "notes.docx").write_text("unsupported", encoding="utf-8")
    old_report = report_dir / "daily_end_of_day_2026-06-20.txt"
    new_report = report_dir / "daily_end_of_day_2026-06-26.txt"
    old_report.write_text(SUCCESS_REPORT.read_text(encoding="utf-8").replace("06/26/2026", "06/20/2026"), encoding="utf-8")
    new_report.write_text(SUCCESS_REPORT.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("SOFTDENT_END_OF_DAY_REPORT_DIR", str(report_dir))

    latest = SoftDentEndOfDayReportAdapter().parse_latest_ar_summary()
    assert latest.report_date == "2026-06-26"
    assert latest.source_file == "daily_end_of_day_2026-06-26.txt"
    assert all(item.source_file != "notes.docx" for item in SoftDentEndOfDayReportAdapter().inventory_reports())


def test_coverage_row_reports_eod_ar_without_raw_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOFTDENT_END_OF_DAY_REPORT_PATH", str(SUCCESS_REPORT))
    coverage = get_softdent_data_coverage()

    eod_row = next(row for row in coverage["rows"] if row["key"] == "dailyEndOfDayAr")
    assert eod_row["status"] == "available"
    assert eod_row["sourceFile"] == SUCCESS_REPORT.name
    assert eod_row["lastPeriod"] == "2026-06-26"
    assert "Accounts Receivable Summary" not in str(eod_row)


def test_broker_role_gate_and_preserves_patient_ledger_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOFTDENT_END_OF_DAY_REPORT_PATH", str(SUCCESS_REPORT))
    broker = SoftDentReadBroker()

    unauthorized = broker.get_end_of_day_ar_summary(roles={SOFTDENT_READ})
    assert unauthorized.available is False
    assert MISSING_SOFTDENT_AR in unauthorized.missing_data_codes

    authorized = broker.get_end_of_day_ar_summary(roles={SOFTDENT_READ, SOFTDENT_LEDGER_READ})
    assert authorized.available is True
    assert authorized.total_ar == Decimal("128450.75")

    ledger = broker.get_ledger_context("John Doe", roles={SOFTDENT_READ, SOFTDENT_LEDGER_READ}, write_audit=False)
    assert ledger.available is False
    assert MISSING_SOFTDENT_AR in ledger.missing_data_codes
    assert ledger.total_ar is None


def test_draft_and_packet_include_verified_report_ar_source_refs(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_patient_exports(monkeypatch)
    monkeypatch.setenv("SOFTDENT_END_OF_DAY_REPORT_PATH", str(SUCCESS_REPORT))

    draft = create_softdent_draft(
        SoftDentDraftRequest(
            patient_query="John Doe",
            draft_type="internal_patient_summary",
            include_clinical_context=True,
            include_ledger_context=True,
        ),
        actor="hal_operator",
        roles=_ledger_roles(),
    )

    assert MISSING_SOFTDENT_AR not in draft.missing_data_codes
    assert any("Daily End-of-Day report A/R" in item for item in draft.checklist_items)
    assert "softdent_eod:2026-06-26:last_page:ar_summary" in draft.source_fact_refs

    packet = create_softdent_local_packet(
        SoftDentLocalPacketRequest(
            draft_artifact=SoftDentDraftArtifact.model_validate(draft.model_dump()),
            packet_type="patient_claim_review_packet",
        ),
        actor="hal_operator",
        roles=_ledger_roles(),
        approval_attestation=_attestation(),
    )

    assert "softdent_eod:2026-06-26:last_page:ar_summary" in packet.source_fact_refs
    assert packet.submission_status == "not_submitted"


def test_draft_keeps_missing_ar_for_stale_report(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_patient_exports(monkeypatch)
    monkeypatch.setenv("SOFTDENT_END_OF_DAY_REPORT_PATH", str(STALE_REPORT))

    draft = create_softdent_draft(
        SoftDentDraftRequest(
            patient_query="John Doe",
            draft_type="internal_patient_summary",
            include_clinical_context=True,
            include_ledger_context=True,
        ),
        actor="hal_operator",
        roles=_ledger_roles(),
    )

    assert MISSING_SOFTDENT_AR in draft.missing_data_codes
    assert any("stale" in limitation.lower() for limitation in draft.limitations)
    assert "$0.00" not in " ".join([draft.body, *draft.checklist_items, *draft.limitations])


# --- Business-day (Mon-Thu) freshness -------------------------------------

def test_working_days_elapsed_ignores_closed_friday_through_sunday() -> None:
    thursday = date(2026, 6, 25)
    # Office is closed Fri/Sat/Sun, so no working days elapse across the weekend.
    assert _working_days_elapsed(thursday, date(2026, 6, 26)) == 0  # Friday
    assert _working_days_elapsed(thursday, date(2026, 6, 27)) == 0  # Saturday
    assert _working_days_elapsed(thursday, date(2026, 6, 28)) == 0  # Sunday
    assert _working_days_elapsed(thursday, date(2026, 6, 29)) == 1  # Monday
    assert _working_days_elapsed(thursday, date(2026, 6, 30)) == 2  # Tuesday
    assert _working_days_elapsed(thursday, date(2026, 7, 1)) == 3  # Wednesday


def test_working_days_elapsed_future_report_is_zero() -> None:
    assert _working_days_elapsed(date(2026, 6, 30), date(2026, 6, 25)) == 0


def _freshness(report_date: str, today: date, monkeypatch: pytest.MonkeyPatch) -> tuple[str, str | None]:
    import app.hal.softdent_end_of_day_report as eod

    class _FixedDate(eod.date):
        @classmethod
        def today(cls):  # pragma: no cover - not used
            return today

    class _FixedDateTime(eod.datetime):
        @classmethod
        def now(cls, tz=None):
            return eod.datetime(today.year, today.month, today.day, tzinfo=tz)

    monkeypatch.setattr(eod, "datetime", _FixedDateTime)
    # modified time recent enough to not trip the file-mtime branch
    return eod._evaluate_freshness(report_date=report_date, modified_at_utc=today.isoformat())


def test_thursday_report_is_current_through_weekend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOFTDENT_EOD_AR_MAX_AGE_DAYS", "2")
    for viewed in (date(2026, 6, 26), date(2026, 6, 27), date(2026, 6, 28)):  # Fri/Sat/Sun
        status, reason = _freshness("2026-06-25", viewed, monkeypatch)
        assert status == "current", f"viewed {viewed} reason {reason}"


def test_thursday_report_goes_stale_after_two_working_days(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOFTDENT_EOD_AR_MAX_AGE_DAYS", "2")
    # Monday (1) and Tuesday (2) remain current; Wednesday (3) is stale.
    assert _freshness("2026-06-25", date(2026, 6, 29), monkeypatch)[0] == "current"
    assert _freshness("2026-06-25", date(2026, 6, 30), monkeypatch)[0] == "current"
    status, reason = _freshness("2026-06-25", date(2026, 7, 1), monkeypatch)
    assert status == "stale"
    assert "working day" in (reason or "")
