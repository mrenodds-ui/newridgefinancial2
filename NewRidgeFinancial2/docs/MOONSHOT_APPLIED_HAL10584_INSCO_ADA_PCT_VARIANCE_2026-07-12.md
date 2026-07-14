# HAL-10584 — InsCo × ADA pay/write-off % +/- variance (applied)

**Date:** 2026-07-12  
**Operator request:** Use ~5 years of patient transactional history with the same insurance; for every ADA, pair SoftDent codes **2** (Ins payment) and **51** (write-off) next to those production codes; extrapolate what each insurance company pays and writes off **by percentage**, with **+/- variance**.

## What shipped

| Piece | Location |
|-------|----------|
| Builder + export | `softdent_insco_ada_pct_variance.py` |
| Sync hook | `import_sync.py` → `inscoAdaPctVariance` |
| APIs | `GET /api/apex/insco-ada-pct-variance/status`, `.../lookup` |
| HAL intent | `policy:insco-ada-pct-variance` in `nr2_hal_gateway.py` |
| Tests | `test_insco_ada_pct_variance_hal10584.py` |
| Live report | `C:\SoftDentFinancialExports\insco_ada_pct_variance_report_2026-07-12.{json,md}` |
| Inbox | `app_data/nr2/document_inbox/softdent/softdent_insco_ada_pct_variance.json` |

## Method (honest)

1. Restrict to accounts with primary carrier from `sd_patient_insurance` (Sensei coverage).
2. Walk `sd_account_transactions` for the last **5 years**.
3. **Episode:** production ADA cluster → forward SoftDent **2** / **51** (and 52) within **60 days** or until the next production charge.
4. **Exact:** one ADA in the cluster. **Inferred:** multi-ADA → allocate 2/51 by billed share (labeled).
5. Skip episodes where pay+WO > 1.25× billed (mis-paired lump payments).
6. Per InsCo × ADA × tier: median/mean pay% and WO% of billed; **+/- = 1 population SD**.
7. Publish floors: exact n≥10 (high n≥30); reject medians outside roughly **-5%..120%**.
8. empty ≠ $0; not SoftDent contractual line truth; no SoftDent write-back.

## Live snapshot (2026-07-12 rebuild)

- Period: **2021-07-13 .. 2026-07-12**
- Episodes: **13,320** (exact 2,396 · inferred 10,924 · skipped overpay 923)
- Exact published cells: **46** · all incl. inferred: **365**

Example exact (median +/- SD):

| Carrier | ADA | n | Pay% | WO% |
|---------|-----|---|------|-----|
| DELTA DENTAL OF KS | D2392 | 172 | 45.87 +/-14.59 | 23.63 +/-5.91 |
| DELTA DENTAL OF KS | D1110 | 35 | 80.95 +/-11.50 | 19.52 +/-11.32 |
| METLIFE DENTAL | D2391 | 77 | 24.87 +/-12.78 | 41.03 +/-9.50 |

## Related

- HAL-10582/83: dollar averages (same ledger pairing family)
- Gold path (`sd_insurance_payment_lines`) still empty until Insurance Payment Analysis lands
