# SoftDent Write-Off Code 51 × ADA — Print Preview Notes (HAL-10582)

**Date:** 2026-07-13  
**Operator:** Excel not available for Writeoff Totals → Print Preview only; write-off code is **51** by ADA codes  
**Status:** Evidence / consult follow-through (no invented InsCo×ADA paid estimates)

## Confirmed on live ledger (`sd_account_transactions`)

| Fact | Evidence |
|------|----------|
| Insurance write-off SoftDent code | **`51`** (also `52` reserved in code) |
| Volume | **76,563** rows · **−$4,377,071.27** in `prod_adj` / `amount` |
| ADA on the write-off row? | **No** — `procedure='51'` only; no CDT/ADA on that line |
| Where ADA appears | Charge rows: SoftDent production codes (`1110`, `120`, `274`, `2392`, …) with `prod`/`charges` |
| Same-day 51 + production | Rare (~2%); production usually posts earlier (within ~30 days ~94%) |

Example (Lozano `531901`): charges `180`/`1110`/`801`/`274` on 2026-06-18; later days post **`51`** write-offs and **`2`** insurance payments as **lump** amounts — not one write-off line per ADA.

## SoftDent Print Preview (Writeoff Totals)

- Menu: Reports → Practice Management → Insurance Reports → **Writeoff Totals**
- Output: **Print Preview only** (operator: Excel not usable)
- Layout observed: **CODE · TOTAL · ALLOWED · WRITE-OFFS** (EXPECTED WRITEOFFS section)
- Live preview (07/01/25–07/12/26): EXPECTED WRITEOFFS page showed **$0.00** totals

## Why preview can be $0 while ledger has millions of `51`

Carestream docs: Write-Off Totals **only calculates write-offs posted as code 50.90** from the **Insurance Payment** screen. This practice posts **`51`** on the account ledger. If SoftDent does not map `51` → report “Actual Write-Offs per CODE,” Print Preview stays empty even though NR2 sees large `51` history.

## Implication for InsCo × ADA “what plans pay”

| Path | Status |
|------|--------|
| Ledger `51` alone | Cannot attribute write-off **by ADA** without inventing allocation |
| SoftDent Write-Off Print Preview by CODE | Correct *shape* (CODE/TOTAL/ALLOWED/WRITE-OFFS) if SoftDent posts/report includes those write-offs |
| Insurance Payment Analysis / payment-screen posting (50.90) / ERA SVC | Still required for **paid** + named InsCo × ADA (hal-10400 pipeline; lines still 0) |

## Catalog updates

- `softdent_gui_menu_map.json` / `softdent_master_reports.json`: `writeoff_totals` → `print_preview_only`, `excelExport: false`

## Honesty

empty ≠ $0 · no SoftDent write-back · do not invent per-ADA splits from lump `51` rows · do not invent Ins Plan Register dollars
