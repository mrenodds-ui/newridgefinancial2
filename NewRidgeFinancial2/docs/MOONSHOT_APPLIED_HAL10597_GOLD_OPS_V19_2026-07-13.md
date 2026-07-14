# HAL-10597 / gold-ops-v19-honest (applied)

**Date:** 2026-07-13  
**Prior:** HAL-10589 gold CSV drop OPS; HAL-10596 InsCo×ADA staff catalog  
**Operator:** plan — both phased (gold OPS second)  
**BUILD_ID:** `hal-10597`

## What shipped

| Piece | Location |
|-------|----------|
| Playbook refresh | `gold_csv_drop_playbook()` — v19 Print Preview, visual-audit bridge |
| Widget | `softdent-gold-csv-drop-ops` — `triggersGoldIngest=false`, `excelAvailable=false` |
| OPS runner | existing Print Preview GUI path retained (`attempt_softdent_...`) |
| Tests | `test_hal10597_gold_ops_v19.py` |

## Behavior

- SoftDent v19.1.4: no Insurance Payment Analysis; Excel unavailable → Print Preview only.
- HAL-10590 visual audit records last-page totals only — **does not** create `sd_insurance_payment_lines`.
- Checklist stays `gapCode=GOLD_CSV_MISSING` / `paymentLines=0` until a real CSV appears.
- Real CSV ingest path unchanged (schema verify → repair).

## Honesty

Never invent gold from ledger/DaySheet. Never Printer. Never Esc on SoftDent main. empty ≠ $0.
