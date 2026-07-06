"""Poll the HAL hub office channel and queue desktop popups (no messenger UI required)."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name, "1" if default else "0").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _station_file(data_dir: Path) -> Path:
    return data_dir / "workstation-popup-station.json"


def resolve_station(data_dir: Path) -> str:
    env_station = os.environ.get("NR2_SIDENOTES_MY_STATION", "").strip()
    if env_station:
        return env_station
    env_station = os.environ.get("NR2_WORKSTATION_STATION", "").strip()
    if env_station:
        return env_station
    path = _station_file(data_dir)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            station = str(data.get("station") or "").strip()
            if station:
                return station
        except Exception:
            pass
    cfg_path = Path(__file__).resolve().parent / "sidenotes-helper" / "config.json"
    if cfg_path.is_file():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            station = str(cfg.get("myStation") or "").strip()
            if station:
                return station
        except Exception:
            pass
    return ""


def save_station(data_dir: Path, station: str) -> None:
    station = str(station or "").strip()
    if not station:
        return
    path = _station_file(data_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"station": station}, indent=2), encoding="utf-8")
    except Exception:
        pass


def _state_path(data_dir: Path) -> Path:
    return data_dir / "hub-popup-watcher-state.json"


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
        trimmed = list(seen)[-800:]
        path.write_text(json.dumps({"seenIds": trimmed}, indent=2), encoding="utf-8")
    except Exception:
        pass


def _normalize_targets(message: dict) -> list[str]:
    raw = message.get("targets")
    if isinstance(raw, list) and raw:
        cleaned = [str(t).strip() for t in raw if str(t).strip()]
        if any(t.lower() in ("all", "everyone") for t in cleaned):
            return ["all"]
        return cleaned
    single = str(message.get("target") or "all").strip()
    if not single or single.lower() in ("all", "everyone"):
        return ["all"]
    if "," in single:
        parts = [p.strip() for p in single.split(",") if p.strip()]
        return parts if parts else ["all"]
    return [single]


def message_for_station(message: dict, station: str) -> bool:
    targets = _normalize_targets(message or {})
    if any(t.lower() in ("all", "everyone") for t in targets):
        return True
    station_key = str(station or "").strip().lower()
    if not station_key:
        return True
    return any(str(t).strip().lower() == station_key for t in targets)


def fetch_office_channel(hub_url: str) -> dict:
    url = f"{hub_url.rstrip('/')}/api/office-channel"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def maybe_announce(message: dict) -> None:
    if not _env_flag("NR2_HUB_POPUP_ANNOUNCE", True):
        return
    try:
        helper = Path(__file__).resolve().parent / "sidenotes-helper"
        if helper.is_dir():
            import sys

            if str(helper) not in sys.path:
                sys.path.insert(0, str(helper))
        from announcer import Announcer

        sender = str(message.get("from") or "Office").strip() or "Office"
        targets = _normalize_targets(message)
        broadcast = any(t.lower() in ("all", "everyone") for t in targets)
        phrase = f"New broadcast from {sender}." if broadcast else f"New message from {sender}."
        Announcer(voice_style=os.environ.get("NR2_HUB_POPUP_VOICE_STYLE", "hal9000")).speak(phrase)
    except Exception:
        pass


def run_hub_popup_watcher(
    *,
    enqueue_popup: Callable[[dict], None],
    hub_url: str,
    data_dir: Path,
    poll_seconds: float | None = None,
) -> None:
    poll = float(poll_seconds if poll_seconds is not None else os.environ.get("NR2_HUB_POPUP_POLL", "3"))
    seen = load_seen_ids(data_dir)
    baseline_done = bool(seen)
    if not baseline_done and _env_flag("NR2_HUB_POPUP_BASELINE_ON_START", True):
        baseline_done = False

    while True:
        station = resolve_station(data_dir)
        try:
            channel = fetch_office_channel(hub_url)
            messages = channel.get("messages") if isinstance(channel, dict) else []
            if not isinstance(messages, list):
                messages = []
            for message in messages:
                if not isinstance(message, dict):
                    continue
                msg_id = str(message.get("id") or "").strip()
                if not msg_id:
                    continue
                if not baseline_done:
                    seen.add(msg_id)
                    continue
                if msg_id in seen:
                    continue
                seen.add(msg_id)
                if not message_for_station(message, station):
                    continue
                from_name = str(message.get("from") or "").strip()
                if (
                    station
                    and from_name.lower() == station.lower()
                    and not _env_flag("NR2_HUB_POPUP_SHOW_SELF", True)
                ):
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
                    }
                )
                maybe_announce(message)
            if not baseline_done:
                baseline_done = True
            save_seen_ids(data_dir, seen)
        except urllib.error.URLError:
            pass
        except Exception:
            pass
        time.sleep(max(1.0, poll))
