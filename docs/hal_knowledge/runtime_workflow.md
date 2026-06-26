# HAL Knowledge Memory — Runtime Workflow (Design Only)

This document describes a **future** SQLite-backed proposal/approval workflow.
It is **not implemented** in production routes or storage yet. Approve
separately before adding tables, API handlers, or UI.

## Goals

- Append-only audit trail for memory proposals, approvals, deprecations, revocations.
- Human review before a memory becomes permanent.
- No guardrail bypass: memories remain context-only.
- Local/private storage in existing `hal_local.sqlite3` path family.

## Proposed tables

### `hal_memories`

| Column | Type | Notes |
| --- | --- | --- |
| `memory_id` | TEXT PK | Stable id (matches JSONL `id`). |
| `category` | TEXT | From categories enum. |
| `text` | TEXT | Sanitized memory body. |
| `source` | TEXT | Provenance reference. |
| `created_at_utc` | TEXT | ISO-8601. |
| `last_verified_at_utc` | TEXT | ISO-8601. |
| `confidence` | TEXT | high / medium / low. |
| `scope` | TEXT | |
| `staleness_rule` | TEXT | |
| `expires_at_utc` | TEXT NULL | |
| `sensitivity_level` | TEXT | |
| `status` | TEXT | proposed / approved / deprecated / revoked. |
| `must_not_override_json` | TEXT | JSON array. |
| `proposed_by` | TEXT | Actor. |
| `approved_by` | TEXT NULL | Reviewer. |
| `approved_at_utc` | TEXT NULL | |

### `hal_memory_events`

| Column | Type | Notes |
| --- | --- | --- |
| `event_id` | TEXT PK | UUID. |
| `memory_id` | TEXT | FK to `hal_memories`. |
| `created_at_utc` | TEXT | |
| `actor` | TEXT | |
| `event_type` | TEXT | proposed / approved / deprecated / revoked / verified / edited. |
| `previous_status` | TEXT NULL | |
| `new_status` | TEXT NULL | |
| `note` | TEXT | Review comment. |
| `snapshot_json` | TEXT | Immutable snapshot at event time. |

## Proposed API surface (future)

All endpoints require `hal:operator` or `admin` and must **not** weaken
`HalAskRequest` or guardrails.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/hal9000/knowledge/memories` | List memories (filter by status). |
| `POST` | `/api/hal9000/knowledge/memories` | Propose new memory (`status: proposed`). |
| `POST` | `/api/hal9000/knowledge/memories/{id}/approve` | Promote to approved. |
| `POST` | `/api/hal9000/knowledge/memories/{id}/revoke` | Revoke with audit event. |
| `POST` | `/api/hal9000/knowledge/export-jsonl` | Export approved set to `memories.jsonl`. |

## Sync with JSONL registry

Until SQLite workflow ships:

- `docs/hal_knowledge/memories.jsonl` remains the canonical seed registry.
- Approved lines are indexed via `app/hal/knowledge_memory.py`.
- Contract tests enforce schema and safety invariants on every line.

After SQLite workflow ships:

- Export approved rows to JSONL for version control snapshots.
- Index builder continues to read JSONL or a merged approved view.
- Revocation must append `hal_memory_events`; never silent delete.

## Safety checks at proposal time

Reject or flag proposals that contain:

- patient names, MRNs, SSNs, account numbers,
- raw CSV row patterns (`PatientName,MRN,ClaimId`),
- API keys, passwords, tokens,
- language that authorizes submit/send/fax/upload/Gateway,
- `missing_softdent_ar` reported as `$0`,
- A/R inferred from claim or ledger totals.

## Files to modify when approved

- `app/hal/storage.py` — table creation and CRUD.
- `app/routes.py` — review endpoints with role checks.
- `frontend/` — optional operator review UI (separate approval).

Do **not** implement these until this design is explicitly approved.
