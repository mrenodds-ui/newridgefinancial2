"""Poll local SideNotesIM history and queue desktop popups (matches SideNotesIM.exe notify path)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Callable

from hub_message_watcher import resolve_station


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name, "1" if default else "0").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _state_path(data_dir: Path) -> Path:
    return data_dir / "sidenotes-popup-watcher-state.json"


def load_seen_ids(data_dir: Path) -> set[str]:
    path = _state_path(data_dir)
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        ids = data.get("seenIds") if isinstance(data, dict) else []
        return {str(x) for x in ids if x}
    except Exception:
        return set()


def save_seen_ids(data_dir: Path, seen: set[str]) -> None:
    path = _state_path(data_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"seenIds": list(seen)[-800:]}, indent=2), encoding="utf-8")
    except Exception:
        pass


def _norm_station(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def sidenotes_message_for_station(message: dict, station: str) -> bool:
    station_key = _norm_station(station)
    target = _norm_station((message or {}).get("target") or "")
    targets = (message or {}).get("targets") or []
    if any(_norm_station(t) in ("all", "everyone") for t in targets):
        return True
    if target in ("all", "everyone"):
        return True
    if not station_key:
        return True
    if target == station_key:
        return True
    return any(_norm_station(t) == station_key for t in targets)


def fetch_sidenotes_messages(station: str) -> list[dict]:
    from sidenotes_bridge import sidenotes_read_messages

    live = sidenotes_read_messages(station=station, limit=48, include_body=True)
    if not live or not live.get("ok"):
        return []
    messages = live.get("messages")
    return messages if isinstance(messages, list) else []


def run_sidenotes_popup_watcher(
    *,
    enqueue_popup: Callable[[dict], None],
    data_dir: Path,
    poll_seconds: float | None = None,
) -> None:
    poll = float(
        poll_seconds if poll_seconds is not None else os.environ.get("NR2_SIDENOTES_POPUP_POLL", "2")
    )
    seen = load_seen_ids(data_dir)
    baseline_done = bool(seen)

    while True:
        station = resolve_station(data_dir)
        try:
            messages = fetch_sidenotes_messages(station)
            for message in messages:
                if not isinstance(message, dict):
                    continue
                raw_id = str(message.get("id") or "").strip()
                if not raw_id:
                    continue
                msg_id = raw_id if raw_id.startswith("sn-") else f"sn-{raw_id}"
                if not baseline_done:
                    seen.add(msg_id)
                    continue
                if msg_id in seen:
                    continue
                seen.add(msg_id)
                if not sidenotes_message_for_station(message, station):
                    continue
                from_name = str(message.get("from") or "").strip()
                if station and _norm_station(from_name) == _norm_station(station):
                    continue
                if message.get("unread") is False:
                    continue
                text = str(message.get("text") or "").strip()
                if not text:
                    continue
                enqueue_popup(
                    {
                        "id": msg_id,
                        "from": from_name or "Office",
                        "text": text,
                        "target": message.get("target"),
                        "targets": message.get("targets"),
                        "source": "sidenotes",
                    }
                )
            if not baseline_done:
                baseline_done = True
            save_seen_ids(data_dir, seen)
        except Exception:
            pass
        time.sleep(max(1.0, poll))
