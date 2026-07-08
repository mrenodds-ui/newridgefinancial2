"""Moonshot AI — final slice: complete Issue 4 remainder + Issues 5-6 + roadmap."""
from __future__ import annotations

import json
import os
import sys
import winreg
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / ".local_logs" / "moonshot_financial_eval"
DOCS = REPO / "NewRidgeFinancial2" / "docs"

SYSTEM = """You are Moonshot AI (kimi-k2.6). Provide COMPLETE code for NR2 Financial 2.0 (hal-10099, moonshot-mockup epoch).

Return markdown ONLY with these sections — keep code blocks complete and closed:

## Issue 4 (continued): AR, Claims, Office Manager, Documents — CODE

## Issue 5: Page Vocabulary — CODE
(taxes kpi-card/kpi-grid, narratives composer-grid x4, documents widget-grid x3, CSS in nr2-mockup-page-vocabulary.css)

## Issue 6: Chart Mount / enhancePage — CODE
(nr2-moonshot-ui.js enhancePage fix, mountChart replace-not-stack, app.js hook after renderPageView)

## Moonshot Independent Roadmap (next 5 commits)

## Operator Smoke Test

Use real files: page-canvas.js, nr2-moonshot-ui.js, app.js, nr2-mockup-page-vocabulary.css.
No Issues 1-3. Be concise in prose, complete in code."""


def _load_user_env(name: str) -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value or "").strip()
    except OSError:
        return ""


def _keys() -> list[tuple[str, str]]:
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for name in ("OPENROUTER_API_KEY", "MOONSHOT_API_KEY"):
        for val in (str(os.getenv(name) or "").strip(), _load_user_env(name)):
            if val and val not in seen:
                seen.add(val)
                out.append((name, val))
    return out


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    audit = (OUT_DIR / "MOCKUP_WIDGET_AUDIT_LATEST.md").read_text(encoding="utf-8", errors="replace")
    user = f"Audit gaps:\n{audit}\n\nComplete Issues 4-6 with code. Issue 4 partial already has financial+softdent chart panels."

    api_key = ""
    key_name = ""
    for name, val in _keys():
        api_key = val
        key_name = name
        break
    if not api_key:
        print("No API key", file=sys.stderr)
        return 1

    base = "https://api.moonshot.ai/v1/chat/completions"
    model = "kimi-k2.6"
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        "temperature": 1.0,
        "max_tokens": 16000,
    }
    req = Request(
        base,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=900) as resp:
            body = json.loads(resp.read())
    except HTTPError as e:
        print(e.read().decode(), file=sys.stderr)
        return 1

    content = str(body["choices"][0]["message"]["content"]).strip()
    out = DOCS / f"MOONSHOT_MOCKUP_FIX_PART3_{stamp}.md"
    log = OUT_DIR / f"MOONSHOT_MOCKUP_FIX_PART3_{stamp}.md"
    full = f"# Moonshot Part 3\n\n**Model:** {model} via {key_name}\n\n---\n\n{content}"
    out.write_text(full, encoding="utf-8")
    log.write_text(full, encoding="utf-8")
    print(out)
    print(f"chars={len(content)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
