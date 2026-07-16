"""Tests for desk smoke confidence loop."""

from __future__ import annotations


def test_desk_smoke_green_path(monkeypatch, tmp_path):
    import desk_smoke as ds
    import daily_closeout as dc
    import hal_brain_tools as h

    monkeypatch.setattr(ds, "OPS_DIR", tmp_path)
    monkeypatch.setattr(ds, "SMOKE_LOG_PATH", tmp_path / "desk_smoke_log.jsonl")
    monkeypatch.setattr(ds, "SMOKE_STATE_PATH", tmp_path / "desk_smoke_state.json")
    monkeypatch.setattr(dc, "OPS_DIR", tmp_path)
    monkeypatch.setattr(dc, "CLOSE_LOG_PATH", tmp_path / "daily_close_log.jsonl")
    monkeypatch.setattr(dc, "CLOSE_STATE_PATH", tmp_path / "period_close_state.json")
    monkeypatch.setattr(dc, "FORCE_CLOSE_LOG_PATH", tmp_path / "force_close_log.jsonl")

    ready = {
        "ok": True,
        "level": "fresh",
        "blocking": [],
        "alignmentLasers": {"red": False, "green": True},
        "periodClose": {"status": "completed"},
    }
    monkeypatch.setattr(
        dc,
        "period_close_status",
        lambda: {
            "ok": True,
            "status": "completed",
            "beamHash": "aabbccddee001122",
            "completedAt": "2026-07-16T01:00:00+00:00",
            "lastClose": {
                "softdentDisplay": "$1,000",
                "softdentTotal": 1000.0,
                "qbDisplay": "$2,000",
                "qbRevenue": 2000.0,
                "dataBeamHash": h.compute_beam_hashes(
                    {"display": "$1,000", "totalOutstanding": 1000.0},
                    {"display": "$2,000", "monthlyRevenue": 2000.0},
                )["dataBeamHash"],
            },
        },
    )
    monkeypatch.setattr(dc, "force_close_available", lambda *a, **k: False)
    monkeypatch.setattr(
        h,
        "softdent_status",
        lambda: {
            "ok": True,
            "hasData": True,
            "display": "$1,000",
            "totalOutstanding": 1000.0,
            "hint": "t",
            "at": "t",
        },
    )
    monkeypatch.setattr(
        h,
        "qb_summary",
        lambda: {
            "ok": True,
            "hasData": True,
            "display": "$2,000",
            "monthlyRevenue": 2000.0,
            "hint": "t",
            "at": "t",
        },
    )
    monkeypatch.setattr(h, "_utc_now", lambda: "2026-07-16T01:00:00+00:00")
    h.clear_beam_attest_cache()

    # Skip HTTP probe so unit test does not depend on live 8765 process.
    result = ds.run_desk_smoke(probe_http=False, readiness=ready)
    assert result["ok"] is True
    assert result["status"] == "GREEN"
    assert result["deskProof"] == "MATCH"
    assert result.get("dataBeamHash")
    assert (tmp_path / "desk_smoke_log.jsonl").is_file()


def test_desk_smoke_fails_when_force_close_wrong(monkeypatch, tmp_path):
    import desk_smoke as ds
    import daily_closeout as dc
    import hal_brain_tools as h

    monkeypatch.setattr(ds, "OPS_DIR", tmp_path)
    monkeypatch.setattr(ds, "SMOKE_LOG_PATH", tmp_path / "desk_smoke_log.jsonl")
    monkeypatch.setattr(ds, "SMOKE_STATE_PATH", tmp_path / "desk_smoke_state.json")

    ready = {
        "ok": False,
        "level": "stale",
        "blocking": [{"datasetKey": "softdent.ar"}],
        "alignmentLasers": {"red": True},
        "periodClose": {"status": "blocked"},
    }
    monkeypatch.setattr(
        dc,
        "period_close_status",
        lambda: {"ok": True, "status": "blocked", "beamHash": "x", "completedAt": "t"},
    )
    # Wrong: Force Close should be available when lasers red, but we report False.
    monkeypatch.setattr(dc, "force_close_available", lambda *a, **k: False)
    monkeypatch.setattr(
        h,
        "money_beam_attestation",
        lambda readiness=None, bypass_cache=False: {
            "ok": True,
            "beamHash": "bbbbbbbbbbbbbbbb",
            "dataBeamHash": "aaaaaaaaaaaaaaaa",
            "softdent": {"display": "$1", "hasData": True},
            "quickbooks": {"display": "$2", "hasData": True},
        },
    )
    monkeypatch.setattr(
        h,
        "beam_desk_proof",
        lambda readiness=None: {
            "ok": True,
            "deskProof": "MATCH",
            "live": {"dataBeamHash": "aaaaaaaaaaaaaaaa"},
            "periodClose": {"dataBeamHash": "aaaaaaaaaaaaaaaa"},
        },
    )

    result = ds.run_desk_smoke(probe_http=False, readiness=ready)
    assert result["ok"] is False
    assert "force_close_availability" in result["failures"]
