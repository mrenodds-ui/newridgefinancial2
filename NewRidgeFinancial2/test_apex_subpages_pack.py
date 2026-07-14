"""Unit tests for Phase-1 Apex subpage pack (FIN-WP, FIN-PRO, CLM-DET)."""

from __future__ import annotations

from apex_subpages_pack import (
    build_claim_detail,
    build_financial_workpapers,
    build_provider_view,
    patient_initials,
    resolve_subpage_builder,
)


def test_patient_initials_formats():
    assert patient_initials("Smith, Jane") == "J.S."
    assert patient_initials("Jane Smith") == "J.S."
    assert patient_initials("") == "—"
    assert patient_initials(None) == "—"


def test_resolve_phase1_and_phase2_builders():
    assert resolve_subpage_builder("financial", "workpapers") is build_financial_workpapers
    assert resolve_subpage_builder("financial", "providers") is build_provider_view
    assert resolve_subpage_builder("claims", "detail") is build_claim_detail
    assert resolve_subpage_builder("claims", "batch") is not None
    assert resolve_subpage_builder("ar", "collections") is not None
    assert resolve_subpage_builder("office-manager", "huddle") is not None
    assert resolve_subpage_builder("documents", "claim-docs") is not None
    assert resolve_subpage_builder("library", "payers") is not None
    assert resolve_subpage_builder("claims", "era") is not None
    assert resolve_subpage_builder("ar", "forecast") is not None
    assert resolve_subpage_builder("financial", "periods") is not None
    assert resolve_subpage_builder("taxes", "bogus") is None


def test_claim_detail_empty_without_id():
    widgets = build_claim_detail({}, {}, claim_id=None)
    types = [w.get("type") for w in widgets]
    assert "claim-detail-card" in types
    card = next(w for w in widgets if w.get("type") == "claim-detail-card")
    assert card.get("status") == "empty"


def test_claim_detail_phi_initials_only():
    bundle = {
        "softdent": {
            "claims": {
                "rows": [
                    {
                        "ClaimId": "C-100",
                        "PatientName": "Doe, John",
                        "Status": "Open",
                        "Payer": "Delta",
                        "ServiceDate": "2026-01-02",
                        "ClaimAmount": "250.00",
                    }
                ]
            }
        }
    }
    widgets = build_claim_detail({}, bundle, claim_id="C-100")
    card = next(w for w in widgets if w.get("type") == "claim-detail-card")
    assert card.get("status") == "ok"
    claim = card.get("claim") or {}
    assert claim.get("patientName") == "J.D."
    assert claim.get("patientInitials") == "J.D."
    assert "John" not in str(claim.get("patientName") or "")


def test_provider_view_empty_honest():
    widgets = build_provider_view({}, {})
    bars = next(w for w in widgets if w.get("id") == "provider-metric-bars")
    assert bars.get("status") == "empty"


def test_workpapers_returns_scrubber():
    widgets = build_financial_workpapers({}, {})
    scrubber = next(w for w in widgets if w.get("type") == "workpaper-scrubber")
    assert scrubber.get("status") in {"ok", "empty"}
    if scrubber.get("status") == "ok":
        assert isinstance(scrubber.get("categories"), list)
        assert scrubber["categories"]  # planning bridge and/or QB categories only


def test_phase2_collections_and_batch_empty_honest():
    from apex_subpages_pack import build_batch_narrative, build_collections_workbench

    col = build_collections_workbench({}, {})
    assert any(w.get("type") == "collection-task-list" for w in col)
    bat = build_batch_narrative({}, {})
    assert any(w.get("type") == "batch-selector" for w in bat)


def test_local_db_roundtrip(tmp_path, monkeypatch):
    import nr2_local_db as db

    monkeypatch.setattr(db, "db_path", lambda: tmp_path / "t.sqlite3")
    note = db.upsert_collection_note(
        {"claimId": "X-9", "patientInitials": "A.B.", "status": "promised", "note": "left VM"}
    )
    assert note["ok"] is True
    assert db.list_collection_notes(limit=5)[0]["claimId"] == "X-9"
    task = db.upsert_task({"title": "Confirm ERA"})
    assert task["ok"] is True
    hud = db.record_huddle(["Check 90+ claims"])
    assert hud["ok"] is True
    assert len(db.list_huddle_history(limit=3)) == 1
    payer = db.upsert_payer_guideline(
        {"payerName": "Delta Dental", "appealDeadlineDays": 180, "guidelines": "Narrative required for crowns"}
    )
    assert payer["ok"] is True
    assert db.list_payer_guidelines()[0]["payerName"] == "Delta Dental"


def test_claim_docs_and_payers_widgets():
    from apex_subpages_pack import build_claim_docs, build_payer_library

    docs = build_claim_docs({}, {}, claim_id=None)
    assert any(w.get("type") == "attachment-dropzone" for w in docs)
    pay = build_payer_library({}, {})
    assert any(w.get("type") == "payer-reference-card" for w in pay)


def test_attachment_rejects_bad_type(tmp_path, monkeypatch):
    from apex_program_improve_pack import save_claim_attachment

    monkeypatch.setattr(
        "document_sync.NR2_DATA_DIR",
        tmp_path,
        raising=False,
    )
    # Patch module-level usage via importing after path — save imports NR2_DATA_DIR inside fn
    import document_sync

    monkeypatch.setattr(document_sync, "NR2_DATA_DIR", tmp_path)
    bad = save_claim_attachment(claim_id="C1", filename="x.exe", raw=b"MZ")
    assert bad["ok"] is False
    ok = save_claim_attachment(claim_id="C1", filename="eob.pdf", raw=b"%PDF-1.4 test")
    assert ok["ok"] is True


def test_phase4_blocked_honest_empty():
    from apex_subpages_pack import build_ar_forecast_subpage, build_claims_era, build_financial_periods

    era = build_claims_era({}, {})
    table = next(w for w in era if w.get("type") == "era-matching-table")
    assert table.get("type") == "era-matching-table"
    if not table.get("rows"):
        assert table.get("status") == "empty"
        assert "Awaiting ERA" in str(table.get("emptyMessage") or "")

    fc = build_ar_forecast_subpage({}, {})
    trend = next(w for w in fc if w.get("type") == "forecast-trend-line")
    if trend.get("blocked") or trend.get("status") == "empty":
        assert "Awaiting ERA" in str(trend.get("emptyMessage") or trend.get("hint") or "") or trend.get(
            "blocked"
        )

    per = build_financial_periods({}, {})
    chart = next(w for w in per if w.get("type") == "period-variance-chart")
    # Empty bundle has no dashboard rows → blocked
    assert chart.get("status") == "empty"
    assert chart.get("blocked") is True


def test_phase4_periods_variance_when_multi():
    from apex_subpages_pack import build_financial_periods

    bundle = {
        "softdent": {
            "dashboard": {
                "rows": [
                    {"period": "2026-01", "production": "10000", "collections": "8000"},
                    {"period": "2026-02", "production": "12000", "collections": "9000"},
                ]
            }
        }
    }
    widgets = build_financial_periods({}, bundle)
    chart = next(w for w in widgets if w.get("id") == "period-variance-chart")
    assert chart.get("status") == "ok"
    assert chart.get("bars")
    assert chart["bars"][0]["value"] == 2000.0


def test_wave5_remaining_add_builders_resolve():
    from apex_subpages_wave5_pack import WAVE5_BUILDERS

    assert ("taxes", "entities") in WAVE5_BUILDERS
    assert ("softdent", "register") in WAVE5_BUILDERS
    assert ("quickbooks", "coa") in WAVE5_BUILDERS
    assert ("ar", "aging-detail") in WAVE5_BUILDERS
    assert ("narratives", "audit") in WAVE5_BUILDERS
    assert ("hal", "system-logs") in WAVE5_BUILDERS
    assert resolve_subpage_builder("taxes", "calendar") is not None
    assert resolve_subpage_builder("office-manager", "tasks") is not None
    assert resolve_subpage_builder("claims", "kanban") is not None
    assert resolve_subpage_builder("office-manager", "operatory") is not None


def test_wave5_register_empty_honest():
    from apex_subpages_wave5_pack import build_softdent_register

    widgets = build_softdent_register({}, {})
    table = next(w for w in widgets if w.get("type") == "data-table")
    assert table.get("status") == "empty"


def test_hal_history_feed_empty_honest():
    from apex_program_improve_pack import _save_json
    from apex_subpages_wave5_pack import STORE_KEY_HAL_HISTORY, build_hal_history

    _save_json(STORE_KEY_HAL_HISTORY, {"entries": []})
    widgets = build_hal_history({}, {})
    types = [w.get("type") for w in widgets]
    assert "hal-sub-strip" in types
    assert "hal-history-feed" in types
    assert "hal-chat" in types
    feed = next(w for w in widgets if w.get("type") == "hal-history-feed")
    assert feed.get("status") == "empty"
    assert feed.get("size") == "full"
    assert "operator" in (feed.get("filters") or [])
    assert next(w for w in widgets if w.get("type") == "hal-chat").get("id") == "hal-ask"


def test_hal_history_append_and_feed():
    from apex_program_improve_pack import _save_json
    from apex_subpages_wave5_pack import STORE_KEY_HAL_HISTORY, append_hal_history_entry, build_hal_history

    _save_json(STORE_KEY_HAL_HISTORY, {"entries": []})
    r1 = append_hal_history_entry("operator", "What is import health?")
    r2 = append_hal_history_entry("hal", "Imports are degraded — refresh Sync.")
    assert r1.get("ok") is True
    assert r2.get("ok") is True
    widgets = build_hal_history({}, {})
    feed = next(w for w in widgets if w.get("type") == "hal-history-feed")
    assert feed.get("status") == "ok"
    entries = feed.get("entries") or []
    assert any("import health" in str(e.get("text") or "").lower() for e in entries)
    assert any(e.get("role") == "hal" for e in entries)


def test_hal_system_logs_console_and_hal_rail():
    from apex_subpages_wave5_pack import build_hal_system_logs

    bundle = {
        "diagnostics": {
            "summary": {"connected": 1, "partial": 1, "missing": 2, "stale": 0, "total": 4},
            "datasets": [
                {
                    "datasetKey": "softdent.ar",
                    "status": "missing",
                    "severity": "critical",
                    "automated": True,
                    "rowCount": 0,
                    "detail": "Dataset file not found.",
                },
                {
                    "datasetKey": "quickbooks.revenue",
                    "status": "missing",
                    "severity": "critical",
                    "automated": True,
                    "rowCount": 0,
                    "detail": "Revenue export missing.",
                },
            ],
        }
    }
    widgets = build_hal_system_logs({}, bundle)
    types = {w.get("type") for w in widgets}
    assert types == {"hal-sub-strip", "hal-sys-console", "hal-chat"}
    console = next(w for w in widgets if w.get("type") == "hal-sys-console")
    assert console.get("status") == "ok"
    assert console.get("lines")
    strip = next(w for w in widgets if w.get("type") == "hal-sub-strip")
    posture = next(m for m in strip.get("metrics") or [] if m.get("key") == "posture")
    assert posture.get("value") == "Degraded"
    assert next(w for w in widgets if w.get("type") == "hal-chat").get("id") == "hal-ask"
