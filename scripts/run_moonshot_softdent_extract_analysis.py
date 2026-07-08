"""Moonshot AI consultation — SoftDent full data extraction strategy for NR2."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / ".local_logs" / "moonshot_financial_eval"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Key SoftDent integration files (truncated per file to stay within token budget).
CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/softdent_odbc_extract.py", 450),
    ("NewRidgeFinancial2/softdent_practice_exports.py", 350),
    ("NewRidgeFinancial2/softdent_operational_pipeline.py", 250),
    ("NewRidgeFinancial2/softdent_dashboard_period_sync.py", 200),
    ("NewRidgeFinancial2/nr2_softdent_daily.py", 200),
    ("NewRidgeFinancial2/import_sync.py", 200),
    ("NewRidgeFinancial2/import_loader.py", 150),
    ("NewRidgeFinancial2/import_contract.py", 120),
    ("docs/softdent_bridge_automation.md", 200),
    ("docs/softdent_end_of_day_ar_inventory.md", 200),
    ("_legacy/app/hal/softdent_read_broker.py", 250),
    ("NewRidgeFinancial2/docs/MOONSHOT_FULLEST_EXTENT_REPORT_2026-07-08.md", 200),
]

SYSTEM = """You are a senior dental practice management systems integrator and data architect.
You are consulting on NewRidge Financial 2.0 (NR2), a solo dental practice financial cockpit
that reads SoftDent data read-only and never writes back to SoftDent.

Analyze ONLY the provided codebase and docs. Do not invent tables, APIs, or SoftDent features
that are not evidenced in the context. When SoftDent schema details are unknown, say so and
recommend discovery steps.

Return markdown with EXACTLY these sections:
# Verdict
## SoftDent Data Inventory (what NR2 already ingests vs missing)
## Extraction Lanes Ranked (bridge exports, daysheet JSONL, ODBC, EOD reports, manual CSV)
## Full Data Extraction Blueprint (every data domain: patients, procedures, payments, claims, appointments, A/R, operatory, clinical notes, treatment plans, hygiene recall)
## Recommended Export File Contracts (filename, fields, frequency)
## ODBC Query Strategy (if applicable — DSN, table discovery, env-var query templates)
## Integration Roadmap (phased commits, acceptance criteria, widget unlocks)
## Risks & Compliance (read-only, PHI boundaries, stale data, sample-data rejection)
## Operator Checklist (concrete steps to get live data flowing)

Be specific to this codebase: reference module names, sd_* tables, import_sync lanes, and widget keys.
Prioritize getting ALL operational and financial data out of SoftDent to improve NR2 dashboards and HAL.
"""


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    omitted = len(lines) - max_lines
    return "\n".join(lines[:max_lines]) + f"\n\n... [{omitted} lines truncated] ..."


def build_context() -> str:
    parts: list[str] = []
    for rel, max_lines in CONTEXT_FILES:
        path = REPO / rel
        if not path.is_file():
            parts.append(f"### FILE: {rel}\n(missing)")
            continue
        content = _truncate(path.read_text(encoding="utf-8", errors="replace"), max_lines)
        ext = path.suffix.lstrip(".") or "txt"
        parts.append(f"### FILE: {rel}\n```{ext}\n{content}\n```")
    return "\n\n".join(parts)


def _resolve_api_key() -> str:
    return str(
        os.getenv("MOONSHOT_API_KEY")
        or os.getenv("KIMI_K2_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or ""
    ).strip()


def _resolve_base_url() -> str:
    explicit = str(os.getenv("MOONSHOT_API_BASE") or "").strip()
    if explicit:
        return explicit
    if os.getenv("MOONSHOT_API_KEY"):
        return "https://api.moonshot.ai/v1/chat/completions"
    return str(
        os.getenv("KIMI_K2_BASE_URL") or "https://openrouter.ai/api/v1/chat/completions"
    ).strip()


def _resolve_model() -> str:
    explicit = str(os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "").strip()
    if explicit:
        return explicit
    base = _resolve_base_url().lower()
    if "api.moonshot.ai" in base or "api.moonshot.cn" in base:
        return "kimi-k2.6"
    return "moonshotai/kimi-k2"


def _call_ollama(system: str, user: str) -> tuple[str | None, str | None]:
    base = str(os.getenv("AI_FRONTEND_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")
    model = str(os.getenv("AI_FRONTEND_MODEL") or "hal-chat:14b").strip()
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": 0.15, "num_predict": 8000},
    }
    req = Request(
        f"{base}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=3600) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError) as exc:
        return None, f"Ollama error: {exc}"
    content = str((body.get("message") or {}).get("content") or "").strip()
    if not content:
        return None, f"Ollama empty response: {json.dumps(body)[:2000]}"
    return content, None


def _failure_report(message: str) -> str:
    return "\n".join(
        [
            "# Verdict",
            f"- Analysis did not run: {message}",
            "## SoftDent Data Inventory (what NR2 already ingests vs missing)",
            "- No Moonshot analysis produced.",
            "## Extraction Lanes Ranked (bridge exports, daysheet JSONL, ODBC, EOD reports, manual CSV)",
            "- N/A",
            "## Full Data Extraction Blueprint",
            "- N/A",
            "## Recommended Export File Contracts",
            "- N/A",
            "## ODBC Query Strategy",
            "- N/A",
            "## Integration Roadmap",
            "- Set MOONSHOT_API_KEY and rerun scripts/run_moonshot_softdent_extract_analysis.py",
            "## Risks & Compliance",
            "- N/A",
            "## Operator Checklist",
            "- Configure API key and rerun.",
        ]
    )


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_file = OUT_DIR / f"MOONSHOT_SOFTDENT_EXTRACT_{stamp}.md"
    doc_file = REPO / "NewRidgeFinancial2" / "docs" / f"MOONSHOT_SOFTDENT_EXTRACT_REPORT_{stamp}.md"

    api_key = _resolve_api_key()
    if not api_key:
        content = _failure_report("Missing MOONSHOT_API_KEY, KIMI_K2_API_KEY, or OPENROUTER_API_KEY.")
        out_file.write_text(content, encoding="utf-8")
        print(out_file)
        return 1

    runtime_notes = f"""## Runtime context (auto-collected)

- Bridge exports folder: `C:\\Users\\mreno\\SoftDentBridge\\exports` (dashboard JSON, claims CSV, clinical notes JSON present; last modified June 2026)
- NR2 import inbox default: `app_data/nr2/document_inbox/softdent`
- ODBC env vars: SOFTDENT_ODBC_DSN / NR2_SOFTDENT_ODBC_DSN + per-table SOFTDENT_ODBC_*_QUERY
- sd_* SQLite tables: sd_providers, sd_patients, sd_procedures, sd_appointments, sd_claims, sd_payments, sd_adjustments
- Consent-gated admin route: POST /api/admin/extract-softdent-odbc
- Widgets needing live SoftDent data: softdentProductionDaily, softdentCollectionsDaily, softdentAgingReceivables, softdentNewPatientsMTD, softdentAppointmentsSnapshot, softdentClaimsOutstanding, softdentProviderProduction, softdentAdjustmentLog, softdentPatientRetention, operatory grid, case acceptance funnel

"""

    user = (
        "Analyze how to extract ALL useful data from SoftDent into NR2 to maximize dashboard, "
        "analytics, and HAL value. The practice runs SoftDent v19.x on Windows. Current bridge "
        "only drops 3 files. ODBC lane exists but queries are env-configured. Daysheet JSONL "
        "pipeline can derive claims/clinical notes. What is the complete extraction strategy?\n\n"
        + runtime_notes
        + build_context()
    )

    payload = {
        "model": _resolve_model(),
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 0.15,
        "top_p": 1,
        "max_tokens": 8000,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    referer = str(os.getenv("OPENROUTER_HTTP_REFERER") or "").strip()
    title = str(os.getenv("OPENROUTER_X_TITLE") or "NewRidgeFamilyFinancial SoftDent Extract").strip()
    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title

    req = Request(
        _resolve_base_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    model_label = _resolve_model()
    cloud_error: str | None = None
    content = ""
    try:
        with urlopen(req, timeout=3600) as response:
            body = json.loads(response.read().decode("utf-8"))
        choices = body.get("choices") if isinstance(body, dict) else []
        message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
        content = str((message or {}).get("content") or "").strip()
        if not content:
            cloud_error = f"Empty cloud response: {json.dumps(body)[:2000]}"
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        cloud_error = f"HTTP {exc.code}: {detail}"
    except URLError as exc:
        cloud_error = f"Network error: {exc.reason}"

    if not content:
        ollama_content, ollama_error = _call_ollama(SYSTEM, user)
        if ollama_content:
            model_label = str(os.getenv("AI_FRONTEND_MODEL") or "hal-chat:14b")
            content = ollama_content
            cloud_error = f"Cloud API unavailable ({cloud_error}); used local Ollama fallback."
        else:
            content = _failure_report(f"{cloud_error}; Ollama fallback failed: {ollama_error}")
            out_file.write_text(content, encoding="utf-8")
            print(out_file)
            return 1

    header = (
        f"# Moonshot SoftDent Full Data Extraction Analysis\n\n"
        f"**Date:** {stamp}  \n"
        f"**Model:** {model_label}  \n"
        f"**Script:** `scripts/run_moonshot_softdent_extract_analysis.py`\n\n"
    )
    if cloud_error and "fallback" in (cloud_error or ""):
        header += f"**Note:** {cloud_error}\n\n"
    header += "---\n\n"
    full = header + content
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
