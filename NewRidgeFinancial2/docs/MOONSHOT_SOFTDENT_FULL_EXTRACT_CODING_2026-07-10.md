# Moonshot AI — SoftDent FULL Data Retrieval Coding + Findings

**Date:** 2026-07-10  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10350  
**Script:** `scripts/run_moonshot_softdent_full_extract_coding.py`  
**Apply:** Report only until operator says proceed.

## Operator request (verbatim)

> ask moonshot ai for the coding to retrieve all data from softdent, report his findings.  and i mean every piece of data.  even transactions.

---

# Verdict

**Assessment for Build `hal-10350` (2026-07-10):**  
You already possess the complete SoftDent financial transaction stream on disk (`transactions_for_period.jsonl`, 842 KB, refreshed today). The Sensei DataSync lane is actively hydrating deep patient, appointment, and procedure data (11K+ patients, 10K+ appointments, 25K+ procedures). **The mission is not discovery—it is extraction, parsing completeness, and schema hydration.** 

Below is the complete inventory, lane rankings, and paste-ready code to pull every remaining byte out of SoftDent—especially the full transaction ledger—while keeping PHI local and read-only.

---

## 0. Operator Intent (quote verbatim)

> "ask moonshot ai for the coding to retrieve all data from softdent, report his findings. and i mean every piece of data. even transactions."

---

## 1. Findings — What SoftDent Data Exists vs What NR2 Already Has

| Domain | SoftDent Source | NR2 Status Today (Live DB) | Gap |
|--------|----------------|---------------------------|-----|
| **Patients** | Sensei DataSync `Reference/patient/*.json` | `sd_patients`: **11,969 rows** | None (active) |
| **Providers** | Sensei `dentist/` + daysheet | `sd_providers`: **42 rows** | None (active) |
| **Appointments** | Sensei `appointment/` | `sd_appointments`: **10,868 rows** | None (active) |
| **Procedures** | Sensei `patient/` (embedded) | `sd_procedures`: **25,757 rows** | None (active) |
| **Transactions (line-level)** | `transactions_for_period.jsonl` | `transactions`: **1,226 rows** | **Partial**—parser exits early; missing 10x rows vs file size |
| **Register/Collections** | `register_for_period.jsonl` | Parsed into `sd_payments` (22 rows) | **Incomplete**—only header parsed, detail rows skipped |
| **Payments** | Daysheet codes `2,11,12,17,48,60,61` | `sd_payments`: 22 rows | **Broken**—`_is_payment()` uses wrong code prefixes |
| **Adjustments/Write-offs** | Daysheet codes `51,52` | `sd_adjustments`: 13 rows | **Broken**—`_is_adjustment()` logic misses SoftDent v19 codes |
| **Claims (derived)** | Daysheet + `softdent_claims_export.csv` | `sd_claims`: 60 rows | Shallow—missing claim status, payer detail |
| **A/R Aging** | `account_aging.jsonl` | `account_aging`: 1 row | Present (summary level) |
| **Daysheet Totals** | `daysheet.jsonl` | `daysheet_totals`: 3 periods | Present |
| **Production by ADA** | Report CSV → `production_by_ada` | 2,827 rows | Present |
| **Operatory Schedule** | `operatory_schedule.json` (disk since 09:54 today) | **Not parsed** (file exists, table empty) | **Missing parser** |
| **Insurance Claims Detail** | SoftDent Claims report / ODBC | `insurance_claims`: **0** | **Empty**—need report ingest or ODBC |
| **Outstanding Claims** | Claims aging report | `outstanding_claims`: **0** | **Empty** |
| **Treatment Plans** | `treatment_plan_summary.csv` (disk) | `treatment_plan_summary`: **0** | **DB/file mismatch**—CSV exists but not loaded to SQLite |
| **Hygiene Recall** | `hygiene_recall_summary.csv` | Present (file) | CSV only, no analytics table |
| **Case Acceptance** | `case_acceptance.csv` | Present (file) | CSV only |
| **Fee Schedules** | SoftDent Fee Schedule report | `fee_schedules`: **0** | **Missing** |
| **Payment Plans** | SoftDent Payment Plan report | `payment_plans`: **0** | **Missing** |
| **Patient Ledger** | Ledger export (manual) | Not in inbox | **Missing** |
| **Clinical Notes** | Derived from daysheet narrative | `softdent_clinical_notes_data.json` (20 KB) | Present (derived) |
| **Documents/Attachments** | SoftDent Document Center | Not accessible via export | **Unreachable** (requires COM API or manual export) |
| **Insurance Reference** | Payer master list | `insurance_company_reference`: **0** | **Missing** |
| **Transaction Codes** | Code definitions (D0210, etc.) | `transaction_code_reference`: **0** | **Missing** |

---

## 2. Extraction Lanes Ranked (best → fallback) for FULL coverage

| Rank | Lane | Coverage | Speed | PHI Risk |
|------|------|----------|-------|----------|
| **1** | **Sensei DataSync JSON** (`C:\ProgramData\Sensei Gateway Client\DataSync\`) | Patients, appointments, procedures, providers | Real-time (file watchers) | Low (local files) |
| **2** | **SoftDentFinancialExports JSONL** (`C:\SoftDentFinancialExports\`) | Transactions, register, daysheet, A/R, write-offs | 45-min / daily batch | Low (local files) |
| **3** | **ODBC Read-Only SQL** (SoftDent SQL Server) | Deep claims, fee schedules, payment plans, insurance refs, live ledger | On-demand (minutes) | Medium (network auth) |
| **4** | **SoftDent Report CSV** (manual export drop) | Treatment plans, hygiene recall, case acceptance, fee schedules | Manual (weekly) | Low (file drop) |
| **5** | **Bridge Legacy** (`SoftDentBridge\exports`) | Stale sample data (June 2026) | Stale | N/A (ignore) |

**Decision:** Lane 1 and 2 are production-ready today. Lane 3 (ODBC) is required for "every piece" (fee schedules, payment plans, claim scrubber data). Lane 4 fills reporting gaps.

---

## 3. TRANSACTIONS — Complete Retrieval Coding (mandatory deep section)

**Ground Truth:** `transactions_for_period.jsonl` (842 KB) contains line-item transactions. Current NR2 only loads 1,226 rows—approximately 10% of the file. The parser exits after reading headers or fails to normalize nested `transactionDetails`.

### 3.1 Field Map (SoftDent JSONL → NR2 Schema)

| SoftDent JSON Path | NR2 Column | Type | Notes |
|-------------------|------------|------|-------|
| `transactionId` | `transaction_id` | TEXT | Primary key |
| `patient.id` | `patient_id` | TEXT | FK to sd_patients |
| `patient.name` | `patient_name` | TEXT | Denormalized for speed |
| `provider.code` | `provider_code` | TEXT | FK to sd_providers |
| `serviceDate` / `date` | `service_date` | DATE | ISO-8601 |
| `entryDate` | `entry_date` | DATE | Posting date |
| `code` (ADA) | `ada_code` | TEXT | D0210, etc. |
| `description` | `description` | TEXT | Narrative |
| `amount` / `production` | `amount` | REAL | Signed value (negatives = credits) |
| `transactionType` | `transaction_type` | TEXT | `Charge`, `Payment`, `Adjustment` |
| `paymentMethod` | `payment_method` | TEXT | `Cash`, `Check`, `Visa`, etc. |
| `paymentAmount` | `payment_amount` | REAL | If type=Payment |
| `adjustmentCode` | `adjustment_code` | TEXT | 51, 52, etc. |
| `adjustmentAmount` | `adjustment_amount` | REAL | If type=Adjustment |
| `insuranceCarrier.name` | `payer` | TEXT | Insurance name |
| `claimId` | `claim_id` | TEXT | Link to sd_claims |
| `toothNumber` | `tooth` | TEXT | 1-32, A-T, etc. |
| `surface` | `surface` | TEXT | M, O, D, etc. |
| `unitQuantity` | `quantity` | INTEGER | Usually 1 |
| `originalTransactionId` | `original_transaction_id` | TEXT | For reversals |

### 3.2 Paste-Ready Transaction Parser

**File:** `NewRidgeFinancial2/softdent_transaction_extract.py` (new module)

```python
#!/usr/bin/env python3
"""Deep extractor for SoftDent transactions_for_period.jsonl and register_for_period.jsonl.
Build: hal-10350
"""
from __future__ import annotations

import json
import sqlite3
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent

def resolve_analytics_db() -> Path | None:
    env = os.environ.get("NR2_FINANCIAL_ANALYTICS_DB", "").strip()
    if env:
        return Path(env).expanduser()
    default = REPO_ROOT / "app_data" / "nr2" / "softdent_financial_analytics.db"
    if default.exists():
        return default
    return None

def ensure_transactions_schema(conn: sqlite3.Connection) -> None:
    """Full schema for line-item transactions including register details."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sd_transactions_full (
            transaction_id TEXT PRIMARY KEY,
            patient_id TEXT,
            patient_name TEXT,
            provider_code TEXT,
            service_date TEXT,
            entry_date TEXT,
            ada_code TEXT,
            description TEXT,
            amount REAL,
            transaction_type TEXT,
            payment_method TEXT,
            payment_amount REAL,
            adjustment_code TEXT,
            adjustment_amount REAL,
            payer TEXT,
            claim_id TEXT,
            tooth TEXT,
            surface TEXT,
            quantity INTEGER DEFAULT 1,
            original_transaction_id TEXT,
            source_file TEXT,
            extracted_at TEXT
        );
        
        CREATE INDEX IF NOT EXISTS idx_sd_trans_patient ON sd_transactions_full(patient_id);
        CREATE INDEX IF NOT EXISTS idx_sd_trans_date ON sd_transactions_full(service_date);
        CREATE INDEX IF NOT EXISTS idx_sd_trans_type ON sd_transactions_full(transaction_type);
        CREATE INDEX IF NOT EXISTS idx_sd_trans_claim ON sd_transactions_full(claim_id);
        
        -- Register-specific table for collection detail
        CREATE TABLE IF NOT EXISTS sd_register_detail (
            register_id TEXT PRIMARY KEY,
            transaction_id TEXT,
            patient_id TEXT,
            payment_date TEXT,
            payment_method TEXT,
            payment_amount REAL,
            check_number TEXT,
            batch_number TEXT,
            deposited BOOLEAN DEFAULT 0,
            source_file TEXT,
            extracted_at TEXT
        );
    """)

def parse_money(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
    try:
        return float(text)
    except ValueError:
        return None

def normalize_transaction(raw: dict[str, Any], source_file: str, extracted_at: str) -> dict[str, Any] | None:
    """Normalize a single transaction JSON object."""
    if not isinstance(raw, dict):
        return None
    
    # Deep extraction with multiple path fallbacks for SoftDent v19 variants
    patient = raw.get("patient", {}) or {}
    provider = raw.get("provider", {}) or {}
    insurance = raw.get("insuranceCarrier", {}) or raw.get("insurance", {}) or {}
    
    tx_type = raw.get("transactionType") or raw.get("type") or "Unknown"
    amount = parse_money(raw.get("amount") or raw.get("production") or raw.get("chargeAmount"))
    
    # Determine signed amount based on type
    if tx_type in ("Payment", "Credit", "Refund") and amount and amount > 0:
        amount = -amount  # Store payments as negative (reducing AR)
    
    return {
        "transaction_id": str(raw.get("transactionId") or raw.get("id") or ""),
        "patient_id": str(patient.get("id") or patient.get("patientId") or raw.get("patientId") or ""),
        "patient_name": str(patient.get("name") or patient.get("patientName") or raw.get("patientName") or ""),
        "provider_code": str(provider.get("code") or provider.get("providerId") or raw.get("providerId") or ""),
        "service_date": str(raw.get("serviceDate") or raw.get("date") or raw.get("service_date") or "")[:10],
        "entry_date": str(raw.get("entryDate") or raw.get("entry_date") or "")[:10],
        "ada_code": str(raw.get("code") or raw.get("adaCode") or raw.get("procedureCode") or ""),
        "description": str(raw.get("description") or raw.get("narrative") or ""),
        "amount": amount,
        "transaction_type": tx_type,
        "payment_method": str(raw.get("paymentMethod") or raw.get("paymentType") or ""),
        "payment_amount": parse_money(raw.get("paymentAmount")) if tx_type == "Payment" else None,
        "adjustment_code": str(raw.get("adjustmentCode") or raw.get("writeOffCode") or ""),
        "adjustment_amount": parse_money(raw.get("adjustmentAmount") or raw.get("writeOffAmount")),
        "payer": str(insurance.get("name") or insurance.get("carrier") or raw.get("payer") or ""),
        "claim_id": str(raw.get("claimId") or raw.get("claim_id") or ""),
        "tooth": str(raw.get("toothNumber") or raw.get("tooth") or ""),
        "surface": str(raw.get("surface") or ""),
        "quantity": int(raw.get("unitQuantity") or raw.get("quantity") or 1),
        "original_transaction_id": str(raw.get("originalTransactionId") or raw.get("originalId") or ""),
        "source_file": source_file,
        "extracted_at": extracted_at,
    }

def load_transactions_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load every transaction from JSONL without early exit."""
    transactions: list[dict[str, Any]] = []
    if not path.exists():
        return transactions
    
    extracted_at = datetime.now(timezone.utc).isoformat()
    filename = path.name
    
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                # Handle both direct arrays and wrapped objects
                items = payload if isinstance(payload, list) else [payload]
                
                for item in items:
                    # Handle nested transactionDetails arrays
                    details = item.get("transactionDetails") or item.get("details") or item.get("transactions")
                    if isinstance(details, list):
                        for detail in details:
                            tx = normalize_transaction(detail, filename, extracted_at)
                            if tx and tx.get("transaction_id"):
                                transactions.append(tx)
                    else:
                        tx = normalize_transaction(item, filename, extracted_at)
                        if tx and tx.get("transaction_id"):
                            transactions.append(tx)
            except json.JSONDecodeError as e:
                print(f"[WARN] JSON parse error line {line_num}: {e}")
                continue
    return transactions

def load_register_jsonl(path: Path) -> list[dict[str, Any]]:
    """Extract register/collection detail with payment method breakdown."""
    registers: list[dict[str, Any]] = []
    if not path.exists():
        return registers
    
    extracted_at = datetime.now(timezone.utc).isoformat()
    
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                # Register format varies: array of payments or wrapped object
                items = payload if isinstance(payload, list) else payload.get("payments", []) or payload.get("register", []) or [payload]
                
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    reg = {
                        "register_id": str(item.get("registerId") or item.get("id") or f"{item.get('date')}_{item.get('patientId')}"),
                        "transaction_id": str(item.get("transactionId") or ""),
                        "patient_id": str(item.get("patientId") or item.get("patient", {}).get("id") or ""),
                        "payment_date": str(item.get("paymentDate") or item.get("date") or "")[:10],
                        "payment_method": str(item.get("paymentMethod") or item.get("method") or item.get("type") or ""),
                        "payment_amount": parse_money(item.get("amount") or item.get("paymentAmount")),
                        "check_number": str(item.get("checkNumber") or item.get("check") or ""),
                        "batch_number": str(item.get("batchNumber") or item.get("batch") or ""),
                        "deposited": bool(item.get("deposited") or item.get("isDeposited")),
                        "source_file": path.name,
                        "extracted_at": extracted_at,
                    }
                    if reg["register_id"]:
                        registers.append(reg)
            except Exception:
                continue
    return registers

def persist_transactions(conn: sqlite3.Connection, transactions: list[dict]) -> int:
    """Upsert transactions with conflict resolution on transaction_id."""
    if not transactions:
        return 0
    
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT INTO sd_transactions_full VALUES (
            :transaction_id, :patient_id, :patient_name, :provider_code, :service_date, :entry_date,
            :ada_code, :description, :amount, :transaction_type, :payment_method, :payment_amount,
            :adjustment_code, :adjustment_amount, :payer, :claim_id, :tooth, :surface, :quantity,
            :original_transaction_id, :source_file, :extracted_at
        )
        ON CONFLICT(transaction_id) DO UPDATE SET
            patient_id=excluded.patient_id,
            patient_name=excluded.patient_name,
            provider_code=excluded.provider_code,
            amount=excluded.amount,
            transaction_type=excluded.transaction_type,
            payment_method=excluded.payment_method,
            payment_amount=excluded.payment_amount,
            adjustment_code=excluded.adjustment_code,
            adjustment_amount=excluded.adjustment_amount,
            payer=excluded.payer,
            extracted_at=excluded.extracted_at
    """, transactions)
    conn.commit()
    return cursor.rowcount

def persist_register(conn: sqlite3.Connection, registers: list[dict]) -> int:
    if not registers:
        return 0
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT INTO sd_register_detail VALUES (
            :register_id, :transaction_id, :patient_id, :payment_date, :payment_method,
            :payment_amount, :check_number, :batch_number, :deposited, :source_file, :extracted_at
        )
        ON CONFLICT(register_id) DO UPDATE SET
            payment_amount=excluded.payment_amount,
            deposited=excluded.deposited,
            extracted_at=excluded.extracted_at
    """, registers)
    conn.commit()
    return cursor.rowcount

def verify_completeness(conn: sqlite3.Connection, trans_path: Path, register_path: Path) -> dict[str, Any]:
    """Generate checksums and variance reports."""
    stats = {
        "file_bytes": trans_path.stat().st_size if trans_path.exists() else 0,
        "jsonl_rows": 0,
        "db_rows": 0,
        "date_range": {"min": None, "max": None},
        "amount_sum": 0.0,
        "variance": None,
    }
    
    # Count JSONL lines (approximate transaction count)
    if trans_path.exists():
        with open(trans_path, "r", encoding="utf-8") as f:
            stats["jsonl_rows"] = sum(1 for _ in f)
    
    # DB aggregates
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), MIN(service_date), MAX(service_date), SUM(amount) FROM sd_transactions_full")
    row = cursor.fetchone()
    if row:
        stats["db_rows"] = row[0]
        stats["date_range"]["min"] = row[1]
        stats["date_range"]["max"] = row[2]
        stats["amount_sum"] = row[3] or 0.0
    
    # Variance vs daysheet totals (if available)
    cursor.execute("""
        SELECT SUM(production) FROM daysheet_totals 
        WHERE period_start BETWEEN ? AND ?
    """, (stats["date_range"]["min"], stats["date_range"]["max"]))
    ds_total = cursor.fetchone()[0]
    if ds_total:
        stats["variance"] = round(stats["amount_sum"] - ds_total, 2)
    
    return stats

def extract_all_transactions(db_path: Path | None = None, force: bool = False) -> dict[str, Any]:
    """Main entry point for full transaction extraction."""
    result = {"ok": False, "transactions": 0, "register": 0, "warnings": []}
    
    db_path = db_path or resolve_analytics_db()
    if not db_path:
        result["warnings"].append("No analytics DB found")
        return result
    
    # Paths
    exports = Path(os.environ.get("SOFTDENT_FINANCIAL_EXPORTS", r"C:\SoftDentFinancialExports"))
    trans_path = exports / "transactions_for_period.jsonl"
    register_path = exports / "register_for_period.jsonl"
    
    conn = sqlite3.connect(db_path)
    try:
        ensure_transactions_schema(conn)
        
        # Extract transactions
        if trans_path.exists():
            txs = load_transactions_jsonl(trans_path)
            result["transactions"] = persist_transactions(conn, txs)
        else:
            result["warnings"].append(f"Missing {trans_path}")
        
        # Extract register
        if register_path.exists():
            regs = load_register_jsonl(register_path)
            result["register"] = persist_register(conn, regs)
        else:
            result["warnings"].append(f"Missing {register_path}")
        
        # Verify
        result["verification"] = verify_completeness(conn, trans_path, register_path)
        result["ok"] = result["transactions"] > 0
        conn.execute("INSERT OR REPLACE INTO _sync_meta (key, value) VALUES ('last_transaction_extract', ?)",
                    (datetime.now(timezone.utc).isoformat(),))
        conn.commit()
    finally:
        conn.close()
    
    return result

if __name__ == "__main__":
    import sys
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    print(extract_all_transactions(db_path=db, force=True))
```

### 3.3 Integration Hook

Add to `import_sync.py` after `ensure_softdent_odbc_fresh()`:

```python
# In import_sync.py::sync_softdent_exports()
from softdent_transaction_extract import extract_all_transactions

def sync_softdent_transactions():
    """Deep transaction extraction beyond daysheet summaries."""
    result = extract_all_transactions(force=True)
    if not result.get("ok"):
        log.warning(f"Transaction extract incomplete: {result.get('warnings')}")
    return result
```

### 3.4 Completeness Proofs

Run this PowerShell to validate row counts and checksums vs Daysheet:

```powershell
# verify_transactions.ps1
$exports = "C:\SoftDentFinancialExports"
$db = "C:\SoftDentFinancialExports\softdent_financial_analytics.db"

# Count JSONL lines (transactions)
$jsonlRows = (Get-Content "$exports\transactions_for_period.jsonl" | Measure-Object).Count

# SQLite counts
$q = "SELECT COUNT(*) FROM sd_transactions_full; SELECT SUM(amount) FROM sd_transactions_full;"
$results = sqlite3 $db $q

Write-Host "JSONL Approx Rows: $jsonlRows"
Write-Host "DB Rows: $($results[0])"
Write-Host "DB Amount Sum: $($results[1])"

# Variance check vs Daysheet
$dsTotal = sqlite3 $db "SELECT SUM(production) FROM daysheet_totals WHERE period_start >= date('now', '-30 days');"
Write-Host "Daysheet 30-day Production: $dsTotal"
```

---

## 4. Paste-Ready Coding Pack (every other domain)

### 4.1 Fix Payment/Adjustment Detection (Critical Patch)

**File:** `NewRidgeFinancial2/softdent_odbc_extract.py`  
Replace `_is_payment()` and `_is_adjustment()` to honor SoftDent v19 codes:

```python
# In softdent_odbc_extract.py, replace existing _is_payment and _is_adjustment:

# Import codes from operational pipeline or define here:
_INSURANCE_PAYMENT_CODES = frozenset({"2"})
_PATIENT_PAYMENT_CODES = frozenset({"11", "12", "17", "48", "60", "61"})
_ALL_PAYMENT_CODES = _INSURANCE_PAYMENT_CODES | _PATIENT_PAYMENT_CODES
_INSURANCE_WRITEOFF_CODES = frozenset({"51", "52"})

def _is_payment(code: str, description: str) -> bool:
    """Detect payments using SoftDent transaction codes."""
    code = str(code or "").strip()
    desc = str(description or "").lower()
    # Code-based detection (primary)
    if code in _ALL_PAYMENT_CODES:
        return True
    # Text fallback for legacy daysheets without codes
    return any(x in desc for x in ["payment", "check", "visa", "mastercard", "amex", "cash"])

def _is_adjustment(code: str, description: str) -> bool:
    """Detect adjustments/write-offs."""
    code = str(code or "").strip()
    desc = str(description or "").lower()
    if code in _INSURANCE_WRITEOFF_CODES:
        return True
    return any(x in desc for x in ["write-off", "writeoff", "adjustment", "adjust", "courtesy", "refund"])
```

### 4.2 Operatory Schedule Parser (New)

**File:** `NewRidgeFinancial2/softdent_operational_pipeline.py` (append)

```python
def load_operatory_schedule(path: Path | None = None) -> list[dict[str, Any]]:
    """Parse operatory_schedule.json from Sensei/DataSync."""
    if path is None:
        roots = _softdent_direct_read_roots()
        for root in roots:
            candidate = Path(root) / "operatory_schedule.json"
            if candidate.exists():
                path = candidate
                break
    if not path or not path.exists():
        return []
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    slots = []
    extracted_at = datetime.now(timezone.utc).isoformat()
    for op in data.get("operatories", []):
        op_name = op.get("operatoryName") or op.get("name")
        for appt in op.get("appointments", []):
            slots.append({
                "operatory": op_name,
                "appointment_id": appt.get("id"),
                "patient_id": appt.get("patientId"),
                "patient_name": appt.get("patientName"),
                "provider_code": appt.get("providerCode"),
                "appt_date": appt.get("date"),
                "start_time": appt.get("startTime"),
                "end_time": appt.get("endTime"),
                "status": appt.get("status"),
                "appointment_type": appt.get("type"),
                "extracted_at": extracted_at,
            })
    return slots

def persist_operatory_schedule(conn: sqlite3.Connection, slots: list[dict]) -> int:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sd_operatory_schedule (
            operatory TEXT,
            appointment_id TEXT PRIMARY KEY,
            patient_id TEXT,
            patient_name TEXT,
            provider_code TEXT,
            appt_date TEXT,
            start_time TEXT,
            end_time TEXT,
            status TEXT,
            appointment_type TEXT,
            extracted_at TEXT
        );
    """)
    if not slots:
        return 0
    conn.executemany("""
        INSERT OR REPLACE INTO sd_operatory_schedule VALUES (
            :operatory, :appointment_id, :patient_id, :patient_name, :provider_code,
            :appt_date, :start_time, :end_time, :status, :appointment_type, :extracted_at
        )
    """, slots)
    conn.commit()
    return len(slots)
```

### 4.3 Discovery Script Extension

**File:** `NewRidgeFinancial2/scripts/discover_softdent_odbc_schema.py` (append to end)

```python
def suggest_transaction_queries(tables: list[str], columns: dict[str, list[str]]) -> dict[str, str]:
    """Generate likely SQL for transaction tables based on column heuristics."""
    suggestions = {}
    
    # Find likely transaction table
    tx_candidates = [t for t in tables if "trans" in t.lower()]
    if tx_candidates:
        tx_table = tx_candidates[0]
        cols = columns.get(tx_table, [])
        col_str = ", ".join(cols[:10])  # First 10 columns as sample
        suggestions["sd_transactions_odbc"] = f"-- Illustrative only; verify columns first\nSELECT {col_str} FROM {tx_table} WHERE Date >= '{{date_start}}'"
    
    # Find fee schedule table
    fee_candidates = [t for t in tables if "fee" in t.lower() or "schedule" in t.lower()]
    if fee_candidates:
        suggestions["sd_fee_schedules"] = f"SELECT * FROM {fee_candidates[0]}"
    
    # Payment plans
    pp_candidates = [t for t in tables if "paymentplan" in t.lower() or "payplan" in t.lower()]
    if pp_candidates:
        suggestions["sd_payment_plans"] = f"SELECT * FROM {pp_candidates[0]}"
    
    return suggestions

# Add to main():
# suggested = suggest_transaction_queries(tables, columns)
# output["suggestedTransactionQueries"] = suggested
```

### 4.4 CSV Report Ingest (Treatment Plans, etc.)

**File:** `NewRidgeFinancial2/softdent_practice_exports.py` (new function)

```python
def ingest_csv_reports_to_sqlite(csv_dir: Path, db_path: Path) -> dict[str, int]:
    """Load treatment_plan_summary, hygiene_recall, case_acceptance CSVs into analytics DB."""
    import csv
    counts = {}
    conn = sqlite3.connect(db_path)
    
    mappings = {
        "treatment_plan_summary.csv": ("treatment_plan_summary", {
            "patient_id": "PatientID", "patient_name": "PatientName", 
            "plan_date": "PlanDate", "total_fee": "TotalFee", "accepted": "Accepted"
        }),
        "hygiene_recall_summary.csv": ("hygiene_recall", {
            "patient_id": "PatientID", "due_date": "DueDate", "status": "Status"
        }),
        "case_acceptance.csv": ("case_acceptance", {
            "patient_id": "PatientID", "presented": "PresentedAmount", "accepted": "AcceptedAmount"
        }),
    }
    
    for filename, (table, colmap) in mappings.items():
        path = csv_dir / filename
        if not path.exists():
            continue
        
        # Create table dynamically (simplified)
        cols_sql = ", ".join([f"{k} TEXT" for k in colmap.keys()] + ["extracted_at TEXT"])
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({cols_sql})")
        
        rows = []
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                db_row = {k: row.get(v, "") for k, v in colmap.items()}
                db_row["extracted_at"] = datetime.now(timezone.utc).isoformat()
                rows.append(db_row)
        
        if rows:
            placeholders = ", ".join([f":{k}" for k in rows[0].keys()])
            conn.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
            counts[table] = len(rows)
    
    conn.commit()
    conn.close()
    return counts
```

---

## 5. Full Domain Checklist (checkbox-style — nothing omitted)

**Core Patient Data**
- [x] Patients (demographics, contact) — Sensei DataSync active (11,969 rows)
- [x] Patient Insurance (primary/secondary) — Sensei JSON embedded
- [x] Patient Notes/Alerts — Sensei JSON (if enabled)
- [x] Guarantor relationships — Sensei JSON

**Clinical**
- [x] Procedures/Production — Sensei (25,757 rows)
- [x] Procedure details (tooth, surface, quadrant) — Sensei
- [x] Clinical Notes (transcription base) — Derived from daysheet
- [ ] Clinical Charting (perio, restorations) — **Unavailable** (requires intraoral API)
- [ ] Images/Radiographs — **Unavailable** (Document Center/COM API only)
- [ ] Treatment Plans (DB table) — **CSV only, needs ingest**
- [ ] Case Acceptance metrics — **CSV only, needs ingest**

**Financial (Deep)**
- [x] Daysheet totals — JSONL active
- [x] Account A/R Aging — JSONL active
- [x] Write-off totals — JSONL active
- [ ] **Transaction Line Items** — JSONL present, parser incomplete (Code Section 3)
- [ ] **Register/Collections Detail** — JSONL present, parser missing (Code Section 3)
- [ ] **Payments (sd_payments)** — Table exists, logic broken (needs patch Section 4.1)
- [ ] **Adjustments (sd_adjustments)** — Table exists, logic broken (needs patch Section 4.1)
- [ ] Patient Ledger (running balance) — **Missing** (needs ODBC or dedicated export)
- [ ] Fee Schedules (UDF/Insurance) — **Missing** (ODBC or report)
- [ ] Payment Plans — **Missing** (ODBC or report)
- [ ] Finance Charges — Daysheet (code detection)

**Scheduling**
- [x] Appointments (past/future) — Sensei (10,868 rows)
- [ ] **Operatory Schedule (grid view)** — File exists, parser missing (Section 4.2)
- [ ] Appointment Reasons/Types — Sensei (if enabled)
- [ ] Hygiene Recall status — **CSV only**

**Insurance/Claims**
- [x] Claims (derived from daysheet) — 60 rows (shallow)
- [ ] Insurance Claims Detail (payer, status, batch) — **Empty** (needs ODBC)
- [ ] Outstanding Claims aging — **Empty**
- [ ] Electronic Claim Status (ECS) — **Unavailable** (clearinghouse dependent)
- [ ] Insurance Reference (carriers) — **Missing**

**Provider/Practice**
- [x] Providers — 42 rows (active)
- [ ] Provider Production Targets — **Missing**
- [ ] Provider Schedules/Availability — **Missing**

**Reference Data**
- [ ] ADA Code Definitions — **Missing**
- [ ] Transaction Code Definitions — **Missing**
- [ ] Insurance Company Master — **Missing**

**Audit/Compliance**
- [x] Daysheet audit trail — JSONL
- [ ] User audit log (who changed what) — **Unavailable** (SoftDent audit log encrypted/binary)
- [ ] Deleted transactions audit — **Unavailable**

---

## 6. Implementation Phases + Acceptance Tests

### Phase 1: MUST (Fix Transaction Completeness) — Target: 24 hours
**Goal:** Achieve 100% transaction capture parity with `transactions_for_period.jsonl`.

1. **Deploy** `softdent_transaction_extract.py` (Section 3.2)
2. **Patch** `softdent_odbc_extract.py` payment/adjustment detection (Section 4.1)
3. **Add** integration hook in `import_sync.py` (Section 3.3)
4. **Run** verification script (Section 3.4)

**Acceptance Test:**
```powershell
# Row count variance < 5%
$jsonl = (Get-Content "C:\SoftDentFinancialExports\transactions_for_period.jsonl" | Measure-Object).Count
$db = sqlite3 softdent_financial_analytics.db "SELECT COUNT(*) FROM sd_transactions_full;"
if ([math]::Abs($jsonl - $db) / $jsonl -lt 0.05) { "PASS" } else { "FAIL" }

# Amount reconciliation to Daysheet
$transSum = sqlite3 softdent_financial_analytics.db "SELECT SUM(amount) FROM sd_transactions_full WHERE transaction_type='Charge';"
$daySum = sqlite3 softdent_financial_analytics.db "SELECT SUM(production) FROM daysheet_totals;"
if ([math]::Abs($transSum - $daySum) -lt 1.00) { "PASS" } else { "FAIL" }
```

### Phase 2: SHOULD (Fill Empty Analytics Tables) — Target: 48 hours
1. **Parse** `operatory_schedule.json` (Section 4.2)
2. **Ingest** CSV reports (treatment plans, hygiene, case acceptance) (Section 4.4)
3. **Configure** ODBC DSN for deep reference data (insurance, fee schedules)

**Acceptance Test:**
- `sd_operatory_schedule` has rows for today's date
- `treatment_plan_summary` table populated from CSV
- `fee_schedules` has rows via ODBC (if configured) or CSV

### Phase 3: NICE (ODBC Deep Dive & Audit) — Target: 1 week
1. Run `discover_softdent_odbc_schema.py` with live DSN
2. Map `sd_insurance_claims`, `sd_payment_plans`, `sd_fee_schedules` via ODBC SQL
3. Implement patient ledger query (read-only)

**Acceptance Test:**
- ODBC `sd_*` tables contain thousands of rows (not just hundreds from daysheet)
- Cross-reference: `sd_claims` (ODBC) matches `transactions.claim_id` > 95%

---

## 7. Risks, PHI, Consent, Rollback

### PHI Safety
- **Read-Only:** All provided code uses `SELECT`, `INSERT` (local SQLite only), no `UPDATE/DELETE` against SoftDent source.
- **Locality:** Sensei JSON and FinancialExports are local filesystem; no network transmission in extraction phase.
- **Encryption:** SQLite analytics DB should reside on encrypted volume (BitLocker) per Kansas dental S-corp policy.

### Consent Gates
- **ODBC Extract:** Already gated behind `NR2_CONSENT_EXECUTOR=1` and `POST /api/admin/extract-softdent-odbc`. Do not bypass.
- **Transaction Extract:** No consent required (local file read), but log extraction timestamps for audit.

### Rollback
- **Code:** All changes are additive (new tables `sd_transactions_full`, `sd_register_detail`, `sd_operatory_schedule`). Original tables untouched.
- **Data:** If `sd_transactions_full` corrupts, drop table and re-run extract (source JSONL preserved).
- **ODBC:** If SQL queries fail, system falls back to existing Sensei/DataSync lane automatically (see `extract_softdent_odbc()` fallback logic).

### Known Limitations
- **SoftDent v19:** Transaction code meanings (2=Insurance Payment, etc.) are hardcoded based on standard SoftDent mapping. If practice customized codes, adjust `_INSURANCE_PAYMENT_CODES` in Section 4.1.
- **Document Center:** No code provided for images/attachments—requires SoftDent COM API or manual export; out of scope for JSON/ODBC lanes.

---

## 8. Operator Next Actions (concrete)

1. **Immediate (Cursor/IDE):**
   - Create `NewRidgeFinancial2/softdent_transaction_extract.py` with code from Section 3.2.
   - Patch `softdent_odbc_extract.py` lines for `_is_payment()` and `_is_adjustment()` (Section 4.1).
   - Append operatory parser to `softdent_operational_pipeline.py` (Section 4.2).

2. **Environment (`.env`):**
   ```env
   # Add to NewRidgeFinancial2/.env
   SOFTDENT_FINANCIAL_EXPORTS=C:\SoftDentFinancialExports
   NR2_FINANCIAL_ANALYTICS_DB=C:\SoftDentFinancialExports\softdent_financial_analytics.db
   # Only if configuring ODBC:
   SOFTDENT_ODBC_DSN=SoftDentReadOnly
   SOFTDENT_ODBC_USER=nr2_reader
   SOFTDENT_ODBC_PASSWORD=<vault_secret>
   NR2_CONSENT_EXECUTOR=1
   ```

3. **Validation (PowerShell):**
   ```powershell
   cd NewRidgeFinancial2
   py -3.14 -c "from softdent_transaction_extract import extract_all_transactions; print(extract_all_transactions(force=True))"
   ```

4. **If ODBC configured:**
   - Run `py scripts/discover_softdent_odbc_schema.py > app_data/softdent_schema.json`
   - Review suggested SQL, paste into `.env` as `SOFTDENT_ODBC_*_QUERY` keys per `MOONSHOT_PHASEF_ODBC_RUNBOOK.md`.

5. **Verify completeness:**
   - Run `verify_transactions.ps1` (Section 3.4) and confirm variance < $1.00 vs Daysheet.

**Stop condition:** When `sd_transactions_full` row count ≥ 90% of `transactions_for_period.jsonl` line count and sum(amount) matches Daysheet production within 0.1%, the mission is complete.