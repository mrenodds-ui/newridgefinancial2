# Moonshot AI — HAL-10607 PWImages Eligibility / Remittance Warehouse (APPLIED)

**Date:** 2026-07-13  
**Build:** `hal-10607`  
**Consult:** `MOONSHOT_PWIMAGES_EOB_MINE_CONSULT_2026-07-13.md`  
**Operator:** `proceed`

## Summary

Applied Moonshot’s recommended package: ingest PWImages **eligibility/benefits** into analytical staging + fuzzy carrier alias bridge; **warehouse remittance EOB paths only** (no OCR dollars into Gold / settlement).

## Shipped

| Piece | Path |
|-------|------|
| Module | `softdent_pwimages_eligibility_hal10607.py` |
| Tests | `test_hal10607_pwimages_eligibility.py` |
| BUILD_ID | `apex_backend.py` → `hal-10607` |
| SoftDent widget | `softdent-pwimages-eligibility-hal10607` |
| APIs | `GET/POST /api/apex/pwimages-eligibility/status\|run` |
| Mine source | `docs/_pwimages_eob_mine/eob_mine_all.json` |
| Remit copies | `docs/_pwimages_eob_mine/remittance_eobs/` |

### Tables (analytics DB)

- `staging_eligibility_parameters` — plan design (deductibles / % / max / frequency notes); NULL when unparsed (**empty ≠ $0**)
- `warehouse_remittance_eobs` — `source_path`, warehouse copy, account id, category, carriers/markers — **no amount/paid columns**

### Honesty

- Does **not** write `sd_insurance_payment_lines` or `settlement_matrix`
- No SoftDent write-back
- Remittance UI honesty banner: *UNVERIFIED SCANNED ESTIMATE — DO NOT POST. AWAIT GOLD CSV OR ERA 835 FOR SETTLEMENT TRUTH.*
- Alias proposals use `match_method=pwimages_eligibility_10607` (pending/auto via existing alias bands)

## Validation

- Unit tests: `test_hal10607_pwimages_eligibility` + tip BUILD_ID on prior HAL packages — OK
- Live ingest against mine JSON:
  - eligibilityUpserted **2276**
  - eligibilityMatched **2126** (fuzzy rate **93.4%** ≥ 80% gate)
  - remittanceUpserted **16** (paths only; `remittanceHasNoMoneyColumns=true`)
  - alias proposals touched via `pwimages_eligibility_10607` (pending/auto bands)

## Not done (explicit)

- OCR remittance auto-posting (HAL-10608 rejected)
- Gold CSV substitute from scanned EOBs
- SoftDent write-back
