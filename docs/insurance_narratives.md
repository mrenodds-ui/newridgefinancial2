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
        +--> case_packet_to_fast_review_source_text(packet)   # later: opt-in fast_review checker
        +--> future narrative drafter (not built yet)
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

## Fast review checker (later)

The opt-in checker (`POST /api/hal9000/fast-review-check`, `run_fast_review_check`) remains
separate. Convert a packet with:

```python
from app.insurance_narratives import build_insurance_narrative_case_packet, case_packet_to_fast_review_source_text

packet = build_insurance_narrative_case_packet(
    patient_ref="CHART-A",
    claim_id="CLAIM-1001",
    narrative_type="denied_claim_resubmission",
    actor="operator",
)
source_text = case_packet_to_fast_review_source_text(packet)
# Later: pass source_text to run_fast_review_check(...) when explicitly requested
```

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
