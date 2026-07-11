#!/usr/bin/env python3
"""Validate HAL single-24B local readiness and run a controlled prompt suite.

Fails closed if the approved model, GPU residency, VRAM headroom, listener
binding, or single-model policy is violated. Does not promote on download alone.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

NR2 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NR2))

from integration_health import (  # noqa: E402
    APPROVED_LOCAL_MODEL,
    VRAM_SAFETY_MARGIN_GIB,
    probe_local_24b_readiness,
)

BASE = os.environ.get("NR2_OLLAMA_BASE", "http://127.0.0.1:11434")
RESULTS_DIR = NR2 / "docs" / "hal-local-24b-test-results"


PROMPTS = [
    ("simple", "Reply with exactly one word: ready"),
    (
        "accounting",
        "In one short paragraph: explain why an A/R aging report showing insurance aging "
        "higher than patient aging usually needs staff review of unpaid claims first. "
        "Do not invent dollar amounts.",
    ),
    (
        "diagnostic",
        "Staff see empty SoftDent production widgets. In two sentences, what should they "
        "check first locally without inventing file contents?",
    ),
    (
        "summarization",
        "Summarize in two sentences: HAL is read-only for SoftDent and QuickBooks; "
        "outbound submit/email requires consent.",
    ),
    (
        "code_review",
        "Review this Python stub in two sentences for a read-only finance app: "
        "def post_qb(entry): return 'posted'. What is the safety issue?",
    ),
]


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _post_chat(model: str, prompt: str, timeout: float = 180.0) -> dict[str, Any]:
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_ctx": 8192, "num_predict": 256},
            "keep_alive": -1,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    elapsed = time.perf_counter() - t0
    eval_count = int(payload.get("eval_count") or 0)
    eval_duration_ns = int(payload.get("eval_duration") or 0)
    prompt_eval_duration_ns = int(payload.get("prompt_eval_duration") or 0)
    load_duration_ns = int(payload.get("load_duration") or 0)
    tps = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns > 0 else None
    first_token_ms = (prompt_eval_duration_ns / 1e6) if prompt_eval_duration_ns else None
    content = ""
    msg = payload.get("message") or {}
    if isinstance(msg, dict):
        content = str(msg.get("content") or "")
    return {
        "ok": bool(content.strip()),
        "elapsedSec": round(elapsed, 3),
        "loadDurationSec": round(load_duration_ns / 1e9, 3) if load_duration_ns else None,
        "firstTokenMs": round(first_token_ms, 1) if first_token_ms is not None else None,
        "tokensPerSecond": round(tps, 2) if tps is not None else None,
        "evalCount": eval_count,
        "replyPreview": content[:240].replace("\n", " "),
    }


def run_prompt_suite(model: str) -> list[dict[str, Any]]:
    results = []
    for name, prompt in PROMPTS:
        try:
            r = _post_chat(model, prompt)
            r["name"] = name
            r["error"] = None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            r = {"name": name, "ok": False, "error": str(exc)}
        results.append(r)
        print(f"  [{name}] ok={r.get('ok')} tps={r.get('tokensPerSecond')} err={r.get('error')}")
    return results


def run_stability(model: str, minutes: int, interval_sec: int) -> dict[str, Any]:
    deadline = time.time() + minutes * 60
    samples: list[dict[str, Any]] = []
    crashes = 0
    while time.time() < deadline:
        gate = probe_local_24b_readiness(BASE)
        try:
            r = _post_chat(model, "Reply with one word: stable", timeout=120.0)
            ok = bool(r.get("ok")) and bool(gate.get("ok"))
        except Exception as exc:  # noqa: BLE001 — record and continue stability loop
            ok = False
            r = {"ok": False, "error": str(exc)}
            crashes += 1
        samples.append({"at": _utc(), "gateOk": gate.get("ok"), "promptOk": ok, "gate": gate, "prompt": r})
        print(f"  stability sample gate={gate.get('ok')} prompt={ok} loaded={gate.get('loadedModels')}")
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        time.sleep(min(interval_sec, max(1, int(remaining))))
    fails = sum(1 for s in samples if not s.get("promptOk") or not s.get("gateOk"))
    return {
        "minutes": minutes,
        "samples": len(samples),
        "failures": fails,
        "crashesOrTimeouts": crashes,
        "ok": fails == 0 and crashes == 0 and len(samples) > 0,
        "detail": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate HAL local 24B single-GPU layout")
    parser.add_argument("--stability-minutes", type=int, default=0, help="Run N-minute stability loop (0=skip)")
    parser.add_argument("--stability-interval", type=int, default=60, help="Seconds between stability pings")
    parser.add_argument("--skip-prompts", action="store_true")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    print("=== HAL local 24B readiness gate ===")
    gate = probe_local_24b_readiness(BASE)
    print(json.dumps({k: v for k, v in gate.items() if k != "processorHint"}, indent=2))

    # Soft promote path: if model not loaded yet, do not claim success — fail.
    if not gate.get("ok"):
        print("READINESS FAILED — do not promote route.")
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out = args.json_out or (RESULTS_DIR / f"fail-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
        out.write_text(json.dumps({"at": _utc(), "gate": gate, "promoted": False}, indent=2), encoding="utf-8")
        return 1

    prompt_results: list[dict[str, Any]] = []
    if not args.skip_prompts:
        print("=== Prompt suite ===")
        prompt_results = run_prompt_suite(APPROVED_LOCAL_MODEL)
        if any(not r.get("ok") for r in prompt_results):
            print("PROMPT SUITE FAILED — do not promote route.")
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            out = args.json_out or (RESULTS_DIR / f"fail-prompts-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
            out.write_text(
                json.dumps({"at": _utc(), "gate": gate, "prompts": prompt_results, "promoted": False}, indent=2),
                encoding="utf-8",
            )
            return 1

    stability: dict[str, Any] | None = None
    if args.stability_minutes > 0:
        print(f"=== Stability {args.stability_minutes} min (interval {args.stability_interval}s) ===")
        stability = run_stability(APPROVED_LOCAL_MODEL, args.stability_minutes, args.stability_interval)
        if not stability.get("ok"):
            print("STABILITY FAILED — do not promote route.")
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            out = args.json_out or (RESULTS_DIR / f"fail-stability-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
            out.write_text(
                json.dumps(
                    {
                        "at": _utc(),
                        "gate": gate,
                        "prompts": prompt_results,
                        "stability": {k: v for k, v in stability.items() if k != "detail"},
                        "promoted": False,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            return 1

    tps_vals = [r["tokensPerSecond"] for r in prompt_results if r.get("tokensPerSecond")]
    summary = {
        "at": _utc(),
        "promoted": True,
        "gate": gate,
        "prompts": prompt_results,
        "stability": ({k: v for k, v in stability.items() if k != "detail"} if stability else None),
        "metrics": {
            "medianTokensPerSecond": round(statistics.median(tps_vals), 2) if tps_vals else None,
            "vramSafetyMarginGiB": VRAM_SAFETY_MARGIN_GIB,
        },
        "routing": {
            "localApprovedLanes": ["chat8b", "reason21b", "escalate30b", "coder32b"],
            "model": APPROVED_LOCAL_MODEL,
            "cloudUnchanged": True,
        },
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = args.json_out or (RESULTS_DIR / f"pass-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"PASS — results: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
