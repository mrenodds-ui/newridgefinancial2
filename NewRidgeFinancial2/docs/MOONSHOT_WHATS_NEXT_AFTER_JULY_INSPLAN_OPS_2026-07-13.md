# Moonshot AI — What's Next After July Register Ins Plan OPS (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10576  
**Prior:** July Register Ins Plan=$0 confirmed (`1954685`)  
**Script:** `scripts/run_moonshot_whats_next_after_july_insplan_ops_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
CODE package to ingest the existing REG202607.XLS Regular Collections ($30,626.42) into the DEF-001 reconciliation path, accepting Ins Plan=$0 as ground truth and leaving only ERA-835 procurement for insurance-specific collections.

## 0. Operator Intent (verbatim: next)
next

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** DEF-001 Regular Collections Ingest from July Register (hal-10577)

**Why now:**  
The gap currently shows `patient: 0.0` despite confirmed Regular Collections of $30,626.42 in the exported Register. OPS is blocked on ERA procurement for insurance collections (discovery=0), but the Regular Collections truth is already resident in `REG202607.XLS` and needs to be formalized in the DEF-001 month-end reconciliation path. This unblocks the $30K patient-portion of month-end without inventing Ins Plan dollars or waiting for external 835 files.

**Effort:** Small (2–3 hours) — read-only parse of REG202607.XLS, extract Regular Collections column, HAL gateway payload to DEF-001, gap tile update to distinguish Regular (satisfied) vs Insurance (pending).

**REAL files:**
- `C:\SoftDentReportExports\REG202607.XLS` (28,672 bytes — source of Regular Collections truth)
- `NewRidgeFinancial2/nr2_hal_gateway.py` (HAL integration endpoint)
- `NewRidgeFinancial2/apex_softdent_hardening_pack.py` (validation/hardening logic)

**Validation gate:**  
DEF-001 dashboard displays Regular Collections = $30,626.42; `gap.patient` updates from `0.0` to `30626.42`; widget renders “Regular Collections: Complete” separately from “Insurance Collections: ERA Required”; no Ins Plan dollars invented.

## 2. Runner-ups (2–3, why not now)
1. **OPS: Concrete payer-portal / clearinghouse 835 acquisition playbook** — Evidence insufficient: no REAL repo docs/paths for Delta/MetLife/Availity/SoftDent ERA procurement menus exist in the provided file tree to construct specific, verifiable steps. Must defer until operator provides portal SOPs or screenshots.
2. **CODE: HAL/dashboard copy strengthening (10571 follow-up)** — Not needed: 10571 honesty UX is already live and correctly surfaces “ERA_835_REQUIRED” with chipLabel “No local ERA files detected; procurement required” without suggesting Register re-export.
3. **OPS: QuickBooks payroll/AP export drop** — Deferred: No evidence of blocking gap or real files in the current snapshot; lower leverage than closing the $30K Regular Collections data hole that is actively distorting the month-end gap view.

## 3. What NOT to redo
- July Register re-export hoping Ins Plan > 0
- Invent Ins/Patient split
- Account-tx year chunks/HAL/chip (already completed)
- 10575/10576 (ERA discovery and Collections Excel-temp already shipped)
- SoftDent write-back

## 4. Acceptance criteria
- [ ] `REG202607.XLS` parsed read-only; Regular Collections = $30,626.42 extracted
- [ ] Ins Plan Collections remains $0.00 (no invention or interpolation)
- [ ] DEF-001 path ingests Regular Collections without triggering Ins Plan validation errors
- [ ] Gap tile distinguishes Regular Collections (satisfied) vs Insurance Collections (ERA procurement required)
- [ ] No SoftDent write-back attempted; no ERA files moved or renamed

## 5. Executive Summary (5 bullets)
- July Register OPS confirmed Ins Plan Collections = $0.00 (ground truth) and Regular Collections = $30,626.42
- ERA discovery (10575) confirmed zero local 835 files; insurance collections remain blocked pending procurement
- Regular Collections data exists in `REG202607.XLS` but gap shows `patient: 0.0`, indicating DEF-001 ingest is not yet live
- Highest leverage next step is additive CODE ingest of existing Regular Collections, unblocking month-end reconciliation for the patient portion while OPS pursues ERA files separately
- Package respects “empty != $0” constraint, avoids redundant re-export, and uses only real files already on disk

## 6. Approval checklist
- [ ] Operator confirms `REG202607.XLS` contains final Regular Collections figure ($30,626.42) and file is not locked by SoftDent
- [ ] Developer confirms DEF-001 ingest path is distinct from completed account-tx coverage chip track
- [ ] HAL gateway ready to accept Regular Collections payload without requiring Ins Plan > 0
- [ ] No ERA file procurement steps included in this package (separate OPS track)
