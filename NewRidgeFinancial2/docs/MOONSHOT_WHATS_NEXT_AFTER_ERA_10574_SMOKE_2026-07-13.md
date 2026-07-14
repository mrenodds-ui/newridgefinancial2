# Moonshot AI — What's Next After ERA Inbox Mutation-Token Smoke (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10574  
**Prior:** 10574 Refresh Inbox smoke PASS (`5166a01`)  
**Script:** `scripts/run_moonshot_whats_next_after_era_10574_smoke_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Scan for existing ERA-835/EDI remittance files across SoftDent export roots and clearinghouse directories to break the OPS deadlock without inventing data.

## 0. Operator Intent (verbatim: next)
next

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** SoftDent ERA Remittance Discovery Scanner (hal-10575)

**Why now:** OPS has been blocked three times on procurement of "first drop" ERA files, yet staff may have existing remittances in unrecognized SoftDent print paths, clearinghouse export directories, or archived EDI folders. A read-only discovery scan leverages the existing scaffold (empty inbox, honesty UX, mutation-token UI) by locating real 835/EDI/CSV files already on disk without requiring new external procurement or inventing dollar amounts. This unblocks the business ROI the moment files are found, while keeping the "empty ≠ $0" honesty contract intact.

**Effort:** Small additive code change (1–2 files): extend `softdent_practice_exports.py` with a read-only `discover_era_candidates()` walker, surface results via `nr2_hal_gateway.py` to HAL chat, and expose a "Scan for ERA Files" action in `site/apex-core.js` (reusing existing mutation-token plumbing from hal-10574).

**REAL files touched:**
- `NewRidgeFinancial2/softdent_practice_exports.py` (additive scanner function)
- `NewRidgeFinancial2/nr2_hal_gateway.py` (HAL chip action wiring)
- `C:\SoftDentFinancialExports\` (recursive scan, read-only)
- `C:\SoftDentReportExports\` (recursive scan, read-only)
- `C:\SoftDent\` (common practice roots for EDI/Print/Image, if accessible)
- `NewRidgeFinancial2/apex_era835_pack.py` (candidate validation helpers)

**Validation gate:** Scanner runs without elevation, returns a list of candidate file paths (`.835`, `.edi`, `.txt`, `.csv` with 835 headers) with timestamps and sizes; HAL chip surfaces "Found N candidate remittances" with paths; staff can confirm move-to-inbox via UI; zero files created, zero dollars invented, zero SoftDent write-back.

## 2. Runner-ups (2–3, why not now)
1. **OPS: Staff procurement of first REAL ERA-835** — Still the highest theoretical ROI, but remains blocked on human/clearinghouse delays with no new concrete acquisition path (payer portal credentials, specific clearinghouse download steps) to differentiate from the three failed attempts. Defer until discovery scan confirms zero local candidates.
2. **CODE: Wire HAL chip action to Refresh Inbox** — The UI button already works (browser smoke PASS on hal-10574); adding a second HAL chat trigger is lower leverage than locating the missing files that are blocking the gap closure.
3. **OPS: Real QuickBooks payroll/AP export drop** — Valid parallel track, but does not address the immediate `ERA_835_REQUIRED` collections gap blocking July insurance reconciliation.

## 3. What NOT to redo
- ERA inbox mutation-token wiring (hal-10574, just shipped)
- ERA inbox scaffold (hal-10573)
- Gap-tile labels and honesty UX (hal-10571/10572)
- Browser smoke tests for Refresh Inbox (just PASSed)
- SoftDent Register Ins Plan re-export (truth is $0, do not invent)
- Synthetic 835 generation (not production truth)
- GitHub/PR as primary package (local additive code only)

## 4. Acceptance criteria
- [ ] Read-only scan executes across `C:\SoftDentFinancialExports\`, `C:\SoftDentReportExports\`, and common SoftDent EDI/print roots without file modification
- [ ] Discovery identifies candidate remittance files by extension (`.835`, `.edi`, `.txt`, `.csv`) and content sniffing (ISA/835 headers)
- [ ] HAL chip surfaces candidate count and full paths to staff ("Found 3 candidate ERA files in C:\...")
- [ ] Apex UI exposes "Scan for ERA Files" action using existing hal-10574 mutation-token security
- [ ] Scan results include file size, last-modified timestamp, and root location for staff verification
- [ ] No SoftDent write-back, no Register re-export, no synthetic dollar invention
- [ ] If zero candidates found, chip updates to "No local ERA files detected; procurement required" (maintains honesty contract)

## 5. Executive Summary (5 bullets)
- **OPS Blocked, Pivot to Discovery:** Third procurement attempt failed; instead of repeating "drop files" guidance, scan for remittances already present but misplaced in SoftDent export hierarchies.
- **Read-Only Scan:** Additive Python scanner walks real practice roots, identifies 835/EDI patterns, surfaces candidates to HAL without moving or altering files.
- **Honesty Preserved:** Empty inbox continues to report `empty_not_zero`; discovery only adds information, never inventing insurance dollars or re-exporting SoftDent data.
- **Immediate Unblock:** If candidates exist, staff can verify and move to inbox immediately; if none exist, chip guides toward procurement with concrete "scanned paths" evidence.
- **Leverages hal-10574:** Reuses existing mutation-token UI plumbing and Refresh Inbox backend; no new security model required.

## 6. Approval checklist
- [ ] Operator confirms read-only scanning is acceptable on production practice servers
- [ ] Paths `C:\SoftDentFinancialExports\` and `C:\SoftDentReportExports\` remain accessible and scan-safe
- [ ] Staff acknowledges that discovery may return zero results (maintaining current "awaiting" state)
- [ ] HAL chip wording reviewed for "candidates vs. confirmed ERA" distinction (avoid false positive claims)
- [ ] No elevation required for directory traversal (run as current user)
