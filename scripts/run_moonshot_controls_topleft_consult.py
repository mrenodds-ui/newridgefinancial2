"""Moonshot AI — move Master Pulse / Period / Phase Comp controls top-left under NR2-12009.

Operator: Master Pulse SYNC SoftDent+QB+HAL · sync Period Wheel 306090120
REFRESH-PERIOD SoftDent · refresh-period Phase Comp RECONCILE now tell moonshot
ai to place this widget in the top left under the n2r-12009
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
OUT.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

CTX = ssl._create_unverified_context()
BASE = os.getenv("NR2_BROWSER", "https://127.0.0.1:8765").rstrip("/")

OPERATOR_REQUEST_VERBATIM = (
    "Master Pulse SYNC SoftDent+QB+HAL · sync Period Wheel 306090120 "
    "REFRESH-PERIOD SoftDent · refresh-period Phase Comp RECONCILE now tell "
    "moonshot ai to place this widget in the top left under the n2r-12009"
)

SYSTEM = """You are Moonshot AI — designer of NR2 Optical Interferometer
landing bench (nr2-12009 / nr2-12011-landing).

Operator (verbatim):
> Master Pulse SYNC SoftDent+QB+HAL · sync Period Wheel 306090120
> REFRESH-PERIOD SoftDent · refresh-period Phase Comp RECONCILE now tell
> moonshot ai to place this widget in the top left under the n2r-12009

Note: "n2r-12009" = **NR2-12009** mode-strip label on the main landing mockup.

DIRECTIVES (mandatory):
1) Relocate the **control strip widget** (Master Pulse / SYNC + Period Wheel
   30/60/90/120 + REFRESH-PERIOD + Phase Comp / RECONCILE) from bottom-center
   to **top-left, directly under the NR2-12009 header/mode-strip**.
2) Keep SoftDent left-bottom white pulse, QuickBooks right, Tax Prism upper-right,
   HAL center. No overlaps. SoftDent must not collide with the relocated controls.
3) Widgets remain bindable (sync/trigger, refresh-period, reconciliation).
4) empty ≠ $0; no SoftDent write-back.
5) CONSULT / DESIGN ONLY. Bump schema if needed (e.g. nr2-12012-controls-tl).

OUTPUT (strict markdown):
# Verdict (schema)
## 0. Operator Intent (verbatim)
## 1. Control strip → top-left under NR2-12009 (coords / layout)
## 2. SoftDent emitter collision avoidance
## 3. Bind map unchanged
## 4. Mockup change list
## 5. Schema bump justification
## 6. Executive Summary (4 bullets)
## 7. Approval checklist
DO NOT APPLY CODE.
"""


def _load_dotenv() -> None:
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
        if val and len(val) >= 20:
            key_name, api_key = name, val
            break
    if not api_key:
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


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No API key", file=sys.stderr)
        return 1
    if (api_key or "").startswith("sk-nv") or key_name == "MOONSHOT_API_KEY":
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    elif "moonshot.ai" in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    else:
        model = str(
            os.getenv("MOONSHOT_MODEL")
            or os.getenv("KIMI_K2_MODEL")
            or "moonshotai/kimi-k2.5"
        ).strip()
    print(f"Using {key_name} @ {base_url} model={model}", flush=True)

    live = {
        "operatorAsk": OPERATOR_REQUEST_VERBATIM,
        "mockup": f"{BASE}/nr2-optical-qb-right-sd-left-mockup.html",
        "widget": "Master Pulse + Period Wheel + Phase Comp control strip",
        "place": "top-left under NR2-12009 mode strip",
    }

    user = (
        f"OPERATOR REQUEST (verbatim):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        f"LIVE:\n```json\n{json.dumps(live, indent=2)}\n```\n\n"
        "Move that control strip top-left under NR2-12009. Return markdown REPORT only."
    )

    body = {
        "model": model,
        "temperature": 1,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if "openrouter.ai" in base_url:
        headers["HTTP-Referer"] = (
            os.getenv("OPENROUTER_HTTP_REFERER") or "https://127.0.0.1:8765/"
        )
        headers["X-Title"] = (
            os.getenv("OPENROUTER_X_TITLE") or "NR2 Moonshot Controls Top-Left"
        )

    req = urllib.request.Request(
        base_url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300, context=CTX) as resp:
            raw = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001
        print(f"Moonshot call failed: {exc}", file=sys.stderr)
        return 2

    text = extract_message_content(raw) or ""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = OUT / f"moonshot_controls_topleft_{stamp}.json"
    md_path = DOCS / f"MOONSHOT_OPTICAL_CONTROLS_TOPLEFT_{DATE}.md"
    raw_path.write_text(json.dumps(raw, indent=2)[:500000], encoding="utf-8")

    header = (
        f"# Moonshot AI — Controls Top-Left under NR2-12009 (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Script:** `scripts/run_moonshot_controls_topleft_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    md_path.write_text(header + text.strip() + "\n", encoding="utf-8")
    print("Wrote", md_path, flush=True)
    print("Raw", raw_path, flush=True)
    sys.stdout.buffer.write((text[:2000] + "\n").encode("utf-8", "replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
