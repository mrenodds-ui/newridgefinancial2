# Moonshot AI — What's Next After HAL-10590 Print Preview Visual Audit (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10590  
**Prior:** HAL-10590 Print Preview visual-audit (`3822665`)  
**Script:** `scripts/run_moonshot_whats_next_after_hal10590_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> next

---

# Verdict (one sentence — THE next package)
**HON-001 — Empty≠$0 Programmatic UI Enforcement Audit**: a defensive, HAL-policy-driven validation layer that guarantees no Apex/SoftDent widget can render null, missing, or visual-audit aggregates as `$0.00`, specifically protecting against conflation of the new Print Preview visual totals (HAL-10590) with empty gold payment lines.

## 0. Operator Intent (verbatim)
next

## 1. Recommended NEXT (name, why now, effort, REAL files/ops steps, validation gate)
**Name:** HON-001 / HAL-10591 — Empty≠$0 Programmatic UI Enforcement Audit  
**Why now:** HAL-10590 introduced real visual-audit aggregates (e.g., `lastPageAggregateTotal: 1.0`) while gold CSV remains blocked (`paymentLines: 0`). This creates a high-risk interface boundary where the UI could falsely render empty gold as `$0.00` or conflate visual aggregates with line-item payments. Without programmatic enforcement, staff or downstream RCM logic may interpret "no gold lines" as "zero dollars," violating the `empty != $0` honesty principle. This is a defensive data-integrity hardening that builds directly atop HAL-10590’s audit log.

**Effort:** 4–6 hours (policy engine + widget audit + tests).

**REAL files/ops steps:**
1. **Policy Module:** `apex/ui_honesty_policy.py` — define `HonestyPolicy` enum: `EMPTY_IS_NOT_ZERO`, `VISUAL_AUDIT_IS_NOT_GOLD`, `NULL_DISPLAYS_AS_NULL`.
2. **Enforcement Layer:** `apex/widget_validators.py` — `enforce_empty_not_zero(widget_value, source_tag)`:
   - If `source_tag in ["gold_csv", "insurance_payment_lines"]` and value is null/None/empty string → render as `"—"` or `"No Data"` (never `"$0.00"`).
   - If `source_tag == "print_preview_visual"` → render with visual-indicator badge (🔍) and tooltip "Visual audit aggregate — not a payment line."
3. **HAL Policy Registration:** `hal/policy/hon_001_empty_not_zero.yaml` — binds to all `apex.widgets.financial.*` and `softdent.widgets.*`.
4. **Widget Audit:** `scripts/audit_ui_honesty.py` — programmatically scans 46 exact usable cells + Print Preview audit widget for hardcoded `$0.00` fallbacks.
5. **Test:** `test_hon_001_empty_not_zero.py` — matrix: null inputs, empty strings, visual audit objects, missing gold CSV.

**Validation gate:** 
- All 46 catalog cells display `"—"` or `"Insufficient Data"` when gold is missing (not `$0.00`).
- Print Preview audit widget shows `1.0` with 🔍 badge, distinct from gold line-item grid showing `"—"`.
- CI fails if any widget renders null as `$0.00`.

## 2. Why this beats the other candidates now
- **vs. Visual-audit × ledger reconciliation (#2):** Reconciliation creates pressure to "explain" variance, which risks inventing allocation logic or forcing gold lines to match visual totals. HON-001 prevents data corruption before reconciliation matters.
- **vs. ERA835 first-drop (#3):** Manifests exist but `era835: null` confirms no real 835 content yet; premature drop would require inventing carrier mappings.
- **vs. Catalog/spine reliability (#4):** Growing the 46-cell catalog is valuable, but meaningless if the UI renders empty cells as `$0.00`, destroying trust in the spine.
- **vs. Uncovered CDT playbook (#5):** Discovery work; does not address immediate honesty risk at the UI layer.
- **vs. Async HAL (#6):** Infrastructure latency improvement; does not unblock data-plane honesty.
- **vs. Print Preview UX polish (#7):** Cosmetic improvements are secondary to ensuring the data displayed is programmatically prevented from being a lie.

## 3. Runner-ups (2–3, why not now)
1. **Visual-audit × ledger spine reconciliation (#2):** High-value validation, but only after HON-001 guarantees that the comparison is between honest nulls and honest visuals, not `$0.00` hallucinations. Risk of forcing variance explanations too early.
2. **Catalog/spine reliability — secondary-ins exclusion (#4):** Needed to grow beyond 46 cells, but requires HON-001 first to ensure new cells don’t default to `$0.00` when data is insufficient.
3. **Staff Print Preview audit UX polish (#7):** Month-close checklist and carrier breakdown helper are operationally useful, but only if the underlying display layer is honesty-enforced; otherwise staff may record false zeros.

## 4. What NOT to redo
- **SoftDent write-back** — still prohibited; no `sd_insurance_payment_lines` inserts.
- **Invent gold from DaySheet/ledger** — do not create synthetic payment lines to match the `1.0` visual audit total.
- **Excel/CSV export fiction** — continue to acknowledge Insurance Income has no Excel export in v19.1.4.
- **BUILD_ID drift** — keep `hal-10590` coupling; do not fragment into unversioned patches.
- **Redo TP chips/catalog/spine** — 10580–10587 foundation stands; build atop, not replace.
- **Register re-export** — do not attempt Ins Plan Register re-export to get dollars.

## 5. Acceptance criteria
- [ ] `apex/widgets/financial.py` and `softdent_print_preview_audit.py` import `enforce_empty_not_zero`.
- [ ] Any widget receiving `null`, `None`, or missing gold CSV renders `"—"` or `"No Data"`; CI screenshot test proves no `$0.00` appears.
- [ ] Visual audit records (source_tag=`print_preview_visual`) render with distinct 🔍 badge and tooltip, never appearing in gold line-item grids.
- [ ] `hon_001_empty_not_zero.py` test suite passes with 100% coverage on null-handling branches.
- [ ] Operator manually verifies: Gold CSV missing → Insurance Income grid shows `"—"` (not `$0.00`); Print Preview audit shows `1.0` with visual indicator.

## 6. Executive Summary (5 bullets)
- **Risk:** HAL-10590 created a visual audit trail with real dollars (1.0) alongside zero gold payment lines; without enforcement, UI will conflate empty and zero, destroying RCM honesty.
- **Defense:** HON-001 programmatically prohibits widgets from rendering null/missing as `$0.00` and visually distinguishes visual audits from gold lines.
- **Foundation:** Builds directly on HAL-10590’s JSONL audit log and `triggersGoldIngest=false` honesty model.
- **Blocking:** Precedes reconciliation (#2) and catalog expansion (#4) to ensure those features operate on honest data, not `$0.00` hallucinations.
- **Outcome:** Staff can trust that `"—"` means "we don't have it yet" and `$1.00` (with 🔍) means "we saw it in Print Preview," with zero ambiguity.

## 7. Approval checklist
- [ ] Operator confirms: Do not proceed to reconciliation (#2) until UI honesty is enforced.
- [ ] Architect approves: `apex/ui_honesty_policy.py` location and `source_tag` discrimination pattern.
- [ ] Compliance confirms: PHI-safe (no new data capture, only display logic).
- [ ] QA confirms: Can test null-rendering via existing 46-cell catalog fixtures.
- [ ] Build ID locked: `hal-10591` (or `hal-10590` patch) — no drift.