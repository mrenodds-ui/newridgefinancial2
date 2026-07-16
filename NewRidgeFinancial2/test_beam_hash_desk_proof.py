"""Formal beamHash desk proof — dataBeamHash identity + attest cache."""

from __future__ import annotations


def test_compute_beam_hashes_stable_data():
    from hal_brain_tools import compute_beam_hashes

    sd = {"display": "$100", "totalOutstanding": 100.0}
    qb = {"display": "$50", "monthlyRevenue": 50.0}
    a = compute_beam_hashes(sd, qb, at="2026-07-15T23:00:00+00:00")
    b = compute_beam_hashes(sd, qb, at="2026-07-15T23:00:01+00:00")
    assert a["dataBeamHash"] == b["dataBeamHash"]
    assert a["beamHash"] != b["beamHash"]
    assert len(a["dataBeamHash"]) == 16


def test_money_beam_attest_cache_shares_snapshot(monkeypatch):
    from hal_brain_tools import clear_beam_attest_cache, money_beam_attestation
    import hal_brain_tools as h

    clear_beam_attest_cache()
    monkeypatch.setattr(
        h,
        "softdent_status",
        lambda: {
            "ok": True,
            "hasData": True,
            "display": "$7,714",
            "totalOutstanding": 7714.0,
            "hint": "test",
            "at": "t1",
        },
    )
    monkeypatch.setattr(
        h,
        "qb_summary",
        lambda: {
            "ok": True,
            "hasData": True,
            "display": "$78,399",
            "monthlyRevenue": 78399.0,
            "hint": "test",
            "at": "t1",
        },
    )
    stamps = iter(["2026-07-15T23:20:00+00:00", "2026-07-15T23:20:01+00:00"])
    monkeypatch.setattr(h, "_utc_now", lambda: next(stamps))

    first = money_beam_attestation(bypass_cache=True)
    second = money_beam_attestation()
    assert second.get("cached") is True
    assert first["beamHash"] == second["beamHash"]
    assert first["dataBeamHash"] == second["dataBeamHash"]

    clear_beam_attest_cache()
    third = money_beam_attestation(bypass_cache=True)
    assert third.get("cached") is False
    assert third["dataBeamHash"] == first["dataBeamHash"]
    assert third["beamHash"] != first["beamHash"]


def test_beam_desk_proof_match(monkeypatch, tmp_path):
    from hal_brain_tools import beam_desk_proof, clear_beam_attest_cache
    import daily_closeout as dc
    import hal_brain_tools as h

    clear_beam_attest_cache()
    monkeypatch.setattr(dc, "OPS_DIR", tmp_path)
    monkeypatch.setattr(dc, "CLOSE_LOG_PATH", tmp_path / "daily_close_log.jsonl")
    monkeypatch.setattr(dc, "CLOSE_STATE_PATH", tmp_path / "period_close_state.json")
    monkeypatch.setattr(dc, "FORCE_CLOSE_LOG_PATH", tmp_path / "force_close_log.jsonl")

    sd = {
        "ok": True,
        "hasData": True,
        "display": "$1,000",
        "totalOutstanding": 1000.0,
        "hint": "t",
        "at": "t",
    }
    qb = {
        "ok": True,
        "hasData": True,
        "display": "$2,000",
        "monthlyRevenue": 2000.0,
        "hint": "t",
        "at": "t",
    }
    monkeypatch.setattr(h, "softdent_status", lambda: sd)
    monkeypatch.setattr(h, "qb_summary", lambda: qb)
    monkeypatch.setattr(h, "_utc_now", lambda: "2026-07-15T23:30:00+00:00")
    monkeypatch.setattr(
        "period_close_ops_notify.notify_period_close_trouble",
        lambda *a, **k: {"ok": True, "skipped": True},
    )

    result = dc.run_period_close(
        store=None,
        actor="test",
        auto=True,
        readiness={
            "ok": True,
            "level": "fresh",
            "blocking": [],
            "alignmentLasers": {"red": False},
        },
    )
    assert result["ok"] is True
    assert result.get("dataBeamHash")

    proof = beam_desk_proof(
        readiness={"ok": True, "level": "fresh", "blocking": [], "alignmentLasers": {"red": False}}
    )
    assert proof["deskProof"] == "MATCH"
    assert proof["match"]["liveDataEqualsCloseData"] is True
    assert proof["live"]["dataBeamHash"] == result["dataBeamHash"]


def test_deterministic_money_cites_hashes(monkeypatch):
    from hal_brain_tools import clear_beam_attest_cache, try_deterministic_money_reply
    import hal_brain_tools as h

    clear_beam_attest_cache()
    monkeypatch.setattr(
        h,
        "softdent_status",
        lambda: {
            "ok": True,
            "hasData": True,
            "display": "$9",
            "totalOutstanding": 9.0,
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
            "display": "$1",
            "monthlyRevenue": 1.0,
            "hint": "t",
            "at": "t",
        },
    )
    monkeypatch.setattr(h, "_utc_now", lambda: "2026-07-15T23:40:00+00:00")
    det = try_deterministic_money_reply("What is our AR outstanding?")
    assert det and det.get("ok")
    assert "beamHash=" in det["text"]
    assert "dataBeamHash=" in det["text"]
    assert det.get("dataBeamHash")
