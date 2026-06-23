# HAL PHI-Safe Local AI Architecture

This document describes the safest practical way to add AI-assisted question answering to New Ridge Family Financial without giving a model broad or uncontrolled access to protected data.

## Current environment

Based on the current repository:

- Data originates from read-only SoftDent exports and related financial imports.
- The backend is a local FastAPI service.
- The backend uses SQLite as a local cache and analytics store.
- The browser frontend uses IndexedDB for local client caching.
- Existing HAL endpoints are placeholders and should not be treated as a production AI boundary.
- The documented operating model is read-only and localhost-first.

This means the right starting point is not direct live EHR connectivity. The right starting point is a local retrieval layer over approved exported data, with strict de-identification and audit logging before any model call.

## Recommended architecture

Use a local Retrieval-Augmented Generation (RAG) flow with a narrow backend tool boundary:

1. Ingest approved export files from the existing SoftDent/financial import pipeline.
2. Normalize those files into internal records already used for reporting.
3. Create sanitized text chunks for AI retrieval.
4. Remove or mask direct identifiers before embedding or prompting.
5. Store only sanitized chunks in a local vector index.
6. Answer HAL questions by retrieving a small relevant context set.
7. Pass only sanitized snippets plus calculated KPI summaries to the local model.
8. Log the question, retrieved chunk ids, model id, and response metadata for audit.

The model should never receive unrestricted database access, full raw exports, or write credentials.

## Boundary rules

### Allowed inputs to HAL

- Calculated KPI summaries already produced by the app
- Sanitized excerpts derived from approved import files
- Explicitly approved operational guidance documents
- Narrow, parameterized read-only lookup results

### Disallowed inputs to HAL

- Raw patient ledgers passed straight to the model
- Full exported CSV files as prompt context
- Direct names, birth dates, account numbers, phone numbers, addresses, or chart identifiers unless a separate legal review approves that path
- Free-form SQL generation by the model
- Any write path back to SoftDent, QuickBooks, or a production database

## Deployment model

For this repository, the safest fit is:

- Local-only model hosting on the same trusted network boundary
- No outbound internet requirement for inference
- Read-only application credentials
- Backend-mediated model access only; never browser-to-model direct

Practical local model hosts:

- Ollama for simpler single-node local deployment
- vLLM if higher-throughput hosted inference is needed later

Keep model serving on a private interface and disable unnecessary network exposure.

## Retrieval design

### Source material

Start with these approved sources only:

- SoftDent-derived read-only imports already accepted by the current pipeline
- QuickBooks-derived financial summaries already accepted by the current pipeline
- Internal policy and workflow documents in `docs/`
- KPI and trend summaries already exposed by the reporting layer

### Chunking strategy

Build retrieval chunks around business meaning rather than raw file rows:

- monthly KPI summaries
- AR aging summaries
- claims trend summaries
- provider production summaries
- reconciliation summaries
- internal policy text

Do not embed entire raw CSV rows when they contain identifiers or line-level patient detail.

### Recommended local libraries

Python-first options that fit the repo:

- `sentence-transformers` for local embedding generation
- `faiss-cpu` or `chromadb` for a local vector store
- `presidio-analyzer` and `presidio-anonymizer` for PHI detection/masking
- `llama-index` or a small custom retrieval service if orchestration is needed

If minimizing moving parts matters more than framework abstraction, a custom FastAPI retrieval service is preferable to a large agent framework.

## De-identification layer

Before text is stored for retrieval or sent to a model:

1. Detect direct identifiers.
2. Replace them with stable placeholders.
3. Preserve business meaning needed for analytics.
4. Store only the sanitized text for embedding and prompt context.

Example transformations:

- patient name -> `PATIENT_001`
- date of birth -> `DOB_REDACTED`
- phone number -> `PHONE_REDACTED`
- account number -> `ACCOUNT_REDACTED`
- exact appointment date -> month-level or relative date when sufficient

Keep the mapping table, if one exists at all, outside the AI retrieval store and protect it separately. In many cases, the best option is to avoid reversible mappings entirely.

## Live data access rules

If HAL later needs live lookups, do not give it general database access.

Use backend-owned tool functions such as:

- `get_monthly_kpi(period)`
- `get_claims_summary(start_date, end_date)`
- `get_ar_aging_snapshot(period)`
- `get_provider_totals(period)`

Rules for those tools:

- read-only only
- parameterized queries only
- no arbitrary SQL from the model
- enforce row/field-level minimization in the backend
- log every invocation

## Best integration points in this repo

### Backend

- Add HAL orchestration under `app/services/` rather than `app/routes.py`.
- Keep `app/routes.py` as the HTTP boundary only.
- Reuse the existing SQLite-backed analytics layer as the source of approved KPI context.
- Add a separate service module for:
  - sanitized document preparation
  - vector index refresh
  - HAL query orchestration
  - audit logging

Suggested future modules:

- `app/services/hal_retrieval.py`
- `app/services/hal_sanitization.py`
- `app/services/hal_orchestrator.py`
- `app/services/hal_audit.py`

### Frontend

- Keep the browser page as a thin question/answer client.
- Do not store raw PHI prompts or model context in browser storage.
- Avoid persisting model transcripts in IndexedDB unless there is a reviewed retention policy.
- Send questions to the FastAPI backend and let the backend enforce sanitization and authorization.

## Security controls

Minimum controls for a production-grade HAL rollout:

- Stronger auth than the current placeholder Basic Auth credentials
- Audit trail for prompts, retrieval ids, tool calls, and response metadata
- Encryption at rest for SQLite and vector-store hosts when feasible in the deployment environment
- TLS for any network hop, even internal ones
- Strict read-only filesystem and data permissions for import roots
- Model host blocked from outbound internet unless explicitly required and reviewed
- Red-team checks for prompt injection via imported documents

## Implementation phases

### Phase 1: Safe local Q&A over sanitized summaries

- No live patient lookup
- No reversible identifiers in context
- Retrieval over KPI summaries, reports, and policy docs only
- Local model hosting only

### Phase 2: Narrow operational lookups

- Add backend-owned read-only tools for approved summary queries
- Keep outputs aggregated whenever possible
- Expand audit logging and role checks

### Phase 3: Case-level workflows only if explicitly approved

- Requires separate privacy, security, and operational review
- Requires stronger identity, authorization, retention, and monitoring controls
- Should remain opt-in and tightly scoped

## Concrete recommendation for this repo

For New Ridge Family Financial today, the best fit is:

- FastAPI backend remains the only AI entry point.
- HAL uses local embeddings over sanitized financial summaries and internal docs.
- HAL answers from KPI/report context first, not raw patient exports.
- Any later live lookup is implemented as a small set of read-only backend tools.
- The frontend remains a thin client and does not hold sensitive AI context at rest.

That approach matches the repository's current read-only SoftDent posture and avoids introducing an uncontrolled PHI exposure path.
