"""Integration health snapshot for NR2 — imports, automations, AI, documents."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automation_registry import list_automation_jobs
from import_diagnostics import (
    STATUS_CONNECTED,
    STATUS_MISSING,
    STATUS_STALE,
    blocking_import_issues,
    evaluate_bundle,
)
from import_loader import load_import_bundle

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "app_data" / "nr2"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _probe_ollama(endpoint: str = "http://127.0.0.1:11434/api/tags", timeout: float = 3.0) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(endpoint, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        models = [m.get("name") for m in body.get("models", []) if m.get("name")]
        return {"ok": True, "endpoint": endpoint.replace("/api/tags", ""), "modelCount": len(models), "models": models[:12]}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {"ok": False, "endpoint": endpoint.replace("/api/tags", ""), "error": str(exc)}


def _document_queue_count(store: Any | None, *, heal: bool = False) -> dict[str, Any]:
    if store is None:
        try:
            from local_store import LocalStore

            store = LocalStore(DATA_DIR)
        except Exception as exc:
            return {"ok": False, "count": 0, "error": str(exc)}
    try:
        raw = store.get("nr2:v2:documents")
        if not raw:
            if heal:
                return _heal_document_queue(store)
            return {"ok": True, "count": 0}
        payload = json.loads(raw)
        queue = payload.get("queue") if isinstance(payload, dict) else []
        count = len(queue) if isinstance(queue, list) else 0
        if count == 0 and heal:
            return _heal_document_queue(store)
        return {"ok": True, "count": count}
    except Exception as exc:
        return {"ok": False, "count": 0, "error": str(exc)}


def _heal_document_queue(store: Any) -> dict[str, Any]:
    try:
        from document_sync import sync_accounting_documents

        result = sync_accounting_documents(store)
        count = int(result.get("queueCount") or 0) if isinstance(result, dict) else 0
        return {"ok": True, "count": count, "healed": True}
    except Exception as exc:
        return {"ok": False, "count": 0, "error": str(exc), "healed": False}


def _posting_queue_count(db_path: Path | None) -> dict[str, Any]:
    if not db_path or not db_path.is_file():
        return {"ok": False, "count": 0, "error": "no_db"}
    try:
        from accounting_bridge import list_posting_queue

        payload = list_posting_queue(db_path, limit=50)
        items = payload.get("items") if isinstance(payload, dict) else []
        return {"ok": True, "count": len(items) if isinstance(items, list) else 0, "metrics": payload.get("metrics")}
    except Exception as exc:
        return {"ok": False, "count": 0, "error": str(exc)}


def _integration_row(
    *,
    integration_id: str,
    label: str,
    ok: bool,
    status: str,
    detail: str,
    action_hint: str = "",
) -> dict[str, Any]:
    return {
        "id": integration_id,
        "label": label,
        "ok": ok,
        "status": status,
        "detail": detail,
        "actionHint": action_hint,
    }


def integration_health_snapshot(
    store: Any | None = None,
    *,
    bundle: dict[str, Any] | None = None,
    sync_state: dict[str, Any] | None = None,
    deep_diagnostics: bool = False,
) -> dict[str, Any]:
    bundle = bundle or load_import_bundle(sync=False, deep=deep_diagnostics)
    diagnostics = bundle.get("diagnostics")
    if not diagnostics:
        diagnostics = evaluate_bundle(bundle, deep=deep_diagnostics)
        bundle["diagnostics"] = diagnostics

    summary = diagnostics.get("summary") if isinstance(diagnostics, dict) else {}
    integrations: list[dict[str, Any]] = []

    stale = int(summary.get("stale") or 0)
    missing = int(summary.get("missing") or 0)
    partial = int(summary.get("partial") or 0)
    connected = int(summary.get("connected") or 0)
    blocking = blocking_import_issues(diagnostics)
    imports_ok = not blocking
    import_status = "ok" if imports_ok else ("degraded" if connected > 0 else "fail")
    import_detail = (
        f"{connected} connected, {partial} partial, {stale} stale, {missing} missing."
    )
    optional_missing = int(summary.get("missingOptional") or 0)
    if optional_missing:
        import_detail = f"{import_detail} {optional_missing} optional export(s) not loaded."
    top_issues: list[str] = []
    for row in diagnostics.get("datasets") or []:
        if not isinstance(row, dict):
            continue
        severity = str(row.get("severity") or "warning")
        if severity == "optional" and row.get("status") == STATUS_MISSING:
            continue
        if row.get("status") in {STATUS_STALE, STATUS_MISSING} or (
            row.get("status") != STATUS_CONNECTED and severity == "critical"
        ):
            hint = row.get("collectorHint") or row.get("detail") or row.get("datasetKey")
            top_issues.append(f"{row.get('datasetKey')}: {hint}")
    if top_issues:
        import_detail = f"{import_detail} Issues: {'; '.join(top_issues[:4])}."
    integrations.append(
        _integration_row(
            integration_id="imports",
            label="SoftDent / QuickBooks imports",
            ok=imports_ok,
            status=import_status,
            detail=import_detail,
            action_hint="Run import sync or Verify-HAL-Readiness.ps1 when stale or missing.",
        )
    )

    sync = sync_state or bundle.get("syncStatus") or {}
    if sync.get("attempted"):
        sync_ok = bool(sync.get("ok"))
        integrations.append(
            _integration_row(
                integration_id="import-sync",
                label="Last import refresh",
                ok=sync_ok,
                status="ok" if sync_ok else "fail",
                detail=str(sync.get("error") or "Last refresh succeeded."),
                action_hint="Use Refresh imports in HAL or Sync-HAL-Imports.ps1.",
            )
        )

    ollama = _probe_ollama()
    integrations.append(
        _integration_row(
            integration_id="ollama",
            label="Local AI (Ollama)",
            ok=bool(ollama.get("ok")),
            status="ok" if ollama.get("ok") else "fail",
            detail=(
                f"{ollama.get('modelCount', 0)} models reachable."
                if ollama.get("ok")
                else str(ollama.get("error") or "Unreachable")
            ),
            action_hint="Start ollama.exe serve and verify hal-chat:8b is loaded.",
        )
    )

    if store is None:
        try:
            from local_store import LocalStore

            store = LocalStore(DATA_DIR)
        except Exception:
            store = None

    docs = _document_queue_count(store, heal=deep_diagnostics)
    posting = _posting_queue_count(Path(getattr(store, "db_path", DATA_DIR / "nr2.sqlite3")) if store else DATA_DIR / "nr2.sqlite3")
    doc_count = int(docs.get("count") or 0)
    posting_count = int(posting.get("count") or 0)
    docs_ok = doc_count > 0 or posting_count > 0
    docs_status = "ok" if doc_count > 0 else ("degraded" if posting_count > 0 else "fail")
    if doc_count == 0 and posting_count > 0:
        docs_detail = f"0 document(s) in intake queue; {posting_count} journal queue item(s) seeded from imports."
    else:
        docs_detail = f"{doc_count} document(s) in local queue."
        if docs.get("healed"):
            docs_detail += " (auto-synced during health check)"
    integrations.append(
        _integration_row(
            integration_id="documents",
            label="Documents queue",
            ok=docs_ok,
            status=docs_status,
            detail=docs_detail,
            action_hint="Run document sync or program self-heal when the queue is empty but imports exist.",
        )
    )

    db_path = getattr(store, "db_path", None) if store else DATA_DIR / "nr2.sqlite3"
    if db_path and not Path(db_path).is_file():
        db_path = DATA_DIR / "nr2.sqlite3"
    if not posting_count:
        posting = _posting_queue_count(Path(db_path) if db_path else None)
        posting_count = int(posting.get("count") or 0)
    integrations.append(
        _integration_row(
            integration_id="posting-queue",
            label="Journal posting queue",
            ok=bool(posting.get("ok")),
            status="ok" if posting.get("ok") else "degraded",
            detail=f"{posting_count} posting queue item(s).",
            action_hint="Review posting queue before month-end close.",
        )
    )

    automation = list_automation_jobs()
    auto_failed = int((automation.get("summary") or {}).get("failed") or 0)
    integrations.append(
        _integration_row(
            integration_id="automations",
            label="Scheduled automations",
            ok=auto_failed == 0,
            status="ok" if auto_failed == 0 else "degraded",
            detail=(
                f"{automation['summary']['total']} jobs registered; "
                f"{automation['summary']['ok']} last OK, {auto_failed} last failed."
            ),
            action_hint="Check automation_runs.json and re-run failed PowerShell sync tasks.",
        )
    )

    enabled_count = len(integrations)
    ok_count = sum(1 for row in integrations if row.get("ok"))
    fail_count = enabled_count - ok_count

    return {
        "generatedAt": _utc_now(),
        "enabled_count": enabled_count,
        "ok_count": ok_count,
        "fail_count": fail_count,
        "status": "ok" if fail_count == 0 else ("degraded" if ok_count > 0 else "fail"),
        "integrations": integrations,
        "importDiagnostics": diagnostics,
        "ollama": ollama,
        "automation": automation,
        "upstreamHealth": bundle.get("upstreamHealth"),
    }


def format_integration_health_text(snapshot: dict[str, Any]) -> str:
    lines = [
        f"Integration health: {snapshot.get('status', 'unknown').upper()} "
        f"({snapshot.get('ok_count', 0)}/{snapshot.get('enabled_count', 0)} OK).",
        "",
    ]
    for row in snapshot.get("integrations") or []:
        flag = "OK" if row.get("ok") else row.get("status", "FAIL").upper()
        lines.append(f"- {row.get('label')}: {flag} — {row.get('detail')}")
        if not row.get("ok") and row.get("actionHint"):
            lines.append(f"  Next: {row.get('actionHint')}")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Print NR2 integration health snapshot.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args()
    snapshot = integration_health_snapshot(deep_diagnostics=True)
    if args.json:
        print(json.dumps(snapshot, indent=2))
    else:
        print(format_integration_health_text(snapshot))
    fail_count = int(snapshot.get("fail_count") or 0)
    status = str(snapshot.get("status") or "").lower()
    sys.exit(1 if status == "fail" else 0)
