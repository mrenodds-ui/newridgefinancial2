# SoftDent morning bundle — TRACK COMPLETE (Excel disabled → Print Preview)

**Date:** 2026-07-16  
**Operator:** continue with all until done  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_RESTART_PROOF_2026-07-16.md`

## Root cause (live SoftDent Output Options)

| Option | Enabled |
|--------|---------|
| Printer | yes (forbidden) |
| File | yes (**forbidden** per operator) |
| Excel | **no** (greyed out even with Excel 16 COM running) |
| Print Preview | yes (**allowed**) |

Excel is installed at `C:\Program Files (x86)\Microsoft Office\root\Office16\EXCEL.EXE` but SoftDent will not enable the Excel radio. Money-beam Excel ingest cannot complete until SoftDent Excel export is enabled in SoftDent itself.

## Shipped this pass

| Item | Status |
|------|--------|
| Never File / never Printer on Output Options | **DONE** (`c6d3e9f` + hardenings) |
| Minimize Claim Management / Explorer / Notepad thieves | **DONE** |
| `SoftDentExcelDisabledError` → Print Preview fallback | **DONE** |
| Aging Print Preview rehearsal | **OK** (`previewOk=true`, `moneyBeamIngest=false`) |
| Register Print Preview rehearsal | **OK** |
| Collections Print Preview | **FAIL** (Output Options click flaky under Practice Management) |
| Money beams / `morningBundle.ok` for Excel aging | **Blocked** — SoftDent Excel greyed out; `attest_only` + empty ≠ `$0` |

## Operator action to unlock Excel money beams

1. In SoftDent, enable Excel export for reports (SoftDent config / Carestream support — NR2 cannot invent Excel when SoftDent greys it out).
2. Confirm Output Options shows **Excel** enabled (not File).
3. Re-run morning bundle; aging Excel drop → `morningBundle.ok=true`.

## Explicitly skipped

- Classic Apex 2B
- Flip `forceCloseAvailable` on MATCH
- Using Output Options **File**

**Track closed** for code + Print Preview path. Excel money ingest waits on SoftDent Excel option.
