"""NR2 loopback HTTP server — serves site/ with index.html at /."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone

from pathlib import Path

import bottle

from webview.http import BottleServer, SSLWSGIRefServer, ThreadedAdapter, _get_random_port, logger
from webview.util import abspath, is_app, is_local_url

REPO_ROOT = Path(__file__).resolve().parent.parent
NR2_DATA_DIR = REPO_ROOT / "app_data" / "nr2"

_sync_lock = threading.Lock()
_sync_state = {
    "status": "idle",
    "startedAt": None,
    "completedAt": None,
    "error": None,
    "result": None,
}

_desktop_session_token: str | None = None
_site_root: Path | None = None
_workstation_show_fn = None


def set_workstation_show_callback(fn) -> None:
    global _workstation_show_fn
    _workstation_show_fn = fn


def set_desktop_session_token(token: str | None) -> None:
    global _desktop_session_token
    _desktop_session_token = str(token) if token else None


def set_site_root(path: Path | str | None) -> None:
    global _site_root
    _site_root = Path(path) if path else None


def _loopback_browser_allowed() -> bool:
    val = os.environ.get("NR2_ALLOW_BROWSER_LOOPBACK", "").strip().lower()
    return val in ("1", "true", "yes")


def _request_desktop_token() -> str | None:
    token = bottle.request.get_cookie("nr2dt")
    if token:
        return str(token)
    token = bottle.request.params.get("nr2dt")
    if token:
        return str(token)
    header = bottle.request.headers.get("X-NR2-Desktop-Token")
    if header:
        return str(header)
    return None


def _loopback_request() -> bool:
    remote = str(getattr(bottle.request, "remote_addr", "") or "")
    return remote in ("127.0.0.1", "::1", "localhost")


def _lan_hal_hub_access_ok() -> bool:
    """Allow workstation clients on the LAN to reach hub relay APIs without desktop cookie."""
    path = bottle.request.path or "/"
    method = (bottle.request.method or "GET").upper()
    if path.startswith("/api/hal-hub"):
        return True
    if path == "/api/office-channel" and method in ("GET", "OPTIONS"):
        return True
    if path == "/api/workstation/show" and method in ("POST", "OPTIONS") and _loopback_request():
        return True
    if method == "OPTIONS" and path.startswith("/api/"):
        return True
    return False


_workstation_mode = False
_browser_mode = False


def set_workstation_mode(enabled: bool = True) -> None:
    global _workstation_mode
    _workstation_mode = bool(enabled)
    if enabled:
        os.environ["NR2_WORKSTATION_APP"] = "1"


def set_browser_mode(enabled: bool = True) -> None:
    global _browser_mode
    _browser_mode = bool(enabled)
    if enabled:
        os.environ["NR2_BROWSER_APP"] = "1"


def _workstation_app() -> bool:
    if _workstation_mode:
        return True
    val = os.environ.get("NR2_WORKSTATION_APP", "").strip().lower()
    return val in ("1", "true", "yes")


def _browser_app() -> bool:
    if _browser_mode:
        return True
    val = os.environ.get("NR2_BROWSER_APP", "").strip().lower()
    return val in ("1", "true", "yes")


def _desktop_access_ok() -> bool:
    if _loopback_browser_allowed():
        return True
    path = bottle.request.path or "/"
    if path.startswith("/js_api/"):
        return True
    if _lan_hal_hub_access_ok():
        return True
    if _workstation_app():
        if _desktop_session_token and _request_desktop_token() == _desktop_session_token:
            return True
        return False
    if _browser_app() and _loopback_request():
        return True
    if _desktop_session_token:
        return _request_desktop_token() == _desktop_session_token
    return True


def _maybe_set_desktop_cookie() -> None:
    if not _desktop_session_token:
        return
    if bottle.request.params.get("nr2dt") != _desktop_session_token:
        return
    bottle.response.set_cookie(
        "nr2dt",
        _desktop_session_token,
        path="/",
        httponly=True,
        samesite="Strict",
        max_age=60 * 60 * 24 * 30,
    )


def _desktop_only_html() -> str:
    if _workstation_app():
        return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>NR2 Office Workstation — Desktop Only</title>
  <style>
    body { font-family: Segoe UI, system-ui, sans-serif; background: #ece9e4; color: #222; margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
    .card { max-width: 32rem; padding: 2rem 2.25rem; background: #fff; border: 1px solid #9a9488; border-radius: 4px; box-shadow: 2px 2px 8px rgba(0,0,0,.15); }
    h1 { margin: 0 0 .75rem; font-size: 1.25rem; color: #8b2020; }
    p { margin: 0 0 .85rem; line-height: 1.55; color: #444; }
    strong { color: #111; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Desktop app only</h1>
    <p><strong>NR2 Office Workstation</strong> is a desktop program (Send Message, Ask HAL, popups). It does not run in a web browser.</p>
    <p>Close this tab. Open the app from <strong>Start-NR2-Workstation.bat</strong> or the <strong>NR2 Workstation</strong> desktop shortcut.</p>
  </div>
</body>
</html>"""
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>NewRidgeFinancial 2.0 — Server Required</title>
  <style>
    body { font-family: Segoe UI, system-ui, sans-serif; background: #0f1419; color: #e8eef4; margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
    .card { max-width: 32rem; padding: 2rem 2.25rem; background: #1a2332; border: 1px solid #2d3a4d; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,.35); }
    h1 { margin: 0 0 .75rem; font-size: 1.35rem; color: #f5c518; }
    p { margin: 0 0 .85rem; line-height: 1.55; color: #b8c5d6; }
    strong { color: #fff; }
  </style>
</head>
<body>
  <div class="card">
    <h1>NR2 server not running</h1>
    <p>NewRidgeFinancial 2.0 is a <strong>browser program</strong> served from this PC. Financial pages, HAL, and imports run at <strong>http://127.0.0.1:8765/</strong> after you start the program.</p>
    <p>Run <strong>StartProgram.bat</strong>, then open that address in Chrome or Edge.</p>
  </div>
</body>
</html>"""

def _json_response(payload, status=200):
    bottle.response.content_type = "application/json"
    bottle.response.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
    if status != 200:
        bottle.response.status = status
    return json.dumps(payload)


def _run_import_sync_http(store) -> None:
    global _sync_state
    try:
        from document_sync import sync_accounting_documents
        from import_loader import direct_first_imports_enabled, load_import_bundle

        if direct_first_imports_enabled():
            bundle = load_import_bundle(sync=True, deep=True)
            documents = sync_accounting_documents(store)
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
            result["documents"] = sync_accounting_documents(store)
        with _sync_lock:
            _sync_state = {
                "status": "success",
                "startedAt": _sync_state.get("startedAt"),
                "completedAt": datetime.now(timezone.utc).isoformat(),
                "error": None,
                "result": result,
            }
    except Exception as exc:
        with _sync_lock:
            _sync_state = {
                "status": "failed",
                "startedAt": _sync_state.get("startedAt"),
                "completedAt": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
                "result": None,
            }


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
        if common_path is None and _site_root is not None:
            common_path = str(_site_root)
        server.root_path = abspath(common_path) if common_path is not None else None
        logger.debug("HTTP server root path: %s", server.root_path)
        app = bottle.Bottle()

        @app.hook("before_request")
        def _enforce_desktop_only():
            if _desktop_access_ok():
                return None
            bottle.abort(403, _desktop_only_html())

        @app.hook("after_request")
        def _hal_hub_cors_headers():
            path = bottle.request.path or ""
            if path.startswith("/api/hal-hub") or path == "/api/office-channel":
                bottle.response.headers["Access-Control-Allow-Origin"] = "*"
                bottle.response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
                bottle.response.headers["Access-Control-Allow-Headers"] = (
                    "Origin, Accept, Content-Type, X-Requested-With"
                )

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
            try:
                from import_loader import load_import_bundle

                return _json_response(load_import_bundle(sync=False, deep=False))
            except Exception as exc:
                return _json_response({"error": str(exc)}, status=500)

        @app.get("/api/app-info")
        def app_info_api():
            try:
                from import_loader import load_import_bundle

                bundle = load_import_bundle(sync=False, deep=False)
                from hal_hub import resolve_hub_data_dir, resolve_hal_hub_url

                return _json_response(
                    {
                        "mode": "loopback",
                        "version": "2.0",
                        "importMode": bundle.get("importMode"),
                        "runtimeAccess": True,
                        "halHubUrl": resolve_hal_hub_url(),
                        "officeHubData": str(resolve_hub_data_dir()),
                    }
                )
            except Exception as exc:
                return _json_response({"mode": "loopback", "version": "2.0", "error": str(exc)})

        @app.get("/api/import-sync-status")
        def import_sync_status_api():
            with _sync_lock:
                return _json_response(dict(_sync_state))

        @app.post("/api/refresh-imports")
        def refresh_imports_api():
            global _sync_state
            with _sync_lock:
                if _sync_state.get("status") == "running":
                    return _json_response(dict(_sync_state))
                _sync_state = {
                    "status": "running",
                    "startedAt": datetime.now(timezone.utc).isoformat(),
                    "completedAt": None,
                    "error": None,
                    "result": None,
                }
                state = dict(_sync_state)
            store = _local_store()
            thread = threading.Thread(target=_run_import_sync_http, args=(store,), daemon=True)
            thread.start()
            return _json_response(state)

        @app.get("/api/practice-source-catalog")
        def practice_source_catalog_api():
            try:
                from practice_source_access import list_catalog

                return _json_response(list_catalog())
            except Exception as exc:
                return _json_response({"error": str(exc)}, status=500)

        @app.post("/api/pull-practice-sources")
        def pull_practice_sources_api():
            try:
                from practice_source_access import pull_all_practice_sources

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                full = bool(payload.get("fullPull"))
                return _json_response(pull_all_practice_sources(full=full))
            except Exception as exc:
                return _json_response({"error": str(exc), "ok": False}, status=500)

        @app.post("/api/fetch-practice-source")
        def fetch_practice_source_api():
            try:
                from practice_source_access import fetch

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                return _json_response(
                    fetch(
                        str(payload.get("system") or ""),
                        str(payload.get("resource") or ""),
                        payload.get("options") if isinstance(payload.get("options"), dict) else {},
                    )
                )
            except Exception as exc:
                return _json_response({"error": str(exc)}, status=500)

        @app.get("/api/storage/<key>")
        def storage_get_api(key):
            try:
                store = _local_store()
                raw = store.get(str(key))
                if raw is None:
                    return _json_response({"key": key, "value": None})
                return _json_response({"key": key, "value": raw})
            except Exception as exc:
                return _json_response({"error": str(exc)}, status=500)

        @app.post("/api/storage/<key>")
        def storage_set_api(key):
            try:
                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else ""
                store = _local_store()
                store.set(str(key), body)
                return _json_response({"ok": True, "key": key})
            except Exception as exc:
                return _json_response({"error": str(exc), "ok": False}, status=500)

        from hal_hub import (
            append_office_channel_message,
            hub_announce,
            hub_status,
            load_office_channel,
            process_pending,
            register_station_heartbeat,
            resolve_hal_hub_url,
            stations_status,
            submit_inbound,
        )

        @app.route("/api/hal-hub/inbound", method=["OPTIONS"])
        @app.route("/api/hal-hub/process", method=["OPTIONS"])
        @app.route("/api/hal-hub/status", method=["OPTIONS"])
        @app.route("/api/hal-hub/announce", method=["OPTIONS"])
        @app.route("/api/hal-hub/stations", method=["OPTIONS"])
        @app.route("/api/hal-hub/stations/heartbeat", method=["OPTIONS"])
        @app.route("/api/office-channel", method=["OPTIONS"])
        @app.route("/api/workstation/show", method=["OPTIONS"])
        def hal_hub_options():
            return ""

        @app.post("/api/workstation/show")
        def workstation_show_api():
            if not _workstation_show_fn:
                return _json_response({"ok": False, "error": "workstation show not available"}, status=404)
            if not _loopback_request():
                return _json_response({"ok": False, "error": "loopback only"}, status=403)
            try:
                result = _workstation_show_fn()
                if isinstance(result, dict):
                    return _json_response(result)
                return _json_response({"ok": True})
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.get("/api/hal-hub/stations")
        def hal_hub_stations_api():
            try:
                return _json_response(stations_status())
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/hal-hub/stations/heartbeat")
        def hal_hub_station_heartbeat_api():
            try:
                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                station = str(payload.get("station") or "").strip()
                if not station:
                    return _json_response({"ok": False, "error": "empty station"}, status=400)
                remote = bottle.request.remote or ""
                host = str(payload.get("host") or remote or "").strip()
                port_raw = payload.get("port")
                port = int(port_raw) if port_raw is not None and str(port_raw).strip() != "" else None
                source = str(payload.get("source") or "nr2-workstation").strip()
                program_id = str(payload.get("programId") or payload.get("program") or "nr2-workstation").strip()
                entry = register_station_heartbeat(
                    station,
                    host=host,
                    port=port,
                    source=source,
                    program_id=program_id,
                )
                return _json_response({"ok": True, "station": entry, "roster": stations_status()})
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.get("/api/hal-hub/status")
        def hal_hub_status_api():
            try:
                return _json_response(hub_status())
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/hal-hub/inbound")
        def hal_hub_inbound_api():
            try:
                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                text = str(payload.get("text") or "").strip()
                if not text:
                    return _json_response({"ok": False, "error": "empty text"}, status=400)
                from_station = str(payload.get("from") or payload.get("fromStation") or "Staff").strip()
                raw_targets = payload.get("targets")
                targets = raw_targets if isinstance(raw_targets, list) else None
                speak = bool(payload.get("speak"))
                role = str(payload.get("role") or "staff")
                type_ = str(payload.get("type") or "announce")
                item = submit_inbound(from_station, targets, text, speak=speak, role=role, type_=type_)
                result = process_pending()
                return _json_response({"ok": True, "inbound": item, "dispatch": result})
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/hal-hub/process")
        def hal_hub_process_api():
            try:
                return _json_response(process_pending())
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/hal-hub/announce")
        def hal_hub_announce_api():
            try:
                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                text = str(payload.get("text") or "").strip()
                sender = str(payload.get("from") or payload.get("sender") or "").strip()
                broadcast = bool(payload.get("broadcast"))
                phrase_only = bool(payload.get("phraseOnly") or payload.get("phrase_only"))
                if phrase_only and not sender:
                    return _json_response({"ok": False, "error": "sender required for phraseOnly"}, status=400)
                result = hub_announce(
                    text,
                    sender=sender,
                    broadcast=broadcast,
                    phrase_only=phrase_only,
                )
                status = 200 if result.get("ok") else 500
                return _json_response(result, status=status)
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.get("/api/office-channel")
        def office_channel_get_api():
            try:
                return _json_response(load_office_channel())
            except Exception as exc:
                return _json_response({"error": str(exc), "messages": []}, status=500)

        @app.post("/api/office-channel")
        def office_channel_post_api():
            try:
                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                msg = payload.get("message") if isinstance(payload.get("message"), dict) else payload
                entry = append_office_channel_message(msg)
                data = load_office_channel()
                return _json_response({"ok": True, "message": entry, "channel": data})
            except ValueError as exc:
                return _json_response({"error": str(exc), "ok": False}, status=400)
            except Exception as exc:
                return _json_response({"error": str(exc), "ok": False}, status=500)

        @app.get("/api/sidenotes/status")
        def sidenotes_status_api():
            if not _workstation_app():
                return _json_response({"ok": False, "error": "sidenotes API is workstation-only"}, status=404)
            try:
                from sidenotes_bridge import sidenotes_status

                return _json_response(sidenotes_status())
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.get("/api/sidenotes/messages")
        def sidenotes_messages_api():
            if not _workstation_app():
                return _json_response({"ok": False, "error": "sidenotes API is workstation-only", "messages": []}, status=404)
            try:
                from sidenotes_bridge import sidenotes_read_messages

                station = bottle.request.params.get("station") or ""
                limit = int(bottle.request.params.get("limit") or 48)
                return _json_response(sidenotes_read_messages(station=station, limit=limit, include_body=True))
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc), "messages": []}, status=500)

        @app.post("/api/sidenotes/send")
        def sidenotes_send_api():
            if not _workstation_app():
                return _json_response({"ok": False, "error": "sidenotes API is workstation-only"}, status=404)
            try:
                from sidenotes_bridge import sidenotes_send_message

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                from_station = str(payload.get("from") or payload.get("fromStation") or "").strip()
                to_station = str(payload.get("to") or payload.get("target") or "Everyone").strip()
                text = str(payload.get("text") or "").strip()
                if not text:
                    return _json_response({"ok": False, "error": "empty text"}, status=400)
                if not from_station:
                    return _json_response({"ok": False, "error": "from station required"}, status=400)
                return _json_response(sidenotes_send_message(from_station, to_station, text))
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.get("/api/hal-memories")
        def hal_memories_api():
            try:
                from knowledge_memory_store import load_approved_memories

                items = load_approved_memories()
                return _json_response({"items": items, "count": len(items)})
            except Exception as exc:
                return _json_response({"error": str(exc), "items": [], "count": 0}, status=500)

        @app.post("/api/hal-memories")
        def hal_remember_api():
            try:
                from knowledge_memory_store import remember_fact

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                result = remember_fact(
                    str(payload.get("text") or ""),
                    source=str(payload.get("source") or "staff:remember"),
                    category=str(payload.get("category") or "").strip() or None,
                    actor="Staff",
                )
                return _json_response(result)
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/outbound/email")
        def outbound_email_api():
            try:
                from outbound_actions import send_email_with_consent

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                store = _local_store()
                result = send_email_with_consent(
                    to=str(payload.get("to") or ""),
                    subject=str(payload.get("subject") or ""),
                    body=str(payload.get("body") or ""),
                    consent_text=str(payload.get("consentText") or ""),
                    actor=str(payload.get("actor") or "Staff"),
                    store=store,
                    dry_run=bool(payload.get("dryRun")),
                )
                return _json_response(result)
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/outbound/qb-export")
        def outbound_qb_export_api():
            try:
                from outbound_actions import export_posting_queue_iif

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                store = _local_store()
                result = export_posting_queue_iif(
                    store.db_path,
                    limit=int(payload.get("limit") or 200),
                    consent_text=str(payload.get("consentText") or ""),
                    actor=str(payload.get("actor") or "Staff"),
                    store=store,
                )
                return _json_response(result)
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/outbound/claim-packet")
        def outbound_claim_packet_api():
            try:
                from outbound_actions import build_claim_submission_packet

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                store = _local_store()
                result = build_claim_submission_packet(
                    claim_id=str(payload.get("claimId") or payload.get("claim_id") or ""),
                    narrative=str(payload.get("narrative") or payload.get("body") or ""),
                    notes=str(payload.get("notes") or payload.get("query") or ""),
                    consent_text=str(payload.get("consentText") or ""),
                    actor=str(payload.get("actor") or "Staff"),
                    store=store,
                )
                return _json_response(result)
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/outbound/narrative-prep")
        def outbound_narrative_prep_api():
            try:
                from outbound_actions import export_narrative_portal_prep

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                store = _local_store()
                result = export_narrative_portal_prep(
                    claim_id=str(payload.get("claimId") or payload.get("claim_id") or ""),
                    narrative=str(payload.get("narrative") or payload.get("body") or ""),
                    consent_text=str(payload.get("consentText") or ""),
                    actor=str(payload.get("actor") or "Staff"),
                    store=store,
                )
                return _json_response(result)
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/outbound/briefing-email")
        def outbound_briefing_email_api():
            try:
                from outbound_actions import send_staff_briefing_email

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                store = _local_store()
                result = send_staff_briefing_email(
                    subject=str(payload.get("subject") or "NR2 HAL briefing"),
                    body=str(payload.get("body") or ""),
                    to=str(payload.get("to") or ""),
                    consent_text=str(payload.get("consentText") or "Scheduled internal briefing"),
                    actor=str(payload.get("actor") or "HAL"),
                    store=store,
                )
                return _json_response(result)
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.get("/api/outbound/audit")
        def outbound_audit_api():
            try:
                from outbound_actions import list_outbound_audit

                store = _local_store()
                limit = int(bottle.request.query.get("limit") or 15)
                return _json_response(list_outbound_audit(store, limit=limit))
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.get("/api/outbound/qbo-status")
        def outbound_qbo_status_api():
            try:
                from outbound_actions import quickbooks_online_status

                return _json_response(quickbooks_online_status())
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/outbound/qbo-post")
        def outbound_qbo_post_api():
            try:
                from outbound_actions import post_qbo_journal_with_consent

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                store = _local_store()
                result = post_qbo_journal_with_consent(
                    store.db_path,
                    limit=int(payload.get("limit") or 25),
                    consent_text=str(payload.get("consentText") or ""),
                    actor=str(payload.get("actor") or "Staff"),
                    store=store,
                    dry_run=bool(payload.get("dryRun")),
                )
                return _json_response(result)
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/outbound/payer-portal-rpa")
        def outbound_payer_portal_rpa_api():
            try:
                from outbound_actions import build_payer_portal_rpa_with_consent

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                store = _local_store()
                result = build_payer_portal_rpa_with_consent(
                    claim_id=str(payload.get("claimId") or payload.get("claim_id") or ""),
                    payer=str(payload.get("payer") or ""),
                    portal_url=str(payload.get("portalUrl") or payload.get("portal_url") or ""),
                    narrative=str(payload.get("narrative") or payload.get("body") or ""),
                    consent_text=str(payload.get("consentText") or ""),
                    actor=str(payload.get("actor") or "Staff"),
                    store=store,
                )
                return _json_response(result)
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/outbound/softdent-writeback")
        def outbound_softdent_writeback_api():
            try:
                from outbound_actions import queue_softdent_writeback_with_consent

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                store = _local_store()
                inner = payload.get("payload")
                result = queue_softdent_writeback_with_consent(
                    action=str(payload.get("action") or "note"),
                    payload=inner if isinstance(inner, dict) else {},
                    consent_text=str(payload.get("consentText") or ""),
                    actor=str(payload.get("actor") or "Staff"),
                    store=store,
                )
                return _json_response(result)
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.get("/api/outbound/softdent-writeback-status")
        def outbound_softdent_writeback_status_api():
            try:
                from outbound_actions import softdent_writeback_status

                return _json_response(softdent_writeback_status())
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.get("/api/employee/status")
        def employee_status_api():
            try:
                from employee_actions import get_employee_status
                from local_store import LocalStore

                store = LocalStore(NR2_DATA_DIR)
                target = int(bottle.request.query.get("targetLevel") or 7)
                return _json_response(get_employee_status(store, target_level=target))
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.get("/api/employee/work-log")
        def employee_work_log_api():
            try:
                from employee_actions import list_employee_work_log
                from local_store import LocalStore

                store = LocalStore(NR2_DATA_DIR)
                limit = int(bottle.request.query.get("limit") or 20)
                return _json_response(list_employee_work_log(store, limit=limit))
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/employee/work-log")
        def employee_work_log_append_api():
            try:
                from employee_actions import append_employee_work_log
                from local_store import LocalStore

                store = LocalStore(NR2_DATA_DIR)
                payload = bottle.request.json or {}
                result = append_employee_work_log(
                    store,
                    action=str(payload.get("action") or "work"),
                    summary=str(payload.get("summary") or ""),
                    level=int(payload.get("level") or 1),
                    actor=str(payload.get("actor") or "HAL"),
                    result=payload.get("result") if isinstance(payload.get("result"), dict) else {},
                )
                return _json_response(result)
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/employee/shift")
        def employee_shift_api():
            try:
                from employee_actions import run_employee_shift
                from local_store import LocalStore

                store = LocalStore(NR2_DATA_DIR)
                payload = bottle.request.json or {}
                result = run_employee_shift(
                    store.db_path,
                    store=store,
                    target_level=int(payload.get("targetLevel") or 7),
                    dry_run=bool(payload.get("dryRun")),
                )
                return _json_response(result)
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

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

        @app.get("/api/hal-tts/status")
        def hal_tts_status_api():
            bottle.response.content_type = "application/json"
            bottle.response.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
            try:
                from miranda_tts import tts_status

                return json.dumps(tts_status())
            except Exception as exc:
                return json.dumps({"ok": False, "error": str(exc)})

        @app.post("/api/hal-tts")
        def hal_tts_api():
            bottle.response.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
            try:
                from miranda_tts import parse_tts_request, synthesize_demo_sync, synthesize_segments_sync

                raw = bottle.request.body.read() if bottle.request.body else b""
                payload = parse_tts_request(raw)
                if payload.get("demo"):
                    audio = synthesize_demo_sync()
                else:
                    segments = payload.get("segments")
                    if not isinstance(segments, list) or not segments:
                        bottle.response.status = 400
                        bottle.response.content_type = "application/json"
                        return json.dumps({"error": "segments or demo required"})
                    audio = synthesize_segments_sync(segments)
                bottle.response.content_type = "audio/mpeg"
                return audio
            except Exception as exc:
                bottle.response.status = 500
                bottle.response.content_type = "application/json"
                return json.dumps({"error": str(exc)})

        @app.get("/")
        def index():
            if not _desktop_access_ok():
                bottle.abort(403, _desktop_only_html())
            if not server.root_path:
                return ""
            _maybe_set_desktop_cookie()
            bottle.response.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
            bottle.response.set_header("Pragma", "no-cache")
            bottle.response.set_header("Expires", 0)
            return bottle.static_file("index.html", root=server.root_path)

        @app.get("/index.html")
        def index_html():
            if not _desktop_access_ok():
                bottle.abort(403, _desktop_only_html())
            if not server.root_path:
                return ""
            _maybe_set_desktop_cookie()
            bottle.response.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
            bottle.response.set_header("Pragma", "no-cache")
            bottle.response.set_header("Expires", 0)
            return bottle.static_file("index.html", root=server.root_path)

        @app.route("/<file:path>")
        def asset(file):
            if not _desktop_access_ok():
                bottle.abort(403, _desktop_only_html())
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
