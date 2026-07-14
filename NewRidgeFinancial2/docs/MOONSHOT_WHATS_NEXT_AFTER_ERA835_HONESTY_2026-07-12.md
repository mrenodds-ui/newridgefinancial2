# Moonshot AI — What's Next After ERA-835 Honesty UX (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10571  
**Prior:** ERA-835 honesty UX (`197efe8` / hal-10571)  
**Script:** `scripts/run_moonshot_whats_next_after_era835_honesty_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Browser smoke validation of hal-10571 ERA-835 honesty UX (ERA_835_REQUIRED gap tile + HAL phrase) alongside widgets NICE and TXN ledger stability after hard-refresh.

## 0. Operator Intent (verbatim: next)
next

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** Browser Smoke — ERA-835 Honesty UX + Widgets NICE + TXN Ledger (hal-10571 hard-refresh validation)  
**Why now:** The ERA-835 honesty UX just shipped (197efe8) introducing `collectionsGapCode=ERA_835_REQUIRED` and new HAL phrasing for SoftDent Register Ins Plan $0.00 truth. Before wiring real file ingest or iterating further, we must verify the gap tile renders correctly, the “do not re-export” hint is legible, and that widgets NICE (hal-10570) and TXN ledger (hal-10569) remain stable after the hardening pack changes. This is the lowest-cost, highest-confidence gate before touching the filesystem inbox.  
**Effort:** Low (single browser session, hard refresh, visual diff of dashboard tiles, console check for 500s).  
**REAL files:**  
- `NewRidgeFinancial2/nr2_hal_gateway.py` (HAL phrase rendering)  
- `NewRidgeFinancial2/apex_softdent_hardening_pack.py` (gap code logic)  
- `NewRidgeFinancial2/apex_better_backend_widgets_pack.py` (widgets NICE)  
- `NewRidgeFinancial2/apex_backend.py` (dashboard tile assembly)  
**Validation gate:**  
- Hard refresh (Ctrl+F5) loads hal-10571 assets without caching stale hal-10570 JS.  
- Dashboard displays `ERA_835_REQUIRED` gap tile with honesty phrase “SoftDent Register Ins Plan Collections $0.00; proceed with ERA-835…”  
- No “Re-export Register” CTA when `registerInsPlanZero=true`.  
- Widgets NICE (pareto, tax-calendar, timeline-lanes) render without JS errors or 500s.  
- TXN ledger loads recent transactions; `eraStub.mode=stub` visible in network trace or debug panel.

## 2. Runner-ups (2–3, why not now)
1. **Wire real ERA-835 inbox ingest (beyond stub)** — Not now because `existingRoots` is empty (no 835 files present yet). Wiring ingest now would test against void; better to confirm UI handles the gap code first so that when files arrive, the display path is proven.  
2. **Collections Summary Excel-temp reliability** — Not now because hal-10571 explicitly instructs the operator *not* to retry Register re-export hoping for Ins Plan > $0. Fixing Excel reliability would contradict the honesty UX directive and encourage the wrong workflow.  
3. **HAL phrase polish / dashboard tile refinement** — Subsumed by the browser smoke; if the smoke reveals phrasing truncation or color contrast issues, polish becomes the follow-up, not the starter.

## 3. What NOT to redo
- ERA-835 Collections Honesty UX logic (gap codes, HAL replies, stub path) — already shipped in hal-10571.  
- Re-export of July Register for Ins Plan > $0 — explicitly prohibited; SoftDent truth is $0.  
- Invention of Insurance/Patient dollar splits from Regular Collections — never permitted.  
- SoftDent write-back of any financial data — out of scope.  
- Widgets MUST/SHOULD/NICE coding — already applied in hal-10570.

## 4. Acceptance criteria
- [ ] Hard refresh (Ctrl+F5) clears browser cache and loads hal-10571 build assets.  
- [ ] Dashboard tile shows `collectionsGapCode: ERA_835_REQUIRED` (not `COLLECTIONS_FORMAT_REQUIRED`).  
- [ ] HAL phrase renders exactly: “SoftDent Register Ins Plan Collections $0.00 is SoftDent truth — proceed with ERA-835 for insurance detail.”  
- [ ] No UI button or link suggesting “Re-export Register to fix Ins Plan.”  
- [ ] Widgets NICE (A/R Aging Pareto, Quarterly Tax Calendar, Claim Status Timeline) render without console errors.  
- [ ] TXN ledger page loads with recent transactions; no regression from hal-10569.  
- [ ] Debug trace shows `eraStub.mode: stub` and `readOnly: true`.  

## 5. Executive Summary (5 bullets)
- **Validate the honesty UX:** Confirm hal-10571 gap tile surfaces correctly when Register Ins Plan = $0.00.  
- **Prevent regression:** Ensure widgets NICE and TXN ledger remain functional after hardening pack insertion.  
- **Cache-bust verification:** Hard refresh proves assets served from 197efe8, not stale hal-10570.  
- **Gate for file ingest:** Once smoke passes, the UI is ready to display real ERA-835 data when files arrive in `C:\SoftDentFinancialExports\era`.  
- **Zero filesystem changes:** Pure browser-side validation; no risk of invented dollars or SoftDent corruption.

## 6. Approval checklist
- [ ] Operator confirms browser smoke takes precedence over wiring empty ERA inboxes.  
- [ ] hal-10571 (197efe8) confirmed deployed to target environment.  
- [ ] Operator has dashboard access and can perform hard refresh.  
- [ ] ERA candidate paths (`C:\SoftDentFinancialExports\era`, `C:\SoftDentReportExports\era`) exist but are expected to be empty (stub mode).  
- [ ] No SoftDent re-export OPS planned during smoke test window.
