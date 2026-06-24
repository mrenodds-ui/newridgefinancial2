from __future__ import annotations

import json
from pathlib import Path

import pytest

import app.hal.widget_feed as widget_feed_module
from app.hal.widget_builder import (
    IMPORT_CACHE_MANAGER,
    build_widget_feed_from_financial_summary,
    refresh_import_driven_widget_feed,
)
from app.hal.widget_feed import clear_widget_feed, configure_widget_feed_cache_path, get_widget_feed, load_widget_feed_from_disk, reset_widget_feed_memory


@pytest.fixture
def widget_cache_path(tmp_path: Path, monkeypatch):
    cache_path = tmp_path / "import_widget_feed.json"
    configure_widget_feed_cache_path(cache_path)
    clear_widget_feed()
    yield cache_path
    clear_widget_feed()
    configure_widget_feed_cache_path(None)


def _sample_financial_summary() -> dict[str, object]:
    return {
        "generatedAt": "2026-06-24T12:00:00Z",
        "lastRefreshed": "2026-06-24T12:00:00Z",
        "sourceReview": {
            "softDent": {
                "status": "ready",
                "metrics": {"providerCount": 1},
            },
            "quickBooks": {
                "status": "ready",
            },
        },
        "quickBooksStatus": {
            "status": "ready",
            "lastError": None,
            "rowCounts": {"revenue": 1, "expenses": 1, "ar": 1},
        },
        "quickBooksProfitLossSummary": [
            {
                "year_month": "2026-06",
                "income_total": 155000.0,
                "expense_total": 93000.0,
                "net_income": 62000.0,
            }
        ],
        "latestDailyKpi": {
            "production": 171500.0,
            "collections": 149250.0,
        },
        "currentMonthProduction": {
            "gross_production": 171500.0,
            "collections": 149250.0,
            "collection_rate": 87.03,
        },
        "latestAr": {
            "total_ar": 21700.0,
            "patient_ar": 9100.0,
            "insurance_ar": 12600.0,
        },
        "claimsSummary": {
            "available": True,
            "true_outstanding_claims_amount": 22110.0,
            "true_outstanding_claims_count": 34,
            "unsubmitted_claims_count": 9,
        },
    }


def test_build_widget_feed_maps_quickbooks_finance_fields(widget_cache_path: Path):
    payload = build_widget_feed_from_financial_summary(_sample_financial_summary())

    assert payload["manager"] == IMPORT_CACHE_MANAGER
    finance = payload["widgets"]["practice_financial_overview"]["metrics"]
    assert finance["monthly_revenue"] == 155000.0
    assert finance["monthly_net_income"] == 62000.0

    ap = payload["widgets"]["accounts_payable_automation"]["metrics"]
    assert ap["expense_total"] == 93000.0
    assert payload["sources"]["quickbooks"]["origin"] == "imports"


def test_build_widget_feed_maps_softdent_operations_fields(widget_cache_path: Path):
    payload = build_widget_feed_from_financial_summary(_sample_financial_summary())

    finance = payload["widgets"]["practice_financial_overview"]["metrics"]
    assert finance["production_total"] == 171500.0
    assert finance["collections_total"] == 149250.0
    assert finance["collection_rate"] == 87.03

    claims = payload["widgets"]["smart_claims_and_receivables"]["metrics"]
    assert claims["outstanding_claim_count"] == 34
    assert claims["outstanding_claim_amount"] == 22110.0
    assert claims["unsubmitted_claim_count"] == 9
    assert claims["accounts_receivable_total"] == 21700.0

    care = payload["widgets"]["care_delivery_performance"]["metrics"]
    assert care["provider_count"] == 1
    assert care["patient_balance_total"] == 9100.0
    assert payload["sources"]["softdent"]["origin"] == "imports"


def test_record_widget_feed_persists_and_reloads_after_restart(widget_cache_path: Path):
    payload = build_widget_feed_from_financial_summary(_sample_financial_summary())
    widget_feed_module.record_widget_feed(payload)

    reset_widget_feed_memory()
    reloaded = load_widget_feed_from_disk()

    assert reloaded is not None
    assert reloaded["manager"] == IMPORT_CACHE_MANAGER
    assert reloaded["widgets"]["practice_financial_overview"]["metrics"]["monthly_revenue"] == 155000.0
    assert widget_cache_path.is_file()


def test_corrupt_widget_feed_snapshot_fails_closed(widget_cache_path: Path):
    widget_cache_path.write_text("{not-json", encoding="utf-8")

    assert load_widget_feed_from_disk() is None
    assert get_widget_feed() is None


def test_refresh_import_driven_widget_feed_uses_financial_summary(monkeypatch, widget_cache_path: Path):
    summary = _sample_financial_summary()

    import app.routes as routes_module

    monkeypatch.setattr(routes_module, "_build_financial_summary_payload", lambda: summary)

    recorded = refresh_import_driven_widget_feed()

    assert recorded["manager"] == IMPORT_CACHE_MANAGER
    assert get_widget_feed() is not None
    assert get_widget_feed()["widgets"]["accounts_payable_automation"]["metrics"]["expense_total"] == 93000.0


def test_recompute_cache_publishes_import_driven_widget_feed(monkeypatch, widget_cache_path: Path):
    from app.data_pipeline import PullSection, recompute_cache
    from app.main import app

    summary = _sample_financial_summary()

    import app.routes as routes_module

    monkeypatch.setattr(routes_module, "_build_financial_summary_payload", lambda: summary)

    def _idle_pull_section(*, evaluated_at: str) -> PullSection:
        return PullSection(
            enabled=False,
            status="idle",
            summary="test pull",
            last_refresh_utc=evaluated_at,
        )

    monkeypatch.setattr("app.data_pipeline._pull_softdent_sources", lambda settings, evaluated_at: _idle_pull_section(evaluated_at=evaluated_at))
    monkeypatch.setattr("app.data_pipeline._pull_quickbooks_sources", lambda settings, evaluated_at: _idle_pull_section(evaluated_at=evaluated_at))
    monkeypatch.setattr("app.data_pipeline._refresh_current_kpis", lambda app: None)

    clear_widget_feed()
    recompute_cache(app)

    feed = get_widget_feed()
    assert feed is not None
    assert feed["widgets"]["smart_claims_and_receivables"]["metrics"]["outstanding_claim_amount"] == 22110.0


def test_build_widget_feed_does_not_mark_empty_imports_success(widget_cache_path: Path):
    payload = build_widget_feed_from_financial_summary(
        {
            "generatedAt": "2026-06-24T12:00:00Z",
            "sourceReview": {
                "softDent": {"status": "ready"},
                "quickBooks": {"status": "ready"},
            },
            "quickBooksStatus": {"status": "ready", "lastError": None, "rowCounts": {}},
            "quickBooksProfitLossSummary": [],
            "claimsSummary": {"available": False},
        }
    )

    assert payload["widgets"]["practice_financial_overview"]["status"] == "FAILED"
    assert payload["widgets"]["accounts_payable_automation"]["status"] == "FAILED"
    assert payload["widgets"]["smart_claims_and_receivables"]["status"] == "FAILED"
    assert payload["jobs"]["widget_publish"]["status"] == "FAILED"


def test_invalid_persisted_widget_feed_shape_is_ignored(widget_cache_path: Path):
    widget_cache_path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")

    assert load_widget_feed_from_disk() is None
