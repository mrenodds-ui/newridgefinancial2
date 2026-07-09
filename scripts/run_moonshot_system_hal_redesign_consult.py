"""Moonshot AI — workstation interference audit + full program deep-dive + HAL redesign.

Operator ask:
- Analyze the computer/runtime for interference with NR2 / other programs / errors
- Deep dive the program (visual + functional): what's wrong, how to fix, improvements + code
- Redesign HAL page: chat box on the RIGHT; more professional/in-depth look
- Widgets too big; too much diagnostic info; pages need to be compacted

Consult-only: writes report + paste-ready code. Does NOT apply changes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / ".local_logs" / "moonshot_financial_eval"
DOCS = REPO / "NewRidgeFinancial2" / "docs"
OUT.mkdir(parents=True, exist_ok=True)
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

sys.path.insert(0, str(OUT))
from _run_moonshot_eval import extract_message_content, resolve_api_and_endpoint  # noqa: E402

CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/site/hal-page-canvas.js", 450),
    ("NewRidgeFinancial2/site/hal-page.js", 200),
    ("NewRidgeFinancial2/site/hal-mockup-overrides.css", 200),
    ("NewRidgeFinancial2/site/nr2-moonshot-mockup-theme.css", 120),
    ("NewRidgeFinancial2/site/moonshot-page-registry.js", 220),
    ("NewRidgeFinancial2/site/app.js", 120),
    ("NewRidgeFinancial2/site/hal-live-widget-bridge.js", 100),
    ("NewRidgeFinancial2/site/hal-skills.js", 120),
    ("NewRidgeFinancial2/site/page-canvas.js", 150),
    ("NewRidgeFinancial2/nr2_hal_gateway.py", 100),
    ("NewRidgeFinancial2/hal_hub.py", 80),
    ("NewRidgeFinancial2/site/data/hal-models.json", 80),
    ("NewRidgeFinancial2/nr2-build.json", 40),
]

SYSTEM = """You are Moonshot AI (kimi-k2 class) — lead systems auditor + product/UX architect
for NewRidge Financial 2.0 (NR2), a solo dental practice financial cockpit on Windows.

Stack: Python Bottle (8765 financial+HAL, 8766 workstation), vanilla JS PageSchema/PageCanvas,
SQLite analytics, SoftDent + QuickBooks imports, local Ollama HAL. Build epoch: moonshot-mockup.

Analyze ONLY provided context + auto-collected workstation notes. Do not invent files or APIs.
When uncertain, say so and recommend discovery steps. Be actionable for a solo Windows operator.

OPERATOR REQUEST (CRITICAL — address ALL of it):
1) Analyze the computer/runtime for interference with NR2: port conflicts, competing programs,
   SoftDent/QuickBooks/Ollama/browser clashes, GPU/VRAM contention, stale processes, errors.
2) Deep dive the ENTIRE program for anything wrong — visual AND functional — with corrections,
   recommendations, and paste-ready CODE.
3) REDESIGN the HAL page:
   - Chat box MUST be on the RIGHT side (persistent chat rail)
   - More in-depth professional look (institutional finance / mission-control density)
   - Widgets are TOO BIG — shrink them
   - TOO MUCH diagnostic information on the main surface — hide under details/drawers
   - Pages need to be MORE COMPACTED rather than huge widgets
4) Provide concrete code (JS/CSS) for the HAL redesign and top program fixes.

HARD RULES:
- Preserve HAL widget keys from PageSchema (halAskHal, halImportHealth, practiceFinancialOverview,
  careDeliveryPerformance, quickbooksProfitLossDetail, officeManagerSurfaces, etc.).
- Prefer compact density: smaller mosaic tiles, collapsed diagnostics, chat-right split layout.
- Honesty: never fabricate financial numbers; empty states stay honest.
- Paste-ready code with exact file paths under NewRidgeFinancial2/site/.
- Mark P0/P1/P2 with acceptance criteria.
- No emoji in production widget titles.

OUTPUT FORMAT (strict markdown):
# Verdict (one paragraph — operator-facing)
## 1. Workstation / System Interference Audit
Port conflicts, SoftDent/QB/Ollama/browser interference, GPU/VRAM, stale NR2 processes, Windows errors
from the notes. What interferes with NR2 vs what is healthy. Fix steps.
## 2. Program Deep Dive — Functional Errors
P0/P1/P2 bugs, data pipeline gaps, HAL wiring, import health, validators. Evidence from context.
## 3. Program Deep Dive — Visual / UX Problems
Why widgets feel huge, diagnostic overload, weak professional density, page sprawl. All staff pages + HAL.
## 4. HAL Page Redesign Spec (chat RIGHT, compact, professional)
Layout ASCII/wire description: left command surface (compact hero + mosaic + surfaces), RIGHT sticky chat rail.
What to demote into <details>/drawers (HCI, stress, agent health, consent lists, runtime diagnostics).
Density targets (tile height, font sizes, grid gaps).
## 5. Moonshot Code Deliverables
### File: NewRidgeFinancial2/site/hal-page-canvas.js
```javascript
// paste-ready: renderDashboard + renderAskHal layout changes for chat-right + compact
```
### File: NewRidgeFinancial2/site/hal-mockup-overrides.css
```css
/* paste-ready: chat-right split, compact mosaic, demoted diagnostics */
```
### File: (optional other paths)
Additional paste-ready patches for top functional/visual fixes.
Minimum: full HAL layout JS change + CSS for right chat rail + compact widgets.
## 6. Staff Pages Compaction Recommendations
financial, taxes, softdent, quickbooks, ar, claims, narratives, documents, library, office-manager —
how to shrink widgets / reduce diagnostic chrome without losing HAL keys.
## 7. Prioritized Fix Roadmap (next 5 commits + acceptance criteria)
## 8. Operator Smoke Test Checklist
Browser + system checks after applying redesign.

Be specific. Reference real file/function names from context. Concise bullets + full code blocks."""


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


def _run(cmd: list[str], timeout: int = 45) -> str:
    try:
        r = subprocess.run(
            cmd,
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
        out = (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")
        return out.strip()[:4000] or f"(exit {r.returncode}, empty)"
    except Exception as exc:
        return f"(error: {exc})"


def collect_system_notes() -> str:
    notes: list[str] = ["## Operator request\n"]
    notes.append(
        "- Analyze entire computer/runtime for interference with NR2 or other programs; find errors.\n"
        "- Deep dive the program for anything wrong (visual + functional); how to correct; improvements; CODE.\n"
        "- Redesign HAL: chat box on the RIGHT; more professional in-depth look.\n"
        "- Widgets too big; too much diagnostic info; pages need to be compacted (not huge widgets).\n"
    )

    # Ports / listeners of interest
    notes.append("\n## Auto-collected workstation diagnostics\n")
    net = _run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | "
                "Where-Object { $_.LocalPort -in 8765,8766,11434,1433,3306,5432,8080,3000,5173 } | "
                "Select-Object LocalAddress,LocalPort,OwningProcess | Format-Table -AutoSize | Out-String -Width 200"
            ),
        ],
        timeout=60,
    )
    notes.append(f"### Listening ports (NR2-relevant)\n```\n{net}\n```\n")

    procs = _run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-Process -ErrorAction SilentlyContinue | "
                "Where-Object { $_.ProcessName -match 'python|ollama|chrome|msedge|SoftDent|QB|qbw|node|powershell' } | "
                "Sort-Object WorkingSet64 -Descending | Select-Object -First 40 "
                "Name,Id,@{N='MB';E={[math]::Round($_.WorkingSet64/1MB,1)}} | "
                "Format-Table -AutoSize | Out-String -Width 200"
            ),
        ],
        timeout=60,
    )
    notes.append(f"### Top related processes\n```\n{procs}\n```\n")

    ollama = _run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "try { (Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5).models | "
                "Select-Object -ExpandProperty name | Out-String } catch { $_.Exception.Message }"
            ),
        ],
        timeout=30,
    )
    notes.append(f"### Ollama models (local)\n```\n{ollama}\n```\n")

    # Financial app is TLS-by-default; plain HTTP to 8765 resets the socket (not a crash).
    nr2_health = _run(
        [
            "python",
            "-c",
            (
                "import ssl,urllib.request; ctx=ssl._create_unverified_context();\n"
                "u='https://127.0.0.1:8765/api/app-info'\n"
                "try:\n"
                " r=urllib.request.urlopen(u, context=ctx, timeout=5); print(r.status, r.read()[:120])\n"
                "except Exception as e:\n"
                " print(type(e).__name__, e)\n"
            ),
        ],
        timeout=30,
    )
    notes.append(f"### NR2 8765 health (HTTPS)\n```\n{nr2_health}\n```\n")

    # Workstation 8766 is pywebview desktop-token gated; bare browser GET / is expected 403.
    ws_health = _run(
        [
            "python",
            "-c",
            (
                "import urllib.request\n"
                "u='http://127.0.0.1:8766/workstation/index.html'\n"
                "try:\n"
                " r=urllib.request.urlopen(u, timeout=5); print(r.status)\n"
                "except Exception as e:\n"
                " print(type(e).__name__, e, '(403 without nr2dt token is expected for desktop-only workstation)')\n"
            ),
        ],
        timeout=30,
    )
    notes.append(f"### Workstation 8766 health (desktop-token gated)\n```\n{ws_health}\n```\n")

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
            notes.append(f"### Git status\n```\n{status.stdout.strip()[:2000]}\n```\n")
    except OSError:
        pass

    for cmd, label in [
        (["node", "validate-pages.mjs"], "validate-pages"),
        (["node", "validate-hal.mjs"], "validate-hal"),
    ]:
        try:
            r = subprocess.run(
                cmd,
                cwd=REPO / "NewRidgeFinancial2",
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            blob = ((r.stdout or "") + (r.stderr or ""))[:600]
            notes.append(f"### {label}\n```\nexit={r.returncode}\n{blob}\n```\n")
        except OSError as exc:
            notes.append(f"### {label}\n```\nerror: {exc}\n```\n")

    # HAL layout note from current code
    notes.append(
        "### Current HAL layout (from hal-page-canvas.js)\n"
        "- `render()` = `renderDashboard()` THEN `renderAskHal()` (chat appended AFTER dashboard, not a right rail).\n"
        "- Dashboard: situational hero + status rail, 8-tile widget mosaic, work surfaces, large session panel "
        "(consent + activity + system controls with HCI/stress/agent diagnostics in details).\n"
        "- Operator wants: chat RIGHT, smaller widgets, less diagnostic chrome, compacted professional look.\n"
    )
    return "".join(notes)


def resolve_model(base_url: str) -> str:
    explicit = str(os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "").strip()
    if explicit:
        return explicit
    base = (base_url or "").lower()
    if "openrouter" in base:
        return "moonshotai/kimi-k2"
    if "api.moonshot.ai" in base or "api.moonshot.cn" in base:
        return "kimi-k2.5"
    return "kimi-k2.5"


def main() -> int:
    # Probe helper reads User env via winreg and finds a working key/endpoint pair.
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No working Moonshot/OpenRouter API key found.", file=sys.stderr)
        return 1

    # Operator env often stores a Moonshot key under OPENROUTER_API_KEY; probe already
    # found the working host. Prefer Moonshot native when that host is moonshot.ai.
    if "moonshot" in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    else:
        model = resolve_model(base_url)
    # Moonshot native kimi models require temperature=1 exactly.
    temperature = 1.0
    print(f"Using {key_name} @ {base_url} model={model} temperature={temperature}")
    print("Collecting system diagnostics + codebase context...")

    user = (
        "Perform the full Moonshot system interference audit, program deep dive, and HAL redesign "
        "per the system instructions. NR2 build from moonshot-page-registry SCHEMA_VERSION.\n\n"
        + collect_system_notes()
        + "\n\n## Codebase context\n\n"
        + build_context()
    )

    # Try primary model, then fallbacks if the host rejects the model id.
    models_to_try = [model]
    if "moonshot" in (base_url or "").lower():
        for alt in ("kimi-k2.5", "kimi-k2.6", "moonshot-v1-128k"):
            if alt not in models_to_try:
                models_to_try.append(alt)
    elif "openrouter" in (base_url or "").lower():
        for alt in ("moonshotai/kimi-k2", "moonshotai/kimi-k2.5"):
            if alt not in models_to_try:
                models_to_try.append(alt)

    content = ""
    status = "error"
    used_model = model
    for try_model in models_to_try:
        payload = {
            "model": try_model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": 16000,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        if "openrouter" in base_url.lower():
            headers["HTTP-Referer"] = str(
                os.getenv("OPENROUTER_HTTP_REFERER") or "https://github.com/NewRidgeFamilyFinancial"
            )
            headers["X-Title"] = str(
                os.getenv("OPENROUTER_X_TITLE") or "NR2 System HAL Redesign Consult"
            )

        req = urllib.request.Request(
            base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        print(f"Calling Moonshot AI with model={try_model} (may take several minutes)...")
        try:
            with urllib.request.urlopen(req, timeout=3600) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = extract_message_content(body)
            status = "ok"
            used_model = try_model
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:4000]
            content = f"HTTP {exc.code}: {detail}"
            status = f"HTTP {exc.code}"
            print(f"  model={try_model} failed: {status}")
            if exc.code not in (400, 404) or "model" not in detail.lower():
                # Auth / other hard failures — don't keep trying models
                if exc.code in (401, 403):
                    break
            continue
        except Exception as exc:
            content = str(exc)
            status = "error"
            print(f"  model={try_model} error: {exc}")
            break
    model = used_model

    header = (
        f"# Moonshot AI — System Interference, Program Deep Dive & HAL Redesign\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Script:** `scripts/run_moonshot_system_hal_redesign_consult.py`\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")

    out_file = OUT / f"MOONSHOT_SYSTEM_HAL_REDESIGN_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_SYSTEM_HAL_REDESIGN_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
