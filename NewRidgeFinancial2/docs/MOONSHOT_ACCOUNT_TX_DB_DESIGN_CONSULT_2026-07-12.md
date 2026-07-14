# Moonshot AI — SoftDent Account Transactions Database Design (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10569  
**Prior:** TXN XLS ingest + ledger surface (001a927)  
**Script:** `scripts/run_moonshot_account_tx_db_design_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> ask moonshot how to make a database to place account transactions now that we know how to get them. then report

---

# Verdict
Extend `softdent_financial_analytics.db` with a new table `sd_account_transactions` (distinct from the existing `sd_transactions_full`) using a composite stable-id of `source_file:row_number`, nullable REAL money columns, and purge-and-insert idempotency per Excel file.

## 0. Operator Intent (verbatim)
ask moonshot how to make a database to place account transactions now that we know how to get them. then report

## 1. Recommended design (DB file, table name, why now, effort)
**DB file:** `C:\SoftDentFinancialExports\softdent_financial_analytics.db` (additive reuse)  
**Table:** `sd_account_transactions`  
**Why:** The analytics DB is already the HAL/widgets read target, already backs `sd_transactions_full` (practice-wide transaction dumps), and avoids file-proliferation backup risks. A separate table preserves the distinct schema of “Trans-for-a-Period” account ledgers (account_num, note_flag, prod/charges/cash columns) without polluting the legacy `sd_transactions_full` shape.  
**Effort:** Low—single DDL, one loader function in `softdent_transaction_extract.py`, and a filter change in `nr2_hal_gateway.py`.

## 2. DDL (CREATE TABLE + indexes) — exact SQL
```sql
CREATE TABLE IF NOT EXISTS sd_account_transactions (
    stable_id TEXT PRIMARY KEY,              -- 'TXN260201.xls:42'
    source_file TEXT NOT NULL,               -- basename only
    row_number INTEGER NOT NULL,
    account_num TEXT NOT NULL,               -- e.g., '27002'
    patient_name TEXT,
    service_date TEXT,                       -- ISO-8601 or raw MM/DD/YY
    provider TEXT,
    procedure TEXT,
    note_flag TEXT,                          -- 'N', 'Y', etc.
    amount REAL,                             -- nullable; empty stays null
    prod REAL,
    charges REAL,
    prod_adj REAL,
    cash REAL,
    check REAL,
    credit REAL,
    pay_adj REAL,
    period_start TEXT,                       -- parsed from periodHint '2026-02-01'
    period_end TEXT,                         -- parsed from periodHint '2026-02-28'
    extracted_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_acctx_account ON sd_account_transactions(account_num);
CREATE INDEX IF NOT EXISTS idx_acctx_date ON sd_account_transactions(service_date);
CREATE INDEX IF NOT EXISTS idx_acctx_period ON sd_account_transactions(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_acctx_source ON sd_account_transactions(source_file);
```

## 3. Load / upsert plan (REAL functions/files, idempotency key)
**Location:** `NewRidgeFinancial2/softdent_transaction_extract.py`  
**Function signature:**
```python
def upsert_account_transactions_jsonl(
    jsonl_path: Path,
    db_path: Path = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
) -> dict:
    """
    Idempotent load: deletes prior rows for the same source_file, inserts all
    records, verifies counts. stable_id = f"{source_file}:{row_number}".
    """
```

**Idempotency key:** `stable_id` = `{source_file}:{row_number}` (e.g., `TXN260201.xls:5`).  
**Transaction flow:**
1. `BEGIN TRANSACTION`
2. `DELETE FROM sd_account_transactions WHERE source_file = ?` (basename of JSONL)
3. Parse JSONL; for each record compute `stable_id`, split `periodHint` into `period_start`/`period_end`.
4. `INSERT OR REPLACE INTO sd_account_transactions ...`
5. **Validation gate:** `SELECT COUNT(*) FROM sd_account_transactions WHERE source_file = ?` must equal `meta.recordCount` (e.g., 1716).
6. **Validation gate:** `SELECT COUNT(*) FROM sd_account_transactions WHERE account_num='27002' AND period_start='2026-02-01'` must equal 5 (Donna rows).
7. `COMMIT`

**Honesty rule:** If the JSONL has `null` for a money field, insert `NULL`; never coerce to `0.0`.

## 4. Read path (HAL, widgets, analytics)
**HAL Gateway** (`nr2_hal_gateway.py`):  
Replace JSONL file walk with SQL:
```python
def query_account_transactions(account_num: str, date_from: str, date_to: str) -> list[dict]:
    conn = sqlite3.connect(ANALYTICS_DB)
    rows = conn.execute(
        """SELECT service_date, procedure, amount, note_flag, provider, 
                  prod, charges, cash, check, credit
           FROM sd_account_transactions
           WHERE account_num = ? AND service_date BETWEEN ? AND ?
           ORDER BY service_date, row_number""",
        (account_num, date_from, date_to)
    ).fetchall()
    return [dict(r) for r in rows]
```

**Widgets** (`apex_better_backend_widgets_pack.py`):  
`build_transaction_ledger_table(account_num, period)` queries the same table, formats as `data-table` rows for SoftDent/OM UI.

**Analytics:** Direct SQL joins against `sd_patients` or `sd_providers` using `account_num` or `provider` columns.

## 5. Runner-ups (2–3, why not)
1. **Extend `sd_transactions_full` with nullable account-ledgers columns** — Rejected: the two sources have different grain (practice-wide claim lines vs. account-ledger rows). Adding 10+ nullable columns and `note_flag` to the existing table would confuse analytics and break existing parity checks.
2. **New separate DB `account_transactions.db`** — Rejected: Backup scripts, connection pools, and HAL config would need to bifurcate; no schema benefit outweighs the operational cost.
3. **Keep JSONL-only, query via file I/O** — Rejected: No indexing for HAL patient lookups, slow for large periods, prevents SQL joins with patient/provider reference tables.

## 6. What NOT to do
- **No ODBC write-back:** Never INSERT/UPDATE back into SoftDent via ODBC; Excel exports remain read-only.
- **No invented claim links:** Do not fabricate `claim_id` or `transaction_id` foreign keys; the Excel rows are account ledger lines, not claim lines.
- **No $0 coercion:** Empty money cells in Excel must remain SQL `NULL`, never `0.0`.
- **No GUI automation:** Do not script SoftDent’s “Trans for a Period” save dialog; continue manual Excel drop to `C:\SoftDentReportExports`.
- **No mutation of `sd_transactions_full`:** That table owns the Sensei/ODBC practice-wide extract; keep the new Excel ingest separate.

## 7. Acceptance criteria
- [ ] DDL executes without error against `softdent_financial_analytics.db`.
- [ ] Load of `TXN260201.jsonl` produces exactly **1716** rows in `sd_account_transactions`.
- [ ] Query `account_num='27002' AND period_start='2026-02-01'` returns **5** rows (Donna validation).
- [ ] `amount`, `cash`, `check`, etc., are `NULL` (not `0`) where the Excel cell was empty.
- [ ] Re-running the loader on the same file produces identical counts (idempotent purge/insert).
- [ ] HAL query `query_account_transactions('27002','2026-02-01','2026-02-28')` returns the 5 Donna rows from the DB, not the JSONL file.
- [ ] Widget `build_transaction_ledger_table` renders the Donna rows without file I/O.

## 8. Executive Summary (5 bullets)
- **Additive reuse:** Add table `sd_account_transactions` to the existing analytics DB; no new files, no changes to `sd_transactions_full`.
- **Stable identity:** Primary key `stable_id = source_file:row_number` guarantees idempotent re-ingest when the same TXN Excel is re-exported.
- **Null honesty:** Money columns use REAL nullable; empty SoftDent cells stay SQL `NULL`, never forced to `$0`.
- **HAL integration:** Gateway and widgets query indexed SQL (account_num + date) instead of scanning JSONL, enabling sub-second patient ledger replies.
- **Validation gates:** Automated rowCount parity (1716) and Donna-spot-check (5 rows) ensure data integrity on every load.

## 9. Approval checklist
- [ ] Operator confirms `sd_account_transactions` DDL aligns with `parse_account_transactions_xls` output keys.
- [ ] Operator confirms `softdent_transaction_extract.py` is the correct home for the upsert function.
- [ ] Operator confirms HAL gateway should prefer DB over `tx_parsed/*.jsonl` for account lookups.
- [ ] Operator confirms no requirement to link these rows to `sd_claims` or `sd_transactions_full` (they remain separate ledgers).
- [ ] Operator ready to test with `TXN260201.xls` → expect 1716 rows, Donna 27002 = 5.
