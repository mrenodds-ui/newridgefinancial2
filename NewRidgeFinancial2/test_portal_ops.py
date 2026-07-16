"""Tests for portal-derived NR2 ops modules."""

from __future__ import annotations

import json

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


def test_period_close_attest_and_status(tmp_path, monkeypatch):
    from daily_closeout import (
        period_close_status,
        run_period_close,
        try_deterministic_period_close_reply,
    )
    import daily_closeout as dc

    monkeypatch.setattr(dc, "OPS_DIR", tmp_path)
    monkeypatch.setattr(dc, "CLOSE_LOG_PATH", tmp_path / "daily_close_log.jsonl")
    monkeypatch.setattr(dc, "CLOSE_STATE_PATH", tmp_path / "period_close_state.json")

    fake_ready = {
        "ok": True,
        "level": "fresh",
        "blocking": [],
        "alignmentLasers": {"red": False, "green": True, "reason": "clear"},
    }
    fake_attest = {
        "ok": True,
        "beamHash": "testhash12345678",
        "beamTimestamp": "2026-07-15T21:00:00+00:00",
        "softdent": {"hasData": True, "display": "$7,714", "totalOutstanding": 7714.0},
        "quickbooks": {"hasData": True, "display": "$78,399", "monthlyRevenue": 78399.0},
    }
    monkeypatch.setattr(
        "import_diagnostics.assess_import_readiness",
        lambda **kwargs: fake_ready,
    )
    monkeypatch.setattr(
        "hal_brain_tools.money_beam_attestation",
        lambda readiness=None: fake_attest,
    )

    result = run_period_close(store=None, actor="test", auto=True, readiness=fake_ready)
    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["beamHash"] == "testhash12345678"
    assert (tmp_path / "daily_close_log.jsonl").is_file()

    status = period_close_status()
    assert status["status"] == "completed"
    assert status["beamHash"] == "testhash12345678"
    assert status["shadowStartedAt"]
    assert "morningBundle" in status
    assert status.get("emptyNotZero") is True

    det = try_deterministic_period_close_reply("Did we close today?")
    assert det and "beamHash=testhash12345678" in det["text"]


def test_period_close_laser_blocks(tmp_path, monkeypatch):
    from daily_closeout import run_period_close
    import daily_closeout as dc

    monkeypatch.setattr(dc, "OPS_DIR", tmp_path)
    monkeypatch.setattr(dc, "CLOSE_LOG_PATH", tmp_path / "daily_close_log.jsonl")
    monkeypatch.setattr(dc, "CLOSE_STATE_PATH", tmp_path / "period_close_state.json")

    blocked = {
        "ok": False,
        "level": "stale",
        "blocking": [{"key": "softdent_claims"}],
        "alignmentLasers": {"red": True, "green": False, "reason": "critical_softgap"},
    }
    result = run_period_close(store=None, actor="test", auto=True, readiness=blocked)
    assert result["ok"] is False
    assert result["status"] == "blocked"


def test_period_close_softdent_pull(tmp_path, monkeypatch):
    from daily_closeout import run_period_close
    import daily_closeout as dc

    monkeypatch.setattr(dc, "OPS_DIR", tmp_path)
    monkeypatch.setattr(dc, "CLOSE_LOG_PATH", tmp_path / "daily_close_log.jsonl")
    monkeypatch.setattr(dc, "CLOSE_STATE_PATH", tmp_path / "period_close_state.json")

    # Pre-pull readiness is red (stale SoftDent) — pull must still run to clear it.
    stale_ready = {
        "ok": False,
        "level": "fresh",
        "blocking": [{"datasetKey": "softdent.ar", "blockingReason": "critical_dataset_stale_exceeds_freshness"}],
        "alignmentLasers": {"red": True, "green": False, "reason": "critical_import_gaps"},
    }
    fresh_ready = {
        "ok": True,
        "level": "fresh",
        "blocking": [],
        "alignmentLasers": {"red": False, "green": True, "reason": "clear"},
    }
    fake_attest = {
        "ok": True,
        "beamHash": "pullhash87654321",
        "beamTimestamp": "2026-07-15T22:00:00+00:00",
        "softdent": {"hasData": True, "display": "$7,714", "totalOutstanding": 7714.0},
        "quickbooks": {"hasData": True, "display": "$78,399", "monthlyRevenue": 78399.0},
    }
    monkeypatch.setattr(
        "hal_brain_tools.softdent_export_morning_bundle",
        lambda **kwargs: {
            "ok": True,
            "bundle": True,
            "reportIds": ["aging", "register", "collections"],
            "okCount": 3,
            "failed": [],
            "agingOk": True,
            "partial": False,
            "path": r"C:\SoftDentReportExports\AG260715.XLS",
            "consentRequired": False,
        },
    )
    monkeypatch.setattr(
        "import_healing.heal_import_pipeline",
        lambda force=False: {"ok": True, "forced": force},
    )
    # Post-pull assess returns clear lasers
    monkeypatch.setattr(
        "import_diagnostics.assess_import_readiness",
        lambda **kwargs: fresh_ready,
    )
    monkeypatch.setattr(
        "hal_brain_tools.money_beam_attestation",
        lambda readiness=None: fake_attest,
    )

    result = run_period_close(
        store=None,
        actor="scheduler",
        auto=True,
        pull_softdent=True,
        readiness=stale_ready,
    )
    assert result["ok"] is True
    assert result["pullSoftdent"] is True
    assert result["softdentTotal"] == 7714.0
    assert (result.get("export") or {}).get("ok") is True
    assert result.get("softdentReports") == ["aging", "register", "collections"]
    assert result.get("exportOkCount") == 3
    assert (result.get("importRefresh") or {}).get("ok") is True


def test_period_close_softdent_pull_blocked_after_heal(tmp_path, monkeypatch):
    from daily_closeout import run_period_close
    import daily_closeout as dc

    monkeypatch.setattr(dc, "OPS_DIR", tmp_path)
    monkeypatch.setattr(dc, "CLOSE_LOG_PATH", tmp_path / "daily_close_log.jsonl")
    monkeypatch.setattr(dc, "CLOSE_STATE_PATH", tmp_path / "period_close_state.json")

    ready_ok = {
        "ok": True,
        "level": "fresh",
        "blocking": [],
        "alignmentLasers": {"red": False, "green": True, "reason": "clear"},
    }
    ready_still_red = {
        "ok": False,
        "level": "stale",
        "blocking": [{"datasetKey": "quickbooks.revenue"}],
        "alignmentLasers": {"red": True, "green": False, "reason": "critical_import_gaps"},
    }
    monkeypatch.setattr(
        "hal_brain_tools.softdent_export_morning_bundle",
        lambda **kwargs: {
            "ok": True,
            "bundle": True,
            "reportIds": ["aging", "register", "collections"],
            "okCount": 3,
            "path": r"C:\SoftDentReportExports\AG260715.XLS",
        },
    )
    monkeypatch.setattr(
        "import_healing.heal_import_pipeline",
        lambda force=False: {"ok": True, "forced": force},
    )
    monkeypatch.setattr(
        "import_diagnostics.assess_import_readiness",
        lambda **kwargs: ready_still_red,
    )

    result = run_period_close(
        store=None,
        actor="scheduler",
        auto=True,
        pull_softdent=True,
        readiness=ready_ok,
    )
    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["error"] == "laser_blocked_after_pull"
    assert result.get("pullSoftdent") is True


def test_period_close_softdent_pull_fallback_attest(tmp_path, monkeypatch):
    """GUI export failure after retries → attest-only close (no stall)."""
    from daily_closeout import run_period_close
    import daily_closeout as dc

    monkeypatch.setattr(dc, "OPS_DIR", tmp_path)
    monkeypatch.setattr(dc, "CLOSE_LOG_PATH", tmp_path / "daily_close_log.jsonl")
    monkeypatch.setattr(dc, "CLOSE_STATE_PATH", tmp_path / "period_close_state.json")

    fake_ready = {
        "ok": True,
        "level": "fresh",
        "blocking": [],
        "alignmentLasers": {"red": False, "green": True, "reason": "clear"},
    }
    fake_attest = {
        "ok": True,
        "beamHash": "fallbackhash1111",
        "beamTimestamp": "2026-07-15T22:00:00+00:00",
        "softdent": {"hasData": True, "display": "$7,714", "totalOutstanding": 7714.0},
        "quickbooks": {"hasData": True, "display": "$78,399", "monthlyRevenue": 78399.0},
    }
    monkeypatch.setattr(
        "hal_brain_tools.softdent_export_morning_bundle",
        lambda **kwargs: {"ok": False, "error": "softdent_gui_unreachable", "bundle": True, "agingOk": False},
    )
    monkeypatch.setattr(
        "import_diagnostics.assess_import_readiness",
        lambda **kwargs: fake_ready,
    )
    monkeypatch.setattr(
        "hal_brain_tools.money_beam_attestation",
        lambda readiness=None: fake_attest,
    )

    result = run_period_close(
        store=None,
        actor="scheduler",
        auto=True,
        pull_softdent=True,
        readiness=fake_ready,
    )
    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["fallback"] == "attest_only"
    assert result["guiExport"] is False
    assert result["softdentTotal"] == 7714.0
    assert (result.get("export") or {}).get("fallback") == "attest_only"


def test_softdent_export_morning_bundle_requires_aging(monkeypatch):
    from hal_brain_tools import softdent_export_morning_bundle
    import hal_brain_tools as h

    calls: list[str] = []

    def fake_export(*, report_id="aging", **kwargs):
        calls.append(report_id)
        if report_id == "aging":
            return {"ok": True, "reportId": "aging", "path": r"C:\SoftDentReportExports\AG.xls"}
        if report_id == "register":
            return {"ok": False, "error": "transient"}
        return {"ok": True, "reportId": report_id, "path": r"C:\SoftDentReportExports\CO.xls"}

    monkeypatch.setattr(h, "softdent_export", fake_export)
    out = softdent_export_morning_bundle(days=30)
    assert out["ok"] is True
    assert out["agingOk"] is True
    assert out["partial"] is True
    assert out["failed"] == ["register"]
    assert calls == ["aging", "register", "collections"]


def test_softdent_export_morning_bundle_aging_fail(monkeypatch):
    from hal_brain_tools import softdent_export_morning_bundle
    import hal_brain_tools as h

    def fake_export(*, report_id="aging", **kwargs):
        if report_id == "aging":
            return {"ok": False, "error": "softdent_gui_unreachable"}
        return {"ok": True, "reportId": report_id, "path": "x.xls"}

    monkeypatch.setattr(h, "softdent_export", fake_export)
    out = softdent_export_morning_bundle(days=30)
    assert out["ok"] is False
    assert out["agingOk"] is False


def test_force_close_decides_pull_on_red_or_stalled():
    from daily_closeout import force_close_available, force_close_should_pull_softdent

    assert force_close_should_pull_softdent(
        {"alignmentLasers": {"red": False}, "blocking": [], "periodClose": {"status": "completed"}},
        status="completed",
    ) is False
    assert force_close_should_pull_softdent(
        {"alignmentLasers": {"red": True}, "blocking": [], "periodClose": {"status": "idle"}},
        status="idle",
    ) is True
    assert force_close_should_pull_softdent(
        {"alignmentLasers": {"red": False}, "blocking": [], "periodClose": {"status": "stalled"}},
        status="stalled",
    ) is True
    assert force_close_should_pull_softdent(
        {
            "alignmentLasers": {"red": False},
            "blocking": [{"datasetKey": "softdent.ar"}],
            "periodClose": {"status": "idle"},
        },
        status="idle",
    ) is True
    assert force_close_available(
        {"alignmentLasers": {"red": False}, "blocking": [], "periodClose": {"status": "completed"}},
        status="completed",
    ) is False
    assert force_close_available(
        {"alignmentLasers": {"red": True}, "blocking": [], "periodClose": {"status": "idle"}},
        status="idle",
    ) is True
    assert force_close_available(
        {"alignmentLasers": {"red": False}, "blocking": [], "periodClose": {"status": "stalled"}},
        status="stalled",
    ) is True
    assert force_close_available(
        {"alignmentLasers": {"red": False}, "blocking": [], "periodClose": {"status": "running"}},
        status="running",
    ) is False


def test_force_period_close_pulls_when_stalled(tmp_path, monkeypatch):
    from daily_closeout import force_period_close, try_deterministic_period_close_reply
    import daily_closeout as dc

    monkeypatch.setattr(dc, "OPS_DIR", tmp_path)
    monkeypatch.setattr(dc, "CLOSE_LOG_PATH", tmp_path / "daily_close_log.jsonl")
    monkeypatch.setattr(dc, "FORCE_CLOSE_LOG_PATH", tmp_path / "force_close_log.jsonl")
    monkeypatch.setattr(dc, "CLOSE_STATE_PATH", tmp_path / "period_close_state.json")
    dc._write_state({"status": "stalled", "activeOperation": "stalled", "laserClear": True})

    calls = {"pull": None, "force_close": None}

    def fake_run(*, pull_softdent=False, force_close=False, **kwargs):
        calls["pull"] = pull_softdent
        calls["force_close"] = force_close
        return {
            "ok": True,
            "status": "completed",
            "completedAt": "2026-07-15T23:10:00+00:00",
            "beamHash": "forcehash2222",
            "pullSoftdent": pull_softdent,
            "forceClose": force_close,
            "softdentTotal": 100.0,
            "softdentDisplay": "$100",
            "qbDisplay": "$1",
            "laserClear": True,
            "auto": False,
            "actor": "optical-hub",
        }

    monkeypatch.setattr(dc, "run_period_close", fake_run)
    ready = {
        "ok": True,
        "level": "fresh",
        "blocking": [],
        "alignmentLasers": {"red": False, "green": True},
        "periodClose": {"status": "stalled"},
    }
    result = force_period_close(store=None, actor="optical-hub", readiness=ready)
    assert result["ok"] is True
    assert result["forceClose"] is True
    assert result["laserOverride"] is True
    assert result["pullSoftdentDecided"] is True
    assert calls["pull"] is True
    assert calls["force_close"] is True
    force_log = tmp_path / "force_close_log.jsonl"
    assert force_log.is_file()
    row = json.loads(force_log.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["laserOverride"] is True
    assert row["shadowMode"] is True
    assert row["systemOfRecord"] is False
    assert row["beamHash"] == "forcehash2222"

    # Make lastClose look like Force Close for HAL cite.
    (tmp_path / "daily_close_log.jsonl").write_text(
        json.dumps(
            {
                "status": "completed",
                "completedAt": "2026-07-15T23:10:00+00:00",
                "beamHash": "forcehash2222",
                "forceClose": True,
                "auto": False,
                "actor": "optical-hub",
                "softdentDisplay": "$100",
                "qbDisplay": "$1",
                "laserClear": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    dc._write_state(
        {
            "status": "completed",
            "completedAt": "2026-07-15T23:10:00+00:00",
            "beamHash": "forcehash2222",
            "laserClear": True,
        }
    )
    det = try_deterministic_period_close_reply("Did we close today?")
    assert det and "Force Close" in det["text"]
    assert det.get("forceClose") is True


def test_force_period_close_attest_only_when_clear(tmp_path, monkeypatch):
    from daily_closeout import force_period_close
    import daily_closeout as dc

    monkeypatch.setattr(dc, "OPS_DIR", tmp_path)
    monkeypatch.setattr(dc, "CLOSE_LOG_PATH", tmp_path / "daily_close_log.jsonl")
    monkeypatch.setattr(dc, "FORCE_CLOSE_LOG_PATH", tmp_path / "force_close_log.jsonl")
    monkeypatch.setattr(dc, "CLOSE_STATE_PATH", tmp_path / "period_close_state.json")
    dc._write_state({"status": "completed", "activeOperation": "completed"})

    calls = {"pull": None}

    def fake_run(*, pull_softdent=False, **kwargs):
        calls["pull"] = pull_softdent
        return {
            "ok": True,
            "status": "completed",
            "completedAt": "2026-07-15T23:11:00+00:00",
            "beamHash": "clearhash3333",
            "pullSoftdent": False,
        }

    monkeypatch.setattr(dc, "run_period_close", fake_run)
    ready = {
        "ok": True,
        "level": "fresh",
        "blocking": [],
        "alignmentLasers": {"red": False},
        "periodClose": {"status": "completed"},
    }
    result = force_period_close(store=None, actor="optical-om", readiness=ready)
    assert result["ok"] is True
    assert result["pullSoftdentDecided"] is False
    assert result["laserOverride"] is False
    assert calls["pull"] is False
    force_log = tmp_path / "force_close_log.jsonl"
    assert force_log.is_file()
    row = json.loads(force_log.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["laserOverride"] is False
    assert row["systemOfRecord"] is False


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
