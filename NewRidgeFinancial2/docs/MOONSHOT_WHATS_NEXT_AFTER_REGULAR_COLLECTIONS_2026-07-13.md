# Moonshot AI — What's Next After Regular Collections DEF-001 (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10576  
**Prior:** Regular Collections DEF-001 applied (`fc2f5aa`)  
**Script:** `scripts/run_moonshot_whats_next_after_regular_collections_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Evidence insufficient for specific payer-portal playbook (no Delta/MetLife/Availity/SoftDent ERA menu docs in-repo); selecting defensive HAL hardening to prevent Register re-export drift while procurement waits.

## 0. Operator Intent (verbatim: next)
next

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** HAL Policy Hardening — Prevent Register Re-export for Ins Plan (hal-10578)

**Why now:**  
Regular Collections DEF-001 just shipped, establishing Ins Plan=$0.00 as ground truth. The widget currently shows the correct terminal state ("Regular Complete · ERA Required"), but the HAL policy must be explicitly hardened to ensure no future drift or operator confusion triggers a Register re-export hoping for Ins Plan > 0. This is a defensive additive fix while OPS is blocked on real ERA-835 procurement (discovery=0).

**Effort:** Small (1–2 hours) — policy guard insertion, no data migration.

**REAL files:**
- `NewRidgeFinancial2/nr2_hal_gateway.py` (policy routing)
- `NewRidgeFinancial2/apex_softdent_hardening_pack.py` (gap/widget logic)
- `NewRidgeFinancial2/apex_era835_pack.py` (ERA-required state constants)
- `app_data/nr2/document_inbox/softdent/softdent_dashboard_data.json` (live state validation)

**Validation gate:**  
HAL response for July 2026 returns `collectionsGapCode: "ERA_835_REQUIRED"` and explicitly excludes `suggestedAction: "re_export_register"` or similar; unit test `test_hal_no_register_reexport_suggestion_hal10578` passes; operator cannot trigger Register re-export from gap tile.

## 2. Runner-ups (2–3, why not now)
- **OPS: Concrete payer-portal / clearinghouse 835 acquisition playbook** — Highest leverage in principle, but evidence insufficient: no REAL repo docs/paths exist for Delta/MetLife/Availity/SoftDent ERA menu procedures in the provided file tree. Procurement steps must be staffed with real payer portal screenshots/SOPs before this package can ship.
- **OPS: Real QuickBooks payroll/AP export drop** — Valid business need, but lower priority than ensuring the collections reconciliation path is hardened against accidental re-export while ERA procurement proceeds.
- **CODE: Browser smoke for Regular-complete + ERA-required gap tile** — Conditional on existence of real smoke harness (e.g., Selenium/Playwright specs in-repo); no such harness evidenced in provided paths.

## 3. What NOT to redo
- Regular Collections ingest (DEF-001 just shipped; patient=$30,626.42 confirmed).
- Re-exporting SoftDent Register hoping Ins Plan > 0 (July OPS confirmed Ins Plan Collections = $0.00 is ground truth).
- Re-ingesting Regular Collections via stale CSV or XLS (max-merge logic prevents clobbering).
- Inventing Ins/Patient splits without ERA-835 files.
- Synthetic 835 creation or SoftDent write-back.

## 4. Acceptance criteria
- [ ] HAL policy explicitly forbids `suggestedAction: "re_export_register"` when `registerInsPlanZero: true` and `regularCollectionsReported: true`.
- [ ] Gap tile message remains stable: "Regular Collections: Complete ($30,626.42) · Insurance Collections: ERA Required".
- [ ] Unit test verifies no re-export suggestion in HAL response for July 2026.
- [ ] No changes to `C:\SoftDentReportExports\REG202607.XLS` or SoftDent system.
- [ ] Documentation update: `MOONSHOT_HAL_HARDENING_NO_REEXPORT_HAL10578.md`.

## 5. Executive Summary (5 bullets)
- Regular Collections DEF-001 is live; patient=$30,626.42, Ins Plan=$0.00 is locked truth.
- ERA procurement is the only remaining blocker; discovery shows 0 local files.
- Specific payer-portal playbook cannot ship without real Delta/MetLife/Availity/SoftDent SOPs in-repo.
- Defensive HAL hardening prevents accidental Register re-export while operators wait for 835s.
- Next actionable package is policy code, not data re-processing or fictional procurement steps.

## 6. Approval checklist
- [ ] Operator confirms no existing HAL smoke harness exists (Candidate 2 invalid).
- [ ] Operator confirms production alignment with Register (Candidate 3 unnecessary).
- [ ] Operator confirms Ins Plan remains $0.00 (no re-export needed).
- [ ] Assignee identified for payer-portal SOP staffing (future Candidate 1 prerequisite).
