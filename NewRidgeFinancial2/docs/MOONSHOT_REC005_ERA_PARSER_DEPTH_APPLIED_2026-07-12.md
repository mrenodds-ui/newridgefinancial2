# Moonshot REC-005 ERA Parser Depth — APPLIED

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_REC009_2026-07-12.md`  
**Operator:** proceed (typo: ptceed)  

## Goal

Deepen ERA 835 Loop 2100/2110 parsing: service-line paid/charge, CAS (CARC) at claim and SVC scope, LQ remark codes (RARC), denial flags, and a HAL remittance summary that does not invent dollars or PHI.

## Applied (real paths — not fictional `apex_era.py`)

| Piece | Where |
|-------|--------|
| Loop 2110 `serviceLines` + claim/line `casCodes`/`casDetails` + `rarcCodes` + `denialFlag` | `era835_parser.py` |
| `summarize_835_for_hal` (patient names omitted) | `era835_parser.py` |
| Ingest stores service lines / RARC / denialFlag; attaches `remittanceSummary` | `apex_program_improve_pack.py` |
| Aggregate CAS labels as `CO-45` | `apex_era835_pack.py` |
| `POST /api/apex/claims/era-summary` | `apex_backend.py` |
| Tests | `test_rec005_era_parser_depth.py` (+ U1 CO-45 assert) |

## Honesty

- Empty ≠ $0 — summary uses `missing` when amounts absent  
- No SoftDent write-back  
- Patient NM1*QC not included in HAL summary text  

## Validate

1. `python -m pytest test_rec005_era_parser_depth.py test_apex_era835_u1.py -q`  
2. Upload sample 835 via Claims ERA ingest → matches include `serviceLines`  
3. `POST /api/apex/claims/era-summary` with EDI body → structured CAS/RARC lines  
