# Phase V1 Applied — Synthetic Fixture Validation (Moonshot REAUDIT4 SHOULD)

**Date:** 2026-07-11  
**Build:** hal-10488  
**Consult:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT4_2026-07-11.md`  
**Status:** V1 applied and validated

## Shipped

| Item | Detail |
|------|--------|
| Generator | `test/fixtures/generate_synthetic_nr2.py` |
| Fixtures | quiet MoM (no false positive), noisy MoM (expect alert), synthetic.835 |
| Tests | `test_apex_synthetic_fixtures_v1.py` |

## Known math

- Moonshot doc example: production **$50k** vs payroll **$48.5k** → **3%** gap (<5%)
- Quiet MoM: ~$50k production / ~$15k payroll (realistic share) with tiny MoM → **no** `RECON_VARIANCE`
- Noisy MoM: $50k → $60k production → **alert**
- ERA: X12 without `NM1*QC` patient segments

## Generate fixtures

```text
python NewRidgeFinancial2/test/fixtures/generate_synthetic_nr2.py
python -m pytest NewRidgeFinancial2/test_apex_synthetic_fixtures_v1.py -q
```

## Honesty

Anonymized `SYNTH_*` ids only; empty ≠ $0; no SoftDent write-back.
