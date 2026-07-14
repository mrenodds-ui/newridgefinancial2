# Moonshot Claims Payer Attribution Refresh — APPLIED (HAL-10581)

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_CLAIMS_BRIDGE_2026-07-13.md`  
**Operator:** proceed  
**Status:** Applied (read-only Sensei Reference + SQLite; no SoftDent write-back; no invented EDI/payer IDs)  
**Build stamp:** kept `hal-10576` (package HAL-10581)

## Verdict shipped

Sensei Gateway **Reference** patient policies + InsCo plan map populate **`sd_patient_insurance`**. Generic daysheet claim payers (`Insurance`) are attributed via claim chart MRN → patient chart Id. HAL-10580 bridge now shows **named carriers**; attribution gap cleared.

## Live snapshot (this workstation)

| Metric | Value |
|--------|-------|
| Sensei root | `C:\ProgramData\Sensei Gateway Client\DataSync\0000950863` |
| `sd_patient_insurance` rows | **5415** |
| Claims attributed this run | **60** (1 already named) |
| Named / unnamed claims | **61 / 0** |
| Claims billed | **$7,714.00** |
| gapCode | `CLAIMS_AR_RECONCILE_MISMATCH` (aging Ins **$0** vs claims — honest; empty ≠ $0) |
| Prior gap cleared | `CLAIMS_PAYER_ATTRIBUTION_REQUIRED` |

Top named carriers (sample): DELTA DENTAL OF KS (17), DELTA DENTAL OF CA (9), AETNA MEDICARE ADVANTAGE (5), CENTRAL STATES (5), GUARDIAN (5), DELTA DENTAL OF OH (4), CIGNA DENTAL (4).

## Why Sensei (not ODBC)

- `SOFTDENT_ODBC_DSN` unset; no SoftDent ODBC System DSN on this host.
- Sensei Reference holds real `InsurancePolicies[]` + `insco_*.json` plan→carrier names.
- Chart `Id` / `InterfaceId` matches daysheet claim ids `DS-YYYYMMDD-{chart}-…`.

## What shipped

| Item | Detail |
|------|--------|
| Plan map | `load_sensei_plan_carrier_map` from `insco_*.json` |
| Insurance populate | `populate_sensei_patient_insurance` (UniqueID + chart keys) |
| Attribution | `attribute_sd_claims_payers_from_insurance` (chart, then name) |
| Refresh entry | `refresh_claims_payer_attribution` |
| Extract hook | Sensei lane + post-claims attribution in `extract_softdent_odbc` |
| Bridge action | `suggestedAction=refresh_sensei_claims_payer_attribution` when attribution gap |
| Tests | `test_payer_attribution_refresh_hal10581.py` |

## Honesty rules preserved

- No invented member / EDI / Availity payer IDs (NULL when absent).
- No SoftDent write-back.
- Aging outstanding insurance **$0** remains SoftDent print truth; claims stay ops detail.
- Already-named claim payers are not overwritten.

## Validation

| Gate | Result |
|------|--------|
| Unit `test_payer_attribution_refresh_hal10581` | **PASS** |
| Unit `test_outstanding_claims_bridge_hal10580` | **PASS** |
| `sd_patient_insurance_count > 0` | **PASS** (5415) |
| `namedPayerClaimCount` majority | **PASS** (61/61) |
| Attribution gap cleared | **PASS** |
| Aging Ins $0 preserved | **PASS** |

```text
cd NewRidgeFinancial2
python -m unittest test_payer_attribution_refresh_hal10581 test_outstanding_claims_bridge_hal10580 -v
```

## Files

- `NewRidgeFinancial2/softdent_odbc_extract.py`
- `NewRidgeFinancial2/softdent_outstanding_claims_bridge.py`
- `NewRidgeFinancial2/test_payer_attribution_refresh_hal10581.py`
- `NewRidgeFinancial2/docs/MOONSHOT_PAYER_ATTRIBUTION_REFRESH_HAL10581_APPLIED_2026-07-13.md`
- `NewRidgeFinancial2/docs/MOONSHOT_SOFTDENT_COMPREHENSIVE_INGEST_HAL_2026-07-13.md` (amendment)

## Not in this package

- ERA-835 procurement / Ins Plan collections dollars  
- SoftDent ODBC DSN setup (optional when available)  
- Inventing carriers or overwriting aging insurance $0  
