# Availity Eligibility in HAL Patient Dossier — Applied

**Date:** 2026-07-11  
**Build:** **hal-10497**  
**Consult:** `MOONSHOT_AVAILITY_DOSSIER_ELIGIBILITY_CONSULT_2026-07-11.md`  
**Status:** Applied after operator “proceed with moonshot ai as directed and do not deviate”

## Shipped checklist

| Priority | Item | Status | Where |
|----------|------|--------|-------|
| **MUST** | `eligibility` section (empty≠$0, gaps[], demo/live) | Done | `patient_dossier.py` |
| **MUST** | Honest SoftDent resolver (`sd_patient_insurance` if present) | Done | `_resolve_eligibility_for_patient` |
| **MUST** | Availity via cache + `fetch_eligibility_271` (cache-first non-blocking) | Done | cache helpers + force fetch |
| **MUST** | PHI-safe audit `eligibility_query` (hashed ids) | Done | `apex_backend.py` → `hal_patient_audit` |
| **MUST** | `DOSSIER_SUMMARY_PROMPT` Eligibility + `[DEMO DATA]` | Done | `patient_dossier_prompts.py` |
| **SHOULD** | OM `eligibility-card` + dossier embed | Done | `apex_missing_widgets_pack.py` · `apex-core.js` |
| **SHOULD** | 5-minute eligibility cache TTL | Done | `store_eligibility_snapshot(..., ttl_sec=300)` |
| **NICE** | `memberId`/`payerId`/`fetchEligibility` overrides | Done | API query params · bridge · HAL tool |
| **NICE** | Background pre-fetch | Deferred | Per consult |

## Honesty / invariants

- SoftDent **READ-ONLY**; gaps listed, never invent member/payer IDs
- Empty money → **`unknown`**, never `$0.00`
- Cache-first: dossier does **not** wait 60s on Availity; staff use `fetch_eligibility_271` or pass overrides + `fetchEligibility=1`
- Kill switch: `DOSSIER_ELIGIBILITY_ENABLED=0`
- Demo until Standard Plan: `AVAILITY_LIVE_FALLBACK_DEMO=1`

## How to try

1. Set `NR2_PROVIDER_NPI` (practice NPI) and keep `DOSSIER_ELIGIBILITY_ENABLED=1`.
2. Ask HAL: **Summarize patient P100** — Eligibility section shows SoftDent gaps or cached benefits.
3. Populate cache: HAL `fetch_eligibility_271` / `fetch_availity_eligibility`, then re-summarize.
4. One-off override: pass `memberId` + `payerId` on summarize (forces Availity fetch).

## Tests

`python -m unittest test_patient_dossier -v` — EligibilityDossierTests + existing dossier tests.
