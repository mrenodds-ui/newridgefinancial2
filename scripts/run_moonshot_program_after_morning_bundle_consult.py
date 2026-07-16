"""Moonshot AI — What's next after SoftDent morning bundle + program suggestion (CONSULT ONLY).

Operator: run agent program suggestion through Moonshot
Just shipped: a753f31 morning SoftDent aging+register+collections (nr2-12037);
c5de424 beamHash desk proof (nr2-12036); OPS alerts; Force Close.
Agent suggestion: desk smoke loop first, then watch real mornings.
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

OPERATOR_REQUEST_VERBATIM = (
    "what do you suggest for program — then: run it through moonshot. "
    "Agent proposal: after SoftDent morning bundle + beamHash proof + Force Close + OPS alerts, "
    "prioritize desk confidence: ship a short desk smoke loop (close status, money-beams + "
    "dataBeamHash, Force Close availability, VERIFY BEAM MATCH) before more SoftDent GUI "
    "hardening, BlueNote send, or QB consent UX. Watch one real morning next."
)

SYSTEM = """You are Moonshot AI — principal architect for NewRidgeFinancial2 (NR2).
CONSULT ONLY — DO NOT APPLY CODE.

Operator asked for a program suggestion and wants YOUR independent verdict on the agent's proposal.

JUST SHIPPED on main (through a753f31 → nr2/main), build nr2-12037-softdent-morning-bundle:

- a753f31 — morning SoftDent pull expands to aging + register + collections
  (aging required; register/collections best-effort; aging fail → attest-only)
- c5de424 — formal beamHash desk proof: dataBeamHash + 3s attest cache;
  GET /api/hal/tools/beam-verify; Hub/OM VERIFY BEAM; HAL money cites hashes
- 0874a03 / 9fa63f7 — period-close OPS alerts (HAL hub) for blocked/stalled/attest_only/Force Close
- 8a468c1 — Force Close optical Hub/OM
- Prior: SoftDent export harden, morning aging auto-pull, landing money-beams, path hygiene

AGENT PROGRAM PROPOSAL (evaluate — do not rubber-stamp):
1) NEXT: Desk smoke script/loop — close status + money-beams + Force Close availability + hash identity
2) Then watch one real morning with 3-report pull before more GUI work
3) Later: laser-stall timer if alerts feel late; defer BlueNote send / QB consent / more SoftDent IDs

PATH HYGIENE:
- ONLY C:\\Users\\mreno\\newridgefamilyfinancial
- NEVER C:\\NewRidgeFamilyFinancial
- SoftDent write-back FORBIDDEN; Excel/Print Preview only; empty ≠ $0
- SoftDent Select File Name never SoftDentReportExports
- Optical under NewRidgeFinancial2/site/nr2-optical-*

YOUR JOB:
Pick THE single best NEXT package for the program NOW.
Agree with the agent only if LIVE AUDIT + OPS risk say so; otherwise name a better next.
Prefer OPS if desk cannot trust shadow money; CODE when a concrete honesty gap remains.

CANDIDATES (pick ONE as THE next):
1) Desk smoke script: close status + money-beams/dataBeamHash + Force Close + VERIFY BEAM
2) Laser-stall timer: red lasers >5 min → OPS alert
3) SoftDent GUI harden further (only if LIVE AUDIT shows morning bundle failures)
4) Wire QB sync consent UX
5) True BlueNote network send (note: NR2 has no programmatic BlueNote send today — hub is the lane)
6) Something else justified from LIVE AUDIT — real paths only

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim)
## 1. Recommended NEXT (name, why now, effort, REAL files/ops, validation gate)
## 2. Why this beats the other candidates now (explicitly address the agent proposal)
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


def _file_has(path: Path, needle: str) -> bool:
    try:
        return needle in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def live_audit() -> dict:
    build = {}
    try:
        build = json.loads((NR2 / "nr2-build.json").read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        build = {"error": str(exc)}
    ops_dir = REPO / "app_data" / "nr2" / "ops"
    last_close = None
    last_force = None
    close_log = ops_dir / "daily_close_log.jsonl"
    force_log = ops_dir / "force_close_log.jsonl"
    for path, key in ((close_log, "lastClose"), (force_log, "lastForce")):
        if not path.is_file():
            continue
        try:
            lines = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
            if lines:
                row = json.loads(lines[-1])
                if key == "lastClose":
                    last_close = {
                        "status": row.get("status"),
                        "completedAt": row.get("completedAt"),
                        "beamHash": row.get("beamHash"),
                        "dataBeamHash": row.get("dataBeamHash"),
                        "fallback": row.get("fallback"),
                        "pullSoftdent": row.get("pullSoftdent"),
                        "softdentReports": row.get("softdentReports"),
                        "exportOkCount": row.get("exportOkCount"),
                        "exportPartial": row.get("exportPartial"),
                        "guiExport": row.get("guiExport"),
                        "forceClose": row.get("forceClose"),
                        "actor": row.get("actor"),
                    }
                else:
                    last_force = {
                        "ok": row.get("ok"),
                        "status": row.get("status"),
                        "beamHash": row.get("beamHash"),
                        "laserOverride": row.get("laserOverride"),
                        "actor": row.get("actor"),
                        "completedAt": row.get("completedAt") or row.get("timestamp"),
                    }
        except Exception as exc:  # noqa: BLE001
            if key == "lastClose":
                last_close = {"error": str(exc)[:120]}
            else:
                last_force = {"error": str(exc)[:120]}

    site = NR2 / "site"
    return {
        "repoRoot": str(REPO),
        "invalidRootExists": Path(r"C:\NewRidgeFamilyFinancial").exists(),
        "build": build,
        "commitHint": "a753f31 morning SoftDent bundle · c5de424 beamHash desk proof · 0874a03 OPS alerts",
        "agentProposal": {
            "next": "desk_smoke_script",
            "then": "watch_one_real_morning",
            "defer": ["bluenote_send", "qb_consent_ux", "more_softdent_report_ids"],
        },
        "lastCloseLog": last_close,
        "lastForceCloseLog": last_force,
        "codeMarkers": {
            "forcePeriodClose": _file_has(site / "nr2-optical-page-wire.js", "forcePeriodClose"),
            "bindVerifyBeamButton": _file_has(site / "nr2-optical-page-wire.js", "bindVerifyBeamButton"),
            "dataBeamHash": _file_has(NR2 / "hal_brain_tools.py", "dataBeamHash"),
            "softdent_export_morning_bundle": _file_has(
                NR2 / "hal_brain_tools.py", "softdent_export_morning_bundle"
            ),
            "beamVerifyRoute": _file_has(NR2 / "nr2_http_server.py", "/api/hal/tools/beam-verify"),
            "deskSmokeScriptExists": (REPO / "scripts" / "desk_beam_hash_smoke.py").is_file()
            or (REPO / "scripts" / "desk_ops_smoke.py").is_file(),
        },
        "live": {
            "appInfo": get_json("/api/app-info", 25),
            "importReadiness": get_json("/api/import-readiness", 40),
            "moneyBeams": get_json("/api/hal/tools/money-beams", 40),
            "beamVerify": get_json("/api/hal/tools/beam-verify", 40),
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
        ("MOONSHOT_WHATS_NEXT_AFTER_FORCE_CLOSE_APPLIED_2026-07-15.md", 3000),
        ("MOONSHOT_WHATS_NEXT_AFTER_FORCE_CLOSE_2026-07-15.md", 2500),
        ("MOONSHOT_WHATS_NEXT_AFTER_SOFTDENT_HARDEN_APPLIED_2026-07-15.md", 2000),
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
        + "\n\nReturn markdown only. CONSULT ONLY. Real paths only. "
        "Explicitly accept or reject the agent desk-smoke proposal with reasons."
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
        headers["X-Title"] = "NR2 Program Suggestion After Morning Bundle"

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
    (OUT / f"moonshot_program_after_morning_bundle_{stamp}.json").write_text(
        json.dumps(raw, indent=2)[:400000], encoding="utf-8"
    )
    (OUT / f"moonshot_program_after_morning_bundle_audit_{stamp}.json").write_text(
        json.dumps(audit, indent=2, default=str)[:200000], encoding="utf-8"
    )

    header = (
        f"# Moonshot AI — Program Suggestion After SoftDent Morning Bundle (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Status:** {status}\n"
        f"**Repo root:** `{REPO}`\n"
        f"**Prior:** `a753f31` SoftDent morning bundle · `c5de424` beamHash desk proof\n"
        f"**Script:** `scripts/run_moonshot_program_after_morning_bundle_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    md = header + (text.strip() or "_(empty)_") + "\n"
    md_path = DOCS / f"MOONSHOT_PROGRAM_AFTER_MORNING_BUNDLE_{DATE}.md"
    md_path.write_text(md, encoding="utf-8")
    (OUT / md_path.name).write_text(md, encoding="utf-8")
    print("Wrote", md_path)
    print("Status", status, "chars", len(text))
    return 0 if status == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
