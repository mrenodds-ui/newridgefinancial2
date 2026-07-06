"""Predictive import healing — Moonshot employee morning-open workflow."""

from __future__ import annotations

import os
import time
from typing import Any


def heal_import_pipeline(*, force: bool = False) -> dict[str, Any]:
    """Retry imports when stale/degraded; surface operator hints."""
    from import_diagnostics import assess_import_readiness
    from import_loader import load_import_bundle

    steps: list[dict[str, Any]] = []
    try:
        bundle = load_import_bundle(sync=False, deep=False)
        readiness = assess_import_readiness()
        steps.append({"step": "assess", "level": readiness.get("level"), "ok": True})
    except Exception as exc:
        return {"ok": False, "error": str(exc), "steps": steps}

    level = str(readiness.get("level") or "unknown")
    if level in ("fresh",) and not force:
        return {
            "ok": True,
            "healed": False,
            "readiness": readiness,
            "steps": steps,
            "message": "Imports fresh — no heal needed.",
        }

    stall_min = int(os.environ.get("NR2_IMPORT_SYNC_STALL_MINUTES", "12") or 12)
    steps.append({"step": "stall_check", "stallMinutes": stall_min, "ok": True})

    try:
        from import_sync import sync_imports

        sync_result = sync_imports(full_pull=force or level in ("expired", "degraded"))
        steps.append({"step": "sync_imports", "ok": bool(sync_result.get("ok", True)), "detail": sync_result})
    except Exception as exc:
        steps.append({"step": "sync_imports", "ok": False, "error": str(exc)})

    time.sleep(0.5)
    try:
        load_import_bundle(sync=True, deep=True)
        readiness2 = assess_import_readiness()
        steps.append({"step": "reassess", "level": readiness2.get("level"), "ok": True})
    except Exception as exc:
        readiness2 = readiness
        steps.append({"step": "reassess", "ok": False, "error": str(exc)})

    hints: list[str] = []
    for ds in readiness2.get("datasets") or []:
        if isinstance(ds, dict) and ds.get("status") in ("stale", "missing", "failed"):
            detail = str(ds.get("detail") or ds.get("error") or "")
            if "locked" in detail.lower() or "permission" in detail.lower():
                hints.append(f"Close SoftDent/QuickBooks export lock for {ds.get('datasetKey')}")
            elif "column" in detail.lower() or "header" in detail.lower():
                hints.append(f"Verify CSV column headers for {ds.get('datasetKey')}")

    from pathlib import Path

    inbox = Path(__file__).resolve().parent.parent / "app_data" / "nr2" / "document_inbox"
    if inbox.is_dir():
        pending = list(inbox.glob("*.pdf")) + list(inbox.glob("*.tif"))
        if pending:
            hints.append(f"{len(pending)} document(s) in inbox — run document sync")

    healed = str(readiness2.get("level") or "") == "fresh" or (
        str(readiness2.get("level") or "") != level and str(readiness2.get("level") or "") in ("fresh", "syncing")
    )
    return {
        "ok": True,
        "healed": healed,
        "readinessBefore": readiness,
        "readinessAfter": readiness2,
        "steps": steps,
        "hints": hints,
        "message": "Import heal completed." if healed else "Import heal ran — manual steps may still be required.",
    }
