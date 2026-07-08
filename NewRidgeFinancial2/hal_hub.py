"""HAL hub — inbound queue, office channel dispatch, SAPI announcements on hub PC."""

from __future__ import annotations

import json
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
NR2_DIR = Path(__file__).resolve().parent
DEFAULT_HUB_DATA = REPO_ROOT / "app_data" / "nr2" / "office"
SIDENOTES_HELPER = NR2_DIR / "sidenotes-helper"

_hub_lock = threading.Lock()
_announcer: Any = None
_announcer_lock = threading.Lock()

INBOUND_SCHEMA = "nr2-hal-hub-inbound-v1"
OFFICE_SCHEMA = "nr2-office-channel-v1"
STATIONS_SCHEMA = "nr2-office-stations-v1"
MAX_MESSAGES = 200
STATION_STALE_SECONDS = 90

CANONICAL_STATIONS = [
    "Frontdesk 1",
    "Frontdesk 2",
    "Office Manager",
    "Room 1",
    "Room 2",
    "Room 3",
    "Room 4",
    "Room 5",
    "Server",
    "Darkroom",
]


def resolve_hub_data_dir() -> Path:
    raw = os.environ.get("NR2_OFFICE_HUB_DATA", "").strip()
    if raw:
        return Path(raw)
    return DEFAULT_HUB_DATA


def inbound_path() -> Path:
    return resolve_hub_data_dir() / "hal-hub-inbound.json"


def office_channel_path() -> Path:
    return resolve_hub_data_dir() / "office-channel.json"


def stations_registry_path() -> Path:
    return resolve_hub_data_dir() / "office-stations.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path, default: dict) -> dict:
    if not path.is_file():
        return dict(default)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return dict(default)
    return data if isinstance(data, dict) else dict(default)


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _normalize_targets(raw: Any) -> tuple[str, list[str]]:
    if isinstance(raw, list) and raw:
        cleaned = [str(t).strip() for t in raw if str(t).strip()]
        if any(t.lower() in ("all", "everyone") for t in cleaned):
            return "all", ["all"]
        return ", ".join(cleaned), cleaned
    single = str(raw or "all").strip()
    if not single or single.lower() in ("all", "everyone"):
        return "all", ["all"]
    if "," in single:
        parts = [p.strip() for p in single.split(",") if p.strip()]
        return single, parts if parts else ["all"]
    return single, [single]


def load_office_channel() -> dict:
    data = _load_json(office_channel_path(), {"schema": OFFICE_SCHEMA, "messages": [], "updatedAt": None})
    if not isinstance(data.get("messages"), list):
        data["messages"] = []
    data["schema"] = OFFICE_SCHEMA
    return data


def save_office_channel(data: dict) -> None:
    data["schema"] = OFFICE_SCHEMA
    data["updatedAt"] = _now_iso()
    _save_json(office_channel_path(), data)


def append_office_channel_message(msg: dict) -> dict:
    text = str(msg.get("text") or "").strip()
    if not text:
        raise ValueError("empty text")
    role = str(msg.get("role") or "staff").lower()
    target_label, targets = _normalize_targets(msg.get("targets") or msg.get("target"))
    entry = {
        "id": str(msg.get("id") or uuid.uuid4()),
        "at": str(msg.get("at") or _now_iso()),
        "from": str(msg.get("from") or ("HAL" if role == "hal" else "Staff")),
        "role": "hal" if role == "hal" else "staff",
        "text": text,
        "speak": bool(msg.get("speak")) if msg.get("speak") is not None else False,
        "type": str(msg.get("type") or ("workflow" if role == "hal" else "announce")),
        "target": target_label,
        "targets": targets,
    }
    if "hubAnnounced" in msg:
        entry["hubAnnounced"] = bool(msg.get("hubAnnounced"))
    with _hub_lock:
        data = load_office_channel()
        messages = data.setdefault("messages", [])
        messages.append(entry)
        if len(messages) > MAX_MESSAGES:
            data["messages"] = messages[-MAX_MESSAGES:]
        save_office_channel(data)
    if any(str(t).lower() in ("all", "everyone") for t in targets):
        record_hub_broadcast(
            {
                "at": entry["at"],
                "from": entry["from"],
                "channel": "office",
                "target": target_label,
            }
        )
    return entry


_last_hub_broadcast: dict = {}

_HUB_TOKEN_PATH = REPO_ROOT / "app_data" / "nr2" / "hub_token.txt"


def resolve_hub_token() -> str:
    env = os.environ.get("NR2_HUB_TOKEN", "").strip()
    if env:
        return env
    _HUB_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _HUB_TOKEN_PATH.is_file():
        return _HUB_TOKEN_PATH.read_text(encoding="utf-8").strip()
    import secrets

    token = secrets.token_urlsafe(32)
    _HUB_TOKEN_PATH.write_text(token, encoding="utf-8")
    return token


def hub_token_header_valid(header: str | None) -> bool:
    import secrets

    expected = resolve_hub_token()
    if not expected:
        return False
    return secrets.compare_digest(str(header or "").strip(), expected)


def _normalize_hub_origin(origin: str | None) -> str:
    return str(origin or "").strip().lower().rstrip("/")


def hub_notify_allowed_origins() -> set[str]:
    origins = {
        "http://127.0.0.1:8766",
        "http://localhost:8766",
        "https://127.0.0.1:8766",
        "https://localhost:8766",
        "http://[::1]:8766",
        "https://[::1]:8766",
    }
    extra = os.environ.get("NR2_HUB_ORIGIN", "").strip()
    if extra:
        origins.add(_normalize_hub_origin(extra))
    return origins


def hub_notify_origin_ok(origin: str | None = None) -> bool:
    if origin is None:
        import bottle

        origin = bottle.request.headers.get("Origin")
    normalized = _normalize_hub_origin(origin)
    if not normalized or normalized == "null":
        return False
    return normalized in hub_notify_allowed_origins()


def hub_last_broadcast_access_ok(header: str | None = None) -> bool:
    if header is None:
        import bottle

        header = bottle.request.headers.get("X-Hub-Token")
    return hub_token_header_valid(header)


def hub_notify_access_ok(origin: str | None = None, header: str | None = None) -> bool:
    if header is None:
        import bottle

        header = bottle.request.headers.get("X-Hub-Token")
    if not hub_notify_origin_ok(origin):
        return False
    return hub_token_header_valid(header)


def record_hub_broadcast(payload: dict) -> None:
    global _last_hub_broadcast
    _last_hub_broadcast = {
        "at": str(payload.get("at") or _now_iso()),
        "from": str(payload.get("from") or ""),
        "channel": str(payload.get("channel") or "office"),
        "target": str(payload.get("target") or "all"),
    }


def last_hub_broadcast() -> dict:
    return dict(_last_hub_broadcast)


def _load_inbound() -> dict:
    data = _load_json(inbound_path(), {"schema": INBOUND_SCHEMA, "pending": []})
    if not isinstance(data.get("pending"), list):
        data["pending"] = []
    data["schema"] = INBOUND_SCHEMA
    return data


def _save_inbound(data: dict) -> None:
    data["schema"] = INBOUND_SCHEMA
    data["updatedAt"] = _now_iso()
    _save_json(inbound_path(), data)


def submit_inbound(
    from_station: str,
    targets: list[str] | None,
    text: str,
    speak: bool = False,
    *,
    role: str = "staff",
    type_: str = "announce",
) -> dict:
    text = str(text or "").strip()
    if not text:
        raise ValueError("empty text")
    from_station = str(from_station or "Staff").strip() or "Staff"
    _, norm_targets = _normalize_targets(targets or ["all"])
    item = {
        "id": str(uuid.uuid4()),
        "at": _now_iso(),
        "from": from_station,
        "targets": norm_targets,
        "text": text,
        "speak": bool(speak),
        "role": str(role or "staff").lower(),
        "type": str(type_ or "announce"),
        "status": "pending",
    }
    with _hub_lock:
        data = _load_inbound()
        data.setdefault("pending", []).append(item)
        _save_inbound(data)
    return item


def get_pending() -> list[dict]:
    with _hub_lock:
        return list(_load_inbound().get("pending") or [])


def _ensure_announcer_path() -> None:
    helper = SIDENOTES_HELPER
    if helper.is_dir() and str(helper) not in sys.path:
        sys.path.insert(0, str(helper))


def _get_announcer():
    global _announcer
    with _announcer_lock:
        if _announcer is not None:
            return _announcer
        _ensure_announcer_path()
        from announcer import Announcer, MusicDucker

        ducker = None
        duck_env = os.environ.get("NR2_HAL_HUB_DUCK_MUSIC", "1").strip().lower()
        if duck_env in ("1", "true", "yes"):
            procs = [
                p.strip()
                for p in os.environ.get("NR2_HAL_HUB_DUCK_PROCESSES", "Pandora.exe").split(",")
                if p.strip()
            ]
            ducker = MusicDucker(
                process_names=procs or ["Pandora.exe"],
                duck_level=float(os.environ.get("NR2_HAL_HUB_DUCK_LEVEL", "0.14")),
            )
        style = os.environ.get("NR2_HAL_HUB_VOICE_STYLE", "hal9000").strip()
        _announcer = Announcer(
            voice_style=style,
            music_ducker=ducker,
            processed_audio=True,
            rate=int(os.environ.get("NR2_HAL_HUB_VOICE_RATE", "-6")),
            volume=int(os.environ.get("NR2_HAL_HUB_VOICE_VOLUME", "90")),
            voice_hint=os.environ.get("NR2_HAL_HUB_VOICE_HINT", "David"),
        )
        return _announcer


def hub_announce(
    text: str,
    *,
    sender: str = "",
    broadcast: bool = False,
    phrase_only: bool = False,
) -> dict:
    """Duck background music and speak once on the hub PC."""
    try:
        line = str(text or "").strip()
        if phrase_only or (sender and not line):
            try:
                _ensure_announcer_path()
                from announcer import pick_announcement

                line = pick_announcement(
                    str(sender or "Unknown").strip() or "Unknown",
                    bool(broadcast),
                )
            except Exception:
                sender_name = str(sender or "Unknown").strip() or "Unknown"
                line = (
                    f"A broadcast message has arrived from {sender_name}."
                    if broadcast
                    else f"I have a message for you from {sender_name}."
                )
        if not line:
            return {"ok": False, "error": "empty text"}
        announcer = _get_announcer()
        announcer.speak(line)
        return {
            "ok": True,
            "spoken": line,
            "sender": sender or None,
            "broadcast": bool(broadcast),
            "phraseOnly": bool(phrase_only or (sender and not text)),
            "voiceStyle": getattr(announcer, "voice_style", "default"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def process_pending() -> dict:
    """Dispatch pending inbound messages to office-channel; announce when speak is true."""
    processed: list[dict] = []
    errors: list[dict] = []
    with _hub_lock:
        data = _load_inbound()
        pending = list(data.get("pending") or [])
        if not pending:
            return {"ok": True, "processed": 0, "messages": [], "errors": []}
        data["pending"] = []
        _save_inbound(data)

    for item in pending:
        try:
            from_station = str(item.get("from") or "Staff")
            text = str(item.get("text") or "").strip()
            targets = item.get("targets") or ["all"]
            speak = bool(item.get("speak"))
            _, norm_targets = _normalize_targets(targets)
            broadcast = norm_targets == ["all"] or any(
                str(t).lower() in ("all", "everyone") for t in norm_targets
            )
            announced = False
            if speak:
                announce_result = hub_announce(
                    "",
                    sender=from_station,
                    broadcast=broadcast,
                    phrase_only=True,
                )
                announced = bool(announce_result.get("ok"))
            entry = append_office_channel_message(
                {
                    "from": from_station,
                    "targets": norm_targets,
                    "text": text,
                    "speak": False,
                    "hubAnnounced": announced,
                    "role": str(item.get("role") or "staff"),
                    "type": str(item.get("type") or ("announce" if speak else "note")),
                }
            )
            processed.append({"inboundId": item.get("id"), "message": entry, "announced": announced})
        except Exception as exc:
            errors.append({"inboundId": item.get("id"), "error": str(exc)})

    return {"ok": True, "processed": len(processed), "messages": processed, "errors": errors}


def _normalize_station_name(value: str) -> str:
    return " ".join(str(value or "").replace("_", " ").replace("-", " ").split()).lower()


def _load_stations_registry() -> dict:
    data = _load_json(
        stations_registry_path(),
        {"schema": STATIONS_SCHEMA, "stations": []},
    )
    if not isinstance(data.get("stations"), list):
        data["stations"] = []
    data["schema"] = STATIONS_SCHEMA
    return data


def _save_stations_registry(data: dict) -> None:
    data["schema"] = STATIONS_SCHEMA
    data["updatedAt"] = _now_iso()
    _save_json(stations_registry_path(), data)


def register_station_heartbeat(
    station: str,
    *,
    host: str = "",
    port: int | None = None,
    source: str = "nr2-workstation",
    program_id: str = "nr2-workstation",
) -> dict:
    name = str(station or "").strip()
    if not name:
        raise ValueError("empty station")
    now = _now_iso()
    entry = {
        "station": name,
        "host": str(host or "").strip(),
        "port": int(port) if port is not None else None,
        "source": str(source or "nr2-workstation").strip() or "nr2-workstation",
        "programId": str(program_id or "nr2-workstation").strip() or "nr2-workstation",
        "lastSeen": now,
        "checkedAt": now,
    }
    key = _normalize_station_name(name)
    with _hub_lock:
        data = _load_stations_registry()
        stations = list(data.get("stations") or [])
        replaced = False
        for idx, row in enumerate(stations):
            if _normalize_station_name(str(row.get("station") or "")) == key:
                prev = stations[idx] if isinstance(row, dict) else {}
                entry["host"] = entry["host"] or str(prev.get("host") or "")
                if entry["port"] is None and prev.get("port") is not None:
                    entry["port"] = prev.get("port")
                stations[idx] = entry
                replaced = True
                break
        if not replaced:
            stations.append(entry)
        data["stations"] = stations
        _save_stations_registry(data)
    return entry


def _station_is_live(last_seen: str | None) -> bool:
    if not last_seen:
        return False
    try:
        seen = datetime.fromisoformat(str(last_seen).replace("Z", "+00:00"))
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - seen.astimezone(timezone.utc)).total_seconds()
        return age <= STATION_STALE_SECONDS
    except ValueError:
        return False


def build_station_monitor_rows(extra_rows: list[dict] | None = None) -> list[dict]:
    """Merge NR2 workstation heartbeats with optional SideNotes-style monitor rows."""
    registry = _load_stations_registry()
    by_name: dict[str, dict] = {}
    for row in extra_rows or []:
        if not isinstance(row, dict):
            continue
        station = str(row.get("station") or "").strip()
        if not station:
            continue
        by_name[_normalize_station_name(station)] = dict(row)

    for entry in registry.get("stations") or []:
        if not isinstance(entry, dict):
            continue
        station = str(entry.get("station") or "").strip()
        if not station:
            continue
        key = _normalize_station_name(station)
        live = _station_is_live(entry.get("lastSeen") or entry.get("checkedAt"))
        nr2_row = {
            "station": station,
            "live": live,
            "status": "live" if live else "offline",
            "source": str(entry.get("source") or "nr2-workstation"),
            "programId": str(entry.get("programId") or "nr2-workstation"),
            "host": entry.get("host") or "",
            "port": entry.get("port"),
            "checkedAt": entry.get("lastSeen") or entry.get("checkedAt") or "",
            "announce": False,
            "bellSuppressed": False,
        }
        prev = by_name.get(key)
        if prev and prev.get("live") and str(prev.get("source") or "").startswith("sidenotes"):
            nr2_row["sidenotesLive"] = True
            nr2_row["live"] = True
            nr2_row["status"] = "live"
            nr2_row["announce"] = bool(prev.get("announce"))
            nr2_row["bellSuppressed"] = bool(prev.get("bellSuppressed"))
            nr2_row["voiceStyle"] = prev.get("voiceStyle") or ""
        by_name[key] = nr2_row if live or not prev else prev

    roster: list[dict] = []
    for name in CANONICAL_STATIONS:
        hit = by_name.get(_normalize_station_name(name))
        if hit:
            roster.append({**hit, "station": name, "live": hit.get("live") is True})
        else:
            roster.append(
                {
                    "station": name,
                    "live": False,
                    "status": "offline",
                    "source": "",
                    "announce": False,
                    "bellSuppressed": False,
                    "checkedAt": "",
                }
            )
    return roster


def stations_status(extra_monitor_rows: list[dict] | None = None) -> dict:
    roster = build_station_monitor_rows(extra_monitor_rows)
    live_rows = [row for row in roster if row.get("live")]
    checked_at = ""
    for row in roster:
        ts = str(row.get("checkedAt") or "")
        if ts and ts > checked_at:
            checked_at = ts
    nr2_live = sum(
        1 for row in live_rows if str(row.get("source") or "").startswith("nr2")
    )
    return {
        "ok": True,
        "schema": STATIONS_SCHEMA,
        "registryPath": str(stations_registry_path()),
        "totalStations": len(CANONICAL_STATIONS),
        "stationCount": len(live_rows),
        "nr2WorkstationCount": nr2_live,
        "checkedAt": checked_at or None,
        "stations": roster,
        "monitor": {
            "checkedAt": checked_at or None,
            "station": "Network" if len(live_rows) != 1 else (live_rows[0].get("station") if live_rows else "Network"),
            "status": "live" if live_rows else "offline",
            "stationCount": len(live_rows),
            "totalStations": len(CANONICAL_STATIONS),
            "stations": roster,
        },
    }


def resolve_hal_hub_url(port: int | None = None) -> str:
    """Hub URL for LAN workstations — env override, else LAN IP of this PC."""
    raw = os.environ.get("NR2_HAL_HUB_URL", "").strip()
    if raw:
        return raw.rstrip("/")
    http_port = port or int(os.environ.get("NR2_HTTP_PORT", "8765"))
    try:
        import socket

        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        ip = probe.getsockname()[0]
        probe.close()
        return f"http://{ip}:{http_port}"
    except OSError:
        return f"http://127.0.0.1:{http_port}"


def hub_cross_status() -> dict:
    """Moonshot cross-runtime — 8765 polls workstation reachability + last broadcast."""
    stations = stations_status()
    ws_live = int(stations.get("nr2WorkstationCount") or 0) > 0
    broadcast = last_hub_broadcast()
    return {
        "ok": True,
        "workstationReachable": ws_live,
        "stationCount": stations.get("stationCount"),
        "totalStations": stations.get("totalStations"),
        "nr2WorkstationCount": stations.get("nr2WorkstationCount"),
        "lastBroadcast": broadcast if broadcast else None,
    }


def hub_status() -> dict:
    pending = get_pending()
    channel = load_office_channel()
    stations = stations_status()
    return {
        "ok": True,
        "hubDataDir": str(resolve_hub_data_dir()),
        "inboundPath": str(inbound_path()),
        "officeChannelPath": str(office_channel_path()),
        "stationsRegistryPath": str(stations_registry_path()),
        "halHubUrl": resolve_hal_hub_url(),
        "pendingCount": len(pending),
        "messageCount": len(channel.get("messages") or []),
        "stationCount": stations.get("stationCount"),
        "totalStations": stations.get("totalStations"),
        "updatedAt": channel.get("updatedAt"),
    }
