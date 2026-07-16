# SoftDent Excel enablement runbook + morning-bundle gate — APPLIED

**Date:** 2026-07-16  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_12072_CONTINUE_2026-07-16.md`  
**Operator:** approve  
**Package:** SoftDent Excel enablement runbook + attended morning-bundle re-run gate

## Shipped

| Item | Path / result |
|------|----------------|
| Operator runbook | [`docs/runbooks/softdent_excel_enablement_nr2.md`](runbooks/softdent_excel_enablement_nr2.md) |
| Attended re-run log | `.local_logs/morning_bundle_excel_gate_2026-07-16.json` |

## Attended gate result (~232s)

Prep: minimized NR2 Optical Bench Chrome; SoftDent focused and signed on.

| Report | Result |
|--------|--------|
| aging | `excelDisabled=true` → Preview path; `print_preview_not_open` |
| register | Output Options closed unexpectedly |
| collections | `excelDisabled=true` → Preview path; `print_preview_not_open` |

Bundle summary:

- `ok=false` · `error=softdent_excel_disabled`
- `paths=[]` · `emptyNotZero=true`
- **No invented directories / Excel drops / `$0`**

SoftDent Output Options still has **Excel greyed out** on this workstation. Runbook documents how the operator/IT enables Excel and keeps SoftDent’s own save folder (never type `C:\SoftDentReportExports` into SoftDent).

## Validation vs consult

| Criterion | Status |
|-----------|--------|
| Runbook at `docs/runbooks/softdent_excel_enablement_nr2.md` | **Done** |
| Attended morningBundle re-run | **Done** (honest fail) |
| `morningBundle.ok=true` | **Not met** — SoftDent Excel still disabled |
| `forceCloseAvailable` not flipped | **Honored** |
| No invent dirs / File / Printer | **Honored** |

## Operator leftover

1. Follow the runbook: enable SoftDent **Excel** on Output Options (Carestream/office install).
2. Once Excel is clickable, say **approve** again for another attended money-bundle run.
3. Tonight 10:10 PM Trellis verify still fills ClearCoverage benefits independently.
