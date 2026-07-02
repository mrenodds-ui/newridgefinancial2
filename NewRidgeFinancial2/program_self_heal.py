"""Program self-heal — refresh imports, documents, practice exports, and report strength."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from integration_health import format_integration_health_text, integration_health_snapshot
from local_store import LocalStore

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "app_data" / "nr2"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _step(name: str, ok: bool, detail: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "ok": ok,
        "detail": detail,
        "payload": payload or {},
    }


def run_program_self_heal(
    store: LocalStore | None = None,
    *,
    full_pull: bool = False,
    reason: str = "manual",
    pull_imports: bool = True,
) -> dict[str, Any]:
    """Run a full local repair cycle without external writes."""
    store = store or LocalStore(DATA_DIR)
    started = _utc_now()
    steps: list[dict[str, Any]] = []
    warnings: list[str] = []

    if pull_imports:
        try:
            from sync_document_sources import sync_document_sources

            doc_sync = sync_document_sources(pull_imports=True, full_pull=full_pull)
            queue_count = doc_sync.get("queueCount")
            import_ok = True
            import_detail = f"imports refreshed; documents queue={queue_count}"
            import_warnings = doc_sync.get("warnings") if isinstance(doc_sync.get("warnings"), list) else []
            warnings.extend(str(w) for w in import_warnings)
            steps.append(_step("import-and-documents", import_ok, import_detail, {"queueCount": queue_count}))
        except Exception as exc:
            steps.append(_step("import-and-documents", False, str(exc)))
            warnings.append(f"Import/document sync failed: {exc}")
    else:
        try:
            from document_sync import sync_accounting_documents

            documents = sync_accounting_documents(store)
            queue_count = documents.get("queueCount") if isinstance(documents, dict) else 0
            steps.append(
                _step(
                    "documents",
                    True,
                    f"documents queue={queue_count}",
                    {"queueCount": queue_count},
                )
            )
            doc_warnings = documents.get("warnings") if isinstance(documents, dict) else None
            if isinstance(doc_warnings, list):
                warnings.extend(str(w) for w in doc_warnings)
        except Exception as exc:
            steps.append(_step("documents", False, str(exc)))

    try:
        from softdent_practice_exports import sync_practice_exports

        practice = sync_practice_exports()
        written = practice.get("written") if isinstance(practice, dict) else []
        steps.append(
            _step(
                "practice-exports",
                bool(practice.get("ok")),
                f"written={len(written) if isinstance(written, list) else 0}",
                practice if isinstance(practice, dict) else {},
            )
        )
    except Exception as exc:
        steps.append(_step("practice-exports", False, str(exc)))

    health = integration_health_snapshot(store, deep_diagnostics=True)
    health_text = format_integration_health_text(health)
    steps.append(
        _step(
            "integration-health",
            str(health.get("status") or "").lower() != "fail",
            f"{health.get('status', 'unknown').upper()} ({health.get('ok_count', 0)}/{health.get('enabled_count', 0)} OK)",
            {"status": health.get("status"), "ok_count": health.get("ok_count"), "enabled_count": health.get("enabled_count")},
        )
    )

    failed = [row for row in steps if not row.get("ok")]
    status = "ok" if not failed and str(health.get("status") or "").lower() == "ok" else (
        "degraded" if str(health.get("status") or "").lower() != "fail" else "fail"
    )

    return {
        "startedAt": started,
        "completedAt": _utc_now(),
        "reason": reason,
        "status": status,
        "steps": steps,
        "warnings": warnings,
        "health": health,
        "healthText": health_text,
        "summary": _format_self_heal_summary(status, steps, health),
    }


def _format_self_heal_summary(status: str, steps: list[dict[str, Any]], health: dict[str, Any]) -> str:
    lines = [
        f"Program self-heal: {status.upper()}",
        "",
        "Steps:",
    ]
    for row in steps:
        flag = "OK" if row.get("ok") else "FAIL"
        lines.append(f"- [{flag}] {row.get('name')}: {row.get('detail')}")
    lines.append("")
    lines.append(format_integration_health_text(health))
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Run NR2 program self-heal cycle.")
    parser.add_argument("--full-pull", action="store_true", help="Pull all upstream export periods.")
    parser.add_argument("--documents-only", action="store_true", help="Skip import pull; refresh documents only.")
    parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    args = parser.parse_args()
    report = run_program_self_heal(
        full_pull=bool(args.full_pull),
        pull_imports=not args.documents_only,
        reason="cli",
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(report.get("summary") or "")
    sys.exit(0 if str(report.get("status") or "").lower() != "fail" else 1)
