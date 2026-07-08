"""Moonshot AI consultation — NR2 Workstation vs SideNotes, HAL as central hub."""

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
DOCS = REPO / "NewRidgeFinancial2" / "docs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/workstation-deploy/README-WORKSTATION.md", 120),
    ("NewRidgeFinancial2/docs/MOONSHOT_PHASE5_HUB_PROTOCOL.md", 150),
    ("NewRidgeFinancial2/docs/MOONSHOT_QB_SOFTDENT_SIDENOTES_REPORT_2026-07-07.md", 120),
    ("NewRidgeFinancial2/site/workstation/workstation-schema.js", 100),
    ("NewRidgeFinancial2/site/workstation-page.js", 200),
    ("NewRidgeFinancial2/site/sidenotes-hub.js", 100),
    ("NewRidgeFinancial2/site/sidenotes-office-fallback.js", 120),
    ("NewRidgeFinancial2/site/hal-hub-client.js", 120),
    ("NewRidgeFinancial2/site/workstation-message-popup.js", 150),
    ("NewRidgeFinancial2/sidenotes_bridge.py", 100),
    ("NewRidgeFinancial2/sidenotes_local_store.py", 120),
    ("NewRidgeFinancial2/workstation_app.py", 150),
    ("NewRidgeFinancial2/hal_hub.py", 120),
    ("NewRidgeFinancial2/site/hal-page-schema.js", 80),
    ("NewRidgeFinancial2/nr2-build.json", 20),
]

SYSTEM = """You are Moonshot AI (kimi-k2 class) consulting on NewRidge Financial 2.0 office messaging.

Architecture:
- **HAL hub (8765):** Owner/financial command center on the main PC — Start Program. HAL agent, KPIs, SideNotes monitor badge (metadata only, no message body).
- **NR2 Workstation (8766):** pywebview desktop app on each operatory/front-desk PC — Send Message + Ask HAL. NOT a browser app.
- **SideNotesIM:** Legacy office messaging app (SideNotesIM.exe) with history.vdb, station names (Room 1–5, Frontdesk, etc.), popups.
- **Integration:** Workstation sends via SideNotes bridge (32-bit helper) AND relays office-wide broadcasts to HAL hub. HAL is the central intelligence hub; workstations are thin clients.

The operator wants the NR2 Workstation program to be **better and comparable to SideNotes** while keeping **HAL as the main hub**.

Analyze ONLY the provided context. Do not invent APIs. When uncertain, recommend discovery steps.
Be actionable for a solo operator/developer on Windows.

Return markdown with EXACTLY these sections:
# Verdict
## 1. SideNotes vs NR2 Workstation — Feature Parity Gap Analysis
## 2. What NR2 Workstation Does Better Today
## 3. What SideNotes Still Wins On (must-match for operator adoption)
## 4. HAL-as-Hub Architecture — Strengths & Gaps
## 5. UX & Workflow Recommendations (make workstation feel like SideNotes)
## 6. Technical Improvements (bridge, popups, sync, reliability, offline)
## 7. Security & Compliance (metadata-only on 8765, hub token, LAN)
## 8. Migration Path (SideNotes-only → NR2 Workstation primary, SideNotes fallback)
## 9. Prioritized Roadmap (next 5 commits with acceptance criteria)

Use concise bullets. Reference specific module/file names. Mark priorities P0/P1/P2.
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
    for name in ("OPENROUTER_API_KEY", "MOONSHOT_API_KEY", "KIMI_K2_API_KEY"):
        val = str(os.getenv(name) or "").strip()
        if val:
            return val
    return ""


def _resolve_base_url() -> str:
    if os.getenv("OPENROUTER_API_KEY"):
        return "https://openrouter.ai/api/v1/chat/completions"
    explicit = str(os.getenv("MOONSHOT_API_BASE") or "").strip()
    if explicit:
        return explicit
    if os.getenv("MOONSHOT_API_KEY"):
        return "https://api.moonshot.ai/v1/chat/completions"
    return str(os.getenv("KIMI_K2_BASE_URL") or "https://openrouter.ai/api/v1/chat/completions").strip()


def _resolve_model() -> str:
    explicit = str(os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "").strip()
    if explicit:
        return explicit
    base = _resolve_base_url().lower()
    if "openrouter" in base:
        return "moonshotai/kimi-k2"
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


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_file = OUT_DIR / f"MOONSHOT_WORKSTATION_SIDENOTES_{stamp}.md"
    doc_file = DOCS / f"MOONSHOT_WORKSTATION_SIDENOTES_{stamp}.md"

    api_key = _resolve_api_key()
    if not api_key:
        print("Missing MOONSHOT_API_KEY, KIMI_K2_API_KEY, or OPENROUTER_API_KEY.", file=sys.stderr)
        return 1

    user = (
        "Consult on how to make the NR2 Office Workstation program better and comparable to SideNotesIM, "
        "with HAL (port 8765 Start Program) as the main hub. Build is hal-10095.\n\n"
        "## Operator goals\n"
        "- Workstation should feel as fast and reliable as SideNotes for room-to-room messaging\n"
        "- Popups must appear without opening the messenger window\n"
        "- Ask HAL on workstation should leverage the same HAL brain as 8765\n"
        "- Office-wide broadcasts should surface on HAL command center (metadata only)\n"
        "- Eventually reduce dependence on SideNotesIM.exe while keeping compatibility during transition\n\n"
        "## Codebase context\n\n"
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
    title = str(os.getenv("OPENROUTER_X_TITLE") or "NR2 Workstation SideNotes Consult").strip()
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
            print(f"Failed: {cloud_error}; Ollama: {ollama_error}", file=sys.stderr)
            return 1

    header = (
        f"# Moonshot AI — Workstation vs SideNotes (HAL Hub)\n\n"
        f"**Date:** {stamp}  \n"
        f"**Model:** {model_label}  \n"
        f"**Build:** hal-10095  \n"
        f"**Script:** `scripts/run_moonshot_workstation_sidenotes_consult.py`\n\n"
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
