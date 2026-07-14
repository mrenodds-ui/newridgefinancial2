"""Moonshot AI — What next after compact pages + gate harden (CONSULT ONLY)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / ".local_logs" / "moonshot_financial_eval"
DOCS = REPO / "NewRidgeFinancial2" / "docs"
OUT.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

HELPER = (
    REPO
    / "_archive"
    / "2026-07-10"
    / ".local_logs"
    / "moonshot_financial_eval"
    / "_run_moonshot_eval.py"
)
sys.path.insert(0, str(HELPER.parent))
from _run_moonshot_eval import extract_message_content, resolve_api_and_endpoint  # noqa: E402

OPERATOR_REQUEST_VERBATIM = "next".strip()

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex (hal-10550).
Operator said only: "next". Recommend the single best NEXT work package now that:
- Expert SE Phases 1–3 shipped (gate split, threaded HTTPS, import health, ERA CAS/claims actions)
- Compact professional pages Phases 1–5 shipped (motion kill, empty collapse, size discipline,
  Claims pipeline+kanban subpage, HAL sole-l, density toggle)
- Import gate hardened: warning/optional don't 403; critical stale-with-rows don't hard-fail;
  QB expenses demoted to warning
- Branch fix/main-validate-ci pushed; no PR yet (gh auth may be needed)

CONSULT ONLY. Pick ONE primary next package + optional follow-ons.
Be blunt. No invented dollars.

OUTPUT:
# Verdict (one sentence: the next package)
## 0. Intent
## 1. Already Done (do not redo)
## 2. Recommended NEXT (single package)
Goal, why now, effort, files, validation gate
## 3. Runner-up options (max 3)
## 4. Approval checklist
DO NOT APPLY CODE.
"""


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No API key", file=sys.stderr)
        return 1
    model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    if "moonshot" not in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2").strip()
    print(f"Using {key_name} @ {base_url} model={model}")
    user = (
        f"OPERATOR REQUEST (VERBATIM): {OPERATOR_REQUEST_VERBATIM}\n\n"
        "What should we do NEXT on NR2 Apex at hal-10550? CONSULT ONLY.\n\n"
        "### Shipped today\n"
        "- Expert SE REC-001/002/003/004/005/006/007 applied\n"
        "- Compact pages plan validated CONDITIONAL APPROVE then fully applied\n"
        "- Import 403 durability: softGaps for warning; stale+rows connected; expenses=warning\n"
        "- Commits on fix/main-validate-ci: 2f51309, 785eb0a, 0384ddf\n"
        "- Live: import fresh, widgets 200 when SoftDent criticals present\n"
        "- Remaining risk: inbox files still flap (AR/dashboard/QB) between syncs\n"
        "- NICE left from Expert SE: REC-008 batch narratives, REC-009 voice context carry\n"
        "- PR not opened yet\n"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 6000,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Whats Next Consult"
    req = urllib.request.Request(base_url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            content = extract_message_content(json.loads(resp.read().decode()))
        status = "ok"
    except Exception as exc:
        content = str(exc)
        status = "error"
    header = (
        f"# Moonshot AI — What's Next (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n**Model:** {model}  \n**Key:** {key_name}  \n"
        f"**Status:** {status}  \n**Build:** hal-10550  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_compact_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_COMPACT_{DATE}.md"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_COMPACT_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    print(out)
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
