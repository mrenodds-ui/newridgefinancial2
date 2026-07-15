"""Moonshot AI — QB back to right; lower widget flush left.

Operator: tell moonshot to place quickbooks widget back to the other side and
move the lower widget all the way over to the left
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
    "tell moonshot to place quickbooks widget back to the other side and "
    "move the lower widget all the way over to the left"
)

SYSTEM = """You are Moonshot AI — designer of NR2 Optical Interferometer
(schema nr2-12008-interference: HAL center; SoftDent upper-left; QuickBooks
left-bottom with white pulse; Tax Prism upper-right; Claims/Narrative gone).

Operator (verbatim):
> tell moonshot to place quickbooks widget back to the other side and move the
> lower widget all the way over to the left

DIRECTIVES (mandatory):
1) **QuickBooks** returns to the **RIGHT / other side** (bottom-right emitter
   like before the left-white-pulse move). Restore an appropriate rolling beam
   into HAL from the right (QB gold/amber beam OK).
2) **Lower widget** = SoftDent (the remaining lower/left financial emitter once
   QB vacates left-bottom). Move SoftDent **all the way to the left** (flush
   left edge / left-bottom zone previously occupied by the white beam origin).
3) SoftDent should own the **left-bottom white pulsing beam** into HAL (light
   originates from SoftDent housing). If SoftDent AR is stale, beam may still
   pulse but carry honesty (broken secondary / dim filament) — empty ≠ $0; no
   SoftDent write-back.
4) Tax Prism stays an emitter (prefer upper-right). HAL stays center.
5) No Claims / Narrative / ERA / Quarantine. No overlaps.

CONSULT / DESIGN ONLY. Bump schema if needed.

OUTPUT (strict markdown):
# Verdict (revision name + schema)
## 0. Operator Intent (verbatim)
## 1. QuickBooks → right side + beam
## 2. SoftDent (lower) → flush left + white pulse origin
## 3. Layout coordinates
## 4. Bind map
## 5. Mockup change list
## 6. Schema bump justification
## 7. Executive Summary (5 bullets)
## 8. Approval checklist
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
        "mockup": f"{BASE}/nr2-optical-qb-left-pulse-mockup.html",
        "schemaConsult": "nr2-12008-interference",
        "must": {
            "quickbooks": "back to RIGHT side",
            "softDentLower": "flush LEFT (left-bottom) + white pulse origin",
        },
    }

    user = (
        f"OPERATOR REQUEST (verbatim):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        f"LIVE:\n```json\n{json.dumps(live, indent=2)}\n```\n\n"
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
            os.getenv("OPENROUTER_X_TITLE") or "NR2 Moonshot QB Right SoftDent Left"
        )

    req = urllib.request.Request(
        base_url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=420, context=CTX) as resp:
            raw = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001
        print(f"Moonshot call failed: {exc}", file=sys.stderr)
        return 2

    text = extract_message_content(raw) or ""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = OUT / f"moonshot_interferometer_qb_right_sd_left_{stamp}.json"
    md_path = DOCS / f"MOONSHOT_OPTICAL_INTERFEROMETER_QB_RIGHT_SD_LEFT_{DATE}.md"
    raw_path.write_text(json.dumps(raw, indent=2)[:500000], encoding="utf-8")

    header = (
        f"# Moonshot AI — QB Right · SoftDent Flush Left (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Script:** `scripts/run_moonshot_interferometer_qb_right_sd_left_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    md_path.write_text(header + text.strip() + "\n", encoding="utf-8")
    print("Wrote", md_path, flush=True)
    print("Raw", raw_path, flush=True)
    sys.stdout.buffer.write((text[:2200] + "\n").encode("utf-8", "replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
