# Moonshot AI — What's Next After Outstanding Claims Bridge (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10576  
**Prior:** Outstanding Claims by Carrier Bridge (`33d6917` / HAL-10580)  
**Script:** `scripts/run_moonshot_whats_next_after_claims_bridge_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Execute **ODBC Patient Insurance Extract & Claims Payer Attribution Refresh** to populate `sd_patient_insurance` and resolve the `CLAIMS_PAYER_ATTRIBUTION_REQUIRED` gap, enabling named-payer visibility on the 60 outstanding claims.

## 0. Operator Intent (verbatim: next)

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**ODBC Patient Insurance Extract & Claims Payer Attribution Refresh**

- **Why now:** HAL-10580 bridge is live but blocked on `gapCode=CLAIMS_PAYER_ATTRIBUTION_REQUIRED`; live snapshot shows `sd_patient_insurance_count=0` and 60/61 claims unnamed. This is the active critical path preventing actionable AR workflows (who owes what). ERA procurement remains blocked on missing files; attribution is the only immediate data fix possible.
- **Effort:** Small (1–2 hrs). Re-use existing `softdent_odbc_extract.py` scaffold from hal-10498; add honest `LEFT JOIN` from claims to insurance/carrier tables; no schema changes.
- **REAL files:**  
  - `NewRidgeFinancial2/softdent_odbc_extract.py` (extend `_populate_from_odbc` for insurance table)  
  - `NewRidgeFinancial2/softdent_outstanding_claims_bridge.py` (refresh payer attribution logic)  
  - `C:\SoftDentFinancialExports\softdent_financial_analytics.db` (target SQLite)  
  - `app_data/nr2/document_inbox/softdent/softdent_outstanding_claims_by_carrier.json` (output validation)
- **Validation gate:**  
  - `sd_patient_insurance_count > 0` (real rows ingested)  
  - `namedPayerClaimCount >= 30` (majority of 61 claims attributed)  
  - `gapCode` clears to `null` or `RECONCILED`  
  - Unit test `test_outstanding_claims_bridge_hal10580` still passes (no regressions)

## 2. Runner-ups (2–3, why not now)
1. **Phase-2 Production by Provider Excel Ingest** — Lower priority. Production authority already fixed in hal-10579; attribution gap is the active blocker preventing AR drill-down. Defer until claims payers are named.
2. **ERA-835 Procurement Playbook** — Evidence insufficient. Live snapshot shows `eraDiscovery.candidateCount=0` and no in-repo portal SOPs exist. OPS remains blocked on missing real files; cannot proceed until procurement completes externally.
3. **Deposit Slip / Collection Reconciliation Phase-2** — Lower leverage. Requires named payers first to reconcile deposits against specific carriers; depends on this package clearing attribution.

## 3. What NOT to redo
- HAL-10580 bridge itself (already shipped)
- Regular Collections DEF-001 ingest (completed)
- Production max-merge honesty fix (hal-10579 completed)
- Register re-export for Ins Plan > $0 (explicitly forbidden)
- Invent fictional carriers, payer IDs, or Insurance Plan dollar amounts (empty ≠ $0)
- SoftDent write-back (remain read-only ODBC SELECT)

## 4. Acceptance criteria
- [ ] `sd_patient_insurance` table populated with >0 rows from SoftDent ODBC (real patient-policy data, NULLs where fields empty, no invented IDs)
- [ ] Claims bridge refresh shows `namedPayerClaimCount` majority (>50%) of 61 claims attributed to specific carriers
- [ ] `gapCode` transitions from `CLAIMS_PAYER_ATTRIBUTION_REQUIRED` to clear state
- [ ] Aging-to-claims reconciliation remains honest (Insurance AR $0 stays $0; claims billed $7,714 preserved as daysheet detail)
- [ ] No regression in HAL-10580 unit tests; new test `test_payer_attribution_refresh` passes
- [ ] Documentation updated: `MOONSHOT_SOFTDENT_COMPREHENSIVE_INGEST_HAL_2026-07-13.md` amended with extraction notes

## 5. Executive Summary (5 bullets)
- HAL-10580 bridge is operational but 98% of claims are unnamed due to empty `sd_patient_insurance`, blocking actionable AR workflows.
- Critical path is executing the ODBC extract (schema ready since hal-10498), not ERA procurement (zero files detected).
- Real extract paths exist: `softdent_odbc_extract.py` and target SQLite at `C:\SoftDentFinancialExports\`.
- Clearing attribution enables "which carrier owes the $7,714" workflows without inventing Insurance Plan collections.
- Remains strictly read-only; no SoftDent write-back or fictional carrier names introduced.

## 6. Approval checklist
- [ ] Operator confirms SoftDent ODBC DSN/credentials active for insurance-related tables (Carrier, PatientInsurance, etc.)
- [ ] Confirm write access to `C:\SoftDentFinancialExports\softdent_financial_analytics.db`
- [ ] Verify `sd_patient_insurance` schema exists from prior hal-10498 apply (document confirms schema shipped)
- [ ] Confirm no ERA files expected in next 24h (OPS stays blocked on procurement)
- [ ] Operator signals "proceed" to execute extract (consult only until then)
