#!/usr/bin/env python3
"""
NewRidgeFinancial 2.0 — single-window desktop program.

One process, one window, local UI assets served over loopback HTTP, local SQLite storage.
No external browser tab; pywebview hosts the site/ bundle.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
SITE_DIR = ROOT / "site"
DATA_DIR = REPO_ROOT / "app_data" / "nr2"
SIDENOTES_HUB_DATA_DIR = Path(os.environ.get("NR2_SIDENOTES_HUB_DATA", r"C:\softdent\HAL-SideNotes-Workstation\data"))
INDEX_HTML = SITE_DIR / "index.html"
BUILD_MANIFEST = ROOT / "nr2-build.json"


def load_build_manifest() -> dict:
    if BUILD_MANIFEST.is_file():
        try:
            data = json.loads(BUILD_MANIFEST.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return {"assetVersion": "hal-94", "schemaVersion": "hal-94"}


_BUILD = load_build_manifest()
DESIGN_SCHEMA_VERSION = str(_BUILD.get("schemaVersion") or _BUILD.get("assetVersion") or "hal-94")
ASSET_VERSION = str(_BUILD.get("assetVersion") or DESIGN_SCHEMA_VERSION)
WEBVIEW_STORAGE_DIR = DATA_DIR / "webview" / DESIGN_SCHEMA_VERSION


class DesktopApi:
    """JavaScript bridge: local files + SQLite only."""

    def __init__(self, site_dir: Path, data_dir: Path) -> None:
        from local_store import LocalStore

        self.site_dir = site_dir
        self.store = LocalStore(data_dir)
        self._sync_lock = threading.Lock()
        self._sync_state: dict = {
            "status": "idle",
            "startedAt": None,
            "completedAt": None,
            "error": None,
            "result": None,
        }
        # Cached upstream-health report. The full scan recursively walks the
        # SoftDent/QuickBooks export trees and is far too slow for the UI hot
        # path, so it is computed off-thread and attached to bundles when ready.
        self._upstream_lock = threading.Lock()
        self._upstream_cache: dict | None = None
        self._upstream_thread: threading.Thread | None = None

    def get_app_info(self) -> dict:
        from document_sync import resolve_archive_path, resolve_inbox_path

        return {
            "mode": "desktop",
            "version": "2.0",
            "designSchemaVersion": DESIGN_SCHEMA_VERSION,
            "assetVersion": ASSET_VERSION,
            "siteDir": str(self.site_dir),
            "repoRoot": str(REPO_ROOT),
            "indexHtml": str(INDEX_HTML),
            "dbPath": str(self.store.db_path),
            "documentInbox": str(resolve_inbox_path()),
            "documentArchive": str(resolve_archive_path()),
            "sidenotesHub": str(SIDENOTES_HUB_DATA_DIR),
            "dataDir": str(self.store.data_dir),
            "directFirstImports": self._direct_first_imports_enabled(),
        }

    @staticmethod
    def _direct_first_imports_enabled() -> bool:
        from import_loader import direct_first_imports_enabled

        return direct_first_imports_enabled()

    def read_data_file(self, name: str) -> str:
        if name.startswith("sidenotes-inbox"):
            hub_path = SIDENOTES_HUB_DATA_DIR / name
            site_fallback = self.site_dir / "data" / name
            candidates: list[tuple[str, Path]] = []
            for path in (hub_path, site_fallback):
                if not path.is_file():
                    continue
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    checked = str((data.get("monitor") or {}).get("checkedAt") or data.get("generatedAt") or "")
                except json.JSONDecodeError:
                    checked = ""
                candidates.append((checked, path))
            if not candidates:
                return json.dumps({"items": [], "monitor": None})
            candidates.sort(key=lambda item: item[0], reverse=True)
            return candidates[0][1].read_text(encoding="utf-8")
        path = self.site_dir / "data" / name
        if not path.is_file():
            raise FileNotFoundError(f"Data file not found: {name}")
        return path.read_text(encoding="utf-8")

    def storage_get(self, key: str) -> str | None:
        return self.store.get(key)

    def storage_set(self, key: str, value_json: str) -> bool:
        try:
            json.loads(value_json)
        except json.JSONDecodeError as exc:
            raise ValueError("storage_set requires valid JSON") from exc
        self.store.set(key, value_json)
        return True

    def _refresh_upstream_health_async(self) -> None:
        def worker() -> None:
            try:
                from import_diagnostics import check_upstream_health

                health = check_upstream_health()
                with self._upstream_lock:
                    self._upstream_cache = health
            except Exception:
                pass
            finally:
                with self._upstream_lock:
                    self._upstream_thread = None

        with self._upstream_lock:
            if self._upstream_thread is not None and self._upstream_thread.is_alive():
                return
            thread = threading.Thread(target=worker, daemon=True)
            self._upstream_thread = thread
        thread.start()

    def get_import_bundle(self) -> dict:
        from import_loader import load_import_bundle

        # Direct-first: scan upstream export roots for the newest files (cache fallback).
        # sync=False keeps dashboard loads fast; manual refresh re-scans upstream.
        bundle = load_import_bundle(sync=False, deep=False)
        with self._upstream_lock:
            cached = self._upstream_cache
        if cached is not None:
            bundle["upstreamHealth"] = cached
        # Refresh the upstream report in the background for the next read.
        self._refresh_upstream_health_async()
        return bundle

    def get_import_sync_status(self) -> dict:
        with self._sync_lock:
            return dict(self._sync_state)

    def _run_import_sync(self) -> None:
        from document_sync import sync_accounting_documents
        from import_loader import direct_first_imports_enabled, load_import_bundle

        try:
            if direct_first_imports_enabled():
                bundle = load_import_bundle(sync=True, deep=True)
                documents = sync_accounting_documents(self.store)
                result = {
                    "directFirst": True,
                    "importMode": bundle.get("importMode"),
                    "diagnostics": bundle.get("diagnostics"),
                    "documents": documents,
                }
                sync_result = bundle.get("syncStatus", {}).get("result")
                if isinstance(sync_result, dict):
                    result["directRefresh"] = sync_result
            else:
                from import_sync import sync_imports

                result = sync_imports()
                result["documents"] = sync_accounting_documents(self.store)
            with self._sync_lock:
                self._sync_state = {
                    "status": "success",
                    "startedAt": self._sync_state.get("startedAt"),
                    "completedAt": datetime.now(timezone.utc).isoformat(),
                    "error": None,
                    "result": result,
                }
        except Exception as exc:
            with self._sync_lock:
                self._sync_state = {
                    "status": "failed",
                    "startedAt": self._sync_state.get("startedAt"),
                    "completedAt": datetime.now(timezone.utc).isoformat(),
                    "error": str(exc),
                    "result": None,
                }

    def sync_accounting_documents(self) -> dict:
        from document_sync import sync_accounting_documents

        return sync_accounting_documents(self.store)

    def clipboard_read(self) -> str:
        """Return system clipboard text (Windows desktop shell)."""
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            try:
                return str(root.clipboard_get())
            except tk.TclError:
                return ""
            finally:
                root.destroy()
        except Exception:
            return ""

    def clipboard_write(self, text: str) -> bool:
        """Write text to the system clipboard."""
        payload = "" if text is None else str(text)
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            root.clipboard_clear()
            root.clipboard_append(payload)
            root.update()
            root.destroy()
            return True
        except Exception:
            return False

    def refresh_imports(self) -> dict:
        with self._sync_lock:
            if self._sync_state.get("status") == "running":
                return dict(self._sync_state)
            self._sync_state = {
                "status": "running",
                "startedAt": datetime.now(timezone.utc).isoformat(),
                "completedAt": None,
                "error": None,
                "result": None,
            }
            state = dict(self._sync_state)
        thread = threading.Thread(target=self._run_import_sync, daemon=True)
        thread.start()
        return state

    def list_practice_source_catalog(self) -> dict:
        from practice_source_access import list_catalog

        return list_catalog()

    def fetch_practice_source(self, system: str, resource: str, options_json: str = "{}") -> dict:
        from practice_source_access import fetch

        try:
            options = json.loads(options_json) if options_json else {}
        except json.JSONDecodeError:
            options = {}
        if not isinstance(options, dict):
            options = {}
        return fetch(system, resource, options)

    def pull_practice_sources(self, options: str = "{}") -> dict:
        from practice_source_access import pull_all_practice_sources
        import json as _json

        opts = _json.loads(options or "{}") if isinstance(options, str) else (options or {})
        full = bool(opts.get("fullPull"))
        return pull_all_practice_sources(full=full)

    def get_chart_of_accounts(self) -> dict:
        from accounting_tools import get_chart_of_accounts

        return {"accounts": get_chart_of_accounts(), "source": "accounting_tools.py"}

    def draft_journal_entry(self, description: str, period: str, amount: float, context_json: str = "{}") -> dict:
        from accounting_bridge import draft_journal_payload, parse_context_json

        return draft_journal_payload(
            description=description,
            period=period,
            amount=float(amount),
            context=parse_context_json(context_json),
        )

    def list_posting_queue(self, limit: int = 20, status: str = "") -> dict:
        from accounting_bridge import list_posting_queue

        return list_posting_queue(self.store.db_path, limit=int(limit or 20), status=status or None)

    def enqueue_journal_posting(self, payload_json: str) -> dict:
        from accounting_bridge import enqueue_journal_posting, parse_context_json
        import json as _json

        payload = _json.loads(payload_json or "{}")
        if not isinstance(payload, dict):
            raise ValueError("enqueue_journal_posting requires a JSON object")
        return enqueue_journal_posting(
            self.store.db_path,
            description=str(payload.get("description") or "Journal entry"),
            period=str(payload.get("period") or ""),
            amount=float(payload.get("amount") or 0),
            actor=str(payload.get("actor") or "Staff"),
            context=parse_context_json(_json.dumps(payload.get("context") or {})),
            transaction_date=str(payload.get("transactionDate") or "") or None,
            enqueue_mode=str(payload.get("enqueueMode") or "manual_review_queue"),
        )

    def review_posting_queue_entry(self, queue_id: str, action: str, reviewer_actor: str, review_note: str = "") -> dict:
        from accounting_bridge import review_posting_queue_entry

        return review_posting_queue_entry(
            self.store.db_path,
            queue_id=queue_id,
            action=action,
            reviewer_actor=reviewer_actor,
            review_note=review_note or None,
        )

    def export_approved_posting_queue(self, limit: int = 200) -> dict:
        from accounting_bridge import export_approved_posting_queue_csv

        return export_approved_posting_queue_csv(self.store.db_path, limit=int(limit or 200))

    def web_research(self, query: str, options_json: str = "{}") -> dict:
        from web_research import research
        import json as _json

        try:
            options = _json.loads(options_json) if options_json else {}
        except _json.JSONDecodeError:
            options = {}
        if not isinstance(options, dict):
            options = {}
        max_results = int(options.get("maxResults") or 5)
        enrich = options.get("enrich", True) is not False
        return research(str(query or ""), max_results=max_results, enrich=enrich)

    def list_hal_memories(self) -> dict:
        from knowledge_memory_store import load_approved_memories

        items = load_approved_memories()
        return {"items": items, "count": len(items)}

    def remember_hal_fact(self, text: str, source: str = "staff:remember", category: str = "") -> dict:
        from knowledge_memory_store import remember_fact

        return remember_fact(
            str(text or ""),
            source=str(source or "staff:remember"),
            category=str(category or "").strip() or None,
            actor="Staff",
        )

    def remember_hal_web_findings(self, query: str, findings_json: str) -> dict:
        from knowledge_memory_store import remember_web_findings
        import json as _json

        try:
            findings = _json.loads(findings_json) if findings_json else []
        except _json.JSONDecodeError:
            findings = []
        if not isinstance(findings, list):
            findings = []
        return remember_web_findings(findings, query=str(query or ""), actor="Staff")

    def get_tax_plan(self) -> dict:
        from import_loader import load_import_bundle
        from tax_engine import build_tax_plan_from_bundle

        bundle = load_import_bundle(sync=False, deep=False)
        return build_tax_plan_from_bundle(bundle)


def main() -> int:
    if not INDEX_HTML.is_file():
        print(f"Site not found: {INDEX_HTML}", file=sys.stderr)
        return 1

    try:
        import webview
    except ImportError:
        print("pywebview is required. Install with: pip install pywebview", file=sys.stderr)
        return 1

    api = DesktopApi(SITE_DIR, DATA_DIR)
    try:
        from document_sync import sync_accounting_documents

        sync_accounting_documents(api.store)
    except Exception as exc:
        print(f"Startup document sync failed: {exc}", file=sys.stderr)
    WEBVIEW_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    default_port = 8765
    http_port = int(os.environ.get("NR2_HTTP_PORT", str(default_port)))
    index_url = f"http://127.0.0.1:{http_port}/index.html"
    print(
        f"NR2 desktop: schema={DESIGN_SCHEMA_VERSION} site={SITE_DIR} storage={WEBVIEW_STORAGE_DIR}",
        file=sys.stderr,
    )
    print(
        f"NR2 desktop: UI at {index_url} (pywebview http_server=True).",
        file=sys.stderr,
    )
    from nr2_http_server import NR2BottleServer

    window = webview.create_window(
        f"NewRidgeFinancial 2.0 ({DESIGN_SCHEMA_VERSION})",
        index_url,
        width=1440,
        height=920,
        min_size=(1024, 700),
        js_api=api,
        # Allow selecting page text so staff can copy values out of widgets.
        # pywebview injects `user-select: none` unless this is enabled.
        text_select=True,
    )
    webview.start(
        debug=False,
        http_server=True,
        http_port=http_port,
        private_mode=True,
        storage_path=str(WEBVIEW_STORAGE_DIR),
        server=NR2BottleServer,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
