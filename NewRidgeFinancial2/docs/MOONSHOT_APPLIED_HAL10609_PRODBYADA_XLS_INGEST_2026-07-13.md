# Moonshot / OPS — PRODBYADA.xls ingest (HAL-10609) APPLIED

**Date:** 2026-07-13  
**Operator:** `proceed` (after `D:\PRODBYADA.xls`)  
**Build package:** `hal-10609`

## Verdict

Ingested SoftDent **Production/Transactions by Code** Excel (`PRODBYADA.xls`) into `production_by_ada` with source tag `softdent_prodbyada_xls:*`. **Not Gold** — `sd_insurance_payment_lines` unchanged (0); `settlementMatrixReady` still requires insurance payment CSV.

## Facts

| Item | Value |
|------|--------|
| Source | `D:\PRODBYADA.xls` |
| Period | **2025-07-13 → 2026-07-13** (1 year) |
| Rows ingested (provider basis) | **171** |
| `production_by_ada` total after | **3002** (Sensei rows kept + tagged XLS) |
| Excel available | **Yes** (unlike Insurance Income) |
| inventedGold | false |
| writesPaymentLines | false |

## Practice GROUP insurance rollups (recon only)

| Code | Description | Amount |
|------|-------------|--------|
| 2 | Insurance Check Payment | $546,778.00 |
| 11.93 | Insurance/Mastercard | $48,193.00 |
| 12.93 | VISA Insurance Payment | $24,584.89 |
| 51 | Insurance Co Write-Off | $552,346.79 |

## Surfaces

- Module: `softdent_prodbyada_xls_ingest.py`
- Sync hook: `import_sync` → `prodByAdaXls`
- API: `GET/POST /api/apex/prodbyada/status|run`
- Menu map: `production_by_ada_code` marked Excel-proven

## Honesty

- SoftDent CODE rollups ≠ InsCo×ADA payment lines
- Do not invent Gold from PRODBYADA
- empty ≠ $0
