"""Moonshot AI — purge legacy schema; mock-only staff pages with code deliverables."""

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
DOCS = REPO / "NewRidgeFinancial2" / "docs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/site/index.html", 240),
    ("NewRidgeFinancial2/site/moonshot-page-registry.js", 220),
    ("NewRidgeFinancial2/site/page-canvas.js", 120),
    ("NewRidgeFinancial2/site/page-views.js", 120),
    ("NewRidgeFinancial2/site/app.js", 160),
    ("NewRidgeFinancial2/site/desktop-boot.js", 120),
    ("NewRidgeFinancial2/site/nr2-moonshot-mockup-chrome.js", 120),
    ("NewRidgeFinancial2/mockup_elite_embed.py", 80),
    ("NewRidgeFinancial2/nr2_http_server.py", 80),
    ("NewRidgeFinancial2/moonshot-site.manifest.json", 120),
    ("NewRidgeFinancial2/validate-pages.mjs", 120),
    ("NewRidgeFinancial2/nr2-build.json", 30),
]

SYSTEM = """You are Moonshot AI (kimi-k2.6) — lead architect for NewRidge Financial 2.0.

OPERATOR GOAL (strict):
- **Remove ALL legacy page schema** (deleted: page-schema.js, page-chrome.js, hal-page-schema.js, pv-canvas shell, MoonshotLayoutEngine live wiring).
- **Staff program (8765) must ONLY show mock pages** for UI evaluation — elite HTML mockups embedded or displayed; NO live widget wiring, NO chart overlays, NO PageCanvasData-driven panel bodies until operator sign-off.
- HAL tab (#hal) may remain live; workstation (8766) is separate.

Current direction already in repo:
- PageSchema = moonshot-page-registry.js (epoch moonshot-mockup, hal-10100)
- PageCanvas.renderBody → mockupPreviewGate with iframe /mockup-elite-embed/<page>
- Elite gallery: .local_logs/moonshot_financial_eval/page_mockups_elite/*.html

Analyze ONLY provided context. Do not invent files.

Return markdown with EXACTLY these sections:
# Verdict (one paragraph)
## 1. Legacy Schema Still Present (inventory)
List every remaining reference path: JS loads, CSS, boot gates, validators, scripts, HAL memos, service worker, manifest bloat.
## 2. Mock-Only Target Architecture
Describe the minimal load order and what each staff page should render (nav chrome + iframe mock only).
## 3. Deletion List (files / blocks / routes to remove)
## 4. Moonshot Code Deliverables (ready-to-paste)
Provide **complete code blocks** for the top changes:
- index.html script list trim
- page-canvas.js / page-views.js mock-only path
- desktop-boot.js epoch gate
- validate-pages.mjs assertions
- Any server route for mock embed
Label each block: FILE, ACTION (replace/insert/delete).
## 5. Migration Steps (ordered, 5–8 steps with acceptance criteria)
## 6. Operator Smoke Test
URLs and what to see on Financial, QuickBooks, HAL.

Be specific. Prioritize P0/P1/P2. Include acceptance: no pv-* / hp-* on staff HTML, no layout engine, mock iframe visible.
"""


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n\n... [{len(lines) - max_lines} lines truncated] ..."


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
    elite = OUT_DIR / "page_mockups_elite"
    if elite.is_dir():
        names = sorted(p.stem for p in elite.glob("*.html") if p.name != "index.html")
        parts.append(f"### ELITE MOCK GALLERY\nPages: {', '.join(names)}\n")
    return "\n\n".join(parts)


def collect_notes() -> str:
    notes = [
        "## Operator request\n",
        "- Purge old schema completely.\n",
        "- Program staff pages = mock HTML only (elite gallery).\n",
        "- Provide code blocks and a report.\n",
        "- Build: hal-10100, epoch moonshot-mockup.\n",
    ]
    nr2 = REPO / "NewRidgeFinancial2"
    for cmd, label in [
        (["node", "validate-pages.mjs"], "validate-pages"),
        (["node", "validate-hal.mjs"], "validate-hal"),
    ]:
        try:
            r = subprocess.run(cmd, cwd=nr2, capture_output=True, text=True, timeout=180, check=False)
            notes.append(f"- **{label}:** exit={r.returncode}\n```\n{(r.stdout or r.stderr)[:500]}\n```\n")
        except OSError as exc:
            notes.append(f"- **{label}:** error {exc}\n")

    try:
        r = subprocess.run(
            ["git", "grep", "-n", "page-schema\\|page-chrome\\|hal-page-schema\\|pv-canvas\\|MoonshotLayoutEngine"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if r.stdout.strip():
            notes.append(f"- **git grep legacy:**\n```\n{r.stdout.strip()[:2500]}\n```\n")
    except OSError:
        pass
    return "".join(notes)


def _resolve_api_key() -> str:
    for name in ("OPENROUTER_API_KEY", "MOONSHOT_API_KEY", "KIMI_K2_API_KEY"):
        val = str(os.getenv(name) or "").strip()
        if val:
            return val
    return ""


def _resolve_base_url() -> str:
    if os.getenv("OPENROUTER_API_KEY"):
        return "https://openrouter.ai/api/v1/chat/completions"
    if os.getenv("MOONSHOT_API_KEY"):
        return "https://api.moonshot.ai/v1/chat/completions"
    return str(os.getenv("KIMI_K2_BASE_URL") or "https://openrouter.ai/api/v1/chat/completions").strip()


def _resolve_model() -> str:
    explicit = str(os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "").strip()
    if explicit:
        return explicit
    if "openrouter" in _resolve_base_url().lower():
        return "moonshotai/kimi-k2"
    if "api.moonshot.ai" in _resolve_base_url() or "api.moonshot.cn" in _resolve_base_url():
        return "kimi-k2.6"
    return "moonshotai/kimi-k2"


def _call_ollama(system: str, user: str) -> tuple[str | None, str | None]:
    base = str(os.getenv("AI_FRONTEND_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")
    model = str(os.getenv("AI_FRONTEND_MODEL") or "hal-chat:14b").strip()
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
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
    return (content, None) if content else (None, "Ollama empty response")


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_file = OUT_DIR / f"MOONSHOT_MOCK_ONLY_SCHEMA_{stamp}.md"
    doc_file = DOCS / f"MOONSHOT_MOCK_ONLY_SCHEMA_{stamp}.md"

    api_key = _resolve_api_key()
    user = collect_notes() + "\n\n## Codebase context\n\n" + build_context()

    model_label = _resolve_model()
    cloud_error: str | None = None
    content = ""

    if api_key:
        payload = {
            "model": model_label,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            "temperature": 0.15,
            "max_tokens": 16000,
        }
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        base = _resolve_base_url()
        if "openrouter" in base.lower():
            headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
            headers["X-Title"] = "NR2 Mock-Only Schema Consult"
        req = Request(base, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urlopen(req, timeout=3600) as response:
                body = json.loads(response.read().decode("utf-8"))
            choices = body.get("choices") if isinstance(body, dict) else []
            message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
            content = str((message or {}).get("content") or "").strip()
            if not content:
                cloud_error = f"Empty cloud response: {json.dumps(body)[:1500]}"
        except HTTPError as exc:
            cloud_error = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:1500]}"
        except URLError as exc:
            cloud_error = f"Network error: {exc.reason}"
    else:
        cloud_error = "No OPENROUTER_API_KEY / MOONSHOT_API_KEY / KIMI_K2_API_KEY set"

    if not content:
        ollama_content, ollama_error = _call_ollama(SYSTEM, user)
        if ollama_content:
            model_label = str(os.getenv("AI_FRONTEND_MODEL") or "hal-chat:14b")
            content = ollama_content
            cloud_error = f"Cloud API unavailable ({cloud_error}); used Ollama fallback."
        else:
            out_file.write_text(
                f"# Verdict\n\nConsultation failed.\n\n- Cloud: {cloud_error}\n- Ollama: {ollama_error}\n",
                encoding="utf-8",
            )
            print(out_file, file=sys.stderr)
            return 1

    header = (
        f"# Moonshot AI — Mock-Only Schema Purge\n\n"
        f"**Date:** {stamp}  \n"
        f"**Model:** {model_label}  \n"
        f"**Script:** `scripts/run_moonshot_mock_only_schema_consult.py`\n\n"
    )
    if cloud_error:
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
