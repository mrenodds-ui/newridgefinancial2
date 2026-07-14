# Moonshot AI — What's Next After Zero-Scroll (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10561  
**Script:** `scripts/run_moonshot_whats_next_after_zero_scroll_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Land hal-10561 immediately by unblocking the merge of branch `fix/main-validate-ci` to main; do not start new features until the zero-scroll remediation is in production.

## 0. Intent
Close the delivery gap between "committed" and "deployed." The zero-scroll remediation (hard height caps, Claims Top 5, compact density) is coded but not on main; every hour it sits unmerged increases divergence risk and leaves production exposed to the scrolling defects you just fixed.

## 1. Already Done (do not redo)
- Expert SE REC-001 through REC-007
- Compact professional pages Phases 1–5 (hal-10550)
- Import gate 403 durability
- Inbox sync coherence (hal-10560)
- Zero-scroll widgets remediation: 120/240/320 caps, HAL sole-l removal, kanban subpage, compact lock (commit `7af33d9`)
- Branch `fix/main-validate-ci` pushed ahead of main

## 2. Recommended NEXT (single package)
**Package: Merge `fix/main-validate-ci` to main and deploy hal-10561**

- **Goal:** Resolve the gh auth blocker (or bypass via web UI) to open and merge the PR containing the zero-scroll fixes, ensuring main HEAD advances to `7af33d9`.
- **Why now:** Shipped value is unrealized until merged; branch divergence is technical debt; speculative NICE work (REC-008/009) should not start on top of an unmerged hotfix branch.
- **Effort:** Low–Medium (30–90 min). Troubleshoot CLI token or manually create PR via GitHub web; standard CI wait time.
- **Files:** None new; validate existing commit `7af33d9`.
- **Validation gate:** 
  - PR created and reviewed
  - CI pipeline green on `fix/main-validate-ci`
  - Merge to main confirmed (HEAD matches `7af33d9`)
  - Post-merge smoke test on staging for widget heights (120/240/320 limits)

## 3. Runner-up options (max 3)
1. **REC-008 Batch Narratives** – Only if gh auth remains blocked >24h and parallel work is unavoidable; accept the cost of eventual rebase.
2. **REC-009 Voice Context Carry** – Deferred NICE; no production risk without it.
3. **site/index.pre-apex.html deletion** – Explicitly excluded per operator directive.

## 4. Approval checklist
- [ ] gh auth token refreshed or PR created via GitHub web UI
- [ ] Diff reviewed: confirms only zero-scroll + validation CI changes
- [ ] CI passes (lint, unit, build) on `fix/main-validate-ci`
- [ ] PR merged to `main`; branch deleted
- [ ] `main` HEAD verified at `7af33d9`
- [ ] Staging deploy confirms hard height caps (120/240/320) active on Claims/Expert widgets