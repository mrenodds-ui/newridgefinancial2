# Patient Force Attest (OM desk review) — APPLIED

**Date:** 2026-07-16  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_HAL_PATIENT_CONTEXT_2026-07-16.md`  
**Operator:** approve (spelled aprroove)

## Shipped (real NR2 paths — not Moonshot’s invented React files)

| Item | Where |
|------|--------|
| Patient attest ledger | `patient_force_attest.py` → `app_data/nr2/ops/patient_force_attest_log.jsonl` |
| MATCH gate (not laser-red) | `patient_attest_eligible` / `force_attest_patient` |
| APIs | `POST/GET /api/apex/patient-force-attest`, `GET …/eligible` |
| Desk smoke flag | `patientAttestEligible` (informational; `forceCloseAvailable` stays laser-gated) |
| OM mini-dossier button | **ATTEST REVIEW** in `nr2-optical-page-office-manager.js` |
| Wire helpers | `patientForceAttest*` in `nr2-optical-page-wire.js` |
| HAL persona | Attested-today line in `patient_context_persona_block` |
| Tests | `test_patient_force_attest.py` |

## Semantics (important)

- **Period Force Close** (`forceCloseAvailable`) = laser/stalled escape hatch — **unchanged**.
- **Patient ATTEST REVIEW** = OM shadow review when `deskProof === MATCH`.
- SoftDent **READ-ONLY**; `empty ≠ $0`; balance may be `unavailable`.
- Does **not** call `force_period_close` or SoftDent write-back.

## Validation

1. Desk smoke GREEN + MATCH → `patientAttestEligible: true`, `forceCloseAvailable: false`.
2. OM mini-dossier → ATTEST REVIEW enabled only on MATCH.
3. Click writes JSONL + HAL patient audit `patient_force_attest`.
4. Second click same day is idempotent (**ATTESTED TODAY**).
5. HAL chat with bound context mentions OM attested today when true.
