"""Moonshot AI — recommendations for HAL main page + History/System Logs (CONSULT ONLY).

Operator: ask moonshot ai for any recommendation for hal's page and report
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / ".local_logs" / "moonshot_financial_eval"
DOCS = REPO / "NewRidgeFinancial2" / "docs"
NR2 = REPO / "NewRidgeFinancial2"
SITE = NR2 / "site"
OUT.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

CTX = ssl._create_unverified_context()
BASE = os.getenv("NR2_BROWSER", "https://127.0.0.1:8765").rstrip("/")


def _load_dotenv() -> None:
    """Load gitignored .env keys into process env if missing (cloud unblock path)."""
    for path in (REPO / ".env", NR2 / ".env"):
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, val = line.partition("=")
                name = name.strip()
                val = val.strip().strip("'").strip('"')
                if name and val and not os.getenv(name):
                    os.environ[name] = val
        except OSError:
            pass


def resolve_api_and_endpoint() -> tuple[str, str, str]:
    _load_dotenv()
    candidates = (
        ("MOONSHOT_API_KEY", os.getenv("MOONSHOT_API_KEY", "").strip()),
        ("OPENROUTER_API_KEY", os.getenv("OPENROUTER_API_KEY", "").strip()),
        ("KIMI_K2_API_KEY", os.getenv("KIMI_K2_API_KEY", "").strip()),
    )
    key_name, api_key = "", ""
    for name, val in candidates:
        if val:
            key_name, api_key = name, val
            break
    base = (
        os.getenv("MOONSHOT_API_BASE") or os.getenv("KIMI_K2_BASE_URL") or ""
    ).strip()
    if not base:
        if key_name == "MOONSHOT_API_KEY" or (api_key or "").startswith("sk-nv"):
            base = "https://api.moonshot.ai/v1/chat/completions"
        else:
            base = "https://openrouter.ai/api/v1/chat/completions"
    if not base.endswith("/chat/completions"):
        base = base.rstrip("/") + "/chat/completions"
    return key_name, api_key, base


def extract_message_content(raw: dict) -> str:
    try:
        choices = raw.get("choices") or []
        if not choices:
            return ""
        msg = (choices[0] or {}).get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text") or ""))
                elif isinstance(block, str):
                    parts.append(block)
            return "\n".join(p for p in parts if p)
        return str(content or "")
    except Exception:
        return ""

OPERATOR_REQUEST_VERBATIM = (
    "ask moonshot ai for any recommendation for hal's page and report"
)

SYSTEM = """You are Moonshot AI — principal UI/data architect + SoftDent RCM engineer
for NR2 Apex HAL (BUILD **hal-10628** + HAL History/System Logs redesign on
branch cursor/hal-subpages-design-d32f).

CONSULT ONLY — do not claim applied. empty ≠ $0. Never invent SoftDent dollars.
Desktop SoftDent Excel/Print Preview remains period-close truth when needed.

CURRENT HAL SURFACE (treat live snapshot as truth):
- Main Chat (#hal): medium spine — Neural Core + Import Health | Program Posture
  trust pair + AI Insight + sticky Ask HAL rail (hal-10624…10628). Mosaic KPI
  clutter (Production/Collections/A/R/Claims/Teach HAL) removed from main.
- Subpages: Chat | Ops | History | System Logs
- History (#hal/history): one strip + conversation feed + live Ask HAL rail;
  Ask again / Ask HAL row actions stay on-page; no holo-tilt wobble.
- System Logs (#hal/system-logs): one strip + diagnostic console + live Ask HAL
  rail; per-row Ask HAL.
- Chat persistence: history-append API; stage lock / no remount while Ask HAL
  composer is active (hal-10625–10628).
- Cloud/LLM prose often fails in cloud preview (Connection refused to hub);
  grounded/tool lanes still answer some asks.
- Import readiness in cloud preview may be monkeypatched fresh while summary
  still shows missing datasets — call out honesty gaps if you see them.

DESIGN INTENT (morning medium-confidence mock):
Import Cache → Bridge Errors → trust pair → SoftDent/Reports recon → Recommended
Actions → AI Insight + Ask HAL. Later commits intentionally dropped cache/errors/
recon/actions tiles from main when unwired/empty. Do NOT blindly restore clutter.

YOUR JOB:
Recommend the best improvements for HAL's page (main + subpages) for staff
daily use. Prefer highest ROI. Prefer OPS when data truth is the blocker.
Prefer CODE only when UI/wiring friction remains after data is honest.

OUTPUT (strict markdown):
# Verdict (one sentence — THE top recommendation)
## 0. Operator Intent (verbatim)
## 1. HAL page assessment (what works / what's weak now)
## 2. Recommended NEXT (name, why now, effort, REAL files or OPS steps, validation gate)
## 3. Runner-ups (2–4 ranked)
## 4. History / System Logs recommendations (specific)
## 5. Ask HAL chat recommendations (reliability + UX)
## 6. What NOT to redo
## 7. Acceptance criteria
## 8. Executive Summary (5 bullets)
## 9. Approval checklist
DO NOT APPLY CODE.
"""


def get_json(path: str, timeout: int = 90):
    try:
        with urllib.request.urlopen(BASE + path, context=CTX, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        return {"error": type(e).__name__, "msg": str(e)[:200]}


def _widget_digest(payload: dict) -> dict:
    if not isinstance(payload, dict) or payload.get("error"):
        return payload
    widgets = [w for w in (payload.get("widgets") or []) if isinstance(w, dict)]
    return {
        "buildId": payload.get("buildId"),
        "sub": payload.get("sub"),
        "n": len(widgets),
        "ids": [w.get("id") for w in widgets],
        "types": [w.get("type") for w in widgets],
        "labels": [w.get("label") or w.get("title") for w in widgets],
        "chrome": [w.get("chrome") for w in widgets],
        "sourceNote": str(payload.get("sourceNote") or "")[:240],
    }


def live_snapshot() -> str:
    sys.path.insert(0, str(NR2))
    live: dict = {
        "buildExpected": "hal-10628",
        "branchHint": "cursor/hal-subpages-design-d32f",
        "operatorAsk": OPERATOR_REQUEST_VERBATIM,
        "prHint": "https://github.com/mrenodds-ui/newridgefamilyfinancial/pull/42",
    }
    try:
        from apex_backend import BUILD_ID, _hal_widgets

        live["buildId"] = BUILD_ID
        live["halWidgetsDoc"] = (_hal_widgets.__doc__ or "")[:240]
    except Exception as exc:  # noqa: BLE001
        live["buildIdError"] = f"{type(exc).__name__}:{exc}"

    live["appInfo"] = get_json("/api/app-info", 20)
    live["halStatus"] = get_json("/api/apex/hal/status", 30)
    live["pages"] = {
        "hal": _widget_digest(get_json("/api/apex/widgets/hal", 90)),
        "hal/history": _widget_digest(get_json("/api/apex/widgets/hal?sub=history", 90)),
        "hal/system-logs": _widget_digest(
            get_json("/api/apex/widgets/hal?sub=system-logs", 90)
        ),
        "hal/ops": _widget_digest(get_json("/api/apex/widgets/hal?sub=ops", 60)),
    }
    for path, key in (
        ("/api/apex/hal/sync-status", "syncStatus"),
        ("/api/apex/gold-era-settlement/status", "goldEra"),
    ):
        live[key] = get_json(path, 45)

    # Tiny code evidence for consult (not a dump)
    evidence = {}
    for rel, needles in (
        ("site/apex-bridge.css", ("hal-10624", "apex-stage--hal-sub", "hal-substrip")),
        ("site/apex-core.js", ("isHalSub", "askHalOnSubpage", "hal-10628", "?sub=")),
        ("apex_backend.py", ("hal-medium", "trust pair", "hal-ask")),
    ):
        path = NR2 / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        evidence[rel] = {
            n: (text.find(n) >= 0) for n in needles
        }
    live["codeEvidence"] = evidence
    return json.dumps(live, indent=2, default=str)[:36000]


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        blocker = DOCS / f"MOONSHOT_HAL_PAGE_RECOMMENDATIONS_BLOCKED_{DATE}.md"
        blocker.write_text(
            "# Moonshot AI — HAL page recommendations (BLOCKED)\n\n"
            f"**Date:** {DATE}\n"
            "**Status:** no API key in this environment\n\n"
            "## Operator request (verbatim)\n\n"
            f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
            "## Blocker\n"
            "Neither `MOONSHOT_API_KEY` nor `OPENROUTER_API_KEY` / `KIMI_K2_API_KEY` "
            "is set in this cloud agent.\n\n"
            "## Unblock\n"
            "1. Set one of those keys in the Cursor Cloud Agent secrets / shell env, or\n"
            "2. Run locally on the Windows workstation where the key already lives:\n\n"
            "```bat\n"
            "cd /d C:\\NewRidgeFamilyFinancial\n"
            "python scripts\\run_moonshot_hal_page_recommendations_consult.py\n"
            "```\n\n"
            "Then re-ask the cloud agent to continue / report.\n",
            encoding="utf-8",
        )
        print("No API key", file=sys.stderr)
        print("Wrote", blocker)
        return 1

    if (api_key or "").startswith("sk-nv") or "moonshot.ai" in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    else:
        model = str(
            os.getenv("MOONSHOT_MODEL")
            or os.getenv("KIMI_K2_MODEL")
            or "moonshotai/kimi-k2.5"
        ).strip()
    print(f"Using {key_name} @ {base_url} model={model}", flush=True)

    live = live_snapshot()
    print("Live snapshot chars:", len(live), flush=True)

    excerpts = []
    for name, lim in (
        ("MOONSHOT_WHATS_NEXT_AFTER_HAL10618_2026-07-14.md", 2500),
        ("MOONSHOT_HAL_CHAT_STILL_REFRESHES_CONSULT_2026-07-14.md", 2000),
        ("MOONSHOT_WHATS_NEXT_AFTER_HAL10608_2026-07-13.md", 1200),
    ):
        path = DOCS / name
        if path.is_file():
            excerpts.append(
                f"### {name}\n{path.read_text(encoding='utf-8', errors='replace')[:lim]}"
            )

    user = (
        f"OPERATOR REQUEST (verbatim):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        f"LIVE SNAPSHOT (hal-10628 + History/Logs redesign):\n```json\n{live}\n```\n\n"
        + ("PRIOR CONSULT EXCERPTS:\n" + "\n\n".join(excerpts) if excerpts else "")
        + "\n\nReturn the markdown report only. CONSULT ONLY."
    )

    body = {
        "model": model,
        "temperature": 1 if "moonshot" in (base_url or "").lower() else 0.3,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "max_tokens": 9000,
    }
    url = base_url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url = url + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if "openrouter" in url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 HAL Page Recommendations Consult"

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=700) as resp:
            raw = json.loads(resp.read().decode("utf-8", "replace"))
        text = extract_message_content(raw) or ""
        status = "ok"
    except Exception as exc:  # noqa: BLE001
        print(f"Moonshot call failed: {exc}", file=sys.stderr)
        raw = {"error": str(exc)}
        text = f"Moonshot call failed: {exc}"
        status = "error"

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = OUT / f"moonshot_hal_page_recommendations_{stamp}.json"
    md_path = DOCS / f"MOONSHOT_HAL_PAGE_RECOMMENDATIONS_CONSULT_{DATE}.md"
    raw_path.write_text(json.dumps(raw, indent=2)[:500000], encoding="utf-8")

    header = (
        f"# Moonshot AI — HAL page recommendations (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Endpoint:** {url}\n"
        f"**Status:** {status}\n"
        f"**Build:** hal-10628\n"
        f"**Script:** `scripts/run_moonshot_hal_page_recommendations_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    md_path.write_text(header + text.strip() + "\n", encoding="utf-8")
    print("Wrote", md_path)
    print("Raw", raw_path)
    print(text[:2000])
    return 0 if status == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
