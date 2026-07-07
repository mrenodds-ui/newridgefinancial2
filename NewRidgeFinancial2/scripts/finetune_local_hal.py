#!/usr/bin/env python3
"""Local HAL fine-tune stub — Moonshot Phase 2C (opt-in anonymized learning not enabled by default)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models" / "hal"


def main() -> int:
    parser = argparse.ArgumentParser(description="NR2 local HAL fine-tune stub (2C)")
    parser.add_argument("--dataset", type=Path, help="JSONL training snippets (sanitized, no PHI)")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs only")
    args = parser.parse_args()

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "ok": True,
        "phase": "2C_stub",
        "trained": False,
        "note": "Anonymized cross-practice learning is opt-in and disabled by default.",
        "evaluatedAt": datetime.now(timezone.utc).isoformat(),
        "dataset": str(args.dataset) if args.dataset else None,
    }
    if args.dataset and args.dataset.is_file():
        lines = [ln for ln in args.dataset.read_text(encoding="utf-8").splitlines() if ln.strip()]
        report["sampleCount"] = len(lines)
    else:
        report["sampleCount"] = 0
        report["warning"] = "Provide --dataset with sanitized JSONL to prepare a future local run."

    out = MODELS_DIR / "finetune_last_run.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
