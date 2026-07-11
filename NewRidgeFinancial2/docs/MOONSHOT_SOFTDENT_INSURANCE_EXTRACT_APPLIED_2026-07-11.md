# SoftDent Insurance Extract for Dossier Availity — Applied

**Date:** 2026-07-11  
**Build:** **hal-10498**  
**Consult:** `MOONSHOT_SOFTDENT_INSURANCE_EXTRACT_CONSULT_2026-07-11.md`  
**Status:** Applied after operator selected next → **1** (apply consult)

## Shipped checklist

| Priority | Item | Status | Where |
|----------|------|--------|-------|
| **MUST** | `sd_patient_insurance` schema | Done | `softdent_odbc_extract.ensure_sd_schema` |
| **MUST** | `SD_TABLES` includes insurance | Done | `softdent_odbc_extract.SD_TABLES` |
| **MUST** | ODBC discovery helper | Done | `discover_insurance_tables` |
| **MUST** | `extract_patient_insurance` honest NULLs | Done | wired in `_populate_from_odbc` |
| **SHOULD** | Secondary coverage (`priority`) | Done | PRI/SEC/TER mapping + CSV Priority |
| **SHOULD** | CSV fallback | Done | `load_insurance_csv` + `SOFTDENT_INSURANCE_CSV_PATH` |
| **SHOULD** | `sd_carrier_payer_map` | Done | lookup when EDI/payer_id missing |
| **NICE** | Termination-date filter | Done | `_termination_still_active` |
| **NICE** | Relationship code normalize | Done | `_normalize_relationship_code` |
| **NICE** | Overnight eligibility pre-fetch | Deferred | Per consult |

## Honesty

- SoftDent **READ-ONLY** (ODBC SELECT only)
- Empty member/payer → SQL **NULL** (never invent IDs)
- Extract failure does **not** fail full SoftDent sync
- Dossier: if carrier name present but member id null → explicit message

## Operator setup

1. Optionally set `SOFTDENT_ODBC_INSURANCE_QUERY` after discovery (default targets `PATIENT`/`PAT_INS`/`CARRIER`).
2. Or drop `patient_insurance_YYYYMMDD.csv` under SoftDentFinancialExports / set `SOFTDENT_INSURANCE_CSV_PATH`.
3. Map SoftDent carrier → Availity payer via `upsert_carrier_payer_map` / `sd_carrier_payer_map` when EDI code missing.
4. Keep `NR2_PROVIDER_NPI` set for Availity.

## Tests

`python -m unittest test_softdent_odbc_extract test_patient_dossier -q`
