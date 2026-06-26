# HAL Knowledge / Memory Registry

Governed, local-only durable operational knowledge for HAL. This is **not** a
guardrail bypass system, **not** a raw-data dump, and **not** a production
allowlist.

Memories help HAL recall stable project facts, workflows, prior decisions,
known fixes, data-source boundaries, and safety rules. They provide **context
only**. They never override:

- auth or `hal:operator` checks,
- `HalAskRequest` validation,
- HAL guardrails,
- live runtime status,
- or current source availability.

## Separation from the intent library

| Asset | Purpose | Location | Production reads? |
| --- | --- | --- | --- |
| Intent/evaluation library | Test HAL behavior | `evals/hal_intent_library/` | **No** |
| Knowledge/memory registry | Durable operational knowledge | `docs/hal_knowledge/` | Approved memories only, via sanitized index |

## Files

| File | Purpose |
| --- | --- |
| `schema.json` | JSON Schema for one memory object (draft-07). |
| `categories.json` | Category definitions, default staleness, retrieval priority. |
| `memories.jsonl` | Canonical registry (one JSON object per line). |
| `runtime_workflow.md` | Future SQLite proposal/approval workflow (design only). |
| `app/hal/knowledge_memory.py` | Load, filter, sanitize, and chunk approved memories. |
| `app/tests/test_hal_knowledge_memory_contract.py` | Contract/schema validation (no live API, no Ollama). |
| `app/tests/test_hal_knowledge_memory_retrieval.py` | Retrieval filter unit tests. |

## Memory lifecycle

1. **Proposed** — draft from incident, test, or maintainer note (`status: proposed`).
2. **Review** — human checks accuracy, safety, source, scope, sensitivity, staleness.
3. **Approved** — eligible for sanitized index inclusion (`status: approved`).
4. **Deprecated / revoked** — excluded from retrieval; revocation is append-only in future SQLite workflow.

Blocked without separate protected-storage approval:

- raw patient data,
- raw SoftDent/QuickBooks CSV rows,
- secrets or credentials,
- full logs containing PHI,
- speculative guesses presented as facts.

## Memory fields

Each line in `memories.jsonl` includes:

- `id`, `category`, `text`, `source`
- `created_at`, `last_verified_at`
- `confidence` (`high` | `medium` | `low`)
- `scope`, `staleness_rule`, optional `expires_at`
- `sensitivity_level`, `status`
- `must_not_override` (e.g. `runtime_status`, `auth`, `guardrails`, `source_availability`, `hal_ask_request`)

Only `approved` memories with `confidence` in (`high`, `medium`) and
`sensitivity_level` not in (`restricted`, `prohibited`) are indexed. Stale
memories are excluded unless the query is explicitly historical.

## Retrieval precedence

At answer time (when wired through the sanitized HAL index):

1. Auth, `HalAskRequest`, role checks, safety policy.
2. Live runtime checks and source availability.
3. Deterministic verified facts from approved data tools.
4. Approved knowledge memories (labelled durable guidance).
5. Historical incidents and future tasks (lowest priority; never authorize actions).

## Phases

- **Phase 1 (foundation):** `docs/hal_knowledge/*`, contract test, sample memories.
- **Phase 2 (retrieval):** `knowledge_memory.py`, index builder integration, retrieval tests. No `/api/hal9000` behavior change beyond richer sanitized index content.
- **Phase 3 (runtime workflow, separate approval):** SQLite `hal_memories` / `hal_memory_events`, operator review API/UI. See `runtime_workflow.md`.

## Running tests

```powershell
.\.venv\Scripts\python.exe -m pytest app\tests\test_hal_knowledge_memory_contract.py
.\.venv\Scripts\python.exe -m pytest app\tests\test_hal_knowledge_memory_retrieval.py
```

Optional broader check:

```powershell
.\.venv\Scripts\python.exe -m pytest app\tests\test_hal_intent_library_contract.py app\tests\test_hal_knowledge_memory_contract.py app\tests\test_hal_knowledge_memory_retrieval.py
```

## Mem0 / OpenMemory

Not used in phase 1 or 2. Reconsider only after the local JSONL registry proves
useful and a vendor solution can meet local-only, auditable, approval-gated,
and non-bypass requirements.
