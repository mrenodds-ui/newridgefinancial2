"""Webhook-only relay for website appointment requests.

Exposes ONLY:
  POST /api/webhooks/website-appointment
  GET  /health

Binds 127.0.0.1 (tunneled via cloudflared). Writes into the same NR2 SQLite
store HAL reads for sidenotes — does not expose the full NR2 UI/API.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# Match nr2_http_server.NR2_DATA_DIR (repo root / app_data / nr2)
DATA_DIR = Path(os.environ.get("NR2_DATA_DIR") or (REPO.parent / "app_data" / "nr2")).resolve()
SECRET_FILE = DATA_DIR / "website_webhook_secret.txt"
DEFAULT_PORT = int(os.environ.get("NR2_WEBSITE_WEBHOOK_PORT") or "8777")


def ensure_secret() -> str:
    existing = str(os.environ.get("NR2_WEBSITE_WEBHOOK_SECRET") or "").strip()
    if existing:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not SECRET_FILE.exists():
            SECRET_FILE.write_text(existing, encoding="utf-8")
        return existing
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SECRET_FILE.exists():
        saved = SECRET_FILE.read_text(encoding="utf-8").strip()
        if saved:
            os.environ["NR2_WEBSITE_WEBHOOK_SECRET"] = saved
            return saved
    generated = secrets.token_urlsafe(32)
    SECRET_FILE.write_text(generated, encoding="utf-8")
    os.environ["NR2_WEBSITE_WEBHOOK_SECRET"] = generated
    return generated


def _json_bytes(payload: dict, status: int = 200) -> tuple[int, bytes, str]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return status, body, "application/json; charset=utf-8"


def handle_webhook(headers: dict[str, str], raw_body: bytes, query: dict[str, list[str]]) -> tuple[int, bytes, str]:
    from local_store import LocalStore
    from sidenotes_local_store import insert_sidenote_local
    from website_leads_store import (
        format_lead_sidenote,
        insert_website_lead,
        normalize_gravity_forms_payload,
        webhook_secret_configured,
        webhook_secret_valid,
    )

    provided = (
        headers.get("x-nr2-webhook-secret")
        or headers.get("x-webhook-secret")
        or (query.get("secret") or [""])[0]
        or ""
    )
    auth = headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        provided = auth[7:].strip() or provided

    if webhook_secret_configured() and not webhook_secret_valid(provided):
        return _json_bytes({"ok": False, "error": "invalid_webhook_secret"}, 403)

    payload: dict = {}
    ctype = (headers.get("content-type") or "").lower()
    text = raw_body.decode("utf-8", errors="replace") if raw_body else ""
    if "application/json" in ctype or (text.strip().startswith("{") or text.strip().startswith("[")):
        if text.strip():
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    payload = parsed
            except json.JSONDecodeError:
                payload = {"rawBody": text[:4000]}
    elif text.strip():
        # application/x-www-form-urlencoded
        form = parse_qs(text, keep_blank_values=True)
        payload = {k: (v[0] if len(v) == 1 else v) for k, v in form.items()}

    normalized = normalize_gravity_forms_payload(payload)
    if not (normalized.get("name") or normalized.get("email") or normalized.get("phone")):
        return _json_bytes(
            {"ok": False, "error": "missing_contact_fields", "hint": "Need name, email, or phone"},
            400,
        )

    store = LocalStore(DATA_DIR)
    sidenote = None
    with store._connect() as conn:
        lead = insert_website_lead(conn, normalized=normalized, source="gravity_forms")
        if not lead.get("duplicate"):
            sidenote = insert_sidenote_local(
                conn,
                text=format_lead_sidenote(lead),
                source="website",
                station="appointment-request",
            )
        conn.commit()

    return _json_bytes(
        {
            "ok": True,
            "lead": {k: v for k, v in lead.items() if k != "raw_json"},
            "sidenote": sidenote,
            "halVisible": True,
        }
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "NR2WebsiteWebhookRelay/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[website-webhook] " + (fmt % args) + "\n")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/health", "/api/health"):
            status, body, ctype = _json_bytes(
                {"ok": True, "service": "website-appointment-webhook", "dataDir": str(DATA_DIR)}
            )
            self._send(status, body, ctype)
            return
        self._send(*_json_bytes({"ok": False, "error": "not_found"}, 404))

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/webhooks/website-appointment":
            self._send(*_json_bytes({"ok": False, "error": "not_found"}, 404))
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length > 0 else b""
        headers = {k.lower(): v for k, v in self.headers.items()}
        query = parse_qs(parsed.query)
        status, body, ctype = handle_webhook(headers, raw, query)
        self._send(status, body, ctype)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-NR2-Webhook-Secret, Authorization")
        self.end_headers()


def main() -> int:
    secret = ensure_secret()
    host = str(os.environ.get("NR2_WEBSITE_WEBHOOK_HOST") or "127.0.0.1").strip() or "127.0.0.1"
    port = DEFAULT_PORT
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"website-webhook-relay listening on http://{host}:{port}", flush=True)
    print(f"data_dir={DATA_DIR}", flush=True)
    print(f"secret_file={SECRET_FILE}", flush=True)
    print(f"secret_prefix={secret[:6]}…", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
