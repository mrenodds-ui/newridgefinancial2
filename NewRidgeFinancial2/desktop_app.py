#!/usr/bin/env python3
"""
NewRidgeFinancial 2.0 — single-window desktop program.

One process, one window, local UI assets, local SQLite storage.
No separate backend server, no localhost API, no external browser.
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

    def get_app_info(self) -> dict:
        return {
            "mode": "desktop",
            "version": "2.0",
            "dataDir": str(self.store.data_dir),
            "dbPath": str(self.store.db_path),
        }

    def read_data_file(self, name: str) -> str:
        if name.startswith("sidenotes-inbox"):
            hub_path = SIDENOTES_HUB_DATA_DIR / name
            if hub_path.is_file():
                return hub_path.read_text(encoding="utf-8")
            site_fallback = self.site_dir / "data" / name
            if site_fallback.is_file():
                return site_fallback.read_text(encoding="utf-8")
            return json.dumps({"items": [], "monitor": None})
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

    def get_import_bundle(self) -> dict:
        from import_loader import load_import_bundle

        return load_import_bundle(sync=False)

    def get_import_sync_status(self) -> dict:
        with self._sync_lock:
            return dict(self._sync_state)

    def _run_import_sync(self) -> None:
        from import_sync import sync_imports

        try:
            result = sync_imports()
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
    window = webview.create_window(
        "NewRidgeFinancial 2.0",
        INDEX_HTML.as_uri(),
        width=1440,
        height=920,
        min_size=(1024, 700),
        js_api=api,
    )
    webview.start(debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
