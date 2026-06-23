import json
from pathlib import Path

import app.services as services
import app.hal.financial_tools as financial_tools


def test_fetch_softdent_dashboard_aggregate_maps_local_snapshot():
    payload = services.fetch_softdent_dashboard_aggregate()

    assert payload["source_file"] == "softdent_dashboard_data.json"
    assert payload["period_start"] == "2026-06-01"
    assert payload["period_end"] == "2026-06-30"
    assert payload["provider_count"] == 3
    assert payload["data_complete"] is True
    assert payload["totals"] == {
        "production": 116780.0,
        "collections": 107015.0,
        "insurance": 65435.0,
        "patient": 41580.0,
    }

    first_provider = payload["provider_rows"][0]
    assert first_provider == {
        "provider_id": "dradams",
        "provider_name": "Dr. Adams",
        "production_amount": 55250.0,
        "collection_amount": 50125.0,
    }


def test_build_softdent_snapshot_preserves_legacy_shape():
    payload = services.build_softdent_snapshot()

    assert payload["available"] is True
    assert payload["period"] == "2026-06"
    assert payload["provider_count"] == 3
    assert payload["totals"] == {
        "production": 116780.0,
        "collections": 107015.0,
        "insurance": 65435.0,
        "patient": 41580.0,
    }

    first_provider = payload["providers"][0]
    assert first_provider == {
        "provider": "Dr. Adams",
        "period": "2026-06",
        "production": 55250.0,
        "collections": 50125.0,
        "insurance": 30875.0,
        "patient": 19250.0,
    }


def test_build_softdent_snapshot_handles_sparse_aggregate_payload(monkeypatch):
    monkeypatch.setattr(
        services,
        "fetch_softdent_dashboard_aggregate",
        lambda: {
            "provider_rows": [
                {
                    "provider_name": "Dr. Sparse",
                }
            ]
        },
    )
    monkeypatch.setattr(services, "_find_softdent_provider_insurance", lambda provider_name: 0.0)
    monkeypatch.setattr(services, "_find_softdent_provider_patient", lambda provider_name: 0.0)

    payload = services.build_softdent_snapshot()

    assert payload["available"] is True
    assert payload["period"] == ""
    assert payload["provider_count"] == 1
    assert payload["totals"] == {
        "production": 0.0,
        "collections": 0.0,
        "insurance": 0.0,
        "patient": 0.0,
    }
    assert payload["providers"] == [
        {
            "provider": "Dr. Sparse",
            "period": "",
            "production": 0.0,
            "collections": 0.0,
            "insurance": 0.0,
            "patient": 0.0,
        }
    ]


def test_get_kpi_data_handles_sparse_snapshot_payload(monkeypatch):
    monkeypatch.setattr(
        services,
        "build_softdent_snapshot",
        lambda: {
            "available": True,
        },
    )

    payload = services.get_kpi_data()

    assert payload == [
        {"name": "production", "value": 0.0},
        {"name": "collections", "value": 0.0},
        {"name": "ar", "value": 0.0},
        {"name": "collection_ratio", "value": 0.0},
        {"name": "provider_count", "value": 0},
        {"name": "period", "value": "unknown"},
    ]


def test_softdent_status_helpers_read_from_aggregate_contract(monkeypatch):
    def fail_legacy_snapshot():
        raise AssertionError("legacy snapshot helper should not be used")

    monkeypatch.setattr(financial_tools, "build_softdent_snapshot", fail_legacy_snapshot)

    provider_status = financial_tools.get_softdent_provider_ranking_status()
    payer_status = financial_tools.get_softdent_payer_mix_status()
    delta_status = financial_tools.get_softdent_collection_delta_status()

    assert provider_status["available"] is True
    assert "Rank 1: Dr. Adams production 55250.0 collections 50125.0" in provider_status["excerpt"]
    assert payer_status["available"] is True
    assert "insurance collections share 0.6115" in payer_status["excerpt"]
    assert "direct-pay collections share 0.3885" in payer_status["excerpt"]
    assert delta_status["available"] is True
    assert "delta 9765.0" in delta_status["excerpt"]
    assert "collection ratio 0.9164" in delta_status["excerpt"]


def test_fetch_softdent_dashboard_aggregate_does_not_read_repo_root_fallback(tmp_path, monkeypatch):
    project_root = tmp_path / "repo"
    project_root.mkdir()
    (project_root / "softdent_dashboard_data.json").write_text(
        json.dumps(
            [
                {
                    "provider": "Dr. Adams",
                    "period": "2026-06",
                    "production": 55250.0,
                    "collections": 50125.0,
                    "insurance": 30875.0,
                    "patient": 19250.0,
                },
                {
                    "provider": "Dr. Lee",
                    "period": "2026-06",
                    "production": 42890.0,
                    "collections": 39410.0,
                    "insurance": 24150.0,
                    "patient": 15260.0,
                },
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(services, "_project_root", lambda: project_root)

    payload = services.fetch_softdent_dashboard_aggregate()

    assert payload["provider_count"] == 0
    assert payload["data_complete"] is False


def test_fetch_softdent_dashboard_aggregate_does_not_read_bridge_exports(tmp_path, monkeypatch):
    project_root = tmp_path / "repo"
    bridge_root = tmp_path / "bridge" / "exports"
    project_root.mkdir()
    bridge_root.mkdir(parents=True)
    (bridge_root / "softdent_dashboard_data.json").write_text(
        json.dumps(
            [
                {
                    "provider": "Dr. Adams",
                    "period": "2026-06",
                    "production": 55250.0,
                    "collections": 50125.0,
                    "insurance": 30875.0,
                    "patient": 19250.0,
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(services, "_project_root", lambda: project_root)
    monkeypatch.setattr(services, "_softdent_bridge_export_root", lambda: bridge_root)

    payload = services.fetch_softdent_dashboard_aggregate()

    assert payload["provider_count"] == 0
    assert payload["data_complete"] is False


def test_fetch_softdent_dashboard_aggregate_does_not_read_latest_seeded_backup(tmp_path, monkeypatch):
    project_root = tmp_path / "repo"
    backup_root = project_root / "_seeded_backup_20260618_103017"
    project_root.mkdir()
    backup_root.mkdir(parents=True)
    (backup_root / "softdent_dashboard_data.json").write_text(
        json.dumps(
            [
                {
                    "provider": "Hygiene Team",
                    "period": "2026-06",
                    "production": 18640.0,
                    "collections": 17480.0,
                    "insurance": 10410.0,
                    "patient": 7070.0,
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(services, "_project_root", lambda: project_root)

    payload = services.fetch_softdent_dashboard_aggregate()

    assert payload["provider_count"] == 0
    assert payload["data_complete"] is False


def test_fetch_softdent_dashboard_aggregate_does_not_read_ai_workspace_staging(tmp_path, monkeypatch):
    project_root = tmp_path / "repo"
    ai_workspace_root = tmp_path / "AI_Workspace"
    project_root.mkdir()
    ai_workspace_root.mkdir(parents=True)
    (ai_workspace_root / "softdent_dashboard_data.json").write_text(
        json.dumps(
            [
                {
                    "provider": "Dr. Shadow",
                    "period": "2026-06",
                    "production": 1.0,
                    "collections": 1.0,
                    "insurance": 1.0,
                    "patient": 0.0,
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(services, "_project_root", lambda: project_root)
    monkeypatch.setattr(services, "get_ai_workspace_path", lambda: ai_workspace_root)

    payload = services.fetch_softdent_dashboard_aggregate()

    assert payload["provider_count"] == 0
    assert payload["data_complete"] is False


def test_load_softdent_claim_rows_validates_normalized_contract(monkeypatch):
    def fake_load_optional_tabular_export(*, env_var: str, default_names: tuple[str, ...]):
        return (
            [
                {
                    "patient_name": "John Doe",
                    "chartnumber": "778899",
                    "claimnumber": "CLM-1001",
                    "status": "Denied",
                    "carrier": "Delta Dental",
                    "description": "Crown buildup",
                    "dos": "2026-06-12",
                    "note": "Missing attachment",
                    "amount": "215.75",
                    "AgingDays": 42,
                }
            ],
            None,
            "json",
        )

    monkeypatch.setattr(services, "_load_optional_tabular_export", fake_load_optional_tabular_export)

    rows = services.load_softdent_claim_rows()

    assert rows == [
        {
            "patient_name": "John Doe",
            "chartnumber": "778899",
            "claimnumber": "CLM-1001",
            "status": "Denied",
            "carrier": "Delta Dental",
            "description": "Crown buildup",
            "dos": "2026-06-12",
            "note": "Missing attachment",
            "amount": "215.75",
            "AgingDays": 42,
            "PatientName": "John Doe",
            "MRN": "778899",
            "ClaimId": "CLM-1001",
            "ClaimStatus": "Denied",
            "Payer": "Delta Dental",
            "Procedure": "Crown buildup",
            "ServiceDate": "2026-06-12",
            "DenialReason": "Missing attachment",
            "ClaimAmount": 215.75,
        }
    ]


def test_load_softdent_clinical_note_rows_validates_normalized_contract(monkeypatch):
    def fake_load_optional_tabular_export(*, env_var: str, default_names: tuple[str, ...]):
        return (
            [
                {
                    "patient": "John Doe",
                    "patient_id": "778899",
                    "entrydate": "2026-06-12",
                    "doctor": "Dr. Adams",
                    "treatment": "Crown buildup",
                    "chartnote": "Patient has fractured cusp with recurrent decay.",
                    "Tooth": "3",
                }
            ],
            None,
            "json",
        )

    monkeypatch.setattr(services, "_load_optional_tabular_export", fake_load_optional_tabular_export)

    rows = services.load_softdent_clinical_note_rows()

    assert rows == [
        {
            "patient": "John Doe",
            "patient_id": "778899",
            "entrydate": "2026-06-12",
            "doctor": "Dr. Adams",
            "treatment": "Crown buildup",
            "chartnote": "Patient has fractured cusp with recurrent decay.",
            "Tooth": "3",
            "PatientName": "John Doe",
            "MRN": "778899",
            "NoteDate": "2026-06-12",
            "Provider": "Dr. Adams",
            "Procedure": "Crown buildup",
            "ClinicalNote": "Patient has fractured cusp with recurrent decay.",
        }
    ]


def test_get_softdent_data_coverage_reports_missing_and_limited_rows(monkeypatch):
    monkeypatch.setattr(
        services,
        "build_softdent_snapshot",
        lambda: {
            "available": True,
            "period": "2026-06",
            "provider_count": 3,
            "providers": [],
            "totals": {
                "production": 116780.0,
                "collections": 107015.0,
                "insurance": 65435.0,
                "patient": 41580.0,
            },
        },
    )
    monkeypatch.setattr(
        services,
        "load_softdent_dashboard_rows",
        lambda: [
            {"provider": "Dr. Adams", "period": "2026-06", "production": 55250.0, "collections": 50125.0},
            {"provider": "Dr. Lee", "period": "2026-06", "production": 42890.0, "collections": 39410.0},
            {"provider": "Hygiene Team", "period": "2026-06", "production": 18640.0, "collections": 17480.0},
        ],
    )
    monkeypatch.setattr(
        services,
        "get_softdent_source_status",
        lambda: {
            "available": True,
            "source_backend": "json",
            "source_file": "softdent_dashboard_data.json",
            "modified_at_utc": "2026-06-18T13:45:00+00:00",
        },
    )
    monkeypatch.setattr(
        services,
        "load_softdent_claim_rows",
        lambda: [{"ClaimId": "CLM-1001", "ServiceDate": "2026-06-12", "ClaimAmount": 215.75}],
    )
    monkeypatch.setattr(
        services,
        "get_softdent_claim_source_status",
        lambda: {
            "available": True,
            "source_backend": "csv",
            "source_file": "softdent_claims_export.csv",
            "modified_at_utc": "2026-06-18T13:50:00+00:00",
        },
    )

    def fake_load_optional_tabular_export(*, env_var: str, default_names: tuple[str, ...]):
        assert env_var in {
            services.SOFTDENT_OUTSTANDING_CLAIMS_EXPORT_ENV,
            services.SOFTDENT_UNSUBMITTED_CLAIMS_EXPORT_ENV,
            services.SOFTDENT_INSURANCE_INCOME_EXPORT_ENV,
            services.SOFTDENT_INSURANCE_PAYMENT_DISTRIBUTION_EXPORT_ENV,
            services.SOFTDENT_INSURANCE_CHECK_DISTRIBUTION_EXPORT_ENV,
            services.SOFTDENT_TREATMENT_PLAN_EXPORT_ENV,
            services.SOFTDENT_PAYMENT_PLAN_EXPORT_ENV,
        }
        return [], None, "missing"

    monkeypatch.setattr(services, "_load_optional_tabular_export", fake_load_optional_tabular_export)

    coverage = services.get_softdent_data_coverage()

    assert coverage["summary"] == "Missing and limited reports explain why some dashboard charts are unavailable."
    assert coverage["counts"] == {"missing": 7, "limited": 5, "available": 7}


def test_get_softdent_data_coverage_handles_sparse_snapshot_payload(monkeypatch):
    monkeypatch.setattr(services, "build_softdent_snapshot", lambda: {})
    monkeypatch.setattr(
        services,
        "load_softdent_dashboard_rows",
        lambda: [{"provider": "Dr. Adams", "period": "2026-06", "production": 55250.0, "collections": 50125.0}],
    )
    monkeypatch.setattr(
        services,
        "get_softdent_source_status",
        lambda: {
            "available": True,
            "source_backend": "json",
            "source_file": "softdent_dashboard_data.json",
            "modified_at_utc": "2026-06-18T13:45:00+00:00",
        },
    )
    monkeypatch.setattr(
        services,
        "load_softdent_claim_rows",
        lambda: [{"ClaimId": "CLM-1001", "ServiceDate": "2026-06-12", "ClaimAmount": 215.75}],
    )
    monkeypatch.setattr(
        services,
        "get_softdent_claim_source_status",
        lambda: {
            "available": True,
            "source_backend": "csv",
            "source_file": "softdent_claims_export.csv",
            "modified_at_utc": "2026-06-18T13:50:00+00:00",
        },
    )
    monkeypatch.setattr(services, "_load_optional_tabular_export", lambda **kwargs: ([], None, "missing"))

    coverage = services.get_softdent_data_coverage()
    rows_by_key = {row["key"]: row for row in coverage["rows"]}

    assert rows_by_key["dashboardSnapshot"]["status"] == "missing"
    assert rows_by_key["dashboardSnapshot"]["lastPeriod"] == ""
    assert rows_by_key["claimsExport"]["status"] == "available"
    assert rows_by_key["currentPeriodTotals"]["status"] == "missing"
    assert rows_by_key["dailyProduction"]["status"] == "missing"

    rows_by_key = {row["key"]: row for row in coverage["rows"]}
    assert rows_by_key["trueOutstandingClaims"]["status"] == "missing"
    assert rows_by_key["transactionFeed"]["status"] == "limited"
    assert rows_by_key["fourYearHistory"]["status"] == "limited"
    assert rows_by_key["claimsExport"]["rowCount"] == 1


def test_get_softdent_coverage_metrics_aggregates_amounts_and_breakdowns(monkeypatch, tmp_path):
    metric_rows = {
        services.SOFTDENT_OUTSTANDING_CLAIMS_EXPORT_ENV: [
            {"Payer": "Delta Dental", "Claim_Count": "3", "Outstanding_Amount": "1200.50"},
            {"Payer": "MetLife", "Claim_Count": "2", "Outstanding_Amount": "800.25"},
        ],
        services.SOFTDENT_UNSUBMITTED_CLAIMS_EXPORT_ENV: [
            {"Payer": "Delta Dental", "Claim_Count": "4", "Unsubmitted_Amount": "540.00"},
        ],
        services.SOFTDENT_INSURANCE_INCOME_EXPORT_ENV: [],
        services.SOFTDENT_INSURANCE_PAYMENT_DISTRIBUTION_EXPORT_ENV: [],
        services.SOFTDENT_INSURANCE_CHECK_DISTRIBUTION_EXPORT_ENV: [],
        services.SOFTDENT_TREATMENT_PLAN_EXPORT_ENV: [],
        services.SOFTDENT_PAYMENT_PLAN_EXPORT_ENV: [],
    }

    def fake_load_optional_tabular_export(*, env_var: str, default_names: tuple[str, ...]):
        rows = metric_rows.get(env_var, [])
        if rows:
            source_path = tmp_path / default_names[0]
            source_path.write_text("placeholder", encoding="utf-8")
            return rows, source_path, "csv"
        return [], None, "missing"

    monkeypatch.setattr(services, "_load_optional_tabular_export", fake_load_optional_tabular_export)

    metrics = services.get_softdent_coverage_metrics()

    outstanding = metrics["trueOutstandingClaims"]
    assert outstanding["available"] is True
    assert outstanding["itemCount"] == 5
    assert outstanding["totalAmount"] == 2000.75
    assert outstanding["breakdown"][0]["label"] == "Delta Dental"
    assert outstanding["breakdown"][0]["count"] == 3

    unsubmitted = metrics["unsubmittedClaims"]
    assert unsubmitted["available"] is True
    assert unsubmitted["itemCount"] == 4
    assert unsubmitted["totalAmount"] == 540.0