"""Run all focused validation slices and persist a combined summary."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path


COMMANDS = [
    {
        "key": "softdentPeriodSync",
        "label": "SoftDent period sync slice",
        "argv": [sys.executable, "scripts/validate_softdent_period_sync_slice.py"],
        "artifact": "softdent_period_sync_slice_validation.json",
    },
    {
        "key": "importDocumentHonesty",
        "label": "Import document honesty slice",
        "argv": ["node", "scripts/validate_import_document_honesty_slice.mjs"],
        "artifact": "import_document_honesty_slice_validation.json",
    },
    {
        "key": "importCache",
        "label": "Import cache slice",
        "argv": [sys.executable, "scripts/validate_import_cache_slice.py"],
        "artifact": "import_cache_slice_validation.json",
    },
    {
        "key": "importManifestChecksums",
        "label": "Import manifest/checksum slice",
        "argv": [sys.executable, "scripts/validate_import_manifest_checksum_slice.py"],
        "artifact": "import_manifest_checksum_slice_validation.json",
    },
]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    data_dir = repo_root / "data"
    output_path = data_dir / "focused_validator_summary.json"
    started_at = time.time()
    results: list[dict[str, object]] = []
    overall_ok = True

    for item in COMMANDS:
        started = time.time()
        try:
            proc = subprocess.run(
                item["argv"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=120,
            )
            artifact_path = data_dir / str(item["artifact"])
            artifact = None
            if artifact_path.exists():
                try:
                    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
                except Exception as exc:  # pragma: no cover - artifact parse fallback
                    artifact = {"ok": False, "errors": [{"test": "artifact-parse", "details": repr(exc)}]}
            ok = proc.returncode == 0 and bool(artifact and artifact.get("ok") is True)
            overall_ok = overall_ok and ok
            results.append(
                {
                    "key": item["key"],
                    "label": item["label"],
                    "ok": ok,
                    "exitCode": proc.returncode,
                    "durationSec": round(time.time() - started, 3),
                    "stdout": (proc.stdout or "").strip()[-1000:],
                    "stderr": (proc.stderr or "").strip()[-1000:],
                    "artifact": artifact,
                }
            )
        except Exception as exc:
            overall_ok = False
            results.append(
                {
                    "key": item["key"],
                    "label": item["label"],
                    "ok": False,
                    "exitCode": -1,
                    "durationSec": round(time.time() - started, 3),
                    "stdout": "",
                    "stderr": repr(exc),
                    "artifact": None,
                }
            )

    payload = {
        "ok": overall_ok,
        "checks": [
            {
                "key": item["key"],
                "label": item["label"],
                "ok": item["ok"],
                "exitCode": item["exitCode"],
                "durationSec": item["durationSec"],
            }
            for item in results
        ],
        "results": results,
        "testsRun": sum(int(((item.get("artifact") or {}).get("testsRun") or 0)) for item in results),
        "durationSec": round(time.time() - started_at, 3),
        "errors": [
            {
                "test": item["key"],
                "details": item.get("stderr") or f"exitCode={item.get('exitCode')}",
            }
            for item in results
            if not item["ok"]
        ],
    }
    data_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
