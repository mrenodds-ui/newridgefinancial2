"""Gather live NR2 snapshot for Moonshot full-program coding consult."""
from __future__ import annotations

import json
import ssl
import urllib.request
from pathlib import Path

CTX = ssl._create_unverified_context()
BASE = "https://127.0.0.1:8765"
OUT = Path(__file__).resolve().parents[1] / ".local_logs" / "moonshot_financial_eval"
OUT.mkdir(parents=True, exist_ok=True)


def get(path: str, timeout: int = 90):
    try:
        with urllib.request.urlopen(BASE + path, context=CTX, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        return None, {"error": type(e).__name__, "msg": str(e)[:300]}


def main() -> int:
    snap: dict = {"base": BASE}
    _, snap["health"] = get("/api/health", 15)
    _, snap["appInfo"] = get("/api/app-info", 15)
    _, snap["census"] = get("/api/apex/widget-census", 90)
    pages = {}
    for page in (
        "financial",
        "taxes",
        "claims",
        "softdent",
        "ar",
        "quickbooks",
        "office-manager",
        "documents",
        "narratives",
        "hal",
    ):
        _, d = get(f"/api/apex/widgets/{page}", 120)
        if isinstance(d, dict):
            ids = [w.get("id") for w in (d.get("widgets") or []) if isinstance(w, dict)]
            pages[page] = {
                "buildId": d.get("buildId"),
                "warming": d.get("warming"),
                "n": len(ids),
                "idsHead": ids[:15],
                "hasTaxCore": "tax-core-strip" in ids,
                "hasTaxTable": "tax-planning-table" in ids,
                "hasTaxCal": "tax-calendar-main" in ids,
            }
        else:
            pages[page] = d
    snap["pages"] = pages
    path = OUT / "moonshot_full_program_live_snap.json"
    path.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    print(json.dumps(snap, indent=2)[:12000])
    print("WROTE", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
