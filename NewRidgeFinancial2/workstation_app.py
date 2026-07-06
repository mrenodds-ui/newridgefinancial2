#!/usr/bin/env python3
"""
NR2 Office Workstation — standalone desktop program.

Send Message + Ask HAL only. Separate from NewRidgeFinancial 2.0 owner/financial app.
"""

from __future__ import annotations

import os
import sys
import threading
import urllib.parse
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE_DIR = ROOT / "site"
INDEX_HTML = SITE_DIR / "workstation" / "index.html"

from desktop_app import (  # noqa: E402
    DATA_DIR,
    DESIGN_SCHEMA_VERSION,
    DesktopApi,
)

WORKSTATION_WEBVIEW_DIR = DATA_DIR / "webview-workstation" / DESIGN_SCHEMA_VERSION
_watcher_proc = None
_popup_lock = threading.Lock()
_popup_windows: dict[str, object] = {}
_popup_queue: list[dict] = []
_popup_queue_lock = threading.Lock()

# SideNotesIM main window size (measured from live SideNotesIM.exe).
WORKSTATION_WINDOW_WIDTH = int(os.environ.get("NR2_WORKSTATION_WIDTH", "536"))
WORKSTATION_WINDOW_HEIGHT = int(os.environ.get("NR2_WORKSTATION_HEIGHT", "447"))
WORKSTATION_WINDOW_MIN = (
    int(os.environ.get("NR2_WORKSTATION_MIN_WIDTH", "480")),
    int(os.environ.get("NR2_WORKSTATION_MIN_HEIGHT", "400")),
)


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name, "1" if default else "0").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _center_window_pos(width: int, height: int) -> tuple[int, int]:
    """Place the main workstation window near the upper-right."""
    try:
        import ctypes

        user32 = ctypes.windll.user32
        screen_w = int(user32.GetSystemMetrics(0))
        screen_h = int(user32.GetSystemMetrics(1))
    except Exception:
        return (80, 80)
    margin = 24
    x = max(margin, screen_w - width - margin)
    y = margin
    return (x, y)


def _screen_work_area() -> tuple[int, int, int]:
    margin = int(os.environ.get("NR2_MSG_POPUP_MARGIN", "24"))
    try:
        import ctypes

        user32 = ctypes.windll.user32
        return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1)), margin
    except Exception:
        return 1280, 800, margin


def _popup_lower_right_pos(stack_index: int, width: int, height: int) -> tuple[int, int]:
    """Lower-right desktop anchor; stack_index 0 = bottom slot, higher = upward."""
    screen_w, screen_h, margin = _screen_work_area()
    gap = int(os.environ.get("NR2_MSG_POPUP_GAP", "10"))
    x = max(margin, screen_w - width - margin)
    bottom_y = max(margin, screen_h - height - margin)
    y = bottom_y - max(0, stack_index) * (height + gap)
    return (x, max(margin, y))


def _reposition_popup_stack(width: int, height: int) -> None:
    """Keep native balloons stacked upward from the lower-right (newest on bottom)."""
    with _popup_lock:
        wins = list(_popup_windows.values())
    for index, win in enumerate(reversed(wins)):
        x, y = _popup_lower_right_pos(index, width, height)
        try:
            win.move(x, y)
        except Exception:
            pass


def enqueue_message_popup(payload: dict) -> None:
    with _popup_queue_lock:
        _popup_queue.append(dict(payload or {}))


def drain_message_popups(api: "WorkstationApi") -> int:
    with _popup_queue_lock:
        batch = list(_popup_queue)
        _popup_queue.clear()
    for item in batch:
        api.show_workstation_message_popup(item)
    return len(batch)


def _workstation_window_title() -> str:
    custom = os.environ.get("NR2_WORKSTATION_TITLE", "").strip()
    if custom:
        return custom
    return "NR2 Workstation"
class WorkstationApi(DesktopApi):
    """Workstation shell — office channel via HAL hub relay."""

    def __init__(self, site_dir: Path, data_dir: Path) -> None:
        super().__init__(site_dir, data_dir)
        self._http_port = int(os.environ.get("NR2_WORKSTATION_PORT", "8766"))

    def get_app_info(self) -> dict:
        info = super().get_app_info()
        info["mode"] = "workstation"
        info["halHubUrl"] = os.environ.get("NR2_HAL_HUB_URL", "http://127.0.0.1:8765").strip()
        info["workstationPort"] = int(os.environ.get("NR2_WORKSTATION_PORT", "8766"))
        info["hubPopupWatcher"] = _env_flag("NR2_HUB_POPUP_WATCHER", True)
        info["workstationFastHal"] = _env_flag("NR2_WORKSTATION_FAST_HAL", True)
        return info

    def sidenotes_status(self) -> dict:
        from sidenotes_bridge import sidenotes_status

        return sidenotes_status()

    def sidenotes_fetch_messages(self, station: str = "", limit: int = 48) -> dict:
        from sidenotes_bridge import sidenotes_read_messages

        return sidenotes_read_messages(station=station, limit=int(limit), include_body=True)

    def sidenotes_send(self, from_station: str, to_station: str, text: str) -> dict:
        from sidenotes_bridge import sidenotes_send_message

        return sidenotes_send_message(from_station, to_station, text)

    def show_workstation_message_popup(self, payload: dict | None = None) -> dict:
        """Small always-on-top balloon for incoming messages (SideNotes-style)."""
        try:
            import webview
        except ImportError:
            return {"ok": False, "error": "pywebview unavailable"}

        data = payload if isinstance(payload, dict) else {}
        msg_id = str(data.get("id") or uuid.uuid4().hex)
        from_name = str(data.get("from") or "Office")[:120]
        text = str(data.get("text") or "")[:500]
        query = urllib.parse.urlencode({"from": from_name, "text": text})
        url = f"http://127.0.0.1:{self._http_port}/workstation/message-popup.html?{query}"
        width = int(os.environ.get("NR2_MSG_POPUP_WIDTH", "288"))
        height = int(os.environ.get("NR2_MSG_POPUP_HEIGHT", "152"))
        window_title = f"SideNotes IM — {from_name}"

        with _popup_lock:
            existing = _popup_windows.pop(msg_id, None)
        if existing is not None:
            try:
                existing.destroy()
            except Exception:
                pass

        x, y = _popup_lower_right_pos(0, width, height)
        try:
            win = webview.create_window(
                window_title,
                url,
                width=width,
                height=height,
                x=x,
                y=y,
                on_top=True,
                resizable=False,
                focus=False,
                minimized=False,
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        with _popup_lock:
            _popup_windows[msg_id] = win
            if len(_popup_windows) > 5:
                for old_id in list(_popup_windows.keys())[:-5]:
                    old_win = _popup_windows.pop(old_id, None)
                    if old_win is not None:
                        try:
                            old_win.destroy()
                        except Exception:
                            pass
        _reposition_popup_stack(width, height)
        return {"ok": True, "id": msg_id}

    def flush_message_popups(self) -> dict:
        count = drain_message_popups(self)
        return {"ok": True, "count": count}

    def set_popup_station(self, station: str) -> dict:
        from hub_message_watcher import save_station

        name = str(station or "").strip()
        if name:
            save_station(DATA_DIR, name)
        return {"ok": True, "station": name}

    def show_workstation_main_window(self) -> dict:
        try:
            import webview

            if webview.windows:
                win = webview.windows[0]
                try:
                    win.show()
                except Exception:
                    pass
                try:
                    win.restore()
                except Exception:
                    pass
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


def _start_hub_popup_watcher(api: WorkstationApi, hub_url: str) -> None:
    if not _env_flag("NR2_HUB_POPUP_WATCHER", True):
        return
    from hub_message_watcher import run_hub_popup_watcher

    threading.Thread(
        target=run_hub_popup_watcher,
        kwargs={
            "enqueue_popup": enqueue_message_popup,
            "hub_url": hub_url,
            "data_dir": DATA_DIR,
        },
        daemon=True,
        name="nr2-hub-popup-watcher",
    ).start()
    print("NR2 workstation: hub popup watcher started (messages show without opening messenger).", file=sys.stderr)


def _start_background_services(api: WorkstationApi, hal_hub_url: str) -> None:
    """Defer SideNotes + hub watchers so pywebview can open the UI first."""

    def _run() -> None:
        _start_sidenotes_watcher()
        _start_sidenotes_popup_watcher()
        _start_hub_popup_watcher(api, hal_hub_url)

    threading.Thread(
        target=_run,
        daemon=True,
        name="nr2-ws-background-services",
    ).start()


def _start_sidenotes_popup_watcher() -> None:
    if not _env_flag("NR2_SIDENOTES_POPUP_WATCHER", True):
        return
    from sidenotes_popup_watcher import run_sidenotes_popup_watcher

    threading.Thread(
        target=run_sidenotes_popup_watcher,
        kwargs={
            "enqueue_popup": enqueue_message_popup,
            "data_dir": DATA_DIR,
        },
        daemon=True,
        name="nr2-sidenotes-popup-watcher",
    ).start()
    print("NR2 workstation: SideNotes popup watcher started (vdb → desktop balloon).", file=sys.stderr)


def _start_sidenotes_watcher() -> None:
    global _watcher_proc
    from sidenotes_bridge import start_sidenotes_watcher

    station = os.environ.get("NR2_SIDENOTES_MY_STATION", "").strip() or None
    proc = start_sidenotes_watcher(station)
    if proc is not None:
        _watcher_proc = proc
        print(f"NR2 workstation: SideNotes watcher started (PID {proc.pid}).", file=sys.stderr)


def main() -> int:
    if not INDEX_HTML.is_file():
        print(f"Workstation site not found: {INDEX_HTML}", file=sys.stderr)
        return 1

    os.environ["NR2_WORKSTATION_APP"] = "1"

    try:
        import webview
    except ImportError:
        print("pywebview is required. Install with: pip install pywebview", file=sys.stderr)
        return 1

    api = WorkstationApi(SITE_DIR, DATA_DIR)
    WORKSTATION_WEBVIEW_DIR.mkdir(parents=True, exist_ok=True)
    default_port = 8766
    http_port = int(os.environ.get("NR2_WORKSTATION_PORT", str(default_port)))
    hal_hub_url = os.environ.get("NR2_HAL_HUB_URL", "http://127.0.0.1:8765").strip()
    _start_background_services(api, hal_hub_url)
    print(
        f"NR2 workstation: schema={DESIGN_SCHEMA_VERSION} entry={INDEX_HTML} port={http_port}",
        file=sys.stderr,
    )
    print(
        f"NR2 workstation: desktop app only — loopback port {http_port} is for the pywebview window, not a browser tab.",
        file=sys.stderr,
    )
    print(f"NR2 workstation: HAL hub URL={hal_hub_url} (set NR2_HAL_HUB_URL for LAN hub PC)", file=sys.stderr)

    from nr2_http_server import (
        NR2BottleServer,
        set_desktop_session_token,
        set_site_root,
        set_workstation_mode,
        set_workstation_show_callback,
    )

    set_workstation_mode(True)
    desktop_token = uuid.uuid4().hex
    set_desktop_session_token(desktop_token)
    set_site_root(SITE_DIR)
    set_workstation_show_callback(api.show_workstation_main_window)
    start_url = f"http://127.0.0.1:{http_port}/workstation/index.html?nr2dt={desktop_token}"
    win_x, win_y = _center_window_pos(WORKSTATION_WINDOW_WIDTH, WORKSTATION_WINDOW_HEIGHT)
    on_top = _env_flag("NR2_WORKSTATION_ON_TOP", True)
    start_hidden = _env_flag("NR2_WORKSTATION_START_HIDDEN", True)
    window = webview.create_window(
        _workstation_window_title(),
        start_url,
        width=WORKSTATION_WINDOW_WIDTH,
        height=WORKSTATION_WINDOW_HEIGHT,
        x=win_x,
        y=win_y,
        min_size=WORKSTATION_WINDOW_MIN,
        resizable=True,
        on_top=on_top,
        hidden=start_hidden,
        js_api=api,
        text_select=True,
        background_color="#ece9e4",
    )
    webview.start(
        debug=False,
        http_server=True,
        http_port=http_port,
        private_mode=True,
        storage_path=str(WORKSTATION_WEBVIEW_DIR),
        server=NR2BottleServer,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
