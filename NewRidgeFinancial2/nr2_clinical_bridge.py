"""Read-only clinical context bridge (8766 SideNotes → 8765 HAL)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
SITE_DATA = Path(__file__).resolve().parent / "site" / "data"
_PHI_SCRUB = re.compile(r"\b(\d{3}-\d{2}-\d{4}|\d{10,}|@\w+\.\w+)\b")


def _scrub(text: str) -> str:
    return _PHI_SCRUB.sub("[REDACTED]", str(text or ""))[:800]


def _load_inbox_files() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for name in ("sidenotes-inbox.json", "sidenotes-inbox-server.json"):
        path = SITE_DATA / name
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        messages = data.get("messages") if isinstance(data, dict) else data
        if isinstance(messages, list):
            items.extend(m for m in messages if isinstance(m, dict))
    return items


def load_clinical_context(
    store=None,
    *,
    patient_id: str = "",
    patient_name: str = "",
    limit: int = 10,
) -> dict[str, Any]:
    cap = max(1, min(int(limit or 10), 50))
    items: list[dict[str, Any]] = []
    pid = str(patient_id or "").strip().lower()
    pname = str(patient_name or "").strip().lower()

    if store:
        try:
            raw = store.get("nr2:clinical:summaries")
            if raw:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    items.extend(parsed)
        except json.JSONDecodeError:
            pass

    for msg in _load_inbox_files():
        body = _scrub(str(msg.get("body") or msg.get("text") or msg.get("message") or ""))
        station = str(msg.get("station") or msg.get("from") or "")
        subject = _scrub(str(msg.get("subject") or msg.get("title") or ""))
        msg_patient = str(msg.get("patientId") or msg.get("patient_id") or "").lower()
        msg_name = str(msg.get("patientName") or msg.get("patient") or "").lower()
        if pid and msg_patient and msg_patient != pid:
            continue
        if pname and msg_name and pname not in msg_name and msg_name not in pname:
            if pname not in body.lower() and pname not in subject.lower():
                continue
        items.append(
            {
                "source": "sidenotes-inbox",
                "station": station,
                "summary": subject or body[:200],
                "text": body,
                "patientId": msg.get("patientId") or msg.get("patient_id") or "",
                "readOnly": True,
            }
        )

    try:
        from sidenotes_bridge import sidenotes_read_messages

        live = sidenotes_read_messages(limit=cap, include_body=True)
        for msg in (live.get("messages") or []) if isinstance(live, dict) else []:
            if not isinstance(msg, dict):
                continue
            body = _scrub(str(msg.get("body") or msg.get("text") or ""))
            items.append(
                {
                    "source": "sidenotes-live",
                    "station": str(msg.get("station") or ""),
                    "summary": body[:200],
                    "text": body,
                    "readOnly": True,
                }
            )
    except Exception:
        pass

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for it in items:
        key = str(it.get("summary") or "")[:80]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)
    return {"ok": True, "items": deduped[:cap], "count": len(deduped[:cap]), "readOnly": True}
