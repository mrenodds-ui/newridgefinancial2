"""
REC-007 extension — HAL local model cache warm / keep-alive (hal-local:32b).

Widget stub fast-path (Phase 3 REC-007) already ships separately. This pack
keeps the Ollama model resident and primes common CARC/payer explain prompts
so cold starts after restart or ERA ingest are shorter.

No invented dollars. No PHI. SoftDent write-back never. Flag: NR2_HAL_CACHE_WARM
(default ON). Keep-alive: NR2_OLLAMA_KEEP_ALIVE (default -1 = forever).
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
STATUS_PATH = REPO_ROOT / "app_data" / "nr2" / "hal_cache_warm_status.json"

# Short, non-PHI priming prompts — empty ≠ $0; never invent remittance amounts.
BASE_WARM_PROMPTS: tuple[str, ...] = (
    "Reply with exactly one word: ready",
    "In one sentence: explain CARC CO-45 as a contractual adjustment code without inventing dollar amounts.",
    "In one sentence: what should staff check first when an ERA shows denialFlag true but no paid amount on the line?",
    "In one sentence: how do RARC remark codes relate to CAS/CARC on an 835 without inventing values?",
    "In two sentences: HAL is read-only for SoftDent and QuickBooks; outbound submit needs consent.",
)

_lock = threading.Lock()
_last_status: dict[str, Any] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def cache_warm_enabled() -> bool:
    raw = str(os.getenv("NR2_HAL_CACHE_WARM") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def ollama_keep_alive() -> int | str:
    """Ollama keep_alive: -1 forever, or duration string like 30m."""
    raw = str(os.getenv("NR2_OLLAMA_KEEP_ALIVE") or "-1").strip()
    if not raw:
        return -1
    if raw.lstrip("-").isdigit():
        return int(raw)
    return raw


def approved_warm_model() -> str:
    try:
        from integration_health import APPROVED_LOCAL_MODEL

        return str(APPROVED_LOCAL_MODEL)
    except Exception:
        return "hal-local:32b"


def _save_status(payload: dict[str, Any]) -> None:
    global _last_status
    with _lock:
        _last_status = dict(payload)
        try:
            STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
            STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass


def warm_status() -> dict[str, Any]:
    with _lock:
        if _last_status:
            return dict(_last_status)
    if STATUS_PATH.is_file():
        try:
            data = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {
        "ok": True,
        "enabled": cache_warm_enabled(),
        "warmed": False,
        "model": approved_warm_model(),
        "keepAlive": ollama_keep_alive(),
        "note": "No warm run yet.",
    }


def build_warm_prompts(
    *,
    payer_labels: list[str] | None = None,
    cas_codes: list[str] | None = None,
) -> list[str]:
    prompts = list(BASE_WARM_PROMPTS)
    for code in (cas_codes or [])[:8]:
        c = str(code or "").strip().upper()
        if not c:
            continue
        prompts.append(
            f"In one sentence: explain adjustment code {c} as a remittance CARC/CAS label "
            "without inventing dollar amounts or patient details."
        )
    for payer in (payer_labels or [])[:6]:
        p = str(payer or "").strip()
        if not p or p.upper() in {"UNKNOWN_PAYER", "UNKNOWN"}:
            continue
        # Payer name only — no PHI; still avoid inventing fee schedules.
        prompts.append(
            f"In one sentence: when reviewing ERA adjustments for payer label {p}, "
            "what should staff verify first without inventing paid amounts?"
        )
    # Dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for pr in prompts:
        if pr in seen:
            continue
        seen.add(pr)
        out.append(pr)
    return out


def _call_chat(**kwargs: Any) -> dict[str, Any]:
    """Indirection so tests can mock without importing bottle-backed gateway."""
    from nr2_hal_gateway import call_ollama_chat

    return call_ollama_chat(**kwargs)


def _run_warm_prompts(
    prompts: list[str],
    *,
    model: str | None = None,
    timeout: float = 90.0,
) -> dict[str, Any]:
    model_name = str(model or approved_warm_model())
    keep = ollama_keep_alive()
    results: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    for i, prompt in enumerate(prompts):
        started = time.perf_counter()
        try:
            res = _call_chat(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                options={"num_ctx": 8192, "num_predict": 64},
                timeout=timeout,
                keep_alive=keep,
            )
            elapsed = round(time.perf_counter() - started, 3)
            ok = bool(res.get("ok"))
            results.append(
                {
                    "index": i,
                    "ok": ok,
                    "elapsedSec": elapsed,
                    "error": None if ok else (res.get("error") or res.get("detail") or "warm_failed"),
                    "promptPreview": prompt[:80],
                }
            )
            if not ok and i == 0:
                # First prompt failed — model likely down; stop early.
                break
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "index": i,
                    "ok": False,
                    "elapsedSec": round(time.perf_counter() - started, 3),
                    "error": str(exc),
                    "promptPreview": prompt[:80],
                }
            )
            break
    total = round(time.perf_counter() - t0, 3)
    ok_count = sum(1 for r in results if r.get("ok"))
    payload = {
        "ok": ok_count > 0,
        "enabled": True,
        "warmed": ok_count > 0,
        "model": model_name,
        "keepAlive": keep,
        "promptCount": len(prompts),
        "okCount": ok_count,
        "elapsedSec": total,
        "at": _utc_now(),
        "results": results,
        "note": "HAL cache warm — keep_alive applied; no invented dollars.",
    }
    _save_status(payload)
    return payload


def warm_hal_cache(
    *,
    payer_labels: list[str] | None = None,
    cas_codes: list[str] | None = None,
    background: bool = False,
) -> dict[str, Any]:
    """Warm approved local model with base (+ optional ERA-selective) prompts."""
    if not cache_warm_enabled():
        return {
            "ok": False,
            "enabled": False,
            "warmed": False,
            "reason": "hal_cache_warm_disabled",
            "keepAlive": ollama_keep_alive(),
        }
    prompts = build_warm_prompts(payer_labels=payer_labels, cas_codes=cas_codes)
    if background:
        threading.Thread(
            target=_run_warm_prompts,
            args=(prompts,),
            kwargs={},
            daemon=True,
            name="nr2-hal-cache-warm",
        ).start()
        return {
            "ok": True,
            "enabled": True,
            "warmed": False,
            "background": True,
            "promptCount": len(prompts),
            "model": approved_warm_model(),
            "keepAlive": ollama_keep_alive(),
            "at": _utc_now(),
            "note": "Warm started in background.",
        }
    return _run_warm_prompts(prompts)


def selective_warm_from_era_summary(summary: dict[str, Any] | None, *, background: bool = True) -> dict[str, Any]:
    """After ERA ingest: prime prompts for seen CAS codes (and optional payer if present)."""
    if not isinstance(summary, dict) or not summary.get("ok"):
        return {"ok": False, "skipped": True, "reason": "no_summary"}
    cas: list[str] = []
    for claim in summary.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        for c in claim.get("casCodes") or []:
            if c and str(c) not in cas:
                cas.append(str(c))
        for sl in claim.get("serviceLines") or []:
            if not isinstance(sl, dict):
                continue
            for c in sl.get("casCodes") or []:
                if c and str(c) not in cas:
                    cas.append(str(c))
    return warm_hal_cache(cas_codes=cas[:8], background=background)
