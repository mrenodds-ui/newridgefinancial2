#!/usr/bin/env python3
"""Phase 2 supervised pilot readiness checks."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _check(name: str, ok: bool, detail: str = "") -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail}


def run_checks() -> dict:
    checks: list[dict] = []

    from scripts.validate_production_readiness import run_checks as prod_checks

    prod = prod_checks()
    checks.append(_check("production_readiness", bool(prod.get("ok")), f"{prod.get('passed')}/{prod.get('total')}"))
    if not prod.get("ok"):
        for item in prod.get("checks") or []:
            if item.get("name") in {"qbo_configured", "twilio_configured"}:
                continue
            if not item.get("ok"):
                checks.append(_check(f"prod:{item.get('name')}", False, str(item.get("detail") or "")))

    role_path = REPO_ROOT / "app_data" / "nr2" / "workstation_role.json"
    if role_path.is_file():
        try:
            role = json.loads(role_path.read_text(encoding="utf-8")).get("role")
            checks.append(_check("workstation_role", bool(role), str(role or "")))
        except json.JSONDecodeError:
            checks.append(_check("workstation_role", False, "invalid json"))
    else:
        checks.append(_check("workstation_role", False, "copy docs/examples/workstation_role.json.example"))

    from local_store import LocalStore

    store = LocalStore(REPO_ROOT / "app_data" / "nr2")
    try:
        from posting_queue_store import PostingQueueStore

        pq = PostingQueueStore(store.db_path)
        entries = pq.list_entries(limit=1)
        checks.append(_check("posting_queue_encrypted_db", True, f"readable ({len(entries)} sample)"))
    except Exception as exc:
        checks.append(_check("posting_queue_encrypted_db", False, str(exc)[:120]))

    try:
        from document_sync import sync_accounting_documents

        sync = sync_accounting_documents(store)
        checks.append(_check("document_sync", True, f"queue={sync.get('queueCount', 0)}"))
    except Exception as exc:
        checks.append(_check("document_sync", False, str(exc)[:120]))

    try:
        from hal_employee_workflows import list_pending_era_matches

        era = list_pending_era_matches(store, limit=5)
        checks.append(_check("era_match_api", bool(era.get("ok")), f"pending={era.get('count', 0)}"))
    except Exception as exc:
        checks.append(_check("era_match_api", False, str(exc)[:120]))

    import_task = os.environ.get("NR2_IMPORT_TASK_REGISTERED", "").strip()
    checks.append(
        _check(
            "import_automation",
            import_task.lower() in {"1", "true", "yes"} or _scheduled_task_exists(),
            "Register-HAL-Import-Automation.ps1" if not import_task else "env set",
        )
    )

    optional = {"import_automation"}
    required_ok = all(c["ok"] for c in checks if c["name"] not in optional)
    return {
        "ok": required_ok,
        "phase": "supervised_pilot",
        "passed": sum(1 for c in checks if c["ok"]),
        "total": len(checks),
        "checks": checks,
    }


def _scheduled_task_exists() -> bool:
    if sys.platform != "win32":
        return False
    import subprocess

    try:
        proc = subprocess.run(
            ["schtasks", "/Query", "/TN", "New Ridge HAL Import Sync", "/FO", "LIST"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return proc.returncode == 0
    except Exception:
        return False


def main() -> int:
    report = run_checks()
    print(json.dumps(report, indent=2))
    if not report.get("ok"):
        print("\nPhase 2 supervised pilot: NOT READY", file=sys.stderr)
        return 1
    print("\nPhase 2 supervised pilot: READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
