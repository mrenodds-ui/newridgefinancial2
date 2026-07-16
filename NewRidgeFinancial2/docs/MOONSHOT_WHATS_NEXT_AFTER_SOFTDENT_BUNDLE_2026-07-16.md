# Moonshot AI — What's Next After SoftDent Morning-Bundle Track (CONSULT ONLY)

**Date:** 2026-07-16
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_whats_next_after_softdent_bundle_consult.py`
**Closed:** SoftDent Print Preview fallback (`b18913e`); Excel still SoftDent-greyed
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> continue

---

# Verdict
Surface the already-generated Trellis full-benefits HTML via a new OM-safe staff link (PHI initials+hash) while leaving SoftDent collections flaky-preview as "acceptable attest_only" until Excel is enabled.

## 0. Operator Intent (verbatim)
continue

## 1. Recommended NEXT
**Package:** Surface Trellis Full-Benefits HTML (OM-safe staff link)  
**Why now:** The LIVE AUDIT shows `reportHtmlHints` with fresh Trellis eligibility HTML files (`trellis_eligibility_report_2026-07-16.html`, etc.) already landed in `app_data/nr2/vyne_pulls/`, but `realModulesExist.trellis_eligibility_report: false` means staff cannot view them. This unblocks immediate value from the ClearCoverage scrape already running on main (c7f658b) without waiting for SoftDent Excel config.  
**Effort:** Small (read-only HTML serve + PHI mask).  
**REAL files under NewRidgeFinancial2/:**
- `trellis/eligibility_server.py` (Flask/Bottle route: `/trellis/benefits/<hash>`)
- `trellis/phi_mask.py` (initials+hash generator, re-use existing `nr2_clean` board logic)
- `static/om_huddle/trellis_benefits_link.js` (optical insert into OM huddle panel, reads `window.NR2_BOARD_HASH`)
- `templates/trellis_eligibility_report.html` (iframe or sanitized HTML embed wrapper)
- Data source: `C:\Users\mreno\newridgefamilyfinancial\app_data\nr2\vyne_pulls\` (read-only, never write-back)

**Validation gate:** Staff clicks "Benefits (Trellis)" in OM huddle → browser opens `/trellis/benefits/<patient_hash>` → sees full benefits HTML with patient name displayed as `J.D. ##a8f3` (initials + 4-char hash) and no raw DOB/SSN; LIVE AUDIT flips `trellis_eligibility_report: true`.

## 2. Ordered backlog AFTER #1
1. **SoftDent Collections Print Preview harden (Practice Management F10)** – Stabilize the flaky collections preview so `morningBundle.failed` drops "collections" and `okCount` becomes 3/3; effort small-polish; only after Trellis surface is live because attest_only is currently acceptable.
2. **SoftDent Excel Enablement Teach / HAL Report-Pull Note** – Operator-facing runbook (not code) documenting the SoftDent config change to enable Excel radio button; include HAL (Human-Assisted Loop) note for manual report pull if Excel remains greyed out; effort documentation only.
3. **Optional QB Stale AP/Payroll Refresh** – Address `datasetGaps` for QuickBooks AP & payroll (2417 min stale); low priority "optional" severity; effort medium (re-auth + ingest pipeline).

## 3. Why this beats the other candidates now
- **vs. SoftDent Excel enablement:** Excel radio is greyed out due to workstation config (SoftDent/Office installation issue), not a code defect; teaching is documentation, not a deliverable package, and cannot be forced until the operator fixes the COM bridge.
- **vs. SoftDent collections harden:** Collections preview is flaky but the system is already in `attest_only` fallback; fixing it is polish that does not unlock new data, whereas surfacing Trellis benefits exposes 27 fresh records (`trellisTomorrow.total`) that are currently invisible.
- **vs. QB stale refresh:** Severity is "optional" and no rows are missing (`rowCount: 0`); Trellis benefits are active patient data with immediate clinical/financial utility.

## 4. What NOT to redo
- OM schedule logic or Trellis huddle PHI panel (already closed in nr2-12070).
- this-patient scoped components.
- PushEngage embeds (must AVOID).
- restart proof (server restart already noted in build notes).
- SoftDent File path (write-back forbidden).
- flip `forceCloseAvailable` on `MATCH` (must stay laser-gated `false`).

## 5. Acceptance criteria
- [ ] `realModulesExist.trellis_eligibility_report` returns `true` in next LIVE AUDIT.
- [ ] Staff link appears in OM huddle only when `trellisTomorrow.hasData: true`.
- [ ] HTML report renders without raw PHI; patient identifiers use `{FirstInitial}{LastInitial} {4-char-hash}` pattern consistent with `nr2-clean` board spec.
- [ ] Route validates `board_hash` against today's session salt; 404 if mismatch.
- [ ] No write operations to SoftDent; no Excel export dependency; Print Preview fallback remains untouched.

## 6. Executive Summary (5 bullets)
- **Gap:** Trellis benefits HTML files exist on disk but lack a staff-facing surface (`trellis_eligibility_report: false`).
- **Fix:** Lightweight read-only server route + OM huddle optical JS to expose existing reports.
- **PHI Guard:** Initials+hash masking aligns with NR2 board standards; no full names or DOB in URL/query params.
- **SoftDent Status:** Remains in `attest_only` until operator enables Excel or collections preview is hardened; no code changes to SoftDent export logic required for this package.
- **Outcome:** Immediate visibility into 27 tomorrow-insurance eligibility checks without blocked dependencies.

## 7. Approval Checklist
- [ ] Confirm `app_data/nr2/vyne_pulls/` path is accessible from NR2 service account.
- [ ] Verify `nr2_clean` hash salt is available to `trellis/phi_mask.py`.
- [ ] Acknowledge SoftDent Excel enablement is operator-side (not in this package).
- [ ] Agree collections harden is #2 priority (post-Trellis surface).
