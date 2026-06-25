from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.run_insurance_narrative_dry_run import (
    DEFAULT_EXPORT_DIR,
    build_dry_run_report,
    prepare_softdent_export_dir,
    run_insurance_narrative_dry_run,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_EXPORT_DIR = PROJECT_ROOT / "app/tests/fixtures/insurance_narratives/softdent"


@pytest.fixture
def fixed_timestamp() -> str:
    return "2026-06-25T12:00:00+00:00"


@pytest.fixture
def prepared_export_dir(tmp_path: Path) -> Path:
    return prepare_softdent_export_dir(FIXTURE_EXPORT_DIR, target_dir=tmp_path / "softdent_exports")


def test_dry_run_builds_packet_draft_export_from_synthetic_exports(
    prepared_export_dir: Path,
    fixed_timestamp: str,
) -> None:
    report = run_insurance_narrative_dry_run(
        export_dir=prepared_export_dir,
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-EXPORT-1",
        procedure_ids=["PROC-CROWN-30"],
        narrative_type="appeal",
        actor="local-operator",
        reviewer="local-reviewer",
        created_at=fixed_timestamp,
    )

    assert report["packet_id"]
    assert report["draft_id"]
    assert report["review_id"]
    assert report["export_id"]
    assert report["workflow_status"] == "export_created"
    assert report["dry_run"] is True
    assert report["no_submission"] is True


def test_dry_run_report_includes_required_fields(
    prepared_export_dir: Path,
    fixed_timestamp: str,
) -> None:
    report = run_insurance_narrative_dry_run(
        export_dir=prepared_export_dir,
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-EXPORT-1",
        procedure_ids=["PROC-CROWN-30"],
        narrative_type="appeal",
        actor="local-operator",
        reviewer="local-reviewer",
        created_at=fixed_timestamp,
    )

    for key in (
        "packet_id",
        "draft_id",
        "review_id",
        "export_id",
        "workflow_status",
        "source_fact_count",
        "missing_data_codes",
        "draft_status",
        "review_status",
        "export_format",
        "submission_status",
        "export_body",
        "warnings",
    ):
        assert key in report


def test_dry_run_submission_status_is_not_submitted(
    prepared_export_dir: Path,
    fixed_timestamp: str,
) -> None:
    report = run_insurance_narrative_dry_run(
        export_dir=prepared_export_dir,
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-EXPORT-1",
        procedure_ids=["PROC-CROWN-30"],
        narrative_type="appeal",
        actor="local-operator",
        reviewer="local-reviewer",
        created_at=fixed_timestamp,
    )

    assert report["submission_status"] == "not_submitted"
    assert "Not submitted" in (report["export_body"] or "")


def test_dry_run_export_body_includes_citation_fact_ids(
    prepared_export_dir: Path,
    fixed_timestamp: str,
) -> None:
    report = run_insurance_narrative_dry_run(
        export_dir=prepared_export_dir,
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-EXPORT-1",
        procedure_ids=["PROC-CROWN-30"],
        narrative_type="appeal",
        actor="local-operator",
        reviewer="local-reviewer",
        created_at=fixed_timestamp,
    )

    assert report["citation_fact_ids"]
    export_body = report["export_body"] or ""
    assert any(fact_id in export_body for fact_id in report["citation_fact_ids"])


def test_dry_run_preserves_missing_softdent_ar(
    prepared_export_dir: Path,
    fixed_timestamp: str,
) -> None:
    report = run_insurance_narrative_dry_run(
        export_dir=prepared_export_dir,
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-EXPORT-1",
        procedure_ids=["PROC-CROWN-30"],
        narrative_type="appeal",
        actor="local-operator",
        reviewer="local-reviewer",
        created_at=fixed_timestamp,
    )

    assert "missing_softdent_ar" in report["missing_data_codes"]


def test_dry_run_includes_claim_status_and_clinical_note_facts(
    prepared_export_dir: Path,
    fixed_timestamp: str,
) -> None:
    report = run_insurance_narrative_dry_run(
        export_dir=prepared_export_dir,
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-EXPORT-1",
        procedure_ids=["PROC-CROWN-30"],
        narrative_type="appeal",
        actor="local-operator",
        reviewer="local-reviewer",
        created_at=fixed_timestamp,
    )

    assert report["has_claim_status_facts"] is True
    assert report["has_clinical_note_facts"] is True
    assert report["source_fact_count"] > 0


def test_dry_run_report_exposes_no_raw_csv_rows(
    prepared_export_dir: Path,
    fixed_timestamp: str,
) -> None:
    report = run_insurance_narrative_dry_run(
        export_dir=prepared_export_dir,
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-EXPORT-1",
        procedure_ids=["PROC-CROWN-30"],
        narrative_type="appeal",
        actor="local-operator",
        reviewer="local-reviewer",
        created_at=fixed_timestamp,
    )

    blob = json.dumps(report)
    assert "raw_rows" not in blob
    assert "database_dump" not in blob
    assert "patient_ref,note_id,note_date" not in blob
    assert "patient_ref,claim_id,payer_name" not in blob


def test_cli_run_checker_defaults_false() -> None:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts/run_insurance_narrative_dry_run.py"), "--help"],
        capture_output=True,
        text=True,
        check=False,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0
    assert "--run-checker" in result.stdout


@patch("app.insurance_narratives.workflow.run_fast_review_check")
def test_dry_run_checker_path_can_be_mocked_without_live_model(
    mock_checker: MagicMock,
    prepared_export_dir: Path,
    fixed_timestamp: str,
) -> None:
    mock_checker.return_value = {
        "status": "ok",
        "review": {
            "missing_data": [],
            "citation_issues": [],
            "possible_invented_facts": [],
            "contradictions": [],
            "recommended_action": "proceed to human review",
            "ready_for_human_review": True,
        },
    }

    report = run_insurance_narrative_dry_run(
        export_dir=prepared_export_dir,
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-EXPORT-1",
        procedure_ids=["PROC-CROWN-30"],
        narrative_type="appeal",
        actor="local-operator",
        reviewer="local-reviewer",
        run_checker=True,
        created_at=fixed_timestamp,
    )

    mock_checker.assert_called_once()
    assert report["checker_opt_in"] is True
    assert report["checker_summary"] is not None
    assert report["checker_summary"]["checker_status"] == "ok"


@patch("app.insurance_narratives.workflow.run_fast_review_check")
def test_dry_run_without_checker_does_not_invoke_fast_review(
    mock_checker: MagicMock,
    prepared_export_dir: Path,
    fixed_timestamp: str,
) -> None:
    run_insurance_narrative_dry_run(
        export_dir=prepared_export_dir,
        patient_ref="CHART-EXPORT",
        claim_id="CLAIM-EXPORT-1",
        procedure_ids=["PROC-CROWN-30"],
        narrative_type="appeal",
        actor="local-operator",
        reviewer="local-reviewer",
        run_checker=False,
        created_at=fixed_timestamp,
    )
    mock_checker.assert_not_called()


def test_build_dry_run_report_without_export_when_blocked(fixed_timestamp: str) -> None:
    from app.insurance_narratives import create_insurance_narrative_draft_workflow

    draft_result = create_insurance_narrative_draft_workflow(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        procedure_ids=["PROC-CROWN-BUILDUP-3"],
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        run_checker=False,
    )

    report = build_dry_run_report(draft_result=draft_result, export_result=None, run_checker=False)
    assert report["draft_status"] == "blocked_missing_data"
    assert report["export_id"] is None
    assert report["submission_status"] == "not_submitted"
