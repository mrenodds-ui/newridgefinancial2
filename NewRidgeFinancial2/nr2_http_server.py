"""NR2 loopback HTTP server — serves site/ with index.html at /."""

from __future__ import annotations

import json
import os
import threading
import uuid

from pathlib import Path

import bottle

from webview.http import BottleServer, SSLWSGIRefServer, ThreadedAdapter, _get_random_port, logger
from webview.util import abspath, is_app, is_local_url

REPO_ROOT = Path(__file__).resolve().parent.parent
NR2_DATA_DIR = REPO_ROOT / "app_data" / "nr2"


class NR2BottleServer(BottleServer):
    """pywebview BottleServer with / → index.html (fixes HTTP 500 on root URL)."""

    @classmethod
    def start_server(cls, urls, http_port, keyfile=None, certfile=None):
        from webview import _state

        apps = [u for u in urls if is_app(u)]
        server = cls()

        if len(apps) > 0:
            return super().start_server(urls, http_port, keyfile, certfile)

        local_urls = [u.split("#")[0] for u in urls if is_local_url(u)]
        common_path = os.path.dirname(os.path.commonpath(local_urls)) if local_urls else None
        server.root_path = abspath(common_path) if common_path is not None else None
        logger.debug("HTTP server root path: %s", server.root_path)
        app = bottle.Bottle()

        @app.post(f"/js_api/{server.uid}")
        def js_api():
            bottle.response.headers["Access-Control-Allow-Origin"] = "*"
            bottle.response.headers["Access-Control-Allow-Methods"] = "PUT, GET, POST, DELETE, OPTIONS"
            bottle.response.headers["Access-Control-Allow-Headers"] = (
                "Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token"
            )
            body = json.loads(bottle.request.body.read().decode("utf-8"))
            if body["uid"] in server.js_callback:
                return json.dumps(server.js_callback[body["uid"]](body))
            logger.error("JS callback function is not set for window %s", body["uid"])

        @app.get("/api/import-bundle")
        def import_bundle():
            bottle.response.content_type = "application/json"
            bottle.response.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
            try:
                from import_loader import load_import_bundle

                return json.dumps(load_import_bundle(sync=False, deep=False))
            except Exception as exc:
                bottle.response.status = 500
                return json.dumps({"error": str(exc)})

        @app.get("/api/sync-documents")
        def sync_documents_api():
            bottle.response.content_type = "application/json"
            bottle.response.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
            try:
                from document_sync import sync_accounting_documents
                from local_store import LocalStore

                store = LocalStore(NR2_DATA_DIR)
                return json.dumps(sync_accounting_documents(store))
            except Exception as exc:
                bottle.response.status = 500
                return json.dumps({"error": str(exc)})

        @app.get("/api/documents-state")
        def documents_state_api():
            bottle.response.content_type = "application/json"
            bottle.response.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
            try:
                from local_store import LocalStore

                store = LocalStore(NR2_DATA_DIR)
                raw = store.get("nr2:v2:documents")
                if not raw:
                    return json.dumps({"queue": [], "period": None})
                return raw
            except Exception as exc:
                bottle.response.status = 500
                return json.dumps({"error": str(exc)})

        @app.get("/api/posting-queue")
        def posting_queue_api():
            bottle.response.content_type = "application/json"
            bottle.response.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
            try:
                from accounting_bridge import list_posting_queue
                from local_store import LocalStore

                store = LocalStore(NR2_DATA_DIR)
                return json.dumps(list_posting_queue(store.db_path, limit=20))
            except Exception as exc:
                bottle.response.status = 500
                return json.dumps({"error": str(exc)})

        def _local_store():
            from local_store import LocalStore

            return LocalStore(NR2_DATA_DIR)

        @app.get("/api/integration-health")
        def integration_health_api():
            bottle.response.content_type = "application/json"
            bottle.response.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
            try:
                from integration_health import integration_health_snapshot

                store = _local_store()
                return json.dumps(integration_health_snapshot(store, deep_diagnostics=True))
            except Exception as exc:
                bottle.response.status = 500
                return json.dumps({"error": str(exc)})

        @app.get("/api/automation-registry")
        def automation_registry_api():
            bottle.response.content_type = "application/json"
            try:
                from automation_registry import list_automation_jobs

                return json.dumps(list_automation_jobs())
            except Exception as exc:
                bottle.response.status = 500
                return json.dumps({"error": str(exc)})

        @app.post("/api/support-bundle")
        def support_bundle_api():
            bottle.response.content_type = "application/json"
            try:
                from support_bundle import build_support_bundle

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                store = _local_store()
                return json.dumps(build_support_bundle(store, note=str(payload.get("note") or "")))
            except Exception as exc:
                bottle.response.status = 500
                return json.dumps({"error": str(exc)})

        @app.get("/api/financial-reports")
        def financial_reports_api():
            bottle.response.content_type = "application/json"
            try:
                from financial_reports import build_financial_reports

                sync_exports = bottle.request.query.get("syncExports") == "1"
                return json.dumps(build_financial_reports(sync_exports=sync_exports))
            except Exception as exc:
                bottle.response.status = 500
                return json.dumps({"error": str(exc)})

        @app.get("/api/daily-closeout")
        def daily_closeout_api():
            bottle.response.content_type = "application/json"
            try:
                from daily_closeout import build_daily_closeout

                store = _local_store()
                return json.dumps(build_daily_closeout(store))
            except Exception as exc:
                bottle.response.status = 500
                return json.dumps({"error": str(exc)})

        @app.post("/api/self-heal")
        def self_heal_api():
            bottle.response.content_type = "application/json"
            try:
                from program_self_heal import run_program_self_heal

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                store = _local_store()
                report = run_program_self_heal(
                    store,
                    full_pull=bool(payload.get("fullPull")),
                    pull_imports=not bool(payload.get("documentsOnly")),
                    reason=str(payload.get("reason") or "http"),
                )
                return json.dumps(report)
            except Exception as exc:
                bottle.response.status = 500
                return json.dumps({"error": str(exc), "status": "fail"})

        @app.get("/")
        def index():
            if not server.root_path:
                return ""
            bottle.response.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
            bottle.response.set_header("Pragma", "no-cache")
            bottle.response.set_header("Expires", 0)
            return bottle.static_file("index.html", root=server.root_path)

        @app.route("/<file:path>")
        def asset(file):
            if not server.root_path:
                return ""
            bottle.response.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
            bottle.response.set_header("Pragma", "no-cache")
            bottle.response.set_header("Expires", 0)
            return bottle.static_file(file, root=server.root_path)

        server.root_path = abspath(common_path) if common_path is not None else None
        server.port = http_port or _get_random_port()
        if keyfile and certfile:
            server_adapter = SSLWSGIRefServer()
            server_adapter.port = server.port
            setattr(server_adapter, "pywebview_keyfile", keyfile)
            setattr(server_adapter, "pywebview_certfile", certfile)
        else:
            server_adapter = ThreadedAdapter
        server.thread = threading.Thread(
            target=lambda: bottle.run(
                app=app, server=server_adapter, port=server.port, quiet=not _state["debug"]
            ),
            daemon=True,
        )
        server.thread.start()

        server.running = True
        protocol = "https" if keyfile and certfile else "http"
        server.address = f"{protocol}://127.0.0.1:{server.port}/"
        cls.common_path = common_path
        server.js_api_endpoint = f"{server.address}js_api/{server.uid}"

        return server.address, common_path, server
