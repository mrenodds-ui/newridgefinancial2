from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from app.insurance_narratives import (
    FixtureInsuranceNarrativeDataAdapter,
    InsuranceNarrativeDataAdapter,
    InsuranceNarrativePacketInputs,
    InsuranceNarrativeScope,
    LocalInsuranceNarrativeDataAdapter,
    SoftDentExportFileInsuranceNarrativeAdapter,
    build_insurance_narrative_case_packet,
    create_insurance_narrative_draft_workflow,
    default_fixture_adapter,
    softdent_export_file_adapter,
)
from app.insurance_narratives.data_adapter import missing_data_item
from app.insurance_narratives.schemas import PatientCaseSummary

FIXTURE_EXPORT_DIR = Path(__file__).resolve().parent / "fixtures" / "insurance_narratives" / "softdent"
FIXTURE_CLAIMS_CSV = FIXTURE_EXPORT_DIR / "claims_export_fixture.csv"
FIXTURE_PROCEDURES_CSV = FIXTURE_EXPORT_DIR / "softdent_procedures_export.csv"


@pytest.fixture
def fixed_timestamp() -> str:
    return "2026-06-25T12:00:00+00:00"


def _build_sample_packet(*, created_at: str, adapter: InsuranceNarrativeDataAdapter | None = None) -> object:
    return build_insurance_narrative_case_packet(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        procedure_ids=["PROC-CROWN-BUILDUP-3"],
        date_range=None,
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=created_at,
        adapter=adapter,
    )


def test_fixture_adapter_preserves_existing_packet_output(fixed_timestamp: str) -> None:
    default_packet = _build_sample_packet(created_at=fixed_timestamp)
    explicit_fixture = _build_sample_packet(
        created_at=fixed_timestamp,
        adapter=FixtureInsuranceNarrativeDataAdapter(),
    )

    assert default_packet.model_dump() == explicit_fixture.model_dump()
    assert default_packet.audit_metadata.adapter_name == "fixture"
    assert default_packet.audit_metadata.source_mode == "fixture"


def test_builder_accepts_explicit_adapter(fixed_timestamp: str) -> None:
    adapter = default_fixture_adapter()
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        adapter=adapter,
    )

    assert packet.claim is not None
    assert packet.claim.claim_id == "CLAIM-1001"
    assert packet.audit_metadata.adapter_name == adapter.adapter_name


@dataclass
class ScopeRecordingAdapter:
    """Test double that records scope and returns minimal bounded inputs."""

    adapter_name: str = "scope_recorder"
    source_mode: str = "test"
    received_scopes: list[InsuranceNarrativeScope] = field(default_factory=list)
    return_inputs: InsuranceNarrativePacketInputs | None = None

    def fetch_packet_inputs(self, scope: InsuranceNarrativeScope) -> InsuranceNarrativePacketInputs:
        self.received_scopes.append(scope)
        if self.return_inputs is not None:
            return self.return_inputs
        return InsuranceNarrativePacketInputs(
            patient=PatientCaseSummary(
                patient_ref=scope.patient_ref,
                chart_ref=scope.patient_ref,
                label=f"Patient ref {scope.patient_ref}",
            ),
            missing_data=[missing_data_item("missing_patient_record")],
        )


def test_explicit_adapter_receives_only_scoped_inputs(fixed_timestamp: str) -> None:
    recorder = ScopeRecordingAdapter()
    build_insurance_narrative_case_packet(
        patient_ref="CHART-B",
        claim_id="CLAIM-2002",
        procedure_ids=["PROC-X"],
        date_range=("2026-01-01", "2026-01-31"),
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        adapter=recorder,
    )

    assert len(recorder.received_scopes) == 1
    scope = recorder.received_scopes[0]
    assert scope.patient_ref == "CHART-B"
    assert scope.claim_id == "CLAIM-2002"
    assert scope.procedure_ids == ["PROC-X"]
    assert scope.date_range == ("2026-01-01", "2026-01-31")
    assert scope.narrative_type == "denied_claim_resubmission"
    assert scope.actor == "operator@test"


def test_packet_has_no_raw_unrestricted_rows(fixed_timestamp: str) -> None:
    packet = _build_sample_packet(created_at=fixed_timestamp)
    dumped = packet.model_dump(mode="json")

    assert "raw_rows" not in dumped
    assert "database_dump" not in dumped
    assert "unrestricted" not in dumped
    blob = json.dumps(dumped)
    assert "PatientName" not in blob
    assert "MRN" not in blob


def test_missing_data_preserved_through_adapter(fixed_timestamp: str) -> None:
    packet = _build_sample_packet(created_at=fixed_timestamp)
    missing_codes = {item.code for item in packet.missing_data}

    assert "missing_softdent_ar" in missing_codes
    assert "missing_prior_auth" in missing_codes
    assert "missing_radiograph" in missing_codes


def test_local_adapter_returns_missing_data_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.get_softdent_claim_source_status",
        lambda: {"available": False},
    )
    monkeypatch.setattr("app.services.load_softdent_claim_rows", lambda: [])
    monkeypatch.setattr("app.services.load_softdent_clinical_note_rows", lambda: [])

    adapter = LocalInsuranceNarrativeDataAdapter()
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-LOCAL",
        claim_id="CLAIM-LOCAL-1",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        adapter=adapter,
    )

    missing_codes = {item.code for item in packet.missing_data}
    assert "missing_patient_record" in missing_codes
    assert "missing_softdent_ar" in missing_codes
    assert packet.source_facts == []
    assert packet.audit_metadata.adapter_name == "local_softdent_export"
    assert packet.audit_metadata.source_mode == "local_softdent"


def test_local_adapter_does_not_invent_facts_when_rows_match(
    monkeypatch: pytest.MonkeyPatch,
    fixed_timestamp: str,
) -> None:
    claim_rows = [
        {
            "MRN": "CHART-LOCAL",
            "ClaimId": "CLAIM-LOCAL-1",
            "ClaimStatus": "Denied",
            "Payer": "Test Payer",
            "Procedure": "Crown",
            "ServiceDate": "2026-06-01",
            "DenialReason": "Needs attachment",
            "ClaimAmount": 100.0,
        }
    ]
    monkeypatch.setattr(
        "app.services.get_softdent_claim_source_status",
        lambda: {
            "available": True,
            "source_file": "softdent_claims_export.csv",
            "source_backend": "csv",
        },
    )
    monkeypatch.setattr("app.services.load_softdent_claim_rows", lambda: claim_rows)
    monkeypatch.setattr("app.services.load_softdent_clinical_note_rows", lambda: [])

    adapter = LocalInsuranceNarrativeDataAdapter()
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-LOCAL",
        claim_id="CLAIM-LOCAL-1",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        adapter=adapter,
    )

    assert packet.claim is not None
    assert packet.claim.status == "Denied"
    assert packet.source_facts
    assert all(fact.fact_id for fact in packet.source_facts)
    assert all(fact.source_label for fact in packet.source_facts)
    assert all(fact.source_type for fact in packet.source_facts)
    assert any(fact.source_date == "2026-06-01" for fact in packet.source_facts)
    assert all("softdent_claims_export.csv" in fact.source_label for fact in packet.source_facts)
    assert all(not hasattr(fact, "raw_row") for fact in packet.source_facts)
    dumped = json.dumps(packet.model_dump(mode="json"))
    assert "raw_rows" not in dumped
    assert "PatientName" not in dumped


def test_local_adapter_scopes_claim_rows_by_procedure_and_date(
    monkeypatch: pytest.MonkeyPatch,
    fixed_timestamp: str,
) -> None:
    claim_rows = [
        {
            "MRN": "CHART-LOCAL",
            "ClaimId": "CLAIM-LOCAL-1",
            "ClaimStatus": "Denied",
            "Payer": "Test Payer",
            "Procedure": "Crown",
            "ServiceDate": "2026-06-01",
            "DenialReason": "Needs attachment",
            "ClaimAmount": 100.0,
        },
        {
            "MRN": "CHART-LOCAL",
            "ClaimId": "CLAIM-LOCAL-1",
            "ClaimStatus": "Denied",
            "Payer": "Test Payer",
            "Procedure": "Root canal",
            "ServiceDate": "2026-05-20",
            "DenialReason": "Needs attachment",
            "ClaimAmount": 200.0,
        },
        {
            "MRN": "OTHER-CHART",
            "ClaimId": "CLAIM-LOCAL-1",
            "ClaimStatus": "Denied",
            "Payer": "Other Payer",
            "Procedure": "Implant",
            "ServiceDate": "2026-06-01",
            "ClaimAmount": 300.0,
        },
    ]
    monkeypatch.setattr(
        "app.services.get_softdent_claim_source_status",
        lambda: {
            "available": True,
            "source_file": "softdent_claims_export.csv",
            "source_backend": "csv",
        },
    )
    monkeypatch.setattr("app.services.load_softdent_claim_rows", lambda: claim_rows)
    monkeypatch.setattr("app.services.load_softdent_clinical_note_rows", lambda: [])

    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-LOCAL",
        claim_id="CLAIM-LOCAL-1",
        procedure_ids=["PROC-CROWN202606011"],
        date_range=("2026-06-01", "2026-06-30"),
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        adapter=LocalInsuranceNarrativeDataAdapter(),
    )

    assert [procedure.description for procedure in packet.procedures] == ["Crown"]
    blob = json.dumps(packet.model_dump(mode="json"))
    assert "Root canal" not in blob
    assert "Implant" not in blob
    assert "Other Payer" not in blob


def test_local_adapter_does_not_emit_default_zero_claim_amount(
    monkeypatch: pytest.MonkeyPatch,
    fixed_timestamp: str,
) -> None:
    claim_rows = [
        {
            "MRN": "CHART-LOCAL",
            "ClaimId": "CLAIM-LOCAL-1",
            "ClaimStatus": "Denied",
            "Payer": "Test Payer",
            "Procedure": "Crown",
            "ServiceDate": "2026-06-01",
            "DenialReason": "Needs attachment",
        }
    ]
    monkeypatch.setattr(
        "app.services.get_softdent_claim_source_status",
        lambda: {"available": True, "source_file": "softdent_claims_export.csv"},
    )
    monkeypatch.setattr("app.services.load_softdent_claim_rows", lambda: claim_rows)
    monkeypatch.setattr("app.services.load_softdent_clinical_note_rows", lambda: [])

    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-LOCAL",
        claim_id="CLAIM-LOCAL-1",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        adapter=LocalInsuranceNarrativeDataAdapter(),
    )

    assert packet.claim is not None
    assert packet.claim.billed_amount is None
    assert all("Billed amount 0.00" not in fact.text for fact in packet.source_facts)


def test_missing_ar_stays_missing_never_zero(
    monkeypatch: pytest.MonkeyPatch,
    fixed_timestamp: str,
) -> None:
    packet = _build_sample_packet(created_at=fixed_timestamp)
    ar_item = next(item for item in packet.missing_data if item.code == "missing_softdent_ar")

    assert ar_item.blocking is False
    dumped = json.dumps(packet.model_dump(mode="json"))
    assert '"ar_total": 0' not in dumped
    assert '"accounts_receivable": 0' not in dumped

    monkeypatch.setattr(
        "app.services.get_softdent_claim_source_status",
        lambda: {"available": False},
    )
    monkeypatch.setattr("app.services.load_softdent_claim_rows", lambda: [])
    monkeypatch.setattr("app.services.load_softdent_clinical_note_rows", lambda: [])

    local_packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-LOCAL",
        claim_id="CLAIM-LOCAL-1",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        adapter=LocalInsuranceNarrativeDataAdapter(),
    )
    local_ar = next(item for item in local_packet.missing_data if item.code == "missing_softdent_ar")
    assert local_ar.code == "missing_softdent_ar"
    local_dumped = json.dumps(local_packet.model_dump(mode="json"))
    assert '"ar_total": 0' not in local_dumped


def test_audit_metadata_records_adapter_source_mode(
    monkeypatch: pytest.MonkeyPatch,
    fixed_timestamp: str,
) -> None:
    fixture_packet = _build_sample_packet(created_at=fixed_timestamp)
    assert fixture_packet.audit_metadata.adapter_name == "fixture"
    assert fixture_packet.audit_metadata.source_mode == "fixture"

    monkeypatch.setattr(
        "app.services.get_softdent_claim_source_status",
        lambda: {"available": False},
    )
    monkeypatch.setattr("app.services.load_softdent_claim_rows", lambda: [])
    monkeypatch.setattr("app.services.load_softdent_clinical_note_rows", lambda: [])

    local_packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-X",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        adapter=LocalInsuranceNarrativeDataAdapter(),
    )
    assert local_packet.audit_metadata.adapter_name == "local_softdent_export"
    assert local_packet.audit_metadata.source_mode == "local_softdent"


def test_workflow_accepts_adapter_without_breaking_safety(fixed_timestamp: str) -> None:
    result = create_insurance_narrative_draft_workflow(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        run_checker=False,
        adapter=FixtureInsuranceNarrativeDataAdapter(),
    )

    assert result.packet.audit_metadata.adapter_name == "fixture"
    assert result.draft.packet_id == result.packet.packet_id
    assert result.draft.approval_required is True
    assert result.export is None
    if result.draft.status == "blocked_missing_data":
        assert any(item.blocking for item in result.draft.missing_data)


@pytest.fixture
def export_fixture_dir(tmp_path: Path) -> Path:
    claims_src = FIXTURE_CLAIMS_CSV
    procedures_src = FIXTURE_PROCEDURES_CSV
    (tmp_path / "softdent_claims_export.csv").write_text(
        claims_src.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "softdent_procedures_export.csv").write_text(
        procedures_src.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return tmp_path


def test_softdent_export_adapter_reads_configured_directory_only(
    export_fixture_dir: Path,
    fixed_timestamp: str,
) -> None:
    adapter = SoftDentExportFileInsuranceNarrativeAdapter(export_dir=export_fixture_dir)
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-EXPORT-1",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        adapter=adapter,
    )

    assert adapter.export_dir == export_fixture_dir
    assert packet.audit_metadata.adapter_name == "softdent_export_file"
    assert packet.audit_metadata.source_mode == "export_file"
    assert packet.claim is not None
    assert packet.claim.claim_id == "CLAIM-EXPORT-1"
    assert packet.claim.status == "Denied"


def test_softdent_export_adapter_missing_files_emit_missing_data(
    tmp_path: Path,
    fixed_timestamp: str,
) -> None:
    adapter = SoftDentExportFileInsuranceNarrativeAdapter(export_dir=tmp_path)
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-EXPORT-1",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        adapter=adapter,
    )

    missing_codes = {item.code for item in packet.missing_data}
    assert "missing_softdent_claims_export" in missing_codes
    assert "missing_softdent_ar" in missing_codes
    assert packet.source_facts == []


def test_softdent_export_adapter_scoped_rows_produce_source_facts(
    export_fixture_dir: Path,
    fixed_timestamp: str,
) -> None:
    adapter = SoftDentExportFileInsuranceNarrativeAdapter(export_dir=export_fixture_dir)
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-EXPORT-1",
        procedure_ids=["PROC-CROWN-30"],
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        adapter=adapter,
    )

    assert packet.source_facts
    assert all(fact.source_type == "softdent" for fact in packet.source_facts)
    assert any("Claim CLAIM-EXPORT-1 status" in fact.text for fact in packet.source_facts)
    assert any("Crown buildup" in fact.text for fact in packet.source_facts)
    assert any(fact.source_label == "softdent_claims_export.csv" for fact in packet.source_facts)
    assert any(fact.source_label == "softdent_procedures_export.csv" for fact in packet.source_facts)


def test_softdent_export_adapter_ignores_non_matching_rows(
    export_fixture_dir: Path,
    fixed_timestamp: str,
) -> None:
    adapter = SoftDentExportFileInsuranceNarrativeAdapter(export_dir=export_fixture_dir)
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-EXPORT-1",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        adapter=adapter,
    )

    dumped = json.dumps(packet.model_dump(mode="json"))
    assert "CHART-OTHER" not in dumped
    assert "CLAIM-OTHER-9" not in dumped
    assert "PROC-OTHER" not in dumped


def test_softdent_export_adapter_no_patient_dump_or_db_access(
    export_fixture_dir: Path,
    fixed_timestamp: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_db_access(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("export adapter must not access database loaders")

    monkeypatch.setattr("app.services.load_softdent_claim_rows", _fail_db_access)
    monkeypatch.setattr("app.services.load_softdent_clinical_note_rows", _fail_db_access)

    adapter = SoftDentExportFileInsuranceNarrativeAdapter(export_dir=export_fixture_dir)
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-EXPORT-1",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        adapter=adapter,
    )

    dumped = packet.model_dump(mode="json")
    assert "raw_rows" not in dumped
    assert "database_dump" not in dumped
    blob = json.dumps(dumped)
    assert "PatientName" not in blob


def test_softdent_export_adapter_missing_ar_never_zero(
    export_fixture_dir: Path,
    fixed_timestamp: str,
) -> None:
    adapter = SoftDentExportFileInsuranceNarrativeAdapter(export_dir=export_fixture_dir)
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-EXPORT-1",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        adapter=adapter,
    )

    ar_item = next(item for item in packet.missing_data if item.code == "missing_softdent_ar")
    assert ar_item.blocking is False
    dumped = json.dumps(packet.model_dump(mode="json"))
    assert '"ar_total": 0' not in dumped
    assert '"accounts_receivable": 0' not in dumped


def test_softdent_export_adapter_malformed_csv_not_invented(
    tmp_path: Path,
    fixed_timestamp: str,
) -> None:
    (tmp_path / "softdent_claims_export.csv").write_bytes(b"\xff\xfe")
    adapter = SoftDentExportFileInsuranceNarrativeAdapter(export_dir=tmp_path)
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-EXPORT-1",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        adapter=adapter,
    )

    missing_codes = {item.code for item in packet.missing_data}
    assert "missing_softdent_claims_export" in missing_codes
    assert packet.source_facts == []


def test_softdent_export_adapter_missing_scoped_claim_row(
    export_fixture_dir: Path,
    fixed_timestamp: str,
) -> None:
    adapter = SoftDentExportFileInsuranceNarrativeAdapter(export_dir=export_fixture_dir)
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-NOT-FOUND",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        adapter=adapter,
    )

    missing_codes = {item.code for item in packet.missing_data}
    assert "missing_scoped_claim_row" in missing_codes
    assert packet.source_facts == []


def test_softdent_export_adapter_missing_scoped_procedure_rows(
    tmp_path: Path,
    fixed_timestamp: str,
) -> None:
    (tmp_path / "softdent_claims_export.csv").write_text(
        "patient_ref,claim_id,payer_name,service_date,claim_status,claim_amount,procedure_ids,source_report_date\n"
        "CHART-EXPORT,CLAIM-EXPORT-1,Delta Dental,2026-06-12,Denied,215.75,PROC-MISSING,2026-06-20\n",
        encoding="utf-8",
    )
    (tmp_path / "softdent_procedures_export.csv").write_text(
        "patient_ref,procedure_id,procedure_code,procedure_description,service_date,tooth,provider_label,source_report_date\n"
        "CHART-EXPORT,PROC-CROWN-30,D2950,Crown buildup,2026-06-12,30,Dr. Smith,2026-06-20\n",
        encoding="utf-8",
    )
    adapter = SoftDentExportFileInsuranceNarrativeAdapter(export_dir=tmp_path)
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-EXPORT-1",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        adapter=adapter,
    )

    missing_codes = {item.code for item in packet.missing_data}
    assert "missing_scoped_procedure_rows" in missing_codes


def test_builder_accepts_softdent_export_adapter_explicitly(
    export_fixture_dir: Path,
    fixed_timestamp: str,
) -> None:
    adapter = softdent_export_file_adapter(export_dir=export_fixture_dir)
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-EXPORT-1",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        adapter=adapter,
    )

    assert packet.audit_metadata.adapter_name == "softdent_export_file"
    assert packet.procedures
    assert packet.procedures[0].procedure_id == "PROC-CROWN-30"


def test_softdent_export_adapter_missing_procedures_file(
    tmp_path: Path,
    fixed_timestamp: str,
) -> None:
    claims_src = FIXTURE_CLAIMS_CSV
    (tmp_path / "softdent_claims_export.csv").write_text(
        claims_src.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    adapter = SoftDentExportFileInsuranceNarrativeAdapter(export_dir=tmp_path)
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-EXPORT-1",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        adapter=adapter,
    )

    missing_codes = {item.code for item in packet.missing_data}
    assert "missing_softdent_procedures_export" in missing_codes
    assert packet.claim is not None
    assert any("Claim CLAIM-EXPORT-1 status" in fact.text for fact in packet.source_facts)
