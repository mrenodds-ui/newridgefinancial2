"""Moonshot AI — remove quarantine dump; no overlap; SoftDent+QB+HAL only.

Operator: tell him to remove the quarantine dump widget and try not to over lap
widgets. tell him all widgets must work with softdent, quickbooks and hall
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
    "tell him to remove the quarantine dump widget and try not to over lap "
    "widgets. tell him all widgets must work with softdent, quickbooks and hal"
)

SYSTEM = """You are Moonshot AI — designer of NR2 Optical Interferometer
(readable-scale nr2-12003-interference).

Operator (verbatim):
> tell him to remove the quarantine dump widget and try not to over lap widgets.
> tell him all widgets must work with softdent, quickbooks and hal

DIRECTIVES (mandatory):
1) **REMOVE Quarantine Dump** entirely from the optical bench. Do not relocate it
   to a drawer/film strip for this pass — cut it from this page.
2) **No overlapping widgets** — every emitter/instrument/control must have clear
   spatial separation (no stacked cards covering beams/labels). Provide exact
   coordinates or region rules so SoftDent / Claims / ERA / Core / Tax / QB /
   HAL / Narrative / Master controls never collide. Prefer larger gutters.
3) **Every remaining widget MUST work with SoftDent, QuickBooks, and/or HAL** —
   each optic cites which source system(s) it binds to AND the real API/capability.
   No orphan widgets, no tax-only-decoration that can't link to QB/HAL contracts,
   no SoftDent write-back.

Keep readable scale (16px base, 48px hits, ~1440×900). Consult/design only.
Bump schema if needed. empty ≠ $0; no SoftDent write-back.

OUTPUT (strict markdown):
# Verdict (revision name + schema)
## 0. Operator Intent (verbatim)
## 1. Cuts (Quarantine Dump + any other)
## 2. SoftDent · QuickBooks · HAL bind map (table: widget → systems → API)
## 3. No-overlap layout (regions / coordinates / gutters)
## 4. Mockup change list
## 5. Additional suggestions only if bindable to SD/QB/HAL
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

    priors = []
    for name in (
        f"MOONSHOT_OPTICAL_INTERFEROMETER_READABLE_BINDABLE_{DATE}.md",
        f"MOONSHOT_OPTICAL_INTERFEROMETER_PROGRAM_ENHANCE_{DATE}.md",
    ):
        p = DOCS / name
        if p.is_file():
            priors.append(f"### {name}\n{p.read_text(encoding='utf-8', errors='replace')[:4500]}")

    live = {
        "operatorAsk": OPERATOR_REQUEST_VERBATIM,
        "mockup": f"{BASE}/nr2-optical-readable-mockup.html",
        "schemaConsult": "nr2-12003-interference",
        "runtimeBuild": "nr2-11000-clean",
        "mustRemove": ["Quarantine Dump"],
        "mustSources": ["SoftDent", "QuickBooks", "HAL"],
        "layoutRule": "no overlapping widgets",
    }

    user = (
        f"OPERATOR REQUEST (verbatim):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        f"LIVE:\n```json\n{json.dumps(live, indent=2)}\n```\n\n"
        + ("PRIOR:\n" + "\n\n".join(priors) if priors else "")
        + "\n\nRemove Quarantine Dump. Deconflict layout. Every widget binds "
        "SoftDent and/or QuickBooks and/or HAL. Return markdown REPORT only."
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
            os.getenv("OPENROUTER_X_TITLE") or "NR2 Moonshot No Dump No Overlap"
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
    raw_path = OUT / f"moonshot_interferometer_no_dump_layout_{stamp}.json"
    md_path = DOCS / f"MOONSHOT_OPTICAL_INTERFEROMETER_NO_DUMP_LAYOUT_{DATE}.md"
    raw_path.write_text(json.dumps(raw, indent=2)[:500000], encoding="utf-8")

    header = (
        f"# Moonshot AI — No Quarantine Dump + No Overlap + SD/QB/HAL (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Script:** `scripts/run_moonshot_interferometer_no_dump_layout_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    md_path.write_text(header + text.strip() + "\n", encoding="utf-8")
    print("Wrote", md_path, flush=True)
    print("Raw", raw_path, flush=True)
    sys.stdout.buffer.write((text[:2800] + "\n").encode("utf-8", "replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
