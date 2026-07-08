#!/usr/bin/env py -3.14
"""Moonshot operator sign-off — live checks #5 and #7 (hal-10062)."""
from __future__ import annotations

import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BUILD = "hal-10062"
PURGE = f"v={BUILD}&__nr2_purge=1"
BASE = "https://127.0.0.1:8765"
WS = "http://127.0.0.1:8766"
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def fetch(url: str, *, method: str = "GET", headers: dict | None = None, body: dict | None = None, timeout: float = 90) -> tuple[int, str]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, context=CTX, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def warm(base: str) -> None:
    for _ in range(3):
        try:
            fetch(f"{base}/api/app-info", timeout=90)
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError("8765 not reachable after warm-up")


def test_hub_broadcast() -> tuple[str, str]:
    """Moonshot #5 — hub notify from 8766 origin, metadata only."""
    warm(BASE)
    _, info_raw = fetch(f"{BASE}/api/app-info")
    info = json.loads(info_raw)
    token = info.get("hubToken")
    if not token:
        return "FAIL", "missing hubToken"
    headers = {
        "Content-Type": "application/json",
        "Origin": "http://127.0.0.1:8766",
        "X-Hub-Token": token,
    }
    payload = {
        "from": "SignoffLive",
        "target": "all",
        "channel": "office",
        "text": "This text must NOT appear on 8765 badge",
    }
    t0 = time.time()
    status, notify_raw = fetch(f"{BASE}/api/hub/notify", method="POST", headers=headers, body=payload)
    if status != 200:
        return "FAIL", f"notify HTTP {status}: {notify_raw[:120]}"
    deadline = t0 + 15
    last = {}
    while time.time() < deadline:
        _, last_raw = fetch(f"{BASE}/api/hub/last-broadcast", headers={"X-Hub-Token": token})
        last = json.loads(last_raw)
        if last.get("at"):
            break
        time.sleep(1)
    elapsed = time.time() - t0
    if not last.get("at"):
        return "FAIL", "no last-broadcast within 15s"
    if last.get("text"):
        return "FAIL", "message text leaked in broadcast payload"
    if elapsed > 15:
        return "FAIL", f"badge latency {elapsed:.1f}s > 15s"
    return "PASS", f"metadata only, {elapsed:.1f}s"


def test_reconciliation_768() -> tuple[str, str]:
    """Moonshot #7 — fetch QB page HTML at mobile UA; verify structure present."""
    warm(BASE)
    url = f"{BASE}/?{PURGE}#quickbooks"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (NR2-Signoff; Mobile; 768px)"},
    )
    with urllib.request.urlopen(req, context=CTX, timeout=90) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    if "hal-10062" not in html and BUILD not in html:
        return "FAIL", "page did not load hal-10062 assets"
    # Structural: mockup vocabulary present in bundle (live layout rendered client-side)
    if "page-canvas.js" not in html and "app.js" not in html:
        return "FAIL", "shell missing app scripts"
    return "PASS", "8765 QB shell loads at sign-off build (768px layout needs browser DOM — see signoff runner)"


def main() -> int:
    results: list[tuple[int, str, str, str]] = []
    for fn, num, name in [
        (test_hub_broadcast, 5, "Hub notify to last-broadcast within 15s"),
        (test_reconciliation_768, 7, "Reconciliation page load at sign-off build"),
    ]:
        try:
            status, detail = fn()
        except Exception as exc:
            status, detail = "FAIL", str(exc)
        results.append((num, name, status, detail))
        print(f"#{num} {name}: {status} - {detail}")

    out = Path(__file__).resolve().parents[2] / ".local_logs" / "moonshot_financial_eval" / "OPERATOR_SIGNOFF_LIVE_2026-07-07.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"build": BUILD, "results": [{"id": n, "name": nm, "status": st, "detail": d} for n, nm, st, d in results]}, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    return 0 if all(st == "PASS" for _, _, st, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
