"""Redacted NR2 support bundle for operator troubleshooting."""

from __future__ import annotations

import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automation_registry import list_automation_jobs
from integration_health import integration_health_snapshot

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
DATA_DIR = REPO_ROOT / "app_data" / "nr2"
OUTPUT_DIR = DATA_DIR / "support_bundles"

REDACTED_ENV_PREFIXES = (
    "PASSWORD",
    "SECRET",
    "TOKEN",
    "API_KEY",
    "APIKEY",
    "PRIVATE",
    "CREDENTIAL",
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _redact_env() -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in os.environ.items():
        upper = key.upper()
        if any(prefix in upper for prefix in REDACTED_ENV_PREFIXES):
            out[key] = "[REDACTED]"
        elif key.startswith("NR2_") or key.startswith("OLLAMA_") or key.startswith("SOFTDENT") or key.startswith("QB_"):
            out[key] = str(value)[:200]
    return out


def _safe_read_text(path: Path, limit: int = 120_000) -> str:
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if len(text) > limit:
        return text[:limit] + f"\n...[truncated at {limit} chars]..."
    return text


def _add_json(zip_file: zipfile.ZipFile, name: str, payload: Any) -> None:
    zip_file.writestr(name, json.dumps(payload, indent=2, ensure_ascii=False))


def build_support_bundle(store: Any | None = None, *, note: str = "") -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _utc_stamp()
    out_path = OUTPUT_DIR / f"nr2-support-{stamp}.zip"

    health = integration_health_snapshot(store, deep_diagnostics=True)
    automation = list_automation_jobs()

    manifest_path = ROOT / "import-manifest.json"
    bundle_path = DATA_DIR / "last_import_bundle.json"

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        _add_json(zf, "integration_health.json", health)
        _add_json(zf, "automation_registry.json", automation)
        _add_json(zf, "environment_redacted.json", _redact_env())
        _add_json(
            zf,
            "bundle_meta.json",
            {
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "note": note,
                "dataDir": str(DATA_DIR),
                "repoRoot": str(REPO_ROOT),
            },
        )
        if manifest_path.is_file():
            zf.writestr("import-manifest.json", _safe_read_text(manifest_path, 80_000))
        if bundle_path.is_file():
            zf.writestr("last_import_bundle.json", _safe_read_text(bundle_path, 80_000))
        diag_path = DATA_DIR / "import_diagnostics_last.json"
        if diag_path.is_file():
            zf.writestr("import_diagnostics_last.json", _safe_read_text(diag_path, 80_000))
        for rel in ("learned_memories.jsonl",):
            mem = DATA_DIR / rel
            if mem.is_file():
                zf.writestr(rel, _safe_read_text(mem, 40_000))

    return {
        "ok": True,
        "path": str(out_path),
        "filename": out_path.name,
        "sizeBytes": out_path.stat().st_size if out_path.is_file() else 0,
        "integrationStatus": health.get("status"),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }
