
# API Documentation for New Ridge Family Financial

## Authentication

Most endpoints require an authenticated user via HTTP Basic credentials or a signed session cookie (`/auth/session` login flow).

- Credentials are loaded from `APP_AUTH_USERS_JSON` in deployment configuration or `.env`.
- HAL routes require role-bearing users, not just any authenticated user.
- Startup fails fast if `APP_AUTH_USERS_JSON` is missing, malformed, or does not include the required HAL/admin roles.
- HAL reads indexed local documentation, KPI summaries, and sanitized SoftDent aggregate snapshots.
- HAL can access QuickBooks only through approved read-only summary queries configured via `HAL_QB_REVENUE_SQL`, `HAL_QB_EXPENSES_SQL`, and `HAL_QB_AR_SQL`.
- Live QuickBooks report helpers are SDK-only in production; raw ODBC access remains an explicit admin diagnostic surface.
- QuickBooks Desktop should be integrated using the local read-only boundary described in `docs/quickbooks_desktop_safe_architecture.md`; HAL is not a write path into QuickBooks.

## Security contracts

### Environment posture (`APP_ENV`)

- **Unset `APP_ENV` is production-like** (same as `production`, `staging`, or any value outside explicit local dev/test).
- **Local-only dev/test values:** `development`, `dev`, `test`, `testing`, `local`.
- `ENVIRONMENT` is read as a fallback when `APP_ENV` is unset.

### Session signing (`APP_AUTH_SESSION_SECRET`)

- Required in production-like environments. Startup fails if missing when `APP_ENV` is unset, `production`, `staging`, or any non-development value.
- In explicit `development` / `test` only, a dev-only fallback may derive signing material from `APP_AUTH_USERS_JSON` (not for deployment).
- Generate a long random secret per environment; never copy example placeholders from `.env.example`.

### Widget update ingestion (`POST /api/widgets/update`, `POST /widgets/update`)

This route does **not** use HTTP Basic/session auth. It uses API-key or localhost policy instead.

| Condition | Auth behavior |
| --- | --- |
| `WIDGET_API_KEY` set | Require matching header (`WIDGET_API_KEY_HEADER`, default `X-API-Key`). Mismatch → `401`. |
| Production-like `APP_ENV` and no `WIDGET_API_KEY` | Reject with `403`. |
| Explicit dev/test (`APP_ENV=development` or `test`, etc.) and no `WIDGET_API_KEY` | Allow only from `127.0.0.1`, `::1`, `localhost`, or `testclient`. Other hosts → `403`. |

**Payload rules:**

- Max body size: **512 KiB** (`MAX_WIDGET_UPDATE_BYTES`). Larger → `413`.
- Body must be non-empty JSON object matching `WidgetUpdateRequest` (Pydantic). Invalid JSON → `400`; schema errors → `422`.
- Successful ingest returns `202` with widget/source counts.

### Control plane routes (`/api/control/*`, `/control/*`)

Require role **`hal:operator`** (HTTP Basic or valid session):

- `GET /control/runtime`, `GET /api/control/runtime`
- `POST /control/route`, `POST /api/control/route`
- `POST /control/score`, `POST /api/control/score`
- `POST /control/workflows/preview`, `POST /api/control/workflows/preview`
- `GET /control/litellm/config`, `GET /api/control/litellm/config`
- `GET /control/litellm/status`, `GET /api/control/litellm/status`

### Prometheus metrics

- `GET /metrics` requires role **`admin`**.

### LiteLLM proxy

- Default bind is **localhost only** (`http://127.0.0.1:4000` via `scripts/start_litellm_proxy.ps1`).
- Set **`LITELLM_MASTER_KEY`** before exposing the proxy beyond strictly local use or shared networks.
- Do not run an unauthenticated LiteLLM proxy on a reachable interface. See `.env.example` (`LITELLM_PROXY_BASE_URL`, `LITELLM_MASTER_KEY`).

### Local AI lanes (normal runtime)

- Frontend lane: `AI_FRONTEND_BASE_URL` / `OLLAMA_FRONTEND_BASE_URL` (default `:11434`).
- Backend lane: `AI_BACKEND_BASE_URL` / `OLLAMA_BACKEND_BASE_URL` (default `:11435`).
- **`OLLAMA_EVALUATOR_BASE_URL` (`:11436`, `qwen3:235b`) is isolated evaluator workflow only** — not part of normal HAL or LiteLLM routing.

## Endpoints

### GET /

- Returns: Welcome message
- Auth: Required

### GET /health

- Returns: API health status
- Auth: Required

### GET /kpis

- Returns: List of available KPIs
- Auth: Required

### GET /admin

- Returns: Admin page placeholder
- Auth: Required

### GET /softdent

- Returns: SoftDent page placeholder
- Auth: Required

### GET /quickbooks

- Returns: QuickBooks page placeholder
- Auth: Required

### GET /accounts-receivable

- Returns: Accounts Receivable page placeholder
- Auth: Required

### GET /reconciliation

- Returns: Reconciliation page placeholder
- Auth: Required

### GET /trends

- Returns: Trends page placeholder
- Auth: Required

### GET /ebitda

- Returns: EBITDA page placeholder
- Auth: Required

### GET /claims

- Returns: Claims page placeholder
- Auth: Required

### GET /hal9000

- Returns: HAL access policy and current local mode
- Auth: Required

### GET /reports

- Returns: Reports page placeholder
- Auth: Required

### POST /rebuild

- Triggers rebuild receipt logic
- Auth: Required

### POST /refresh

- Triggers refresh and verification
- Auth: Required

### POST /ci-gates

- Runs CI gates
- Auth: Required

### POST /smoke

- Runs smoke tests
- Auth: Required

### POST /api/widgets/update

- Accepts HAL supervisor widget feed JSON for ingestion into the persisted widget snapshot.
- Auth: `WIDGET_API_KEY` header and/or localhost policy (see **Security contracts**); not HTTP Basic.
- Returns `202` on success; enforces 512 KiB payload limit and `WidgetUpdateRequest` schema validation.
- Alias: `POST /widgets/update` (omitted from OpenAPI).

### POST /softdent/import

- Accepts a multipart file upload.
- Normalizes supported SoftDent dashboard, claims, or clinical-note files into canonical files under `SOFTDENT_IMPORT_DIR`.
- Recomputes pull status and the live financial summary after the import.
- Auth: Required

### POST /quickbooks/import

- Accepts a multipart file upload.
- Writes the uploaded report into the canonical `QUICKBOOKS_IMPORT_DIR` naming convention.
- Recomputes pull status and the live financial summary after the import.
- Auth: Required

### POST /hal9000

- HAL question endpoint with sanitization, Chroma-backed retrieval, and audit logging
- Automatically augments answers with live SoftDent aggregate summaries when the question asks about production, collections, insurance, patient mix, or provider ranking.
- Can call a controlled QuickBooks summary tool only for approved topics; arbitrary SQL is not allowed.
- Requires `hal:operator`
- Auth: Required

### POST /api/hal9000/accounting/journal-draft

- Creates a draft accounting journal entry from approved accounting input
- Returns draft-only journal lines plus deterministic validation output
- Requires `hal:operator`
- Auth: Required

### POST /api/hal9000/accounting/policy-answer

- Returns draft accounting policy guidance with local citations
- Requires `hal:operator`
- Auth: Required

### POST /api/hal9000/accounting/posting-queue

- Queues a draft QuickBooks Desktop posting request for local human review only
- Accepts balanced, valid, open-period journal lines only; invalid drafts are rejected
- Persists the draft in local HAL SQLite storage with `pending_review` status
- Persists `enqueue_mode` so downstream admin and reporting consumers can distinguish manual queue requests from auto-validated AI drafts
- Does not post anything to QuickBooks Desktop
- Requires `hal:operator`
- Auth: Required

### GET /api/hal9000/accounting/posting-queue

- Returns recent locally queued QuickBooks Desktop posting drafts
- Supports `status`, `limit`, and `cursor` query parameters for filtered review slices
- Returns `next_cursor` when another page of results is available
- Returns `range_start` and `range_end` so the UI can display exact page position without estimating from client state
- Includes persisted `enqueue_mode` lineage metadata on each item
- Intended for review workflows and later approval tooling
- Requires `hal:operator`
- Auth: Required

### GET /api/hal9000/accounting/posting-queue/metrics

- Returns lightweight aggregate counts for the local QuickBooks Desktop posting queue
- Includes total, pending review, approved, and rejected counts
- Intended for admin summaries that do not need the full queue payload
- Requires `hal:operator`
- Auth: Required

### GET /api/hal9000/accounting/posting-queue/activity

- Returns lightweight recent posting-queue activity for admin summaries
- Excludes journal lines and validation details used only by the full review workflow
- Includes persisted `enqueue_mode` lineage metadata for audit and reporting consumers
- Supports `limit` up to 25
- Requires `hal:operator`
- Auth: Required

### POST /api/hal9000/accounting/posting-queue/{queue_id}/review

- Approves or rejects a pending QuickBooks Desktop posting draft
- Records reviewer identity, review timestamp, and optional review note
- Rejects attempts to review an item more than once
- Does not post anything to QuickBooks Desktop
- Requires `hal:operator`
- Auth: Required

### POST /api/hal9000/refresh-index

- Refreshes the local HAL Chroma index from approved local documents and KPI summaries
- Requires `hal:index:refresh`
- Auth: Required
- Returns current vector backend metadata, including the local embedding provider

### GET /api/hal9000/status

- Returns HAL local index status, document count, vector backend, and embedding provider
- Also includes SoftDent snapshot availability and QuickBooks summary-tool readiness by topic
- Requires `hal:operator`
- Auth: Required

### GET /api/hal9000/audits

- Returns recent HAL audit events for review
- Requires `admin`
- Auth: Required

### POST /api/insurance-narratives/draft (internal)

- Operator-only local workflow endpoint for bounded packet + template draft creation
- Requires `hal:operator`
- Hidden from public OpenAPI (`include_in_schema=False`)
- `run_checker` defaults to **`false`** — no live model unless explicitly requested
- When `run_checker=true`, invokes the opt-in `fast_review` checker only (no cloud fallback)
- Does not approve, export, or submit narratives
- Returns `InsuranceNarrativeWorkflowResult`

Request body (`InsuranceNarrativeDraftWorkflowRequest`):

| Field | Type | Notes |
| --- | --- | --- |
| `patient_ref` | string | Bounded patient reference (fixture/export scope) |
| `claim_id` | string \| null | Optional claim scope |
| `procedure_ids` | string[] \| null | Optional procedure scope |
| `date_range` | `[start, end]` \| null | Optional service window |
| `narrative_type` | string | Narrative workflow type |
| `run_checker` | boolean | Default `false` |

### POST /api/insurance-narratives/approve-export (internal)

- Operator-only workflow for human approval + local export formatting
- Requires `hal:operator`
- Hidden from public OpenAPI (`include_in_schema=False`)
- Enforces review approval rules (`approval_attestation=true` required)
- `export.submission_status` is always `not_submitted` — no payer email/fax/upload
- Returns `InsuranceNarrativeWorkflowResult` with `status=export_created`

Request body includes full `packet` and `draft` objects plus `reviewer`, `notes`,
`approval_attestation`, optional `export_format` (`markdown` \| `plain_text`), and optional
advisory `checker_summary`.

---

For more details, see README.md and the OpenAPI docs at `/docs` when running the server.
