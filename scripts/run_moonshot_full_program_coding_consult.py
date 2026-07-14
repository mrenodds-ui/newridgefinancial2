"""Moonshot AI — Full program coding review (CONSULT ONLY).

Operator: give all the coding to moonshot ai everything and ask for the
correct coding back to make this program work and report.

Does NOT apply patches. Writes coding + report docs for operator approval.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / ".local_logs" / "moonshot_financial_eval"
DOCS = REPO / "NewRidgeFinancial2" / "docs"
NR2 = REPO / "NewRidgeFinancial2"
OUT.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

HELPER = (
    REPO
    / "_archive"
    / "2026-07-10"
    / ".local_logs"
    / "moonshot_financial_eval"
    / "_run_moonshot_eval.py"
)
sys.path.insert(0, str(HELPER.parent))
from _run_moonshot_eval import extract_message_content, resolve_api_and_endpoint  # noqa: E402

OPERATOR_REQUEST_VERBATIM = (
    "i want you to give all the coding to moonshot ai everything and ask for "
    "the correct coding back to make this program work and report"
)

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL
(office financial program on https://127.0.0.1:8765/).

Operator wants CORRECT CODING BACK to make the program work, plus a REPORT.
CONSULT ONLY — DO NOT claim you applied code. empty ≠ $0. Never invent
SoftDent dollars / Gold CSV / ERA amounts. Prefer local Apex/HAL fixes over
GitHub/PR as the primary package. Real file paths only.

OFFICE POLICY:
- HAL AI = local `hal-local:32b` only on GPU (no cloud/other local models)
- SoftDent data truth for period-close via desktop SoftDent when required
  (Excel or Print Preview only — never Printer)
- Compact/zero-scroll target: micro≤120, secondary≤240, primary≤320
- KPI budget ≤4 pills above fold

CURRENT BUILD SKEW (fix this as first-class):
- Runtime `apex_backend.BUILD_ID` / widget payloads: **hal-10610**
- `nr2-build.json` + `app-info` schema/assetVersion: still **hal-10608**
- `site/apex-core.js` ASSET_V: **hal-10610**
- Start script still prints schema from nr2-build.json (stale)

JUST SHIPPED (hal-10610 compact remap — commit 214d2e9):
- Taxes: tax-core-strip on main; planning table/calendar → #taxes/planning
- Financial vitals: removed Efficiency pill (keep collections radial-gauge)
- SoftDent: ops chips → strip; collections gauge; TP strip; ledger limit=5
- Claims: aging exposure m; skip critical-actions when Top 5 present
- Tests: test_hal10610_compact_remap.py (pass locally)

PROCESS REALITY:
- Two python processes for ONE browser_app: venv launcher PID parents uv
  child that listens on 8765. Not a second NR2 UI. Singleton pidfile tracks
  parent but child is the listener — review if ensure_singleton is wrong
  for Windows venv re-exec.

KNOWN OPEN FAILURE MODES (confirm/refute with coding):
1) Build/schema/asset skew (10608 vs 10610) → client purge/skew reloads
2) SoftDent A/R dataset stale (~150 min) — critical completeness softGap
3) Financial still many below-fold widgets → page scroll remains
4) Widget warming-bridge stampede / fillProgress wrong page (prior consult)
5) Dual process confusion (operator nearly killed parent launcher)
6) SoftDent ops strip chain still ~12 status surfaces above fold
7) nr2-build.json not bumped with BUILD_ID on apply

YOUR JOB — return CORRECT CODING:
A) Ranked MUST / SHOULD / NICE packages to make the program coherently work
B) Full unified diffs against REAL paths (keep diffs surgical)
C) Explicit validation gates (pytest + live probes on 8765)
D) What NOT to redo
E) Executive report for the operator

OUTPUT (strict markdown):
# Verdict (one sentence)
## 0. Operator Intent (verbatim; confirm consult-only)
## 1. Program health diagnosis (what is broken vs already OK)
## 2. Ranked coding packages (MUST / SHOULD / NICE)
## 3. Full code patches (unified diffs — real files only)
## 4. Process/start script guidance (venv parent vs listener child)
## 5. What NOT to redo / invent
## 6. Acceptance criteria + validation gate
## 7. Executive Summary (5–7 bullets)
## 8. Approval checklist (operator must approve before apply)
Prefer one coherent ship package over a laundry list of unrelated ops.
"""


def _read(path: Path, limit: int | None = None) -> str:
    if not path.is_file():
        return f"(missing: {path})"
    text = path.read_text(encoding="utf-8", errors="replace")
    if limit is not None:
        lines = text.splitlines()
        text = "\n".join(lines[:limit])
        if len(lines) > limit:
            text += f"\n... ({len(lines) - limit} more lines)"
    return text


def _excerpt(path: Path, needle: str, before: int = 2, after: int = 40) -> str:
    if not path.is_file():
        return f"(missing: {path})"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, line in enumerate(lines):
        if needle in line:
            lo = max(0, i - before)
            hi = min(len(lines), i + after + 1)
            body = "\n".join(f"{n+1}|{lines[n]}" for n in range(lo, hi))
            return f"### {path.relative_to(REPO)} around `{needle}`\n```\n{body}\n```"
    return f"(needle not found in {path}: {needle})"


def _sanitize_snap(obj: object) -> object:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            lk = str(k).lower()
            if any(x in lk for x in ("token", "secret", "password", "csrf", "hubtoken", "session")):
                out[k] = "[REDACTED]"
            else:
                out[k] = _sanitize_snap(v)
        return out
    if isinstance(obj, list):
        return [_sanitize_snap(x) for x in obj]
    return obj


def _live_bundle() -> str:
    parts: list[str] = []
    snap_path = OUT / "moonshot_full_program_live_snap.json"
    if snap_path.is_file():
        raw = json.loads(snap_path.read_text(encoding="utf-8"))
        clean = _sanitize_snap(raw)
        # Keep pages + health + appInfo versions only for size
        slim = {
            "health": {
                k: (clean.get("health") or {}).get(k)
                for k in (
                    "ok",
                    "db",
                    "ollama",
                    "importPipeline",
                    "readinessLevel",
                    "import_bundle_age_minutes",
                    "softdentOdbcMode",
                )
            },
            "appInfo": {
                k: (clean.get("appInfo") or {}).get(k)
                for k in (
                    "schemaVersion",
                    "assetVersion",
                    "designSchemaVersion",
                    "importReadiness",
                )
            },
            "pages": clean.get("pages"),
            "censusPages": [
                {
                    "page": p.get("page"),
                    "total": p.get("total"),
                    "withData": p.get("withData"),
                    "empty": p.get("empty"),
                    "emptyIds": p.get("emptyIds"),
                }
                for p in ((clean.get("census") or {}).get("pages") or [])
                if isinstance(p, dict)
            ],
        }
        # Truncate readiness further
        ir = slim["appInfo"].get("importReadiness")
        if isinstance(ir, dict):
            slim["appInfo"]["importReadiness"] = {
                "summary": ir.get("summary"),
                "softGaps": ir.get("softGaps"),
                "blocking": ir.get("blocking"),
                "completeness": ir.get("completeness"),
            }
        parts.append(
            "### Live snap (sanitized)\n```json\n"
            + json.dumps(slim, indent=2)[:14000]
            + "\n```"
        )

    parts.append(_excerpt(NR2 / "apex_backend.py", "BUILD_ID = ", after=5))
    parts.append(_excerpt(NR2 / "site" / "apex-core.js", 'ASSET_V = "', after=8))
    parts.append(_excerpt(NR2 / "nr2-build.json", "schemaVersion", after=12))
    parts.append(_excerpt(NR2 / "browser_app.py", "def ensure_singleton", after=45))
    parts.append(
        _excerpt(
            REPO / "scripts" / "start_nr2_browser.ps1",
            "function Resolve-Python",
            after=25,
        )
    )
    parts.append(
        _excerpt(
            REPO / "scripts" / "start_nr2_browser.ps1",
            "Stop-AllBrowserAppProcesses",
            after=20,
        )
    )
    parts.append(
        _excerpt(NR2 / "apex_backend.py", "def _taxes_widgets", after=50)
    )
    parts.append(
        _excerpt(
            NR2 / "apex_financial_console_pack.py",
            "def build_financial_vital_signs",
            after=40,
        )
    )
    parts.append(_read(DOCS / "HAL_32B_COMPACT_WIDGETS_APPLIED_2026-07-13.md", 80))
    parts.append(
        "### Prior open issues (summaries)\n"
        "- Import cache KPIs warming-bridge stampede / `_FILL_PROGRESS` (consult 2026-07-13)\n"
        "- Crash/perf singleton + Sync 423 already shipped (hal-10608 era)\n"
        "- SoftDent A/R softGap stale in live snap\n"
        "- Compact remap applied but Financial scroll not fully solved\n"
    )
    return "\n\n".join(parts)


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No API key", file=sys.stderr)
        return 1
    if "moonshot" in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    else:
        model = str(
            os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2"
        ).strip()

    live = _live_bundle()
    user = (
        f"Operator request (verbatim):\n> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"Live + coding context:\n{live}\n\n"
        "Return the full report with CORRECT coding patches. Consult only — do not apply."
    )

    import urllib.error
    import urllib.request

    payload = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 12000,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    # kimi-k2.5 sometimes needs temperature 1 on moonshot direct
    if "moonshot" in base_url.lower() and "kimi" in model.lower():
        payload["temperature"] = 1.0

    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://newridgefamilyfinancial.local",
            "X-Title": "NR2 Moonshot Full Program Coding Consult",
        },
        method="POST",
    )
    print(f"key={key_name} model={model} base={base_url}", flush=True)
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:1000]
        print(f"HTTPError {e.code}: {err}", file=sys.stderr)
        return 1

    content = extract_message_content(body)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = OUT / f"moonshot_full_program_coding_raw_{stamp}.json"
    raw_path.write_text(
        json.dumps(
            {
                "model": model,
                "key": key_name,
                "base": base_url,
                "operator": OPERATOR_REQUEST_VERBATIM,
                "content": content,
                "raw": body,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    header = (
        f"# Moonshot AI — Full program coding (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Runtime BUILD:** hal-10610 (nr2-build.json still 10608)\n"
        f"**Script:** `scripts/run_moonshot_full_program_coding_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    doc_path = DOCS / f"MOONSHOT_FULL_PROGRAM_CODING_CONSULT_{DATE}.md"
    # coding twin for applied naming consistency
    coding_path = DOCS / f"MOONSHOT_FULL_PROGRAM_CODING_{DATE}.md"
    text = header + (content or "(empty model response)") + "\n"
    doc_path.write_text(text, encoding="utf-8")
    coding_path.write_text(text, encoding="utf-8")
    print(f"wrote {doc_path}", flush=True)
    print(f"wrote {coding_path}", flush=True)
    print(f"wrote {raw_path}", flush=True)
    preview = re.sub(r"[^\x00-\x7F]+", "?", content or "")[:5000]
    print("--- REPORT PREVIEW ---", flush=True)
    print(preview, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
