"""Ask Moonshot AI which local Ollama models to pin on the R9700 32GB GPU."""

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
OUT_DIR.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)

CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/site/data/hal-models.json", 220),
    ("NewRidgeFinancial2/model-automation/README.md", 120),
    ("NewRidgeFinancial2/model-automation/Modelfile.hal-chat-8b", 80),
    ("NewRidgeFinancial2/model-automation/Modelfile.hal-escalate-30b", 80),
    ("NewRidgeFinancial2/nr2_hal_gateway.py", 100),
]

SYSTEM = """You are Moonshot AI (kimi-k2 class) consulting on NewRidge Financial 2.0 HAL local AI.

You advise a solo dental-practice operator/developer on Windows. Stack: Ollama local inference,
HAL agent with chat + escalation lanes, SoftDent/QuickBooks read-only imports, consent-gated outbound.

Analyze ONLY the provided GPU facts, inventory, and config. Do not invent VRAM numbers or models
not listed unless you clearly mark them as external recommendations to pull.

Return markdown with EXACTLY these sections:
# Verdict
## 1. Recommended Always-On GPU Pin Layout (what stays resident)
## 2. Role Map (chat / helper / reasoning / escalation / coder / deep)
## 3. Quantization & Context Budget (Q4/Q5/Q8, num_ctx, keep_alive)
## 4. What To Drop Or Keep On-Demand Only
## 5. Best Experience Config (speed + quality for staff HAL chat)
## 6. Greatest Program Config (max capability without thrashing VRAM)
## 7. Concrete Ollama Tags & Modelfile Changes
## 8. Risks On AMD ROCm / R9700
## Prioritized Apply Order (steps operator can validate before changing code)

Use concise bullets. Name specific Ollama tags. Mark priorities P0/P1/P2.
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


def load_user_env(name: str) -> str:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value or "").strip()
    except OSError:
        return ""


def _collect_keys() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name in ("MOONSHOT_API_KEY", "OPENROUTER_API_KEY", "KIMI_K2_API_KEY"):
        for src, val in (
            ("process", str(os.getenv(name) or "").strip()),
            ("registry", load_user_env(name)),
        ):
            if val and val not in seen and len(val) >= 20:
                seen.add(val)
                found.append((f"{name}/{src}", val))
    return found


def _endpoints_for_key(key_label: str) -> list[tuple[str, str]]:
    """Return (url, model) pairs. Prefer Moonshot direct — OpenRouter key often works there."""
    explicit_base = str(os.getenv("MOONSHOT_API_BASE") or "").strip()
    explicit_model = str(os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "").strip()
    if explicit_base:
        model = explicit_model or ("kimi-k2.6" if "moonshot" in explicit_base.lower() else "moonshotai/kimi-k2")
        return [(explicit_base, model)]
    # kimi-k2.5 accepts custom temperature; kimi-k2.6 often requires temperature=1 only.
    pairs: list[tuple[str, str]] = [
        ("https://api.moonshot.ai/v1/chat/completions", explicit_model or "kimi-k2.5"),
        ("https://api.moonshot.ai/v1/chat/completions", "kimi-k2.6"),
    ]
    if "OPENROUTER" in key_label:
        pairs.append(
            ("https://openrouter.ai/api/v1/chat/completions", explicit_model or "moonshotai/kimi-k2")
        )
    return pairs


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_file = OUT_DIR / f"MOONSHOT_GPU_MODEL_CONSULT_{stamp}.md"
    doc_file = DOCS / f"MOONSHOT_GPU_MODEL_CONSULT_{stamp}.md"

    keys = _collect_keys()
    if not keys:
        print("Missing usable MOONSHOT_API_KEY / OPENROUTER_API_KEY / KIMI_K2_API_KEY.", file=sys.stderr)
        return 1

    user = (
        "Recommend the best AI models to run on my GPU for the best staff experience "
        "and the greatest HAL program capability. Wait for operator validation before any apply.\n\n"
        "## GPU facts (operator-verified)\n"
        "- Device: AMD Radeon AI PRO R9700\n"
        "- VRAM: 32 GB\n"
        "- Vendor/library: AMD / ROCm (gfx1201)\n"
        "- Runtime: Ollama 0.31.1 at 127.0.0.1:11434 (server may bind 0.0.0.0)\n"
        "- Models path: D:\\LocalAI\\ActiveModels\n"
        "- Current pin: hal-chat:8b + hal-escalate:30b (~5 GB + ~18 GB, ctx 3072/4096, keep_alive -1)\n"
        "- OLLAMA_MAX_LOADED_MODELS=2\n"
        "- Integrated Intel GPU disabled (OLLAMA_IGPU_ENABLE=0)\n\n"
        "## Program goals\n"
        "- Best experience: fast, natural staff chat; reliable escalation for hard insurance/accounting questions\n"
        "- Greatest program: strongest local agent loop (tools, coding, deep review) without constant VRAM thrash\n"
        "- Stay local-first; PHI stays on machine\n"
        "- Prefer dual-resident pins when possible on 32 GB\n\n"
        "## Inventory available (from config)\n"
        "hal-chat:8b, hal-escalate:30b, hal-helper:14b, deepseek-r1:8b, deepseek-r1:14b, "
        "qwen3:14b, qwen3:4b, qwen3-coder:30b, qwen2.5-coder:32b, qwen3:235b, gpt-oss:120b, "
        "qwen3:30b, mistral-small3.1:24b-fast, mistral-small3.1:24b, llama3.3:latest\n\n"
        "## Codebase context\n\n"
        + build_context()
    )

    payload_messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
    ]

    body = None
    used_key = ""
    used_url = ""
    used_model = ""
    last_err = ""

    for key_label, api_key in keys:
        for base_url, model in _endpoints_for_key(key_label):
            # Moonshot kimi-k2.x: temperature=1 and top_p=0.95 only.
            if "api.moonshot." in base_url:
                payload = {
                    "model": model,
                    "messages": payload_messages,
                    "temperature": 1.0,
                    "top_p": 0.95,
                    "max_tokens": 10000,
                }
            else:
                payload = {
                    "model": model,
                    "messages": payload_messages,
                    "temperature": 0.15,
                    "top_p": 1,
                    "max_tokens": 10000,
                }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": str(
                    os.getenv("OPENROUTER_HTTP_REFERER") or "https://github.com/NewRidgeFamilyFinancial"
                ),
                "X-Title": str(os.getenv("OPENROUTER_X_TITLE") or "NR2 GPU Model Consult"),
            }
            req = Request(
                base_url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            print(f"Trying {key_label} @ {base_url} model={model} ...")
            try:
                with urlopen(req, timeout=600) as response:
                    body = json.loads(response.read().decode("utf-8"))
                used_key, used_url, used_model = key_label, base_url, model
                break
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:400]
                last_err = f"HTTP {exc.code}: {detail}"
                print(f"  fail: {last_err}")
            except URLError as exc:
                last_err = f"URL error: {exc}"
                print(f"  fail: {last_err}")
        if body is not None:
            break

    if body is None:
        print(f"All endpoints failed. Last error: {last_err}", file=sys.stderr)
        return 1

    content = str((body.get("choices") or [{}])[0].get("message", {}).get("content") or "").strip()
    if not content:
        print(f"Empty response: {json.dumps(body)[:2000]}", file=sys.stderr)
        return 1

    header = (
        f"# Moonshot GPU Model Consult\n\n"
        f"**Date:** {stamp}  \n"
        f"**Model:** {used_model} via {used_key} @ {used_url}  \n"
        f"**GPU:** AMD Radeon AI PRO R9700 · 32 GB VRAM · ROCm  \n"
        f"**Status:** AWAITING OPERATOR VALIDATION — do not apply until approved  \n\n"
        f"---\n\n"
    )
    report = header + content
    out_file.write_text(report, encoding="utf-8")
    doc_file.write_text(report, encoding="utf-8")
    print(f"Wrote {out_file}")
    print(f"Wrote {doc_file}")
    print("\n" + "=" * 72 + "\n")
    print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
