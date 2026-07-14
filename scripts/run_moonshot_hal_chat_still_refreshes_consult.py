"""Moonshot AI — why HAL chat still refreshes (CONSULT ONLY).

Operator request is passed VERBATIM. Does NOT apply any code.
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

OPERATOR_REQUEST_VERBATIM = """
ask moonshot why it still does it
""".strip()

OPERATOR_CONTEXT = """
Operator symptom (ongoing): every time they try to ask HAL a question in the HAL chat box,
the page refreshes and they cannot ask him a question.

Cursor agent already shipped/pushed hal-10626 which removed the insight-SSE hard remount
(Apex.loadPage("hal") from nr2-insight-sse.js). Build is live as hal-10626 / commit 2276962.
Operator still experiences the refresh — diagnose remaining causes and name the most likely one.
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — senior frontend + Apex bridge debugger for
NewRidge Financial 2.0 (NR2) on Windows. CONSULT ONLY — do not apply code.

Mission: explain WHY the HAL chat box still refreshes / remounts when the operator tries to ask
a question, AFTER the hal-10626 insight-SSE remount removal.

Hard rules:
- Treat the operator request as the source of truth.
- Prefer remaining CODE PATHS that still call loadPage("hal") non-silent, location.reload,
  renderWidgets wipe, softRenderHalMain while composing, flashStage glitch that FEELS like refresh,
  board-actions navigate/sync, SW/build skew, or stale cached assets.
- Rank causes by likelihood given the shipped fix.
- Distiguish true browser reload vs Apex stage remount vs visual glitch.
- Never invent SoftDent/QB dollars.
- CONSULT ONLY.

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent
## 1. What "still does it" means (reload vs remount vs visual)
## 2. Why it can STILL happen after hal-10626
Ranked remaining causes with file:function evidence.
## 3. Most likely root cause right now
One primary answer + why.
## 4. Fast verify plan (operator can do in 2 minutes)
DevTools / network / which string to grep in Sources for loaded JS.
## 5. Minimal fix package (paste-ready only if needed)
## 6. Do Not Apply Gate
"""


def _slice(path: Path, *needles: str, radius: int = 18) -> str:
    if not path.is_file():
        return f"(missing {path})"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    hits: list[str] = []
    for i, line in enumerate(lines):
        if any(n in line for n in needles):
            a = max(0, i - radius)
            b = min(len(lines), i + radius + 1)
            chunk = "\n".join(f"{ln+1}: {lines[ln]}" for ln in range(a, b))
            hits.append(f"--- {path.name}:{i+1} ---\n{chunk}")
    if not hits:
        return f"(no hits for {needles} in {path.name})"
    return "\n\n".join(hits[:8])


def build_context() -> str:
    site = REPO / "NewRidgeFinancial2" / "site"
    parts = [
        f"### BUILD\n```json\n{(REPO / 'NewRidgeFinancial2' / 'nr2-build.json').read_text(encoding='utf-8')}\n```",
        "### nr2-insight-sse.js (full after hal-10626)\n```js\n"
        + (site / "nr2-insight-sse.js").read_text(encoding="utf-8")
        + "\n```",
        "### apex-core.js remaining remount / chat paths\n```js\n"
        + _slice(
            site / "apex-core.js",
            'loadPage("hal"',
            "softRenderHalMain",
            "flashStage",
            "location.reload",
            "chatComposerActive",
            "refresh_page",
            "refresh_widget",
            "renderWidgets(list)",
            "halChatBusy",
        )
        + "\n```",
        "### apex-hal-bridge.js\n```js\n"
        + _slice(site / "apex-hal-bridge.js", 'loadPage("hal"', "askHalFromBridge")
        + "\n```",
        "### apex-motion-helper.js flashStage\n```js\n"
        + _slice(site / "apex-motion-helper.js", "flashStage", "is-glitching")
        + "\n```",
        "### sw.js build gate\n```js\n"
        + _slice(site / "sw.js", "BUILD_ID", "location", "cache")
        + "\n```",
    ]
    return "\n\n".join(parts)


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

    print(f"key={key_name} model={model} base={base_url}", flush=True)
    user = (
        "OPERATOR REQUEST (VERBATIM — do not rewrite):\n\n"
        f"{OPERATOR_REQUEST_VERBATIM}\n\n"
        "OPERATOR CONTEXT (facts):\n\n"
        f"{OPERATOR_CONTEXT}\n\n"
        "CONSULT ONLY — diagnose remaining HAL chat refresh causes after hal-10626.\n\n"
        "## Code evidence\n\n"
        + build_context()
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0 if "moonshot" in base_url.lower() else 0.2,
        "max_tokens": 8000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 HAL Chat Still Refreshes Consult"

    print("Calling Moonshot AI (consult only)...", flush=True)
    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
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
        f"# Moonshot AI — HAL Chat Still Refreshes (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10626  \n"
        f"**Script:** `scripts/run_moonshot_hal_chat_still_refreshes_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator validates.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_HAL_CHAT_STILL_REFRESHES_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    docs_file = DOCS / f"MOONSHOT_HAL_CHAT_STILL_REFRESHES_CONSULT_{DATE}.md"
    docs_file.write_text(full, encoding="utf-8")
    print(f"Wrote {out_file}")
    print(f"Wrote {docs_file}")
    print(full[:4000])
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
