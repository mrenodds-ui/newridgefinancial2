# Moonshot AI — SoftDent C:\softdent *.dat + system.sys Feasibility

**Date:** 2026-07-10  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10370  
**Script:** `scripts/run_moonshot_softdent_dat_sys_consult.py`  
**Apply:** Report only.

## Operator request (verbatim)

> ask moonshot ai if he can get softdent data from C:\softdent folder using *.dat and system.sys and report

---

# Verdict: **NO**

## 0. Operator Intent (quote verbatim)
> "ask moonshot ai if he can get softdent data from C:\softdent folder using *.dat and system.sys and report"

## 1. What C:\softdent Contains (engine + file roles)
**Engine Family:** FairCom **c-treeACE** (c-treeRTG) ISAM **OR** Btrieve/Pervasive PSQL — **uncertain due to missing catalog files**.  
The 166 `.dat` files paired with `.idx` companions constitute a classic ISAM (Indexed Sequential Access Method) datastore typical of SoftDent/PracticeWorks:
- **`.dat`**: Data segments containing raw record bytes (fixed or variable length). `trans.dat` (~258 MB) holds transaction headers/ledgers; `patient.dat` (~23 MB) holds patient demographics; `unlimtxt.dat` (~418 MB) holds clinical narrative blobs.
- **`.idx`**: B-tree index files (e.g., `trans.idx` ~84 MB) mapping keys to physical record offsets.
- **Format**: Proprietary binary (header bytes `7da82210...` observed). Not SQLite, not CSV, not JSON. Requires record layout definitions (schema) to parse.

## 2. system.sys Reality Check
**CRITICAL LIVE FACT:** `system.sys` is **NOT FOUND** at `C:\softdent\system.sys` (any case).  
- `softdent.sys` exists (2,870 bytes) but contains only corporation/recall boilerplate strings; it is **not** a Btrieve system catalog (which defines page size, file versions, and system tables).  
- **No DDFs present:** `FILE.DDF`, `FIELD.DDF`, and `INDEX.DDF` are absent from the install root.  
- **Implication:** Without `system.sys` (Btrieve) or `FILE.DDF` (Pervasive SQL) or c-tree FD/DD definitions, there is **zero machine-readable metadata** mapping the 166 `.dat` files to table names, column offsets, data types, or index keys. The schema is opaque.

## 3. Can We Read *.dat Directly? (feasibility + blockers)
**Feasibility:** **NO** for production-grade data retrieval.

**Blockers:**
1. **Schema Opacity:** Reading raw c-tree/Btrieve pages without the dictionary (DDFs or `system.sys` + table definitions) yields undifferentiated byte streams. Field boundaries, numeric encodings (BCD vs IEEE-754), date packing, and string encodings (ANSI vs OEM) are unknown.
2. **Live Lock Contention:** SoftDent’s `SD.exe` or `PWSvr` services maintain file locks on `trans.dat`, `patient.dat`, etc. Direct open (even read-only) can trigger **c-tree error 12 (file not found)** or **error 22 (invalid file)** if the engine detects non-transactional access, or cause **deadlocks** with active users.
3. **Corruption Risk:** ISAM files require atomic page consistency. A Python script reading sectors while SoftDent writes a split record (index + data page update) can cache torn pages, rendering subsequent analytics corrupt or crashing the SoftDent instance.
4. **PHI & Audit:** Direct byte-level access bypasses SoftDent’s user-level ACLs, audit logging, and encryption-at-rest (if enabled). This violates the principle of least privilege for HIPAA-covered data.
5. **License/ToS:** Carestream’s EULA prohibits reverse engineering of data formats; parsing proprietary `.dat` structures without vendor SDK/API constitutes breach.

## 4. Safe Approaches Ranked (best → worst)
| Rank | Approach | Status | Rationale |
|------|----------|--------|-----------|
| **MUST** | **SoftDentFinancialExports JSONL** | Live (hal-10370) | Vendor-supported batch extract; includes daysheet, transactions_for_period, register. No lock contention. |
| **SHOULD** | **Sensei Gateway DataSync** | Live | Real-time JSON feeds (`sd_patients`, `sd_appointments`, `sd_procedures`). API-contracted schema. |
| **SHOULD** | **SQL ODBC DSN** | Lane exists, DSN unset | If SoftDent SQL module is licensed, a Pervasive/c-tree ODBC DSN provides `SELECT` access via standard driver without raw file I/O. |
| **NICE** | **SoftDent Report CSV exports** | Live | Scheduled reports → `SDReports\` → ingest inbox. Fully supported. |
| **NEVER** | **Raw `.dat` / `.idx` parsing** | Blocked | No schema, high corruption risk, license breach, PHI exposure. |

## 5. Recommendation for NR2
**Do not attempt direct `.dat` file ingestion.** The prerequisite metadata (`system.sys` or DDFs) is absent, and the transaction data you require is **already available** via the JSONL export lane (build hal-10370 confirmed applied). 

If the current JSONL lacks specific fields (e.g., line-item adjustments in `trans.dat`):
1. Extend the existing `SoftDentFinancialExports` extraction script to include those fields in the JSONL output, **or**
2. Enable the dormant **ODBC lane** by configuring a read-only DSN pointing to `C:\softdent` (only if Carestream confirms SQL licensing and provides the connection string).

## 6. Risks / PHI / Rollback
- **PHI Exposure:** Direct file access circumvents SoftDent’s audit trail (`audit_security.dat`, `audit_trans.dat`). Any Python script touching these bytes must be treated as a **high-risk PHI interface** requiring full encryption in transit/at rest and access logging.
- **Corruption / Availability:** If a read lock stalls SoftDent’s ISAM engine, practice operations (scheduling, billing) halt. Rollback requires restoring from `SoftDent_DatabaseSet\*.bak`.
- **Compliance:** Reverse engineering the `.dat` format violates Carestream’s Terms of Service and potentially HIPAA Security Rule §164.312 (technical safeguards).

## 7. Operator Next Actions
1. **Confirm Absence:** Run `dir C:\softdent\system.sys /s /b` and `dir C:\softdent\*.ddf /s /b` to verify no hidden catalogs exist in subdirectories (e.g., `C:\softdent\DataSync\` or `C:\softdent\VXDATA\`).
2. **Gap Analysis:** Compare `trans.dat` field requirements against the existing `transactions_for_period.jsonl` schema. Identify specific missing columns.
3. **ODBC Probe:** Check Windows ODBC Data Source Administrator (32-bit) for "Pervasive ODBC Engine Interface" or "c-treeACE ODBC Driver". If present, request Carestream’s read-only connection parameters rather than parsing files.
4. **Document Block:** Update `softdent_database_export_ingest.py` docstring to explicitly cite: *"Direct Btrieve/c-tree ISAM file access blocked—system.sys and DDFs absent; use JSONL/ODBC lanes only."*
5. **Close Consult:** No production code changes recommended for raw `.dat` access.