"""Moonshot AI — praise Optical Interferometer; ask what he would ADD next.

Operator: tell him nice can he add to it
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

OPERATOR_REQUEST_VERBATIM = "tell him nice can he add to it"

PRIOR = DOCS / f"MOONSHOT_WALLSTREET_FINANCIAL_IMAGINATIVE_{DATE}.md"
MOCKUP = SITE / "nr2-optical-interferometer-mockup.html"

SYSTEM = """You are Moonshot AI — author of the NR2 **Optical Interferometer** concept
(schema **nr2-12000-interference**). Operator viewed the live mockup and said:

> tell him nice can he add to it

Tone: they LIKE it. Do not restart from Bloomberg/mosaic. EXTEND this metaphor.

YOUR JOB — propose concrete ADDITIONS that deepen the optical-bench idea:
- New instruments / emitters / overlays that still feel like physics-lab finance
- What HAL / SoftDent / QuickBooks gain without collapsing back into a side rail mosaic
- Optional schema micro-bump only if needed (nr2-12001-* ok if justified)
- Keep zero-scroll sealed viewport spirit; empty ≠ $0; never invent SoftDent dollars;
  stale softdent.ar stays a broken beam
- No apex-* packs; no purple neon cyberpunk

CONSULT / DESIGN ONLY — do not claim applied.

OUTPUT (strict markdown):
# Verdict (one sentence — the add-on package name)
## 0. Operator Intent (verbatim)
## 1. Acknowledgement (what worked in Interferometer v1)
## 2. Additions (ranked; name each; WHY it belongs on the optical bench)
## 3. Spec for THE best 3–5 additions (layout math, visual/behavior, data honesty)
## 4. Updated ASCII / mermaid sketch (v1 + additions)
## 5. Schema (keep nr2-12000-interference OR bump — justify)
## 6. Mockup change list (exact elements to add to nr2-optical-interferometer-mockup.html)
## 7. Implementation phases
## 8. Acceptance criteria
## 9. Executive Summary (5–7 bullets)
## 10. Approval checklist
DO NOT APPLY CODE. Stay imaginative within THIS concept.
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
    print(f"Using {key_name} @ {base_url} model={model}")

    prior = ""
    if PRIOR.is_file():
        prior = PRIOR.read_text(encoding="utf-8", errors="replace")[:10000]

    mock_snip = ""
    if MOCKUP.is_file():
        mock_snip = MOCKUP.read_text(encoding="utf-8", errors="replace")[:4500]

    live = {
        "operatorAsk": OPERATOR_REQUEST_VERBATIM,
        "mockupUrl": f"{BASE}/nr2-optical-interferometer-mockup.html",
        "mockupExists": MOCKUP.is_file(),
        "schema": "nr2-12000-interference",
    }

    user = (
        f"OPERATOR REQUEST (verbatim):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        f"LIVE:\n```json\n{json.dumps(live, indent=2)}\n```\n\n"
        f"PRIOR CONSULT (v1 concept):\n{prior}\n\n"
        f"CURRENT MOCKUP HTML (excerpt):\n```html\n{mock_snip}\n```\n\n"
        "Say nice back briefly via the acknowledgement section, then ADD to it. "
        "Return markdown REPORT only. CONSULT ONLY."
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
            os.getenv("OPENROUTER_X_TITLE") or "NR2 Moonshot Interferometer Add-ons"
        )

    req = urllib.request.Request(
        base_url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=700, context=CTX) as resp:
            raw = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001
        print(f"Moonshot call failed: {exc}", file=sys.stderr)
        return 2

    text = extract_message_content(raw) or ""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = OUT / f"moonshot_interferometer_addons_{stamp}.json"
    md_path = DOCS / f"MOONSHOT_OPTICAL_INTERFEROMETER_ADDONS_{DATE}.md"
    raw_path.write_text(json.dumps(raw, indent=2)[:500000], encoding="utf-8")

    header = (
        f"# Moonshot AI — Optical Interferometer Additions (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Schema base:** nr2-12000-interference\n"
        f"**Script:** `scripts/run_moonshot_interferometer_addons_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    md_path.write_text(header + text.strip() + "\n", encoding="utf-8")
    print("Wrote", md_path)
    print("Raw", raw_path)
    print(text[:2800])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
