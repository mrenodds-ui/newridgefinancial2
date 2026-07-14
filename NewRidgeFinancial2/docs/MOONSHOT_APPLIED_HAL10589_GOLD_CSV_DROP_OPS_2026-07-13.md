# HAL-10589 / OPS-10589 — SoftDent Gold CSV Drop Facilitation & Ingest Verification (applied)

**Date:** 2026-07-13  
**Prior consult:** `MOONSHOT_WHATS_NEXT_AFTER_HAL10588_2026-07-13.md`  
**Operator:** `proceed`  
**BUILD_ID:** `hal-10589`

## What shipped

| Piece | Location |
|-------|----------|
| OPS module | `softdent_gold_csv_drop_ops.py` — playbook, schema verify, pre/post checklist, GUI attempt, Sync-safe run |
| SoftDent menu map | `insurance_payment_analysis` → **Insurance Income** (+ alts) |
| GUI paths | `softdent_gui_export.py` win32 candidates for Insurance Income / Contractual Plan Analysis / Payment Allocation |
| Widget | `softdent-gold-csv-drop-ops` |
| API | `GET /api/apex/gold-csv-drop-ops/status`, `POST .../run` |
| HAL | `policy:gold-csv-drop-ops` |
| Sync hook | `import_sync.py` → `run_ops_10589_gold_csv_drop(attempt_gui_export=False)` |
| Tests | `test_gold_csv_drop_ops_hal10589.py` (4 OK) |
| Checklist report | `C:\SoftDentFinancialExports\gold_csv_drop_ops_checklist_*.{json,md}` |

## SoftDent discovery (honest)

Live SoftDent **v19.1.4** menu probe found **no** item named **Insurance Payment Analysis**.

Closest real menus:

1. **Reports → Practice Management → Insurance Reports → Insurance Income** (primary) — F10 `r m i i`
2. **… → Contractual Plan Analysis** — F10 `r m i a`
3. **… → Production Reports → Payment Allocation** — F10 `r m p p`
4. **Reports → Accounting → Insurance Payment Distribution** — F10 `r a i`

**Output mode (operator):** Excel is **not available** → **Print Preview only** (click Print Preview → Enter → **Next/PageDown** through pages as needed → **last page** for totals). Page 1 alone is often incomplete. Never Printer.

## Live OPS result

| Check | Result |
|-------|--------|
| gapCode | `GOLD_CSV_MISSING` |
| paymentLines | `0` (empty ≠ $0) |
| Exact spine | 46 checked / 46 pass / 0 flag |
| Output path | **Print Preview only** (Excel unavailable) |
| Gold CSV ingest | **Not produced** by Print Preview — visual totals only; do not invent line items |

## Operator unblock (manual)

1. SoftDent foreground, signed on.  
2. **Reports → Practice Management → Insurance Reports → Insurance Income**.  
3. Output Options: **Print Preview** only (Excel not available; never Printer).  
4. Page through with **Next / PageDown** for detail; go to the **last page** for exact totals (page 1 alone is incomplete).  
5. Checklist Sync records preview OPS status; `sd_insurance_payment_lines` stays 0 until a real line-item file exists elsewhere (empty ≠ $0).

## Honesty

No SoftDent write-back. No invented gold from ledger/DaySheet. Print Preview ≠ CSV gold lines. Missing file remains empty, not `$0.00`.
