# SoftDent July Register Ins Plan OPS — RESULT (honesty)

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_COVERAGE_CHIP_2026-07-13.md`  
**Operator:** proceed  
**Status:** SoftDent desktop export completed; **Ins Plan Collections = $0.00** (ground truth — not invented)

## What ran

SoftDent signed on (`COMPUTE`) → Reports → Accounting → Registers → Period → Excel  
Range: **07/01/26–07/12/26** via `scripts/automate_softdent_register_period_export.py`

## Output files

| File | Bytes |
|------|-------|
| `C:\SoftDentReportExports\register_for_period_2026-07-01_2026-07-12.xls` | 28,672 |
| `C:\SoftDentReportExports\REG202607.XLS` | 28,672 (copy) |

## SoftDent totals (read from export — empty ≠ invent)

| Line | Amount |
|------|--------|
| Productions | 44,735.00 |
| Net Productions | 26,025.09 |
| Collections / Net Collections | **30,626.42** |
| Ins Plan Collections | **0.00** |
| Regular Collections | **30,626.42** |
| Patients Seen | 114 |

## Conclusion

Re-export does **not** create Ins Plan > 0. SoftDent Register attributes all July collections to **Regular**, not Ins Plan. Insurance detail still requires real **ERA-835** files (`ERA_835_REQUIRED`). Do not invent an Ins/Patient split.

## Not done

- Inventing Ins Plan dollars  
- SoftDent write-back  
- Claiming month-end insurance truth without ERA  
