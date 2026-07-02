"""Run Gemma 2 HAL programming error review via Ollama."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROFILES_PATH = ROOT / "evals" / "local_model_profiles.json"
DEFAULT_CONTEXT = ROOT / "gemma2_hal_program_context.txt"
BUILD_SCRIPT = ROOT / "scripts" / "build_gemma2_hal_program_context.ps1"

PROFILE_ALIASES = {
    "9b": "gemma2_hal_9b",
    "27b": "gemma2_hal_27b",
}

USER_TEMPLATE = """Review HAL programming for errors in NewRidgeFinancial 2.0.

Focus areas:
1. Intent routing mismatches (hal-core.js vs validate-hal.mjs)
2. Agent loop / self-check gaps (hal-agent.js)
3. Widget contract violations (widget-contract.js vs hal-skills.js)
4. Route execution edge cases (hal-route-exec.js)
5. Model lane config vs runtime behavior (hal-models.json, app.js)

{context}

Deliver the structured programming error review. Prioritize confirmed bugs over style.
"""


def load_profiles() -> dict:
    return json.loads(PROFILES_PATH.read_text(encoding="utf-8"))


def resolve_profile(size: str) -> dict:
    config = load_profiles()
    alias = PROFILE_ALIASES.get(size.lower())
    if not alias:
        raise ValueError(f"Unknown size {size!r}. Use 9b or 27b.")
    profile = config.get("profiles", {}).get(alias)
    if not profile:
        raise RuntimeError(f"Profile {alias!r} missing from {PROFILES_PATH}")
    profile = dict(profile)
    profile["_alias"] = alias
    return profile


def load_system_prompt(profile: dict) -> str:
    rel = profile.get("system_prompt_path")
    if not rel:
        raise RuntimeError("Profile missing system_prompt_path")
    path = ROOT / rel
    return path.read_text(encoding="utf-8").strip()


def build_context(force: bool) -> Path:
    if DEFAULT_CONTEXT.is_file() and not force:
        return DEFAULT_CONTEXT
    if not BUILD_SCRIPT.is_file():
        raise RuntimeError(f"Missing context builder: {BUILD_SCRIPT}")
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BUILD_SCRIPT)],
        cwd=ROOT,
        check=True,
    )
    if not DEFAULT_CONTEXT.is_file():
        raise RuntimeError(f"Context builder did not create {DEFAULT_CONTEXT}")
    return DEFAULT_CONTEXT


def preflight(base_url: str, model: str) -> None:
    with urllib.request.urlopen(f"{base_url}/api/tags", timeout=15) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    names = {m.get("name") for m in body.get("models", [])}
    # Ollama tags may include :latest suffix variants
    if model not in names and f"{model}:latest" not in names:
        available = sorted(x for x in names if x)
        raise RuntimeError(
            f"Model {model!r} not available at {base_url}. "
            f"Run profile ollama_pull first. Have: {available[:16]}"
        )


def call_model(
    *,
    base_url: str,
    model: str,
    system: str,
    user_prompt: str,
    profile: dict,
    timeout_seconds: int,
) -> tuple[str, dict]:
    options: dict = {
        "temperature": profile.get("temperature", 0.1),
        "top_p": profile.get("top_p", 0.95),
        "num_predict": profile.get("num_predict", 4096),
    }
    if profile.get("num_ctx"):
        options["num_ctx"] = profile["num_ctx"]
    if profile.get("seed") is not None:
        options["seed"] = profile["seed"]

    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": options,
    }
    keep_alive = profile.get("keep_alive")
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive

    req = urllib.request.Request(
        f"{base_url}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = (body.get("message", {}).get("content") or "").strip()
    return content or "(empty response)", body


def validate_answer(answer: str) -> list[str]:
    errors: list[str] = []
    lowered = answer.lower()
    if not answer or answer == "(empty response)":
        errors.append("empty model response")
    if "finding" not in lowered and "severity" not in lowered:
        errors.append("missing Finding/Severity structure")
    if "executive summary" not in lowered and "executive" not in lowered and "summary" not in lowered:
        if "finding 1" not in lowered and "### finding" not in lowered:
            errors.append("missing review structure (summary or findings)")
    return errors


def report_stem(size: str) -> str:
    return f"gemma2_hal_program_{size.lower()}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Gemma 2 HAL programming error review.")
    parser.add_argument("--size", choices=["9b", "27b"], default=os.getenv("GEMMA2_HAL_SIZE", "9b"))
    parser.add_argument("--base-url", default=os.getenv("GEMMA2_HAL_OLLAMA_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--context", type=Path, default=DEFAULT_CONTEXT)
    parser.add_argument("--rebuild-context", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    profile = resolve_profile(args.size)
    model = profile["model"]
    timeout = int(profile.get("timeout_seconds", 300))
    system = load_system_prompt(profile)

    context_path = build_context(force=args.rebuild_context) if args.context == DEFAULT_CONTEXT else args.context
    if not context_path.is_file():
        print(f"Missing context: {context_path}", file=sys.stderr)
        return 1

    context = context_path.read_text(encoding="utf-8", errors="replace")
    user_prompt = USER_TEMPLATE.format(context=context)

    if args.dry_run:
        print(json.dumps({
            "profile": profile["_alias"],
            "model": model,
            "base_url": args.base_url,
            "context_file": str(context_path),
            "context_chars": len(context),
            "system_chars": len(system),
        }, indent=2))
        return 0

    preflight(args.base_url.rstrip("/"), model)
    print(f"Calling {model} at {args.base_url}...", flush=True)
    answer, raw = call_model(
        base_url=args.base_url.rstrip("/"),
        model=model,
        system=system,
        user_prompt=user_prompt,
        profile=profile,
        timeout_seconds=timeout,
    )

    validation_errors = validate_answer(answer)
    if validation_errors:
        print(f"Validation: {', '.join(validation_errors)} — retrying with format reminder...", flush=True)
        retry_prompt = (
            f"{user_prompt}\n\n"
            "Rewrite using the required markdown sections and ### Finding N blocks with **Severity:** lines."
        )
        answer, raw = call_model(
            base_url=args.base_url.rstrip("/"),
            model=model,
            system=system,
            user_prompt=retry_prompt,
            profile=profile,
            timeout_seconds=timeout,
        )
        validation_errors = validate_answer(answer)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    stem = report_stem(args.size)
    report_path = ROOT / f"{stem}_report.md"
    raw_path = ROOT / f"{stem}_raw.json"

    validation_note = "OK" if not validation_errors else ", ".join(validation_errors)
    report = (
        f"# HAL Programming Review — Gemma 2 {args.size.upper()}\n\n"
        f"**Model:** `{model}`  \n"
        f"**Endpoint:** `{args.base_url}`  \n"
        f"**Generated:** {stamp}  \n"
        f"**Context:** `{context_path.name}` ({len(context)} chars)  \n"
        f"**Validation:** {validation_note}\n\n"
        f"---\n\n"
        f"{answer}\n"
    )
    report_path.write_text(report, encoding="utf-8")
    raw_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    print(f"Wrote {report_path}")
    if validation_errors:
        print(f"Warning: {', '.join(validation_errors)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
