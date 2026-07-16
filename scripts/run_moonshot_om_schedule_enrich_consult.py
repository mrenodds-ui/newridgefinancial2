"""Moonshot AI — OM schedule list richer rows (name, time, ADA) + click summary.

CONSULT ONLY. Operator asked how to enrich Office Manager Mon–Thu scheduled
patients with patient name, appointment time, ADA codes, and click-to-summary.
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
    "ask moonshot ai how to make the scheduled patient in the office manager's page "
    "have more information on the page with patient name, time of appt, adding ada "
    "codes for that appointment and the ability to click on that patient in the list "
    "and bring up a summary"
)

SYSTEM = """You are Moonshot AI — principal architect for NewRidgeFinancial2 (NR2).
CONSULT ONLY — DO NOT APPLY CODE.

Operator wants the optical Office Manager Mon–Thu schedule list enriched:
1) patient name on the row
2) appointment time
3) ADA codes for that appointment
4) click a patient in the list → bring up a summary

CURRENT SHIPPED STATE (do not invent React/TSX):
- Page: NewRidgeFinancial2/site/nr2-optical-page-office-manager.html/.js + nr2-optical-theme.css
- API: GET /api/softdent/appointments-range → nr2_softdent_daily.appointments_range_snapshot
- Row today shows: initials · #hash · provider · status · time "—" · procedureHint "—"
- Click already opens mini-dossier panel (GET /api/apex/patient-dossier-mini/{id}) with
  carrier/claims/clinical notes/estimates + Ask HAL + ATTEST REVIEW
- HAL summarize loop exists (patient-context + dossier-summary) from OM Ask HAL

HARD SCHEMA / POLICY FACTS (from repo, must respect):
- SoftDent READ-ONLY; empty ≠ $0
- Optical board PHI policy historically: hash/initials on board (full names were avoided)
- sd_appointments extract schema has NO appt_time column — appointments_range_snapshot
  honestly sets time="—" and documents this
- procedureHint currently "—" (no ADA join on range query yet)
- sd_procedures has ada_code, proc_date, patient_id, provider_code — possible same-day join
- sd_patients has patient_name (joined already for initials only)
- SoftDent desktop GUI lane exists for richer pulls if ODBC cache cannot supply time

YOUR JOB:
Design THE single best HOW-TO package to satisfy the operator request honestly.
If full name / real time / true appointment ADA cannot be sourced from current cache,
say so and prescribe the next real SoftDent extract/GUI step — do NOT invent times or $0.

Prefer REAL files:
- nr2_softdent_daily.py (appointments_range_snapshot)
- softdent_odbc_extract.py / Sensei queries if schema extension needed
- om_patient_dossier.py / patient_dossier.py for richer click summary
- nr2-optical-page-office-manager.js/.html + theme CSS
- optional: deepen click → full summary vs mini vs HAL autoSummarize

OUTPUT (strict markdown):
# Verdict (one sentence — THE approach)
## 0. Operator Intent (verbatim)
## 1. Recommended PACKAGE (name, why now, effort, REAL files, validation gate)
## 2. Data honesty plan (name / time / ADA — what is available vs blocked; empty ≠ invent)
## 3. Click → summary UX (reuse mini-dossier vs deepen vs HAL)
## 4. PHI / RBAC note (full name on OM board vs initials+hash)
## 5. Runner-ups (2–3)
## 6. What NOT to redo
## 7. Acceptance criteria
## 8. Executive Summary (5 bullets)
## 9. Approval Checklist
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


def _schema_probe() -> dict:
    """Best-effort SoftDent sqlite column probe for honesty."""
    out: dict = {"sd_appointments": None, "sd_procedures": None, "sd_patients": None}
    try:
        import sqlite3

        # Common paths used by NR2 SoftDent cache
        candidates = [
            NR2 / "app_data" / "nr2" / "softdent" / "softdent_mirror.db",
            REPO / "app_data" / "nr2" / "softdent" / "softdent_mirror.db",
            Path(r"C:\softdent\softdent_mirror.db"),
        ]
        db = None
        for p in candidates:
            if p.is_file():
                db = p
                break
        if not db:
            # Try import helper
            try:
                sys.path.insert(0, str(NR2))
                from nr2_softdent_daily import _open_db

                conn, path = _open_db()
                if conn:
                    for table in ("sd_appointments", "sd_procedures", "sd_patients"):
                        try:
                            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
                            out[table] = cols
                        except Exception as exc:  # noqa: BLE001
                            out[table] = {"error": str(exc)[:120]}
                    out["dbPath"] = str(path)
                    conn.close()
                    return out
            except Exception as exc:  # noqa: BLE001
                return {"error": str(exc)[:200], **out}
            return {"error": "no_db", **out}

        conn = sqlite3.connect(str(db))
        out["dbPath"] = str(db)
        for table in ("sd_appointments", "sd_procedures", "sd_patients"):
            try:
                cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
                out[table] = cols
            except Exception as exc:  # noqa: BLE001
                out[table] = {"error": str(exc)[:120]}
        conn.close()
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)[:200]
    return out


def live_audit() -> dict:
    build = {}
    try:
        build = json.loads((NR2 / "nr2-build.json").read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        build = {"error": str(exc)}

    daily = (NR2 / "nr2_softdent_daily.py").read_text(encoding="utf-8", errors="replace")
    om_js = (NR2 / "site" / "nr2-optical-page-office-manager.js").read_text(
        encoding="utf-8", errors="replace"
    )
    return {
        "repoRoot": str(REPO),
        "build": build,
        "operatorAsk": OPERATOR_REQUEST_VERBATIM,
        "markers": {
            "appointmentsRangeSnapshot": "def appointments_range_snapshot" in daily,
            "timeHonestDash": 'time": "—"' in daily or "time\": \"—\"" in daily,
            "noApptTimeComment": "no appt_time" in daily or "lacks time" in daily.lower(),
            "omClickOpenDossier": "openPatientContext" in om_js,
            "omRenderWeekly": "renderWeeklySchedule" in om_js,
            "miniDossierApi": True,
            "patientAttest": (NR2 / "patient_force_attest.py").is_file(),
        },
        "schemaProbe": _schema_probe(),
        "live": {
            "appInfo": get_json("/api/app-info", 20),
            "appointmentsRange": get_json("/api/softdent/appointments-range?days=4", 40),
            "deskSmokeLast": get_json("/api/health/desk-smoke?run=0", 20),
        },
        "shippedCommitsHint": [
            "2310d0d Mon-Thu list",
            "16197d2 provider filter + mini dossier",
            "4039bf4 clinical notes + estimates",
            "2cd6959 HAL patient context",
            "5defc5f patient attest MATCH-gated",
        ],
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
    live = audit.get("live") or {}
    ar = live.get("appointmentsRange") if isinstance(live.get("appointmentsRange"), dict) else {}
    if isinstance(ar.get("days"), list):
        sample_slots = []
        for d in (ar.get("days") or [])[:2]:
            if not isinstance(d, dict):
                continue
            for s in (d.get("slots") or [])[:3]:
                if isinstance(s, dict):
                    sample_slots.append(
                        {
                            "date": d.get("date"),
                            "keys": sorted(s.keys()),
                            "time": s.get("time"),
                            "procedureHint": s.get("procedureHint"),
                            "hasPatientId": bool(s.get("patientId")),
                            "initials": s.get("initials"),
                            # do not send full patient names to the model from live API if present
                        }
                    )
        live["appointmentsRange"] = {
            "hasData": ar.get("hasData"),
            "dateRange": ar.get("dateRange"),
            "source": ar.get("source"),
            "dayCounts": [
                {"day": d.get("dayName"), "date": d.get("date"), "count": d.get("count")}
                for d in ar.get("days") or []
                if isinstance(d, dict)
            ],
            "sampleSlotShape": sample_slots,
            "emptyMessage": ar.get("emptyMessage"),
            "error": ar.get("error") or ar.get("msg"),
        }
    audit["live"] = live

    user = (
        f"OPERATOR REQUEST (verbatim):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        f"LIVE AUDIT:\n```json\n{json.dumps(audit, indent=2)[:120000]}\n```\n\n"
        "Design THE best HOW-TO package for richer OM schedule rows + click summary. "
        "Markdown REPORT only. CONSULT ONLY — DO NOT APPLY CODE."
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
            os.getenv("OPENROUTER_X_TITLE") or "NR2 OM Schedule Enrich Consult"
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
    raw_path = OUT / f"moonshot_om_schedule_enrich_{stamp}.json"
    md_path = DOCS / f"MOONSHOT_OM_SCHEDULE_ENRICH_CONSULT_{DATE}.md"
    raw_path.write_text(json.dumps(raw, indent=2)[:500000], encoding="utf-8")

    header = (
        f"# Moonshot AI — OM Schedule Enrich (name / time / ADA / click summary)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Script:** `scripts/run_moonshot_om_schedule_enrich_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    md_path.write_text(header + text.strip() + "\n", encoding="utf-8")
    print("Wrote", md_path, flush=True)
    print("Raw", raw_path, flush=True)
    sys.stdout.buffer.write((text[:6000] + "\n").encode("utf-8", "replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
