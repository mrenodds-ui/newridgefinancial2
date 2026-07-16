"""Moonshot AI — What's next after Trellis ClearCoverage full benefits report.

Operator: next
Just closed: Trellis full benefits scrape + printable HTML report (main c7f658b);
  SoftDent morning-bundle code harden APPLIED but live Excel still blocked.
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

OPERATOR_REQUEST_VERBATIM = "next"

SYSTEM = """You are Moonshot AI — principal architect for NewRidgeFinancial2 (NR2).
CONSULT ONLY — DO NOT APPLY CODE.

Operator said (verbatim): next

JUST CLOSED / SHIPPED ON MAIN:
- Trellis ClearCoverage FULL benefits scrape (deductible, annual max, Preventive/Basic/Major/Ortho,
  expanded ADA codes/%) hooked into nightly verify batch
- Printable HTML day report: trellis_eligibility_report_YYYY-MM-DD.html
- Status-only prior rows re-queued for benefits scrape on next --verify (not skipped as already done)
- SoftDent morning Excel bundle: CODE harden APPLIED (focus reclaim, F10 menus, AG*.XLS) but
  LIVE morningBundle.ok still false — Claim Management Chrome stole SoftDent; needs ATTENDED re-run

CONSTRAINTS:
- SoftDent READ-ONLY; empty ≠ $0; board PHI initials+hash
- SoftDent desktop: Excel or Print Preview only — never Printer / never File when Excel greyed
- Do NOT redo: OM schedule track, Trellis huddle panel, this-patient, PushEngage embeds,
  restart/Trellis HTTP proof, or flip forceCloseAvailable on GREEN+MATCH
- Prefer REAL Python + optical JS under NewRidgeFinancial2/ (no invented React paths)
- Tonight 10:10 PM Task Scheduler already runs Trellis --verify (will fill benefits)

YOUR JOB: Pick THE single best NEXT package + ordered backlog (2–4).

CANDIDATES (pick ONE as #1 from LIVE AUDIT + context):
1) Attended SoftDent morning Excel bundle re-run (close Claim Management; aging→register→collections)
2) Surface full benefits HTML / OM-safe link for staff (no $ on PHI huddle panel)
3) SoftDent desktop report-pull / HAL softdent-report-pull teach hardening
4) Optional QB stale AP/payroll refresh
5) Classic Apex 2B weekly widget (optional only)
6) Something else justified ONLY from LIVE AUDIT — real paths

OUTPUT (strict markdown):
# Verdict (one sentence)
## 0. Operator Intent (verbatim)
## 1. Recommended NEXT (name, why now, effort, REAL files under NewRidgeFinancial2/, validation gate)
## 2. Ordered backlog AFTER #1 (2–4)
## 3. Why this beats the other candidates now
## 4. What NOT to redo
## 5. Acceptance criteria
## 6. Executive Summary (5 bullets)
## 7. Approval Checklist
DO NOT APPLY CODE. Never invent file paths.
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
    tr = get_json("/api/trellis/tomorrow-insurance", 20)
    pc = get_json("/api/hal/tools/period-close-status", 20)
    ready = get_json("/api/import-readiness", 30)
    gaps = []
    if isinstance(ready, dict):
        gaps = ready.get("datasetGaps") or []
    vyne = REPO / "app_data" / "nr2" / "vyne_pulls"
    reports = sorted(vyne.glob("trellis_eligibility_report_*.html")) if vyne.is_dir() else []
    results = sorted(vyne.glob("tomorrow_trellis_verify_results_*.json")) if vyne.is_dir() else []
    return {
        "repoRoot": str(REPO),
        "nr2Root": str(NR2),
        "build": build,
        "commitHint": "Trellis full benefits + re-queue on main (c7f658b); morning bundle live still blocked",
        "realModulesExist": {
            "trellis_clearcoverage_scrape": (NR2 / "scripts" / "trellis_clearcoverage_scrape.py").is_file(),
            "build_trellis_eligibility_report": (
                NR2 / "scripts" / "build_trellis_eligibility_report.py"
            ).is_file(),
            "vyne_trellis_add_verify_batch": (NR2 / "scripts" / "vyne_trellis_add_verify_batch.py").is_file(),
            "softdent_gui_export": (NR2 / "softdent_gui_export.py").is_file(),
            "hal_brain_tools": (NR2 / "hal_brain_tools.py").is_file(),
            "daily_closeout": (NR2 / "daily_closeout.py").is_file(),
            "softdent_report_pull": (NR2 / "softdent_report_pull.py").is_file(),
        },
        "trellisArtifacts": {
            "eligibilityReports": [p.name for p in reports[-3:]],
            "verifyResults": [p.name for p in results[-3:]],
        },
        "live": {
            "appInfo": {
                "assetVersion": (get_json("/api/app-info", 15) or {}).get("assetVersion"),
                "schemaVersion": (get_json("/api/app-info", 15) or {}).get("schemaVersion"),
            },
            "deskSmokeLast": {
                "ok": smoke.get("ok") if isinstance(smoke, dict) else None,
                "status": smoke.get("status") if isinstance(smoke, dict) else None,
                "deskProof": smoke.get("deskProof") if isinstance(smoke, dict) else None,
                "forceCloseAvailable": smoke.get("forceCloseAvailable") if isinstance(smoke, dict) else None,
                "morningConfidence": smoke.get("morningConfidence") if isinstance(smoke, dict) else None,
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
                "emptyNotZero": pc.get("emptyNotZero") if isinstance(pc, dict) else None,
            },
            "importReadiness": {
                "ok": ready.get("ok") if isinstance(ready, dict) else None,
                "level": ready.get("level") if isinstance(ready, dict) else None,
                "lasersGreen": ((ready.get("alignmentLasers") or {}) if isinstance(ready, dict) else {}).get(
                    "green"
                ),
                "blockingCount": len(ready.get("blocking") or []) if isinstance(ready, dict) else None,
                "datasetGaps": gaps[:6] if isinstance(gaps, list) else [],
                "error": (ready.get("error") or ready.get("msg")) if isinstance(ready, dict) else None,
            },
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
        model = str(os.getenv("OPENROUTER_MODEL") or "moonshotai/kimi-k2.5").strip()

    audit = live_audit()
    audit_path = OUT / f"moonshot_whats_next_after_trellis_benefits_audit_{DATE}.json"
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")

    user = (
        "LIVE AUDIT JSON follows. Pick THE next package after Trellis full benefits closed.\n\n"
        + json.dumps(audit, indent=2)[:120000]
    )
    payload = {
        "model": model,
        "temperature": 1,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter.ai" in base_url:
        headers["HTTP-Referer"] = (
            os.getenv("OPENROUTER_HTTP_REFERER") or "https://127.0.0.1:8765/"
        )
        headers["X-Title"] = "NR2 Whats Next After Trellis Benefits"
    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=700) as resp:
            raw = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001
        err_body = ""
        if hasattr(exc, "read"):
            try:
                err_body = exc.read().decode("utf-8", "replace")[:500]
            except Exception:
                pass
        print("API_FAIL", type(exc).__name__, str(exc)[:400], err_body, file=sys.stderr)
        return 1

    text = extract_message_content(raw).strip()
    if not text:
        print("EMPTY_REPLY", file=sys.stderr)
        return 1

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_out = OUT / f"moonshot_whats_next_after_trellis_benefits_{stamp}.md"
    raw_out.write_text(text + "\n", encoding="utf-8")

    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_TRELLIS_BENEFITS_{DATE}.md"
    header = (
        "# Moonshot AI — What's Next After Trellis Full Benefits (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_trellis_benefits_consult.py`\n"
        f"**Closed:** Trellis ClearCoverage full benefits + HTML report (main); "
        "morning-bundle code harden (live still blocked)\n"
        "**Apply:** Operator must say continue / approve before Cursor applies.\n\n"
        "## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        "---\n\n"
    )
    doc.write_text(header + text + "\n", encoding="utf-8")
    print("WROTE", doc)
    print("AUDIT", audit_path)
    print("RAW", raw_out)
    sys.stdout.buffer.write((text[:5500] + "\n").encode("utf-8", "replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
