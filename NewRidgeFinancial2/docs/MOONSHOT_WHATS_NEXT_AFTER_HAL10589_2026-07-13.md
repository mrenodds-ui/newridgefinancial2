# Moonshot AI — What's Next After HAL-10589 Gold Print Preview OPS (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10589  
**Prior:** HAL-10589 gold Print Preview OPS (`cfdb92a`)  
**Script:** `scripts/run_moonshot_whats_next_after_hal10589_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> next

---

# Verdict
The next package is **HAL-10590 SoftDent Print Preview Visual-Audit Protocol** — a structured, PHI-safe operational capture of Insurance Income last-page totals that accepts Print Preview as the only available ground truth without inventing gold CSV line items or violating `empty != $0`.

## 0. Operator Intent (verbatim)
next

## 1. Recommended NEXT (name, why now, effort, REAL files/ops steps, validation gate)
**Name:** HAL-10590 / OPS-10590 — SoftDent Print Preview Visual-Audit Protocol  
**Why now:** HAL-10589 definitively established that SoftDent v19.1.4 offers no CSV/Excel export for Insurance Income (Excel unavailable) and that Print Preview is the sole source of financial truth. Rather than stall on the impossible (gold CSV ingestion), the highest-leverage move is to operationalize the Print Preview reality: give staff a guided, auditable protocol to capture last-page aggregate totals (carrier-level Insurance Income) while explicitly distinguishing visual audit data from gold line-item ingest. This unblocks immediate RCM reconciliation honesty and creates the audit trail required to validate any future ERA alternative.

**Effort:** 2–3 hours local code + 30 minutes staff playbook update.

**REAL files/ops steps:**
1. **Code:** `softdent_print_preview_audit.py` — lightweight module with Pydantic schema `PrintPreviewAuditRecord`
   - Fields: `report_type` (enum: InsuranceIncome, ContractualPlanAnalysis), `date_range`, `last_page_aggregate_total`, `carrier_breakdown_if_visible`, `page_count`, `preview_timestamp`, `operator_id`, `source_tag` = `"print_preview_visual"`
   - Explicitly prohibits patient-level detail capture (PHI-safe aggregates only)
2. **Widget:** `softdent-print-preview-audit` — simple staff UI: "Record Last Page Total" button, validation that total > 0, confirmation dialog `This is a visual audit only; no payment lines will be created`
3. **Sync Hook:** `run_ops_10590_print_preview_audit()` — appends audit record to `C:\SoftDentFinancialExports\print_preview_audit_log.jsonl`, updates HAL state `visual_audit_available: true` while keeping `gapCode: GOLD_CSV_MISSING` (honest distinction)
4. **Ops Playbook Update:** `softdent_gold_csv_drop_ops.py` extended with section *"When Print Preview is the Only Option"*
   - F10 sequence `r m i i` → Print Preview → Enter → PageDown/Next to last page → Read *Total Insurance Income* (not page 1 subtotals)
   - Enter aggregate into widget → Save audit record
5. **HAL Policy:** `policy:print-preview-audit` — read-only, no write-back to SoftDent, no synthetic line creation

**Validation gate:** 
- Staff completes Insurance Income Print Preview audit for prior month; JSONL record exists with correct aggregate total.
- `sd_insurance_payment_lines` remains `0` (empty != $0 enforced).
- `gapCode` remains `GOLD_CSV_MISSING` (honest).
- New field `visual_audit_last_page_total` populated with actual dollar amount seen.

## 2. Why this beats the other candidates now
- **Option 3 (ERA835 cross-check):** The `eraLikeFilesSample` shows only manifest wrappers (`manifest_*.json`), not confirmed 835 content. Pursuing ERA now risks inventing a data plane that may not exist. The visual audit accepts confirmed reality (Print Preview exists today).
- **Option 2 (Empty≠$0 enforcement):** Critical hygiene, but defensive; it does not advance operational capability or provide staff a way to record the financial truth they can actually see.
- **Option 7 (Alternate report evaluation):** HAL-10589 already mapped the menu landscape and identified Insurance Income as the primary candidate. Re-evaluating alternate menus without first operationalizing the known-good path is speculative redundancy.
- **Option 4 (Catalog growth):** Growing beyond 46 cells is dangerous without gold validation data; the constraint is data famine, not catalog coverage.
- **Option 6 (Async HAL):** Latency optimization is irrelevant when the data source is manual Print Preview.

## 3. Runner-ups (2–3, why not now)
1. **Option 3 — Remittance/ERA835 first-drop:** Becomes #1 priority *only if* ops confirms real 835 files (not just manifests) exist on disk with payment content. Until then, visual audit is the honest path.
2. **Option 2 — Empty≠$0 programmatic enforcement (HON-001):** Essential safety work, but should follow the visual audit protocol; once staff manually capture totals, we must ensure the UI never renders null as `$0.00`.
3. **Option 5 — Uncovered ledger CDT playbook:** Valuable for the 47 unpaired CDTs, but secondary to establishing a reconcilable audit trail for the 46 exact usable cells already validated.

## 4. What NOT to redo
- SoftDent write-back or ledger mutation
- Invent gold payment lines from DaySheet, sd_payments, or ledger CDT totals
- Pretend Excel/CSV exists for Insurance Income or related reports
- Allow BUILD_ID drift (remain coupled to `hal-10590`)
- Redo TP estimate chips, catalog/spine validation, or InsCo×ADA pairing (46/46 pass is current truth)
- Register re-export "Ins Plan > 0" fiction
- GitHub/PR as primary delivery mechanism (keep local OPS+CODE)
- Re-litigate HAL-10588/10589 discovery (Print Preview only, no Insurance Payment Analysis menu)

## 5. Acceptance criteria
- [ ] `softdent_print_preview_audit.py` module committed with schema validation
- [ ] Widget records session without creating `sd_insurance_payment_lines` (line count stays 0)
- [ ] Audit log JSONL schema reviewed for PHI (no patient names, account numbers, or procedure dates; carrier names and aggregate dollars only)
- [ ] Staff playbook includes F10 `r m i i` sequence and explicit warning: *"Page 1 is incomplete; navigate to last page for totals"*
- [ ] HAL state shows `visual_audit_last_page_total` populated and `gapCode: GOLD_CSV_MISSING` simultaneously (proving honesty distinction)
- [ ] Unit test asserts that visual audit record ≠ gold CSV ingest trigger

## 6. Executive Summary (5 bullets)
- **Honest Acceptance:** Acknowledges SoftDent Print Preview as the only available financial truth source on v19.1.4 (no CSV/Excel export).
- **PHI-Safe Capture:** Structured protocol records last-page Insurance Income aggregates without patient-level detail, satisfying compliance while enabling reconciliation.
- **Empty≠$0 Integrity:** Explicitly distinguishes visual audit totals from gold line-item ingest; `paymentLines` remains 0 until real file appears.
- **Immediate RCM Value:** Gives staff a guided, repeatable method to capture and log insurance totals for month-end close without manual spreadsheets.
- **Future-Proof:** Creates audit trail schema that can later be cross-referenced against ERA835 data if/when that source materializes.

## 7. Approval checklist
- [ ] Operator confirms no real ERA835 files are currently available on disk (if available, abort and switch to Option 3)
- [ ] HAL-10589 post-ops checklist reviewed: `gapCode` still `GOLD_CSV_MISSING`, `paymentLines` = 0
- [ ] Build ID set to `hal-10590` (maintain coupling, no drift)
- [ ] Staff availability confirmed for 15-minute training on new widget
- [ ] `print_preview_audit_log.jsonl` path writeable on `C:\SoftDentFinancialExports\` (same dir as 10589)