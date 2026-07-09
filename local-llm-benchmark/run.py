#!/usr/bin/env python3
"""CLI for local LLM health checks, routed chat, and benchmarking."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from local_llm_benchmark.client import LocalLLMClient, run_benchmark_suite
from local_llm_benchmark.config import load_settings
from local_llm_benchmark.router import TaskComplexity, route_prompt
from local_llm_benchmark.server import ServerUnavailableError, check_server, ensure_server_ready

console = Console()


def _load_env() -> None:
    project_root = Path(__file__).resolve().parent
    load_dotenv(project_root / ".env")


def cmd_health(_: argparse.Namespace) -> int:
    settings = load_settings()
    try:
        status = check_server(settings)
    except ServerUnavailableError as exc:
        console.print(f"[red]OFFLINE[/red] {exc}")
        return 1

    console.print(f"[green]ONLINE[/green] backend={status.backend} url={status.health_url}")
    if status.version:
        console.print(f"version: {status.version}")
    if status.installed_models:
        console.print("models:")
        for name in status.installed_models[:20]:
            console.print(f"  - {name}")
        if len(status.installed_models) > 20:
            console.print(f"  ... and {len(status.installed_models) - 20} more")
    return 0


def cmd_route(args: argparse.Namespace) -> int:
    settings = load_settings()
    force = TaskComplexity(args.force) if args.force else None
    decision = route_prompt(args.prompt, settings, force=force)
    console.print(json.dumps({
        "complexity": decision.complexity.value,
        "model": decision.model,
        "reason": decision.reason,
    }, indent=2))
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    settings = load_settings()
    try:
        ensure_server_ready(settings)
    except ServerUnavailableError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1

    client = LocalLLMClient(settings)
    if args.model:
        text = client.chat(args.prompt, model=args.model)
        console.print(text)
        return 0

    text, decision = client.routed_chat(args.prompt)
    console.print(f"[dim]routed -> {decision.model} ({decision.reason})[/dim]")
    console.print(text)
    return 0


def _print_benchmark_table(results: list) -> None:
    table = Table(title="Benchmark Results")
    table.add_column("Model")
    table.add_column("Route")
    table.add_column("TTFT (ms)", justify="right")
    table.add_column("Gen (ms)", justify="right")
    table.add_column("Total (ms)", justify="right")
    table.add_column("Tok", justify="right")
    table.add_column("Tok/s", justify="right")

    for result in results:
        if result.error:
            table.add_row(result.model, "ERROR", "-", "-", f"{result.total_ms:.0f}", "0", result.error[:40])
            continue
        table.add_row(
            result.model,
            result.complexity,
            f"{result.ttft_ms:.1f}" if result.ttft_ms is not None else "-",
            f"{result.generation_ms:.1f}",
            f"{result.total_ms:.1f}",
            str(result.output_tokens),
            f"{result.tokens_per_second:.2f}" if result.tokens_per_second is not None else "-",
        )
    console.print(table)


def cmd_bench(args: argparse.Namespace) -> int:
    settings = load_settings()
    try:
        ensure_server_ready(settings, [settings.model_fast, settings.model_heavy] if args.suite else None)
    except ServerUnavailableError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1

    client = LocalLLMClient(settings)

    if args.suite:
        results = run_benchmark_suite(settings)
        _print_benchmark_table(results)
        if args.json:
            console.print_json(data=[r.to_dict() for r in results])
        return 0

    if args.model:
        result = client.benchmark(args.prompt, model=args.model)
    else:
        result = client.routed_benchmark(args.prompt)

    _print_benchmark_table([result])
    if args.json:
        console.print_json(data=result.to_dict())
    if result.error:
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark and route prompts across local LLMs")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="Verify the inference server is reachable")

    route = sub.add_parser("route", help="Show routing decision without calling a model")
    route.add_argument("prompt")
    route.add_argument("--force", choices=[c.value for c in TaskComplexity])

    chat = sub.add_parser("chat", help="Send a prompt using automatic routing")
    chat.add_argument("prompt")
    chat.add_argument("--model", help="Override routed model")

    bench = sub.add_parser("bench", help="Benchmark latency and throughput")
    bench.add_argument("prompt", nargs="?", default="Summarize local LLM benchmarking in one sentence.")
    bench.add_argument("--model", help="Benchmark a specific model tag")
    bench.add_argument("--suite", action="store_true", help="Run fast/heavy + routed benchmark suite")
    bench.add_argument("--json", action="store_true", help="Also print JSON output")

    return parser


def main(argv: list[str] | None = None) -> int:
    _load_env()
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "health": cmd_health,
        "route": cmd_route,
        "chat": cmd_chat,
        "bench": cmd_bench,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
