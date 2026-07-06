#!/usr/bin/env python3
"""
NewRidgeFinancial 2.0 — browser program (financial pages + HAL).

Serves site/ over loopback HTTP. Staff open http://127.0.0.1:8765/ in a browser.
No pywebview window — workstation app remains a separate desktop program.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
SITE_DIR = ROOT / "site"
DATA_DIR = REPO_ROOT / "app_data" / "nr2"
INDEX_HTML = SITE_DIR / "index.html"

from desktop_app import ASSET_VERSION, DESIGN_SCHEMA_VERSION  # noqa: E402


def main() -> int:
    if not INDEX_HTML.is_file():
        print(f"Site not found: {INDEX_HTML}", file=sys.stderr)
        return 1

    os.environ["NR2_BROWSER_APP"] = "1"
    default_port = 8765
    http_port = int(os.environ.get("NR2_HTTP_PORT", str(default_port)))

    from nr2_http_server import NR2BottleServer, set_browser_mode, set_desktop_session_token, set_site_root

    set_browser_mode(True)
    set_desktop_session_token(None)
    set_site_root(SITE_DIR)

    try:
        from document_sync import sync_accounting_documents
        from local_store import LocalStore

        sync_accounting_documents(LocalStore(DATA_DIR))
    except Exception as exc:
        print(f"Startup document sync failed: {exc}", file=sys.stderr)

    def _startup_import_sync() -> None:
        try:
            from import_sync import sync_imports

            sync_imports()
        except Exception as exc:
            print(f"Startup import sync failed: {exc}", file=sys.stderr)

    threading.Thread(target=_startup_import_sync, daemon=True, name="nr2-import-sync").start()

    print(
        f"NR2 browser app: schema={DESIGN_SCHEMA_VERSION} site={SITE_DIR} port={http_port}",
        file=sys.stderr,
    )
    print(
        f"NR2 browser app: open http://127.0.0.1:{http_port}/ in your browser (financial pages + HAL).",
        file=sys.stderr,
    )

    address, _, server = NR2BottleServer.start_server([f"http://127.0.0.1:{http_port}/"], http_port)
    print(f"NR2 browser app: listening at {address}", file=sys.stderr)

    try:
        while server.running and server.thread and server.thread.is_alive():
            server.thread.join(timeout=1.0)
    except KeyboardInterrupt:
        print("NR2 browser app: stopped.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
