"""Moonshot AI — What to do with the LOOK of the NR2 program (CONSULT ONLY).

Operator: ask moonshot what to do with the look of the program and report
Context: OPS packages just shipped (desk smoke, morning SoftDent bundle, beamHash,
Force Close). Now evaluate visual/UX direction for optical program pages.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\mreno\newridgefamilyfinancial")
if not REPO.is_dir():
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
    "ask moonshot what to do with the look of the program and report"
)

SYSTEM = """You are Moonshot AI — principal product designer + architect for NewRidgeFinancial2 (NR2).
CONSULT ONLY — DO NOT APPLY CODE.

Operator asked: what to do with the LOOK of the program (visual/UX), and wants a clear report.

CONTEXT — OPS is ahead of chrome:
Just shipped on main: desk smoke (nr2-12038), SoftDent morning aging+register+collections,
beamHash desk proof, Force Close, OPS alerts, money-beam honesty. Shadow period-close is live.
The optical program (interferometer theme) is the desk face of that OPS.

PATH HYGIENE:
- ONLY C:\\Users\\mreno\\newridgefamilyfinancial
- Optical under NewRidgeFinancial2/site/nr2-optical-* and nr2-optical-theme.css
- SoftDent write-back FORBIDDEN; empty ≠ $0 must stay readable in chrome
- Prefer REAL file paths; no invented UI frameworks

DESIGN HARD RULES (respect when recommending):
- One composition first viewport (not a dashboard collage) unless page IS the hub
- Brand/product signal strong; avoid generic purple-on-white / cream-serif / broadsheet clichés
- Cards only when they hold interaction; hero should not be card soup
- LIVE/STALE/CLOSE honesty must remain visible — never pretty-up away money truth
- SoftDent vs QB color language (sd/qb/hal tokens) already exists — evolve, don't discard

YOUR JOB:
1) Diagnose current optical look (strengths + visual debt) from LIVE AUDIT + CSS/HTML excerpts.
2) Pick THE single best NEXT visual package (not a wishlist of 10).
3) Say what NOT to redesign now (OPS honesty chrome that must stay).

CANDIDATES (pick ONE as THE next look package):
1) Optical theme lock pass — typography, spacing, banner hierarchy, reduce card clutter on Hub
2) Main interferometer landing polish — first viewport composition + money face hierarchy
3) Unify Hub / OM / HAL / SoftDent / QB subpages to one visual rhythm (nav + banner + honesty strip)
4) Desk smoke / Force Close / VERIFY BEAM control chrome — make OPS actions feel intentional, not bolted-on
5) Reduce “sci-fi mono dump” density — more scannable staff English without losing laser honesty
6) Something else justified from LIVE AUDIT — real paths only

OUTPUT (strict markdown):
# Verdict (one sentence — THE next look package)
## 0. Operator Intent (verbatim)
## 1. Current look diagnosis (what works / what's noisy)
## 2. Recommended NEXT look package (name, why now, effort, REAL files, validation gate)
## 3. Why this beats the other candidates now
## 4. Runner-ups (2–3)
## 5. What NOT to redo / must keep for money honesty
## 6. Acceptance criteria (visual + honesty)
## 7. Executive Summary (5 bullets)
## 8. Approval Checklist
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


def get_json(path: str, timeout: int = 40):
    try:
        with urllib.request.urlopen(BASE + path, context=CTX, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        return {"error": type(e).__name__, "msg": str(e)[:240]}


def _excerpt(path: Path, lim: int = 3500) -> str:
    if not path.is_file():
        return f"(missing {path.name})"
    return path.read_text(encoding="utf-8", errors="replace")[:lim]


def live_audit() -> dict:
    build = {}
    try:
        build = json.loads((NR2 / "nr2-build.json").read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        build = {"error": str(exc)}

    optical_pages = sorted(p.name for p in SITE.glob("nr2-optical*.html"))
    return {
        "repoRoot": str(REPO),
        "build": build,
        "commitHint": "eee9168 desk smoke · a753f31 SoftDent morning bundle · c5de424 beamHash",
        "opticalPages": optical_pages,
        "themeCssBytes": (SITE / "nr2-optical-theme.css").stat().st_size
        if (SITE / "nr2-optical-theme.css").is_file()
        else None,
        "hubHasDeskSmoke": "btn-desk-smoke" in _excerpt(SITE / "nr2-optical-pages-hub.html", 8000),
        "hubHasForceClose": "btn-force-close" in _excerpt(SITE / "nr2-optical-pages-hub.html", 8000),
        "hubHasVerifyBeam": "btn-verify-beam" in _excerpt(SITE / "nr2-optical-pages-hub.html", 8000),
        "live": {
            "appInfo": get_json("/api/app-info", 25),
            "importReadiness": get_json("/api/import-readiness", 40),
            "moneyBeams": get_json("/api/hal/tools/money-beams", 40),
            "deskSmokeLast": get_json("/api/health/desk-smoke?run=0", 20),
        },
        "excerpts": {
            "themeCss": _excerpt(SITE / "nr2-optical-theme.css", 4000),
            "hubHtml": _excerpt(SITE / "nr2-optical-pages-hub.html", 4500),
            "landingHtmlHead": _excerpt(SITE / "nr2-optical-beam-touch-mockup.html", 3500),
            "omHtml": _excerpt(SITE / "nr2-optical-page-office-manager.html", 3000),
            "halHtml": _excerpt(SITE / "nr2-optical-page-hal.html", 2500),
        },
    }


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No API key", flush=True)
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

    audit = live_audit()
    prior = []
    for name, lim in (
        ("MOONSHOT_OPTICAL_INTERFEROMETER_PAGES_THEME_2026-07-15.md", 2500),
        ("MOONSHOT_OPTICAL_INTERFEROMETER_NO_DUMP_LAYOUT_2026-07-15.md", 2000),
        ("MOONSHOT_PROGRAM_AFTER_MORNING_BUNDLE_APPLIED_2026-07-16.md", 2000),
    ):
        path = DOCS / name
        if path.is_file():
            prior.append(f"### {name}\n{path.read_text(encoding='utf-8', errors='replace')[:lim]}")

    user = (
        f"OPERATOR REQUEST (verbatim): {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"LIVE AUDIT (look + OPS face):\n```json\n{json.dumps(audit, indent=2, default=str)[:32000]}\n```\n\n"
        + ("PRIOR LOOK DOCS:\n" + "\n\n".join(prior) if prior else "")
        + "\n\nReturn markdown only. CONSULT ONLY. Real paths only. One next look package."
    )

    body = {
        "model": model,
        "temperature": 1 if "moonshot" in (base_url or "").lower() else 0.3,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "max_tokens": 7000,
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
        headers["X-Title"] = "NR2 Program Look Consult"

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
        print(f"Moonshot call failed: {exc}", flush=True)
        raw = {"error": str(exc)}
        text = f"Moonshot call failed: {exc}"
        status = "error"

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (OUT / f"moonshot_program_look_{stamp}.json").write_text(
        json.dumps(raw, indent=2)[:400000], encoding="utf-8"
    )
    (OUT / f"moonshot_program_look_audit_{stamp}.json").write_text(
        json.dumps(audit, indent=2, default=str)[:250000], encoding="utf-8"
    )

    header = (
        f"# Moonshot AI — What To Do With The LOOK Of The Program (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Status:** {status}\n"
        f"**Repo root:** `{REPO}`\n"
        f"**Prior OPS:** `eee9168` desk smoke · `a753f31` SoftDent morning bundle\n"
        f"**Script:** `scripts/run_moonshot_program_look_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    md = header + (text.strip() or "_(empty)_") + "\n"
    md_path = DOCS / f"MOONSHOT_PROGRAM_LOOK_{DATE}.md"
    md_path.write_text(md, encoding="utf-8")
    (OUT / md_path.name).write_text(md, encoding="utf-8")
    print("Wrote", md_path)
    print("Status", status, "chars", len(text))
    return 0 if status == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
