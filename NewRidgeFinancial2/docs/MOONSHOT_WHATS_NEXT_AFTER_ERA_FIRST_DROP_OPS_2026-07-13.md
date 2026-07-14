# Moonshot AI — What's Next After ERA-835 First Drop OPS (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10573  
**Prior:** ERA first drop OPS attempt 2 blocked (`e5a4fbd`)  
**Script:** `scripts/run_moonshot_whats_next_after_era_first_drop_ops_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Wire the browser mutation-token path so staff can trigger ERA inbox ingest from the Apex UI without a raw POST 403, unblocking the manual ingest workflow while real payer files remain pending.

## 0. Operator Intent (verbatim: next)
next

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** UI Mutation-Token Wiring for ERA Inbox Ingest (hal-10574)

**Why now:** OPS has failed twice to procure real ERA-835 files due to external clearinghouse delays. The backend ingest pipeline (`ingest_era_inbox`) is fully operational and the helper script `scripts/run_era_inbox_ingest_ops.py` works locally, but the browser UI returns 403 on POST `/api/apex/hal/era-inbox/ingest` because the mutation-token/CORS gate blocks unauthenticated requests. Enabling a staff-facing UI ingest button (with proper token validation) allows immediate validation of the pipeline the moment files arrive, without requiring staff to run Python scripts or wait for the next OPS cycle.

**Effort:** Small additive code change (~2 files: `nr2_browser_security.py` for token validation logic, `nr2_hal_gateway.py` or `apex_backend.py` for the wired endpoint, plus minor UI hook in `site/index.html`).

**REAL files:** None. This is a CODE package to fix the browser security gate; no SoftDent export or payer files required.

**Validation gate:** 
1. Staff opens Apex UI in browser, sees ERA inbox chip "Awaiting first 835 drop"
2. Staff clicks "Scan & Ingest Now" button (or equivalent chip action)
3. Browser POST succeeds (200 not 403), mutation token validated
4. `ingest_era_inbox()` executes, returns `{"ok": true, "ingested": [], "honesty": "empty_not_zero"}` (since inbox still empty)
5. Chip updates briefly to "Processing" then returns to "Awaiting first 835 drop" with timestamp
6. No SoftDent write-back occurs; `writeBack: false` confirmed in response

## 2. Runner-ups (2–3, why not now)
**OPS: Third ERA-835 Procurement Attempt** — Demoted from primary because the first two attempts established that files are not available on the workstation or clearinghouse portals yet. Repeating the same guidance without new evidence of file arrival is low leverage compared to unblocking the UI path.

**Browser Smoke: hal-10573 Gap Tile Regression** — Lower priority than the 403 unblock. The gap tile and chip are already verified as displaying correctly; a regression test can be bundled with the mutation-token work rather than standing alone.

**OPS: QuickBooks Payroll/AP Export Drop** — While valuable for cash reconciliation, it does not address the immediate `ERA_835_REQUIRED` blocker that is preventing insurance collections from appearing in the ledger.

## 3. What NOT to redo
- ERA inbox scan/ingest wiring (`scan_era_inbox`, `ingest_era_inbox` — already shipped in hal-10573)
- Gap-tile honesty labels (`ERA_835_REQUIRED` display logic — shipped hal-10572)
- Import Dataset Hygiene (shipped prior)
- ERA honesty UX (`empty_not_zero` gates — shipped hal-10571)
- Browser smoke of hal-10571/10572 widgets
- TXN ledger wiring (already live)
- Inventing Ins/Patient splits without 835 data
- SoftDent Register re-export (forbidden; Register shows $0 truth)
- Synthetic 835 fixtures as production truth (forbidden)
- SoftDent write-back of invented dollars (forbidden)

## 4. Acceptance criteria
- [ ] `nr2_browser_security.py` exposes a validated mutation-token check that permits POST `/api/apex/hal/era-inbox/ingest` from the same-origin UI session
- [ ] `nr2_hal_gateway.py` (or `apex_backend.py`) wires the token validation into the ingest handler
- [ ] `site/index.html` renders an "Ingest ERA Inbox" action (button or chip click) that acquires the token and POSTs correctly
- [ ] Empty inbox ingest via UI returns `{"ok": true, "ingested": [], "honesty": "empty_not_zero", "writeBack": false}` without 403
- [ ] Staff can trigger ingest without running `scripts/run_era_inbox_ingest_ops.py` manually
- [ ] No change to `C:\SoftDentFinancialExports\era` directory permissions or structure
- [ ] No synthetic dollars posted to SoftDent or unified DB

## 5. Executive Summary (5 bullets)
- OPS blocked twice on real payer 835 files; inbox remains empty with `honesty: empty_not_zero`
- Current browser POST returns 403 due to missing mutation-token path, forcing staff to use Python scripts
- Package wires UI token validation to enable click-to-ingest from the browser
- Keeps all existing honesty gates intact; no dollars invented, no SoftDent write-back
- Unblocks immediate staff validation when files eventually arrive, without waiting for next Moonshot consult

## 6. Approval checklist
- [ ] Confirm no production 835 files have arrived in `C:\SoftDentFinancialExports\era` since last check
- [ ] Confirm mutation-token approach aligns with existing `nr2_browser_security.py` patterns (CSRF or JWT)
- [ ] Confirm UI placement for ingest trigger (chip click vs dedicated button)
- [ ] Confirm rollback plan: revert token requirement to restore 403 if needed
- [ ] Verify staff training: UI ingest is for convenience; `scripts/run_era_inbox_ingest_ops.py` remains valid fallback
