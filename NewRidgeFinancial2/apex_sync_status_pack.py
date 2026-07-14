"""
Phase V0 — Data freshness / sync status (Moonshot REAUDIT4 SHOULD).

Surfaces last successful SoftDent / QB / ERA import timestamps.
Empty ≠ $0; no SoftDent write-back.
Flag: NR2_DATA_FRESHNESS (default OFF until burn-in — Moonshot V0).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def freshness_enabled() -> bool:
    # Moonshot Expert SE Phase 2 (REC-004): default ON so SoftDent/QB age chips surface.
    # Set NR2_DATA_FRESHNESS=0 to hide the bar when all imports are fresh.
    raw = str(os.getenv("NR2_DATA_FRESHNESS") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(float(raw), tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _age_hours(ts: datetime | None, *, now: datetime | None = None) -> float | None:
    if ts is None:
        return None
    now = now or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max(0.0, (now - ts).total_seconds() / 3600.0)


def _level(hours: float | None) -> str:
    """Import age bands — Moonshot Phase 2: critical when SoftDent/QB age > 7 days."""
    if hours is None:
        return "unknown"
    if hours < 24:
        return "fresh"
    if hours < 168:  # 7 days
        return "stale"
    return "critical"


def build_sync_status(*, bundle: dict[str, Any] | None = None, db_path: Path | None = None) -> dict[str, Any]:
    """Last-import timestamps for SoftDent / QB / ERA — no dollar amounts."""
    b = bundle if isinstance(bundle, dict) else {}
    loaded = _parse_ts(b.get("loadedAt") or b.get("syncedAt"))

    softdent_at = None
    qb_at = None
    try:
        sd = b.get("softdent") if isinstance(b.get("softdent"), dict) else {}
        qb = b.get("quickbooks") if isinstance(b.get("quickbooks"), dict) else {}
        softdent_at = _parse_ts(sd.get("loadedAt") or sd.get("importedAt") or loaded)
        qb_at = _parse_ts(qb.get("loadedAt") or qb.get("importedAt") or loaded)
    except Exception:
        pass

    era_at = None
    try:
        from apex_softdent_era_pack import list_era_aggregates

        rows = list_era_aggregates(limit=1, db_path=db_path)
        if rows:
            era_at = _parse_ts(rows[0].get("importedAt"))
    except Exception:
        pass
    try:
        from apex_era835_pack import list_era835_payments

        rows = list_era835_payments(limit=1, db_path=db_path)
        if rows:
            ts = _parse_ts(rows[0].get("ingestedAt"))
            if ts and (era_at is None or ts > era_at):
                era_at = ts
    except Exception:
        pass

    # Unified DB ingest health as fallback signal
    unified_at = None
    try:
        from apex_unified_db_pack import open_unified, unified_db_path

        path = db_path or unified_db_path()
        if path.is_file():
            with open_unified(path=path) as conn:
                row = conn.execute(
                    "SELECT MAX(detected_at) AS t FROM import_health_log"
                ).fetchone()
                if row and row["t"]:
                    unified_at = _parse_ts(row["t"])
    except Exception:
        pass

    now = datetime.now(timezone.utc)

    def chip(name: str, ts: datetime | None) -> dict[str, Any]:
        hours = _age_hours(ts, now=now)
        return {
            "source": name,
            "lastImport": ts.isoformat().replace("+00:00", "Z") if ts else None,
            "ageHours": round(hours, 2) if hours is not None else None,
            "level": _level(hours),
        }

    chips = [
        chip("softdent", softdent_at or loaded),
        chip("quickbooks", qb_at or loaded),
        chip("era", era_at),
        chip("unified", unified_at),
    ]
    worst = "unknown"
    order = {"critical": 3, "stale": 2, "fresh": 1, "unknown": 0}
    for c in chips:
        if order.get(c["level"], 0) > order.get(worst, 0):
            worst = c["level"]

    # Moonshot REC-004: force-enable bar when SoftDent/QB is stale or >7d critical.
    force_show = worst in ("stale", "critical")
    softdent_chip = chips[0] if chips else {}
    softdent_hours = softdent_chip.get("ageHours")
    if isinstance(softdent_hours, (int, float)) and softdent_hours >= 168:
        force_show = True
        softdent_chip["alert"] = "SoftDent export older than 7 days — refresh imports."

    return {
        "ok": True,
        "phase": "V0",
        "enabled": bool(freshness_enabled() or force_show),
        "forceShow": force_show,
        "flag": "NR2_DATA_FRESHNESS",
        "softdent_last_import": chips[0]["lastImport"],
        "qb_last_import": chips[1]["lastImport"],
        "era_last_import": chips[2]["lastImport"],
        "unified_last_signal": chips[3]["lastImport"],
        "chips": chips,
        "worstLevel": worst,
        "bundleLoadedAt": loaded.isoformat().replace("+00:00", "Z") if loaded else None,
        "refreshedAt": _utc_now(),
        "note": "Timestamps only — empty imports stay empty (≠ $0). Critical = age ≥7 days.",
        "hint": "green <24h · yellow 24h–7d · red ≥7d",
    }


def freshness_widget(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    if not freshness_enabled():
        return {
            "id": "data-freshness-status",
            "type": "status",
            "label": "Data Freshness (V0)",
            "size": "full",
            "status": "empty",
            "message": "Freshness OFF",
            "emptyMessage": "Set NR2_DATA_FRESHNESS=1 (default) to show import age chips.",
            "hint": "Default ON per Moonshot Expert SE Phase 2; set 0 to hide when fresh.",
        }
    st = build_sync_status(bundle=bundle)
    chips = st.get("chips") or []
    msg = " · ".join(
        f"{c.get('source')}={c.get('level')}"
        for c in chips
        if isinstance(c, dict)
    )
    level = str(st.get("worstLevel") or "unknown")
    return {
        "id": "data-freshness-status",
        "type": "status",
        "label": "Data Freshness (V0)",
        "size": "full",
        "status": "ok" if level == "fresh" else ("warn" if level != "unknown" else "empty"),
        "message": msg or "No import timestamps",
        "hint": "green <24h · yellow 24h–7d · red ≥7d",
        "chips": chips,
        "worstLevel": level,
    }
