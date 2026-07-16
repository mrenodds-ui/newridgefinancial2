"""Moonshot AI — What's next after continue-until-done track closed.

Operator: continue
Track closed: 82aa59e / 8619c2a / 5efcee3 / 4585e6d + MOONSHOT_CONTINUE_UNTIL_DONE_APPLIED
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

OPERATOR_REQUEST_VERBATIM = "continue"

SYSTEM = """You are Moonshot AI — principal architect for NewRidgeFinancial2 (NR2).
CONSULT ONLY — DO NOT APPLY CODE.

Operator said (verbatim): continue

JUST CLOSED on main (82aa59e / 8619c2a / 5efcee3 / 4585e6d / c2cda63):
- PushEngage flash-risk hygiene (AVOID embeds; cursor rule; HAL persona)
- appointments-range early returns always emit apptTimeColumn + emptyNotZero
- period_close_status.morningBundle + Hub close-chip surface
- desk smoke: trellis_tomorrow_http + morningConfidence (Force Close stays laser-gated)
- Hub/OM Force Close titles / bindForceCloseButton; Claims/HAL empty≠$0 polish
- SoftDent morning-bundle already on main via softdent_export_morning_bundle

CONSTRAINTS:
- SoftDent READ-ONLY; empty ≠ $0; board PHI initials+hash
- Do NOT redo: OM schedule enrich, Trellis huddle, this-patient, PushEngage scorer,
  or flip forceCloseAvailable true on GREEN+MATCH (laser-gated by design)
- Prefer REAL Python + optical JS paths (no invented React/SQLAlchemy)
- Pick THE next package + ordered backlog for sequential apply

CANDIDATES (pick ONE as #1 from LIVE AUDIT — invent nothing):
1) Restart / prove Trellis tomorrow HTTP 200 + desk smoke with HTTP GREEN
2) SoftDent GUI morning Excel bundle rehearsal / period-close shadow day run
3) Classic Apex 2B weekly widget (optional; only if audit warrants)
4) SoftDent desktop report-pull / period-close Excel path hardening
5) HAL BlueNote / voice / ducking follow-on (if audit shows gap)
6) Something else justified ONLY from LIVE AUDIT — real repo paths

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim)
## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
## 2. Ordered backlog AFTER #1 (2–4 items)
## 3. Why this beats the other candidates now
## 4. What NOT to redo
## 5. Acceptance criteria
## 6. Executive Summary (5 bullets)
## 7. Approval Checklist
DO NOT APPLY CODE. Never invent file paths not present in LIVE AUDIT or known NR2 layout.
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
    smoke = get_json("/api/health/desk-smoke?run=0", 20)
    smoke_live = get_json("/api/health/desk-smoke?run=1", 90)
    ar = get_json("/api/softdent/appointments-range?days=4", 40)
    tr = get_json("/api/trellis/tomorrow-insurance", 20)
    pc = get_json("/api/hal/tools/period-close-status", 20)
    return {
        "repoRoot": str(REPO),
        "build": build,
        "commitHint": "82aa59e continue-until-done track closed",
        "closedDocs": {
            "continueUntilDone": (DOCS / "MOONSHOT_CONTINUE_UNTIL_DONE_APPLIED_2026-07-16.md").is_file(),
            "postOmTrack": (DOCS / "MOONSHOT_POST_OM_TRACK_COMPLETE_2026-07-16.md").is_file(),
            "pushEngageApplied": (DOCS / "MOONSHOT_PUSHENGAGE_FLASH_RISK_APPLIED_2026-07-16.md").is_file(),
        },
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
                "morningConfidence": smoke.get("morningConfidence") if isinstance(smoke, dict) else None,
                "error": (smoke.get("error") or smoke.get("msg")) if isinstance(smoke, dict) else None,
            },
            "deskSmokeRun": {
                "ok": smoke_live.get("ok") if isinstance(smoke_live, dict) else None,
                "status": smoke_live.get("status") if isinstance(smoke_live, dict) else None,
                "failures": smoke_live.get("failures") if isinstance(smoke_live, dict) else None,
                "deskProof": smoke_live.get("deskProof") if isinstance(smoke_live, dict) else None,
                "forceCloseAvailable": smoke_live.get("forceCloseAvailable")
                if isinstance(smoke_live, dict)
                else None,
                "error": (smoke_live.get("error") or smoke_live.get("msg"))
                if isinstance(smoke_live, dict)
                else None,
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
            "periodCloseStatus": {
                "ok": pc.get("ok") if isinstance(pc, dict) else None,
                "status": pc.get("status") if isinstance(pc, dict) else None,
                "morningBundle": pc.get("morningBundle") if isinstance(pc, dict) else None,
                "forceClose": pc.get("forceClose") if isinstance(pc, dict) else None,
                "emptyNotZero": pc.get("emptyNotZero") if isinstance(pc, dict) else None,
                "error": (pc.get("error") or pc.get("msg")) if isinstance(pc, dict) else None,
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
        headers["X-Title"] = os.getenv("OPENROUTER_X_TITLE") or "NR2 Whats Next After Continue Done"

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
    raw_path = OUT / f"moonshot_whats_next_after_continue_done_{stamp}.json"
    md_path = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_CONTINUE_UNTIL_DONE_{DATE}.md"
    raw_path.write_text(json.dumps(raw, indent=2)[:500000], encoding="utf-8")
    header = (
        f"# Moonshot AI — What's Next After Continue-Until-Done (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_continue_until_done_consult.py`\n"
        f"**Shipped:** `82aa59e` continue-until-done closed\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
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
