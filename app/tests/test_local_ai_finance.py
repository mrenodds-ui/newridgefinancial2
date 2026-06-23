import json
from pathlib import Path

from local_ai_finance import main as local_ai_finance


def test_normalize_claims_extraction_result_fills_total_and_record_count(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(local_ai_finance, "WORKSPACE_DIR", tmp_path)
    claims_path = tmp_path / "claims.csv"
    claims_path.write_text(
        "PatientName,MRN,ClaimId,ClaimStatus,Payer,Procedure,ServiceDate,DenialReason,ClaimAmount\n"
        "John Doe,778899,CLM-1,Denied,Delta Dental,Crown,2026-06-12,Need docs,215.75\n"
        "Jane Roe,889900,CLM-2,Paid,MetLife,SRP,2026-06-10,Paid,486.50\n",
        encoding="utf-8",
    )
    payload = {
        "record_count": 0,
        "total_claim_amount": 0,
        "claim_status_counts": {"denied": 1, "pending_review": 0, "paid": 1, "other": 0},
        "patients_requiring_follow_up": [],
        "flag_for_review": False,
        "review_reason": "",
    }

    normalized = local_ai_finance.normalize_claims_extraction_result(payload, filename="claims.csv")

    assert normalized["record_count"] == 2
    assert normalized["total_claim_amount"] == 702.25


def test_apply_claims_extraction_guardrails_flags_denials_and_missing_total() -> None:
    payload = {
        "record_count": 2,
        "total_claim_amount": 0,
        "claim_status_counts": {"denied": 1, "pending_review": 1, "paid": 0, "other": 0},
        "patients_requiring_follow_up": [{"patient_name": "John", "mrn": "1", "claim_id": "A", "claim_status": "Denied", "follow_up_reason": "Need docs"}],
        "flag_for_review": False,
        "review_reason": "",
    }

    guarded = local_ai_finance.apply_claims_extraction_guardrails(payload)

    assert guarded["flag_for_review"] is True
    assert "denied claim(s) require follow-up" in guarded["review_reason"]
    assert "pending-review claim(s) require follow-up" in guarded["review_reason"]
    assert "total_claim_amount is missing or non-positive" in guarded["review_reason"]


def test_analyze_workspace_file_logs_single_consolidated_entry(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(local_ai_finance, "WORKSPACE_DIR", tmp_path)
    log_path = tmp_path / "ai_activity.log"
    monkeypatch.setattr(local_ai_finance, "LOG_FILE", log_path)
    local_ai_finance.ensure_workspace()
    claims_path = tmp_path / "claims.csv"
    claims_path.write_text(
        "PatientName,MRN,ClaimId,ClaimStatus,Payer,Procedure,ServiceDate,DenialReason,ClaimAmount\n"
        "John Doe,778899,CLM-1,Denied,Delta Dental,Crown,2026-06-12,Need docs,215.75\n",
        encoding="utf-8",
    )

    summary = local_ai_finance.analyze_workspace_file("claims.csv", purpose="prompt-based review")
    log_text = log_path.read_text(encoding="utf-8")

    assert "CSV file: claims.csv" in summary
    assert "AI analyzed claims.csv inside AI_Workspace for prompt-based review." in log_text
    assert "AI summarized claims.csv inside AI_Workspace." not in log_text


def test_write_reviewed_export_writes_json_after_review(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(local_ai_finance, "WORKSPACE_DIR", tmp_path)
    log_path = tmp_path / "ai_activity.log"
    monkeypatch.setattr(local_ai_finance, "LOG_FILE", log_path)
    local_ai_finance.ensure_workspace()
    monkeypatch.setattr(local_ai_finance, "review_step", lambda plan_text: None)

    output_path = local_ai_finance.write_reviewed_export(
        source_file="claims.csv",
        output_filename="claims-output.json",
        payload={"ok": True, "items": [1, 2, 3]},
        export_kind="claims_extraction",
    )

    assert Path(output_path).exists()
    written_payload = json.loads(Path(output_path).read_text(encoding="utf-8"))
    assert written_payload == {"ok": True, "items": [1, 2, 3]}
    assert "AI wrote reviewed claims_extraction JSON export to claims-output.json inside AI_Workspace." in log_path.read_text(encoding="utf-8")


def test_build_structured_prompt_explicitly_mutes_personality() -> None:
    prompt = local_ai_finance.build_structured_prompt(
        input_payload={
            "user_request": "Render a bar chart for overhead variance.",
            "context_text": "Software 540",
        },
        output_schema={
            "name": "render_financial_chart",
            "description": "Return chart JSON only.",
        },
    )

    assert "Structured response mode is now active." in prompt
    assert "Mute all conversational personality, tone, explanations, and chain-of-thought." in prompt
    assert "Return only one top-level JSON object that matches the provided schema exactly." in prompt
    assert "Do not add commentary before or after the JSON object." in prompt