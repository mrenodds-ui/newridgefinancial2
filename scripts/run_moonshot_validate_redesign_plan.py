"""Moonshot AI — validate the complete redesign plan (CONSULT ONLY).

Sends the prior redesign plan back to Moonshot for formal validation
against the operator's verbatim requirements. Does NOT apply anything.
"""

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

OPERATOR_REQUEST_VERBATIM = """
i dont want a mock up but a complete high tech redesign of the entire program wilf smal widgets of graphs charts and icon like print buttons, to remove current layout and a detailed plan from start to fish on how to do it.  i want it to look highly high tech professional with a detailed futuristic presentation wih anything animated and automated.  problem is i dont want overlays, old legacry rearrangement.  i want that wiped out before laying down a new design.  i believe past inknown programs were interfereing.  if i need a backend do it and replace it with functions that help the frontend.  plsease have him give code, report and dont proceed until validated.  do not rewrite what i want.
""".strip()

PLAN_PATH = DOCS / "MOONSHOT_COMPLETE_REDESIGN_PLAN_2026-07-10.md"

SYSTEM = """You are Moonshot AI (kimi-k2 class) acting as an independent VALIDATOR of your own
prior redesign plan for NewRidge Financial 2.0.

Role: Validate the plan against the operator's VERBATIM requirements. Be critical.
Do NOT rewrite the operator's request. Do NOT apply any code. CONSULT ONLY.

Operator requirements checklist (must all be satisfied for APPROVE):
1. NOT a mockup — complete high-tech redesign of the entire program
2. Small widgets with graphs, charts, and icon controls (e.g. print buttons)
3. Remove current layout; detailed plan start → finish
4. Highly high-tech professional, futuristic presentation; animated + automated
5. NO overlays; NO old legacy rearrangement; wipe BEFORE new design
6. Account for past unknown program interference
7. Backend if needed — functions that help the frontend
8. Code + report provided
9. Do not proceed until validated
10. Do not rewrite what the operator wants

Return markdown with EXACTLY these sections:
# Validation Verdict (APPROVE | CONDITIONAL APPROVE | REJECT)
## 1. Requirement Coverage Matrix
For each of the 10 requirements: PASS | PARTIAL | FAIL — evidence from the plan — gap if any
## 2. Wipe Plan Adequacy
Is wipe-first strong enough? Missing deletes? Dangerous deletes (app_data, secrets)?
## 3. Design System Fit
Small widgets, charts, icons, futuristic/animated/automated — enough or weak?
## 4. Backend Helping Frontend
Are proposed APIs sufficient? Missing functions?
## 5. Code Deliverables Quality
Are foundations paste-ready and aligned with wipe-first (not overlay)? Gaps?
## 6. Phase Plan Start→Finish
Completeness, order, validation gates, risks
## 7. Interference / Unknown Programs
Does the plan adequately neutralize interference?
## 8. Required Modifications Before Operator Can Say Proceed
Concrete edits to the plan (if CONDITIONAL or REJECT). If APPROVE, say "None."
## 9. Operator Validation Script
Exact reply strings for: proceed / modify / abort
## 10. Final Recommendation to Operator
One short paragraph: approve as-is, approve with listed mods, or reject and replan.

Be strict. Prefer CONDITIONAL APPROVE over rubber-stamping. CONSULT ONLY.
"""


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No Moonshot/OpenRouter API key.", file=sys.stderr)
        return 1

    if "moonshot" in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    else:
        model = str(
            os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2"
        ).strip()

    if not PLAN_PATH.is_file():
        print(f"Missing plan: {PLAN_PATH}", file=sys.stderr)
        return 1

    plan_text = PLAN_PATH.read_text(encoding="utf-8", errors="replace")
    # Keep under model context; plan is ~30k chars — send full if possible, else truncate mid
    max_plan = 28000
    if len(plan_text) > max_plan:
        plan_text = plan_text[:max_plan] + "\n\n... [plan truncated for validator context] ..."

    print(f"Using {key_name} @ {base_url} model={model}")
    print(f"Validating plan ({len(plan_text)} chars)...")

    user = (
        "OPERATOR REQUEST (VERBATIM — do not rewrite):\n\n"
        f"{OPERATOR_REQUEST_VERBATIM}\n\n"
        "The operator asks you to VALIDATE the following redesign plan/report before any apply.\n"
        "Return formal validation verdict. CONSULT ONLY — do not proceed with implementation.\n\n"
        "## PLAN UNDER VALIDATION\n\n"
        f"{plan_text}\n"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 10000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Redesign Plan Validation"

    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3600) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = extract_message_content(body)
        status = "ok"
    except urllib.error.HTTPError as exc:
        content = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:4000]}"
        status = f"HTTP {exc.code}"
    except Exception as exc:
        content = str(exc)
        status = "error"

    header = (
        f"# Moonshot AI — Redesign Plan Validation Report\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Plan validated:** `NewRidgeFinancial2/docs/MOONSHOT_COMPLETE_REDESIGN_PLAN_2026-07-10.md`  \n"
        f"**Script:** `scripts/run_moonshot_validate_redesign_plan.py`  \n"
        f"**Apply:** DO NOT APPLY — validation consult only.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_REDESIGN_PLAN_VALIDATION_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_REDESIGN_PLAN_VALIDATION_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
