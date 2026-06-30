"""Emit JSON snapshot for Verify-HAL-Readiness.ps1 (document queue counts)."""

from __future__ import annotations

import json
import sys

from document_sync import DOCUMENTS_KEY, NR2_DATA_DIR
from local_store import LocalStore


def main() -> int:
    raw = LocalStore(NR2_DATA_DIR).get(DOCUMENTS_KEY)
    state = json.loads(raw or "{}")
    queue = state.get("queue") or []
    counts = {"quickbooks": 0, "softdent": 0, "ocr": 0, "manual": 0}
    for doc in queue:
        if not isinstance(doc, dict):
            continue
        sys_name = str(doc.get("sourceSystem") or "").lower()
        if sys_name in counts:
            counts[sys_name] += 1
        elif doc.get("autoImported"):
            counts["ocr"] += 1
        else:
            counts["manual"] += 1
    pending = sum(
        1
        for doc in queue
        if isinstance(doc, dict) and "pending" in str(doc.get("status") or "").lower()
    )
    print(
        json.dumps(
            {
                "queueCount": len(queue),
                "counts": counts,
                "pendingReview": pending,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
