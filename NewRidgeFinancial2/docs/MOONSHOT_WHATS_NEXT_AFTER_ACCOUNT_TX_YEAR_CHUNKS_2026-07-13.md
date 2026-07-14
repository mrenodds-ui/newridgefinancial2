# Moonshot AI — What's Next After Account-TX Year Chunks (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10576  
**Prior:** year-chunk TX 10/10 verified (`f80b58d`)  
**Script:** `scripts/run_moonshot_whats_next_after_account_tx_year_chunks_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Ingest the verified year-chunk TX Excel files (TXN2017H2 through TXN2026YTD plus TXNALL260712) into the existing SoftDent account-tx SQLite/JSONL ledger by extending `scripts/continue_softdent_txn_excel.py` to process the full 2017–2026 history idempotently against the manifest at `softdent_account_tx_year_chunks.json`.

## 0. Operator Intent (verbatim: next)
next

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** Year-Chunk Account-TX Ingest (extend `continue_softdent_txn_excel.py`)

**Why now:** The 10 year-chunk files (~164k rows) and TXNALL260712 (~385k rows) are verified on disk but remain "dark" to HAL. This is the highest-leverage additive fix: it unlocks multi-year account history immediately using real files already procured, while ERA procurement (external) and July Register Ins>0 (blocked on ERA) remain stalled. Extending the proven XLS ingest path respects the existing data architecture and avoids inventing pipelines.

**Effort:** Medium (1–2 files, ~50–80 lines): extend `continue_softdent_txn_excel.py` to read the chunk manifest JSON, iterate `TXN*.XLS` files, and upsert into the account-tx DB with idempotency checks (file stem + row hash).

**REAL files:**
- **Inputs:** `C:\SoftDentReportExports\TXN2017H2.XLS` … `TXN2026YTD.XLS`, `TXNALL260712.csv`
- **Manifest:** `C:\SoftDentFinancialExports\softdent_account_tx_year_chunks.json` (row counts, year ranges, validation)
- **Script to extend:** `scripts/continue_softdent_txn_excel.py`
- **Parsing helpers:** `NewRidgeFinancial2/softdent_practice_exports.py`
- **Target:** Existing account-tx SQLite/JSONL ledger (consumed by `nr2_hal_gateway.py`)

**Validation gate:**
- Row-count parity for each chunk matches manifest (e.g., TXN2025 = 21,642 rows).
- Idempotency: re-running ingest produces zero duplicate rows.
- HAL query for account history spanning 2017–2026 returns non-empty results.
- TXNALL260712 mid-2017 truncation handled (no overlap duplicates with TXN2017H2).

## 2. Runner-ups (2–3, why not now)
1. **OPS: Commit/ship hal-10576 Collections Excel-temp reliability** — Local code already applied; while uncommitted, it is hygiene, not capability. Defer until after ingest commits, or parallel-track if commit overhead is <5 min.
2. **CODE/OPS: Wire HAL answers for multi-year coverage** — Consumer logic that requires the year-chunk data to be ingested first. Cannot proceed until this ingest completes.
3. **OPS: Concrete payer-portal 835 acquisition** — Discovery (hal-10575) proved zero local candidates; procurement is external/vendor-blocking and cannot be forced by local code.

## 3. What NOT to redo
- Year-chunk GUI pulls (10/10 already verified on disk).
- ERA discovery (hal-10575 already shipped, candidateCount=0 confirmed).
- Collections Excel-temp 10576 mutation smoke (already applied locally).
- Widgets MUST/SHOULD/NICE (awaiting data).
- Invent Register Ins Plan > 0 dollars (still blocked on ERA_835_REQUIRED).
- Synthetic ERA/835 generation.
- SoftDent write-back of any kind.

## 4. Acceptance criteria
- [ ] All 10 year-chunk XLS files plus TXNALL260712 parsed and loaded into account-tx store.
- [ ] `softdent_account_tx_year_chunks.json` manifest row counts match DB insert counts per chunk.
- [ ] Idempotency key (file stem + transaction UID hash) prevents duplicates on re-run.
- [ ] HAL gateway query for date range 2017-06-01 to 2026-07-12 returns > 500k rows.
- [ ] No `SoftDent write-back` or synthetic dollars invented; empty fields remain empty (≠ $0).
- [ ] Existing `softdent_excel_temp.py` (hal-10576) file handles reused for atomic reads.

## 5. Executive Summary (5 bullets)
- **Verified assets idle:** 10 year-chunk TX files (2017H2–2026YTD) and TXNALL260712 (~550k total rows) sit on disk uningested, blocking multi-year HAL answers.
- **Proven path exists:** `scripts/continue_softdent_txn_excel.py` provides the extension point; no new pipeline invention required.
- **External blockers persist:** ERA procurement and July Register Ins Plan > 0 remain stuck on `ERA_835_REQUIRED`; this ingest is the only high-ROI code work available.
- **Additive only:** Extends existing SQLite/JSONL ledger and HAL surface; respects `empty != $0` and zero-invention policy.
- **Validation concrete:** Row counts from `softdent_account_tx_year_chunks.json` provide exact acceptance metrics.

## 6. Approval checklist
- [ ] Operator confirms `scripts/continue_softdent_txn_excel.py` is the correct extension point (or cites alternative REAL ingest module).
- [ ] Backup of existing account-tx DB verified before bulk ingest.
- [ ] `softdent_account_tx_year_chunks.json` loaded as validation manifest (not source of truth for business logic).
- [ ] Confirmation that hal-10576 commit status is non-blocking (parallel git hygiene allowed).
- [ ] HAL policy updated to expose `account_tx_multi_year_available=true` only after validation gate passes.
