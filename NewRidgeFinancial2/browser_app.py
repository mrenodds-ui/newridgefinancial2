#!/usr/bin/env python3
"""
NewRidgeFinancial 2.0 — browser program (financial pages + HAL).

Serves site/ over loopback HTTPS (TLS enforced by default).
Staff open https://127.0.0.1:8765/ in a browser.
"""

from __future__ import annotations

import atexit
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
# Moonshot crash/perf MUST: prevent dual browser_app launches (port/cache contention).
PIDFILE = ROOT / ".nr2_browser_app.pid"

from desktop_app import ASSET_VERSION, DESIGN_SCHEMA_VERSION  # noqa: E402


def _pid_alive(pid: int) -> bool:
    """True if pid is a live process (Windows-safe; Moonshot singleton intent)."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        # PROCESS_QUERY_LIMITED_INFORMATION — os.kill(pid, 0) is not portable on Windows.
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _port_available(host: str, port: int) -> bool:
    """Probe if host:port is free to bind (stdlib only; no psutil)."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except (OSError, socket.error):
            return False


def ensure_singleton(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Moonshot MUST: exit if another browser_app.py is already running."""
    # Stale PID cleanup and cross-check
    if PIDFILE.is_file():
        old_raw = PIDFILE.read_text(encoding="utf-8", errors="replace").strip()
        try:
            old_pid = int(old_raw)
        except ValueError:
            old_pid = 0
        if old_pid and old_pid != os.getpid() and _pid_alive(old_pid):
            print(
                f"ERROR: browser_app.py already running (PID {old_pid}). Exiting.",
                file=sys.stderr,
            )
            raise SystemExit(1)

    # Port-aware probe: ensure we can bind before claiming PID
    if not _port_available(host, port):
        print(
            f"ERROR: Port {port} already in use on {host} (another instance running?). Exiting.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    PIDFILE.write_text(str(os.getpid()), encoding="utf-8")

    def _cleanup_pidfile() -> None:
        try:
            if PIDFILE.is_file() and PIDFILE.read_text(encoding="utf-8").strip() == str(
                os.getpid()
            ):
                PIDFILE.unlink(missing_ok=True)
        except OSError:
            pass

    atexit.register(_cleanup_pidfile)


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

    ensure_singleton(bind_host, http_port)

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
        # Optical UI: do not warm legacy apex widget layout (packs removed).
        try:
            from import_loader import load_import_bundle

            load_import_bundle(sync=False, deep=False)
            print("NR2 cache warm complete (import bundle only; apex widgets skipped).", file=sys.stderr)
        except Exception as exc:
            print(f"Startup cache warm failed: {exc}", file=sys.stderr)
        # HAL model keep-alive (optional; pack may be absent after clean slate).
        try:
            from apex_hal_cache_warm_pack import warm_hal_cache

            warm = warm_hal_cache(background=True)
            print(
                f"NR2 HAL model warm: ok={warm.get('ok')} background={warm.get('background')} "
                f"prompts={warm.get('promptCount')} keepAlive={warm.get('keepAlive')}",
                file=sys.stderr,
            )
        except Exception as exc:
            print(f"HAL model cache warm skipped: {exc}", file=sys.stderr)
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

            def _eod_tick() -> None:
                try:
                    from nr2_scheduler import eod_handoff_tick

                    eod_handoff_tick(store)
                except Exception as exc:
                    print(f"EOD handoff tick failed: {exc}", file=sys.stderr)

            def _trellis_verify_tick() -> None:
                """Mon–Thu 10pm local — next clinical day Trellis eligibility."""
                try:
                    from nr2_scheduler import insurance_verify_tick

                    result = insurance_verify_tick(store)
                    print(
                        f"Trellis insurance verify tick: ok={result.get('ok')} "
                        f"skipped={result.get('skipped')} target={result.get('targetDate')} "
                        f"ready={result.get('worklistReady')}",
                        file=sys.stderr,
                    )
                except Exception as exc:
                    print(f"Trellis insurance verify tick failed: {exc}", file=sys.stderr)

            def _health_monitor_tick() -> None:
                """Moonshot Expert SE Phase 2 REC-004 — proactive import/health audit (no PHI)."""
                try:
                    from apex_health_monitor_pack import run_scheduled_health_audit

                    # classify_only avoids long Ollama holds on the scheduler thread.
                    result = run_scheduled_health_audit(classify_only=True)
                    print(
                        f"Health monitor tick: ok={result.get('ok')} reason={result.get('reason') or result.get('lane')}",
                        file=sys.stderr,
                    )
                except Exception as exc:
                    print(f"Health monitor tick failed: {exc}", file=sys.stderr)

            def _hal_autonomous_tick() -> None:
                try:
                    from nr2_scheduler import hal_autonomous_ops_tick

                    result = hal_autonomous_ops_tick(store)
                    print(
                        f"HAL autonomous tick: ok={result.get('ok')} steps={len(result.get('steps') or [])}",
                        file=sys.stderr,
                    )
                except Exception as exc:
                    print(f"HAL autonomous tick failed: {exc}", file=sys.stderr)

            sched = BackgroundScheduler(daemon=True)
            sched.add_job(_alert_tick, IntervalTrigger(minutes=15), id="nr2-alerts")
            sched.add_job(_hal_autonomous_tick, IntervalTrigger(minutes=15), id="nr2-hal-autonomous")
            sched.add_job(_morning_tick, CronTrigger(hour=6, minute=30), id="nr2-morning")
            sched.add_job(_eod_tick, CronTrigger(hour=22, minute=0), id="nr2-eod")
            # Next-day Trellis eligibility — Mon–Thu 22:00 local (chair days Mon–Thu).
            sched.add_job(
                _trellis_verify_tick,
                CronTrigger(day_of_week="mon-thu", hour=22, minute=0),
                id="nr2-trellis-verify",
            )
            # Proactive health every 6 hours (Moonshot REC-004).
            sched.add_job(_health_monitor_tick, IntervalTrigger(hours=6), id="nr2-health-monitor")
            sched.start()
            print(
                "NR2 background scheduler: alerts+HAL autonomy every 15m, health every 6h, "
                "morning 06:30, EOD handoff 22:00, Trellis verify Mon–Thu 22:00",
                file=sys.stderr,
            )
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
