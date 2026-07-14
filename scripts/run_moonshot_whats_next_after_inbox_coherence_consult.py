"""Moonshot AI — What next after inbox sync coherence (CONSULT ONLY)."""

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

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex (hal-10560).
Operator said only: "next". Recommend the single best NEXT work package now that:
- Expert SE Phases 1–3 shipped (gate split, threaded HTTPS, import health, ERA CAS/claims actions)
- Compact professional pages Phases 1–5 shipped
- Import gate hardened (warning/optional softGaps; stale-with-rows; QB expenses=warning)
- Inbox sync coherence shipped (hal-10560): retention soft-skip criticals; content-hash
  no-op writes; Period expenses protected; direct-first mirror skips existing criticals;
  two consecutive syncs left AR/dashboard/QB expenses bit-identical
- Branch fix/main-validate-ci pushed through 0dcf1d7; NO PR yet (gh auth login still needed)
- NICE still open from Expert SE: REC-008 batch narratives, REC-009 voice context carry

CONSULT ONLY. Pick ONE primary next package + optional follow-ons.
Be blunt. No invented dollars. Prefer landing value already shipped over speculative NICE
unless there is a clear production risk remaining.

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
        model = str(
            os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2"
        ).strip()
    print(f"Using {key_name} @ {base_url} model={model}")
    user = (
        f"OPERATOR REQUEST (VERBATIM): {OPERATOR_REQUEST_VERBATIM}\n\n"
        "What should we do NEXT on NR2 Apex at hal-10560? CONSULT ONLY.\n\n"
        "### Shipped\n"
        "- Expert SE REC-001..007 applied\n"
        "- Compact pages Phases 1–5 applied\n"
        "- Import 403 durability applied\n"
        "- Inbox sync coherence applied (hal-10560 / commit 0dcf1d7)\n"
        "- Docs: MOONSHOT_INBOX_SYNC_COHERENCE_APPLIED_2026-07-11.md\n"
        "- Prior what's-next recommended inbox coherence first; that is DONE\n"
        "- Branch fix/main-validate-ci ahead of main; gh pr blocked (needs gh auth login)\n"
        "- Open NICE: REC-008 batch narratives, REC-009 voice context carry\n"
        "- Untracked leftover: site/index.pre-apex.html (exclude from commits)\n"
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
        headers["X-Title"] = "NR2 Whats Next After Inbox Coherence"
    req = urllib.request.Request(
        base_url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            content = extract_message_content(json.loads(resp.read().decode()))
        status = "ok"
    except Exception as exc:
        content = str(exc)
        status = "error"
    header = (
        f"# Moonshot AI — What's Next After Inbox Coherence (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n**Model:** {model}  \n**Key:** {key_name}  \n"
        f"**Status:** {status}  \n**Build:** hal-10560  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_inbox_coherence_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_INBOX_COHERENCE_{DATE}.md"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_INBOX_COHERENCE_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    print(out)
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
