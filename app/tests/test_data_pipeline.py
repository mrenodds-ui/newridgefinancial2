from pathlib import Path

import pytest

import app.data_pipeline as data_pipeline


def test_merge_dashboard_rows_replaces_existing_period_with_latest_import_batch():
    existing_rows = [
        {
            "provider": "Dr. Reno",
            "period": "2026-05",
            "production": 900.0,
            "collections": 700.0,
            "insurance": 300.0,
            "patient": 400.0,
        },
        {
            "provider": "Dr. Reno",
            "period": "2026-06",
            "production": 1000.0,
            "collections": 800.0,
            "insurance": 350.0,
            "patient": 450.0,
        },
    ]
    incoming_rows = [
        {
            "provider": "Dr. Reno",
            "period": "2026-06",
            "production": 1200.0,
            "collections": 900.0,
            "insurance": 500.0,
            "patient": 400.0,
        },
        {
            "provider": "Dr. Reno",
            "period": "2026-06",
            "production": 300.0,
            "collections": 200.0,
            "insurance": 100.0,
            "patient": 100.0,
        },
    ]

    merged_rows = data_pipeline._merge_dashboard_rows(existing_rows, incoming_rows)
    merged_by_key = {(row["provider"], row["period"]): row for row in merged_rows}

    assert merged_by_key[("Dr. Reno", "2026-05")]["production"] == 900.0
    assert merged_by_key[("Dr. Reno", "2026-06")] == {
        "provider": "Dr. Reno",
        "period": "2026-06",
        "production": 1500.0,
        "collections": 1100.0,
        "insurance": 600.0,
        "patient": 500.0,
    }


@pytest.mark.parametrize(
    ("suffix", "attribute_name", "expected_message"),
    [
        (".xlsx", "load_workbook", "requires openpyxl support"),
        (".xls", "xlrd", "requires xlrd support"),
    ],
)
def test_read_rows_from_path_reports_missing_spreadsheet_dependency(monkeypatch, tmp_path: Path, suffix: str, attribute_name: str, expected_message: str):
    monkeypatch.setattr(data_pipeline, attribute_name, None)

    with pytest.raises(ValueError, match=expected_message):
        data_pipeline._read_rows_from_path(tmp_path / f"upload{suffix}")


def test_pull_quickbooks_sources_ignores_ai_workspace_staged_files(tmp_path: Path):
    settings = data_pipeline.RuntimeImportSettings(
        softdent_source_dir=None,
        quickbooks_source_dir=None,
        softdent_import_dir=tmp_path / "softdent_imports",
        quickbooks_import_dir=tmp_path / "quickbooks_imports",
        softdent_auto_pull_enabled=False,
        quickbooks_auto_pull_enabled=False,
        financial_daily_refresh_enabled=True,
        ai_workspace_dir=tmp_path / "AI_Workspace",
    )
    settings.ai_workspace_dir.mkdir(parents=True, exist_ok=True)
    (settings.ai_workspace_dir / "quickbooks_profit_and_loss.csv").write_text(
        "Date,Income,Expenses\n2026-06-01,100,25\n",
        encoding="utf-8",
    )

    section = data_pipeline._pull_quickbooks_sources(
        settings,
        evaluated_at="2026-06-22T00:00:00Z",
    )

    assert section.scanned == 0
    assert section.copied == 0
    assert section.files == []