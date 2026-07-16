"""Moonshot AI — What's next after nr2-12072 continue proof (ee53f4c).

Operator: next
Closed: NR2 restart + desk GREEN/MATCH; trellisBenefits counts live; Preview≠money;
  SoftDent Excel still greyed; morningBundle attest_only.
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

JUST CLOSED on main (ee53f4c + bd435ae nr2-12072):
- Desk smoke GREEN/MATCH; forceCloseAvailable=false (laser-gated)
- morningConfidence.trellisBenefits live (patients/withBenefits/statusOnly, no $)
- SoftDent Print Preview Date Wizard harden shipped; aging probe still excelDisabled=true
- morningBundle.ok=false attest_only — SoftDent Excel greyed OR Select File Name pathless (refuse invent dirs)
- Cursor REJECTED flipping morningBundle.ok from Print Preview alone (Preview ≠ moneyBeamIngest)
- Optional QB AP/payroll still stale (SDK unavailable)
- Tonight 10:10 PM Trellis --verify will scrape ClearCoverage benefits for status-only rows

CONSTRAINTS:
- SoftDent READ-ONLY; empty ≠ $0; board PHI initials+hash
- Output Options: Excel OR Print Preview only — NEVER File, NEVER Printer
- Do NOT invent SoftDent Excel drops / directories / morningBundle.ok from Preview
- Do NOT flip forceCloseAvailable on GREEN+MATCH alone
- Do NOT redo: OM schedule, Trellis huddle PHI, benefits HTML surface, Preview Date Wizard harden, this-patient, PushEngage
- Prefer REAL NewRidgeFinancial2/ paths only (no phantom modules like hal_softdent_teach.json)

YOUR JOB: Pick THE single best NEXT package + ordered backlog (2–4).

CANDIDATES (pick ONE as #1 from LIVE AUDIT):
1) SoftDent Excel enablement operator runbook + attended morning-bundle re-run gate (no invent Excel)
2) Wait / monitor tonight Trellis benefits scrape; surface withBenefits>0 proof tomorrow AM
3) Optional QB AP/payroll inbox drop checklist (staff exports)
4) Classic Apex 2B (optional only)
5) Something else justified ONLY from LIVE AUDIT — real paths

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
    base = (os.getenv("MOONSHOT_API_BASE") or os.getenv("KIMI_K2_BASE_URL") or "").strip()
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
    pc = get_json("/api/hal/tools/period-close-status", 20)
    ready = get_json("/api/import-readiness", 30)
    elig = get_json("/api/trellis/eligibility-report", 20)
    info = get_json("/api/app-info", 15)
    mc = smoke.get("morningConfidence") if isinstance(smoke, dict) else None
    return {
        "repoRoot": str(REPO),
        "commitHint": "ee53f4c continue proof; bd435ae nr2-12072 Preview harden",
        "build": build,
        "live": {
            "appInfo": {
                "assetVersion": (info or {}).get("assetVersion") if isinstance(info, dict) else None,
            },
            "deskSmokeLast": {
                "ok": smoke.get("ok") if isinstance(smoke, dict) else None,
                "status": smoke.get("status") if isinstance(smoke, dict) else None,
                "deskProof": smoke.get("deskProof") if isinstance(smoke, dict) else None,
                "forceCloseAvailable": smoke.get("forceCloseAvailable") if isinstance(smoke, dict) else None,
                "morningConfidence": mc,
            },
            "eligibilityReport": {
                "ok": elig.get("ok") if isinstance(elig, dict) else None,
                "hasReport": elig.get("hasReport") if isinstance(elig, dict) else None,
                "patients": elig.get("patients") if isinstance(elig, dict) else None,
                "withBenefits": elig.get("withBenefits") if isinstance(elig, dict) else None,
                "statusOnly": elig.get("statusOnly") if isinstance(elig, dict) else None,
                "targetDate": elig.get("targetDate") if isinstance(elig, dict) else None,
            },
            "periodCloseStatus": {
                "ok": pc.get("ok") if isinstance(pc, dict) else None,
                "status": pc.get("status") if isinstance(pc, dict) else None,
                "morningBundle": pc.get("morningBundle") if isinstance(pc, dict) else None,
            },
            "importReadiness": {
                "ok": ready.get("ok") if isinstance(ready, dict) else None,
                "datasetGaps": (ready.get("datasetGaps") or [])[:6] if isinstance(ready, dict) else [],
            },
        },
        "realModulesExist": {
            "softdent_gui_export": (NR2 / "softdent_gui_export.py").is_file(),
            "softdent_report_pull": (NR2 / "softdent_report_pull.py").is_file(),
            "hal_brain_tools": (NR2 / "hal_brain_tools.py").is_file(),
            "desk_smoke": (NR2 / "desk_smoke.py").is_file(),
            "build_trellis_eligibility_report": (
                NR2 / "scripts" / "build_trellis_eligibility_report.py"
            ).is_file(),
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
            os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2.5"
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
        headers["X-Title"] = "NR2 Whats Next After 12072 Continue"

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
    raw_path = OUT / f"moonshot_whats_next_after_12072_continue_{stamp}.json"
    md_path = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_12072_CONTINUE_{DATE}.md"
    raw_path.write_text(json.dumps(raw, indent=2)[:500000], encoding="utf-8")
    header = (
        f"# Moonshot AI — What's Next After nr2-12072 Continue (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_12072_continue_consult.py`\n"
        f"**Closed:** ee53f4c continue proof + bd435ae Preview harden\n"
        f"**Apply:** Operator must say continue / approve before Cursor applies.\n\n"
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
