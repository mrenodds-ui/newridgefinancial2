# Insurance narrative case packets

Foundation for insurance narrative work in New Ridge Family Financial. This patch adds a
**bounded case-packet layer** only — no full narrative generation, no UI wiring, and no
unrestricted database access for models.

## Why case packets

Models should not receive raw, unrestricted patient or claim database dumps. Future narrative
drafting and the opt-in `fast_review` checker will consume a **minimum-necessary case packet**
that is:

- patient-scoped (`patient_ref`, not open-ended queries)
- claim-scoped (`claim_id`)
- procedure / date-range scoped
- source-cited (`source_facts[]` with `fact_id`)
- read-only and audit-friendly
- human-reviewable before submission

## Architecture

```text
Scoped adapter (fixture | local export | SoftDent export file)
        |
        v
InsuranceNarrativeScope  ->  fetch_packet_inputs(scope)
        |
        v
InsuranceNarrativePacketInputs  (bounded — no raw rows)
        |
        v
build_insurance_narrative_case_packet(..., adapter=None|explicit)
        |
        v
InsuranceNarrativeCasePacket
        |
        +--> draft_insurance_narrative_from_packet(packet) -> InsuranceNarrativeDraft
        |         |
        |         +--> draft_to_fast_review_source_text(packet, draft)   # opt-in checker input
        |         |
        |         +--> create_narrative_review_record(draft) -> InsuranceNarrativeReviewRecord
        |                   |
        |                   +--> approve / reject / request_narrative_revision
        |                             |
        |                             +--> export_approved_insurance_narrative(...) -> InsuranceNarrativeExport
        |
        +--> create_insurance_narrative_draft_workflow(..., adapter=None)  # orchestrated facade
        +--> approve_and_export_insurance_narrative_workflow(...)
        +--> case_packet_to_fast_review_source_text(packet)
```

Python module: `app.insurance_narratives`

| Type | Purpose |
| --- | --- |
| `InsuranceNarrativeDataAdapter` | Protocol for scoped read-only packet input providers |
| `InsuranceNarrativeScope` | Explicit scope: `patient_ref`, `claim_id`, `procedure_ids`, `date_range`, `narrative_type`, `actor` |
| `InsuranceNarrativePacketInputs` | Bounded adapter output before packet assembly (no raw DB rows) |
| `FixtureInsuranceNarrativeDataAdapter` | Deterministic de-identified fixtures (default for tests) |
| `LocalInsuranceNarrativeDataAdapter` | Conservative SoftDent export reader (explicit opt-in only) |
| `SoftDentExportFileInsuranceNarrativeAdapter` | Scoped CSV export reader for insurance narrative packets |
| `InsuranceNarrativeCasePacket` | Top-level bounded packet |
| `PatientCaseSummary` | Patient reference label (no raw PHI dump) |
| `ClaimCaseSummary` | Claim id, status, payer, billed amount, denial reason |
| `ProcedureCaseSummary` | Scoped procedures |
| `NarrativeSourceFact` | Citable fact with `fact_id` and `source_type` |
| `NarrativeAttachmentSummary` | Attachment availability summary |
| `NarrativeMissingDataItem` | Explicit unavailable data (never fake `$0`) |
| `NarrativeAuditMetadata` | Actor, timestamps, schema version, `adapter_name`, `source_mode` |
| `InsuranceNarrativeDraft` | Template draft from a bounded packet |
| `NarrativeDraftSection` | Purpose, summary, facts, limitations, next step |
| `NarrativeDraftCitation` | `fact_id` citation tied to a draft section |
| `NarrativeDraftWarning` | Non-blocking missing-data warnings |
| `InsuranceNarrativeReviewRecord` | Human review state for a draft |
| `NarrativeReviewAuditEvent` | Append-only audit trail entry |
| `NarrativeCheckerSummary` | Advisory fast-review checker counts |
| `InsuranceNarrativeExport` | Local formatted export for approved drafts |
| `NarrativeExportSection` | Exported narrative section |
| `NarrativeExportApprovalSummary` | Reviewer attestation summary on export |
| `InsuranceNarrativeWorkflowResult` | Orchestrated workflow output |
| `InsuranceNarrativeWorkflowOptions` | Workflow options (`run_checker`, `export_format`) |

## Data adapter layer

`app.insurance_narratives.data_adapter` separates **scoped data retrieval** from **packet assembly**.
Adapters never return raw database rows or unrestricted exports — only bounded
`InsuranceNarrativePacketInputs` normalized into the existing `InsuranceNarrativeCasePacket`
schema.

### Adapter protocol

```python
from app.insurance_narratives import (
    InsuranceNarrativeScope,
    FixtureInsuranceNarrativeDataAdapter,
    LocalInsuranceNarrativeDataAdapter,
    SoftDentExportFileInsuranceNarrativeAdapter,
    softdent_export_file_adapter,
    build_insurance_narrative_case_packet,
    build_packet_inputs_from_adapter_scope,
)

scope = InsuranceNarrativeScope(
    patient_ref="CHART-A",
    claim_id="CLAIM-1001",
    procedure_ids=["PROC-CROWN-BUILDUP-3"],
    date_range=None,
    narrative_type="denied_claim_resubmission",
    actor="staff@clinic",
)

# Default (None) uses fixture adapter — deterministic for tests
packet = build_insurance_narrative_case_packet(**scope.model_dump(), adapter=None)

# Explicit local export adapter (opt-in; not exposed on public HTTP routes yet)
local_packet = build_insurance_narrative_case_packet(
    **scope.model_dump(),
    adapter=LocalInsuranceNarrativeDataAdapter(),
)

# Explicit SoftDent export-file adapter (CSV imports; no E-Services/Gateway)
export_packet = build_insurance_narrative_case_packet(
    **scope.model_dump(),
    adapter=softdent_export_file_adapter(),
)
```

### Fixture vs local vs export-file adapter

| Adapter | `adapter_name` | `source_mode` | When to use |
| --- | --- | --- | --- |
| `FixtureInsuranceNarrativeDataAdapter` | `fixture` | `fixture` | Tests, local dev, default when `adapter=None` |
| `LocalInsuranceNarrativeDataAdapter` | `local_softdent_export` | `local_export` | Explicit opt-in when approved SoftDent claim/clinical-note exports exist |
| `SoftDentExportFileInsuranceNarrativeAdapter` | `softdent_export_file` | `export_file` | Scoped insurance-narrative CSV exports from `INSURANCE_NARRATIVE_SOFTDENT_EXPORT_DIR` |

The fixture adapter preserves all prior deterministic behavior (`CHART-A` / `CLAIM-1001`).
The local adapter reads only scoped rows from `load_softdent_claim_rows()` and
`load_softdent_clinical_note_rows()` matched by `patient_ref`, `claim_id`, optional
`procedure_ids`, and optional `date_range`. It emits source facts only when the row can
be cited with a `fact_id`, `source_type`, `source_label`, and `source_date`; it does not
invent facts, synthesize A/R, or read arbitrary files.

The export-file adapter reads **only** known CSV files from a configured import directory.
It does **not** use Carestream/Sensei E-Services, Gateway APIs, or direct SoftDent database
access. Configure with:

```bash
INSURANCE_NARRATIVE_SOFTDENT_EXPORT_DIR=app/data/imports/insurance_narratives/softdent
```

Supported first-pass exports:

| File | Required columns |
| --- | --- |
| `softdent_claims_export.csv` | `patient_ref`, `claim_id`, `payer_name`, `service_date`, `claim_status`, `claim_amount`, `procedure_ids`, `source_report_date` |
| `softdent_procedures_export.csv` | `patient_ref`, `procedure_id`, `procedure_code`, `procedure_description`, `service_date`, `tooth`, `provider_label`, `source_report_date` |
| `softdent_patient_ledger_export.csv` | `patient_ref`, `transaction_id`, `transaction_date`, `transaction_type`, `procedure_id`, `claim_id`, `description`, `amount`, `source_report_date` |

Scoped parsing matches `patient_ref` and `claim_id`; procedure rows are linked via
`procedure_ids` on the claim row (comma-separated). Ledger rows are scoped by `patient_ref`,
optional `claim_id`, optional `procedure_ids`, and optional `date_range` on `transaction_date`.
When `claim_id` is provided, ledger rows with a matching `claim_id` are included, as are rows
with a blank `claim_id` when `procedure_id` is tied to an included procedure. Non-matching
export rows are ignored. Ledger `amount` values become supporting source facts only — they do
**not** create A/R totals, patient balance totals, or `latestAr` values. Explicit A/R still
requires a dedicated A/R export (`missing_softdent_ar` remains until that export is supported).
Malformed or missing exports surface explicit missing-data codes — never invented clinical
facts or synthetic `$0` A/R.

### Explicit scope (no open queries)

Every adapter call requires an `InsuranceNarrativeScope` with explicit `patient_ref`.
Optional `claim_id`, `procedure_ids`, and `date_range` further narrow the case. Adapters
cannot perform unrestricted patient or database lookups.

### No raw DB dumps

Adapter output is limited to typed summaries (`PatientCaseSummary`, `ClaimCaseSummary`,
`ProcedureCaseSummary`, `NarrativeSourceFact`, etc.). Raw export rows, PHI field names, and
`database_dump`-style payloads are never placed in the packet.

### Missing data policy

When exports are unavailable or incomplete, adapters append `NarrativeMissingDataItem`
entries (e.g. `missing_softdent_ar`, `missing_claim_record`, `missing_softdent_patient_ledger_export`,
`missing_scoped_ledger_rows`, `invalid_softdent_patient_ledger_export`). Missing A/R remains
**unavailable**, never `$0`. The local adapter always flags `missing_softdent_ar` until a
scoped A/R mapping is approved. Ledger exports are optional supporting inputs; absent or
invalid ledger files do not block claim/procedure facts, but ledger amounts never substitute
for A/R.

### Future SoftDent mapping plan

1. Wire scoped A/R aging from approved exports (still as missing-data when absent).
2. Map attachment availability from SoftDent imaging export contracts.
3. Add prior-auth reference lookup when export schema is stable.
4. Expose adapter selection on operator routes via a safe enum (`fixture` | `local_softdent`) only.

Audit metadata on each packet records `adapter_name` and `source_mode` for traceability.

## Local workflow facade

`app.insurance_narratives.workflow` composes the packet → draft → optional checker → review →
approval → export pipeline as **pure local functions**. Operator-only HTTP endpoints wrap this
facade for future UI integration. No automatic submission and no unrestricted database access.

### Operator-only API endpoints (internal)

| Endpoint | Purpose |
| --- | --- |
| `POST /api/insurance-narratives/draft` | Packet + draft workflow (`run_checker` defaults `false`) |
| `POST /api/insurance-narratives/approve-export` | Approve + local export (`submission_status=not_submitted`) |

Both require `hal:operator`, are hidden from public OpenAPI (`include_in_schema=False`), and do
not submit to payers. See `docs/API.md` for request/response shapes.

```python
from app.insurance_narratives import (
    create_insurance_narrative_draft_workflow,
    approve_and_export_insurance_narrative_workflow,
)

# Step 1: packet + draft (checker off by default)
draft_result = create_insurance_narrative_draft_workflow(
    patient_ref="CHART-A",
    claim_id="CLAIM-1001",
    narrative_type="denied_claim_resubmission",
    actor="staff@clinic",
    run_checker=False,  # explicit opt-in only
)

# Step 2: after human approval — separate from draft creation
export_result = approve_and_export_insurance_narrative_workflow(
    packet=draft_result.packet,
    draft=draft_result.draft,
    reviewer="staff@clinic",
    notes="Citations verified.",
    approval_attestation=True,
    actor="staff@clinic",
)
# export_result.export.submission_status == "not_submitted"
```

### Draft workflow (`create_insurance_narrative_draft_workflow`)

- Always builds a bounded case packet and template draft from packet facts only
- `run_checker=False` by default — **no live model call**
- `run_checker=True` explicitly invokes `run_fast_review_check` once using
  `draft_to_fast_review_source_text(packet, draft)`
- Checker lane unavailable → `checker_unavailable` status + advisory warning; workflow continues
- `blocked_missing_data` drafts are never auto-approved; no export from this function

### Approval/export workflow (`approve_and_export_insurance_narrative_workflow`)

- Creates review record, approves with attestation, formats local export
- `blocked_missing_data` drafts fail safely at approval
- `approval_attestation=True` required
- `submission_status` remains `not_submitted`; no email, fax, upload, or payer API calls

### Workflow statuses

| Status | When |
| --- | --- |
| `draft_created` | Packet + draft created; checker not run |
| `blocked_missing_data` | Draft has blocking missing data |
| `checker_completed` | Opt-in checker returned `ok` |
| `checker_unavailable` | Opt-in checker lane unavailable |
| `export_created` | Approved export formatted locally |

Audit lineage: `packet_id` → `draft_id` → `review_id` → `export_id`

## Approved-only export formatting

After human approval, staff can format an export for **local copy/review** only. Export does
not submit, email, fax, upload, or write to disk.

```python
from app.insurance_narratives import export_approved_insurance_narrative

export = export_approved_insurance_narrative(
    packet=packet,
    draft=draft,
    review=approved_review,
    actor="staff@clinic",
    export_format="markdown",  # or "plain_text"
)
# export.body is ready for human copy; submission_status is always "not_submitted"
```

### Export rules

- `review.status` must be `approved`
- `review.approval_attestation` must be `true`
- `packet_id`, `draft_id`, and `review_id` lineage must match
- `blocked_missing_data` drafts cannot be exported (defensive guard)
- Citations, missing-data disclosures, and approval summary are always included
- `submission_status` is always `not_submitted`

### Supported formats

| Format | Description |
| --- | --- |
| `markdown` | Headings with `#` / `##` for staff copy into documents |
| `plain_text` | Same content with ASCII section dividers |

### Audit lineage

Full traceability chain:

`packet_id` → `draft_id` → `review_id` → `export_id`

Each export records `created_at`, `actor`, and `NarrativeExportAuditMetadata`.

## Human review workflow

After drafting, staff open a **local, auditable review record** tied to `packet_id` and
`draft_id`. No UI or export wiring in this patch.

```python
from app.insurance_narratives import (
    create_narrative_review_record,
    approve_narrative_draft,
    reject_narrative_draft,
    request_narrative_revision,
    checker_result_to_summary,
)

review = create_narrative_review_record(draft, reviewer="staff@clinic")
# Optional advisory checker (explicit opt-in only, not called here):
# summary = checker_result_to_summary(run_fast_review_check(...))
# review = create_narrative_review_record(draft, reviewer="staff@clinic", checker_summary=summary)

approved = approve_narrative_draft(
    review,
    reviewer="staff@clinic",
    notes="Citations verified against packet.",
    approval_attestation=True,
)
```

### Review statuses

| Status | Meaning |
| --- | --- |
| `pending_review` | Awaiting human decision |
| `approved` | Reviewer attested and approved (no auto-submit) |
| `rejected` | Reviewer rejected the draft |
| `revision_requested` | Reviewer requested specific changes |

### Approval attestation

`approve_narrative_draft(..., approval_attestation=True)` requires the reviewer to confirm:

- the draft was reviewed by a human
- citations and source facts were checked
- missing-data limitations were considered
- the narrative is **not** automatically submitted to any payer

Approval does not call export or submission code.

### Blocked draft behavior

Drafts with `status == blocked_missing_data` cannot be approved. Staff must resolve
blocking `missing_data[]` items and produce a new draft before approval.

### Checker summary is advisory only

`checker_summary` stores normalized counts from an optional `run_fast_review_check()` result
(`checker_status`, issue counts, `ready_for_human_review`). It is informational only — it
does not gate approval and is never required.

### Audit trail and lineage

Each `InsuranceNarrativeReviewRecord` preserves immutable `packet_id` / `draft_id` lineage.
`audit_events[]` append on create, approve, reject, and revision request with actor,
timestamp, previous status, and new status.

## Packet-bounded drafting

`draft_insurance_narrative_from_packet(packet, actor=...)` builds a **template/rule-based** draft
from packet facts only. No live model is required in this patch.

Draft sections:

1. **Purpose** — human-reviewed scope statement
2. **Case Summary** — patient/claim scope with cited facts
3. **Supporting Facts** — one line per `source_facts[]` entry with `[fact_id]`
4. **Missing Information / Limitations** — explicit missing-data codes (unavailable, not `$0`)
5. **Recommended Next Step** — staff action before any submission

### Draft status

| Status | When |
| --- | --- |
| `blocked_missing_data` | Any `missing_data[].blocking == true` |
| `ready_for_human_review` | No blocking missing data |
| `draft` | Reserved for future in-progress states |

`approval_required` is **always** `true`. Nothing auto-submits to payers.

### Citation requirements

Every factual sentence in **Case Summary** and **Supporting Facts** must cite a packet
`fact_id`. Missing-data references use `missing_data[].code` in the limitations section.
The drafter does not invent clinical facts, patient details, or synthetic A/R.

```python
from app.insurance_narratives import (
    build_insurance_narrative_case_packet,
    draft_insurance_narrative_from_packet,
    draft_to_fast_review_source_text,
)

packet = build_insurance_narrative_case_packet(...)
draft = draft_insurance_narrative_from_packet(packet, actor="operator")
checker_input = draft_to_fast_review_source_text(packet, draft)
# Later (explicit opt-in only): run_fast_review_check(source_text=checker_input, ...)
```

## Source facts and citations

Each `NarrativeSourceFact` includes:

- `fact_id` — stable id used in fast-review source text and future citations
- `source_type` — e.g. `claim`, `clinical_note`, `payer_denial`, `softdent`
- `source_label`, `source_date`, `text`
- `supports` — related ids (claim, procedure)
- `source_strength` — `primary` or `supporting`

Narrative generation (future) must cite `fact_id` values instead of inventing facts.

## Missing data strategy

Missing exports are **explicit** `NarrativeMissingDataItem` entries:

| Code | Meaning |
| --- | --- |
| `missing_softdent_ar` | No A/R export — unavailable, **not** `$0` |
| `missing_softdent_claims_export` | `softdent_claims_export.csv` missing or unreadable in narrative import dir |
| `missing_softdent_procedures_export` | `softdent_procedures_export.csv` missing or unreadable |
| `missing_scoped_claim_row` | No claim row matched `patient_ref` + `claim_id` |
| `missing_scoped_procedure_rows` | Linked procedure rows not found in procedures export |
| `missing_prior_auth` | Prior auth reference not in packet |
| `missing_radiograph` | Supporting image unavailable |
| `missing_claim_record` | No matching claim in approved scope |

Each item has `severity`, `why_it_matters`, and `blocking`.

## Human approval

Case packets are inputs to human-reviewed workflows. Nothing in this layer auto-submits to payers
or replaces staff judgment.

## Fast review checker (opt-in, later)

The opt-in checker (`POST /api/hal9000/fast-review-check`, `run_fast_review_check`) is **not**
called automatically by the drafter. Use `draft_to_fast_review_source_text(packet, draft)` to
prepare deterministic checker input when staff explicitly requests a structured review.

`fast_review` is **not** a default narrative writer. `chat_second_opinion` remains the production
second-opinion path on `:11435` / `qwen3:30b`.

## Current builder scope

`build_insurance_narrative_case_packet()` defaults to `FixtureInsuranceNarrativeDataAdapter`
when `adapter=None` (deterministic de-identified fixtures). Pass
`LocalInsuranceNarrativeDataAdapter()` for conservative reads from approved SoftDent
dashboard claim exports, or `SoftDentExportFileInsuranceNarrativeAdapter()` for scoped
reads from `INSURANCE_NARRATIVE_SOFTDENT_EXPORT_DIR` CSV files. The builder does not invent
clinical facts, synthesize dental A/R, or return unrestricted database tables regardless of
adapter.

## Tests

`app/tests/test_insurance_case_packet.py` covers serialization, deterministic ids, missing A/R
semantics, fact ids, fast-review source text, and PHI-like fixture scans.

`app/tests/test_insurance_case_packet_adapter.py` covers fixture preservation, explicit
adapter wiring, scoped inputs only, no raw rows in packets, missing-data policy, local
and SoftDent export-file adapter behavior, audit metadata (`adapter_name` / `source_mode`),
and workflow adapter passthrough.

`app/tests/test_insurance_narrative_draft.py` covers template drafting, citations, blocking
status, warnings, approval requirements, and `draft_to_fast_review_source_text`.

`app/tests/test_insurance_narrative_review.py` covers human review workflow, approval
attestation, blocked-draft rules, advisory checker summary, audit events, and no auto-submit.

`app/tests/test_insurance_narrative_export.py` covers approved-only export, lineage guards,
citation/disclosure inclusion, format variants, and no filesystem/network side effects.

`app/tests/test_insurance_narrative_workflow.py` covers the orchestrated facade, checker
opt-in behavior, approval/export composition, lineage, and no submission side effects.

`app/tests/test_insurance_narrative_routes.py` covers operator-only HTTP endpoints, auth scope,
checker defaults, advisory unavailable handling, and export safety rules.
