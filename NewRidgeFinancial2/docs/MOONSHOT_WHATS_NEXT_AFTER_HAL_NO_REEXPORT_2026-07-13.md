# Moonshot AI — What's Next After HAL No-Reexport Hardening (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10576  
**Prior:** HAL no-reexport hardening applied (`12451bb` / hal-10578)  
**Script:** `scripts/run_moonshot_whats_next_after_hal_no_reexport_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Select **July Production Max-Merge Honesty (hal-10579)** to correct the $949.25 drift between live dashboard production ($45,684.25) and Register truth ($44,735.00), ensuring operators see honest collection ratios while ERA procurement remains blocked.

## 0. Operator Intent (verbatim: next)
next

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** July Production Max-Merge Honesty (hal-10579)

**Why now:**  
The LIVE SNAPSHOT shows `julyDashboardRow.production` at **$45,684.25** while `registerProductionTruth` is **$44,735.00**—a material $949.25 inflation. This drift silently distorts July collection-efficiency metrics (e.g., 67.0% vs. true 68.4%) and risks operator mistrust of the dashboard. With ERA procurement blocked (discovery=0), correcting this data-integrity gap is the highest-leverage defensive fix.

**Effort:** Small (1–2 hours) — surgical max-merge guard; no data migration or SoftDent write-back.

**REAL files:**
- `NewRidgeFinancial2/apex_softdent_hardening_pack.py` (max-merge logic for production across DaySheet/Register/Schedule fragments)
- `NewRidgeFinancial2/nr2_hal_gateway.py` (period assembly & dashboard row construction)
- `app_data/nr2/document_inbox/softdent/softdent_dashboard_data.json` (live dashboard cache target for refresh)

**Validation gate:**
- Post-fix `julyDashboardRow.production` equals `registerProductionTruth` (**44,735.00**).
- New unit test `test_production_max_merge_honesty_hal10579` passes, asserting Register authority over stale CSV/XLS accumulation.
- Dashboard refresh shows **$44,735.00** with gap message unchanged (“Regular Complete · ERA Required”).

## 2. Runner-ups (2–3, why not now)
- **CODE: Wire suggestedAction into gap-tile UI / HAL chips** — Backend already surfaces `era_835_procure` in the gap object and widget text clearly states “ERA Required”; this is UX polish that can follow the data-honesty fix.
- **OPS: Concrete payer-portal / clearinghouse 835 acquisition playbook** — Evidence insufficient; no REAL in-repo docs/paths exist for Delta/MetLife/Availity/SoftDent ERA download menus, and OPS is blocked on real files.
- **CODE: Small unit/integration harden around policy:forbid-register-reexport** — Package 12451bb (hal-10578) just shipped; live snapshot shows no policy hole (forbid flag is true and respected).

## 3. What NOT to redo
- 10578 hardening (HAL no-reexport)
- Regular Collections ingest (fc2f5aa)
- Register re-export for Ins Plan
- Invent Ins/Patient split logic
- Account-tx track
- 10571/10575/10576 specific code
- SoftDent write-back of any kind
- Synthetic 835 generation

## 4. Acceptance criteria
- [ ] `julyDashboardRow.production` aligns to `registerProductionTruth` (44,735.00) after cache refresh.
- [ ] Max-merge logic prioritizes Register production when SoftDent export root contains `REG202607.XLS`.
- [ ] Stale CSV/XLS fragments cannot inflate production above Register authority.
- [ ] Gap assessment (`ERA_835_REQUIRED`) and Regular Collections ($30,626.42) remain untouched.
- [ ] Unit test `test_production_max_merge_honesty_hal10579` PASS.

## 5. Executive Summary (5 bullets)
- **Drift detected:** Dashboard shows $45,684 production vs. Register truth $44,735 (~$949 variance).
- **Risk:** Misstated collection ratios could skew performance reviews and financial planning.
- **Root:** Max-merge accumulation likely pulling stale/overlapping CSV/XLS fragments alongside Register.
- **Fix:** Harden merge logic to treat Register as authoritative for July 2026 production; additive code change only.
- **Outcome:** Honest production metric preserves operator trust while awaiting real ERA-835 procurement.

## 6. Approval checklist
- [ ] Operator confirms the $949 production delta is unintended and Register should be authority.
- [ ] Developer access confirmed to `apex_softdent_hardening_pack.py` and `nr2_hal_gateway.py`.
- [ ] Staging plan includes dashboard cache refresh (`softdent_dashboard_data.json` rebuild).
- [ ] No objection to deferring UI wiring of `suggestedAction` chips until data accuracy is restored.
- [ ] QA sign-off on production alignment before next “next” request.
