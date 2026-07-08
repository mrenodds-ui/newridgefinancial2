"""Moonshot AI comprehensive consultation — repo cleanup, data lanes, HAL, workstation, GPU."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / ".local_logs" / "moonshot_financial_eval"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/docs/MOONSHOT_FULLEST_EXTENT_COMPLETE_2026-07-09.md", 120),
    ("NewRidgeFinancial2/docs/MOONSHOT_SOFTDENT_EXTRACT_REPORT_2026-07-08.md", 180),
    ("NewRidgeFinancial2/docs/MOONSHOT_QB_SOFTDENT_SIDENOTES_REPORT_2026-07-07.md", 150),
    ("NewRidgeFinancial2/docs/MOONSHOT_PHASE5_HUB_PROTOCOL.md", 120),
    ("NewRidgeFinancial2/site/data/hal-models.json", 200),
    ("NewRidgeFinancial2/site/hal-agent-programming.js", 120),
    ("NewRidgeFinancial2/site/hal-narrative-library.js", 100),
    ("NewRidgeFinancial2/site/services.js", 150),
    ("NewRidgeFinancial2/softdent_operational_pipeline.py", 180),
    ("NewRidgeFinancial2/softdent_odbc_extract.py", 150),
    ("NewRidgeFinancial2/import_sync.py", 120),
    ("NewRidgeFinancial2/nr2_qb_reports.py", 120),
    ("NewRidgeFinancial2/hal_hub.py", 100),
    ("NewRidgeFinancial2/model-automation/README.md", 120),
    ("scripts/Refresh-NR2-DesktopShortcut.ps1", 80),
    ("scripts/Refresh-NR2-WorkstationShortcut.ps1", 80),
    (".gitignore", 80),
]

SYSTEM = """You are Moonshot AI (kimi-k2 class) consulting on NewRidge Financial 2.0 — a solo dental
practice financial cockpit (ports 8765 financial+HAL, 8766 office workstation). Stack: Python Bottle
server, vanilla JS PageSchema, SQLite analytics, read-only SoftDent + QuickBooks imports, local Ollama HAL.

Analyze ONLY the provided context and operator notes. Do not invent files or APIs. When uncertain, say so
and recommend discovery steps. Be actionable for a solo operator/developer on Windows.

Return markdown with EXACTLY these sections:
# Verdict
## 1. Repo Cleanup & Hygiene (unneeded files, _legacy, duplicates, git, .local_logs, scripts)
## 2. Architecture, Runtime & Error Fixes (8765/8766, validators, known gaps post hal-10085)
## 3. Claims Narratives from SoftDent Clinical Notes + HAL (workflow, data needs, implementation)
## 4. SoftDent — Additional Data to Extract (beyond current bridge/ODBC/daysheet)
## 5. QuickBooks — Capturing More Data (SDK, reports, OAuth, cross-domain with SoftDent)
## 6. HAL Programming Update (agent contract, tools, models, narrative/claims assist)
## 7. Desktop Icons & Program Launchers (Start Program + Workstation shortcuts)
## 8. Workstation ↔ SideNotes ↔ HAL Central Hub (8766 vs SideNotesIM, metadata-only, compatibility)
## 9. Best Local AI Model for 16GB Radeon RX 9060 XT (VRAM budget, pin strategy, speed vs quality)
## 10. Additional Suggestions (anything else high-value for this practice)
## Prioritized Roadmap (next 5 commits with acceptance criteria)

Use concise bullets. Reference specific module/file names from context. Mark priorities P0/P1/P2.
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


def collect_repo_notes() -> str:
    notes: list[str] = ["## Operator request & auto-collected repo notes\n"]
    notes.append(
        "- **Build:** hal-10085 (Tier S3 complete — semantic zoom, HAL presence, hero mirror, citations)\n"
        "- **Ask:** Evaluate entire `C:\\NewRidgeFamilyFinancial` for cleanup, errors, runtime, architecture, "
        "repo hygiene; claims narratives from SoftDent clinical notes with HAL; more SoftDent/QB data; HAL "
        "programming update; desktop icons for Start Program + Workstation; workstation vs SideNotes with "
        "HAL as hub; best AI model for 16GB Radeon; any other suggestions.\n"
    )
    try:
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if status.stdout.strip():
            notes.append(f"- **Git status:**\n```\n{status.stdout.strip()[:2000]}\n```\n")
    except OSError:
        pass

    large_dirs = [
        REPO / "NewRidgeFinancial2" / "sidenotes-helper" / "py32",
        REPO / "_legacy",
        REPO / "frontend",
        REPO / "app",
    ]
    for d in large_dirs:
        if d.is_dir():
            try:
                count = sum(1 for _ in d.rglob("*") if _.is_file())
                notes.append(f"- **Large folder:** `{d.relative_to(REPO)}` (~{count} files)\n")
            except OSError:
                pass

    untracked_script = REPO / "scripts" / "run_moonshot_softdent_extract_analysis.py"
    if untracked_script.is_file():
        notes.append("- **Untracked:** `scripts/run_moonshot_softdent_extract_analysis.py`\n")

    notes.append(
        "- **SoftDent gaps (prior report):** sd_payments/sd_adjustments=0; ODBC DSN unset; "
        "operatory_schedule.json missing; shallow claims from daysheet only; legacy bridge stale.\n"
    )
    notes.append(
        "- **Claims/narratives today:** `hal-narrative-library.js` templates + `services.js` local drafts; "
        "clinical notes from daysheet via `softdent_operational_pipeline.py`; full workflow in `_legacy/app/insurance_narratives/`.\n"
    )
    notes.append(
        "- **GPU:** AMD Radeon RX 9060 XT 16GB; Ollama at 127.0.0.1:11434; active lane hal-chat:8b; "
        "helper 14b disabled; models at D:\\LocalAI\\ActiveModels.\n"
    )
    notes.append(
        "- **Desktop shortcuts:** `Refresh-NR2-DesktopShortcut.ps1`, `Refresh-NR2-WorkstationShortcut.ps1`, "
        "icon at `assets/nr2-icon.ico`.\n"
    )
    return "".join(notes)


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
    sections = [
        "# Verdict",
        f"- Consultation did not run: {message}",
    ]
    for title in [
        "1. Repo Cleanup & Hygiene",
        "2. Architecture, Runtime & Error Fixes",
        "3. Claims Narratives from SoftDent Clinical Notes + HAL",
        "4. SoftDent — Additional Data to Extract",
        "5. QuickBooks — Capturing More Data",
        "6. HAL Programming Update",
        "7. Desktop Icons & Program Launchers",
        "8. Workstation ↔ SideNotes ↔ HAL Central Hub",
        "9. Best Local AI Model for 16GB Radeon RX 9060 XT",
        "10. Additional Suggestions",
        "Prioritized Roadmap",
    ]:
        sections.append(f"## {title}\n- N/A")
    return "\n\n".join(sections)


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_file = OUT_DIR / f"MOONSHOT_COMPREHENSIVE_CONSULT_{stamp}.md"
    doc_file = REPO / "NewRidgeFinancial2" / "docs" / f"MOONSHOT_COMPREHENSIVE_CONSULT_{stamp}.md"

    api_key = _resolve_api_key()
    if not api_key:
        content = _failure_report("Missing MOONSHOT_API_KEY, KIMI_K2_API_KEY, or OPENROUTER_API_KEY.")
        out_file.write_text(content, encoding="utf-8")
        print(out_file, file=sys.stderr)
        return 1

    user = (
        "Provide a comprehensive Moonshot consultation for the operator's full request list. "
        "The practice is New Ridge Family Dental (solo). NR2 is production at hal-10085.\n\n"
        + collect_repo_notes()
        + "\n\n## Codebase context\n\n"
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
        "max_tokens": 12000,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    referer = str(os.getenv("OPENROUTER_HTTP_REFERER") or "").strip()
    title = str(os.getenv("OPENROUTER_X_TITLE") or "NewRidgeFamilyFinancial Comprehensive Consult").strip()
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
        f"# Moonshot AI Comprehensive Consultation\n\n"
        f"**Date:** {stamp}  \n"
        f"**Model:** {model_label}  \n"
        f"**Build:** hal-10085  \n"
        f"**Script:** `scripts/run_moonshot_comprehensive_consult.py`\n\n"
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
