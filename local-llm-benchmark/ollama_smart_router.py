#!/usr/bin/env python3
"""
Ollama Smart Router + Benchmark (Windows)
=========================================

Connects to a local Ollama server on **http://127.0.0.1:11434** using the
official **OpenAI-compatible** API (`openai` Python library).

## Setup (run in PowerShell or CMD)

### 1. Install Ollama for Windows

Download and install from https://ollama.com/download , then verify:

```powershell
ollama --version
```

Ollama runs as a Windows background service. If commands fail, open the
Ollama app or run:

```powershell
ollama serve
```

### 2. Download the 8B model (fast lane)

If you already use HAL's pinned chat tag, skip the pull and use `hal-chat:8b` (default).

```powershell
# HAL workstation tag (default in this script)
ollama list | findstr hal-chat

# Or stock Llama 3 8B
ollama pull llama3:8b
```

### 3. Download a 30B-class model (heavy lane)

Default in this script: `qwen3:30b` (already on this workstation).

```powershell
# Default — Q4_K_M (~18 GB)
ollama pull qwen3:30b

# Alternatives
ollama pull qwen2.5:32b
ollama pull command-r
```

Verify:

```powershell
ollama show qwen3:30b
```

### 4. Install Python dependencies

```powershell
cd path/to/this/script
py -3 -m venv .venv
.venv/Scripts/Activate.ps1
pip install openai httpx rich python-dotenv
```

Optional — official Ollama Python client (same server):

```powershell
pip install ollama
```

### 5. Quick smoke test

```powershell
python ollama_smart_router.py health
python ollama_smart_router.py chat "Summarize why local LLMs help with privacy."
python ollama_smart_router.py bench --suite
```

---

Usage
-----
    python ollama_smart_router.py health
    python ollama_smart_router.py route "Classify these tickets as billing or clinical."
    python ollama_smart_router.py chat "Implement merge sort in Python with O(n log n) time."
    python ollama_smart_router.py bench "Summarize on-prem inference benefits."
    python ollama_smart_router.py bench --suite
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from enum import Enum

import httpx
from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.table import Table

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "127.0.0.1")
OLLAMA_PORT = int(os.getenv("OLLAMA_PORT", "11434"))
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/v1")
OLLAMA_CHAT = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/chat"
OLLAMA_HEALTH = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/version"
OLLAMA_TAGS = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/tags"
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")

MODEL_FAST = os.getenv("OLLAMA_MODEL_FAST", "hal-chat:8b")
MODEL_HEAVY = os.getenv("OLLAMA_MODEL_HEAVY", "hal-escalate:30b")

MAX_TOKENS = int(os.getenv("OLLAMA_MAX_TOKENS", "512"))
TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))
HEALTH_TIMEOUT = float(os.getenv("OLLAMA_HEALTH_TIMEOUT", "5"))
SHORT_PROMPT_CHARS = int(os.getenv("OLLAMA_SHORT_PROMPT_CHARS", "120"))

# Qwen3 (and other thinking models) hide output in a `thinking` field unless think=false.
# The OpenAI-compatible API does not expose think=false, so the heavy lane uses native /api/chat.
HEAVY_THINK_ENABLED = os.getenv("OLLAMA_HEAVY_THINK", "0").strip().lower() in {"1", "true", "yes"}

console = Console()


def _use_native_chat(model: str) -> bool:
    """Route models that need native Ollama options (e.g. think=false)."""
    if model == MODEL_HEAVY:
        return True
    base = model.split(":")[0].lower()
    return base in {"qwen3", "deepseek-r1"} and not HEAVY_THINK_ENABLED


def _think_flag(model: str) -> bool | None:
    if not _use_native_chat(model):
        return None
    if HEAVY_THINK_ENABLED and model == MODEL_HEAVY:
        return True
    return False


class TaskKind(str, Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"


@dataclass(frozen=True)
class RouteDecision:
    kind: TaskKind
    model: str
    reason: str


@dataclass(frozen=True)
class BenchmarkResult:
    model: str
    prompt: str
    route_reason: str
    kind: str
    ttft_ms: float | None
    generation_ms: float
    total_ms: float
    output_tokens: int
    tokens_per_second: float | None
    preview: str
    error: str | None = None


# ---------------------------------------------------------------------------
# Server health
# ---------------------------------------------------------------------------


class OllamaOfflineError(RuntimeError):
    """Raised when the Ollama Windows service / server is not reachable."""


def check_ollama_running() -> dict:
    """Verify Ollama is listening and return version payload."""
    try:
        with httpx.Client(timeout=HEALTH_TIMEOUT) as client:
            response = client.get(OLLAMA_HEALTH)
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError as exc:
        raise OllamaOfflineError(
            "Ollama is not running or not reachable on "
            f"{OLLAMA_HOST}:{OLLAMA_PORT}.\n"
            "Fix: open the Ollama app, or run `ollama serve` in a terminal, "
            "then retry."
        ) from exc
    except httpx.HTTPError as exc:
        raise OllamaOfflineError(
            f"Ollama health check failed at {OLLAMA_HEALTH}: {exc}"
        ) from exc


def list_installed_models() -> list[str]:
    with httpx.Client(timeout=HEALTH_TIMEOUT) as client:
        response = client.get(OLLAMA_TAGS)
        response.raise_for_status()
        payload = response.json()
    names: list[str] = []
    for item in payload.get("models") or []:
        name = item.get("name")
        if isinstance(name, str):
            names.append(name)
    return names


def ensure_ollama_ready(required: list[str] | None = None) -> None:
    check_ollama_running()
    if not required:
        return
    installed = list_installed_models()
    missing = [m for m in required if not _model_present(m, installed)]
    if missing:
        raise OllamaOfflineError(
            "Ollama is running but these models are missing: "
            + ", ".join(missing)
            + f"\nPull them, e.g.: ollama pull {missing[0]}"
        )


def _model_present(target: str, installed: list[str]) -> bool:
    base = target.split(":")[0]
    return any(name == target or name.startswith(f"{base}:") for name in installed)


# ---------------------------------------------------------------------------
# Smart routing
# ---------------------------------------------------------------------------

_SIMPLE_RE = re.compile(
    r"\b(summarize|summary|classify|classification|categorize|label|extract|"
    r"bullet|tl;dr|shorten|paraphrase|sentiment|rewrite|translate)\b",
    re.I,
)
_COMPLEX_RE = re.compile(
    r"\b(code|coding|implement|debug|refactor|algorithm|logic|sql|python|javascript|"
    r"typescript|function|class|api|regex|optimize|architecture|prove|derive|"
    r"analyze|analysis|investigate|root cause|multi-step|complex)\b",
    re.I,
)
_CODE_FENCE = re.compile(r"```")


def route_prompt(prompt: str, *, force: TaskKind | None = None) -> RouteDecision:
    """Route short/basic prompts to 8B; code/deep analysis to 30B-class model."""
    if force is not None:
        model = MODEL_FAST if force is TaskKind.SIMPLE else MODEL_HEAVY
        return RouteDecision(kind=force, model=model, reason=f"forced:{force.value}")

    text = (prompt or "").strip()
    lowered = text.lower()

    if _CODE_FENCE.search(text):
        return RouteDecision(TaskKind.COMPLEX, MODEL_HEAVY, "code_fence")

    if _COMPLEX_RE.search(text):
        return RouteDecision(TaskKind.COMPLEX, MODEL_HEAVY, "complex_keywords")

    if _SIMPLE_RE.search(text):
        return RouteDecision(TaskKind.SIMPLE, MODEL_FAST, "simple_keywords")

    if len(text) <= SHORT_PROMPT_CHARS:
        return RouteDecision(TaskKind.SIMPLE, MODEL_FAST, f"short_prompt<={SHORT_PROMPT_CHARS}")

    if len(text) > 400:
        return RouteDecision(TaskKind.COMPLEX, MODEL_HEAVY, "long_prompt")

    # Default: simple manipulation / Q&A -> fast model
    return RouteDecision(TaskKind.SIMPLE, MODEL_FAST, "default_simple")


# ---------------------------------------------------------------------------
# Inference — OpenAI-compatible + native Ollama (/api/chat, think=false for 30B)
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text.split()))


def make_client() -> OpenAI:
    return OpenAI(base_url=OLLAMA_BASE, api_key=OLLAMA_API_KEY)


def _native_stream(
    prompt: str,
    model: str,
    *,
    think: bool | None,
) -> tuple[str, float | None, float, int, float | None]:
    """Stream via native Ollama API; return text, ttft_ms, total_ms, eval_count, eval_duration_s."""
    payload: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "options": {"num_predict": MAX_TOKENS, "temperature": TEMPERATURE},
    }
    if think is not None:
        payload["think"] = think

    start = time.perf_counter()
    ttft_ms: float | None = None
    parts: list[str] = []
    eval_count = 0
    eval_duration_ns = 0

    with httpx.stream(
        "POST",
        OLLAMA_CHAT,
        json=payload,
        timeout=httpx.Timeout(300.0, connect=HEALTH_TIMEOUT),
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            message = chunk.get("message") or {}
            text = message.get("content") or ""
            if text:
                if ttft_ms is None:
                    ttft_ms = (time.perf_counter() - start) * 1000
                parts.append(text)
            if chunk.get("done"):
                eval_count = int(chunk.get("eval_count") or 0)
                eval_duration_ns = int(chunk.get("eval_duration") or 0)

    total_ms = (time.perf_counter() - start) * 1000
    eval_duration_s = eval_duration_ns / 1_000_000_000 if eval_duration_ns else None
    return "".join(parts).strip(), ttft_ms, total_ms, eval_count, eval_duration_s


def _openai_stream(prompt: str, model: str) -> tuple[str, float | None, float]:
    client = make_client()
    start = time.perf_counter()
    ttft_ms: float | None = None
    parts: list[str] = []

    stream = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        stream=True,
    )
    for event in stream:
        delta = event.choices[0].delta.content if event.choices else None
        if not delta:
            continue
        if ttft_ms is None:
            ttft_ms = (time.perf_counter() - start) * 1000
        parts.append(delta)

    total_ms = (time.perf_counter() - start) * 1000
    return "".join(parts).strip(), ttft_ms, total_ms


def chat(prompt: str, model: str) -> str:
    if _use_native_chat(model):
        text, _, _, _, _ = _native_stream(prompt, model, think=_think_flag(model))
        return text
    text, _, _ = _openai_stream(prompt, model)
    return text


def benchmark_prompt(
    prompt: str,
    model: str,
    *,
    kind: str = "manual",
    route_reason: str = "manual",
) -> BenchmarkResult:
    start = time.perf_counter()
    try:
        if _use_native_chat(model):
            text, ttft_ms, total_ms, eval_count, eval_duration_s = _native_stream(
                prompt,
                model,
                think=_think_flag(model),
            )
            output_tokens = eval_count or _estimate_tokens(text)
            generation_ms = total_ms - (ttft_ms or 0.0)
            if eval_duration_s and eval_count:
                tokens_per_second = eval_count / eval_duration_s
            elif output_tokens and generation_ms > 0:
                tokens_per_second = output_tokens / (generation_ms / 1000)
            else:
                tokens_per_second = None
        else:
            text, ttft_ms, total_ms = _openai_stream(prompt, model)
            output_tokens = _estimate_tokens(text)
            generation_ms = total_ms - (ttft_ms or 0.0)
            tokens_per_second = (
                output_tokens / (generation_ms / 1000) if output_tokens and generation_ms > 0 else None
            )
    except Exception as exc:  # noqa: BLE001
        total_ms = (time.perf_counter() - start) * 1000
        return BenchmarkResult(
            model=model,
            prompt=prompt,
            route_reason=route_reason,
            kind=kind,
            ttft_ms=None,
            generation_ms=total_ms,
            total_ms=total_ms,
            output_tokens=0,
            tokens_per_second=None,
            preview="",
            error=str(exc),
        )

    return BenchmarkResult(
        model=model,
        prompt=prompt,
        route_reason=route_reason,
        kind=kind,
        ttft_ms=ttft_ms,
        generation_ms=generation_ms,
        total_ms=total_ms,
        output_tokens=output_tokens,
        tokens_per_second=tokens_per_second,
        preview=text[:200],
    )


def routed_chat(prompt: str) -> tuple[str, RouteDecision]:
    decision = route_prompt(prompt)
    return chat(prompt, decision.model), decision


def routed_benchmark(prompt: str) -> BenchmarkResult:
    decision = route_prompt(prompt)
    return benchmark_prompt(
        prompt,
        decision.model,
        kind=decision.kind.value,
        route_reason=decision.reason,
    )


def run_benchmark_suite() -> list[BenchmarkResult]:
    ensure_ollama_ready([MODEL_FAST, MODEL_HEAVY])
    warmup = benchmark_prompt("Reply: ready", MODEL_FAST, kind="warmup", route_reason="warmup")

    simple = "Summarize in two sentences why running LLMs locally improves data privacy."
    complex_p = (
        "Write a Python function to parse a QuickBooks IIF export and flag rows "
        "where debits and credits do not balance. Explain the logic."
    )

    return [
        warmup,
        benchmark_prompt(simple, MODEL_FAST, kind="simple", route_reason="suite:8b"),
        benchmark_prompt(complex_p, MODEL_HEAVY, kind="complex", route_reason="suite:30b"),
        routed_benchmark(simple),
        routed_benchmark(complex_p),
    ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_bench_table(results: list[BenchmarkResult]) -> None:
    table = Table(title="Ollama Benchmark")
    table.add_column("Model")
    table.add_column("Kind")
    table.add_column("TTFT ms", justify="right")
    table.add_column("Gen ms", justify="right")
    table.add_column("Total ms", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Tok/s", justify="right")

    for r in results:
        if r.error:
            table.add_row(r.model, "ERROR", "-", "-", f"{r.total_ms:.0f}", "0", r.error[:36])
            continue
        table.add_row(
            r.model,
            r.kind,
            f"{r.ttft_ms:.1f}" if r.ttft_ms is not None else "-",
            f"{r.generation_ms:.1f}",
            f"{r.total_ms:.1f}",
            str(r.output_tokens),
            f"{r.tokens_per_second:.2f}" if r.tokens_per_second else "-",
        )
    console.print(table)


def cmd_health(_: argparse.Namespace) -> int:
    try:
        info = check_ollama_running()
        models = list_installed_models()
    except OllamaOfflineError as exc:
        console.print(f"[red]OFFLINE[/red] {exc}")
        return 1

    console.print(f"[green]ONLINE[/green] {OLLAMA_HEALTH}")
    console.print(f"version: {info.get('version', 'unknown')}")
    console.print(f"fast model: {MODEL_FAST}")
    console.print(f"heavy model: {MODEL_HEAVY} (native API, think={'on' if HEAVY_THINK_ENABLED else 'off'})")
    for name in models[:25]:
        console.print(f"  - {name}")
    if len(models) > 25:
        console.print(f"  ... +{len(models) - 25} more")
    return 0


def cmd_route(args: argparse.Namespace) -> int:
    force = TaskKind(args.force) if args.force else None
    decision = route_prompt(args.prompt, force=force)
    console.print_json(json.dumps(asdict(decision), default=lambda o: o.value if isinstance(o, Enum) else o))
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    try:
        ensure_ollama_ready()
    except OllamaOfflineError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1

    if args.model:
        console.print(chat(args.prompt, args.model))
        return 0

    text, decision = routed_chat(args.prompt)
    console.print(f"[dim]→ {decision.model} ({decision.reason})[/dim]")
    console.print(text)
    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    try:
        ensure_ollama_ready([MODEL_FAST, MODEL_HEAVY] if args.suite else None)
    except OllamaOfflineError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1

    if args.suite:
        results = run_benchmark_suite()
    elif args.model:
        results = [benchmark_prompt(args.prompt, args.model)]
    else:
        results = [routed_benchmark(args.prompt)]

    _print_bench_table(results)
    if args.json:
        console.print_json(json.dumps([asdict(r) for r in results]))
    return 1 if any(r.error for r in results) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Smart Ollama router + benchmark for Windows (port 11434)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="See module docstring for full Ollama setup commands.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="Check if Ollama Windows service is running")

    route = sub.add_parser("route", help="Show routing decision without inference")
    route.add_argument("prompt")
    route.add_argument("--force", choices=[k.value for k in TaskKind])

    chat_p = sub.add_parser("chat", help="Chat with automatic 8B/30B routing")
    chat_p.add_argument("prompt")
    chat_p.add_argument("--model", help="Override model tag")

    bench = sub.add_parser("bench", help="Measure TTFT, total time, and tokens/sec")
    bench.add_argument("prompt", nargs="?", default="Summarize local LLM benchmarking in one sentence.")
    bench.add_argument("--model", help="Benchmark a specific model")
    bench.add_argument("--suite", action="store_true", help="Run 8B, 30B, and routed benchmarks")
    bench.add_argument("--json", action="store_true", help="Print JSON results")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "health": cmd_health,
        "route": cmd_route,
        "chat": cmd_chat,
        "bench": cmd_bench,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
