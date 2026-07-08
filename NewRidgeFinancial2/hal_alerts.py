"""Proactive HAL alerts — Phase 2 Moonshot Priority E."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

ALERT_TYPES = ("soft_stale", "high_value_batch", "import_failure")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_alert_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS hal_alerts (
            id TEXT PRIMARY KEY,
            created_at_utc TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'medium',
            title TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            acknowledged_at TEXT,
            meta_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.commit()


def _has_active_alert(conn: sqlite3.Connection, *, alert_type: str, title: str) -> bool:
    ensure_alert_schema(conn)
    row = conn.execute(
        """
        SELECT 1 FROM hal_alerts
        WHERE acknowledged_at IS NULL AND alert_type = ? AND title = ?
        LIMIT 1
        """,
        (str(alert_type or ""), str(title or "")[:200]),
    ).fetchone()
    return row is not None


def create_alert(
    conn: sqlite3.Connection,
    *,
    alert_type: str,
    title: str,
    body: str = "",
    severity: str = "medium",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_alert_schema(conn)
    alert_id = f"alert-{uuid.uuid4().hex[:12]}"
    conn.execute(
        """
        INSERT INTO hal_alerts (id, created_at_utc, alert_type, severity, title, body, meta_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            alert_id,
            _utc_now(),
            str(alert_type or "general"),
            str(severity or "medium"),
            str(title or "")[:200],
            str(body or "")[:2000],
            json.dumps(meta if isinstance(meta, dict) else {}),
        ),
    )
    conn.commit()
    return {"ok": True, "alertId": alert_id, "alertType": alert_type, "title": title}


def list_active_alerts(conn: sqlite3.Connection, *, limit: int = 50) -> dict[str, Any]:
    ensure_alert_schema(conn)
    cur = conn.execute(
        """
        SELECT id, created_at_utc, alert_type, severity, title, body, meta_json
        FROM hal_alerts
        WHERE acknowledged_at IS NULL
        ORDER BY created_at_utc DESC
        LIMIT ?
        """,
        (max(1, min(int(limit or 50), 200)),),
    )
    items = []
    for row in cur.fetchall():
        try:
            meta = json.loads(row[6] or "{}")
        except json.JSONDecodeError:
            meta = {}
        items.append(
            {
                "id": row[0],
                "createdAt": row[1],
                "alertType": row[2],
                "severity": row[3],
                "title": row[4],
                "body": row[5],
                "meta": meta,
            }
        )
    return {"ok": True, "items": items, "count": len(items)}


def acknowledge_alert(conn: sqlite3.Connection, alert_id: str) -> dict[str, Any]:
    ensure_alert_schema(conn)
    conn.execute(
        "UPDATE hal_alerts SET acknowledged_at = ? WHERE id = ?",
        (_utc_now(), str(alert_id or "")),
    )
    conn.commit()
    return {"ok": True, "alertId": alert_id, "acknowledged": True}


class AlertMonitor:
    """Evaluate alert conditions and persist new alerts."""

    def __init__(self, store) -> None:
        self.store = store

    def _conn(self) -> sqlite3.Connection | None:
        if not self.store or not hasattr(self.store, "_connect"):
            return None
        return self.store._connect()

    def evaluate(self, *, readiness: dict[str, Any] | None = None, pending_batch_usd: float = 0) -> list[dict[str, Any]]:
        conn = self._conn()
        if not conn:
            return []
        created: list[dict[str, Any]] = []
        readiness = readiness if isinstance(readiness, dict) else {}
        level = str(readiness.get("level") or "unknown")
        age = readiness.get("ageHours")
        try:
            age_f = float(age) if age is not None else None
        except (TypeError, ValueError):
            age_f = None
        if level != "fresh" and age_f is not None and age_f >= 1:
            if not _has_active_alert(conn, alert_type="soft_stale", title="Import data stale"):
                created.append(
                    create_alert(
                        conn,
                        alert_type="soft_stale",
                        severity="high",
                        title="Import data stale",
                        body="Refresh imports before posting or batch actions.",
                        meta={"level": level, "ageHours": age_f},
                    )
                )
        if pending_batch_usd >= 5000:
            if not _has_active_alert(conn, alert_type="high_value_batch", title="High-value batch awaiting consent"):
                created.append(
                    create_alert(
                        conn,
                        alert_type="high_value_batch",
                        severity="medium",
                        title="High-value batch awaiting consent",
                        body=f"${pending_batch_usd:,.2f} pending approval.",
                        meta={"pendingUsd": pending_batch_usd},
                    )
                )
        if level in ("degraded", "expired"):
            title = "Import pipeline requires attention"
            if not _has_active_alert(conn, alert_type="import_failure", title=title):
                created.append(
                    create_alert(
                        conn,
                        alert_type="import_failure",
                        severity="high",
                        title=title,
                        body=f"Import readiness: {level}.",
                        meta={"level": level},
                    )
                )
        return created
