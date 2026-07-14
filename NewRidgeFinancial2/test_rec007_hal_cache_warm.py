"""REC-007 HAL cache warm / keep-alive pack tests (mocked Ollama)."""

from __future__ import annotations

from apex_hal_cache_warm_pack import (
    build_warm_prompts,
    cache_warm_enabled,
    selective_warm_from_era_summary,
    warm_hal_cache,
    warm_status,
)


def test_build_warm_prompts_includes_cas_and_payer():
    prompts = build_warm_prompts(cas_codes=["CO-45", "PR-1"], payer_labels=["DELTA DENTAL"])
    blob = "\n".join(prompts)
    assert "CO-45" in blob
    assert "PR-1" in blob
    assert "DELTA DENTAL" in blob
    assert "inventing dollar" in blob.lower() or "inventing" in blob.lower()


def test_warm_disabled(monkeypatch):
    monkeypatch.setenv("NR2_HAL_CACHE_WARM", "0")
    assert cache_warm_enabled() is False
    result = warm_hal_cache()
    assert result.get("ok") is False
    assert result.get("reason") == "hal_cache_warm_disabled"


def test_warm_hal_cache_mocked(monkeypatch, tmp_path):
    monkeypatch.setenv("NR2_HAL_CACHE_WARM", "1")
    monkeypatch.setattr(
        "apex_hal_cache_warm_pack.STATUS_PATH",
        tmp_path / "hal_cache_warm_status.json",
    )

    def _fake_chat(**kwargs):
        assert kwargs.get("keep_alive") == -1 or kwargs.get("keep_alive") is not None
        return {"ok": True, "body": {"message": {"content": "ready"}}}

    monkeypatch.setattr("apex_hal_cache_warm_pack._call_chat", _fake_chat)
    result = warm_hal_cache(cas_codes=["CO-45"], background=False)
    assert result.get("ok") is True
    assert result.get("warmed") is True
    assert result.get("okCount", 0) >= 1
    status = warm_status()
    assert status.get("warmed") is True


def test_selective_warm_from_era_summary(monkeypatch):
    monkeypatch.setenv("NR2_HAL_CACHE_WARM", "1")
    called = {}

    def _fake_warm(**kwargs):
        called["cas"] = kwargs.get("cas_codes")
        called["background"] = kwargs.get("background")
        return {"ok": True, "background": True}

    monkeypatch.setattr("apex_hal_cache_warm_pack.warm_hal_cache", _fake_warm)
    summary = {
        "ok": True,
        "claims": [
            {
                "casCodes": ["CO-45"],
                "serviceLines": [{"casCodes": ["PR-1"]}],
            }
        ],
    }
    out = selective_warm_from_era_summary(summary, background=True)
    assert out.get("ok") is True
    assert "CO-45" in (called.get("cas") or [])
    assert "PR-1" in (called.get("cas") or [])
    assert called.get("background") is True
