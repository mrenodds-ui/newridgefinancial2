"""NR2 loopback HTTP server — serves site/ with index.html at /."""

from __future__ import annotations

import json
import os
import threading
import uuid

import bottle

from webview.http import BottleServer, SSLWSGIRefServer, ThreadedAdapter, _get_random_port, logger
from webview.util import abspath, is_app, is_local_url


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
