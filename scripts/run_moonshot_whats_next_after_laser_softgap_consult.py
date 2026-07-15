"""Moonshot AI — What's next after laser softGap unify + BlueNote sender fallback (CONSULT ONLY).

Operator: next
Just shipped: 639d601 laser softGap unify; 7026b72 BlueNote sender fallback.
Prior consult (c7b0729) recommended period-close OPS loop — NOT yet operator-approved/applied.
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

JUST SHIPPED on main (through 7026b72 → nr2/main), build stamp nr2-12024-laser-softgap-unify:

- 639d601 — Unify critical softGaps past TTL into blocking lasers + live Pages Hub stamps
- 7026b72 — BlueNote announce with sender fallback when message-box text unavailable
- c7b0729 — Documented prior next package (period-close OPS) — CONSULT ONLY, NOT APPLIED
- b3e7ed2 — short BlueNote cue openers
- cec10bc — SoftDent refresh-period fail-fast
- money honesty / recon UNAVAILABLE / board navigate / SoftDent export consent → still shipped earlier today

PRIOR CONSULT (still PENDING operator approve — do NOT pretend it shipped):
MOONSHOT_WHATS_NEXT_AFTER_BLUENOTE_VOICE_2026-07-15.md
Verdict: Import-readiness / period close daily OPS loop (pulls → beams → HAL cite)

EXISTING related code (do not invent greenfield if reuse is better):
- NewRidgeFinancial2/daily_closeout.py + /api/... daily_closeout already exist (checklist layer)
- SoftDent GUI export + import refresh consent already wired (f30465b)
- Money beams / money honesty live
- SoftDent write-back FORBIDDEN; Excel/Print Preview only; empty ≠ $0

PATH HYGIENE:
- ONLY C:\\Users\\mreno\\newridgefamilyfinancial
- NEVER C:\\NewRidgeFamilyFinancial
- Gateway ONLY NewRidgeFinancial2/nr2_hal_gateway.py
- NEVER invent NewRidgeFinancial2/gateway/routes/...

YOUR JOB:
Pick THE single best NEXT package NOW after softGap laser unify + BlueNote sender fallback.
You MAY reaffirm period-close OPS if still THE best, OR pick a new next if laser/hub/BlueNote
work opens a sharper immediate package. Prefer one clear next.
Prefer OPS if data truth blocks UX; CODE when wiring/honesty is the blocker.
Do NOT redo: money honesty, short cues, recon UNAVAILABLE, board navigate, refresh timeout,
softGap laser unify (639d601), BlueNote sender fallback (7026b72).

CANDIDATES (pick ONE as THE next):
1) Reaffirm + scope period-close daily OPS loop (reuse daily_closeout.py where real; no invent)
2) Bind next optical SoftDent/QB bench subpage for daily money loop (real beams on page)
3) SoftDent GUI export ops hardening (aging/register/collections Excel save reliability)
4) HAL consent UX polish on optical command center
5) BlueNote watcher reliability (supervisor / encrypted body desk proof)
6) Laser/softGap optical desk proof — prove blocking lasers + hub LIVE/STALE on live 8765
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

    return {
        "repoRoot": str(REPO),
        "invalidRootExists": Path(r"C:\NewRidgeFamilyFinancial").exists(),
        "build": build,
        "siteBuild": site_build,
        "commitHint": "7026b72 BlueNote sender fallback · 639d601 laser softGap · c7b0729 period-close consult pending",
        "dailyCloseoutExists": (NR2 / "daily_closeout.py").is_file(),
        "periodCloseOpsExists": (NR2 / "nr2_period_close_ops.py").is_file(),
        "live": {
            "appInfo": get_json("/api/app-info", 25),
            "importReadiness": get_json("/api/import-readiness", 40),
            "softdentStatus": get_json("/api/hal/tools/softdent-status", 40),
            "qbSummary": get_json("/api/hal/tools/qb-summary", 40),
            "moneyBeams": get_json("/api/hal/tools/money-beams", 40),
            "actionsPending": get_json("/api/hal/actions/pending", 20),
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
        ("MOONSHOT_WHATS_NEXT_AFTER_BLUENOTE_VOICE_2026-07-15.md", 4500),
        ("MOONSHOT_WHATS_NEXT_AFTER_HAL_BRAINS_LIVE_APPLIED_2026-07-15.md", 2500),
        ("MOONSHOT_TOTAL_FUNCTIONABILITY_2026-07-15.md", 2000),
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
        headers["X-Title"] = "NR2 Whats Next After Laser SoftGap"

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
    (OUT / f"moonshot_whats_next_after_laser_softgap_{stamp}.json").write_text(
        json.dumps(raw, indent=2)[:400000], encoding="utf-8"
    )
    (OUT / f"moonshot_whats_next_after_laser_softgap_audit_{stamp}.json").write_text(
        json.dumps(audit, indent=2, default=str)[:200000], encoding="utf-8"
    )

    header = (
        f"# Moonshot AI — What's Next After Laser SoftGap Unify (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Status:** {status}\n"
        f"**Repo root:** `{REPO}`\n"
        f"**Prior:** `7026b72` sender fallback · `639d601` laser softGap · period-close consult pending\n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_laser_softgap_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    md = header + (text.strip() or "_(empty)_") + "\n"
    md_path = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_LASER_SOFTGAP_{DATE}.md"
    md_path.write_text(md, encoding="utf-8")
    (OUT / md_path.name).write_text(md, encoding="utf-8")
    print("Wrote", md_path)
    print("Status", status, "chars", len(text))
    return 0 if status == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
