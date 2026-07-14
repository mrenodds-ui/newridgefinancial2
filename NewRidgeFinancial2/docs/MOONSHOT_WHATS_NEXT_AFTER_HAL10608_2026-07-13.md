# Moonshot AI — What's Next After HAL-10608 (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10608  
**Script:** `scripts/run_moonshot_whats_next_after_hal10608_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> next

---

# Verdict
OPS: SoftDent Gold CSV drop — procure and land the Insurance Payment Analysis line-item CSV to unblock HAL-10605/10608 settlement matrix hydration.

## 0. Operator Intent (verbatim)
next

## 1. Confirmation of HAL-10608 apply (pass/fail; residual risks)
**PASS** — Surface shipped correctly: `ocrExpansionStopped=true`, `writesFromOcr=false`, `settlement_matrix` hydrates only from Gold CSV, ERA inbox tooling wired but idle.  
**Residual risk:** Readiness reports `true` via ERA lane while `eraFileCount=0` and `paymentLines=0`; this creates a "ghost ready" state that masks the critical Gold lane gap. Gold CSV absence remains the sole blocker to matrix hydration.

## 2. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**OPS: SoftDent Gold CSV drop (HAL-10606 completion)**  
- **Why now:** HAL-10605/10606/10608 infrastructure is live and awaiting only this file. Zero code risk. Immediate unlock of settlement truth (`paymentLines>0` → matrix hydration). Without this, 10608 remains an empty vessel.  
- **Effort:** Staff OPS (30–60 min to locate line-item export in SoftDent v19 or request from SoftDent support; Print Preview summaries are insufficient).  
- **REAL files:** `insurance_payments_YYYYMMDD.csv` containing line-item insurance payment detail (claim-level allocations, not summary) dropped into `C:\SoftDentFinancialExports\` → Sync → `POST /api/apex/gold-era-settlement/run`.  
- **Validation gate:** `paymentLines > 0`, `matrixCells > 0`, `acceptanceGateMet = true`, `inventedGold = false`, `gapGold = null`.

## 3. Why this beats other candidates now
- **ERA 835 drop (Candidate 2):** Valid alternate lane, but Gold is the primary prepared path (HAL-10605/10606 specifically engineered for it). ERA can follow once Gold proves the settlement pipeline end-to-end.  
- **TP UI chip (Candidate 3):** Surfaces "no data" truth but does not unblock settlement; cosmetic without the underlying Gold CSV.  
- **Coventry MEDIUM (Candidate 4):** Narrow carrier fix without foundation data; premature until Gold establishes baseline dollars.  
- **Code candidates (5–7):** Build views or estimations without the dollar truth Gold provides; violates "prefer OPS when only missing input is real file."

## 4. Runner-ups (2–3)
1. **OPS: ERA 835 first real drop** — Alternate lane if SoftDent v19 proves incapable of exporting line-item Insurance Payment Analysis CSV (fallback to 835 inbox ingest).  
2. **CODE: TP UI chip** — Surface `viaGold` / `viaAlias` / `pending` / `insufficient` states for staff transparency after Gold drop (post-hydration UX).  
3. **OPS: Coventry MEDIUM pending accept/reject** — Only after Gold CSV establishes payment baseline to compare against Coventry estimates.

## 5. What NOT to redo
- SoftDent write-back to production ledger.  
- Invent gold from DaySheet, Print Preview, or PWImages OCR (HAL-10608 STOP policy).  
- Force-match rejected carrier aliases (75 pending) without Gold evidence.  
- Rebuild HAL-10588–10608 greenfield (build ON them, not replace).  
- Additional PWImages JPEG/PDF OCR for settlement (explicitly stopped per 10608).

## 6. Acceptance criteria
- [ ] File `insurance_payments_*.csv` present in `C:\SoftDentFinancialExports\` with line-item claim/payment allocations.  
- [ ] Sync completes without OCR fallback or invented dollar injection.  
- [ ] `paymentLines` count > 0 in `sd_insurance_payment_lines`.  
- [ ] `settlement_matrix` hydrates with >0 cells linked to real payment lines.  
- [ ] `goldEra.acceptanceGateMet` = true.  
- [ ] `inventedGold` flag remains false; `empty ≠ $0` preserved.  
- [ ] No SoftDent write-back attempted.

## 7. Executive Summary (5 bullets)
- HAL-10608 surface is live but empty (`paymentLines=0`, `matrixCells=0`).  
- Gold CSV is the sole missing keystone to unlock settlement truth without inventing data.  
- OPS-only package: procure real line-item export from SoftDent v19 (staff action, zero dev).  
- Unblocks HAL-10605 matrix hydration immediately upon file drop.  
- ERA lane remains valid alternate, but Gold is the prepared primary path.

## 8. Approval checklist
- [ ] Staff briefed: SoftDent v19 "Insurance Income" Print Preview ≠ Gold; need line-item CSV export (or SoftDent support request).  
- [ ] Export path `C:\SoftDentFinancialExports\` writable verified (HAL-10606).  
- [ ] CSV drop scheduled within 24h.  
- [ ] Validation gate criteria understood and measurable.