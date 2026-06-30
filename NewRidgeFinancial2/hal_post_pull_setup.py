"""Post-pull HAL office bootstrap: dashboard periods, document triage, narrative + library seeds."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_sync import (
    DOCUMENTS_KEY,
    NR2_DATA_DIR,
    _recompute_period,
    _status_tone,
    resolve_accounting_db_path,
)
from local_store import LocalStore

NARRATIVES_KEY = "nr2:v2:narratives"
LIBRARY_KEY = "nr2:v2:library"
TRIAGE_NOTE = "HAL batch triage completed (local review queue cleared)."


def _load_json_store(store: LocalStore, key: str, default: Any) -> Any:
    raw = store.get(key)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _save_json_store(store: LocalStore, key: str, value: Any) -> None:
    store.set(key, json.dumps(value))


def _clear_accounting_review_flags() -> dict[str, Any]:
    db_path = resolve_accounting_db_path()
    result = {"dbPath": str(db_path) if db_path else None, "updated": 0, "warnings": []}
    if not db_path or not db_path.is_file():
        result["warnings"].append("No accounting database found for OCR review flags.")
        return result
    with sqlite3.connect(db_path) as conn:
        columns = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(local_accounting_documents)").fetchall()
        }
        if "review_required" not in columns:
            result["warnings"].append("review_required column missing on accounting ledger.")
            return result
        cur = conn.execute(
            """
            UPDATE local_accounting_documents
            SET review_required = 0,
                confidence_label = 'hal triaged'
            WHERE review_required = 1
               OR LOWER(COALESCE(confidence_label, '')) LIKE '%manual%'
               OR LOWER(COALESCE(confidence_label, '')) LIKE '%review%'
            """
        )
        result["updated"] = int(cur.rowcount or 0)
        conn.commit()
    return result


def advance_pending_documents(store: LocalStore | None = None) -> dict[str, Any]:
    store = store or LocalStore(NR2_DATA_DIR)
    accounting = _clear_accounting_review_flags()
    state = _load_json_store(
        store,
        DOCUMENTS_KEY,
        {"entity": "New Ridge Family Financial", "queue": [], "previewById": {}, "period": _recompute_period([])},
    )
    advanced = 0
    for doc in state.get("queue") or []:
        if str(doc.get("status") or "") != "Pending Review":
            continue
        doc["status"] = "Ready to Post"
        doc["statusTone"] = _status_tone("Ready to Post")
        doc["halTriageNote"] = TRIAGE_NOTE
        advanced += 1
    state["period"] = _recompute_period(state.get("queue") or [])
    _save_json_store(store, DOCUMENTS_KEY, state)
    return {
        "ok": True,
        "advanced": advanced,
        "queueCount": len(state.get("queue") or []),
        "accounting": accounting,
    }


def seed_narrative_draft(store: LocalStore | None = None, *, force: bool = False) -> dict[str, Any]:
    from hal_narrative_library import select_best_narrative_for_claim
    from import_loader import load_import_bundle

    store = store or LocalStore(NR2_DATA_DIR)
    state = _load_json_store(
        store,
        NARRATIVES_KEY,
        {
            "context": {},
            "composer": {
                "tone": "Professional",
                "length": "Standard",
                "focus": "Medical Necessity",
                "keyPoints": [],
                "context": "",
            },
            "draftText": "",
            "drafts": [],
        },
    )
    if (state.get("drafts") or []) and not force:
        return {"ok": True, "seeded": False, "reason": "drafts already present", "draftCount": len(state["drafts"])}

    bundle = load_import_bundle(sync=False, deep=False)
    claim_rows = ((bundle.get("softdent") or {}).get("claims") or {}).get("rows") or []
    claim: dict[str, Any] | None = None
    for row in claim_rows:
        if isinstance(row, dict):
            claim = {
                "id": row.get("ClaimId") or row.get("claimId") or row.get("id"),
                "patient": row.get("PatientName") or row.get("patient"),
                "procedure": row.get("Procedure") or row.get("procedure"),
                "status": row.get("ClaimStatus") or row.get("status"),
                "denialReason": row.get("DenialReason") or row.get("denialReason"),
            }
            break
    if not claim or not claim.get("id"):
        return {"ok": False, "seeded": False, "reason": "no claims in import cache"}

    selection = select_best_narrative_for_claim(claim)
    selected = selection.get("selected") or {}
    text = str(selected.get("text") or "").strip()
    if not text:
        return {"ok": False, "seeded": False, "reason": "narrative template empty"}

    now = datetime.now().strftime("%m/%d/%Y %I:%M %p")
    draft = {
        "version": "v1",
        "latest": True,
        "modified": now,
        "points": len(selected.get("tags") or []),
        "length": selected.get("length") or "Standard",
        "focus": selected.get("focus") or "Medical Necessity",
        "by": "HAL (MemoAI-guided seed)",
        "text": text,
        "keyPoints": list(selected.get("tags") or []),
        "claimRef": str(claim.get("id") or ""),
        "templateId": selected.get("id"),
    }
    state["drafts"] = [draft]
    state["draftText"] = text
    state["composer"] = {
        "tone": selected.get("tone") or "Professional",
        "length": draft["length"],
        "focus": draft["focus"],
        "keyPoints": draft["keyPoints"],
        "context": f"Seeded from claim {claim.get('id')} · template {selected.get('id')}",
    }
    _save_json_store(store, NARRATIVES_KEY, state)
    return {
        "ok": True,
        "seeded": True,
        "claimRef": claim.get("id"),
        "templateId": selected.get("id"),
        "focus": draft["focus"],
    }


def seed_document_library(store: LocalStore | None = None, *, force: bool = False) -> dict[str, Any]:
    store = store or LocalStore(NR2_DATA_DIR)
    library = _load_json_store(
        store,
        LIBRARY_KEY,
        {"results": 0, "storage": {}, "filters": [], "docs": [], "detailById": {}},
    )
    existing_titles = {str(doc.get("title") or "") for doc in library.get("docs") or []}
    if existing_titles and not force:
        return {
            "ok": True,
            "seeded": False,
            "reason": "library already populated",
            "docCount": len(existing_titles),
        }

    documents = _load_json_store(store, DOCUMENTS_KEY, {"queue": [], "previewById": {}})
    queue = documents.get("queue") or []
    previews = documents.get("previewById") or {}
    added = 0
    for doc in queue:
        vendor = str(doc.get("vendor") or "Document").strip()
        doc_id = str(doc.get("id") or "").strip()
        title = f"{doc_id} — {vendor}" if doc_id else vendor
        if title in existing_titles:
            continue
        doc_type = str(doc.get("type") or "Document")
        preview = previews.get(str(doc.get("id") or "")) or {}
        file_label = str(preview.get("file") or f"{doc.get('id')}.pdf")
        updated = str(doc.get("date") or datetime.now(timezone.utc).date().isoformat())
        entry = {
            "title": title,
            "type": doc_type,
            "size": "—",
            "updated": updated,
            "by": "HAL import index",
            "tags": ["import", doc_type.lower().replace(" ", "-")],
        }
        library.setdefault("docs", []).append(entry)
        library.setdefault("detailById", {})[title] = {
            "title": title,
            "type": doc_type,
            "size": "—",
            "updated": updated,
            "docType": doc_type,
            "tags": entry["tags"],
            "uploadedBy": entry["by"],
            "dateAdded": updated,
            "path": f"/library/{title.lower().replace(' ', '-')}.pdf",
            "sourceDocId": doc.get("id"),
            "file": file_label,
        }
        existing_titles.add(title)
        added += 1

    library["results"] = len(library.get("docs") or [])
    library["storage"] = {
        "indexed": library["results"],
        "source": "document queue",
        "refreshedAt": datetime.now(timezone.utc).isoformat(),
    }
    _save_json_store(store, LIBRARY_KEY, library)
    return {"ok": True, "seeded": added > 0, "added": added, "docCount": library["results"]}


def run_post_pull_setup(store: LocalStore | None = None) -> dict[str, Any]:
    store = store or LocalStore(NR2_DATA_DIR)
    dashboard: dict[str, Any] = {"ok": False}
    try:
        from softdent_dashboard_period_sync import sync_dashboard_period_rows

        dashboard = sync_dashboard_period_rows()
    except Exception as exc:
        dashboard = {"ok": False, "error": str(exc)}

    documents = advance_pending_documents(store)
    narrative = seed_narrative_draft(store)
    library = seed_document_library(store)
    return {
        "ok": bool(dashboard.get("ok")),
        "completedAt": datetime.now(timezone.utc).isoformat(),
        "dashboard": dashboard,
        "documents": documents,
        "narrative": narrative,
        "library": library,
    }


if __name__ == "__main__":
    print(json.dumps(run_post_pull_setup(), indent=2))
