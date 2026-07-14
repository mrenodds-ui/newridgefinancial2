# Moonshot AI — Confirm HAL-10601 TP Carrier Alias (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10601  
**Prior apply:** HAL-10601 (`58e05c0`)  
**Script:** `scripts/run_moonshot_confirm_hal10601_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> again confer with moonshot ai what you just did and consult only

---

# Verdict
HAL-10601 applied matches consult exactly—no deviations; NEXT package is **Candidate #3 — Honesty CI Gate** (fail build if TP/widgets regress null→$0.00).

## 0. Operator Intent (verbatim)
> "again confer with moonshot ai what you just did and consult only"
> 
> Confirm HAL-10601 apply vs your prior TP recommendation. Then pick THE next package. CONSULT ONLY — do not apply.

## 1. Confirmation of HAL-10601 apply (pass/fail; deviations; residual risks)

**PASS — Exact match to Moonshot consult specification (MOONSHOT_CONFIRM_HAL10600_TREATMENT_PLANNING).**

| Consult Requirement | Applied Reality (58e05c0) | Status |
|---------------------|---------------------------|--------|
| Wire `lookup_treatment_estimate` through accepted alias before spine | `resolve_accepted_alias_for_tp()` called prior to spine lookup; gold checked first | ✓ |
| Accepted alias = `confidence=auto` + `review_status=accepted` only | 107 auto-accepted used; 19 manual pending excluded | ✓ |
| Pending manuals → blockedPending / null $ / HAL message | `anthem188_pending_D1110` probe shows `blockedPending=true`, `paidAmountAvg=null`, `showDollars=false` | ✓ |
| Source tagging `ledger_episode_5yr_via_alias` | Probe shows `source=ledger_episode_5yr_via_alias` for Aetna Healthcare | ✓ |
| `tpCodeUsesCarrierAlias=true` status flag | `treatmentPlanningStatus.tpCodeUsesCarrierAlias=true` | ✓ |
| No SoftDent write-back; empty≠$0 | No payment lines invented; `emptyIsNotZero=true` on all probes | ✓ |

**Deviations:** None.

**Residual Risks:**
1. **Manual band contamination (19 rows):** "Guardian Advantage"→"AETNA MEDICARE ADVANTAGE" (70.6) and similar dubious fuzzy matches remain in `pending`. Auto-accepting these would misattribute spine dollars to wrong carriers.
2. **Orphan leakage (89 rejected):** Carriers like Assurant, Bankers remain with `no_settlement`. Staff must not manually pad these with synthetic estimates.
3. **Regression risk:** Future TP widget changes could accidentally coerce `null`→`0.00` in UI formatting, violating the `emptyIsNotZero` contract and presenting "insurance pays $0" when data is actually unknown.

## 2. Recommended NEXT (name, why now, effort, REAL files, validation gate)

**Package:** **Candidate #3 — Honesty CI Gate: Null-to-Zero Regression Prevention**

**Why now:**
- HAL-10601 established the alias→spine resolution pipeline and exposed true `null` dollars for pending/blocked states. The cardinal compliance risk is no longer missing data (which is handled) but **misrepresenting missing data as zero dollars**.
- A single UI formatting regression (e.g., `{{ estimate.paidAmountAvg | default:"0.00" }}`) would cause treatment plans to display "$0.00" for the 8,637 `no_settlement` cells and 19 pending aliases, misleading clinicians into believing insurance contributes nothing rather than "unknown."
- This must harden **before** expanding coverage to 47 additional CDTs (#6) or secondary insurance (#4), as expanded coverage increases the blast radius of any null-handling bug.

**Effort:** Low (0.5–1 dev day). Add CI test suite to `test_hal10601_tp_carrier_alias.py` or new `test_hal10603_honesty_ci.py`.

**REAL files:**
- `tests/integration/test_tp_null_handling.py` — assert `showDollars=false` when `paidAmountAvg is None`
- `tests/integration/test_widget_regression.py` — assert UI JSON returns `null` not `"0.00"` for insufficient estimates
- `.github/workflows/validate-ci.yml` (existing `fix/main-validate-ci` branch) — add step `pytest -m honesty`

**Validation gate:**
- Build fails if any probe returns `emptyIsNotZero=false` or if `paidAmountAvg=0.00` for records with `paymentLines=0` and `source≠probabilistic_estimates`.
- Specific test: `anthem188_pending_D1110` must never show dollars; `aetnaHealthcare_D2391` must show `$60.80` (not null).

## 3. Why this beats other candidates now

| Candidate | Why #3 wins |
|-----------|-------------|
| **#1 UI metadata** (masterCompanyId on chip) | Cosmetic; foundation already solid. Risk of regression is higher than value of metadata display. |
| **#2 Review 19 pending** | Critical OPS track, but **parallel** to dev. Does not require code shipment (accept/reject is data ops via `--accept-pending` flag). Can proceed while CI gate is built. |
| **#4 Secondary insurance** | Premature. Secondary resolution requires primary identity to be bulletproof; we need the honesty gate first to ensure primary alias resolution never degrades. |
| **#5 Gold CSV/ERA** | Blocked by `GOLD_CSV_MISSING`. No REAL files on disk to process. |
| **#6 Uncovered 47 CDTs** | High value but offensive expansion. Expanding coverage before hardening the null-handling invariant risks misrepresenting the new cells as $0 if a regression occurs. Gate first, grow second. |

## 4. Runner-ups (2–3)

1. **Candidate #6 — Uncovered Ledger CDT Playbook (47 CDTs)**  
   Unlock additional spine settlements for CDTs already present in 5-year ledger but not yet mapped to treatment estimates. **Defer until after CI gate** to ensure new coverage cannot be misrepresented as zero.

2. **Candidate #2 — HAL Review of 19 Pending Manuals**  
   Parallel operational track. Review "Guardian Advantage"→"AETNA" (70.6) and similar; accept only if spine attribution is certain. **Not a code package** primarily, though requires CLI `--accept-pending` execution.

3. **Candidate #4 — Grow Usable InsCo×ADA (Secondary Insurance)**  
   Expand alias resolution to `secondary_insurance_company_id`. **Defer** until primary alias pipeline proven stable via CI gate.

## 5. What NOT to redo

- **SoftDent write-back:** Do not write aliases or estimates back to SoftDent tables.
- **Invent gold:** Do not create synthetic `paymentLines` or `GOLD_CSV` data.
- **Accept all 19 pending blindly:** Do not batch-accept the manual band; "Guardian→Aetna" and similar fuzzy matches require individual HAL review.
- **Force ≤20 alias gap:** Do not lower threshold to 60% to force-match the 89 rejected orphans (Assurant, Bankers, etc.).
- **Rebuild spine greenfield:** Do not replace existing `ledger_episode_5yr` spine; extend it only.
- **Re-wire 10601:** Do not modify `resolve_accepted_alias_for_tp()` logic; it is correct.
- **GitHub/PR as primary:** Continue using BUILD_ID tagging (`hal-10603` for next) rather than PR-centric workflow.

## 6. Acceptance criteria

- [ ] CI build `hal-10603` fails if `emptyIsNotZero` flips to `false` for any probe
- [ ] CI build fails if `paidAmountAvg` is `0.00` (number) rather than `null` for records with `source=carrier_alias_pending` or `source=ledger_episode_5yr_via_alias` where raw spine data is null
- [ ] UI widget tests confirm `$—` or hidden field displayed, not `$0.00`, when `showDollars=false`
- [ ] Existing probes (`aetnaHealthcare_D2391`, `anthem188_pending_D1110`) remain green on commit
- [ ] No changes to `softdent_treatment_planning.py` logic (only tests/CI added)

## 7. Executive Summary (5 bullets)

- **HAL-10601 verified:** Alias resolution pipeline matches spec; 107 accepted carriers now flow through to TP, 19 pending correctly blocked with null dollars.
- **Residual risk:** Null values could regress to $0.00 in UI formatting, violating the "empty≠$0" financial honesty contract.
- **Next move:** Install Honesty CI Gate (#3) to fail builds on null→zero regression before expanding coverage.
- **Deferred value:** 47 uncovered CDTs (#6) and secondary insurance (#4) queued behind the safety gate.
- **Parallel ops:** Manual review of 19 pending aliases (#2) proceeds independently via CLI; no code block.

## 8. Approval checklist

- [ ] Operator acknowledges HAL-10601 confirmation (pass, no deviations)
- [ ] Operator selects Candidate #3 as the single next package
- [ ] CI test file location confirmed (`tests/integration/test_tp_null_handling.py`)
- [ ] Build ID assigned: `hal-10603` (or next available)
- [ ] Parallel ops approved for Candidate #2 (review 19 pending) if desired
- [ ] Deferred confirmation: Candidates #4, #6, #5 remain blocked until this gate ships