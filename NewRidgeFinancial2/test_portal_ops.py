"""Tests for portal-derived NR2 ops modules."""

from __future__ import annotations

from automation_registry import list_automation_jobs, record_job_run
from daily_closeout import build_daily_closeout, format_daily_closeout_text
from financial_reports import build_financial_reports, format_financial_reports_text
from integration_health import format_integration_health_text, integration_health_snapshot
from knowledge_memory_index import build_memory_index, search_memories
from program_help import format_program_help, match_program_help


def test_automation_registry_lists_jobs():
    payload = list_automation_jobs()
    assert payload["summary"]["total"] >= 3
    assert any(job["id"] == "import-sync" for job in payload["jobs"])


def test_record_job_run_persists(tmp_path, monkeypatch):
    fake_state = tmp_path / "automation_runs.json"
    monkeypatch.setattr("automation_registry.STATE_PATH", fake_state)
    record_job_run("import-sync", ok=True, detail="test")
    payload = list_automation_jobs()
    assert any((j.get("lastRun") or {}).get("detail") == "test" for j in payload["jobs"])


def test_integration_health_snapshot_shape():
    snap = integration_health_snapshot(store=None, deep_diagnostics=False)
    assert snap["enabled_count"] >= 4
    assert isinstance(snap["integrations"], list)
    text = format_integration_health_text(snap)
    assert "Integration health" in text


def test_program_help_matches_imports():
    match = match_program_help("how do I refresh SoftDent imports")
    assert match is not None
    assert match["id"] == "imports"
    text = format_program_help("how do I refresh imports")
    assert "Sync-HAL-Imports" in text or "Refresh imports" in text


def test_financial_reports_build():
    reports = build_financial_reports(sync_exports=False)
    assert "claimTracking" in reports
    assert "arAging" in reports
    text = format_financial_reports_text(reports)
    assert "Financial reports" in text


def test_daily_closeout_build():
    payload = build_daily_closeout(store=None)
    assert payload["overall"] in {"ok", "warn", "fail"}
    assert len(payload["items"]) >= 5
    text = format_daily_closeout_text(payload)
    assert "Daily closeout" in text


def test_memory_index_search():
    index = build_memory_index([])
    assert index == []
    hits = search_memories("softdent import", limit=3, memories=[])
    assert hits == []


def test_memory_index_finds_dental_narrative_playbooks():
    hits = search_memories("crown D2740 denial appeal medical necessity fracture", limit=5)
    assert hits
    assert any(row.get("id") == "crown-d2740-medical-necessity" for row in hits)


def test_memory_search_prefers_practice_learned():
    hits = search_memories("Steve office manager", limit=3)
    assert hits
    assert hits[0].get("id") == "nr2-practice-office-manager-steve"

    hits = search_memories("Dr Michael Reno dentist owner", limit=3)
    assert hits
    assert hits[0].get("id") == "nr2-practice-doctor-michael-reno"

    hits = search_memories("New Ridge morning huddle Steve", limit=3)
    assert hits
    assert hits[0].get("id") == "nr2-practice-steve-morning-huddle"


def test_memory_search_hygiene_and_tax_learned():
    hits = search_memories("hygiene recall prophy six months New Ridge", limit=3)
    assert hits
    assert hits[0].get("id") == "nr2-practice-hygiene-recall-interval"

    hits = search_memories("Kansas PTE tax election Dr Reno CPA", limit=3)
    assert hits
    assert hits[0].get("id") == "nr2-practice-tax-kansas-pte-annual"

    hits = search_memories("UnitedHealthcare UHC crown code 16", limit=3)
    assert hits
    assert hits[0].get("id") == "nr2-practice-uhc-dental-narratives"


def test_resolve_memory_citations_for_tax_plan():
    from knowledge_memory_store import resolve_memory_citations
    from tax_engine import build_tax_plan

    cites = resolve_memory_citations(["scorp-reasonable-compensation-dental"])
    assert cites[0]["title"]
    assert len(cites[0]["detail"]) > 20

    plan = build_tax_plan(book_net_income=250_000)
    memo = plan.get("memoCitations") or []
    assert len(memo) >= 4
    assert all(isinstance(row, dict) and row.get("detail") for row in memo)
