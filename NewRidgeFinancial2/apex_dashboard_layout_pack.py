"""
Phase U3 — Dashboard layout schema (Moonshot REAUDIT3 NICE).

Backend layout presets + persistence for Apex mosaic order/span.
Frontend applies via localStorage + optional server sync.
Preserves existing starship-bridge visual language (no theme rewrite).
Flag: NR2_DASHBOARD_LAYOUT (default ON).
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORE_KEY = "nr2:v2:apex:dashboard-layout"
MAX_ITEMS = 48

# Real widget ids used by Apex pages (evolves with packs; unknown ids ignored by UI).
DEFAULT_LAYOUTS: dict[str, dict[str, Any]] = {
    "financial": {
        "page": "financial",
        "theme": "starship-bridge",
        "version": 1,
        "grid": [
            {"id": "hal-ai-insight", "x": 0, "y": 0, "w": 12, "h": 3, "order": 0},
            {"id": "deep-audit-status", "x": 0, "y": 3, "w": 6, "h": 2, "order": 1},
            {"id": "reconciliation-status", "x": 6, "y": 3, "w": 6, "h": 2, "order": 2},
            {"id": "production-vs-payroll", "x": 0, "y": 5, "w": 6, "h": 2, "order": 3},
            {"id": "unified-db-snapshot", "x": 6, "y": 5, "w": 6, "h": 2, "order": 4},
            {"id": "import-quarantine-status", "x": 0, "y": 7, "w": 12, "h": 2, "order": 5},
        ],
    },
    "softdent": {
        "page": "softdent",
        "theme": "starship-bridge",
        "version": 1,
        "grid": [
            {"id": "softdent-collections-gap", "x": 0, "y": 0, "w": 12, "h": 2, "order": 0},
            {"id": "softdent-production-gap", "x": 0, "y": 2, "w": 6, "h": 2, "order": 1},
            {"id": "softdent-aging-gap", "x": 6, "y": 2, "w": 6, "h": 2, "order": 2},
            {"id": "era835-ingest-gap", "x": 0, "y": 4, "w": 12, "h": 2, "order": 3},
        ],
    },
    "quickbooks": {
        "page": "quickbooks",
        "theme": "starship-bridge",
        "version": 1,
        "grid": [
            {"id": "qb-net-profit-gap", "x": 0, "y": 0, "w": 6, "h": 2, "order": 0},
            {"id": "qb-payroll-gap", "x": 6, "y": 0, "w": 6, "h": 2, "order": 1},
            {"id": "qb-ap-gap", "x": 0, "y": 2, "w": 12, "h": 2, "order": 2},
        ],
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def layout_enabled() -> bool:
    raw = str(os.getenv("NR2_DASHBOARD_LAYOUT") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _layout_store_path() -> Path:
    override = str(os.getenv("NR2_LAYOUT_STORE") or "").strip()
    if override:
        return Path(override)
    try:
        from document_sync import NR2_DATA_DIR

        return Path(NR2_DATA_DIR) / "dashboard_layouts.json"
    except Exception:
        return Path(__file__).resolve().parent / "app_data" / "nr2" / "dashboard_layouts.json"


def _load_all() -> dict[str, Any]:
    path = _layout_store_path()
    if not path.is_file():
        return {"layouts": {}, "updatedAt": None}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {"layouts": {}}
    except Exception:
        return {"layouts": {}}


def _save_all(data: dict[str, Any]) -> None:
    path = _layout_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updatedAt"] = _utc_now()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        from document_sync import NR2_DATA_DIR
        from local_store import LocalStore

        LocalStore(NR2_DATA_DIR).set(STORE_KEY, json.dumps(data))
    except Exception:
        pass


def _sanitize_cell(cell: Any, *, idx: int) -> dict[str, Any] | None:
    if not isinstance(cell, dict):
        return None
    wid = str(cell.get("id") or "").strip()
    if not wid or not re.fullmatch(r"[a-zA-Z0-9_.:\-]{1,80}", wid):
        return None
    def _i(key: str, default: int, lo: int, hi: int) -> int:
        try:
            v = int(cell.get(key, default))
        except (TypeError, ValueError):
            v = default
        return max(lo, min(hi, v))

    return {
        "id": wid,
        "x": _i("x", 0, 0, 12),
        "y": _i("y", idx, 0, 200),
        "w": _i("w", 6, 1, 12),
        "h": _i("h", 2, 1, 12),
        "order": _i("order", idx, 0, 500),
    }


def sanitize_layout(layout: dict[str, Any] | None, *, page: str) -> dict[str, Any]:
    page_key = str(page or "financial").strip().lower() or "financial"
    base = DEFAULT_LAYOUTS.get(page_key) or {
        "page": page_key,
        "theme": "starship-bridge",
        "version": 1,
        "grid": [],
    }
    src = layout if isinstance(layout, dict) else {}
    grid_in = src.get("grid") if isinstance(src.get("grid"), list) else base.get("grid")
    grid: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, cell in enumerate(grid_in or []):
        clean = _sanitize_cell(cell, idx=i)
        if not clean or clean["id"] in seen:
            continue
        seen.add(clean["id"])
        grid.append(clean)
        if len(grid) >= MAX_ITEMS:
            break
    theme = str(src.get("theme") or base.get("theme") or "starship-bridge")[:64]
    # Do not invent alternate brand themes — stick to bridge family
    if theme not in {"starship-bridge", "starship-bridge-light", "starship-bridge-dark"}:
        theme = "starship-bridge"
    return {
        "page": page_key,
        "theme": theme,
        "version": int(src.get("version") or base.get("version") or 1),
        "grid": grid,
        "phase": "U3",
        "refreshedAt": _utc_now(),
    }


def get_layout(page: str | None = None, *, user_id: str | None = None) -> dict[str, Any]:
    """Return saved layout for page, else default. user_id reserved for multi-station."""
    del user_id
    if not layout_enabled():
        return {
            "ok": False,
            "reason": "layout_disabled",
            "hint": "Set NR2_DASHBOARD_LAYOUT=1 (default on).",
            "phase": "U3",
        }
    page_key = str(page or "financial").strip().lower() or "financial"
    data = _load_all()
    layouts = data.get("layouts") if isinstance(data.get("layouts"), dict) else {}
    saved = layouts.get(page_key)
    layout = sanitize_layout(saved if isinstance(saved, dict) else DEFAULT_LAYOUTS.get(page_key), page=page_key)
    return {
        "ok": True,
        "phase": "U3",
        "default": saved is None,
        "layout": layout,
        "localStorageKey": f"nr2:apex:layout:{page_key}",
        "refreshedAt": _utc_now(),
    }


def save_layout(
    layout: dict[str, Any] | None,
    *,
    page: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    del user_id
    if not layout_enabled():
        return {"ok": False, "reason": "layout_disabled", "phase": "U3"}
    page_key = str(page or (layout or {}).get("page") or "financial").strip().lower()
    clean = sanitize_layout(layout, page=page_key)
    data = _load_all()
    layouts = data.get("layouts") if isinstance(data.get("layouts"), dict) else {}
    layouts[page_key] = clean
    data["layouts"] = layouts
    _save_all(data)
    return {"ok": True, "phase": "U3", "layout": clean, "savedAt": _utc_now()}


def reset_layout(page: str | None = None) -> dict[str, Any]:
    if not layout_enabled():
        return {"ok": False, "reason": "layout_disabled", "phase": "U3"}
    page_key = str(page or "financial").strip().lower()
    data = _load_all()
    layouts = data.get("layouts") if isinstance(data.get("layouts"), dict) else {}
    if page_key in layouts:
        del layouts[page_key]
        data["layouts"] = layouts
        _save_all(data)
    return get_layout(page_key)


def order_widget_specs(specs: list[dict[str, Any]], *, page: str) -> list[dict[str, Any]]:
    """Reorder Apex widget specs by layout order; append unknowns after."""
    got = get_layout(page)
    if not got.get("ok"):
        return list(specs)
    layout = got.get("layout") if isinstance(got.get("layout"), dict) else {}
    grid = layout.get("grid") if isinstance(layout.get("grid"), list) else []
    order_map = {
        str(c.get("id")): int(c.get("order", i))
        for i, c in enumerate(grid)
        if isinstance(c, dict) and c.get("id")
    }
    span_map = {
        str(c.get("id")): c
        for c in grid
        if isinstance(c, dict) and c.get("id")
    }

    def sort_key(spec: dict[str, Any]) -> tuple[int, int]:
        wid = str(spec.get("id") or "")
        if wid in order_map:
            return (0, order_map[wid])
        return (1, 999)

    ordered = sorted([s for s in specs if isinstance(s, dict)], key=sort_key)
    for spec in ordered:
        wid = str(spec.get("id") or "")
        cell = span_map.get(wid)
        if cell:
            spec["layout"] = {
                "x": cell.get("x"),
                "y": cell.get("y"),
                "w": cell.get("w"),
                "h": cell.get("h"),
                "order": cell.get("order"),
            }
    return ordered


def layout_status() -> dict[str, Any]:
    return {
        "ok": True,
        "phase": "U3",
        "enabled": layout_enabled(),
        "flag": "NR2_DASHBOARD_LAYOUT",
        "pages": sorted(DEFAULT_LAYOUTS.keys()),
        "theme": "starship-bridge",
        "endpoints": {
            "get": "GET /api/apex/hal/dashboard-layout?page=financial",
            "save": "POST /api/apex/hal/dashboard-layout",
            "reset": "POST /api/apex/hal/dashboard-layout-reset",
        },
        "note": "Frontend localStorage mirrors server layout; preserves existing mosaic CSS.",
        "refreshedAt": _utc_now(),
    }


def layout_widget(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    del bundle
    st = layout_status()
    fin = get_layout("financial")
    grid_n = len(((fin.get("layout") or {}).get("grid") or []))
    return {
        "id": "dashboard-layout-status",
        "type": "status",
        "label": "Dashboard Layout (U3)",
        "size": "full",
        "status": "ok" if st.get("enabled") else "empty",
        "message": (
            f"Layout {'ON' if st.get('enabled') else 'OFF'} · "
            f"financial grid={grid_n} · theme=starship-bridge"
        ),
        "hint": "Order/span presets for mosaic — drag prefs via localStorage key nr2:apex:layout:*.",
        "phase": "U3",
    }
