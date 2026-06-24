from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Mapping


logger = logging.getLogger(__name__)
_WIDGET_FEED_LOCK = Lock()
_LATEST_WIDGET_FEED: dict[str, Any] | None = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_cache_path() -> Path:
    configured = os.getenv("WIDGET_FEED_CACHE_PATH", "").strip()
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            candidate = _project_root() / candidate
        return candidate.expanduser().resolve()
    return _project_root() / "app" / "data" / "cache" / "import_widget_feed.json"


def _cache_path() -> Path:
    override = getattr(_cache_path, "_override", None)
    if isinstance(override, Path):
        return override
    return _default_cache_path()


def configure_widget_feed_cache_path(path: Path | None) -> None:
    _cache_path._override = path  # type: ignore[attr-defined]


def _require_mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"Widget update payload field {field_name} must be a JSON object")
    return dict(value)


def _validate_widget_feed_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    manager = str(payload.get("manager") or "").strip()
    if not manager:
        raise ValueError("Widget update payload must include manager")

    widgets = _require_mapping(payload.get("widgets"), field_name="widgets")
    if not widgets:
        raise ValueError("Widget update payload must include at least one widget")

    return {
        "manager": manager,
        "run_id": str(payload.get("run_id") or "").strip() or None,
        "generated_at": str(payload.get("generated_at") or "").strip() or _utc_now_iso(),
        "received_at": str(payload.get("received_at") or "").strip() or _utc_now_iso(),
        "widgets": deepcopy(widgets),
        "sources": deepcopy(_require_mapping(payload.get("sources"), field_name="sources")),
        "jobs": deepcopy(_require_mapping(payload.get("jobs"), field_name="jobs")),
    }


def _write_persisted_widget_feed(payload: dict[str, Any]) -> None:
    cache_path = _cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_persisted_widget_feed() -> dict[str, Any] | None:
    cache_path = _cache_path()
    if not cache_path.is_file():
        return None
    try:
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("Ignoring corrupt widget feed cache at %s: %s", cache_path, exc)
        return None
    if not isinstance(raw, dict):
        logger.warning("Ignoring invalid widget feed cache shape at %s", cache_path)
        return None
    try:
        return _validate_widget_feed_payload(raw)
    except ValueError as exc:
        logger.warning("Ignoring invalid widget feed cache payload at %s: %s", cache_path, exc)
        return None


def load_widget_feed_from_disk() -> dict[str, Any] | None:
    with _WIDGET_FEED_LOCK:
        global _LATEST_WIDGET_FEED
        if _LATEST_WIDGET_FEED is not None:
            return deepcopy(_LATEST_WIDGET_FEED)
        persisted = _read_persisted_widget_feed()
        if persisted is None:
            return None
        _LATEST_WIDGET_FEED = persisted
        return deepcopy(persisted)


def record_widget_feed(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _validate_widget_feed_payload(payload)
    normalized["received_at"] = _utc_now_iso()

    with _WIDGET_FEED_LOCK:
        global _LATEST_WIDGET_FEED
        _LATEST_WIDGET_FEED = normalized

    try:
        _write_persisted_widget_feed(normalized)
    except OSError as exc:
        logger.warning("Failed to persist widget feed cache: %s", exc)

    return deepcopy(normalized)


def get_widget_feed() -> dict[str, Any] | None:
    global _LATEST_WIDGET_FEED
    with _WIDGET_FEED_LOCK:
        if _LATEST_WIDGET_FEED is not None:
            return deepcopy(_LATEST_WIDGET_FEED)

    persisted = _read_persisted_widget_feed()
    if persisted is None:
        return None

    with _WIDGET_FEED_LOCK:
        if _LATEST_WIDGET_FEED is None:
            _LATEST_WIDGET_FEED = persisted
        return deepcopy(_LATEST_WIDGET_FEED)


def clear_widget_feed() -> None:
    with _WIDGET_FEED_LOCK:
        global _LATEST_WIDGET_FEED
        _LATEST_WIDGET_FEED = None

    cache_path = _cache_path()
    if cache_path.is_file():
        try:
            cache_path.unlink()
        except OSError as exc:
            logger.warning("Failed to delete widget feed cache at %s: %s", cache_path, exc)


def reset_widget_feed_memory() -> None:
    with _WIDGET_FEED_LOCK:
        global _LATEST_WIDGET_FEED
        _LATEST_WIDGET_FEED = None


__all__ = [
    "clear_widget_feed",
    "configure_widget_feed_cache_path",
    "get_widget_feed",
    "load_widget_feed_from_disk",
    "record_widget_feed",
    "reset_widget_feed_memory",
]
