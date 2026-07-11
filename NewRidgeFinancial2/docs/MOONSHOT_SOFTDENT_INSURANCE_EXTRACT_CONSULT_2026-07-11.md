# Moonshot AI — SoftDent Insurance Extract for Dossier Availity (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Script:** `scripts/run_moonshot_softdent_insurance_extract_consult.py`  
**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.

## Operator request (verbatim)

> ask moonshot ai how to extract SoftDent patient insurance fields (member id,
subscriber id, payer id / carrier name) into the local SoftDent SQLite extract
so HAL patient dossier eligibility can auto-resolve Availity Coverages without
staff manually typing memberId/payerId every time

---

# Verdict — SoftDent insurance extract for dossier Availity auto-eligibility

## 0. Operator Intent (quote; consult-only)

> "ask moonshot ai how to extract SoftDent patient insurance fields (member id, subscriber id, payer id / carrier name) into the local SoftDent SQLite extract so HAL patient dossier eligibility can auto-resolve Availity Coverages without staff manually typing memberId/payerId every time"

**Consult-only directive:** Recommend extraction architecture; do not commit code. Wait for explicit "approve / proceed".

## 1. Current State Audit (ODBC extract schema vs dossier resolver vs Availity)

| Component | State | Notes |
|-----------|-------|-------|
| **SQLite Schema** (`ensure_sd_schema`) | Missing insurance table | Has `sd_patients`, `sd_claims`, `sd_payments`, etc. **No `sd_patient_insurance`** defined. |
| **Dossier Resolver** (`hal-10497`) | Defensive reader exists | `_resolve_eligibility_for_patient` PRAGMA-checks `sd_patient_insurance` via `_table_exists()`; if absent, reports gaps `["memberId", "payerId"]`. |
| **Availity Backend** | Live-ready | `fetch_eligibility_271` + cache store operational; requires `memberId` + `payerId` + `providerNPI`. |
| **ODBC Extract** | Partial | `softdent_odbc_extract.py` handles providers, patients, procedures, appointments, claims, payments, adjustments. No insurance extraction logic. |
| **CSV Path** | Used for payments | `SoftDentFinancialExports` already ingested for payments; insurance CSV export available but unused. |
| **PHI Handling** | Local-only | Raw member IDs stay in local SQLite; audit uses `patient_hash()`; cache keys hashed. |

## 2. Gap Map

| Area | Status | Gap | Effort | Depends on |
|------|--------|-----|--------|------------|
| **Schema** | Missing | `sd_patient_insurance` table definition | Small | None |
| **ODBC Discovery** | Unknown | SoftDent table names for insurance (PAT_INS, CARRIER, INSURANCE?) vary by version | Small | Read-only catalog query |
| **ODBC Extract** | Missing | SELECT from SoftDent insurance tables → SQLite | Medium | Discovery results |
| **CSV Fallback** | Missing | Loader for SoftDent Financial Export "Insurance" or "Patient Insurance" CSV | Small | Export path config |
| **Dossier Wire** | Ready | Resolver already reads table if present; no code changes needed there | None | Table populated |
| **Payer ID Map** | Gap | SoftDent `carrier_code` ≠ Availity `payerId`; may need lookup table or manual mapping | Medium | Availity directory |

## 3. Target Design

### 3A sd_patient_insurance schema (columns; PRIMARY KEY; empty≠invent)

```sql
CREATE TABLE IF NOT EXISTS sd_patient_insurance (
    practice_id TEXT NOT NULL DEFAULT '',
    patient_id TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 1,  -- 1=Primary, 2=Secondary, 3=Tertiary
    member_id TEXT,                       -- NULL if SoftDent empty (empty≠invent)
    subscriber_id TEXT,                   -- Often same as member_id for self
    subscriber_name TEXT,                 -- NULL if not in SoftDent
    relationship_code TEXT,               -- 'SELF', 'SPOUSE', 'CHILD', etc.
    carrier_code TEXT,                    -- SoftDent internal carrier ID
    insurance_name TEXT,                  -- Carrier name (e.g., "Delta Dental PPO")
    payer_id TEXT,                        -- Availity/EDI payer ID if known in SoftDent
    group_number TEXT,                    -- NULL if empty
    group_name TEXT,                      -- NULL if empty
    effective_date TEXT,                  -- ISO date or NULL
    termination_date TEXT,                -- ISO date or NULL
    extracted_at TEXT NOT NULL,
    PRIMARY KEY (practice_id, patient_id, priority)
);
```

**Invariants:**
- `empty ≠ invent`: If SoftDent returns empty string for `member_id`, store NULL; dossier resolver will list gap.
- `gaps ≠ invent`: If no insurance row exists for patient, table simply has no row; resolver reports gaps.
- Multiple insurances supported via `priority` column (composite PK).

### 3B Extract sources (ODBC SoftDent tables/views OR CSV export) — honest discovery

**Primary: ODBC (preferred)**
SoftDent schema varies by version (v16 vs v20+). Must discover actual tables:

1. **Catalog query** (read-only):
   ```sql
   SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
   WHERE TABLE_TYPE = 'TABLE' AND (TABLE_NAME LIKE '%INS%' OR TABLE_NAME LIKE '%CARR%')
   ```
2. **Likely candidates** (to verify):
   - `PATIENT` table may have `Pri_Carrier`, `Sec_Carrier` columns
   - `CARRIER` table (insurance company directory)
   - `PAT_INS` or `PATIENT_INSURANCE` (junction/policy details)
   - `INSURANCE` or `POLICY` (plan details)

3. **Honest mapping** (example if tables confirmed):
   ```sql
   SELECT 
     p.Patient_ID,
     c.Carrier_Code,
     c.Carrier_Name as insurance_name,
     pi.Member_ID,
     pi.Subscriber_ID,
     pi.Group_Num,
     pi.Effective_Date,
     1 as priority  -- Primary
   FROM PATIENT p
   LEFT JOIN PAT_INS pi ON p.Patient_ID = pi.Patient_ID AND pi.Type = 'PRI'
   LEFT JOIN CARRIER c ON pi.Carrier_Code = c.Carrier_Code
   ```

**Secondary: CSV Export** (`SoftDentFinancialExports/`)
SoftDent can export "Patient Insurance" CSV:
- Columns often: `PatientID`, `LastName`, `FirstName`, `InsuranceCompany`, `PolicyNumber`, `GroupNumber`
- Use when ODBC discovery fails or for historical backfill.

### 3C Wire into ensure_sd_schema + extract job + dossier (already reads table)

1. **Schema**: Add `CREATE TABLE` block to `ensure_sd_schema()` in `softdent_odbc_extract.py`
2. **Tuple**: Add `"sd_patient_insurance"` to `SD_TABLES` tuple for validation
3. **Extract function**: New `extract_patient_insurance(odbc_conn, sqlite_conn, practice_id)`:
   - Queries SoftDent ODBC (discovered tables)
   - Inserts/upserts into SQLite with `extracted_at = _utc_now()`
   - Uses parameterized queries to prevent injection
4. **Orchestration**: Add call in `run_full_extract()` (existing function) after `sd_patients` extraction
5. **Dossier**: No changes needed; resolver already PRAGMA-checks table existence and reads columns defensively

### 3D PHI, redaction, audit, demo vs live honesty

- **Local-only PHI**: Raw `member_id`, `subscriber_id` stored only in local SQLite file (`resolve_sd_sqlite_db()`). File permissions must be `0600` or user-only.
- **Audit**: `hal_patient_audit` table uses `patient_hash(patient_id)` for eligibility queries; raw member ID never logged or sent to cloud.
- **Availity cache**: Cache keys use `patient_hash(f"{patient_id}:{member_id}:{payer_id}")`; reverse engineering impossible without local DB.
- **Demo honesty**: If `sd_patient_insurance` has NULL `member_id`, dossier reports gap and does **not** fake eligibility; staff must use HAL tool `fetch_eligibility_271` with manual overrides until data populated.
- **Empty handling**: SQLite NULLs flow through to dossier `gaps[]` array; UI shows "Insurance on file but Member ID missing" rather than invented ID.

## 4. Coding Plan by Phase (files · paste-ready sketches · validation)

### Phase 1: Schema + Discovery (MUST)

**File:** `softdent_odbc_extract.py`

```python
# Add to ensure_sd_schema()
"""
CREATE TABLE IF NOT EXISTS sd_patient_insurance (
    practice_id TEXT NOT NULL DEFAULT '',
    patient_id TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 1,
    member_id TEXT,
    subscriber_id TEXT,
    subscriber_name TEXT,
    relationship_code TEXT,
    carrier_code TEXT,
    insurance_name TEXT,
    payer_id TEXT,
    group_number TEXT,
    group_name TEXT,
    effective_date TEXT,
    termination_date TEXT,
    extracted_at TEXT NOT NULL,
    PRIMARY KEY (practice_id, patient_id, priority)
);
"""

# Update SD_TABLES
SD_TABLES = (
    "sd_providers",
    "sd_patients",
    "sd_procedures",
    "sd_appointments",
    "sd_claims",
    "sd_payments",
    "sd_adjustments",
    "sd_patient_insurance",  # ADD
)
```

**Discovery helper** (run once to identify SoftDent schema):
```python
def discover_insurance_tables(odbc_conn) -> list[dict]:
    """Read-only catalog search. Returns candidate table names."""
    cur = odbc_conn.cursor()
    try:
        # SQL Server/MS Access style (SoftDent typically MS Access or SQL Server)
        cur.execute(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE = 'TABLE' AND (TABLE_NAME LIKE ? OR TABLE_NAME LIKE ?)",
            ("%INS%", "%CARR%")
        )
        rows = cur.fetchall()
        return [{"table": r[0]} for r in rows]
    except Exception:
        # Fallback: list all tables for manual inspection
        cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'TABLE'")
        return [{"table": r[0]} for r in cur.fetchall()]
```

### Phase 2: ODBC Extract (MUST)

**File:** `softdent_odbc_extract.py`

```python
def extract_patient_insurance(
    odbc_conn,
    sqlite_conn: sqlite3.Connection,
    practice_id: str,
    dry_run: bool = False,
) -> int:
    """Extract insurance policies from SoftDent → sd_patient_insurance.
    
    Honest: empty strings stored as NULL. No invented payer IDs.
    """
    cursor_sqlite = sqlite_conn.cursor()
    extracted_at = _utc_now()
    count = 0
    
    # Example query - adjust after Phase 1 discovery confirms actual table/column names
    query = """
    SELECT 
        p.Patient_ID as patient_id,
        1 as priority,
        pi.Member_ID as member_id,
        pi.Subscriber_ID as subscriber_id,
        pi.Subscriber_Name as subscriber_name,
        pi.Relationship as relationship_code,
        c.Carrier_Code as carrier_code,
        c.Carrier_Name as insurance_name,
        c.EDI_Code as payer_id,  -- May be NULL; Availity mapping may need external lookup
        pi.Group_Num as group_number,
        pi.Group_Name as group_name,
        pi.Effective_Date as effective_date,
        pi.Termination_Date as termination_date
    FROM PATIENT p
    LEFT JOIN PAT_INS pi ON p.Patient_ID = pi.Patient_ID AND pi.Ins_Type = 'PRI'
    LEFT JOIN CARRIER c ON pi.Carrier_Code = c.Carrier_Code
    WHERE pi.Carrier_Code IS NOT NULL
    """
    
    cur_odbc = odbc_conn.cursor()
    cur_odbc.execute(query)
    
    cols = [desc[0] for desc in cur_odbc.description]
    
    for row in cur_odbc.fetchall():
        row_dict = dict(zip(cols, row))
        
        # Normalize empties → NULL (honest: no invention)
        def norm(val):
            if val is None:
                return None
            s = str(val).strip()
            return s if s else None
        
        patient_id = norm(row_dict.get("patient_id"))
        if not patient_id:
            continue  # Cannot link without patient_id
            
        member_id = norm(row_dict.get("member_id"))
        payer_id = norm(row_dict.get("payer_id"))  # NULL if SoftDent lacks EDI code
        
        if not dry_run:
            cursor_sqlite.execute(
                """INSERT INTO sd_patient_insurance (
                    practice_id, patient_id, priority, member_id, subscriber_id,
                    subscriber_name, relationship_code, carrier_code, insurance_name,
                    payer_id, group_number, group_name, effective_date, termination_date, extracted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(practice_id, patient_id, priority) DO UPDATE SET
                    member_id=excluded.member_id,
                    subscriber_id=excluded.subscriber_id,
                    subscriber_name=excluded.subscriber_name,
                    relationship_code=excluded.relationship_code,
                    carrier_code=excluded.carrier_code,
                    insurance_name=excluded.insurance_name,
                    payer_id=excluded.payer_id,
                    group_number=excluded.group_number,
                    group_name=excluded.group_name,
                    effective_date=excluded.effective_date,
                    termination_date=excluded.termination_date,
                    extracted_at=excluded.extracted_at
                """,
                (
                    practice_id,
                    patient_id,
                    row_dict.get("priority", 1),
                    member_id,
                    norm(row_dict.get("subscriber_id")),
                    norm(row_dict.get("subscriber_name")),
                    norm(row_dict.get("relationship_code")),
                    norm(row_dict.get("carrier_code")),
                    norm(row_dict.get("insurance_name")),
                    payer_id,
                    norm(row_dict.get("group_number")),
                    norm(row_dict.get("group_name")),
                    norm(row_dict.get("effective_date")),
                    norm(row_dict.get("termination_date")),
                    extracted_at,
                ),
            )
        count += 1
    
    sqlite_conn.commit()
    return count
```

**Wire into orchestration** (in `run_full_extract` or similar):
```python
# After extract_patients(...)
if odbc_conn:
    try:
        ins_count = extract_patient_insurance(odbc_conn, sqlite_conn, practice_id)
        _set_meta(sqlite_conn, "insurance_extracted_count", str(ins_count))
        _set_meta(sqlite_conn, "insurance_extracted_at", _utc_now())
    except Exception as e:
        _set_meta(sqlite_conn, "insurance_extract_error", str(e))
        # Continue extraction - don't kill entire job for insurance failure
```

### Phase 3: CSV Fallback (SHOULD)

**File:** `softdent_csv_ingest.py` (new or extend existing payments CSV loader)

```python
def load_insurance_csv(csv_path: Path, sqlite_conn: sqlite3.Connection, practice_id: str) -> int:
    """Ingest SoftDent Financial Export 'Patient Insurance' CSV.
    
    Expected columns: PatientID, InsuranceCompany, PolicyNumber, GroupNumber, etc.
    """
    import csv
    cursor = sqlite_conn.cursor()
    count = 0
    extracted_at = _utc_now()
    
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            patient_id = (row.get("PatientID") or row.get("Patient ID") or "").strip()
            if not patient_id:
                continue
            
            member_id = (row.get("PolicyNumber") or row.get("Member ID") or "").strip() or None
            insurance_name = (row.get("InsuranceCompany") or row.get("Insurance Company") or "").strip() or None
            
            cursor.execute(
                """INSERT INTO sd_patient_insurance (
                    practice_id, patient_id, priority, member_id, insurance_name,
                    group_number, extracted_at
                ) VALUES (?, ?, 1, ?, ?, ?, ?)
                ON CONFLICT(practice_id, patient_id, priority) DO UPDATE SET
                    member_id=excluded.member_id,
                    insurance_name=excluded.insurance_name,
                    group_number=excluded.group_number,
                    extracted_at=excluded.extracted_at
                """,
                (
                    practice_id,
                    patient_id,
                    member_id,
                    insurance_name,
                    (row.get("GroupNumber") or "").strip() or None,
                    extracted_at,
                ),
            )
            count += 1
    sqlite_conn.commit()
    return count
```

**Config:** Add env var `SOFTDENT_INSURANCE_CSV_PATH` optional fallback.

### Phase 4: Validation (MUST)

**Test:** `test_softdent_extract.py` (extend existing)
```python
def test_insurance_schema_created(self):
    conn = sqlite3.connect(":memory:")
    ensure_sd_schema(conn)
    self.assertTrue(_table_exists(conn, "sd_patient_insurance"))

def test_insurance_extract_honest_nulls(self):
    # Mock ODBC returning empty strings
    # Verify SQLite stores NULL, not empty string
    # Verify dossier resolver reports gaps when member_id NULL
```

**Validation query** (run after extract):
```sql
SELECT 
    COUNT(*) as total_policies,
    COUNT(member_id) as with_member_id,
    COUNT(payer_id) as with_payer_id,
    COUNT(CASE WHEN member_id IS NULL THEN 1 END) as missing_member_id
FROM sd_patient_insurance;
```

## 5. MUST / SHOULD / NICE ranked table

| Priority | Item | Business Impact |
|----------|------|----------------|
| **MUST** | Create `sd_patient_insurance` schema + ODBC discovery | Unblocks auto-eligibility; without this, staff type IDs manually |
| **MUST** | `extract_patient_insurance()` with honest NULL handling | Prevents invented member IDs causing Availity lockouts/fraud flags |
| **MUST** | Update `SD_TABLES` tuple | Ensures validation catches missing table |
| **SHOULD** | Secondary insurance support (`priority=2`) | 30% of dental patients have dual coverage; reduces manual overrides |
| **SHOULD** | CSV fallback loader | Insurance ODBC tables sometimes restricted; CSV export is universal workaround |
| **SHOULD** | Carrier-to-Payer ID mapping table (`sd_carrier_payer_map`) | SoftDent `carrier_code` rarely matches Availity `payerId`; staff can map once, system reuses |
| **NICE** | Termination date filtering (`termination_date >= TODAY`) | Prevents stale primary insurance from blocking current eligibility |
| **NICE** | Background pre-fetch eligibility for upcoming appointments | Warms cache overnight using extracted insurance data |
| **NICE** | Relationship code normalization ( map 1→SELF, 2→SPOUSE) | Improves Availity query accuracy for dependent coverage |

## 6. Risks, PHI, SoftDent honesty, Rollback

**Risks:**
- **Schema mismatch**: SoftDent versions vary (SQL Server vs Access). **Mitigation**: Phase 1 discovery query; log actual table names to `sd_extract_meta`.
- **Stale data**: Insurance changes in SoftDent not reflected until next extract. **Mitigation**: `extracted_at` timestamp visible in dossier; daily extract job.
- **Wrong payer ID**: SoftDent `carrier_code` → Availity `payerId` mapping may be wrong, causing eligibility failures. **Mitigation**: Dossier shows `carrier_code` + `insurance_name` in gaps if `payer_id` NULL; staff can override via HAL tool.

**PHI Safeguards:**
- SQLite file must have restrictive permissions (`chmod 600` on Linux; ACLs on Windows).
- Raw `member_id` never appears in logs; audit uses `patient_hash()`.
- ODBC connection string must not log passwords.

**SoftDent Honesty:**
- `SELECT` only; no `INSERT`/`UPDATE` to SoftDent.
- Empty strings normalized to SQL NULL; dossier resolver treats NULL as missing (gap), not as "$0" or default ID.
- If `sd_patient_insurance` row exists but `member_id` is NULL, dossier explicitly states: *"Primary insurance on file (Delta Dental) but Member ID missing from SoftDent."*

**Rollback:**
```sql
-- Emergency rollback: drop table (dossier reverts to gap reporting)
DROP TABLE IF EXISTS sd_patient_insurance;
DELETE FROM sd_extract_meta WHERE key LIKE 'insurance%';
```
Remove call to `extract_patient_insurance()` from orchestration.

## 7. Approval Checklist

**Before any code is applied, operator must confirm:**

- [ ] **Discovery approved**: Run `discover_insurance_tables()` against production SoftDent ODBC (read-only) and review actual table/column names
- [ ] **Schema approved**: `sd_patient_insurance` columns sufficient for practice's SoftDent version (some versions lack `Member_ID` field entirely)
- [ ] **PHI handling**: SQLite file permissions restricted to service account only; no cloud sync of `.db` file
- [ ] **CSV path** (if used): `SoftDentFinancialExports` directory path confirmed and accessible
- [ ] **Payer ID strategy**: Decision on whether to maintain `sd_carrier_payer_map` lookup table or rely on staff overrides for mismatched payer IDs
- [ ] **Extract schedule**: Daily extract job timing confirmed (insurance changes rarely intra-day)
- [ ] **Rollback tested**: Confirm `DROP TABLE sd_patient_insurance` restores current behavior (gaps reported)

**DO NOT APPLY until operator replies "approve / proceed".**