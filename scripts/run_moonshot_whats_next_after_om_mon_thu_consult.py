"""Moonshot AI — What's next after OM Mon–Thu patient list (CONSULT ONLY).

Operator: continue
Just shipped on main: 2310d0d → 16197d2 → 873b4c6 optical OM Mon–Thu schedule
+ provider filter + mini dossier + claims + HAL handoff.
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

JUST SHIPPED on main (optical Office Manager Mon–Thu track):

- 2310d0d — Mon–Thu SoftDent patient schedule list on optical OM
  (nr2-optical-page-office-manager.html/.js + theme; GET /api/softdent/appointments-range)
- 16197d2 — Provider filter, mini dossier click panel, print CSS
- 873b4c6 — SoftDent claims sample on mini dossier + Ask HAL handoff
  (patientHash compose prefill on nr2-optical-page-hal.html)

Already true from prior Mon–Thu era (backend, not re-invent):
- appointments_range_snapshot + monday_of_week_iso
- om_patient_dossier.get_patient_dossier_mini / get_claims_review_detail
- HAL patient audit POST /api/audit/hal-patient-context
- Classic Apex append_office_manager_missing pack still STRIPPED (2B not done)

CONSTRAINTS:
- SoftDent READ-ONLY; empty ≠ $0; PHI hash/initials on board
- Optical pages under NewRidgeFinancial2/site/nr2-optical-page-*
- Do NOT redo the optical Mon–Thu list, provider filter, mini dossier, claims embed, or HAL prefill
- Classic Apex 2B (restore weekly widget pack) is OPTIONAL — only pick if clearly highest value now

YOUR JOB:
Pick THE single best NEXT package after this Mon–Thu OM patient track.

CANDIDATES (pick ONE as THE next):
1) Classic Apex OM weekly schedule widget restore (thin nr2_om_weekly_widget.py) — Option 2B
2) Deepen OM patient context: clinical notes summary + treatment estimate on click (local tools)
3) HAL patient hash handoff → real set_patient_context / dossier summarize tool (not just compose draft)
4) SoftDent/Trellis tomorrow-insurance worklist next step (repo has Trellis helpers uncommitted nearby)
5) Desk smoke: OM Mon–Thu list + mini dossier + Force Close / beam proof one-shot check
6) Something else justified from LIVE AUDIT — real paths only

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim)
## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
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

    om_js = (NR2 / "site" / "nr2-optical-page-office-manager.js").read_text(
        encoding="utf-8", errors="replace"
    )
    pack_py = NR2 / "apex_missing_widgets_pack.py"
    return {
        "repoRoot": str(REPO),
        "build": build,
        "commits": ["2310d0d", "16197d2", "873b4c6"],
        "opticalOmHasWeekly": "appointments-range" in om_js and "wk-dossier" in om_js,
        "classicPackExists": pack_py.is_file(),
        "live": {
            "appInfo": get_json("/api/app-info", 20),
            "appointmentsRange": get_json("/api/softdent/appointments-range?days=4", 40),
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
    # Trim live payload size for model
    live = audit.get("live") or {}
    ar = live.get("appointmentsRange") if isinstance(live.get("appointmentsRange"), dict) else {}
    if "days" in ar and isinstance(ar.get("days"), list):
        live["appointmentsRange"] = {
            "hasData": ar.get("hasData"),
            "dateRange": ar.get("dateRange"),
            "dayCounts": [
                {"day": d.get("dayName"), "date": d.get("date"), "count": d.get("count")}
                for d in ar.get("days") or []
                if isinstance(d, dict)
            ],
            "error": ar.get("error") or ar.get("msg"),
        }
    audit["live"] = live

    user = (
        f"OPERATOR REQUEST (verbatim):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        f"LIVE AUDIT:\n```json\n{json.dumps(audit, indent=2)[:120000]}\n```\n\n"
        "Pick THE single best NEXT package. Markdown REPORT only. CONSULT ONLY."
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
            os.getenv("OPENROUTER_X_TITLE") or "NR2 Whats Next After OM Mon-Thu"
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
    raw_path = OUT / f"moonshot_whats_next_after_om_mon_thu_{stamp}.json"
    md_path = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_OM_MON_THU_{DATE}.md"
    raw_path.write_text(json.dumps(raw, indent=2)[:500000], encoding="utf-8")

    header = (
        f"# Moonshot AI — What's Next After OM Mon–Thu Patient List (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_om_mon_thu_consult.py`\n"
        f"**Shipped:** `2310d0d` · `16197d2` · `873b4c6`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    md_path.write_text(header + text.strip() + "\n", encoding="utf-8")
    print("Wrote", md_path, flush=True)
    print("Raw", raw_path, flush=True)
    sys.stdout.buffer.write((text[:5000] + "\n").encode("utf-8", "replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
