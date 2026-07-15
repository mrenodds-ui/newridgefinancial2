"""Moonshot AI — What's next after optical money-beam binding (CONSULT ONLY).

Operator: next
Just shipped: 2d195e5 optical SoftDent/QB benches bound to live money beams.
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
OUT.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

CTX = ssl._create_unverified_context()
BASE = os.getenv("NR2_BROWSER", "https://127.0.0.1:8765").rstrip("/")

OPERATOR_REQUEST_VERBATIM = "next"

SYSTEM = """You are Moonshot AI — principal architect for NewRidgeFinancial2 (NR2).
CONSULT ONLY — DO NOT APPLY CODE.

Operator said (verbatim): next

JUST SHIPPED on main (through 2d195e5 → nr2/main):

- 2d195e5 — Bind optical SoftDent/QB benches to live money beams (AR/SoftDent/QB headlines cite
  /api/hal/tools/money-beams + beamHash; lasers suppress dollars; empty ≠ $0)
- 29629c1 — LIVE chrome honesty on Tax/OM/Documents subpages
- 263b26b — SoftDent Excel export consent-free for HAL
- 8972b8d — Shadow period-close OPS loop + HAL cite
- fc804b6 — BlueNote-only announce (SideNotes retired)

PRIOR APPLIED runner-ups (still open):
1) SoftDent GUI Excel path hardening (aging/register/collections save reliability)
2) BlueNote alerts when period-close stalls / laser-blocks
3) HAL Force Close control on optical pages (laser-gated)

PATH HYGIENE:
- ONLY C:\\Users\\mreno\\newridgefamilyfinancial
- NEVER C:\\NewRidgeFamilyFinancial
- Gateway ONLY NewRidgeFinancial2/nr2_hal_gateway.py
- Optical pages live under NewRidgeFinancial2/site/nr2-optical-page-* (NOT templates/optical/)
- SoftDent write-back FORBIDDEN; Excel/Print Preview only; empty ≠ $0

YOUR JOB:
Pick THE single best NEXT package now that optical benches show the same beams HAL cites.
Prefer one clear next. Prefer OPS if data truth blocks UX; CODE when reliability/honesty is the blocker.
Do NOT redo: money-beam binding, period-close attest, SoftDent consent-free export, money honesty,
BlueNote chrome filter, recon UNAVAILABLE, board navigate, laser softGap unify, LIVE chrome honesty.

CANDIDATES (pick ONE as THE next):
1) SoftDent GUI export ops hardening (aging/register/collections Excel path reliability)
2) BlueNote alert when period-close stalls / laser-blocks
3) HAL Force Close optical control (OM / Pages Hub — laser-gated, JSONL attest)
4) Wire period-close morning scheduler SoftDent pull (pull_softdent=True on auto close)
5) Bind main interferometer beam-touch headlines to money-beams (same as subpages)
6) Desk proof smoke: optical AR/QB pages + HAL chat cite identical beamHash on live 8765
7) Something else justified from LIVE AUDIT — real paths only

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim)
## 1. Recommended NEXT (name, why now, effort, REAL files/ops, validation gate)
## 2. Why this beats the other candidates now
## 3. Runner-ups (2–3)
## 4. What NOT to redo
## 5. Acceptance criteria
## 6. Executive Summary (5 bullets)
## 7. Approval Checklist
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


def live_audit() -> dict:
    build = {}
    try:
        build = json.loads((NR2 / "nr2-build.json").read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        build = {"error": str(exc)}
    site_build = {}
    try:
        site_build = json.loads(
            (NR2 / "site" / "nr2-build.json").read_text(encoding="utf-8")
        )
    except Exception as exc:  # noqa: BLE001
        site_build = {"error": str(exc)}

    ops_dir = REPO / "app_data" / "nr2" / "ops"
    return {
        "repoRoot": str(REPO),
        "invalidRootExists": Path(r"C:\NewRidgeFamilyFinancial").exists(),
        "build": build,
        "siteBuild": site_build,
        "commitHint": "2d195e5 optical money-beam bind · 263b26b SoftDent export consent-free",
        "opticalPages": {
            "ar": (NR2 / "site" / "nr2-optical-page-ar.js").is_file(),
            "softdent": (NR2 / "site" / "nr2-optical-page-softdent.js").is_file(),
            "qb": (NR2 / "site" / "nr2-optical-page-quickbooks.js").is_file(),
            "wireHasBeams": "getMoneyBeams"
            in (NR2 / "site" / "nr2-optical-page-wire.js").read_text(
                encoding="utf-8", errors="replace"
            ),
            "beamTouchExists": (NR2 / "site" / "nr2-optical-beam-touch.js").is_file(),
        },
        "closeLogExists": (ops_dir / "daily_close_log.jsonl").is_file(),
        "live": {
            "appInfo": get_json("/api/app-info", 25),
            "importReadiness": get_json("/api/import-readiness", 40),
            "moneyBeams": get_json("/api/hal/tools/money-beams", 40),
            "periodCloseStatus": get_json("/api/hal/tools/period-close-status", 25),
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
    excerpts = []
    for name, lim in (
        ("MOONSHOT_WHATS_NEXT_AFTER_PERIOD_CLOSE_APPLIED_2026-07-15.md", 4000),
        ("MOONSHOT_WHATS_NEXT_AFTER_PERIOD_CLOSE_2026-07-15.md", 2500),
        ("MOONSHOT_WHATS_NEXT_AFTER_LASER_SOFTGAP_APPLIED_2026-07-15.md", 2000),
    ):
        path = DOCS / name
        if path.is_file():
            excerpts.append(
                f"### {name}\n{path.read_text(encoding='utf-8', errors='replace')[:lim]}"
            )

    user = (
        f"OPERATOR REQUEST (verbatim): {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"LIVE AUDIT:\n```json\n{json.dumps(audit, indent=2, default=str)[:28000]}\n```\n\n"
        + ("PRIOR DOCS:\n" + "\n\n".join(excerpts) if excerpts else "")
        + "\n\nReturn markdown only. CONSULT ONLY. Real paths only."
    )

    body = {
        "model": model,
        "temperature": 1 if "moonshot" in (base_url or "").lower() else 0.25,
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
        headers["X-Title"] = "NR2 Whats Next After Optical Beam Bind"

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
    (OUT / f"moonshot_whats_next_after_optical_beam_bind_{stamp}.json").write_text(
        json.dumps(raw, indent=2)[:400000], encoding="utf-8"
    )
    (OUT / f"moonshot_whats_next_after_optical_beam_bind_audit_{stamp}.json").write_text(
        json.dumps(audit, indent=2, default=str)[:200000], encoding="utf-8"
    )

    header = (
        f"# Moonshot AI — What's Next After Optical Money-Beam Binding (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Status:** {status}\n"
        f"**Repo root:** `{REPO}`\n"
        f"**Prior:** `2d195e5` optical SoftDent/QB money-beam bind\n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_optical_beam_bind_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    md = header + (text.strip() or "_(empty)_") + "\n"
    md_path = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_OPTICAL_BEAM_BIND_{DATE}.md"
    md_path.write_text(md, encoding="utf-8")
    (OUT / md_path.name).write_text(md, encoding="utf-8")
    print("Wrote", md_path)
    print("Status", status, "chars", len(text))
    return 0 if status == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
