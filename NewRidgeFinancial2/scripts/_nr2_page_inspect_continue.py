"""Live re-inspect after fix-all continue (honest empty + library seed)."""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

CTX = ssl._create_unverified_context()
BASE = "https://127.0.0.1:8765"
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
HONEST = {
    "ZERO_VOLUME",
    "NO_PATIENT_CONTEXT",
    "LIBRARY_NOT_INDEXED",
    "GOLD_CSV_MISSING",
    "ERA_835_REQUIRED",
    "CLAIMS_AR_RECONCILE_MISMATCH",
}


def req(path: str, method: str = "GET", body: dict | None = None, token: str | None = None):
    headers = {"Accept": "application/json"}
    data = None
    if token:
        headers["X-NR2-Session-Token"] = token
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, context=CTX, timeout=180) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"body": raw[:300]}
        return e.code, payload


def classify(w: dict) -> str:
    s = str(w.get("status") or "").lower()
    gap = str(w.get("gapCode") or "").upper()
    msg = str(w.get("message") or "")
    if w.get("id") == "warming-bridge":
        return "warming"
    if s in {"error", "failed"}:
        return "faulty"
    if gap in HONEST:
        return "honest"
    if s in {"pending", "gap", "missing", "stale", "warn", "warning", "empty"}:
        return "faulty"
    if gap and gap not in {"OK", "GOLD_OK", "NONE", "", "READY"}:
        return "faulty"
    if any(x in msg.upper() for x in ["REQUIRED", "MISMATCH", "MISSING", "GOLD_CSV", "ERA_835", "DEF-001"]):
        return "faulty"
    return "active"


def main() -> int:
    for _ in range(25):
        st, d = req("/api/health")
        if st == 200 and isinstance(d, dict) and d.get("ok"):
            break
        time.sleep(1)
    else:
        print("health fail")
        return 1

    st, app = req("/api/app-info")
    token = (app or {}).get("sessionToken")
    print("schema", (app or {}).get("schemaVersion"), "asset", (app or {}).get("assetVersion"))
    st, sync = req("/api/apex/sync/trigger", "POST", {"fullSync": True}, token=token)
    print("SYNC", st, (sync or {}).get("status"), (sync or {}).get("ok"))

    st, app = req("/api/app-info")
    ir = (app or {}).get("importReadiness") or {}
    print("readiness", ir.get("level"))
    print(
        "ar_gaps",
        [g for g in (ir.get("datasetGaps") or []) if "ar" in str(g.get("datasetKey") or "").lower()],
    )

    for i in range(12):
        warm = 0
        counts = {}
        for p in PAGES:
            time.sleep(0.1)
            _, d = req(f"/api/apex/widgets/{p}")
            ws = (d or {}).get("widgets") or []
            ids = [w.get("id") for w in ws if isinstance(w, dict)]
            if ids == ["warming-bridge"]:
                warm += 1
            counts[p] = len(ws)
        print(f"t+{i * 3}s warm={warm}/11", counts)
        if warm == 0:
            break
        time.sleep(3)

    totals = Counter()
    by_page = {}
    rows = []
    for p in PAGES:
        _, d = req(f"/api/apex/widgets/{p}")
        ws = (d or {}).get("widgets") or []
        c = Counter()
        for w in ws:
            if not isinstance(w, dict):
                continue
            state = classify(w)
            c[state] += 1
            totals[state] += 1
            if state != "active":
                rows.append(
                    {
                        "page": p,
                        "id": w.get("id"),
                        "state": state,
                        "status": w.get("status"),
                        "gapCode": w.get("gapCode"),
                        "msg": str(w.get("message") or "")[:120],
                    }
                )
        by_page[p] = dict(c)

    out = {
        "summary": dict(totals),
        "pages": by_page,
        "non_active": rows,
        "app": {
            "schemaVersion": (app or {}).get("schemaVersion"),
            "importReadiness": ir.get("level"),
            "arGaps": [
                g
                for g in (ir.get("datasetGaps") or [])
                if "ar" in str(g.get("datasetKey") or "").lower()
            ],
        },
    }
    path = Path(__file__).resolve().parents[1] / "docs" / "_nr2_page_inspect_after_continue.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("WROTE", path)
    print("SUMMARY", dict(totals))
    for p, info in by_page.items():
        print(p, info)
    for r in rows:
        print(r["state"], r["page"], r["id"], r.get("gapCode"), r["msg"][:70])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
