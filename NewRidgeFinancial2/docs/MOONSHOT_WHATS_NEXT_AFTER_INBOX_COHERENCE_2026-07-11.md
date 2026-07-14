# Moonshot AI — What's Next After Inbox Coherence (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10560  
**Script:** `scripts/run_moonshot_whats_next_after_inbox_coherence_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Open the pull request for branch `fix/main-validate-ci`, complete GitHub authentication, and merge commit `0dcf1d7` to `main` to release the stranded coherence and durability fixes.

## 0. Intent
Close the delivery gap. Unmerged code is inventory-at-risk: it blocks production deployment of verified fixes (inbox sync coherence, import 403 durability) and invites divergence or bit-rot. The only remaining blocker is administrative (`gh auth`), not technical.

## 1. Already Done (do not redo)
- Expert SE REC-001..007 (gate split, threaded HTTPS, import health, ERA actions)  
- Compact professional pages Phases 1–5  
- Import gate hardening (softGaps, stale-row detection, QB expense warnings)  
- Inbox sync coherence implementation (retention soft-skip, content-hash no-ops, Period protection, direct-first mirror) at commit `0dcf1d7`  
- Branch `fix/main-validate-ci` prepared and pushed ahead of `main`

## 2. Recommended NEXT (single package)
**Goal:** Land `fix/main-validate-ci` (`0dcf1d7`) into `main` via PR and clean the untracked artifact.  
**Why now:** The branch contains production-critical fixes that are currently unreleased. Every hour it sits unmerged increases the risk of merge conflicts, environment drift, and failure to realize ROI on completed engineering.  
**Effort:** Low (15–30 min administrative; zero code logic changes).  
**Files:**  
- Git operations only (no source edits).  
- Optionally `.gitignore` (add `site/index.pre-apex.html` to prevent accidental commit of the untracked leftover).  
**Validation gate:**  
1. `gh auth login` succeeds (web or token flow).  
2. PR created: `fix/main-validate-ci` → `main` with description referencing hal-10560 coherence fixes.  
3. CI pipeline passes (inbox sync coherence tests green).  
4. PR merged; `main` HEAD descends from `0dcf1d7`.  
5. `git status` shows `site/index.pre-apex.html` ignored (if `.gitignore` updated).

## 3. Runner-up options (max 3)
1. **Repository hygiene** – Add `site/index.pre-apex.html` to `.gitignore` and `git rm --cached` if previously staged; cleans workspace before next feature cycle.  
2. **REC-008 Batch narratives** – Implement Expert SE NICE-to-have for bulk narrative generation (park until `main` is current).  
3. **REC-009 Voice context carry** – Implement voice-session context retention (park until `main` is current).

## 4. Approval checklist
- [ ] Operator confirms `gh` CLI installed and GitHub credentials available.  
- [ ] Operator runs `gh auth login` and verifies authentication.  
- [ ] Operator verifies local branch `fix/main-validate-ci` matches remote `origin/fix/main-validate-ci` at `0dcf1d7`.  
- [ ] Operator creates PR, links to hal-10560 coherence docs, and awaits CI green.  
- [ ] Operator merges PR; `git log main` shows `0dcf1d7`.  
- [ ] (Optional) Operator commits `.gitignore` change excluding `site/index.pre-apex.html` if not included in the merge.