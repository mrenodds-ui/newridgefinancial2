# HAL Intent / Evaluation Library

Eval-only library for verifying HAL behavior. This is **not** a production
allowlist, **not** an "acceptable questions" list, and **not** a guardrail
bypass. It exists so we can check that HAL:

- answers normal business-safe questions correctly,
- asks for clarification when a request is ambiguous,
- reports unavailable data honestly,
- escalates to the 30B backend lane when appropriate, and
- refuses or limits unsafe actions.

## What this is NOT

This library must never be used to:

- skip backend validation or `HalAskRequest` checks,
- skip auth or `hal:operator` access checks,
- weaken or bypass any HAL guardrail,
- act as a production allowlist wired into `/api/hal9000`,
- authorize submit / send / fax / upload / Gateway actions,
- expose raw SoftDent CSV rows or direct patient identifiers,
- infer A/R from ledger or claim totals, or
- report `missing_softdent_ar` as `$0` instead of unavailable.

A case appearing here grants HAL **no** new permission. If HAL would refuse a
request in production, it must still refuse it even though the request is listed
here as an adversarial case.

## Files

| File | Purpose |
| --- | --- |
| `schema.json` | JSON Schema (draft-07) describing the case/profile shape and enums. |
| `fixture_profiles.json` | Named, de-identified data states (source availability only). No PHI, no raw rows. |
| `cases.json` | ~40 cases: ~30 normal business-safe and ~10 adversarial that must refuse/limit/require review. |
| (test) `app/tests/test_hal_intent_library_contract.py` | Contract/schema-only validation. No live API calls, no Ollama dependency. |

## Case fields

Each case in `cases.json` has:

- `id` – stable kebab-case identifier.
- `question` – the operator-style prompt.
- `intent_category` – one of the intent enums (see `schema.json`).
- `route` – `primary` or `second_opinion`.
- `expected_behavior` – e.g. `answer_normally`, `report_data_unavailable`,
  `escalate_to_30b`, `refuse_unsafe_external_action`,
  `explain_local_only_limitation`, `preserve_no_submission_guarantee`,
  `ask_for_clarification`.
- `allowed_to_answer` – whether HAL is permitted to give a substantive answer.
- `should_escalate_to_30b` – whether the backend lane is expected.
- `requires_source_summary` – whether a "what HAL looked at" summary is expected.
- `fixture_profile` – name in `fixture_profiles.json`.
- `must_not_do` – forbidden action tokens (submit, send, fax, upload,
  gateway_send, expose_raw_csv, infer_ar_from_totals,
  report_missing_ar_as_zero, etc.).
- `assertions` – contract-checkable expectations (status, contains, forbidden
  contains, guardrails, review action).
- `notes` – short rationale.

## Roadmap

- **Phase 1 (this change): contract/schema validation only.** Validates JSON
  shape, required fields, enums, safety invariants, and the absence of obvious
  bypass semantics. No `/api/hal9000` calls and no running Ollama lanes.
- **Phase 2 (future, separate approval): live harness.** Replay cases through
  the existing authenticated `/api/hal9000` path **without** weakening
  validation, auth, or guardrails, scoring against `assertions`.

## Running the contract test

```powershell
.\.venv\Scripts\python.exe -m pytest app\tests\test_hal_intent_library_contract.py
```

Optional broader check:

```powershell
.\.venv\Scripts\python.exe -m pytest app\tests\test_evaluation_prompt_packs.py app\tests\test_hal_intent_library_contract.py
```
