"""Run one NR2 audit section with dual-model pass: 120B draft + 70B review."""
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from run_235b_eval_section import (  # noqa: E402
    BACKEND_URL,
    FRONTEND_URL,
    MICRO_SECTIONS,
    SECTION_META,
    SECTION_PROMPTS,
    SETUP_GUIDE_MARKERS,
    SLICE_SECTIONS,
    context_limit_for,
    lane_reachable,
    pick_context,
    scope_from_context,
    truncate,
)

EVAL_HOST = os.getenv("NR2_EVAL_OLLAMA_HOST", "127.0.0.1:11438")
EVAL_URL = f"http://{EVAL_HOST}"
PRIMARY_MODEL = os.getenv("NR2_EVAL_PRIMARY_MODEL", "gpt-oss:120b")
SECONDARY_MODEL = os.getenv("NR2_EVAL_SECONDARY_MODEL", "llama3.3:latest")
TIMEOUT_SECONDS = 3600
MICRO_TOKENS_PRIMARY = 2560
MICRO_TOKENS_SECONDARY = 2048
SLICE_TOKENS_PRIMARY = 1536
SLICE_TOKENS_SECONDARY = 1280

PRIMARY_SYSTEM = (
    "Senior backend auditor. Evidence-based only. Never invent files. "
    "Draft 2-5 audit findings from the code. Each finding: Title, Severity, Files, Evidence, Fix, Test. "
    "Plain markdown bullets are fine. No setup guides."
)

SECONDARY_SYSTEM = (
    "Senior reviewer. You receive draft audit notes plus code context. "
    "Output ONLY finalized findings using this structure:\n"
    "### Finding N: <title>\n"
    "- **Severity:** Critical|High|Medium|Low\n"
    "- **Files/functions:** ...\n"
    "- **Evidence:** ...\n"
    "- **Recommended narrow fix:** ...\n"
    "- **Test to add or run:** ...\n"
    "Drop speculative items. No chain-of-thought. End with "
    "**Code changes recommended now:** yes|no — <one sentence>."
)


def verify_dual_lane_isolation(isolated: bool) -> dict[str, bool]:
    frontend_up = lane_reachable(FRONTEND_URL)
    backend_up = lane_reachable(BACKEND_URL)
    evaluator_up = eval_lane_up()
    if isolated:
        if frontend_up or backend_up:
            raise RuntimeError(
                "Normal lanes must be stopped before dual-model evaluation. "
                f":11434 up={frontend_up}, :11435 up={backend_up}"
            )
        if not evaluator_up:
            raise RuntimeError(f"Eval lane unreachable at {EVAL_URL}")
    return {
        "normal_lanes_stopped": not frontend_up and not backend_up,
        "only_235b_running": evaluator_up and not frontend_up and not backend_up,
        "evaluator_up": evaluator_up,
    }


def report_name(key: str) -> str:
    return f"eval_section{key}_120b_70b_report.md"


def eval_lane_up(timeout: float = 5.0) -> bool:
    return lane_reachable(EVAL_URL, timeout=timeout)


def preflight_models() -> None:
    with urllib.request.urlopen(f"{EVAL_URL}/v1/models", timeout=15) as resp:
        models = json.loads(resp.read().decode("utf-8"))
    ids = {item.get("id") for item in models.get("data", [])}
    missing = [m for m in (PRIMARY_MODEL, SECONDARY_MODEL) if m not in ids]
    if missing:
        raise RuntimeError(f"Missing models on {EVAL_URL}: {missing}. Available sample: {sorted(x for x in ids if x)[:12]}")


def call_ollama(*, model: str, system: str, user_prompt: str, max_tokens: int, think: bool = False) -> tuple[str, dict]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "think": think,
        "options": {"temperature": 0.1, "num_predict": max_tokens},
    }
    req = urllib.request.Request(
        f"{EVAL_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = (body.get("message", {}).get("content") or "").strip()
    return content or "(empty response)", body


def unload_model(model: str) -> None:
    env = os.environ.copy()
    env["OLLAMA_HOST"] = EVAL_HOST
    subprocess.run(
        ["ollama", "stop", model],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def validate_answer(answer: str) -> list[str]:
    errors: list[str] = []
    lowered = answer.lower()
    if not answer or answer == "(empty response)":
        errors.append("empty model response")
    if "severity" not in lowered and "**severity:**" not in lowered:
        errors.append("missing Severity labels in findings")
    if "finding 1" not in lowered and "### finding" not in lowered:
        errors.append("missing numbered Finding sections")
    if any(marker in lowered for marker in SETUP_GUIDE_MARKERS):
        errors.append("looks like a setup guide, not an audit")
    return errors


def build_dual_report(
    *,
    meta: dict,
    context_path: Path,
    lane_state: dict[str, bool],
    primary_draft: str,
    final_answer: str,
    validation_errors: list[str],
) -> str:
    now = datetime.now(timezone.utc).isoformat()
    title = str(meta["title"])
    scope = scope_from_context(context_path)
    stopped = "yes" if lane_state.get("normal_lanes_stopped") else "no"
    credible_note = "See reviewed findings below." if not validation_errors else f"Validation issues: {', '.join(validation_errors)}"

    return f"""# {title}

## Section metadata

- Generated (UTC): {now}
- Primary model (draft): `{PRIMARY_MODEL}` @ `{EVAL_URL}`
- Review model (final): `{SECONDARY_MODEL}` @ `{EVAL_URL}`
- Context file: `{context_path.name}`
- 24B/30B stopped before run: {stopped}
- Eval lane: `{EVAL_HOST}`

## Scope/files reviewed

{scope}

## Primary pass ({PRIMARY_MODEL}) — draft

{primary_draft}

## Review pass ({SECONDARY_MODEL}) — final findings

{final_answer}

## Credible vs low-confidence findings

{credible_note}

## Whether code changes are recommended now

See final findings above.

---
*Dual-model sectional audit (120B + 70B) — local artifact, do not commit unless approved.*
"""


def run_section(key: str, *, isolated: bool, overwrite: bool) -> int:
    meta = dict(SECTION_META[key])
    meta["report"] = report_name(key)
    meta["title"] = f"{meta['title']} (120B draft + 70B review)"

    report_path = ROOT / report_name(key)
    primary_raw_path = ROOT / f"eval_section{key}_120b.raw.json"
    secondary_raw_path = ROOT / f"eval_section{key}_70b.raw.json"

    if report_path.exists() and not overwrite:
        raise FileExistsError(f"Report already exists: {report_path}. Pass --overwrite.")

    if not eval_lane_up():
        raise RuntimeError(f"Eval lane unreachable at {EVAL_URL}")

    print("Lane isolation check...", flush=True)
    lane_state = verify_dual_lane_isolation(isolated)

    print("Model preflight...", flush=True)
    preflight_models()

    context_path, context_raw = pick_context(
        Path(str(meta["focus"])),
        Path(str(meta["fallback"])) if meta.get("fallback") else None,
    )
    context_limit = context_limit_for(key)
    context = truncate(context_raw, context_limit)
    print(f"Context: {context_path.name} ({len(context)} chars)", flush=True)

    section_prompt = SECTION_PROMPTS[key]
    if key in SLICE_SECTIONS:
        finding_cap = "Draft 2-3 findings max."
        primary_tokens = SLICE_TOKENS_PRIMARY
        secondary_tokens = SLICE_TOKENS_SECONDARY
    else:
        finding_cap = "Draft 2-5 findings max."
        primary_tokens = MICRO_TOKENS_PRIMARY
        secondary_tokens = MICRO_TOKENS_SECONDARY
    primary_prompt = (
        f"{section_prompt}\n\n"
        f"{finding_cap} Audit only.\n\n"
        f"--- CODE ---\n{context}\n--- END ---"
    )

    print(f"[1/2] Primary draft with {PRIMARY_MODEL}...", flush=True)
    primary_draft, primary_raw = call_ollama(
        model=PRIMARY_MODEL,
        system=PRIMARY_SYSTEM,
        user_prompt=primary_prompt,
        max_tokens=primary_tokens,
    )
    primary_raw_path.write_text(json.dumps(primary_raw, indent=2), encoding="utf-8")
    print(f"Primary draft: {len(primary_draft)} chars", flush=True)

    print(f"Unloading {PRIMARY_MODEL}...", flush=True)
    unload_model(PRIMARY_MODEL)

    review_prompt = (
        f"Section scope:\n{section_prompt}\n\n"
        f"Draft audit from {PRIMARY_MODEL}:\n{primary_draft}\n\n"
        f"Rewrite into {finding_cap.replace('Draft ', '')} with Severity labels. Use only evidence from the code below.\n\n"
        f"--- CODE ---\n{context}\n--- END ---"
    )

    print(f"[2/2] Review with {SECONDARY_MODEL}...", flush=True)
    final_answer, secondary_raw = call_ollama(
        model=SECONDARY_MODEL,
        system=SECONDARY_SYSTEM,
        user_prompt=review_prompt,
        max_tokens=secondary_tokens,
    )
    secondary_raw_path.write_text(json.dumps(secondary_raw, indent=2), encoding="utf-8")

    validation_errors = validate_answer(final_answer)
    if validation_errors:
        print(f"Validation: {', '.join(validation_errors)} — retrying review...", flush=True)
        retry_prompt = (
            f"{review_prompt}\n\n"
            "Rewrite using ONLY ### Finding N blocks with **Severity:** lines. No reasoning."
        )
        final_answer, secondary_raw = call_ollama(
            model=SECONDARY_MODEL,
            system=SECONDARY_SYSTEM,
            user_prompt=retry_prompt,
            max_tokens=secondary_tokens,
        )
        secondary_raw_path.write_text(json.dumps(secondary_raw, indent=2), encoding="utf-8")
        validation_errors = validate_answer(final_answer)

    if validation_errors:
        print(f"Warning: {', '.join(validation_errors)}", flush=True)

    report = build_dual_report(
        meta=meta,
        context_path=context_path,
        lane_state=lane_state,
        primary_draft=primary_draft,
        final_answer=final_answer,
        validation_errors=validation_errors,
    )
    report_path.write_text(report, encoding="utf-8")
    print(f"Report saved: {report_path}", flush=True)
    unload_model(SECONDARY_MODEL)
    return 1 if validation_errors and "empty model response" in validation_errors[0] else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one dual-model (120B+70B) NR2 audit section.")
    parser.add_argument("section", choices=sorted(SECTION_META.keys()))
    parser.add_argument("--isolated", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        return run_section(args.section, isolated=args.isolated, overwrite=args.overwrite)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
