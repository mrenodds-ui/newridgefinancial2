"""NR2 loopback HTTP server — serves site/ with index.html at /."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone

from pathlib import Path

import bottle

from webview.http import BottleServer, ThreadedAdapter, _get_random_port, logger
from webview.util import abspath, is_app, is_local_url


class NR2SSLWSGIRefServer(bottle.ServerAdapter):
    """Loopback HTTPS for NR2 — persistent cert/key paths, no TLS renegotiation."""

    def run(self, handler):  # pragma: no cover
        import socket
        import ssl
        from socketserver import ThreadingMixIn
        from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

        adapter = self

        class FixedHandler(WSGIRequestHandler):
            def address_string(self) -> str:
                return self.client_address[0]

            def log_request(*args, **kwargs):
                if not adapter.quiet:
                    return WSGIRequestHandler.log_request(*args, **kwargs)

        class ThreadedWSGIServer(ThreadingMixIn, WSGIServer):
            daemon_threads = True

        handler_cls = self.options.get("handler_class", FixedHandler)
        server_cls = self.options.get("server_class", ThreadedWSGIServer)

        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
        no_reneg = getattr(ssl, "OP_NO_RENEGOTIATION", 0)
        if no_reneg:
            ssl_context.options |= no_reneg
        ssl_context.load_cert_chain(self.pywebview_certfile, self.pywebview_keyfile)

        self.srv = make_server(self.host, self.port, handler, server_cls, handler_cls)
        self.srv.socket = ssl_context.wrap_socket(self.srv.socket, server_side=True)
        self.port = self.srv.server_port
        try:
            self.srv.serve_forever()
        except KeyboardInterrupt:
            self.srv.server_close()
            raise

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
_browser_session_token: str | None = None
_site_root: Path | None = None
_workstation_show_fn = None


def set_workstation_show_callback(fn) -> None:
    global _workstation_show_fn
    _workstation_show_fn = fn


def set_desktop_session_token(token: str | None) -> None:
    global _desktop_session_token
    _desktop_session_token = str(token) if token else None


def set_browser_session_token(token: str | None) -> None:
    global _browser_session_token
    _browser_session_token = str(token) if token else None


def ensure_browser_session_token() -> str:
    global _browser_session_token
    if not _browser_session_token:
        _browser_session_token = uuid.uuid4().hex
    return _browser_session_token


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


def _state_changing_request() -> bool:
    method = (bottle.request.method or "GET").upper()
    return method in ("POST", "PUT", "DELETE", "PATCH")


def _request_browser_session_token() -> str | None:
    header = bottle.request.headers.get("X-NR2-Session-Token")
    if header:
        return str(header).strip()
    refresh = bottle.request.headers.get("X-NR2-Refresh-Token")
    if refresh:
        return str(refresh).strip()
    cookie = bottle.request.get_cookie("nr2st")
    if cookie:
        return str(cookie).strip()
    return None


_import_overrides: dict[str, dict] = {}
_readiness_cache: dict[str, Any] = {"payload": None, "syncCompletedAt": None, "cachedAt": 0.0}
_READINESS_CACHE_TTL_SEC = 45.0


def _get_import_readiness(*, operation: str | None = None) -> dict:
    from import_diagnostics import assess_import_readiness
    import time

    with _sync_lock:
        sync_state = dict(_sync_state)
    sync_completed_at = sync_state.get("completedAt")
    now = time.time()
    cached = _readiness_cache.get("payload")
    cached_at = float(_readiness_cache.get("cachedAt") or 0.0)
    cached_sync = _readiness_cache.get("syncCompletedAt")
    if (
        cached
        and not operation
        and cached_sync == sync_completed_at
        and (now - cached_at) < _READINESS_CACHE_TTL_SEC
    ):
        readiness = dict(cached)
    else:
        readiness = assess_import_readiness(sync_state=sync_state, operation=operation)
        if not operation:
            _readiness_cache["payload"] = dict(readiness)
            _readiness_cache["syncCompletedAt"] = sync_completed_at
            _readiness_cache["cachedAt"] = now
    token = _request_browser_session_token() or _browser_session_token or ""
    override = _import_overrides.get(str(token))
    if override and float(override.get("expires") or 0) > datetime.now(timezone.utc).timestamp():
        readiness = {
            **readiness,
            "ok": True,
            "level": "fresh",
            "override": True,
            "overrideReasonHash": override.get("reason_hash"),
            "overrideExpires": override.get("expires"),
        }
    return readiness


def _coerce_amount(payload: dict) -> float | None:
    for key in ("amount", "paidAmount", "totalAmount", "variance", "balance"):
        if key in payload and payload[key] is not None:
            try:
                return float(payload[key])
            except (TypeError, ValueError):
                continue
    return None


def _audit_mutation(action: str, *, detail: dict | None = None, actor: str | None = None) -> None:
    try:
        from nr2_audit_log import FINANCIAL_MUTATION_ACTIONS, append_audit_event, append_financial_mutation

        body: dict = {}
        path = ""
        try:
            path = bottle.request.path or ""
            raw = bottle.request.body.read() if bottle.request.body else b""
            if raw:
                parsed = json.loads(raw.decode("utf-8") or "{}")
                if isinstance(parsed, dict):
                    body = parsed
        except Exception:
            pass
        resolved_actor = str(
            actor
            or body.get("actor")
            or body.get("reviewerActor")
            or body.get("reviewer")
            or body.get("enabledBy")
            or "Staff"
        )
        hal_involved = str(resolved_actor).upper() == "HAL" or bool(body.get("halInvolved"))
        audit_detail = detail if detail is not None else body
        kind = str(action or "unknown")
        path_l = (path or "").lower()
        if kind not in FINANCIAL_MUTATION_ACTIONS:
            if "consent" in path_l or "consent" in kind.lower():
                kind = "consent_action"
            elif "outbound" in path_l:
                kind = "hal_outbound_consent"
            elif "claim" in path_l and ("post" in path_l or "action" in path_l or "card" in path_l):
                kind = "claim_action"
        if isinstance(audit_detail, dict):
            audit_detail = dict(audit_detail)
            audit_detail.setdefault("kind", kind)
        append_audit_event(
            kind,
            actor=resolved_actor,
            detail=audit_detail,
            path=path or None,
        )
        if kind in FINANCIAL_MUTATION_ACTIONS:
            result_detail = audit_detail if isinstance(audit_detail, dict) else {}
            append_financial_mutation(
                kind,
                actor=resolved_actor,
                patient_id=str(result_detail.get("patientId") or result_detail.get("patient_id") or "") or None,
                before=result_detail.get("before") if isinstance(result_detail.get("before"), dict) else None,
                after=result_detail.get("after") if isinstance(result_detail.get("after"), dict) else result_detail,
                amount=_coerce_amount(result_detail),
                hal_involved=hal_involved,
                detail=result_detail,
                path=path or None,
            )
    except Exception:
        pass


def _browser_api_request() -> bool:
    path = bottle.request.path or "/"
    return path.startswith("/api/")


def _browser_mutation_auth_ok() -> bool:
    from nr2_browser_security import mutation_auth_failure_reason

    if not _browser_app():
        return True
    if not _state_changing_request():
        return True
    path = bottle.request.path or "/"
    method = (bottle.request.method or "GET").upper()
    if path.startswith("/js_api/"):
        return True
    if path == "/api/hub/notify" and method == "POST":
        from hal_hub import hub_notify_access_ok

        if hub_notify_access_ok():
            return True
    if path == "/api/webhooks/website-appointment" and method == "POST":
        # Shared-secret validated in handler (Gravity Forms / tunnel).
        return True
    if not _loopback_request():
        return False
    expected = _browser_session_token or ensure_browser_session_token()
    return mutation_auth_failure_reason(expected) is None


def _browser_mutation_auth_reason() -> str:
    from nr2_browser_security import mutation_auth_failure_reason

    expected = _browser_session_token or ensure_browser_session_token()
    return mutation_auth_failure_reason(expected) or "token_invalid"


def _require_imports_for_posting():
    gate = _require_import_readiness_level("fresh", for_posting=True)
    return gate


def _require_pilot_posting_gate(operation: str):
    from nr2_pilot import check_posting_gate

    denied = check_posting_gate(operation)
    if denied:
        return _json_response(denied, status=403)
    return None


def _require_import_readiness_level(required_level: str = "fresh", *, for_posting: bool = False):
    from nr2_browser_security import abort_import_read

    readiness = _get_import_readiness()
    level = str(readiness.get("level") or "unknown")
    # Moonshot Phase 1: "connected" = system up — allow fresh/degraded/stale/syncing.
    # Only block when readiness itself is unavailable (unknown with no payload).
    if required_level == "connected":
        if level == "unknown" and not readiness:
            abort_import_read(readiness or {"ok": False, "level": "unknown"})
        return None
    if required_level == "fresh" and level != "fresh":
        if for_posting:
            return _json_response({"ok": False, **readiness}, status=409)
        abort_import_read(readiness)
    return None


def _lan_hal_hub_access_ok() -> bool:
    """Allow workstation clients on the LAN to reach hub relay APIs without desktop cookie."""
    path = bottle.request.path or "/"
    method = (bottle.request.method or "GET").upper()
    if path.startswith("/api/hal-hub"):
        return True
    if path in ("/api/office-channel",) and method in ("GET", "POST", "OPTIONS"):
        return True
    if path in ("/api/hub/notify", "/api/hub/last-broadcast", "/api/hub/status"):
        if method == "OPTIONS":
            return True
        if path == "/api/hub/notify" and method == "POST":
            from hal_hub import hub_notify_access_ok

            return hub_notify_access_ok()
        if path in ("/api/hub/last-broadcast", "/api/hub/status") and method == "GET":
            from hal_hub import hub_last_broadcast_access_ok

            return hub_last_broadcast_access_ok()
    if path == "/api/workstation/show" and method in ("POST", "OPTIONS") and _loopback_request():
        return True
    if path == "/api/webhooks/website-appointment" and method in ("POST", "OPTIONS"):
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
        os.environ.pop("NR2_WORKSTATION_APP", None)


_WORKSTATION_ASSET_FILES = frozenset(
    {
        "workstation-page.js",
        "workstation-message-popup.js",
        "sidenotes-hub.js",
    }
)


def _workstation_asset_blocked(path: str) -> bool:
    """Financial / desktop programs must not serve workstation UI on the same origin."""
    if _workstation_app():
        return False
    norm = (path or "").lstrip("/")
    if not norm:
        return False
    if norm == "workstation" or norm.startswith("workstation/"):
        return True
    base = norm.split("/")[-1]
    return base in _WORKSTATION_ASSET_FILES


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


def _loopback_secured() -> bool:
    return _browser_app() or _workstation_app()


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
        _audit_mutation("refresh_imports_complete", detail={"status": "success", "resultKeys": list(result.keys()) if isinstance(result, dict) else []})
    except Exception as exc:
        with _sync_lock:
            _sync_state = {
                "status": "failed",
                "startedAt": _sync_state.get("startedAt"),
                "completedAt": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
                "result": None,
            }
        _audit_mutation("refresh_imports_complete", detail={"status": "failed", "error": str(exc)})


class NR2BottleServer(BottleServer):
    """pywebview BottleServer with / → index.html (fixes HTTP 500 on root URL)."""

    @classmethod
    def start_server(cls, urls, http_port, keyfile=None, certfile=None, bind_host: str | None = None):
        from nr2_startup_checks import require_loopback_bind_host

        host = str(bind_host or os.environ.get("NR2_BIND_HOST", "127.0.0.1")).strip() or "127.0.0.1"
        require_loopback_bind_host(host)
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
            import hashlib
            import json as _json

            from nr2_browser_security import (
                abort_browser_auth,
                bind_session_user_agent,
                financial_read_path,
                host_allowed,
                register_browser_session,
                session_vault,
                token_fingerprint,
            )
            from nr2_rate_limit import classify_route, is_allowed, is_rate_limit_exempt

            if not _desktop_access_ok():
                bottle.abort(403, _desktop_only_html())
            if _loopback_secured() and _browser_api_request() and not host_allowed():
                abort_browser_auth("host_rejected", "Host header not allowed for NR2 loopback.")
            active_token = _browser_session_token or _desktop_session_token
            if _loopback_secured() and active_token:
                # Register once; subsequent requests only refresh UA binding.
                if session_vault().has_session(active_token):
                    bind_session_user_agent(active_token)
                else:
                    register_browser_session(active_token)
            if _loopback_secured() and _browser_api_request():
                path = bottle.request.path or ""
                if not is_rate_limit_exempt(path):
                    token = _request_browser_session_token() or active_token or ""
                    route_class = classify_route(path, bottle.request.method or "GET")
                    ok, retry = is_allowed(token_fingerprint(token), route_class)
                    if not ok:
                        bottle.response.content_type = "application/json"
                        bottle.response.headers["Retry-After"] = str(retry)
                        bottle.abort(429, _json.dumps({"ok": False, "error": "rate_limited", "retryAfter": retry}))
            if _browser_app() and _state_changing_request() and not _browser_mutation_auth_ok():
                reason = _browser_mutation_auth_reason()
                abort_browser_auth(
                    reason,
                    "Loopback mutation auth failed.",
                    recovery_token=(_browser_session_token or ensure_browser_session_token())
                    if reason in ("token_invalid", "binding_invalid")
                    else None,
                )
            if _browser_app() and bottle.request.method == "GET":
                from nr2_browser_security import system_status_path

                path = bottle.request.path or ""
                if system_status_path(path):
                    # Tier-2 telemetry: system up only (allow degraded imports).
                    gate = _require_import_readiness_level("connected")
                    if gate is not None:
                        return gate
                elif financial_read_path(path):
                    # Tier-1 money/PHI: require fresh imports.
                    gate = _require_import_readiness_level("fresh")
                    if gate is not None:
                        return gate
            return None

        @app.hook("after_request")
        def _audit_financial_reads():
            from nr2_audit_log import append_read_audit
            from nr2_browser_security import financial_read_path, token_fingerprint
            from nr2_rbac import current_role

            if not _browser_app():
                return
            if bottle.request.method != "GET":
                return
            path = bottle.request.path or ""
            if not financial_read_path(path):
                return
            token = _request_browser_session_token() or _browser_session_token or ""
            append_read_audit(
                token_fingerprint=token_fingerprint(token),
                path=path,
                role=current_role(),
                params=dict(bottle.request.params) if bottle.request.params else None,
            )

        @app.hook("after_request")
        def _browser_security_headers():
            from nr2_browser_security import apply_browser_security_headers, maybe_rotate_session_token

            if not _loopback_secured():
                return
            rotated = None
            global _browser_session_token
            if _browser_session_token:
                new_token, did = maybe_rotate_session_token(_browser_session_token)
                if did:
                    _browser_session_token = new_token
                    rotated = new_token
            apply_browser_security_headers(rotated)

        @app.hook("after_request")
        def _hal_hub_cors_headers():
            path = bottle.request.path or ""
            if path.startswith("/api/hal-hub") or path in ("/api/office-channel", "/api/hub/notify", "/api/hub/last-broadcast"):
                bottle.response.headers["Access-Control-Allow-Origin"] = "*"
                bottle.response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
                bottle.response.headers["Access-Control-Allow-Headers"] = (
                    "Origin, Accept, Content-Type, X-Requested-With, X-Hub-Token"
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
                from hal_hub import resolve_hub_data_dir, resolve_hal_hub_url, resolve_hub_token

                build_manifest = {}
                try:
                    build_path = (_site_root or Path(__file__).resolve().parent / "site") / "nr2-build.json"
                    if build_path.is_file():
                        build_manifest = json.loads(build_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    build_manifest = {}

                asset_version = str(
                    build_manifest.get("assetVersion") or build_manifest.get("BUILD_ID") or ""
                ).strip()
                schema_version = str(
                    build_manifest.get("schemaVersion") or asset_version or ""
                ).strip()

                payload = {
                    "mode": "workstation" if _workstation_app() else "financial",
                    "program": "nr2-workstation" if _workstation_app() else "nr2-financial",
                    "financialOnly": not _workstation_app(),
                    "version": "2.0",
                    "importMode": bundle.get("importMode"),
                    "runtimeAccess": True,
                    "halHubUrl": resolve_hal_hub_url(),
                    "officeHubData": str(resolve_hub_data_dir()),
                    "hubToken": resolve_hub_token(),
                }
                if asset_version:
                    payload["assetVersion"] = asset_version
                if schema_version:
                    payload["designSchemaVersion"] = schema_version
                    payload["schemaVersion"] = schema_version
                if _browser_app():
                    token = ensure_browser_session_token()
                    from nr2_browser_security import bind_session_user_agent

                    bind_session_user_agent(token)
                    from nr2_browser_security import register_browser_session

                    register_browser_session(token)
                    readiness = _get_import_readiness()
                    payload["sessionToken"] = token
                    payload["csrfToken"] = token
                    payload["importReadiness"] = readiness
                    from nr2_settings_store import read_cloud_hal_settings
                    from nr2_rbac import app_info_rbac

                    payload["cloudHal"] = read_cloud_hal_settings(_local_store())
                    payload.update(app_info_rbac())
                    from nr2_pilot import pilot_info

                    payload["pilot"] = pilot_info()
                return _json_response(payload)
            except Exception as exc:
                payload = {"mode": "loopback", "version": "2.0", "error": str(exc)}
                if _browser_app():
                    token = ensure_browser_session_token()
                    payload["sessionToken"] = token
                    payload["csrfToken"] = token
                    try:
                        payload["importReadiness"] = _get_import_readiness()
                    except Exception:
                        pass
                return _json_response(payload)

        @app.get("/api/import-readiness")
        def import_readiness_api():
            operation = str(bottle.request.params.get("operation") or "").strip() or None
            return _json_response(_get_import_readiness(operation=operation))

        @app.get("/api/hal/import-guard")
        def hal_import_guard_api():
            from nr2_browser_security import classify_financial_query, import_guard_response

            query = str(bottle.request.params.get("q") or bottle.request.params.get("query") or "")
            readiness = _get_import_readiness()
            financial = classify_financial_query(query)
            return _json_response(import_guard_response(readiness, financial_intent=financial))

        @app.post("/api/hal/evaluate-query")
        def hal_evaluate_query_api():
            from employee_actions import get_current_shift_context
            from nr2_hal_gateway import evaluate_query, resolve_lane, route_by_complexity
            from nr2_audit_log import record_hal_session

            if bottle.request.headers.get("X-Direct-Ollama"):
                return _json_response({"ok": False, "error": "direct_ollama_rejected"}, status=403)

            body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(body or "{}")
            query = str(payload.get("query") or "")
            from nr2_hal_gateway import reject_financial_lane_downgrade

            if reject_financial_lane_downgrade(query, bottle.request.headers.get("X-HAL-Model-Override")):
                return _json_response(
                    {"ok": False, "error": "financial_lane_downgrade_rejected", "minimumLane": "reason21b"},
                    status=403,
                )
            from nr2_hal_gateway import APPROVED_LOCAL_MODEL, enforce_approved_local_model

            model_gate = enforce_approved_local_model(
                payload.get("model"),
                override_header=bottle.request.headers.get("X-HAL-Model-Override"),
            )
            if not model_gate.get("ok"):
                return _json_response(model_gate, status=403)
            if payload.get("cloud") or str(payload.get("lane") or "").lower() == "cloud":
                return _json_response(
                    {
                        "ok": False,
                        "error": "cloud_hal_disabled",
                        "approvedModel": APPROVED_LOCAL_MODEL,
                        "detail": "Office HAL is local 32B only",
                    },
                    status=403,
                )
            store = _local_store()
            readiness = _get_import_readiness()
            shift_context = payload.get("shiftContext") if isinstance(payload.get("shiftContext"), dict) else None
            if not shift_context:
                shift_context = get_current_shift_context(store)
            requested_lane = payload.get("lane") or payload.get("requestedLane")
            lane_key = str(requested_lane or route_by_complexity(query, shift_context=shift_context, store=store))
            resolved = resolve_lane(lane_key)
            model = APPROVED_LOCAL_MODEL
            session_id = str(payload.get("sessionId") or payload.get("session_id") or "")
            use_stream = bool(payload.get("stream"))
            if use_stream:
                from nr2_hal_gateway import evaluate_query_stream

                result = evaluate_query_stream(
                    query=query,
                    readiness=readiness,
                    model=model,
                    system_prompt=str(payload.get("systemPrompt") or payload.get("system") or ""),
                    messages=payload.get("messages") if isinstance(payload.get("messages"), list) else None,
                    options=payload.get("options") if isinstance(payload.get("options"), dict) else None,
                    shift_context=shift_context,
                    requested_lane=lane_key,
                    store=store,
                )
            else:
                result = evaluate_query(
                    query=query,
                    readiness=readiness,
                    model=model,
                    system_prompt=str(payload.get("systemPrompt") or payload.get("system") or ""),
                    messages=payload.get("messages") if isinstance(payload.get("messages"), list) else None,
                    options=payload.get("options") if isinstance(payload.get("options"), dict) else None,
                    shift_context=shift_context,
                    requested_lane=lane_key,
                    store=store,
                )
            result["resolvedLane"] = result.get("resolvedLane") or resolved["lane"]
            bottle.response.set_header("X-HAL-Gateway-Enforced", "1")
            bottle.response.set_header("X-HAL-Lane-Used", str(result.get("resolvedLane") or resolved["lane"]))
            if session_id:
                record_hal_session(
                    store,
                    session_id,
                    {
                        "type": "evaluate_query",
                        "lane": result.get("resolvedLane"),
                        "intent": result.get("intent"),
                        "blocked": bool(result.get("blocked")),
                        "error": result.get("error"),
                    },
                )
            if result.get("blocked") or result.get("error") == "HAL_UNAVAILABLE_STALE_DATA":
                return _json_response(result, status=503)
            if not result.get("ok"):
                return _json_response(result, status=502)
            return _json_response(result)

        @app.post("/api/hal/acknowledge-stale")
        def hal_acknowledge_stale_api():
            from nr2_hal_gateway import acknowledge_stale

            body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(body or "{}")
            result = acknowledge_stale(
                _local_store(),
                actor=str(payload.get("actor") or "Staff"),
                reason=str(payload.get("reason") or ""),
            )
            return _json_response(result)

        @app.get("/api/audit/hal-session/<session_id>")
        def audit_hal_session_api(session_id: str):
            from nr2_audit_log import get_hal_session

            return _json_response(get_hal_session(_local_store(), session_id))

        @app.post("/api/audit/explain-block")
        def audit_explain_block_api():
            from nr2_audit_log import explain_hal_block

            body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(body or "{}")
            return _json_response(explain_hal_block(_local_store(), payload))

        @app.post("/api/import-readiness/override")
        def import_readiness_override_api():
            import hashlib

            from nr2_rbac import current_role

            role = current_role()
            if role not in ("office_manager", "admin", "dentist"):
                return _json_response({"ok": False, "error": "insufficient_privilege", "role": role}, status=403)
            body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(body or "{}")
            reason = str(payload.get("reason") or "").strip()
            if len(reason) < 5:
                return _json_response({"ok": False, "error": "reason_required"}, status=400)
            ttl_minutes = min(int(payload.get("ttl_minutes") or payload.get("ttl") or 60), 240)
            token = _request_browser_session_token() or _browser_session_token or ""
            expires = datetime.now(timezone.utc).timestamp() + ttl_minutes * 60
            reason_hash = hashlib.sha256(reason.encode("utf-8")).hexdigest()
            _import_overrides[str(token)] = {
                "expires": expires,
                "reason_hash": reason_hash,
                "scopes": payload.get("scopes") or ["posting", "ar"],
            }
            _audit_mutation("import_readiness_override", detail={"reason_hash": reason_hash, "ttl_minutes": ttl_minutes})
            return _json_response({"ok": True, "expires": expires, "reasonHash": reason_hash})

        @app.get("/api/ollama/tags")
        def ollama_tags_api():
            from integration_health import _probe_ollama

            probe = _probe_ollama()
            names = [str(n) for n in (probe.get("models") or []) if n]
            return _json_response(
                {
                    "ok": bool(probe.get("ok")),
                    "models": [{"name": n} for n in names],
                    "modelCount": len(names),
                    "endpoint": probe.get("endpoint"),
                    "error": probe.get("error"),
                }
            )

        @app.get("/api/health")
        def health_api():
            from import_loader import load_import_bundle
            from integration_health import integration_health_snapshot
            from nr2_db_crypto import db_encryption_enabled
            from nr2_consent_executor import consent_executor_enabled
            from softdent_odbc_extract import read_extract_status

            store = _local_store()
            health = integration_health_snapshot(store)
            sd_extract = read_extract_status()
            ollama_ok = bool((health.get("ollama") or {}).get("ok"))
            db_ok = store.db_path.is_file()
            readiness = _get_import_readiness()
            backup_dir = NR2_DATA_DIR / "backups"
            backup_last = None
            if backup_dir.is_dir():
                backups = sorted(backup_dir.glob("nr2-*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)
                if backups:
                    backup_last = datetime.fromtimestamp(backups[0].stat().st_mtime, tz=timezone.utc).isoformat()
            import_bundle_age_minutes = None
            last_qb_sync = None
            try:
                bundle = load_import_bundle(sync=False)
                loaded_at = bundle.get("loadedAt") or (bundle.get("syncStatus") or {}).get("completedAt")
                if loaded_at:
                    dt = datetime.fromisoformat(str(loaded_at).replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    import_bundle_age_minutes = int((datetime.now(timezone.utc) - dt).total_seconds() / 60)
                qb = bundle.get("quickbooks") if isinstance(bundle.get("quickbooks"), dict) else {}
                last_qb_sync = qb.get("lastSync") or qb.get("syncedAt") or (bundle.get("syncStatus") or {}).get("completedAt")
            except Exception:
                pass
            db_size_mb = None
            if db_ok:
                db_size_mb = round(store.db_path.stat().st_size / (1024 * 1024), 2)
            payload = {
                "ok": db_ok and ollama_ok,
                "db": db_ok,
                "ollama": ollama_ok,
                "importPipeline": readiness.get("level") not in ("expired", "degraded"),
                "readinessLevel": readiness.get("level"),
                "backupLastAt": backup_last,
                "encryptionEnabled": db_encryption_enabled(),
                "lastOdbcExtract": sd_extract.get("lastExtractAt"),
                "softdentOdbcMode": sd_extract.get("lastMode"),
                "softdentSdTablesPopulated": sd_extract.get("populatedTables"),
                "import_bundle_age_minutes": import_bundle_age_minutes,
                "last_qb_sync": last_qb_sync,
                "db_size_mb": db_size_mb,
                "consentExecutorEnabled": consent_executor_enabled(),
            }
            status = 200 if payload["ok"] else 503
            return _json_response(payload, status=status)

        @app.post("/api/audit/log")
        def operator_audit_log_api():
            from operator_audit_store import append_operator_audit

            payload = bottle.request.json or {}
            action = str(payload.get("action") or "").strip()
            if not action:
                return _json_response({"ok": False, "error": "action required"}, status=400)
            store = _local_store()
            with store._connect() as conn:
                row = append_operator_audit(
                    conn,
                    action=action,
                    page_key=str(payload.get("pageKey") or payload.get("page_key") or "").strip() or None,
                    widget_key=str(payload.get("widgetKey") or payload.get("widget_key") or "").strip() or None,
                    detail=payload.get("detail") if isinstance(payload.get("detail"), dict) else None,
                    session_hash=str(payload.get("sessionHash") or payload.get("session_hash") or "").strip() or None,
                )
                conn.commit()
            return _json_response({"ok": True, "record": row})

        @app.get("/api/audit/operator")
        def operator_audit_tail_api():
            from operator_audit_store import read_operator_audit_tail

            limit = int(bottle.request.params.get("limit") or 50)
            store = _local_store()
            with store._connect() as conn:
                items = read_operator_audit_tail(conn, limit=limit)
            return _json_response({"ok": True, "items": items})

        @app.post("/api/sidenote")
        def sidenote_bridge_api():
            from sidenotes_local_store import insert_sidenote_local

            payload = bottle.request.json or {}
            text = str(payload.get("text") or "").strip()
            if not text:
                return _json_response({"ok": False, "error": "text required"}, status=400)
            store = _local_store()
            try:
                with store._connect() as conn:
                    note = insert_sidenote_local(
                        conn,
                        text=text,
                        source=str(payload.get("source") or "workstation"),
                        station=str(payload.get("station") or payload.get("from") or "").strip() or None,
                        timestamp=str(payload.get("timestamp") or "").strip() or None,
                    )
                    conn.commit()
            except ValueError as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=400)
            return _json_response({"ok": True, "note": note})

        @app.get("/api/sidenotes/local")
        def sidenotes_local_api():
            from sidenotes_local_store import list_sidenotes_local

            limit = int(bottle.request.params.get("limit") or 48)
            store = _local_store()
            with store._connect() as conn:
                notes = list_sidenotes_local(conn, limit=limit)
            return _json_response({"ok": True, "notes": notes})

        @app.post("/api/admin/backup-db")
        def backup_db_api():
            from backup_db import run_scheduled_backup
            from nr2_consent_executor import consent_executor_enabled

            if not consent_executor_enabled():
                return _json_response(
                    {
                        "ok": False,
                        "error": "consent_executor_disabled",
                        "message": "Set NR2_CONSENT_EXECUTOR=1 to run backups.",
                    },
                    status=403,
                )
            store = _local_store()
            result = run_scheduled_backup(store)
            status = 200 if result.get("ok") else 500
            return _json_response(result, status=status)

        @app.get("/api/audit-log/mutations")
        def audit_log_mutations_api():
            from nr2_audit_log import read_audit_tail

            limit = int(bottle.request.params.get("limit") or 100)
            return _json_response({"ok": True, "items": read_audit_tail("mutations", limit=limit)})

        @app.get("/api/audit-log/reads")
        def audit_log_reads_api():
            from nr2_audit_log import read_audit_tail
            from nr2_rbac import has_capability

            if not has_capability("read_financial") and not has_capability("read_all"):
                return _json_response({"ok": False, "error": "capability_rejected"}, status=403)
            limit = int(bottle.request.params.get("limit") or 100)
            return _json_response({"ok": True, "items": read_audit_tail("reads", limit=limit)})

        @app.get("/api/clinical-summaries")
        def clinical_summaries_api():
            from nr2_clinical_bridge import load_clinical_context
            from nr2_rbac import has_capability

            limit = int(bottle.request.params.get("limit") or 5)
            patient_id = str(bottle.request.params.get("patientId") or bottle.request.params.get("patient_id") or "").strip()
            patient_name = str(bottle.request.params.get("patientName") or bottle.request.params.get("patient_name") or "").strip()
            ctx = load_clinical_context(
                _local_store(),
                patient_id=patient_id,
                patient_name=patient_name,
                limit=limit,
            )
            read_only = not has_capability("write_clinical")
            return _json_response({**ctx, "source": "clinical-bridge", "readOnly": read_only, "proxyMode": True})

        @app.get("/api/v1/import-readiness")
        def api_v1_import_readiness():
            operation = str(bottle.request.params.get("operation") or "").strip() or None
            return _json_response(_get_import_readiness(operation=operation))

        @app.get("/api/v1/health")
        def api_v1_health():
            return health_api()

        @app.post("/api/webhooks/patient-payment")
        def patient_payment_webhook_api():
            body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(body or "{}")
            _audit_mutation("patient_payment_webhook", detail={"patientId": payload.get("patientId"), "amount": payload.get("amount")})
            return _json_response({"ok": True, "freshnessInvalidated": True, "patientId": payload.get("patientId")})

        @app.post("/api/webhooks/website-appointment")
        def website_appointment_webhook_api():
            """Gravity Forms (or compatible) appointment-request webhook → HAL sidenote."""
            from sidenotes_local_store import insert_sidenote_local
            from website_leads_store import (
                format_lead_sidenote,
                insert_website_lead,
                normalize_gravity_forms_payload,
                webhook_secret_configured,
                webhook_secret_valid,
            )

            provided = (
                bottle.request.headers.get("X-NR2-Webhook-Secret")
                or bottle.request.headers.get("X-Webhook-Secret")
                or bottle.request.params.get("secret")
                or ""
            )
            auth = bottle.request.headers.get("Authorization") or ""
            if auth.lower().startswith("bearer "):
                provided = auth[7:].strip() or provided
            if webhook_secret_configured() and not webhook_secret_valid(provided):
                return _json_response({"ok": False, "error": "invalid_webhook_secret"}, status=403)
            if not webhook_secret_configured() and not _loopback_request():
                return _json_response(
                    {"ok": False, "error": "webhook_secret_required", "hint": "Set NR2_WEBSITE_WEBHOOK_SECRET"},
                    status=403,
                )

            payload: dict = {}
            ctype = str(bottle.request.content_type or "").lower()
            if "application/json" in ctype or (bottle.request.body and not bottle.request.forms):
                raw_body = bottle.request.body.read().decode("utf-8") if bottle.request.body else ""
                if raw_body.strip():
                    try:
                        parsed = json.loads(raw_body)
                        if isinstance(parsed, dict):
                            payload = parsed
                    except json.JSONDecodeError:
                        payload = {"rawBody": raw_body[:4000]}
            if not payload and bottle.request.forms:
                payload = {k: bottle.request.forms.get(k) for k in bottle.request.forms.keys()}
            if not payload and bottle.request.json and isinstance(bottle.request.json, dict):
                payload = dict(bottle.request.json)

            normalized = normalize_gravity_forms_payload(payload)
            if not (normalized.get("name") or normalized.get("email") or normalized.get("phone")):
                return _json_response(
                    {"ok": False, "error": "missing_contact_fields", "hint": "Need name, email, or phone"},
                    status=400,
                )

            store = _local_store()
            sidenote = None
            with store._connect() as conn:
                lead = insert_website_lead(conn, normalized=normalized, source="gravity_forms")
                if not lead.get("duplicate"):
                    note_text = format_lead_sidenote(lead)
                    sidenote = insert_sidenote_local(
                        conn,
                        text=note_text,
                        source="website",
                        station="appointment-request",
                    )
                conn.commit()

            _audit_mutation(
                "website_appointment_webhook",
                detail={
                    "leadId": lead.get("id"),
                    "duplicate": bool(lead.get("duplicate")),
                    "hasEmail": bool(lead.get("email")),
                    "hasPhone": bool(lead.get("phone")),
                },
            )
            return _json_response(
                {
                    "ok": True,
                    "lead": {k: v for k, v in lead.items() if k != "raw_json"},
                    "sidenote": sidenote,
                    "halVisible": True,
                }
            )

        @app.get("/api/website-leads")
        def website_leads_list_api():
            from website_leads_store import list_website_leads

            status = str(bottle.request.params.get("status") or "open").strip()
            if status.lower() in ("all", "*"):
                status_filter = None
            else:
                status_filter = status
            limit = int(bottle.request.params.get("limit") or 50)
            with _local_store()._connect() as conn:
                items = list_website_leads(conn, status=status_filter, limit=limit)
            for item in items:
                item.pop("raw_json", None)
            return _json_response({"ok": True, "items": items, "count": len(items)})

        @app.post("/api/website-leads/<lead_id>/handled")
        def website_leads_handled_api(lead_id: str):
            from website_leads_store import mark_website_lead_handled

            with _local_store()._connect() as conn:
                result = mark_website_lead_handled(conn, lead_id)
                conn.commit()
            if not result.get("ok"):
                return _json_response(result, status=404)
            _audit_mutation("website_lead_handled", detail={"leadId": lead_id})
            return _json_response(result)

        @app.get("/api/ocr-exceptions")
        def ocr_exceptions_list_api():
            from ocr_exceptions_store import list_exceptions

            status = str(bottle.request.params.get("status") or "pending").strip() or None
            with _local_store()._connect() as conn:
                items = list_exceptions(conn, status=status, limit=int(bottle.request.params.get("limit") or 200))
            return _json_response({"ok": True, "items": items, "count": len(items)})

        @app.post("/api/ocr-exceptions/<exc_id>/resolve")
        def ocr_exceptions_resolve_api(exc_id: str):
            from nr2_rbac import has_capability

            if not has_capability("manage_ocr"):
                return _json_response({"ok": False, "error": "capability_rejected"}, status=403)
            body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(body or "{}")
            from ocr_exceptions_store import resolve_exception

            with _local_store()._connect() as conn:
                result = resolve_exception(
                    conn,
                    exc_id,
                    action=str(payload.get("action") or "resolve"),
                    notes=str(payload.get("notes") or payload.get("resolution_notes") or ""),
                )
            _audit_mutation("ocr_exception_resolve", detail={"id": exc_id, "result": result})
            return _json_response(result)

        @app.get("/api/settings/cloud-hal")
        def cloud_hal_settings_get():
            from nr2_settings_store import read_cloud_hal_settings

            return _json_response(read_cloud_hal_settings(_local_store()))

        @app.post("/api/settings/cloud-hal")
        def cloud_hal_settings_post():
            from nr2_rbac import has_capability
            from nr2_settings_store import read_cloud_hal_settings, write_cloud_hal_settings

            body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(body or "{}")
            confirm = str(payload.get("confirm") or "")
            enable = bool(payload.get("enable"))
            if enable and not has_capability("cloud_hal"):
                return _json_response({"ok": False, "error": "insufficient_privilege"}, status=403)
            if enable and confirm != "ENABLE CLOUD HAL":
                return _json_response({"ok": False, "error": "confirm phrase required"}, status=400)
            baa_ack = str(payload.get("baaAcknowledgement") or payload.get("baa_ack") or "").strip()
            if enable and baa_ack != "BAA ON FILE":
                return _json_response({"ok": False, "error": "cloud_hal_baa_required"}, status=400)
            if enable:
                record = write_cloud_hal_settings(
                    _local_store(),
                    enabled=True,
                    enabled_by=str(payload.get("enabledBy") or "Staff"),
                    baa_signed=True,
                )
            else:
                record = write_cloud_hal_settings(
                    _local_store(),
                    enabled=False,
                    enabled_by=str(payload.get("enabledBy") or "Staff"),
                )
            return _json_response({"ok": True, "settings": read_cloud_hal_settings(_local_store()), "record": record})

        @app.post("/api/import-sync-reset")
        def import_sync_reset_api():
            global _sync_state
            with _sync_lock:
                if _sync_state.get("status") != "running":
                    return _json_response({"ok": False, "error": "sync not running"})
                _sync_state = {
                    "status": "idle",
                    "startedAt": None,
                    "completedAt": datetime.now(timezone.utc).isoformat(),
                    "error": "reset by operator",
                    "result": None,
                }
                state = dict(_sync_state)
            _audit_mutation("import_sync_reset", detail=state)
            return _json_response({"ok": True, "state": state})

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
            _audit_mutation("refresh_imports", detail=state)
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
            last_hub_broadcast,
            load_office_channel,
            process_pending,
            record_hub_broadcast,
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
        @app.route("/api/hub/notify", method=["OPTIONS"])
        @app.route("/api/hub/last-broadcast", method=["OPTIONS"])
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

        @app.get("/api/hub/status")
        def hub_cross_status_api():
            try:
                from hal_hub import hub_cross_status

                return _json_response(hub_cross_status())
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.get("/api/hub/last-broadcast")
        def hub_last_broadcast_api():
            try:
                data = last_hub_broadcast()
                return _json_response({"ok": True, **data} if data else {"ok": True})
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/hub/notify")
        def hub_notify_api():
            try:
                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                record_hub_broadcast(payload if isinstance(payload, dict) else {})
                return _json_response({"ok": True, **last_hub_broadcast()})
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

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

        @app.get("/api/payer-reference")
        def payer_reference_api():
            try:
                from payer_reference_store import format_payer_hits, payer_reference_summary, search_payers

                query = str(bottle.request.params.get("q") or bottle.request.params.get("query") or "")
                limit = int(bottle.request.params.get("limit") or 5)
                if query.strip():
                    items = search_payers(query, limit=limit)
                    return _json_response(
                        {
                            "ok": True,
                            "items": items,
                            "count": len(items),
                            "text": format_payer_hits(items),
                        }
                    )
                return _json_response(payer_reference_summary())
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc), "items": [], "count": 0}, status=500)

        @app.get("/api/dental-carrier-catalog")
        def dental_carrier_catalog_api():
            try:
                from us_dental_carrier_catalog import catalog_summary, format_carrier_hits, search_carriers

                query = str(bottle.request.params.get("q") or bottle.request.params.get("query") or "")
                limit = int(bottle.request.params.get("limit") or 8)
                if query.strip():
                    items = search_carriers(query, limit=limit)
                    return _json_response(
                        {
                            "ok": True,
                            "items": items,
                            "count": len(items),
                            "text": format_carrier_hits(items),
                        }
                    )
                return _json_response(catalog_summary())
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc), "items": [], "count": 0}, status=500)

        @app.post("/api/claim-payer-join")
        def claim_payer_join_api():
            try:
                from payer_reference_store import enrich_claims, format_claim_payer_joins

                body = bottle.request.json or {}
                claims = body.get("claims") if isinstance(body, dict) else None
                if not isinstance(claims, list):
                    claims = []
                items = enrich_claims(claims, limit=20)
                joined = [c for c in items if c.get("payerMatch")]
                return _json_response(
                    {
                        "ok": True,
                        "items": items,
                        "count": len(joined),
                        "text": format_claim_payer_joins(claims),
                    }
                )
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc), "items": [], "count": 0}, status=500)

        @app.get("/api/fee-schedule")
        def fee_schedule_api():
            try:
                from fee_schedule_store import fee_schedule_summary, format_fee_hits, lookup_fees

                query = str(bottle.request.params.get("q") or bottle.request.params.get("query") or "")
                limit = int(bottle.request.params.get("limit") or 3)
                if query.strip():
                    items = lookup_fees(query, limit=limit)
                    return _json_response(
                        {
                            "ok": True,
                            "items": items,
                            "count": len(items),
                            "text": format_fee_hits(items),
                        }
                    )
                return _json_response(fee_schedule_summary())
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc), "items": [], "count": 0}, status=500)

        @app.get("/api/eligibility-cache")
        def eligibility_cache_list_api():
            try:
                from eligibility_cache_store import eligibility_cache_summary, format_eligibility_hits, list_eligibility_entries, search_eligibility_cache

                query = str(bottle.request.params.get("q") or bottle.request.params.get("query") or "")
                limit = int(bottle.request.params.get("limit") or 10)
                if query.strip():
                    items = search_eligibility_cache(query, limit=limit)
                else:
                    items = list_eligibility_entries(limit=limit, fresh_only=True)
                return _json_response(
                    {
                        "ok": True,
                        "items": items,
                        "count": len(items),
                        "text": format_eligibility_hits(items),
                        "summary": eligibility_cache_summary(),
                    }
                )
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc), "items": [], "count": 0}, status=500)

        @app.post("/api/eligibility-cache")
        def eligibility_cache_upsert_api():
            try:
                from eligibility_cache_store import upsert_eligibility_entry

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                entry_payload = payload.get("entry") if isinstance(payload.get("entry"), dict) else payload
                return _json_response(upsert_eligibility_entry(entry_payload))
            except ValueError as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=400)
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/eligibility-cache/fetch")
        def eligibility_cache_fetch_api():
            try:
                from clearinghouse_eligibility_adapter import fetch_eligibility_271

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                request_payload = payload.get("request") if isinstance(payload.get("request"), dict) else payload
                return _json_response(fetch_eligibility_271(request_payload))
            except ValueError as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=400)
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.get("/api/eligibility-cache/status")
        def eligibility_cache_status_api():
            try:
                from clearinghouse_eligibility_adapter import clearinghouse_status

                return _json_response({"ok": True, **clearinghouse_status()})
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.get("/api/tesia-payers")
        def tesia_payers_api():
            try:
                from tesia_payer_list_store import format_tesia_hits, payer_list_summary, search_tesia_payers

                query = str(bottle.request.params.get("q") or bottle.request.params.get("query") or "")
                limit = int(bottle.request.params.get("limit") or 8)
                kansas_only = str(bottle.request.params.get("kansas") or "").strip().lower() in (
                    "1",
                    "true",
                    "yes",
                )
                if query.strip() or kansas_only:
                    items = search_tesia_payers(query, limit=limit, kansas_only=kansas_only)
                    return _json_response(
                        {
                            "ok": True,
                            "items": items,
                            "count": len(items),
                            "text": format_tesia_hits(items),
                        }
                    )
                return _json_response(payer_list_summary())
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc), "items": [], "count": 0}, status=500)

        @app.post("/api/tesia-payers/import")
        def tesia_payers_import_api():
            try:
                from tesia_payer_list_store import import_payer_list_file, import_payer_rows

                body = bottle.request.json or {}
                if not isinstance(body, dict):
                    body = {}
                merge = bool(body.get("merge", True))
                if body.get("path") or body.get("file"):
                    return _json_response(
                        import_payer_list_file(str(body.get("path") or body.get("file")), merge=merge)
                    )
                rows = body.get("rows") or body.get("payers") or body.get("items")
                if isinstance(rows, list):
                    return _json_response(import_payer_rows(rows, merge=merge))
                return _json_response(
                    {
                        "ok": False,
                        "error": "path_or_rows_required",
                        "hint": "POST {path: 'data/imports/tesia_export.csv'} or {rows: [...]}",
                    },
                    status=400,
                )
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/tesia-payers/join-softdent")
        def tesia_payers_join_softdent_api():
            try:
                from softdent_tesia_join import apply_softdent_tesia_join, build_join_plan, format_join_summary

                body = bottle.request.json or {}
                if not isinstance(body, dict):
                    body = {}
                dry_run = bool(body.get("dryRun") or body.get("dry_run"))
                if dry_run:
                    plan = build_join_plan()
                    return _json_response(
                        {
                            "ok": True,
                            "dryRun": True,
                            "counts": plan.get("counts"),
                            "text": format_join_summary({"counts": plan.get("counts"), "kansasExact": [
                                r for r in plan.get("exactMatches") or [] if r.get("kansasRelevant")
                            ][:10]}),
                            "exactMatches": (plan.get("exactMatches") or [])[:20],
                            "expandFromSoftDent": (plan.get("expandFromSoftDent") or [])[:20],
                        }
                    )
                result = apply_softdent_tesia_join(
                    write_payer_reference=bool(body.get("writePayerReference", True)),
                    expand_tesia=bool(body.get("expandTesia", True)),
                )
                result["text"] = format_join_summary(result)
                return _json_response(result)
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

        @app.get("/api/hal-learning/status")
        def hal_learning_status_api():
            try:
                from hal_learning import learning_status

                return _json_response(learning_status())
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/hal-learning/session")
        def hal_session_context_api():
            try:
                from hal_learning import update_session_context

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                return _json_response(
                    update_session_context(
                        claim_id=str(payload.get("claimId") or payload.get("claim_id") or ""),
                        narrative_id=str(payload.get("narrativeId") or payload.get("narrative_id") or ""),
                        page=str(payload.get("page") or ""),
                        topic=str(payload.get("topic") or ""),
                        payer=str(payload.get("payer") or ""),
                    )
                )
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
                appeal_payload = payload.get("appealPacket") if isinstance(payload.get("appealPacket"), dict) else None
                result = build_claim_submission_packet(
                    claim_id=str(payload.get("claimId") or payload.get("claim_id") or ""),
                    narrative=str(payload.get("narrative") or payload.get("body") or ""),
                    notes=str(payload.get("notes") or payload.get("query") or ""),
                    consent_text=str(payload.get("consentText") or ""),
                    actor=str(payload.get("actor") or "Staff"),
                    store=store,
                    appeal_packet=appeal_payload,
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

        @app.get("/api/employee/current-shift")
        def employee_current_shift_api():
            try:
                from employee_actions import get_current_shift_context

                return _json_response(get_current_shift_context(_local_store()))
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.get("/api/employee/standing-consent/<action_type>")
        def employee_standing_consent_api(action_type: str):
            try:
                from employee_actions import check_action_consent

                amount_raw = bottle.request.params.get("amount")
                amount = float(amount_raw) if amount_raw not in (None, "") else None
                employee_id = str(bottle.request.params.get("employeeId") or "HAL")
                return _json_response(
                    check_action_consent(employee_id, action_type, amount, store=_local_store())
                )
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/employee/clock-in")
        def employee_clock_in_api():
            try:
                from employee_actions import clock_in_shift

                payload = bottle.request.json or {}
                return _json_response(
                    clock_in_shift(
                        _local_store(),
                        employee_id=str(payload.get("employeeId") or "HAL"),
                        tier=int(payload.get("tier") or payload.get("targetLevel") or 7),
                    )
                )
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.get("/api/hal/lane-history")
        def hal_lane_history_api():
            from nr2_hal_gateway import list_lane_history

            limit = int(bottle.request.params.get("limit") or 20)
            return _json_response(list_lane_history(_local_store(), limit=limit))

        @app.post("/api/collections/generate-queue")
        def collections_generate_queue_api():
            from hal_employee_workflows import generate_collections_queue

            payload = bottle.request.json or {}
            limit = int(payload.get("limit") or 25)
            return _json_response(generate_collections_queue(_local_store(), limit=limit))

        @app.get("/api/collections/queue")
        def collections_queue_api():
            from hal_employee_workflows import list_collections_queue

            limit = int(bottle.request.params.get("limit") or 50)
            return _json_response(list_collections_queue(_local_store(), limit=limit))

        @app.post("/api/collections/letter")
        def collections_letter_api():
            from hal_employee_workflows import generate_collection_letter

            payload = bottle.request.json or {}
            return _json_response(generate_collection_letter(_local_store(), payload))

        @app.post("/api/collections/schedule-call")
        def collections_schedule_call_api():
            from hal_employee_workflows import schedule_call_task

            payload = bottle.request.json or {}
            return _json_response(schedule_call_task(_local_store(), payload))

        @app.post("/api/collections/queue-status")
        def collections_queue_status_api():
            from hal_employee_workflows import update_collections_queue_status

            payload = bottle.request.json or {}
            return _json_response(update_collections_queue_status(_local_store(), payload))

        @app.post("/api/import/heal")
        def import_heal_api():
            from import_healing import heal_import_pipeline

            payload = bottle.request.json or {}
            force = bool((payload or {}).get("force"))
            return _json_response(heal_import_pipeline(force=force))

        @app.post("/api/era/parse")
        def era_parse_api():
            from hal_employee_workflows import parse_era_import

            payload = bottle.request.json or {}
            return _json_response(parse_era_import(_local_store(), payload))

        @app.post("/api/deposits/analyze")
        def deposits_analyze_api():
            from hal_employee_workflows import draft_deposit_reconciliation

            payload = bottle.request.json or {}
            return _json_response(draft_deposit_reconciliation(_local_store(), payload))

        @app.post("/api/deposits/draft-recon")
        def deposits_draft_recon_api():
            from hal_employee_workflows import draft_deposit_reconciliation

            payload = bottle.request.json or {}
            result = draft_deposit_reconciliation(_local_store(), payload)
            _audit_mutation("deposit_reconciliation", detail=result if isinstance(result, dict) else {"result": result})
            return _json_response(result)

        @app.post("/api/claims/preflight")
        def claims_preflight_api():
            from hal_employee_workflows import stage_claim_preflight

            payload = bottle.request.json or {}
            return _json_response(stage_claim_preflight(_local_store(), payload))

        @app.post("/api/claims/appeal-packet")
        def claims_appeal_packet_api():
            from hal_employee_workflows import build_appeal_packet

            payload = bottle.request.json or {}
            return _json_response(build_appeal_packet(_local_store(), payload))

        @app.post("/api/fee/scrub-paid")
        def fee_scrub_paid_api():
            from hal_employee_workflows import scrub_fee_vs_paid

            payload = bottle.request.json or {}
            return _json_response(scrub_fee_vs_paid(payload, store=_local_store()))

        @app.post("/api/eob/match")
        def eob_match_api():
            from hal_employee_workflows import process_eob_match

            payload = bottle.request.json or {}
            result = process_eob_match(_local_store(), payload)
            _audit_mutation("eob_era_match", detail=result if isinstance(result, dict) else {"result": result})
            return _json_response(result)

        @app.post("/api/posting/batch-approve")
        def posting_batch_approve_api():
            from hal_employee_workflows import batch_approve_postings

            payload = bottle.request.json or {}
            result = batch_approve_postings(_local_store(), payload)
            _audit_mutation(
                "posting_batch_approve",
                detail=result if isinstance(result, dict) else {"result": result},
                actor=str(payload.get("reviewerActor") or payload.get("actor") or "Staff"),
            )
            status = 403 if result.get("error") == "consent_denied" else 200
            return _json_response(result, status=status)

        @app.post("/api/close/generate-tasks")
        def close_generate_tasks_api():
            from hal_employee_workflows import generate_month_end_tasks

            payload = bottle.request.json or {}
            period = str(payload.get("period") or "") if isinstance(payload, dict) else ""
            return _json_response(generate_month_end_tasks(_local_store(), period=period or None))

        @app.post("/api/v1/hal/stream-sse")
        def hal_stream_sse_api():
            from employee_actions import get_current_shift_context
            from nr2_hal_gateway import evaluate_query_sse_frames, reject_financial_lane_downgrade, route_by_complexity, resolve_lane

            body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(body or "{}")
            query = str(payload.get("query") or "")
            if reject_financial_lane_downgrade(query, bottle.request.headers.get("X-HAL-Model-Override")):
                bottle.response.content_type = "text/event-stream; charset=utf-8"
                bottle.response.set_header("Cache-Control", "no-cache")
                bottle.response.set_header("X-HAL-Gateway-Enforced", "1")
                return f"event: error\ndata: {json.dumps({'error': 'financial_lane_downgrade_rejected', 'done': True})}\n\n"
            from nr2_hal_gateway import APPROVED_LOCAL_MODEL, enforce_approved_local_model

            model_gate = enforce_approved_local_model(
                payload.get("model"),
                override_header=bottle.request.headers.get("X-HAL-Model-Override"),
            )
            if not model_gate.get("ok"):
                bottle.response.content_type = "text/event-stream; charset=utf-8"
                bottle.response.set_header("Cache-Control", "no-cache")
                bottle.response.set_header("X-HAL-Gateway-Enforced", "1")
                return f"event: error\ndata: {json.dumps({**model_gate, 'done': True})}\n\n"
            if payload.get("cloud") or str(payload.get("lane") or "").lower() == "cloud":
                bottle.response.content_type = "text/event-stream; charset=utf-8"
                bottle.response.set_header("Cache-Control", "no-cache")
                bottle.response.set_header("X-HAL-Gateway-Enforced", "1")
                return (
                    f"event: error\ndata: {json.dumps({'error': 'cloud_hal_disabled', 'approvedModel': APPROVED_LOCAL_MODEL, 'done': True})}\n\n"
                )
            store = _local_store()
            readiness = _get_import_readiness()
            shift_context = payload.get("shiftContext") if isinstance(payload.get("shiftContext"), dict) else None
            if not shift_context:
                shift_context = get_current_shift_context(store)
            lane_key = str(
                payload.get("lane")
                or payload.get("requestedLane")
                or route_by_complexity(query, shift_context=shift_context, store=store)
            )
            resolved = resolve_lane(lane_key)
            bottle.response.content_type = "text/event-stream; charset=utf-8"
            bottle.response.set_header("Cache-Control", "no-cache")
            bottle.response.set_header("Connection", "keep-alive")
            bottle.response.set_header("X-Accel-Buffering", "no")
            bottle.response.set_header("X-HAL-Gateway-Enforced", "1")
            bottle.response.set_header("X-HAL-Lane-Used", str(resolved["lane"]))

            def _gen():
                yield from evaluate_query_sse_frames(
                    query=query,
                    readiness=readiness,
                    model=APPROVED_LOCAL_MODEL,
                    system_prompt=str(payload.get("systemPrompt") or payload.get("system") or ""),
                    messages=payload.get("messages") if isinstance(payload.get("messages"), list) else None,
                    options=payload.get("options") if isinstance(payload.get("options"), dict) else None,
                    shift_context=shift_context,
                    requested_lane=lane_key,
                    store=store,
                )

            return _gen()

        @app.get("/api/lane/enforce-financial")
        def lane_enforce_financial_api():
            from nr2_hal_gateway import financial_lane_policy_status

            return _json_response(financial_lane_policy_status())

        @app.post("/api/employee/clock-out")
        def employee_clock_out_api():
            from employee_actions import clock_out_shift

            payload = bottle.request.json or {}
            return _json_response(
                clock_out_shift(_local_store(), employee_id=str(payload.get("employeeId") or "HAL"))
            )

        @app.get("/api/shift/handoff/<handoff_id>")
        def shift_handoff_get_api(handoff_id: str):
            from employee_actions import get_shift_handoff

            return _json_response(get_shift_handoff(_local_store(), handoff_id))

        @app.post("/api/era/match-feedback")
        def era_match_feedback_api():
            from hal_employee_workflows import record_era_match_feedback_api

            payload = bottle.request.json or {}
            return _json_response(record_era_match_feedback_api(_local_store(), payload))

        @app.get("/api/era/pending-matches")
        def era_pending_matches_api():
            from hal_employee_workflows import list_pending_era_matches

            limit = int(bottle.request.query.get("limit") or 25)
            return _json_response(list_pending_era_matches(_local_store(), limit=limit))

        @app.post("/api/era/confirm-match")
        def era_confirm_match_api():
            from hal_employee_workflows import confirm_era_match

            payload = bottle.request.json or {}
            result = confirm_era_match(_local_store(), payload)
            _audit_mutation("era_confirm_match", detail=result if isinstance(result, dict) else {"result": result})
            return _json_response(result)

        @app.post("/api/era/train-predictor")
        def era_train_predictor_api():
            from era_ml_trainer import train_era_model

            store = _local_store()
            conn = store._connect()
            return _json_response(train_era_model(conn))

        @app.post("/api/voip/dial")
        def voip_dial_api():
            from voip_actions import get_voice_script, initiate_call

            payload = bottle.request.json or {}
            store = _local_store()
            conn = store._connect()
            scenario = str(payload.get("scriptScenario") or payload.get("context") or "collections")
            script = get_voice_script(
                scenario,
                patient_name=str(payload.get("patientName") or ""),
                balance=str(payload.get("balance") or ""),
            )
            dial = initiate_call(
                conn,
                phone_number=str(payload.get("phoneNumber") or payload.get("phone") or ""),
                patient_id=str(payload.get("patientId") or ""),
                reason=scenario,
                call_id=str(payload.get("callId") or "") or None,
                queue_id=str(payload.get("queueId") or payload.get("queue_id") or ""),
                meta={
                    "patientName": payload.get("patientName") or "",
                    "claimId": payload.get("claimId") or "",
                },
            )
            dial["script"] = script.get("script")
            dial["scenario"] = scenario
            return _json_response(dial)

        @app.post("/api/voip/log")
        def voip_log_api():
            from voip_actions import log_call_outcome

            payload = bottle.request.json or {}
            store = _local_store()
            conn = store._connect()
            return _json_response(
                log_call_outcome(
                    conn,
                    call_id=str(payload.get("callId") or payload.get("call_id") or ""),
                    outcome=str(payload.get("outcome") or "unknown"),
                    notes=str(payload.get("notes") or ""),
                    duration_sec=int(payload.get("durationSec") or payload.get("duration_sec") or 0) or None,
                    queue_id=str(payload.get("queueId") or payload.get("queue_id") or ""),
                    store=store,
                )
            )

        @app.get("/api/voip/scripts/<scenario>")
        def voip_scripts_api(scenario: str):
            from voip_actions import get_voice_script

            return _json_response(
                get_voice_script(
                    scenario,
                    patient_name=str(bottle.request.params.get("patientName") or ""),
                    balance=str(bottle.request.params.get("balance") or ""),
                )
            )

        @app.get("/api/v1/calls/log")
        def calls_log_list_api():
            from voip_actions import list_call_log

            patient_id = str(bottle.request.params.get("patientId") or "")
            conn = _local_store()._connect()
            return _json_response(list_call_log(conn, patient_id=patient_id))

        @app.get("/api/alerts/active")
        def alerts_active_api():
            from hal_alerts import list_active_alerts

            conn = _local_store()._connect()
            return _json_response(list_active_alerts(conn))

        @app.get("/api/alerts/stream")
        def alerts_stream_api():
            from hal_alerts import AlertMonitor, list_active_alerts

            store = _local_store()
            readiness = _get_import_readiness()
            AlertMonitor(store).evaluate(readiness=readiness)
            conn = store._connect()
            items = list_active_alerts(conn).get("items") or []

            def _gen():
                yield f"data: {json.dumps({'type': 'snapshot', 'items': items})}\n\n"

            bottle.response.content_type = "text/event-stream; charset=utf-8"
            bottle.response.set_header("Cache-Control", "no-cache")
            return _gen()

        @app.post("/api/alerts/<alert_id>/ack")
        def alerts_ack_api(alert_id: str):
            from hal_alerts import acknowledge_alert

            conn = _local_store()._connect()
            return _json_response(acknowledge_alert(conn, alert_id))

        @app.get("/api/scheduler/status")
        def scheduler_status_api():
            from nr2_scheduler import scheduler_status

            return _json_response(scheduler_status(_local_store()))

        @app.post("/api/scheduler/morning-run")
        def scheduler_morning_run_api():
            from nr2_scheduler import morning_routine_tick

            payload = bottle.request.json or {}
            force = bool((payload or {}).get("force"))
            return _json_response(morning_routine_tick(_local_store(), force=force))

        @app.post("/api/scheduler/halt")
        def scheduler_halt_api():
            from nr2_scheduler import halt_autonomous_run

            return _json_response(halt_autonomous_run(_local_store()))

        @app.post("/api/scheduler/undo")
        def scheduler_undo_api():
            from nr2_scheduler import undo_autonomous_run

            payload = bottle.request.json or {}
            run_id = str(payload.get("runId") or payload.get("run_id") or "").strip()
            return _json_response(undo_autonomous_run(_local_store(), run_id=run_id))

        @app.get("/api/scheduler/work")
        def scheduler_work_list_api():
            from nr2_scheduler import list_autonomous_work

            open_only = str(bottle.request.params.get("openOnly") or "1").lower() not in {
                "0",
                "false",
                "no",
            }
            limit = int(bottle.request.params.get("limit") or 50)
            kind = str(bottle.request.params.get("kind") or "").strip()
            return _json_response(
                list_autonomous_work(_local_store(), open_only=open_only, limit=limit, kind=kind)
            )

        @app.post("/api/scheduler/work/ack")
        def scheduler_work_ack_api():
            from nr2_scheduler import ack_autonomous_work

            payload = bottle.request.json or {}
            return _json_response(ack_autonomous_work(_local_store(), payload))

        @app.post("/api/scheduler/eod-run")
        def scheduler_eod_run_api():
            from nr2_scheduler import eod_handoff_tick

            payload = bottle.request.json or {}
            force = bool((payload or {}).get("force"))
            return _json_response(eod_handoff_tick(_local_store(), force=force))

        @app.get("/api/qb/auth-url")
        def qb_auth_url_api():
            from qb_connector import auth_url

            return _json_response(auth_url())

        @app.post("/api/qb/callback")
        def qb_callback_api():
            from qb_connector import store_oauth_tokens

            payload = bottle.request.json or {}
            return _json_response(
                store_oauth_tokens(
                    _local_store(),
                    code=str(payload.get("code") or ""),
                    realm_id=str(payload.get("realmId") or payload.get("realm_id") or ""),
                )
            )

        @app.post("/api/rbac/writeoff/approve")
        def rbac_writeoff_approve_api():
            from nr2_rbac import current_role, evaluate_writeoff_approval

            payload = bottle.request.json or {}
            try:
                amount = float(payload.get("amountUsd") or payload.get("amount") or 0)
            except (TypeError, ValueError):
                amount = 0.0
            prior = payload.get("priorApprovals") if isinstance(payload.get("priorApprovals"), list) else []
            result = evaluate_writeoff_approval(amount_usd=amount, role=current_role(), prior_approvals=prior)
            if result.get("allowed"):
                _audit_mutation(
                    "writeoff_approval",
                    detail={"amountUsd": amount, "chain": result.get("chain"), "role": current_role()},
                )
            status = 200 if result.get("allowed") else 403
            bottle.response.status = status
            return _json_response(result)

        @app.get("/api/analytics/production-reconciliation")
        def analytics_production_reconciliation_api():
            from nr2_analytics import production_reconciliation

            return _json_response(production_reconciliation())

        @app.get("/api/analytics/collection-lag")
        def analytics_collection_lag_api():
            from nr2_analytics import collection_lag

            return _json_response(collection_lag())

        @app.get("/api/qb/monthly-revenue")
        def qb_monthly_revenue_api():
            from nr2_analytics import quickbooks_monthly_revenue

            return _json_response(quickbooks_monthly_revenue())

        @app.get("/api/softdent/production-daily")
        def softdent_production_daily_api():
            from nr2_analytics import softdent_production_daily

            return _json_response(softdent_production_daily())

        @app.get("/api/analytics/kpi-ribbon")
        def analytics_kpi_ribbon_api():
            from nr2_analytics import kpi_ribbon

            return _json_response(kpi_ribbon())

        @app.get("/api/analytics/goal-scorecard")
        def analytics_goal_scorecard_api():
            from nr2_analytics import goal_scorecard

            return _json_response(goal_scorecard())

        @app.get("/api/analytics/alert-ticker")
        def analytics_alert_ticker_api():
            from nr2_analytics import alert_ticker

            return _json_response(alert_ticker())

        @app.get("/api/analytics/provider-comp")
        def analytics_provider_comp_api():
            from nr2_analytics import provider_compensation

            return _json_response(provider_compensation())

        @app.get("/api/analytics/monthly-trend-combo")
        def analytics_monthly_trend_combo_api():
            from nr2_analytics import monthly_trend_combo

            return _json_response(monthly_trend_combo())

        @app.get("/api/qb/balance-sheet")
        def qb_balance_sheet_api():
            from qb_connector import get_balance_sheet

            return _json_response(get_balance_sheet())

        @app.get("/api/qb/cash-flow")
        def qb_cash_flow_api():
            from qb_connector import get_cash_flow_trend

            return _json_response(get_cash_flow_trend())

        @app.get("/api/qb/net-income")
        def qb_net_income_api():
            from qb_connector import get_net_income_summary

            return _json_response(get_net_income_summary())

        @app.get("/api/qb/revenue-by-service")
        def qb_revenue_by_service_api():
            from qb_connector import get_revenue_by_service

            return _json_response(get_revenue_by_service())

        @app.get("/api/qb/ap-aging")
        def qb_ap_aging_api():
            from qb_connector import get_ap_aging

            return _json_response(get_ap_aging())

        @app.get("/api/qb/ar-aging")
        def qb_ar_aging_api():
            from qb_connector import get_ar_aging

            return _json_response(get_ar_aging())

        @app.get("/api/qb/credit-cards")
        def qb_credit_cards_api():
            from qb_connector import get_credit_card_balances

            return _json_response(get_credit_card_balances())

        @app.get("/api/softdent/collections-daily")
        def softdent_collections_daily_api():
            from nr2_softdent_daily import collections_daily

            return _json_response(collections_daily())

        @app.get("/api/softdent/new-patients-mtd")
        def softdent_new_patients_mtd_api():
            from nr2_softdent_daily import new_patients_mtd

            return _json_response(new_patients_mtd())

        @app.get("/api/softdent/appointments-snapshot")
        def softdent_appointments_snapshot_api():
            from nr2_softdent_daily import appointments_snapshot

            return _json_response(appointments_snapshot())

        @app.get("/api/softdent/appointments-today")
        def softdent_appointments_today_api():
            import bottle
            from nr2_softdent_daily import appointments_today_snapshot

            target = str(bottle.request.query.get("date") or "").strip() or None
            return _json_response(appointments_today_snapshot(target_date=target))

        @app.get("/api/softdent/appointments-range")
        def softdent_appointments_range_api():
            """Mon–Thu (or N-day) SoftDent appointment list — PHI hashes, SoftDent read-only."""
            import bottle
            from nr2_softdent_daily import appointments_range_snapshot, monday_of_week_iso

            start = str(bottle.request.query.get("start") or "").strip() or monday_of_week_iso()
            try:
                days = int(bottle.request.query.get("days") or 4)
            except ValueError:
                days = 4
            provider = str(bottle.request.query.get("provider") or "").strip() or None
            return _json_response(
                appointments_range_snapshot(start, days=days, provider_filter=provider)
            )

        @app.get("/api/softdent/today-schedule")
        def softdent_today_schedule_api():
            """Alias for Moonshot daily_ops_briefing (read-only SoftDent appointments)."""
            import bottle
            from nr2_softdent_daily import appointments_today_snapshot

            target = str(bottle.request.query.get("date") or "").strip() or None
            return _json_response(appointments_today_snapshot(target_date=target))

        @app.get("/api/claims/aging-summary")
        def claims_aging_summary_api():
            """Counts-only aging summary for spoken briefings (no invented dollars)."""
            from datetime import date, datetime

            from nr2_softdent_daily import claims_outstanding

            raw = claims_outstanding(limit=200)
            claims = raw.get("claims") if isinstance(raw.get("claims"), list) else []
            over30 = 0
            today = date.today()
            for claim in claims:
                if not isinstance(claim, dict):
                    continue
                sd = str(claim.get("serviceDate") or "")[:10]
                try:
                    d = datetime.strptime(sd, "%Y-%m-%d").date()
                except ValueError:
                    continue
                if (today - d).days > 30:
                    over30 += 1
            return _json_response(
                {
                    "ok": True,
                    "hasData": bool(claims),
                    "count": len(claims),
                    "over30": over30,
                    "source": raw.get("source"),
                }
            )

        @app.get("/api/employee/on-duty")
        def employee_on_duty_api():
            """Staff currently clocked in (read-only shift context)."""
            try:
                from employee_actions import get_current_shift_context
                from local_store import LocalStore

                store = LocalStore(NR2_DATA_DIR)
                ctx = get_current_shift_context(store)
                names = []
                if ctx.get("active"):
                    names.append(str(ctx.get("employeeId") or "HAL"))
                return _json_response(
                    {
                        "ok": True,
                        "names": names,
                        "count": len(names),
                        "active": bool(ctx.get("active")),
                        "tier": ctx.get("tier"),
                    }
                )
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc), "names": [], "count": 0}, status=500)

        @app.get("/api/softdent/provider-utilization-7d")
        def softdent_provider_utilization_7d_api():
            from nr2_softdent_daily import provider_utilization_last_7d

            return _json_response(provider_utilization_last_7d())

        @app.get("/api/softdent/claims-outstanding")
        def softdent_claims_outstanding_api():
            from nr2_softdent_daily import claims_outstanding

            return _json_response(claims_outstanding())

        @app.get("/api/softdent/provider-production")
        def softdent_provider_production_api():
            from nr2_softdent_daily import provider_production

            return _json_response(provider_production())

        @app.get("/api/softdent/adjustment-log")
        def softdent_adjustment_log_api():
            from nr2_softdent_daily import adjustment_log

            return _json_response(adjustment_log())

        @app.get("/api/softdent/patient-retention")
        def softdent_patient_retention_api():
            from nr2_softdent_daily import patient_retention

            return _json_response(patient_retention())

        @app.get("/api/softdent/operatory-grid")
        def softdent_operatory_grid_api():
            from nr2_softdent_daily import operatory_grid

            return _json_response(operatory_grid())

        @app.post("/api/admin/extract-softdent-odbc")
        def extract_softdent_odbc_api():
            from softdent_odbc_extract import consent_executor_enabled, ensure_softdent_odbc_fresh

            if not consent_executor_enabled():
                bottle.response.status = 403
                return _json_response(
                    {
                        "ok": False,
                        "error": "consent_executor_disabled",
                        "message": "Set NR2_CONSENT_EXECUTOR=1 to run SoftDent ODBC extract.",
                    }
                )
            payload = bottle.request.json or {}
            force = bool(payload.get("force"))
            try:
                max_age = int(payload.get("maxAgeMinutes") or 60)
            except (TypeError, ValueError):
                max_age = 60
            result = ensure_softdent_odbc_fresh(max_age_minutes=max(1, max_age), force=force)
            if result.get("refreshed"):
                _audit_mutation(
                    "softdent_odbc_extract",
                    detail={
                        "refreshed": True,
                        "mode": ((result.get("extract") or {}).get("mode")),
                        "populatedTables": int((result.get("status") or {}).get("populatedTables") or 0),
                    },
                )
            return _json_response(result)

        @app.get("/api/softdent/odbc-status")
        def softdent_odbc_status_api():
            from softdent_odbc_extract import read_extract_status

            return _json_response(read_extract_status())

        @app.post("/api/qb/sync-if-stale")
        def qb_sync_if_stale_api():
            from import_loader import quickbooks_import_dir
            from quickbooks_monthly_sync import ensure_quickbooks_fresh

            payload = bottle.request.json or {}
            try:
                max_age = int(payload.get("maxAgeMinutes") or 60)
            except (TypeError, ValueError):
                max_age = 60
            qb_dest = quickbooks_import_dir()
            probe_payload = None
            probe_path = qb_dest / "quickbooks_diagnostics" / "quickbooks_sdk_report_probe_summary.json"
            if probe_path.is_file():
                try:
                    probe_payload = json.loads(probe_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    probe_payload = None
            result = ensure_quickbooks_fresh(qb_dest, max_age_minutes=max(1, max_age), probe_payload=probe_payload)
            if result.get("refreshed"):
                _audit_mutation("qb_sync_if_stale", detail={"refreshed": True, "destination": result.get("destination")})
            return _json_response(result)

        @app.post("/api/qb/sync")
        def qb_sync_api():
            from qb_connector import sync_read_only

            return _json_response(sync_read_only(_local_store()))

        @app.post("/api/qb/push")
        def qb_push_api():
            from qb_connector import push_journal_with_consent

            payload = bottle.request.json or {}
            amount = payload.get("amount")
            try:
                amount_f = float(amount) if amount is not None else None
            except (TypeError, ValueError):
                amount_f = None
            result = push_journal_with_consent(
                _local_store(),
                entries=payload.get("entries") if isinstance(payload.get("entries"), list) else None,
                memo=str(payload.get("memo") or ""),
                amount=amount_f,
            )
            _audit_mutation("qb_journal_post", detail=result if isinstance(result, dict) else {"result": result})
            status = 403 if result.get("error") == "consent_denied" else 200
            return _json_response(result, status=status)

        @app.get("/api/qb/reconciliation")
        def qb_reconciliation_api():
            from qb_connector import reconciliation_status

            return _json_response(reconciliation_status(_local_store()))

        @app.post("/api/qb/pull")
        def qb_pull_api():
            from qb_connector import pull_payments_read_only

            return _json_response(pull_payments_read_only(_local_store()))

        @app.post("/api/era/denial-predict")
        def era_denial_predict_api():
            from era_denial_trainer import predict_denial_risk

            payload = bottle.request.json or {}
            codes = payload.get("cdtCodes") or payload.get("cdt_codes") or []
            if not isinstance(codes, list):
                codes = []
            return _json_response(
                predict_denial_risk(
                    cdt_codes=[str(c) for c in codes],
                    payer_id=str(payload.get("payerId") or payload.get("payer_id") or ""),
                    has_narrative=bool(payload.get("hasNarrative", True)),
                    prior_denials=int(payload.get("priorDenials") or payload.get("prior_denials") or 0),
                    claim=payload.get("claim") if isinstance(payload.get("claim"), dict) else payload,
                )
            )

        @app.post("/api/sms/send")
        def sms_send_api():
            from sms_actions import send_billing_sms

            payload = bottle.request.json or {}
            conn = _local_store()._connect()
            return _json_response(
                send_billing_sms(
                    conn,
                    patient_id=str(payload.get("patientId") or ""),
                    phone_number=str(payload.get("phoneNumber") or payload.get("phone") or ""),
                    template_key=str(payload.get("templateKey") or payload.get("template") or "reminder"),
                    body=str(payload.get("body") or ""),
                    variables=payload.get("variables") if isinstance(payload.get("variables"), dict) else None,
                )
            )

        @app.post("/api/sms/webhook")
        def sms_webhook_api():
            from sms_actions import handle_inbound_sms, inbound_webhook_allowed

            payload = bottle.request.forms if bottle.request.forms else {}
            params = {k: payload.get(k) for k in payload.keys()} if hasattr(payload, "keys") else {}
            sig = bottle.request.headers.get("X-Twilio-Signature") or ""
            gate = inbound_webhook_allowed(url=bottle.request.url, params=params, signature=sig)
            if not gate.get("ok"):
                return _json_response(gate, status=403)
            conn = _local_store()._connect()
            return _json_response(
                handle_inbound_sms(
                    conn,
                    phone_number=str(params.get("From") or ""),
                    body=str(params.get("Body") or ""),
                    patient_id=str(params.get("patientId") or ""),
                )
            )

        @app.get("/api/sms/thread/<patient_id>")
        def sms_thread_api(patient_id: str):
            from sms_actions import get_sms_thread

            conn = _local_store()._connect()
            return _json_response(get_sms_thread(conn, patient_id=patient_id))

        @app.post("/api/documents/classify")
        def documents_classify_api():
            from document_classifier import classify_document_text, route_for_category

            payload = bottle.request.json or {}
            text = str(payload.get("text") or payload.get("content") or "")
            if not text and payload.get("path"):
                from document_classifier import classify_document_path

                return _json_response(classify_document_path(str(payload.get("path"))))
            result = classify_document_text(text)
            result["suggestedRoute"] = route_for_category(result.get("category") or "Unknown")
            return _json_response(result)

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

        @app.get("/api/financial/post-queue")
        def financial_post_queue_api():
            return posting_queue_api()

        @app.get("/api/posting-queue")
        def posting_queue_api():
            bottle.response.content_type = "application/json"
            bottle.response.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
            try:
                from accounting_bridge import list_posting_queue
                from local_store import LocalStore

                store = LocalStore(NR2_DATA_DIR)
                limit = int(bottle.request.params.get("limit") or 20)
                status = str(bottle.request.params.get("status") or "").strip() or None
                return json.dumps(list_posting_queue(store.db_path, limit=limit, status=status))
            except Exception as exc:
                bottle.response.status = 500
                return json.dumps({"error": str(exc)})

        @app.post("/api/posting-queue/enqueue")
        def posting_queue_enqueue_api():
            from nr2_rbac import has_capability

            if not has_capability("write_posting"):
                return _json_response({"ok": False, "error": "capability_rejected"}, status=403)
            gate = _require_imports_for_posting()
            if gate is not None:
                return gate
            bottle.response.content_type = "application/json"
            try:
                from accounting_bridge import enqueue_journal_posting, parse_context_json
                from local_store import LocalStore

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                if not isinstance(payload, dict):
                    return _json_response({"ok": False, "error": "payload must be a JSON object"}, status=400)
                store = LocalStore(NR2_DATA_DIR)
                result = enqueue_journal_posting(
                    store.db_path,
                    description=str(payload.get("description") or "Journal entry"),
                    period=str(payload.get("period") or ""),
                    amount=float(payload.get("amount") or 0),
                    actor=str(payload.get("actor") or "Staff"),
                    context=parse_context_json(json.dumps(payload.get("context") or {})),
                    transaction_date=str(payload.get("transactionDate") or "") or None,
                    enqueue_mode=str(payload.get("enqueueMode") or "manual_review_queue"),
                )
                _audit_mutation("posting_queue_enqueue", detail=result if isinstance(result, dict) else {"result": result})
                return _json_response(result)
            except ValueError as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=400)
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/posting-queue/review")
        def posting_queue_review_api():
            from nr2_rbac import has_capability

            if not has_capability("write_posting"):
                return _json_response({"ok": False, "error": "capability_rejected"}, status=403)
            gate = _require_imports_for_posting()
            if gate is not None:
                return gate
            bottle.response.content_type = "application/json"
            try:
                from accounting_bridge import review_posting_queue_entry
                from local_store import LocalStore

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                if not isinstance(payload, dict):
                    return _json_response({"ok": False, "error": "payload must be a JSON object"}, status=400)
                queue_id = str(payload.get("queueId") or payload.get("queue_id") or "").strip()
                action = str(payload.get("action") or "").strip()
                reviewer = str(payload.get("reviewerActor") or payload.get("reviewer") or "Staff").strip()
                note = str(payload.get("reviewNote") or payload.get("note") or "")
                if not queue_id:
                    return _json_response({"ok": False, "error": "queueId required"}, status=400)
                store = LocalStore(NR2_DATA_DIR)
                result = review_posting_queue_entry(
                    store.db_path,
                    queue_id=queue_id,
                    action=action,
                    reviewer_actor=reviewer,
                    review_note=note or None,
                )
                _audit_mutation("posting_queue_review", detail=result if isinstance(result, dict) else {"result": result})
                return _json_response(result)
            except ValueError as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=400)
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/posting-queue/bulk-review")
        def posting_queue_bulk_review_api():
            from nr2_rbac import has_capability

            if not has_capability("write_posting"):
                return _json_response({"ok": False, "error": "capability_rejected"}, status=403)
            gate = _require_imports_for_posting()
            if gate is not None:
                return gate
            pilot_gate = _require_pilot_posting_gate("posting_queue_bulk_review")
            if pilot_gate is not None:
                return pilot_gate
            bottle.response.content_type = "application/json"
            try:
                from accounting_bridge import bulk_review_posting_queue
                from local_store import LocalStore

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                if not isinstance(payload, dict):
                    return _json_response({"ok": False, "error": "payload must be a JSON object"}, status=400)
                store = LocalStore(NR2_DATA_DIR)
                result = bulk_review_posting_queue(
                    store.db_path,
                    action=str(payload.get("action") or "approved"),
                    reviewer_actor=str(payload.get("reviewerActor") or payload.get("reviewer") or "Staff"),
                    review_note=str(payload.get("reviewNote") or payload.get("note") or "") or None,
                    limit=int(payload.get("limit") or 50),
                )
                _audit_mutation("posting_queue_bulk_review", detail=result if isinstance(result, dict) else {"result": result})
                return _json_response(result)
            except ValueError as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=400)
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

        @app.post("/api/posting-queue/export-approved")
        def posting_queue_export_approved_api():
            from nr2_rbac import has_capability

            if not has_capability("write_posting"):
                return _json_response({"ok": False, "error": "capability_rejected"}, status=403)
            gate = _require_imports_for_posting()
            if gate is not None:
                return gate
            pilot_gate = _require_pilot_posting_gate("posting_queue_export_approved")
            if pilot_gate is not None:
                return pilot_gate
            bottle.response.content_type = "application/json"
            try:
                from accounting_bridge import export_approved_posting_queue_csv
                from local_store import LocalStore

                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                if not isinstance(payload, dict):
                    payload = {}
                store = LocalStore(NR2_DATA_DIR)
                result = export_approved_posting_queue_csv(store.db_path, limit=int(payload.get("limit") or 200))
                _audit_mutation("posting_queue_export_approved", detail=result if isinstance(result, dict) else {"result": result})
                return _json_response(result)
            except Exception as exc:
                return _json_response({"ok": False, "error": str(exc)}, status=500)

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

        @app.post("/api/export/cpa-packet")
        def export_cpa_packet_api():
            from nr2_rbac import has_capability

            if _browser_app() and not (has_capability("read_financial") or has_capability("read_all")):
                bottle.response.content_type = "application/json"
                bottle.response.status = 403
                return json.dumps({"ok": False, "error": "capability_rejected"})
            try:
                from cpa_packet_export import build_cpa_packet_zip_bytes

                filename, data = build_cpa_packet_zip_bytes()
                bottle.response.content_type = "application/zip"
                bottle.response.set_header("Content-Disposition", f'attachment; filename="{filename}"')
                return data
            except Exception as exc:
                bottle.response.content_type = "application/json"
                bottle.response.status = 500
                return json.dumps({"ok": False, "error": str(exc)})

        @app.post("/api/export/page-storyboard")
        def export_page_storyboard_api():
            from nr2_rbac import has_capability

            if _browser_app() and not (has_capability("read_financial") or has_capability("read_all")):
                bottle.response.content_type = "application/json"
                bottle.response.status = 403
                return json.dumps({"ok": False, "error": "capability_rejected"})
            try:
                body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
                payload = json.loads(body or "{}")
                page_id = str(payload.get("pageId") or "financial").strip().lower()
                from page_storyboard_export import build_page_storyboard_zip_bytes

                filename, data = build_page_storyboard_zip_bytes(page_id)
                bottle.response.content_type = "application/zip"
                bottle.response.set_header("Content-Disposition", f'attachment; filename="{filename}"')
                return data
            except Exception as exc:
                bottle.response.content_type = "application/json"
                bottle.response.status = 500
                return json.dumps({"ok": False, "error": str(exc)})

        @app.get("/api/financial-reports")
        def financial_reports_api():
            from nr2_rbac import has_capability

            if _browser_app() and not (has_capability("read_financial") or has_capability("read_all")):
                return _json_response({"ok": False, "error": "capability_rejected"}, status=403)
            bottle.response.content_type = "application/json"
            try:
                from financial_reports import build_financial_reports

                sync_exports = bottle.request.query.get("syncExports") == "1"
                return json.dumps(build_financial_reports(sync_exports=sync_exports))
            except Exception as exc:
                bottle.response.status = 500
                return json.dumps({"error": str(exc)})

        # NR2-Apex widget/print/sync routes (wrap existing financial_reports / import_loader)
        from apex_backend import register_apex_routes

        register_apex_routes(app, _json_response)

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
                from hal_tts import tts_status

                return json.dumps(tts_status())
            except Exception as exc:
                return json.dumps({"ok": False, "error": str(exc)})

        @app.post("/api/hal-tts")
        def hal_tts_api():
            bottle.response.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
            try:
                from hal_tts import parse_tts_request, synthesize_test_sync, synthesize_segments_sync

                raw = bottle.request.body.read() if bottle.request.body else b""
                payload = parse_tts_request(raw)
                if payload.get("test") or payload.get("demo"):
                    audio = synthesize_test_sync()
                else:
                    segments = payload.get("segments")
                    if not isinstance(segments, list) or not segments:
                        bottle.response.status = 400
                        bottle.response.content_type = "application/json"
                        return json.dumps({"error": "segments or demo required"})
                    audio = synthesize_segments_sync(segments, payload)
                bottle.response.content_type = "audio/mpeg"
                return audio
            except Exception as exc:
                bottle.response.status = 500
                bottle.response.content_type = "application/json"
                return json.dumps({"error": str(exc)})

        @app.get("/api/v1/financial-reports")
        def api_v1_financial_reports():
            return financial_reports_api()

        @app.get("/api/v1/posting-queue")
        def api_v1_posting_queue():
            return posting_queue_api()

        @app.get("/api/v1/ocr-exceptions")
        def api_v1_ocr_exceptions():
            return ocr_exceptions_list_api()

        @app.post("/api/v1/eob/auto-match")
        def eob_auto_match_api():
            from hal_employee_workflows import process_eob_match

            body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(body or "{}")
            return _json_response(process_eob_match(_local_store(), payload))

        @app.post("/api/v1/era/import")
        def era_import_api():
            from hal_employee_workflows import parse_era_import

            body = bottle.request.body.read().decode("utf-8") if bottle.request.body else "{}"
            payload = json.loads(body or "{}")
            return _json_response(parse_era_import(_local_store(), payload))

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

        @app.get("/deferred-live-wire/<file:path>")
        def deferred_live_wire(file):
            if not _desktop_access_ok():
                bottle.abort(403, _desktop_only_html())
            wire_root = Path(__file__).resolve().parent / "site" / "deferred-live-wire"
            if not wire_root.is_dir():
                wire_root = Path(__file__).resolve().parent / "deferred-live-wire"
            safe = Path(file)
            if safe.name != file or ".." in safe.parts:
                bottle.abort(400, "Invalid path")
            target = wire_root / file
            if not target.is_file():
                bottle.abort(404, "Deferred live-wire asset not found")
            bottle.response.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
            bottle.response.set_header("Pragma", "no-cache")
            bottle.response.set_header("Expires", 0)
            return bottle.static_file(file, root=str(wire_root))

        @app.get("/mockup-elite-embed/<page_id>")
        def mockup_elite_embed(page_id):
            if not _desktop_access_ok():
                bottle.abort(403, _desktop_only_html())
            from mockup_elite_embed import render_embed_html

            html = render_embed_html(str(page_id or "").strip().lower())
            if html is None:
                bottle.abort(404, "Elite mock preview not found for this page.")
            bottle.response.content_type = "text/html; charset=UTF-8"
            bottle.response.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
            bottle.response.set_header("Pragma", "no-cache")
            return html

        @app.get("/api/mockup-elite-pages")
        def mockup_elite_pages_api():
            if not _desktop_access_ok():
                bottle.abort(403, _desktop_only_html())
            from mockup_elite_embed import list_mockup_page_ids

            bottle.response.content_type = "application/json; charset=UTF-8"
            bottle.response.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
            return json.dumps({"pages": list_mockup_page_ids()}, ensure_ascii=False)

        @app.route("/<file:path>")
        def asset(file):
            if not _desktop_access_ok():
                bottle.abort(403, _desktop_only_html())
            if _workstation_asset_blocked(file):
                bottle.abort(
                    404,
                    "Workstation is not part of the financial program. Use Start Workstation on port 8766.",
                )
            if not server.root_path:
                return ""
            bottle.response.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
            bottle.response.set_header("Pragma", "no-cache")
            bottle.response.set_header("Expires", 0)
            return bottle.static_file(file, root=server.root_path)

        server.root_path = abspath(common_path) if common_path is not None else None
        server.port = http_port or _get_random_port()
        if keyfile and certfile:
            from nr2_tls import ensure_tls_key_material

            certfile, keyfile = ensure_tls_key_material(certfile, keyfile)
            server_adapter = NR2SSLWSGIRefServer()
            server_adapter.port = server.port
            setattr(server_adapter, "pywebview_keyfile", keyfile)
            setattr(server_adapter, "pywebview_certfile", certfile)
        else:
            server_adapter = ThreadedAdapter
        server.thread = threading.Thread(
            target=lambda: bottle.run(
                app=app,
                server=server_adapter,
                host=host,
                port=server.port,
                quiet=not _state["debug"],
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
