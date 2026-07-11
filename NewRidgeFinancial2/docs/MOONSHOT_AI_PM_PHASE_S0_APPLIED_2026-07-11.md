# Phase S0 Applied — QB Payroll / AP automation

**Date:** 2026-07-11  
**Build:** hal-10479  
**Plan:** AI Program Manager SHOULD Wave  
**Prior:** MUST I0–I4 (hal-10475)  
**Status:** Phase S0 validated (shipped in SHOULD wave closeout)

## Shipped

| Item | Detail |
|------|--------|
| Pack | `apex_qb_payroll_pack.py` — SSN redact, payroll/AP gap honesty, widgets |
| Contract | `quickbooks.payroll` / `quickbooks.ap` filenames in `import_contract.py` |
| Loader | Bundle keys `payroll` + `ap` in `import_loader.py` |
| DB | `qb_payroll_rows`, `qb_ap_rows`; snapshot adds `total_payroll` / `total_ap` |
| Sync | `ingest_from_bundle` calls payroll/AP ingest |
| Widgets | `qb-payroll-gap`, `qb-ap-aging` on Financial + QuickBooks |
| HAL | “why is payroll pending”, “show AP aging” |
| Tests | `test_apex_qb_payroll_s0.py` |

## Honesty

- Missing payroll/AP → pending gap codes (not $0)
- Employee SSN patterns redacted to `[REDACTED]` before storage
- Net operating uses payroll only when rows exist (COALESCE 0 for math; `payrollPending` flag when null)

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_qb_payroll_s0.py -q
```

## Next

**S1** ERA harden into unified DB + Collections gap
