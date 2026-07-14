# Moonshot AI — What's Next After ERA Remittance Discovery (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10575  
**Prior:** 10575 discovery live candidates=0 (`7eec3ed`)  
**Script:** `scripts/run_moonshot_whats_next_after_era_10575_discovery_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Recommend Collections Summary Excel-temp reliability patch (hal-10576) to unblock parallel staff reporting while ERA procurement continues.

## 0. Operator Intent (verbatim: next)
next

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** Collections Summary Excel-Temp Reliability Fix (hal-10576)

**Why now:** ERA discovery (hal-10575) conclusively proved zero local 835 candidates exist, blocking the insurance gap (`ERA_835_REQUIRED`) on external procurement. Rather than idle waiting, this CODE package hardens the SoftDent Collections Summary Excel export path (atomic temp-write pattern) to eliminate zero-byte temp files and AV-lock failures. It is the highest-ROI non-ERA code fix, respects `registerInsPlanZero=true` (no Register re-export), and keeps staff productive on manual collections workflows while payer files are procured separately.

**Effort:** Small surgical patch (1 file, ~20 lines): refactor Excel writer in `softdent_practice_exports.py` to use `NamedTemporaryFile(delete=False)` + `shutil.move()` instead of direct overwrite, with explicit cleanup.

**REAL files touched:**
- `NewRidgeFinancial2/softdent_practice_exports.py` (Collections Summary Excel export function)
- `NewRidgeFinancial2/apex_era835_pack.py` (if shared temp utilities reside here)

**Validation gate:** Unit test `test_collections_summary_excel_atomic_temp_hal10576` passes; manual SoftDent → Collections Summary → Excel export produces valid `.xlsx` with no residual `.tmp` files in `%TEMP%`/working directory.

## 2. Runner-ups (2–3, why not now)
1. **OPS: Concrete payer-portal 835 acquisition playbook** — Deferred because no REAL repo docs/paths for Delta Dental, MetLife, Availity, or SoftDent ERA download menus are listed in the provided context; cannot cite evidence. Revisit once staff provide portal credentials or documentation.
2. **OPS: Real QuickBooks payroll/AP export drop** — High-ROI lateral move contingent on staff producing real QB export files today; if files appear, this supersedes Excel-temp work.
3. **CODE: Expand discovery roots** — No new REAL SoftDent/EDI paths exist beyond the three already scanned (`C:\SoftDentFinancialExports`, `C:\SoftDentReportExports`, `C:\SoftDent`); additional probes would be speculative.

## 3. What NOT to redo
- ERA Remittance Discovery Scanner (hal-10575) — shipped and live-validated with `candidateCount=0`.
- ERA Inbox Mutation-Token wiring / browser smoke (hal-10574) — already PASS.
- Gap-tile honesty UX (`empty_not_zero`) — already live.
- Register Ins Plan re-export or synthetic 835 generation — never invent dollars or production remittances.
- Additional "drop 835" OPS without specific portal/clearinghouse steps grounded in repo evidence.

## 4. Acceptance criteria
- [ ] Collections Summary Excel export completes without `PermissionError`, `FileInUse`, or zero-byte temp debris.
- [ ] Output `.xlsx` passes `openpyxl` load validation and contains expected rows/columns.
- [ ] Temp files are atomically moved; no partial writes visible to other processes.
- [ ] HAL telemetry emits `collections_summary_export_success` with `temp_cleanup=true`.
- [ ] No SoftDent write-back occurs; operation remains read-only export.

## 5. Executive Summary (5 bullets)
- **ERA dead-end confirmed:** hal-10575 discovery scanned all listed roots and proved zero local 835 files; procurement must happen externally.
- **Parallel track:** Fix Collections Summary Excel-temp reliability to prevent staff blocking on export failures while waiting for payer files.
- **Surgical scope:** Single-file patch (`softdent_practice_exports.py`) implementing atomic temp-write pattern.
- **Honesty preserved:** No invented dollars, no Register re-export, `empty_not_zero` contract maintained.
- **Validation:** Clean Excel output, zero temp-file leakage, unit test coverage.

## 6. Approval checklist
- [ ] Operator confirms Collections Summary Excel exports currently fail or leave temp debris.
- [ ] Verify target logic resides in `softdent_practice_exports.py` (confirm before editing).
- [ ] Acknowledge ERA gap (`ERA_835_REQUIRED`) remains open until staff procure real payer 835s via portal/clearinghouse.
