"""Pull SoftDent/QuickBooks exports into the Documents page queue.

Runs import_sync (upstream export pull + cache refresh) then merges source rows
into nr2:v2:documents via document_sync (OCR ledger + document_source_import).

Designed for manual runs and the 30-minute scheduled task.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any


def sync_document_sources(*, pull_imports: bool = True, full_pull: bool | None = None) -> dict[str, Any]:
    """Refresh import cache and merge SoftDent/QuickBooks rows into Documents."""
    import os

    from document_sync import NR2_DATA_DIR, sync_accounting_documents
    from local_store import LocalStore

    result: dict[str, Any] = {
        "syncedAt": datetime.now(timezone.utc).isoformat(),
        "importSync": None,
        "documents": None,
        "postPullSetup": None,
        "warnings": [],
    }

    if full_pull is None:
        full_pull = os.environ.get("NR2_HAL_FULL_PULL", "").strip().lower() in {"1", "true", "yes", "on"}

    if pull_imports:
        from import_sync import sync_imports

        result["importSync"] = sync_imports(full_pull=full_pull)
        import_warnings = result["importSync"].get("warnings") if isinstance(result["importSync"], dict) else None
        if isinstance(import_warnings, list):
            result["warnings"].extend(import_warnings)

    store = LocalStore(NR2_DATA_DIR)
    documents = sync_accounting_documents(store)
    result["documents"] = documents
    doc_warnings = documents.get("warnings") if isinstance(documents, dict) else None
    if isinstance(doc_warnings, list):
        result["warnings"].extend(doc_warnings)
    source_import = documents.get("sourceImport") if isinstance(documents, dict) else None
    if isinstance(source_import, dict):
        result["sourceImport"] = source_import
    result["queueCount"] = documents.get("queueCount") if isinstance(documents, dict) else None

    if full_pull:
        try:
            from hal_post_pull_setup import run_post_pull_setup

            result["postPullSetup"] = run_post_pull_setup(store)
        except Exception as exc:
            result["postPullSetup"] = {"ok": False, "error": str(exc)}
            result["warnings"].append(f"Post-pull setup skipped: {exc}")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync SoftDent/QuickBooks data into the Documents page.")
    parser.add_argument(
        "--skip-import-pull",
        action="store_true",
        help="Only merge cached import files into Documents (do not pull upstream exports).",
    )
    args = parser.parse_args()
    payload = sync_document_sources(pull_imports=not args.skip_import_pull)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
