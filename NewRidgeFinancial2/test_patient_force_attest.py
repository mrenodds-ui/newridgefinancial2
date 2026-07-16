"""Tests for patient Force Attest (MATCH-gated OM review)."""

from __future__ import annotations


def test_patient_attest_rejects_mismatch(monkeypatch, tmp_path):
    import patient_force_attest as pfa

    monkeypatch.setattr(pfa, "OPS_DIR", tmp_path)
    monkeypatch.setattr(pfa, "ATTEST_LOG_PATH", tmp_path / "patient_force_attest_log.jsonl")
    monkeypatch.setattr(
        pfa,
        "patient_attest_eligible",
        lambda readiness=None: {
            "ok": True,
            "eligible": False,
            "deskProof": "MISMATCH",
            "emptyNotZero": True,
        },
    )
    result = pfa.force_attest_patient("12345", actor="test")
    assert result["ok"] is False
    assert result["error"] == "desk_proof_not_match"
    assert result["deskProof"] == "MISMATCH"


def test_patient_attest_writes_log_on_match(monkeypatch, tmp_path):
    import patient_force_attest as pfa

    monkeypatch.setattr(pfa, "OPS_DIR", tmp_path)
    monkeypatch.setattr(pfa, "ATTEST_LOG_PATH", tmp_path / "patient_force_attest_log.jsonl")
    monkeypatch.setattr(
        pfa,
        "patient_attest_eligible",
        lambda readiness=None: {
            "ok": True,
            "eligible": True,
            "deskProof": "MATCH",
            "dataBeamHash": "abcd" * 8,
            "beamHash": "beef" * 8,
            "emptyNotZero": True,
        },
    )

    def fake_mini(pid):
        return {
            "ok": True,
            "patientHash": "a1b2",
            "initials": "JD",
            "accountBalance": "unavailable",
        }

    monkeypatch.setattr("om_patient_dossier.get_patient_dossier_mini", fake_mini)
    monkeypatch.setattr("patient_dossier.patient_hash", lambda pid: "a1b2")

    result = pfa.force_attest_patient("999", actor="optical-om-test")
    assert result["ok"] is True
    assert result["closed"] is True
    assert result["accountBalanceDisplay"] == "unavailable"
    assert result["emptyNotZero"] is True
    assert (tmp_path / "patient_force_attest_log.jsonl").is_file()

    again = pfa.force_attest_patient("999", actor="optical-om-test")
    assert again["ok"] is True
    assert again.get("idempotent") is True


def test_desk_smoke_exposes_patient_attest_eligible(monkeypatch, tmp_path):
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
    data_hash = h.compute_beam_hashes(
        {"display": "$1,000", "totalOutstanding": 1000.0},
        {"display": "$2,000", "monthlyRevenue": 2000.0},
    )["dataBeamHash"]
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
                "dataBeamHash": data_hash,
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

    result = ds.run_desk_smoke(probe_http=False, readiness=ready)
    assert result["ok"] is True
    assert result["deskProof"] == "MATCH"
    assert result.get("patientAttestEligible") is True
    assert result.get("forceCloseAvailable") is False
