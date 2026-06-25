"""Local dry-run for insurance narrative workflow using SoftDent export fixtures.

Builds packet → draft → optional checker → review → local export only.
Never submits, emails, faxes, uploads, or calls cloud/235B models.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.insurance_narratives.data_adapter import softdent_export_file_adapter  # noqa: E402
from app.insurance_narratives.workflow import (  # noqa: E402
    approve_and_export_insurance_narrative_workflow,
    create_insurance_narrative_draft_workflow,
)

DEFAULT_EXPORT_DIR = PROJECT_ROOT / "app/tests/fixtures/insurance_narratives/softdent"
DEFAULT_OUT = "insurance_narrative_dry_run_report.json"

EXPORT_FILE_ALIASES: dict[str, list[str]] = {
    "softdent_claims_export.csv": [
        "softdent_claims_export.csv",
        "claims_export_fixture.csv",
    ],
    "softdent_procedures_export.csv": ["softdent_procedures_export.csv"],
    "softdent_patient_ledger_export.csv": ["softdent_patient_ledger_export.csv"],
    "softdent_claim_status_export.csv": ["softdent_claim_status_export.csv"],
    "softdent_clinical_notes_export.csv": ["softdent_clinical_notes_export.csv"],
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def prepare_softdent_export_dir(source_dir: Path, *, target_dir: Path | None = None) -> Path:
    """Copy export fixtures into a directory with canonical SoftDent filenames."""
    prepared = target_dir or Path(tempfile.mkdtemp(prefix="softdent_narrative_dry_run_"))
    prepared.mkdir(parents=True, exist_ok=True)
    for canonical_name, candidates in EXPORT_FILE_ALIASES.items():
        for candidate in candidates:
            source = source_dir / candidate
            if source.is_file():
                shutil.copy2(source, prepared / canonical_name)
                break
    return prepared


def build_dry_run_report(
    *,
    draft_result: Any,
    export_result: Any | None = None,
    run_checker: bool,
) -> dict[str, Any]:
    packet = (export_result or draft_result).packet
    draft = (export_result or draft_result).draft
    review = export_result.review if export_result else None
    export = export_result.export if export_result else None
    checker_summary = draft_result.checker_summary
    warnings = list(draft_result.warnings)
    if export_result:
        warnings.extend(export_result.warnings)

    workflow_status = export_result.status if export_result else draft_result.status
    supports = {tag for fact in packet.source_facts for tag in fact.supports}

    return {
        "dry_run": True,
        "no_submission": True,
        "generated_at_utc": _utc_now_iso(),
        "packet_id": packet.packet_id,
        "draft_id": draft.draft_id,
        "review_id": review.review_id if review else None,
        "export_id": export.export_id if export else None,
        "workflow_status": workflow_status,
        "source_fact_count": len(packet.source_facts),
        "missing_data_codes": [item.code for item in packet.missing_data],
        "draft_status": draft.status,
        "review_status": review.status if review else None,
        "export_format": export.format if export else None,
        "submission_status": export.submission_status if export else "not_submitted",
        "export_body": export.body if export else None,
        "checker_summary": checker_summary.model_dump(mode="json") if checker_summary else None,
        "checker_opt_in": run_checker,
        "warnings": [warning.model_dump(mode="json") for warning in warnings],
        "adapter_name": packet.audit_metadata.adapter_name,
        "source_mode": packet.audit_metadata.source_mode,
        "citation_fact_ids": [citation.fact_id for citation in draft.citations],
        "has_claim_status_facts": "claim_status" in supports,
        "has_clinical_note_facts": "clinical_note" in supports,
        "patient_ref": packet.patient.patient_ref,
        "claim_id": packet.claim.claim_id if packet.claim else None,
    }


def run_insurance_narrative_dry_run(
    *,
    export_dir: Path,
    patient_ref: str,
    claim_id: str,
    procedure_ids: list[str],
    narrative_type: str,
    actor: str,
    reviewer: str,
    run_checker: bool = False,
    export_format: str = "markdown",
    created_at: str | None = None,
    prepared_dir: Path | None = None,
) -> dict[str, Any]:
    timestamp = created_at or _utc_now_iso()
    adapter = softdent_export_file_adapter(export_dir=export_dir)

    draft_result = create_insurance_narrative_draft_workflow(
        patient_ref=patient_ref,
        claim_id=claim_id,
        procedure_ids=procedure_ids,
        narrative_type=narrative_type,
        actor=actor,
        created_at=timestamp,
        run_checker=run_checker,
        adapter=adapter,
    )

    export_result = None
    if draft_result.draft.status != "blocked_missing_data":
        export_result = approve_and_export_insurance_narrative_workflow(
            packet=draft_result.packet,
            draft=draft_result.draft,
            reviewer=reviewer,
            notes="Dry-run local approval for synthetic SoftDent export workflow.",
            approval_attestation=True,
            actor=actor,
            export_format=export_format,
            reviewed_at=timestamp,
            created_at=timestamp,
            checker_summary=draft_result.checker_summary,
        )

    return build_dry_run_report(
        draft_result=draft_result,
        export_result=export_result,
        run_checker=run_checker,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run insurance narrative workflow from SoftDent export CSV fixtures. "
            "Local packet/draft/review/export only — never submits to payers."
        )
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=DEFAULT_EXPORT_DIR,
        help=f"Directory containing SoftDent narrative export CSVs (default: {DEFAULT_EXPORT_DIR})",
    )
    parser.add_argument("--patient-ref", default="CHART-EXPORT")
    parser.add_argument("--claim-id", default="CLAIM-EXPORT-1")
    parser.add_argument(
        "--procedure-ids",
        default="PROC-CROWN-30",
        help="Comma-separated procedure ids",
    )
    parser.add_argument("--narrative-type", default="appeal")
    parser.add_argument("--actor", default="local-operator")
    parser.add_argument("--reviewer", default="local-reviewer")
    parser.add_argument(
        "--run-checker",
        action="store_true",
        help="Explicitly opt in to fast_review checker (default: off)",
    )
    parser.add_argument(
        "--export-format",
        default="markdown",
        choices=["markdown", "plain_text"],
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help=f"Write JSON report to this path (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args()

    procedure_ids = [part.strip() for part in args.procedure_ids.split(",") if part.strip()]
    prepared_dir = prepare_softdent_export_dir(args.export_dir.resolve())

    report = run_insurance_narrative_dry_run(
        export_dir=prepared_dir,
        patient_ref=args.patient_ref.strip().upper(),
        claim_id=args.claim_id.strip().upper(),
        procedure_ids=procedure_ids,
        narrative_type=args.narrative_type,
        actor=args.actor,
        reviewer=args.reviewer,
        run_checker=args.run_checker,
        export_format=args.export_format,
    )

    out_path = Path(args.out)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nDry-run report written to {out_path.resolve()}", file=sys.stderr)
    print("submission_status=not_submitted (no payer submission performed)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
