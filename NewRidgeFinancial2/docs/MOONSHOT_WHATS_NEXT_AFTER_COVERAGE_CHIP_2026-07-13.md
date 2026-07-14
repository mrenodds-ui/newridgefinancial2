# Moonshot AI — What's Next After Account-TX Coverage Chip (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10576  
**Prior:** coverage chip shipped (`8096158`)  
**Script:** `scripts/run_moonshot_whats_next_after_coverage_chip_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
OPS SoftDent July Register/Collections export with Ins Plan Collections > 0 to unblock DEF-001 month-end reconciliation — programming on the account-tx track is done.

## 0. Operator Intent (verbatim: next)

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** OPS SoftDent July 2026 Register/Collections Export (Ins Plan Collections > 0)

**Why now:**  
- Month-end AR reconciliation is blocked on insurance collections truth (`registerInsPlanZero: true`, `insurance: 0.0` for 2026-07).  
- DEF-001 ingest pipeline is deployed and ready; the only missing component is the input file with populated Ins Plan Collections column.  
- Current `REG202607.XLS` (28 KB → 945-byte CSV conversion) indicates the export omitted insurance splits or used an incorrect report variant.  
- 15 minutes of operator export work unblocks the gap versus days of low-ROI code hedging around missing data.

**Effort:** 15 minutes (SoftDent GUI navigation and export); zero code changes.

**REAL files:**  
- Target overwrite: `C:\SoftDentReportExports\REG202607.XLS`  
- Alternative naming: `C:\SoftDentReportExports\register_for_period_2026-07-01_2026-07-31.xls`  
- Ingest destination: `C:\SoftDentFinancialExports\softdent_financial_analytics.db` (DEF-001 target table)

**Validation gate:**  
1. File size increases significantly (>100 KB vs. current 28 KB stub).  
2. CSV conversion shows non-zero values in `Ins Plan Collections` column for July 2026 dates.  
3. DEF-001 ingest completes without schema errors.  
4. Query `SELECT SUM(ins_plan_collections) FROM register WHERE period = '2026-07'` returns non-zero dollars.  
5. `registerInsPlanZero` flag flips to `false` in live snapshot.

## 2. Runner-ups (2–3, why not now)
- **OPS Payer Portal / Clearinghouse 835 Acquisition:** Not now because hal-10575 discovery conclusively proved zero local ERA candidates exist, and the repo contains no evidence of portal API credentials or clearinghouse SFTP endpoints; procurement requires external contracting outside current scope. Defer until SoftDent Register export confirms insurance collections logic is sound.  
- **CODE Collections Summary Excel-Temp Atomicity Patch:** Not now because the immediate blocker is data absence (zero insurance dollars), not file I/O reliability; patching temp-write patterns offers <5% ROI while the insurance column remains empty. Revisit only after data provenance is established.  
- **CODE HAL Teach / Policy Line for Coverage Chip:** Not now because the coverage chip is live (549,564 rows, 1996–2026 range) and HAL multi-year queries are operational; additive teaching yields marginal gain compared to unblocking the $0 insurance gap.

## 3. What NOT to redo
Account-tx coverage chip (8096158), multi-year HAL wiring (2906b0e), year-chunk pull/ingest (6843a9c), hal-10575/10576 discovery sweeps, widget MUST/SHOULD/NICE classification taxonomy, inventing Ins Plan/ERA dollar amounts, SoftDent write-back operations, or GitHub/PR rituals as primary delivery vehicle.

## 4. Acceptance criteria
- [ ] Operator generates July 2026 Collections or Register report from SoftDent ensuring the **Ins Plan Collections** column is selected and contains non-zero values.  
- [ ] Export file overwrites `C:\SoftDentReportExports\REG202607.XLS` (or creates the alternative naming variant).  
- [ ] File size demonstrates substantial row presence (>100 KB).  
- [ ] DEF-001 ingest processes the file without `KeyError` on `Ins Plan Collections`.  
- [ ] Database reflects non-zero insurance collections for July 2026 and `registerInsPlanZero` flag updates to `false`.

## 5. Executive Summary (5 bullets)
- **Account-tx programming track is complete:** Coverage chip shipped, multi-year HAL live, SQL LIMIT filters active, 549k rows queryable (1996–2026).  
- **Gap is data procurement, not code:** July Register export lacks Ins Plan Collections values; DEF-001 ingest pipeline is idle-awaiting valid input.  
- **ERA/835 discovery finished:** Hal-10575 confirmed zero local remittance files; insurance truth must originate from SoftDent export until external procurement concludes.  
- **Highest leverage action:** Operator-side SoftDent export (15 min) unblocks month-end reconciliation versus speculative coding around missing files.  
- **Concrete path forward:** Overwrite `REG202607.XLS` with populated Ins Plan Collections column, re-run DEF-001 ingest, validate non-zero insurance dollars.

## 6. Approval checklist
- [ ] I understand this recommendation is **CONSULT ONLY** — no code will be applied by Moonshot AI.  
- [ ] I acknowledge the account-tx code track is considered complete and no further programming is recommended on this branch.  
- [ ] I will execute the SoftDent export (or delegate to practice staff) targeting `C:\SoftDentReportExports\REG202607.XLS`.  
- [ ] I will verify the new file size exceeds the current 28 KB stub and contains populated Ins Plan Collections data.  
- [ ] I will re-run DEF-001 ingest and confirm July 2026 insurance collections displays non-zero dollars in the analytics DB.
