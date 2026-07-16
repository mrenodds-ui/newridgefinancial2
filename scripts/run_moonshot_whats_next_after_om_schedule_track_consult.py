"""Moonshot AI — What's next after OM schedule track complete.

Operator: continue with all until done
Track closed: a4909f2 + MOONSHOT_OM_SCHEDULE_TRACK_COMPLETE_2026-07-16.md
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

OPERATOR_REQUEST_VERBATIM = "continue with all until done"

SYSTEM = """You are Moonshot AI — principal architect for NewRidgeFinancial2 (NR2).
CONSULT ONLY — DO NOT APPLY CODE.

Operator said (verbatim): continue with all until done

JUST CLOSED track on main (a4909f2 / 137bc1a / 3992284 / 17de5f9):
- OM Mon–Thu enrich: ADA, appt_time, click summary, NEXT hint, provider groups
- Sensei/ODBC appt_time preserve + backfill + desk smoke mon_thu_appt_time
- Trellis tomorrow insurance OM panel (PHI-safe)
- HAL this-patient bind + expired TTL rebind hint
- Classic Apex 2B skipped as optional

CONSTRAINTS:
- SoftDent READ-ONLY; empty ≠ $0; board PHI initials+hash
- Do NOT redo the closed OM schedule / Trellis huddle / this-patient track
- Prefer REAL Python + optical JS paths (no invented React)
- Operator wants an ORDERED backlog they can apply sequentially until done

YOUR JOB:
Pick THE single best NEXT package, then list 2–4 ordered backlog items after it.

CANDIDATES (pick ONE as #1):
1) PushEngage / flash-risk consult sitting untracked in repo (if LIVE AUDIT warrants)
2) Desk smoke GREEN rehearsal + Force Close / beam MATCH morning confidence script
3) SoftDent GUI morning-bundle / period-close shadow hardening
4) Optical Hub / wire-page honesty or money-beam UX polish
5) Something else justified from LIVE AUDIT — real paths only

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim)
## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
## 2. Ordered backlog AFTER #1 (2–4 items for continue-with-all)
## 3. Why this beats the other candidates now
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
    untracked_hint = {
        "pushEngageDoc": (DOCS / "MOONSHOT_PUSHENGAGE_FLASH_RISK_2026-07-15.md").is_file(),
        "pushEngageScript": (REPO / "scripts" / "run_moonshot_pushengage_flash_risk_consult.py").is_file(),
        "trackCompleteDoc": (DOCS / "MOONSHOT_OM_SCHEDULE_TRACK_COMPLETE_2026-07-16.md").is_file(),
    }
    smoke = get_json("/api/health/desk-smoke?run=0", 20)
    ar = get_json("/api/softdent/appointments-range?days=4", 40)
    tr = get_json("/api/trellis/tomorrow-insurance", 20)
    return {
        "repoRoot": str(REPO),
        "build": build,
        "commitHint": "a4909f2 OM schedule track complete",
        "untrackedHint": untracked_hint,
        "live": {
            "appInfo": get_json("/api/app-info", 20),
            "deskSmokeLast": {
                "ok": smoke.get("ok") if isinstance(smoke, dict) else None,
                "status": smoke.get("status") if isinstance(smoke, dict) else None,
                "deskProof": smoke.get("deskProof") if isinstance(smoke, dict) else None,
                "forceCloseAvailable": smoke.get("forceCloseAvailable") if isinstance(smoke, dict) else None,
                "patientAttestEligible": smoke.get("patientAttestEligible") if isinstance(smoke, dict) else None,
                "monThuApptTimeOk": smoke.get("monThuApptTimeOk") if isinstance(smoke, dict) else None,
                "thisPatientShortcutCovered": smoke.get("thisPatientShortcutCovered")
                if isinstance(smoke, dict)
                else None,
                "error": (smoke.get("error") or smoke.get("msg")) if isinstance(smoke, dict) else None,
            },
            "appointmentsRange": {
                "hasData": ar.get("hasData") if isinstance(ar, dict) else None,
                "apptTimeColumn": ar.get("apptTimeColumn") if isinstance(ar, dict) else None,
                "nextPatient": (ar.get("nextPatient") or {}).get("available")
                if isinstance(ar, dict) and isinstance(ar.get("nextPatient"), dict)
                else None,
                "error": (ar.get("error") or ar.get("msg")) if isinstance(ar, dict) else None,
            },
            "trellisTomorrow": {
                "ok": tr.get("ok") if isinstance(tr, dict) else None,
                "hasData": tr.get("hasData") if isinstance(tr, dict) else None,
                "targetDate": tr.get("targetDate") if isinstance(tr, dict) else None,
                "total": tr.get("total") if isinstance(tr, dict) else None,
                "error": (tr.get("error") or tr.get("msg")) if isinstance(tr, dict) else None,
            },
            "importReadiness": get_json("/api/import-readiness", 30),
        },
    }


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

    audit = live_audit()
    user = (
        f"OPERATOR REQUEST (verbatim):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        f"LIVE AUDIT:\n```json\n{json.dumps(audit, indent=2)[:120000]}\n```\n\n"
        "Pick THE next package + ordered backlog. Markdown REPORT only. CONSULT ONLY."
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
        headers["X-Title"] = os.getenv("OPENROUTER_X_TITLE") or "NR2 Whats Next After OM Track"

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
    raw_path = OUT / f"moonshot_whats_next_after_om_track_{stamp}.json"
    md_path = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_OM_SCHEDULE_TRACK_{DATE}.md"
    raw_path.write_text(json.dumps(raw, indent=2)[:500000], encoding="utf-8")
    header = (
        f"# Moonshot AI — What's Next After OM Schedule Track (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_om_schedule_track_consult.py`\n"
        f"**Shipped:** `a4909f2` track complete\n"
        f"**Apply:** Operator said continue with all until done — Cursor may apply ordered backlog.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    md_path.write_text(header + text.strip() + "\n", encoding="utf-8")
    print("Wrote", md_path, flush=True)
    print("Raw", raw_path, flush=True)
    sys.stdout.buffer.write((text[:5500] + "\n").encode("utf-8", "replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
