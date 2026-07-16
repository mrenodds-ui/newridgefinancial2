# Do-all-next after nr2-12072 consult — APPLIED

**Date:** 2026-07-16  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_12072_CONTINUE_2026-07-16.md`  
**Operator:** do all next  
**Build:** `nr2-12073-excel-gate-all-next`

## Package 1 — SoftDent Excel enablement runbook + morning-bundle gate

| Piece | Status |
|-------|--------|
| `docs/runbooks/softdent_excel_enablement_nr2.md` | Shipped |
| HAL `policy:softdent-report-pull` points at runbook | Shipped |
| `softdent_export_morning_bundle.excelEnablementGate` / `.excelEnablementRunbook` | Shipped |
| `period_close_status.morningBundle` surfaces gate | Shipped |
| Attended SoftDent Excel money-bundle re-run | **Gated** — SoftDent still greys Excel; refuse invent paths/dollars |

**Operator leftover:** Enable SoftDent Output Options **Excel**, then say **approve** for attended morning bundle. Until then `morningBundle.ok` stays false / `attest_only`. `forceCloseAvailable` stays laser-gated.

## Package 2 — Trellis withBenefits AM proof (monitor tonight scrape)

| Piece | Status |
|-------|--------|
| `scripts/prove_trellis_withbenefits_am.py` | Shipped |
| Live now | `withBenefits=0` / status-only (honest until 10:10 PM ClearCoverage) |

Tomorrow AM: `python scripts/prove_trellis_withbenefits_am.py` → exit 0 when `withBenefits>0`. Counts only — no $ invent.

## Package 3 — Optional QB AP/payroll inbox checklist

| Piece | Status |
|-------|--------|
| `docs/runbooks/qb_ap_payroll_inbox_drop_nr2.md` | Shipped |
| Real ingest paths already on main (`apex_qb_export_inbox_pack`, `import_sync`) | Unchanged |

Staff drop CSVs when available. Does not block Force Close.

## Package 4 — Classic Apex 2B

**Deferred** — optional and premature while SoftDent Excel money beams remain blocked.

## Explicitly not done

- Invent SoftDent Excel / Select File Name directories
- Flip `forceCloseAvailable` on GREEN+MATCH
- Invent Trellis deductible/$ or QB AP/payroll rows
- Redo Preview Date Wizard / Trellis HTML / OM schedule

## Tests

`test_softdent_excel_enablement` + existing SoftDent/Trellis unit suite.
