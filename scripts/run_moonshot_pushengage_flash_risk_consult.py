"""Moonshot AI — does PushEngage live-chat article inject Flash into NR2 pages?

Operator: ask moonshot ai if this website has anything that would put flash into
my page - https://www.pushengage.com/best-free-live-chat-widgets-wordpress/
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

OPERATOR_REQUEST_VERBATIM = (
    "ask moonshot ai if this website has anything that would put flash into my "
    "page - https://www.pushengage.com/best-free-live-chat-widgets-wordpress/"
)

# Article summary fetched 2026-07-15 (no .swf / Adobe Flash mentioned in body).
ARTICLE_SUMMARY = """
URL: https://www.pushengage.com/best-free-live-chat-widgets-wordpress/
Title: 7 Best Free Live Chat Widgets for WordPress in 2026
Type: Marketing / affiliate roundup blog post by PushEngage.

Products promoted (WordPress live-chat or contact widgets):
1. PushEngage Chat Widget ($49/yr) — inbox-free; routes to email/SMS/WhatsApp/Slack/Telegram
2. Tawk.to (free) — classic embeddable live chat + agent dashboard
3. Tidio (free + paid) — live chat + AI chatbot; WooCommerce
4. HubSpot Free Live Chat — CRM-bundled chat widget
5. Crisp (free + paid) — lightweight live chat
6. Chatty / Chaty — floating multichannel contact button (WhatsApp etc.), not full on-site chat
7. LiveChat (trial / paid) — premium live chat

Installation model described: WordPress plugin or JS embed script; floating chat
bubble / inbox redirect. No mention of Adobe Flash, .swf, ActiveX, or Shockwave.
PushEngage also markets push notifications / WhatsApp / multichannel messaging CTAs
on the same page.

NR2 context (important):
- Our pages use HAL live-widget bridge with optional visual "flash" rings
  (flashElement / data-hal-flash / eventContract flash) — currently disabled in
  hal-live-widget-bridge.js to avoid blue/gold rings on refresh.
- Operator may mean Adobe Flash OR our HAL flash visual OR flashy third-party overlays.
"""

SYSTEM = """You are Moonshot AI — security/integration reviewer for NewRidgeFinancial2 (NR2).

Operator (verbatim):
> ask moonshot ai if this website has anything that would put flash into my page -
> https://www.pushengage.com/best-free-live-chat-widgets-wordpress/

Answer in plain operator language. Be decisive.

Interpret "flash" in THREE senses and check each:
A) Adobe Flash / Shockwave (.swf, object/embed Flash Player) — EOL since 2020
B) NR2 HAL widget "flash" (visual gold/blue flash rings via flashElement / data-hal-flash)
C) Flashy third-party overlays (floating chat bubbles, push permission prompts, popups)
   that would visually invade an NR2 SoftDent/optical/financial page if you pasted
   their embed / WordPress plugin into our site

RULES:
- The article itself is a blog page. Visiting/reading it in a browser does NOT put
  Flash into OUR NR2 page. Only INSTALLING/EMBEDDING a recommended widget would.
- Use the ARTICLE_SUMMARY provided (already fetched). Do not claim you browsed live
  unless inferring from summary.
- If no Adobe Flash: say so clearly.
- If embedding widgets: state what THEY would inject (JS widget bubble, tracking,
  push prompts) and whether that equals NR2 HAL flash (it does not unless we wire it).
- Recommend: do not paste PushEngage/Tawk/Tidio/etc. scripts into NR2 pages unless
  operator explicitly wants visitor chat.

OUTPUT (strict markdown):
# Verdict
## 0. Operator Intent (verbatim)
## 1. Does reading that website put Flash into my NR2 page?
## 2. Adobe Flash / .swf risk (A)
## 3. NR2 HAL flash rings risk (B)
## 4. Flashy third-party chat overlays if I install a widget (C)
## 5. Per-product inject risk table (product → injects → Flash? → HAL flash?)
## 6. Recommendation for NR2 (keep / avoid)
## 7. Executive Summary (5 bullets)
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
        "url": "https://www.pushengage.com/best-free-live-chat-widgets-wordpress/",
        "nr2FlashMeaning": {
            "halBridge": "NewRidgeFinancial2/site/hal-live-widget-bridge.js",
            "flashElement": "disabled — avoids transient blue/gold rings",
            "eventFlash": "hal-pilot-widgets.js eventContract includes flash",
        },
        "question": "Would that website / its recommended widgets put Flash into my page?",
    }

    user = (
        f"OPERATOR REQUEST (verbatim):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        f"ARTICLE_SUMMARY:\n{ARTICLE_SUMMARY}\n\n"
        f"LIVE CONTEXT:\n```json\n{json.dumps(live, indent=2)}\n```\n\n"
        "Decide clearly: reading the page vs installing embeds. Cover Adobe Flash, "
        "NR2 HAL flash rings, and flashy chat overlays. Markdown REPORT only."
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
            os.getenv("OPENROUTER_X_TITLE") or "NR2 Moonshot PushEngage Flash Risk"
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
    raw_path = OUT / f"moonshot_pushengage_flash_risk_{stamp}.json"
    md_path = DOCS / f"MOONSHOT_PUSHENGAGE_FLASH_RISK_{DATE}.md"
    raw_path.write_text(json.dumps(raw, indent=2)[:500000], encoding="utf-8")

    header = (
        f"# Moonshot AI — PushEngage Live-Chat Flash Risk (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Script:** `scripts/run_moonshot_pushengage_flash_risk_consult.py`\n"
        f"**Source URL:** https://www.pushengage.com/best-free-live-chat-widgets-wordpress/\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    md_path.write_text(header + text.strip() + "\n", encoding="utf-8")
    print("Wrote", md_path, flush=True)
    print("Raw", raw_path, flush=True)
    sys.stdout.buffer.write((text[:4000] + "\n").encode("utf-8", "replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
