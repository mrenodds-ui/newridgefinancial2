#!/usr/bin/env python3
"""
NewRidgeFinancial 2.0 — single-window desktop program.

One process, one window, local UI assets, local SQLite storage.
No separate backend server, no localhost API, no external browser.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
SITE_DIR = ROOT / "site"
DATA_DIR = REPO_ROOT / "app_data" / "nr2"
INDEX_HTML = SITE_DIR / "index.html"


class DesktopApi:
    """JavaScript bridge: local files + SQLite only."""

    def __init__(self, site_dir: Path, data_dir: Path) -> None:
        from local_store import LocalStore

        self.site_dir = site_dir
        self.store = LocalStore(data_dir)

    def get_app_info(self) -> dict:
        return {
            "mode": "desktop",
            "version": "2.0",
            "dataDir": str(self.store.data_dir),
            "dbPath": str(self.store.db_path),
        }

    def read_data_file(self, name: str) -> str:
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
