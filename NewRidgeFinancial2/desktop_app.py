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
import uuid
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
        from hal_hub import resolve_hub_data_dir, resolve_hal_hub_url

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
            "halHubUrl": resolve_hal_hub_url(),
            "officeHubData": str(resolve_hub_data_dir()),
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

    def export_posting_queue_iif_with_consent(self, payload_json: str = "{}") -> dict:
        from outbound_actions import export_posting_queue_iif
        import json as _json

        payload = _json.loads(payload_json or "{}")
        if not isinstance(payload, dict):
            payload = {}
        return export_posting_queue_iif(
            self.store.db_path,
            limit=int(payload.get("limit") or 200),
            consent_text=str(payload.get("consentText") or ""),
            actor=str(payload.get("actor") or "Staff"),
            store=self.store,
        )

    def send_email_with_consent(self, payload_json: str = "{}") -> dict:
        from outbound_actions import send_email_with_consent
        import json as _json

        payload = _json.loads(payload_json or "{}")
        if not isinstance(payload, dict):
            payload = {}
        return send_email_with_consent(
            to=str(payload.get("to") or ""),
            subject=str(payload.get("subject") or ""),
            body=str(payload.get("body") or ""),
            consent_text=str(payload.get("consentText") or ""),
            actor=str(payload.get("actor") or "Staff"),
            store=self.store,
            dry_run=bool(payload.get("dryRun")),
        )

    def build_claim_packet_with_consent(self, payload_json: str = "{}") -> dict:
        from outbound_actions import build_claim_submission_packet
        import json as _json

        payload = _json.loads(payload_json or "{}")
        if not isinstance(payload, dict):
            payload = {}
        return build_claim_submission_packet(
            claim_id=str(payload.get("claimId") or payload.get("claim_id") or ""),
            narrative=str(payload.get("narrative") or payload.get("body") or ""),
            notes=str(payload.get("notes") or payload.get("query") or ""),
            consent_text=str(payload.get("consentText") or ""),
            actor=str(payload.get("actor") or "Staff"),
            store=self.store,
        )

    def export_narrative_portal_prep_with_consent(self, payload_json: str = "{}") -> dict:
        from outbound_actions import export_narrative_portal_prep
        import json as _json

        payload = _json.loads(payload_json or "{}")
        if not isinstance(payload, dict):
            payload = {}
        return export_narrative_portal_prep(
            claim_id=str(payload.get("claimId") or payload.get("claim_id") or ""),
            narrative=str(payload.get("narrative") or payload.get("body") or ""),
            consent_text=str(payload.get("consentText") or ""),
            actor=str(payload.get("actor") or "Staff"),
            store=self.store,
        )

    def quickbooks_online_status(self) -> dict:
        from outbound_actions import quickbooks_online_status

        return quickbooks_online_status()

    def post_qbo_journal_with_consent(self, payload_json: str = "{}") -> dict:
        from outbound_actions import post_qbo_journal_with_consent
        import json as _json

        payload = _json.loads(payload_json or "{}")
        if not isinstance(payload, dict):
            payload = {}
        return post_qbo_journal_with_consent(
            self.store.db_path,
            limit=int(payload.get("limit") or 25),
            consent_text=str(payload.get("consentText") or ""),
            actor=str(payload.get("actor") or "Staff"),
            store=self.store,
            dry_run=bool(payload.get("dryRun")),
        )

    def build_payer_portal_rpa_with_consent(self, payload_json: str = "{}") -> dict:
        from outbound_actions import build_payer_portal_rpa_with_consent
        import json as _json

        payload = _json.loads(payload_json or "{}")
        if not isinstance(payload, dict):
            payload = {}
        return build_payer_portal_rpa_with_consent(
            claim_id=str(payload.get("claimId") or payload.get("claim_id") or ""),
            payer=str(payload.get("payer") or ""),
            portal_url=str(payload.get("portalUrl") or payload.get("portal_url") or ""),
            narrative=str(payload.get("narrative") or payload.get("body") or ""),
            consent_text=str(payload.get("consentText") or ""),
            actor=str(payload.get("actor") or "Staff"),
            store=self.store,
        )

    def queue_softdent_writeback_with_consent(self, payload_json: str = "{}") -> dict:
        from outbound_actions import queue_softdent_writeback_with_consent
        import json as _json

        payload = _json.loads(payload_json or "{}")
        if not isinstance(payload, dict):
            payload = {}
        inner = payload.get("payload")
        return queue_softdent_writeback_with_consent(
            action=str(payload.get("action") or "note"),
            payload=inner if isinstance(inner, dict) else {},
            consent_text=str(payload.get("consentText") or ""),
            actor=str(payload.get("actor") or "Staff"),
            store=self.store,
        )

    def softdent_writeback_status(self) -> dict:
        from outbound_actions import softdent_writeback_status

        return softdent_writeback_status()

    def list_outbound_audit(self, limit: int = 15) -> dict:
        from outbound_actions import list_outbound_audit

        return list_outbound_audit(self.store, limit=int(limit or 15))

    def employee_status(self, target_level: int = 7) -> dict:
        from employee_actions import get_employee_status

        return get_employee_status(self.store, target_level=int(target_level or 7))

    def list_employee_work_log(self, limit: int = 20) -> dict:
        from employee_actions import list_employee_work_log

        return list_employee_work_log(self.store, limit=int(limit or 20))

    def append_employee_work_log(self, payload_json: str = "{}") -> dict:
        from employee_actions import append_employee_work_log
        import json as _json

        payload = _json.loads(payload_json or "{}")
        if not isinstance(payload, dict):
            payload = {}
        return append_employee_work_log(
            self.store,
            action=str(payload.get("action") or "work"),
            summary=str(payload.get("summary") or ""),
            level=int(payload.get("level") or 1),
            actor=str(payload.get("actor") or "HAL"),
            result=payload.get("result") if isinstance(payload.get("result"), dict) else {},
        )

    def run_employee_shift(self, payload_json: str = "{}") -> dict:
        from employee_actions import run_employee_shift
        import json as _json

        payload = _json.loads(payload_json or "{}")
        if not isinstance(payload, dict):
            payload = {}
        return run_employee_shift(
            self.store.db_path,
            store=self.store,
            target_level=int(payload.get("targetLevel") or 7),
            dry_run=bool(payload.get("dryRun")),
        )

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

    def update_hal_session_context(
        self,
        claim_id: str = "",
        narrative_id: str = "",
        page: str = "",
        topic: str = "",
        payer: str = "",
    ) -> dict:
        from hal_learning import update_session_context

        return update_session_context(
            claim_id=str(claim_id or ""),
            narrative_id=str(narrative_id or ""),
            page=str(page or ""),
            topic=str(topic or ""),
            payer=str(payer or ""),
        )

    def hal_learning_status(self) -> dict:
        from hal_learning import learning_status

        return learning_status()

    def get_tax_plan(self) -> dict:
        from import_loader import load_import_bundle
        from tax_engine import build_tax_plan_from_bundle

        bundle = load_import_bundle(sync=False, deep=False)
        return build_tax_plan_from_bundle(bundle)

    def get_integration_health(self) -> dict:
        from integration_health import integration_health_snapshot

        with self._sync_lock:
            sync_state = dict(self._sync_state)
        return integration_health_snapshot(self.store, sync_state=sync_state, deep_diagnostics=True)

    def get_automation_registry(self) -> dict:
        from automation_registry import list_automation_jobs

        return list_automation_jobs()

    def build_support_bundle(self, note: str = "") -> dict:
        from hal_audit import append_audit_event
        from support_bundle import build_support_bundle

        result = build_support_bundle(self.store, note=str(note or ""))
        append_audit_event(event_type="support_bundle", actor="Staff", detail=result.get("path", ""))
        return result

    def get_financial_reports(self, sync_exports: bool = False) -> dict:
        from financial_reports import build_financial_reports

        return build_financial_reports(sync_exports=bool(sync_exports))

    def get_daily_closeout(self) -> dict:
        from daily_closeout import build_daily_closeout

        return build_daily_closeout(self.store)

    def run_program_self_heal(self, full_pull: bool = False, documents_only: bool = False, reason: str = "desktop", approve_journal: bool = False) -> dict:
        from program_self_heal import run_program_self_heal

        return run_program_self_heal(
            self.store,
            full_pull=bool(full_pull),
            pull_imports=not bool(documents_only),
            approve_journal_pending=bool(approve_journal),
            reason=str(reason or "desktop"),
        )

    def bulk_review_posting_queue(self, action: str = "approved", reviewer_actor: str = "local-user", review_note: str = "") -> dict:
        from accounting_bridge import bulk_review_posting_queue

        return bulk_review_posting_queue(
            self.store.db_path,
            action=str(action or "approved"),
            reviewer_actor=str(reviewer_actor or "local-user"),
            review_note=str(review_note or ""),
        )

    def get_program_help(self, query: str) -> dict:
        from program_help import format_program_help, match_program_help

        return {"text": format_program_help(query), "match": match_program_help(query)}

    def search_hal_memories(self, query: str, limit: int = 5) -> dict:
        from knowledge_memory_index import format_memory_hits, search_memories

        hits = search_memories(str(query or ""), limit=int(limit or 5))
        return {"items": hits, "count": len(hits), "text": format_memory_hits(hits)}

    def search_payer_reference(self, query: str, limit: int = 5) -> dict:
        from payer_reference_store import format_payer_hits, search_payers

        hits = search_payers(str(query or ""), limit=int(limit or 5))
        return {"items": hits, "count": len(hits), "text": format_payer_hits(hits)}

    def join_claim_payers(self, claims_json: str) -> dict:
        import json

        from payer_reference_store import enrich_claims, format_claim_payer_joins

        try:
            claims = json.loads(claims_json) if claims_json else []
        except json.JSONDecodeError:
            claims = []
        if not isinstance(claims, list):
            claims = []
        items = enrich_claims(claims, limit=20)
        joined = [c for c in items if c.get("payerMatch")]
        return {
            "items": items,
            "count": len(joined),
            "text": format_claim_payer_joins(claims),
        }

    def lookup_fee_schedule(self, query: str, limit: int = 3) -> dict:
        from fee_schedule_store import format_fee_hits, lookup_fees

        hits = lookup_fees(str(query or ""), limit=int(limit or 3))
        return {"items": hits, "count": len(hits), "text": format_fee_hits(hits)}

    def list_eligibility_cache(self, limit: int = 20) -> dict:
        from eligibility_cache_store import eligibility_cache_summary, format_eligibility_hits, list_eligibility_entries

        items = list_eligibility_entries(limit=int(limit or 20), fresh_only=True)
        return {
            "items": items,
            "count": len(items),
            "text": format_eligibility_hits(items),
            "summary": eligibility_cache_summary(),
        }

    def upsert_eligibility_cache(self, entry_json: str) -> dict:
        from eligibility_cache_store import upsert_eligibility_entry
        import json as _json

        try:
            payload = _json.loads(entry_json or "{}")
        except _json.JSONDecodeError as exc:
            return {"ok": False, "error": f"invalid_json:{exc}"}
        if not isinstance(payload, dict):
            return {"ok": False, "error": "entry_must_be_object"}
        return upsert_eligibility_entry(payload)

    def search_eligibility_cache(self, query: str, limit: int = 10) -> dict:
        from eligibility_cache_store import format_eligibility_hits, search_eligibility_cache

        items = search_eligibility_cache(str(query or ""), limit=int(limit or 10))
        return {
            "items": items,
            "count": len(items),
            "text": format_eligibility_hits(items),
        }

    def fetch_eligibility_271(self, request_json: str) -> dict:
        from clearinghouse_eligibility_adapter import fetch_eligibility_271
        import json as _json

        try:
            payload = _json.loads(request_json or "{}")
        except _json.JSONDecodeError as exc:
            return {"ok": False, "error": f"invalid_json:{exc}"}
        if not isinstance(payload, dict):
            return {"ok": False, "error": "request_must_be_object"}
        return fetch_eligibility_271(payload)

    def clearinghouse_status(self) -> dict:
        from clearinghouse_eligibility_adapter import clearinghouse_status

        return {"ok": True, **clearinghouse_status()}

    def grep_program_source(self, query: str, limit: int = 24) -> dict:
        from program_source_grep import grep_program_source

        return grep_program_source(REPO_ROOT, self.site_dir, str(query or ""), int(limit or 24))

    def read_program_file(self, rel_path: str, max_chars: int = 12000) -> dict:
        from program_source_grep import read_program_file

        return read_program_file(REPO_ROOT, self.site_dir, str(rel_path or ""), int(max_chars or 12000))

    def list_program_files(self, subdir: str = "site", limit: int = 80) -> dict:
        from program_source_grep import list_program_files

        return list_program_files(REPO_ROOT, self.site_dir, str(subdir or "site"), int(limit or 80))

    def apply_program_patch(self, rel_path: str, old_string: str, new_string: str, dry_run: bool = False) -> dict:
        from program_source_grep import apply_program_patch

        return apply_program_patch(
            REPO_ROOT,
            self.site_dir,
            str(rel_path or ""),
            str(old_string or ""),
            str(new_string or ""),
            dry_run=bool(dry_run),
        )

    def run_hal_validation(self, timeout_sec: int = 120) -> dict:
        from program_source_grep import run_hal_validation

        return run_hal_validation(REPO_ROOT, int(timeout_sec or 120))

    def run_node_syntax_check(self, rel_paths: list) -> dict:
        from program_source_grep import run_node_syntax_check

        paths = [str(p) for p in (rel_paths or [])]
        return run_node_syntax_check(REPO_ROOT, self.site_dir, paths)

    def semantic_search_program(self, query: str, limit: int = 15) -> dict:
        from program_source_grep import semantic_search_program

        return semantic_search_program(REPO_ROOT, self.site_dir, str(query or ""), int(limit or 15))

    def run_git_readonly(self, command: str = "status") -> dict:
        from program_source_grep import run_git_readonly

        return run_git_readonly(REPO_ROOT, str(command or "status"))

    def run_allowlisted_command(self, command_id: str = "validate-hal") -> dict:
        from program_source_grep import run_allowlisted_command

        return run_allowlisted_command(REPO_ROOT, str(command_id or "validate-hal"))

    def apply_program_patches(self, patches: list, dry_run: bool = False) -> dict:
        from program_source_grep import apply_program_patches

        return apply_program_patches(REPO_ROOT, self.site_dir, patches or [], dry_run=bool(dry_run))

    def get_hal_audit_recent(self, limit: int = 20) -> dict:
        from hal_audit import read_recent_audit

        items = read_recent_audit(limit=int(limit or 20))
        return {"items": items, "count": len(items)}


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

    def _startup_import_sync() -> None:
        try:
            api._run_import_sync()
        except Exception as exc:
            print(f"Startup import sync failed: {exc}", file=sys.stderr)

    threading.Thread(target=_startup_import_sync, daemon=True).start()
    WEBVIEW_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    default_port = 8765
    http_port = int(os.environ.get("NR2_HTTP_PORT", str(default_port)))
    print(
        f"NR2 desktop: schema={DESIGN_SCHEMA_VERSION} site={SITE_DIR} storage={WEBVIEW_STORAGE_DIR}",
        file=sys.stderr,
    )
    print(
        f"NR2 desktop: UI in pywebview window only (loopback port {http_port} is not for browser use).",
        file=sys.stderr,
    )
    from hal_hub import resolve_hub_data_dir

    print(f"NR2 desktop: HAL hub data={resolve_hub_data_dir()} (NR2_OFFICE_HUB_DATA)", file=sys.stderr)
    from nr2_http_server import NR2BottleServer, set_desktop_session_token, set_site_root, set_workstation_mode

    desktop_token = uuid.uuid4().hex
    set_desktop_session_token(desktop_token)
    set_workstation_mode(False)
    set_site_root(SITE_DIR)
    start_url = f"http://127.0.0.1:{http_port}/?nr2dt={desktop_token}"
    window = webview.create_window(
        f"NewRidgeFinancial 2.0 ({DESIGN_SCHEMA_VERSION})",
        start_url,
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
