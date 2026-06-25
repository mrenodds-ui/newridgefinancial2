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
Approved exports / fixtures
        |
        v
build_insurance_narrative_case_packet(...)
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
        +--> case_packet_to_fast_review_source_text(packet)
```

Python module: `app.insurance_narratives`

| Type | Purpose |
| --- | --- |
| `InsuranceNarrativeCasePacket` | Top-level bounded packet |
| `PatientCaseSummary` | Patient reference label (no raw PHI dump) |
| `ClaimCaseSummary` | Claim id, status, payer, billed amount, denial reason |
| `ProcedureCaseSummary` | Scoped procedures |
| `NarrativeSourceFact` | Citable fact with `fact_id` and `source_type` |
| `NarrativeAttachmentSummary` | Attachment availability summary |
| `NarrativeMissingDataItem` | Explicit unavailable data (never fake `$0`) |
| `NarrativeAuditMetadata` | Actor, timestamps, schema version |
| `InsuranceNarrativeDraft` | Template draft from a bounded packet |
| `NarrativeDraftSection` | Purpose, summary, facts, limitations, next step |
| `NarrativeDraftCitation` | `fact_id` citation tied to a draft section |
| `NarrativeDraftWarning` | Non-blocking missing-data warnings |
| `InsuranceNarrativeReviewRecord` | Human review state for a draft |
| `NarrativeReviewAuditEvent` | Append-only audit trail entry |
| `NarrativeCheckerSummary` | Advisory fast-review checker counts |

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

`build_insurance_narrative_case_packet()` uses deterministic **de-identified fixtures** for
this foundation patch. It does not invent clinical facts, synthesize dental A/R, or read
unrestricted database tables. Service-backed assembly can replace fixtures in a later patch once
export contracts are wired with the same bounds.

## Tests

`app/tests/test_insurance_case_packet.py` covers serialization, deterministic ids, missing A/R
semantics, fact ids, fast-review source text, and PHI-like fixture scans.

`app/tests/test_insurance_narrative_draft.py` covers template drafting, citations, blocking
status, warnings, approval requirements, and `draft_to_fast_review_source_text`.

`app/tests/test_insurance_narrative_review.py` covers human review workflow, approval
attestation, blocked-draft rules, advisory checker summary, audit events, and no auto-submit.
