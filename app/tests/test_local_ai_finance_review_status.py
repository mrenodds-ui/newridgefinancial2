from pathlib import Path

from local_ai_finance import main as local_ai_finance


def test_list_review_status_reports_pending_and_reviewed_exports(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(local_ai_finance, "WORKSPACE_DIR", tmp_path)
    local_ai_finance.ensure_workspace()
    (tmp_path / "pending_review_step.txt").write_text("pending", encoding="utf-8")
    (tmp_path / "claims-reviewed-export.json").write_text("{}", encoding="utf-8")
    (tmp_path / "invoice-reviewed-export.json").write_text("{}", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")

    status = local_ai_finance.list_review_status()

    assert status == {
        "pending_review_files": ["pending_review_step.txt"],
        "reviewed_exports": ["claims-reviewed-export.json", "invoice-reviewed-export.json"],
        "rendered_charts": [],
    }