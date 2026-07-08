#!/usr/bin/env python3
"""
NewRidgeFinancial 2.0 — browser program (financial pages + HAL).

Serves site/ over loopback HTTPS (TLS enforced by default).
Staff open https://127.0.0.1:8765/ in a browser.
"""

from __future__ import annotations

import os
import sys
import threading
import uuid
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

    os.environ.setdefault("NR2_BROWSER_APP", "1")
    os.environ.setdefault("NR2_ENFORCE_TLS", "1")
    os.environ.setdefault("NR2_DB_ENCRYPTION", "1")

    default_port = 8765
    http_port = int(os.environ.get("NR2_HTTP_PORT", str(default_port)))

    from nr2_startup_checks import run_browser_production_checks

    startup = run_browser_production_checks(REPO_ROOT, DATA_DIR)
    tls_cert = startup.get("tlsCert") or ""
    tls_key = startup.get("tlsKey") or ""
    bind_host = str(startup.get("bindHost") or "127.0.0.1")
    os.environ["NR2_BIND_HOST"] = bind_host

    from nr2_http_server import (
        NR2BottleServer,
        set_browser_mode,
        set_browser_session_token,
        set_desktop_session_token,
        set_site_root,
        set_workstation_mode,
    )

    set_browser_mode(True)
    set_workstation_mode(False)
    set_desktop_session_token(None)
    set_browser_session_token(uuid.uuid4().hex)
    set_site_root(SITE_DIR)

    try:
        from integration_health import integration_health_snapshot

        health = integration_health_snapshot(None)
        if not (health.get("ollama") or {}).get("ok"):
            print("WARNING: Ollama not reachable at 127.0.0.1:11434 — set OLLAMA_HOST=127.0.0.1", file=sys.stderr)
    except Exception as exc:
        print(f"Ollama startup check skipped: {exc}", file=sys.stderr)

    try:
        from document_sync import sync_accounting_documents
        from local_store import LocalStore

        store = LocalStore(DATA_DIR)
        from nr2_sqlite_backup import backup_sqlite

        backup = backup_sqlite(store.db_path)
        if not backup.get("ok"):
            print(f"Startup SQLite backup skipped: {backup.get('error')}", file=sys.stderr)
        else:
            print(f"Startup SQLite backup: {backup.get('path')}", file=sys.stderr)
        sync_accounting_documents(store)
    except Exception as exc:
        print(f"Startup document sync failed: {exc}", file=sys.stderr)

    def _startup_import_sync() -> None:
        try:
            from import_sync import sync_imports

            sync_imports()
        except Exception as exc:
            print(f"Startup import sync failed: {exc}", file=sys.stderr)

    threading.Thread(target=_startup_import_sync, daemon=True, name="nr2-import-sync").start()

    def _background_scheduler() -> None:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
            from apscheduler.triggers.interval import IntervalTrigger
            from local_store import LocalStore

            store = LocalStore(DATA_DIR)

            def _alert_tick() -> None:
                try:
                    from hal_alerts import AlertMonitor
                    from import_diagnostics import assess_import_readiness

                    readiness = assess_import_readiness(operation="dailyOps")
                    conn = store._connect()
                    AlertMonitor(store).evaluate(readiness=readiness)
                except Exception as exc:
                    print(f"Alert scheduler tick failed: {exc}", file=sys.stderr)

            def _morning_tick() -> None:
                try:
                    from nr2_scheduler import morning_routine_tick

                    morning_routine_tick(store)
                except Exception as exc:
                    print(f"Morning routine tick failed: {exc}", file=sys.stderr)

            sched = BackgroundScheduler(daemon=True)
            sched.add_job(_alert_tick, IntervalTrigger(minutes=15), id="nr2-alerts")
            sched.add_job(_morning_tick, CronTrigger(hour=6, minute=30), id="nr2-morning")
            sched.start()
            print("NR2 background scheduler: alerts every 15m, morning routine 06:30 UTC", file=sys.stderr)
        except ImportError:
            print("APScheduler not installed — background alert/morning ticks disabled.", file=sys.stderr)
        except Exception as exc:
            print(f"Background scheduler failed to start: {exc}", file=sys.stderr)

    threading.Thread(target=_background_scheduler, daemon=True, name="nr2-scheduler").start()

    scheme = "https" if tls_cert and tls_key else "http"
    print(
        f"NR2 browser app: schema={DESIGN_SCHEMA_VERSION} site={SITE_DIR} port={http_port} bind={bind_host} tls={scheme}",
        file=sys.stderr,
    )
    print(
        f"NR2 browser app: open {scheme}://127.0.0.1:{http_port}/ in your browser (financial pages + HAL).",
        file=sys.stderr,
    )

    address, _, server = NR2BottleServer.start_server(
        [f"{scheme}://127.0.0.1:{http_port}/"],
        http_port,
        certfile=tls_cert or None,
        keyfile=tls_key or None,
        bind_host=bind_host,
    )
    print(f"NR2 browser app: listening at {address}", file=sys.stderr)

    try:
        while server.running and server.thread and server.thread.is_alive():
            server.thread.join(timeout=1.0)
    except KeyboardInterrupt:
        print("NR2 browser app: stopped.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
