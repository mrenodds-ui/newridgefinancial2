"""NR2 live page smoke using actual /api/apex/widgets/{page} payloads."""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://127.0.0.1:8765"
CTX = ssl._create_unverified_context()
OUT = Path(r"C:\SoftDentFinancialExports\nr2_page_smoke_live_2026-07-13.json")

PAGES = [
    "financial",
    "taxes",
    "softdent",
    "quickbooks",
    "ar",
    "claims",
    "narratives",
    "documents",
    "library",
    "office-manager",
    "hal",
]

APEX_GETS = [
    "/api/health",
    "/api/apex/hal/status",
    "/api/apex/hal/orchestrator",
    "/api/apex/ticker",
    "/api/apex/unified/snapshot",
    "/api/apex/gold-era-settlement/status",
    "/api/apex/gold-drop-facilitation/status",
    "/api/apex/prodbyada/status",
    "/api/apex/print-preview-audit/status",
    "/api/apex/pwimages-eligibility/status",
]


def fetch(path: str, *, method: str = "GET", body: dict | None = None, timeout: float = 60.0) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            payload = json.loads(raw) if raw else {}
            return {"ok": True, "status": resp.status, "ms": round((time.perf_counter() - t0) * 1000), "payload": payload}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"_raw": raw[:400]}
        return {
            "ok": False,
            "status": int(exc.code),
            "ms": round((time.perf_counter() - t0) * 1000),
            "payload": payload,
            "error": str(exc.reason),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status": None,
            "ms": round((time.perf_counter() - t0) * 1000),
            "error": f"{type(exc).__name__}:{exc}",
        }


def classify(w: dict) -> str:
    st = str(w.get("status") or "").lower()
    if st in {"error", "failed", "fail"}:
        return "broken"
    if w.get("error") and w.get("ok") is False:
        return "broken"
    if st in {"pending", "gap", "missing", "stale", "warn", "warning"}:
        return "honest_gap_or_pending"
    if w.get("gapCode") and str(w.get("gapCode")).upper() not in {"OK", "GOLD_OK", "NONE", ""}:
        return "honest_gap_or_pending"
    if w.get("pending") or w.get("empty"):
        return "honest_gap_or_pending"
    if st in {"ok", "ready", "success", "info", "neutral", ""}:
        # empty message with no numbers can still be working shell
        return "working"
    return "working"


def main() -> int:
    report: dict = {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "base": BASE,
        "pages": {},
        "apex": {},
        "hal": {},
        "summary": {},
    }

    for path in APEX_GETS:
        r = fetch(path)
        pl = r.get("payload") if isinstance(r.get("payload"), dict) else {}
        report["apex"][path] = {
            "ok": r.get("ok"),
            "status": r.get("status"),
            "ms": r.get("ms"),
            "error": r.get("error"),
            "buildId": pl.get("buildId") or pl.get("packageBuildId"),
            "reply": str(pl.get("reply") or pl.get("statusLabel") or "")[:140],
        }

    totals = {"working": 0, "honest_gap_or_pending": 0, "broken": 0}
    for page in PAGES:
        r = fetch(f"/api/apex/widgets/{page}")
        entry: dict = {
            "apiOk": r.get("ok"),
            "httpStatus": r.get("status"),
            "ms": r.get("ms"),
            "error": r.get("error"),
            "errors": (r.get("payload") or {}).get("errors") if r.get("ok") else None,
            "widgets": [],
            "counts": {},
        }
        widgets = ((r.get("payload") or {}).get("widgets") or []) if r.get("ok") else []
        counts = {"working": 0, "honest_gap_or_pending": 0, "broken": 0}
        for w in widgets:
            if not isinstance(w, dict):
                continue
            state = classify(w)
            counts[state] = counts.get(state, 0) + 1
            totals[state] = totals.get(state, 0) + 1
            entry["widgets"].append(
                {
                    "id": w.get("id"),
                    "label": w.get("label") or w.get("title"),
                    "type": w.get("type"),
                    "status": w.get("status"),
                    "state": state,
                    "message": str(w.get("message") or w.get("hint") or "")[:160],
                    "gapCode": w.get("gapCode"),
                }
            )
        entry["counts"] = counts
        entry["widgetCount"] = len(entry["widgets"])
        report["pages"][page] = entry

    # HAL prompt via orchestrate
    for prompt in ("Import status", "Summarize MTD production", "Review A/R aging"):
        r = fetch(
            "/api/apex/hal/orchestrate",
            method="POST",
            body={"query": prompt, "page": "financial"},
            timeout=120.0,
        )
        pl = r.get("payload") if isinstance(r.get("payload"), dict) else {}
        report["hal"][prompt] = {
            "ok": r.get("ok"),
            "status": r.get("status"),
            "ms": r.get("ms"),
            "error": r.get("error"),
            "lane": pl.get("lane") or (pl.get("route") or {}).get("lane"),
            "replyPreview": str(
                pl.get("reply") or pl.get("answer") or pl.get("message") or pl.get("text") or ""
            )[:240],
            "keys": sorted(pl.keys())[:20] if pl else [],
        }

    report["summary"] = {
        **totals,
        "pagesOk": sum(1 for p in report["pages"].values() if p.get("apiOk")),
        "pagesFail": sum(1 for p in report["pages"].values() if not p.get("apiOk")),
        "apexOk": sum(1 for v in report["apex"].values() if v.get("ok")),
        "apexFail": sum(1 for v in report["apex"].values() if not v.get("ok")),
        "halOk": sum(1 for v in report["hal"].values() if v.get("ok")),
        "halFail": sum(1 for v in report["hal"].values() if not v.get("ok")),
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print("WROTE", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
