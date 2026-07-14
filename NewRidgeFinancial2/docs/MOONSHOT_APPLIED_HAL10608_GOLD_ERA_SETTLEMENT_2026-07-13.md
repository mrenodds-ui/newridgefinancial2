# Moonshot AI — HAL-10608 Gold ∪ ERA Settlement Hydration (APPLIED)

**Date:** 2026-07-13  
**Build:** `hal-10608`  
**Consult:** `MOONSHOT_PWIMAGES_JPEG_PDF_EOB_CONSULT_2026-07-13.md`  
**Operator:** `proceed` (§3 STOP OCR → Gold/ERA pivot)

## Summary

Shipped the Moonshot-recommended pivot: **STOP further PWImages JPEG/PDF OCR for settlement**, and expose a single **Gold CSV ∪ ERA 835 readiness** surface that delegates to existing Gold facilitation (10606) and ERA inbox packs — without inventing dollars or SoftDent write-back.

## Shipped

| Piece | Path |
|-------|------|
| Module | `softdent_gold_era_settlement_hal10608.py` |
| Tests | `test_hal10608_gold_era_settlement.py` |
| BUILD_ID | `apex_backend.py` → `hal-10608` |
| Widget | `softdent-gold-era-settlement-hal10608` |
| APIs | `GET/POST /api/apex/gold-era-settlement/status\|run` |

### Behavior

- `STOP_OCR_POLICY`: `ocrExpansionStopped=true`, `writesFromOcr=false`, Patient JPG OCR blocked, PDF remittance yield documented as 0
- Readiness: `GOLD_OK && paymentLines>0` **OR** ERA inbox `fileCount>0` / ingested 835 rows
- Run: optional Gold repair + ERA inbox ingest via existing helpers; **never** PWImages OCR
- `settlement_matrix` still hydrates **only** from Gold `sd_insurance_payment_lines` (ERA readiness ≠ matrix invent)

### Honesty

- empty ≠ $0 · inventedGold=false · softDentWriteBack=false  
- Banner: *UNVERIFIED SCANNED ESTIMATE — DO NOT POST. AWAIT GOLD CSV OR ERA 835 FOR SETTLEMENT TRUTH.*

## Explicitly not done

- Account/Patient JPG deep OCR (rejected runners)
- OCR $ → settlement/Gold
- SoftDent write-back
