"""Moonshot AI — larger readable interferometer; more suggestions; widgets must be real.

Operator: can he make it a little bigger for easier read and if he has any more suggestions
please give. remind him that all widgets must work with the final program
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

OPERATOR_REQUEST_VERBATIM = (
    "can he make it a little bigger for easier read and if he has any more suggestions "
    "please give. remind him that all widgets must work with the final program"
)

PROGRAM_REMINDER = """
FINAL PROGRAM = shipping NR2 (clean-slate nr2-11000-clean runtime + contracts), not decoration.
Every optic/widget MUST map 1:1 to a real backend/API/RBAC surface that can be implemented:
- SoftDent / QuickBooks / HAL / ERA / imports / quarantine / recon / narratives / taxes /
  claims / sync / refresh-period / board-actions / import-readiness / unified snapshot
Honesty: empty≠$0, stale softdent.ar breaks money reads, no SoftDent write-back,
HAL never invents dollars/write-offs.
No fake gauges/widgets that have no data path in the final app.
"""

SYSTEM = """You are Moonshot AI — designer of NR2 Optical Interferometer Full Spectrum
(nr2-12002-interference mockups).

Operator (verbatim):
> can he make it a little bigger for easier read and if he has any more suggestions
> please give. remind him that all widgets must work with the final program

DIRECTIVES:
1) **Bigger / easier to read** — enlarge type, hit targets, emitter panels, core labels,
   control strip. Prefer ~1440×900 or allow slight zoom without becoming scroll-spam.
   Keep professional optical metaphor; reduce 8–9px micro-type.
2) **More suggestions** — offer 3–7 NEW improvements (prioritized) beyond what exists.
3) **HARD: all widgets must work with the FINAL program** — forbid ornamental optics.
   Every proposed control must cite the real NR2 route/capability/dataset it binds to.
   If something cannot bind, CUT it or mark DEFER — do not leave fake UI.

CONSULT / DESIGN ONLY. Stay in interferometer family (do not revert to Bloomberg mosaic).
empty ≠ $0; no SoftDent write-back.

OUTPUT (strict markdown):
# Verdict (readable-scale revision name + schema stamp)
## 0. Operator Intent (verbatim)
## 1. Readability scale-up (exact size/type/spacing changes)
## 2. Final-program bind rule (what “must work” means; kill list if unbound)
## 3. Existing controls re-bound (table: optic → API/capability → acceptance)
## 4. Additional suggestions ranked (only if bindable)
## 5. Layout wireframe at larger readable scale
## 6. Schema (bump? justify)
## 7. Mockup change list
## 8. Implementation checklist for wire-up to final program
## 9. Executive Summary (6 bullets)
## 10. Approval checklist
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
    print(f"Using {key_name} @ {base_url} model={model}")

    priors = []
    for name in (
        f"MOONSHOT_OPTICAL_INTERFEROMETER_PROGRAM_ENHANCE_{DATE}.md",
        f"MOONSHOT_OPTICAL_INTERFEROMETER_ADDONS_{DATE}.md",
    ):
        p = DOCS / name
        if p.is_file():
            priors.append(f"### {name}\n{p.read_text(encoding='utf-8', errors='replace')[:5500]}")

    live = {
        "operatorAsk": OPERATOR_REQUEST_VERBATIM,
        "mockup": f"{BASE}/nr2-optical-fullspectrum-mockup.html",
        "schemaConsult": "nr2-12002-interference",
        "runtimeBuild": "nr2-11000-clean",
    }

    user = (
        f"OPERATOR REQUEST (verbatim):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        f"LIVE:\n```json\n{json.dumps(live, indent=2)}\n```\n\n"
        f"FINAL PROGRAM BIND REMINDER:\n{PROGRAM_REMINDER}\n\n"
        + ("PRIOR:\n" + "\n\n".join(priors) if priors else "")
        + "\n\nMake it more readable, suggest more ONLY if bindable to final program, "
        "and enforce working widgets. Return markdown REPORT only. CONSULT ONLY."
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
            os.getenv("OPENROUTER_X_TITLE") or "NR2 Moonshot Readable Bindable Revise"
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
    raw_path = OUT / f"moonshot_interferometer_readable_bindable_{stamp}.json"
    md_path = DOCS / f"MOONSHOT_OPTICAL_INTERFEROMETER_READABLE_BINDABLE_{DATE}.md"
    raw_path.write_text(json.dumps(raw, indent=2)[:500000], encoding="utf-8")

    header = (
        f"# Moonshot AI — Readable Scale + Bindable Widgets (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Script:** `scripts/run_moonshot_interferometer_readable_bindable_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    md_path.write_text(header + text.strip() + "\n", encoding="utf-8")
    print("Wrote", md_path)
    print("Raw", raw_path)
    print(text[:3200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
