"""Moonshot AI — review live optical mockups: improvements + will widgets work?

Operator: show the mock ups to moonshot ai and ask if anything can improve
and will all the widgets work
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
    "show the mock ups to moonshot ai and ask if anything can improve "
    "and will all the widgets work"
)

SYSTEM = """You are Moonshot AI — reviewer of the NR2 Optical Interferometer
mockups (landing schema nr2-12014-lower-ctrl-beam). CONSULT ONLY.

Operator (verbatim):
> show the mock ups to moonshot ai and ask if anything can improve and will
> all the widgets work

You are shown the CURRENT applied mockup state (landing + pages inventory +
prior bindability findings). Be honest about mock vs production wiring.

LANDING (nr2-12014-lower-ctrl-beam) — applied visual state:
- SoftDent lower-left (white pulse) → HAL
- QuickBooks lower-right (orange) → HAL
- Tax Prism upper-right (magenta) → HAL
- Controls upper-left (Master Pulse SYNC / Period Wheel / RECONCILE) teal CTRL beam → HAL
- HAL center SPECTRAL · RECON INCOHERENT
- Floating outside beam title labels REMOVED (SD WHITE PULSE / QB BEAM / TAX BEAM / CTRL BEAM gone)
- Beams are HTML rays snapped to apertures (CSP blocks inline scripts; logic in external JS)
- empty ≠ $0; no SoftDent write-back; Role OM / Front Desk RBAC shutters; SCRAM ornamental
- Film strip footer (claims stubs); red alignment lasers when import not ready
- Mock toasts only — landing still toast-bound, NOT live API wired in this HTML

PAGES HUB + subpages exist (nr2-12010-pages theme): SoftDent, QuickBooks, HAL (+chat),
Claims, Taxes, AR, Narratives, Office Manager, Content — optical theme CSS shared.

PRIOR BINDABILITY (nr2-12010, still relevant unless you revise):
BINDABLE intents: SoftDent AR read / refresh-period; QB sync/export; Tax planning;
HAL recon; Master SYNC; Period Wheel; import-readiness lasers.
NEEDS WORK: SCRAM (no halt API); Film deep ERA on subpage; SoftDent write-back = CUT.
HAL chat page mock-transmits toward POST /api/hal/evaluate-query.

DIRECTIVES:
1) Review the mockups for visual/UX improvements (keep optical interferometer theme;
   do not propose purple/cream/card clutter; no SoftDent write-back).
2) Answer clearly: WILL ALL THE WIDGETS WORK? — wireable vs mock-only vs needs API,
   table per landing widget + note on subpages.
3) Rank top 5 improvements (impact vs effort). Flag anything dishonest if shipped as-is.
4) Schema bump only if you recommend a coherent next stamp (e.g. nr2-12015-*).
5) CONSULT ONLY — DO NOT APPLY CODE.

OUTPUT (strict markdown):
# Verdict (schema)
## 0. Operator Intent (verbatim)
## 1. Mockup review — what works visually
## 2. Will all the widgets work? (bindability matrix)
## 3. Gaps / honesty risks if shipped as-is
## 4. Top improvements (ranked, max 5)
## 5. Executive Summary (4 bullets)
## 6. Approval checklist
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


def fetch(url: str, limit: int = 12000) -> str:
    try:
        with urllib.request.urlopen(url, timeout=20, context=CTX) as resp:
            return resp.read().decode("utf-8", "replace")[:limit]
    except Exception as exc:  # noqa: BLE001
        return f"[fetch failed: {exc}]"


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

    inv_path = OUT.parent / "moonshot_mockup_inventory.json"
    inventory = {}
    if inv_path.is_file():
        try:
            inventory = json.loads(inv_path.read_text(encoding="utf-8"))
        except Exception:
            inventory = {}

    landing_html = fetch(f"{BASE}/nr2-optical-beam-touch-mockup.html", 14000)
    hub_html = fetch(f"{BASE}/nr2-optical-pages-hub.html", 5000)
    hal_html = fetch(f"{BASE}/nr2-optical-page-hal.html", 6000)

    live = {
        "operatorAsk": OPERATOR_REQUEST_VERBATIM,
        "landingUrl": f"{BASE}/nr2-optical-beam-touch-mockup.html",
        "hubUrl": f"{BASE}/nr2-optical-pages-hub.html",
        "schemaLanding": "nr2-12014-lower-ctrl-beam",
        "inventory": inventory,
        "honesty": {
            "emptyNotZero": True,
            "noSoftDentWriteBack": True,
            "landingWiredToLiveApis": False,
            "landingIsMockToasts": True,
            "externalJsForCsp": "/nr2-optical-beam-touch.js",
            "outsideBeamTitlesRemoved": True,
        },
    }

    user = (
        f"OPERATOR REQUEST (verbatim):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        f"LIVE CONTEXT:\n```json\n{json.dumps(live, indent=2)[:8000]}\n```\n\n"
        f"LANDING HTML (truncated):\n```html\n{landing_html}\n```\n\n"
        f"PAGES HUB HTML (truncated):\n```html\n{hub_html}\n```\n\n"
        f"HAL PAGE HTML (truncated):\n```html\n{hal_html}\n```\n\n"
        "Review the mockups. Answer if anything can improve AND whether all "
        "widgets will work. Return markdown REPORT only."
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
            os.getenv("OPENROUTER_X_TITLE") or "NR2 Moonshot Mockup Review"
        )

    req = urllib.request.Request(
        base_url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=360, context=CTX) as resp:
            raw = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001
        print(f"Moonshot call failed: {exc}", file=sys.stderr)
        return 2

    text = extract_message_content(raw) or ""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = OUT / f"moonshot_mockup_improve_workability_{stamp}.json"
    md_path = DOCS / f"MOONSHOT_OPTICAL_MOCKUP_IMPROVE_WORKABILITY_{DATE}.md"
    raw_path.write_text(json.dumps(raw, indent=2)[:500000], encoding="utf-8")

    header = (
        f"# Moonshot AI — Mockup Review: Improve + Will Widgets Work "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Script:** `scripts/run_moonshot_mockup_improve_workability_consult.py`\n"
        f"**Landing:** `{BASE}/nr2-optical-beam-touch-mockup.html`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    md_path.write_text(header + text.strip() + "\n", encoding="utf-8")
    print("Wrote", md_path, flush=True)
    print("Raw", raw_path, flush=True)
    sys.stdout.buffer.write((text[:3500] + "\n").encode("utf-8", "replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
