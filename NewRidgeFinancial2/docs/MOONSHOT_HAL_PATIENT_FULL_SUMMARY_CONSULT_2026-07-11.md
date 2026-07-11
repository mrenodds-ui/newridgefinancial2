# Moonshot AI — HAL Patient Full Summary / Mega-Dossier (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Script:** `scripts/run_moonshot_hal_patient_full_summary_consult.py`  
**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.

## Operator request (verbatim)

> ask moonoshot ai how to program hal to give a summary of patient's data and transactional information as well as their treatment notes, claims, everything in one summary.

---

# Verdict — HAL one-patient mega-summary (dossier)

## 0. Operator Intent (quote; consult-only)

> "ask moonoshot ai how to program hal to give a summary of patient's data and transactional information as well as their treatment notes, claims, everything in one summary."

**Interpretation (consult-only):**  
Provide HAL with a **single, staff-gated, auditable command** that assembles a unified patient dossier from local SoftDent-derived stores (demographics, appointments, procedures, payments/adjustments, claims, treatment plans, clinical notes) and renders it as one concise, honest summary using the local 24B model. No cloud PHI exposure. No SoftDent writes. Empty financial fields must remain "unknown," never $0.

---

## 1. Current State Audit (HAL tools, SoftDent stores, clinical notes, claims, tx planning)

| Component | Live State (hal-10494) |
|-----------|------------------------|
| **HAL Discrete Tools** | `read_clinical_summary` (notes), `read_claims_summary` (claims), `lookup_treatment_estimate` (tx estimates), `lookup_fee_schedule`, `join_claim_payers`, `list_eligibility_cache`, `softdent_extract_status`. Each queries a single domain. |
| **SoftDent Stores (Read-Only)** | `sd_patients`, `sd_procedures`, `sd_appointments`, `sd_claims`, `sd_payments`, `sd_adjustments` in local SQLite. Updated via ODBC extract; no write-back. |
| **Clinical Notes** | Imported narrative packs; `fetchClinicalContext` available via `DesktopBridge`. |
| **Treatment Planning** | `softdent_treatment_planning.py` aggregates `sd_insurance_payment_lines` into payer×ADA averages; HAL tool exposes estimates. |
| **Patient Context** | No unified "dossier" API. Staff must ask HAL separate questions for notes, claims, tx, etc. |
| **Audit / Gating** | Generic HAL session logging exists; no per-patient query audit or `patient_dossier` permission check. |
| **Local AI** | Single 24B (Q4_K_M) on R9700 loopback. Cloud models off by default. |

---

## 2. Gap Map

| Area | Status | Gap | Effort | Depends on |
|------|--------|-----|--------|------------|
| **Unified Dossier API** | Missing | No loopback endpoint joins patients, transactions, procedures, appointments, claims, notes, and tx estimates into one JSON structure. | M | Existing stores |
| **HAL Orchestrator Tool** | Missing | No `summarize_patient_dossier` tool in `hal-agent.js` to fetch dossier + prompt local 24B. | S | Dossier API |
| **Empty≠$0 Enforcement** | Partial | Discrete tools handle honesty individually; dossier builder must centralize "unknown" substitution for all financial fields. | S | Dossier API |
| **Staff Gate + Audit** | Partial | No RBAC role `hal:patient-dossier:read` or `hal_patient_query_audit` table. | S | Auth context |
| **Local Summarization Prompt** | Missing | No tested prompt template for 24B to render multi-section dossiers without hallucination. | S | 24B inference |

---

## 3. Target Design — "everything in one summary"

### 3A Meaning of mega-summary (sections, honesty rules, what is excluded)

**Sections (always present, may be empty):**
1. **Demographics** — Patient hash/initials, practice ID, first/last visit dates (SoftDent), age range (not full DOB unless gated).
2. **Appointment Timeline** — Last 3 visits + next scheduled (from `sd_appointments`).
3. **Procedure History** — Recent ADA codes, teeth, surfaces, providers (from `sd_procedures`).
4. **Transactional Ledger** — Payments and adjustments (last 12 mo). **Honesty:** `NULL`, `0`, or missing → string `"unknown"`; never `$0.00`.
5. **Claims Summary** — Open/pending/denied claims with amounts, payer, status, narrative draft status (from `sd_claims` + `read_claims_summary` logic).
6. **Treatment Estimates** — Active tx plan lines with payer-specific estimates where available; empty estimate → `"unknown"`.
7. **Clinical Notes** — Last 3–5 narrative summaries (from `read_clinical_summary` logic).

**Honesty Rules:**
- SoftDent is read-only; summary is a **reflection** of extracted data, not a new source of truth.
- Financial fields without source data render as `"unknown"` or `"—"`.
- No inferred insurance benefits; only stored `sd_insurance_payment_lines` averages surfaced via existing `lookup_treatment_estimate`.

**Excluded (unless explicitly gated):**
- Full SSN, full DOB, full patient name in the initial HAL utterance (hashes/initials only).
- Raw cloud transmission of the dossier JSON (summarization must happen locally).

### 3B Tool/API orchestration (existing tools vs new summarize_patient_dossier)

**Recommendation:** Introduce **one new orchestrator** (`summarize_patient_dossier`) because composition of 6+ discrete HAL tools in the browser would require multiple round-trips and complicate "empty≠$0" consistency across domains.

**Architecture:**
```
HAL Chat ("Summarize patient A3F9")
    ↓
hal-agent.js → summarize_patient_dossier tool
    ↓
DesktopBridge.fetchPatientDossier(patientId)  [NEW]
    ↓
GET /api/apex/patient-dossier/{patientId}  [NEW endpoint]
    ↓
build_patient_dossier()  [NEW server-side]
    ├── sd_patients, sd_appointments, sd_procedures
    ├── sd_payments + sd_adjustments (txn)
    ├── sd_claims (claims)
    ├── clinical notes (local SQLite)
    └── treatment_planning_estimates (existing table)
    ↓
Returns JSON dossier (structured)
    ↓
HAL prompts local Ollama 24B with DOSSIER_SUMMARY_PROMPT
    ↓
Structured markdown reply to staff
```

**Reuse of existing tools:**  
`build_patient_dossier` will internally call the same SQL/helpers underlying `read_clinical_summary`, `read_claims_summary`, and `lookup_treatment_estimate`, but co-locates the joins so HAL makes one call, not six.

### 3C UX sketch (HAL chat utterance → gated fetch → structured reply; optional OM dossier)

1. **Staff Intent**  
   Type: `"HAL, summarize patient A3F9"` or click **"HAL Dossier"** button on OM patient card.

2. **Gate Check**  
   HAL verifies `window.NR2AuthContext.permissions.includes('hal:patient-dossier:read')`.  
   If missing → reply: *"You do not have permission to request patient dossiers. Contact office manager."*

3. **Audit Log**  
   HAL logs to `hal_patient_query_audit` (patient_hash, staff_id, timestamp, session_id, intent='dossier_summary').

4. **Fetch**  
   `DesktopBridge.fetchPatientDossier('A3F9')` → loopback server (no cloud).

5. **Summarize**  
   Server returns JSON dossier (~2–4KB). HAL posts to `http://127.0.0.1:11434/api/generate` (24B) with prompt:
   ```
   You are a dental practice assistant. Summarize the following patient dossier for staff.
   Rules:
   - Use 'unknown' for any missing financial value. Never write $0.
   - Do not invent insurance coverage.
   - Use concise bullets.
   Dossier: {{json}}
   ```

6. **Reply**  
   HAL returns markdown:
   ```
   **Patient A3F9 — Dossier Summary**
   - Demographics: ...
   - Last Visit: ...
   - Open Claims: ...
   ```

7. **OM Widget (Optional)**  
   Widget `patient-dossier-card` can display the same JSON (unedited) for staff who prefer scanning raw fields; HAL summary remains the default view.

### 3D Staff gate + audit trail (who can ask, what is logged, PHI display)

| Control | Implementation |
|---------|----------------|
| **Permission** | RBAC role `hal:patient-dossier:read` (default: Dentist, Office Manager, Insurance Coordinator). Hygienists/Receptionists may be excluded by policy. |
| **Patient ID Display** | HAL utterances use 4-char hash (`A3F9`). Full name revealed only after gate click, logged separately. |
| **Audit Table** | `hal_patient_query_audit` (id, staff_id, patient_hash, query_type, timestamp, ip/session). Retention: 7 years (HIPAA). |
| **Data Residency** | Dossier JSON never leaves loopback. 24B model runs on R9700. Cloud models explicitly disabled for this tool. |
| **Rate Limit** | Max 1 dossier request per 10 seconds per staff session to prevent scraping. |

---

## 4. Coding Plan by Phase (files · paste-ready sketches · validation)

### Phase 1: Dossier API (Server)

**File:** `nr2_server/apex/patient_dossier.py` (new)
```python
"""Assemble unified patient dossier from SoftDent stores. READ-ONLY. Empty≠$0."""
from __future__ import annotations
import sqlite3
from typing import Any, Dict, List
from datetime import datetime, timedelta

DB_PATH = "analytics/softdent_analytics.db"

def _safe_money(val) -> str:
    if val is None or val == "" or val == 0:
        return "unknown"
    try:
        return f"${float(val):.2f}"
    except Exception:
        return "unknown"

def build_patient_dossier(patient_id: str, practice_id: str = "default") -> Dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    dossier = {
        "patient_id": patient_id,
        "practice_id": practice_id,
        "generated_at": datetime.utcnow().isoformat(),
        "demographics": {},
        "appointments": [],
        "procedures": [],
        "transactions": {"payments": [], "adjustments": []},
        "claims": [],
        "clinical_notes": [],
        "treatment_estimates": []
    }

    # Demographics
    cur.execute("""
        SELECT patient_name, first_visit_date, last_visit_date
        FROM sd_patients WHERE patient_id=? AND practice_id=?
    """, (patient_id, practice_id))
    row = cur.fetchone()
    if row:
        dossier["demographics"] = {
            "name_hash": hashlib.sha256(row["patient_name"].encode()).hexdigest()[:4].upper(),
            "first_visit": row["first_visit_date"] or "unknown",
            "last_visit": row["last_visit_date"] or "unknown"
        }

    # Appointments (last 3 + next 2)
    cur.execute("""
        SELECT appt_date, provider_code, status FROM sd_appointments
        WHERE patient_id=? AND practice_id=? ORDER BY appt_date DESC LIMIT 5
    """, (patient_id, practice_id))
    dossier["appointments"] = [dict(r) for r in cur.fetchall()]

    # Procedures (last 5)
    cur.execute("""
        SELECT proc_date, ada_code, tooth, surface, provider_code, description, production
        FROM sd_procedures
        WHERE patient_id=? AND practice_id=? ORDER BY proc_date DESC LIMIT 5
    """, (patient_id, practice_id))
    for r in cur.fetchall():
        dossier["procedures"].append({
            "date": r["proc_date"],
            "ada": r["ada_code"],
            "tooth": r["tooth"],
            "surface": r["surface"],
            "provider": r["provider_code"],
            "production": _safe_money(r["production"])
        })

    # Transactions (last 12 months)
    since = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")
    cur.execute("""
        SELECT payment_date, amount, payer, method FROM sd_payments
        WHERE patient_id=? AND practice_id=? AND payment_date >= ?
        ORDER BY payment_date DESC LIMIT 10
    """, (patient_id, practice_id, since))
    for r in cur.fetchall():
        dossier["transactions"]["payments"].append({
            "date": r["payment_date"],
            "amount": _safe_money(r["amount"]),
            "payer": r["payer"] or "unknown",
            "method": r["method"] or "unknown"
        })

    # Claims
    cur.execute("""
        SELECT claim_id, payer, service_date, claim_amount, claim_status
        FROM sd_claims WHERE patient_id=? AND practice_id=?
        ORDER BY service_date DESC LIMIT 10
    """, (patient_id, practice_id))
    for r in cur.fetchall():
        dossier["claims"].append({
            "claim_id": r["claim_id"],
            "payer": r["payer"] or "unknown",
            "service_date": r["service_date"],
            "amount": _safe_money(r["claim_amount"]),
            "status": r["claim_status"] or "unknown"
        })

    # Clinical notes (via existing helper pattern)
    cur.execute("""
        SELECT note_date, summary FROM clinical_note_imports
        WHERE patient_id=? ORDER BY note_date DESC LIMIT 5
    """, (patient_id,))
    dossier["clinical_notes"] = [dict(r) for r in cur.fetchall()]

    conn.close()
    return dossier
```

**File:** `nr2_server/api/apex_routes.py` (add route)
```python
from nr2_server.apex.patient_dossier import build_patient_dossier
from nr2_server.apex.audit_logger import log_patient_query  # Phase 2

@app.route('/api/apex/patient-dossier/<patient_id>', methods=['GET'])
@require_permission('hal:patient-dossier:read')
def api_patient_dossier(patient_id):
    staff_id = get_current_staff_id()  # from JWT/session
    log_patient_query(staff_id, patient_id, 'dossier')
    dossier = build_patient_dossier(patient_id)
    return jsonify({"ok": True, "dossier": dossier})
```

**Validation:**  
```powershell
python -c "from nr2_server.apex.patient_dossier import build_patient_dossier; import json; print(json.dumps(build_patient_dossier('TEST123'), indent=2))"
# Verify no $0.00 appears where SoftDent has NULL.
```

### Phase 2: Audit Logger

**File:** `nr2_server/apex/audit_logger.py` (new or extend)
```python
import sqlite3, time
AUDIT_DB = "analytics/nr2_audit.db"

def init_audit():
    conn = sqlite3.connect(AUDIT_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hal_patient_query_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id TEXT NOT NULL,
            patient_hash TEXT NOT NULL,
            query_type TEXT,
            timestamp REAL,
            session_id TEXT
        )
    """)
    conn.commit(); conn.close()

def log_patient_query(staff_id: str, patient_id: str, query_type: str, session_id: str = ""):
    conn = sqlite3.connect(AUDIT_DB)
    conn.execute("""
        INSERT INTO hal_patient_query_audit (staff_id, patient_hash, query_type, timestamp, session_id)
        VALUES (?,?,?,?,?)
    """, (staff_id, patient_id, query_type, time.time(), session_id))
    conn.commit(); conn.close()
```

### Phase 3: HAL Tool + Desktop Bridge

**File:** `site/hal-agent.js` (add tool)
```javascript
summarize_patient_dossier: {
  label: "Summarize patient dossier (data + tx + notes + claims)",
  run: async (ctx, args) => {
    const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
    if (!bridge || typeof bridge.fetchPatientDossier !== "function") {
      return { ok: false, summary: "Patient dossier requires NR2 loopback server." };
    }
    const patientId = String(args.patientId || args.query || "").trim();
    if (!patientId) return { ok: false, summary: "Provide patientId." };
    
    // Gate check (pseudo-code; align with NR2AuthContext)
    if (!window.NR2AuthContext?.permissions?.includes('hal:patient-dossier:read')) {
      return { ok: false, summary: "Permission denied: patient dossier." };
    }

    const data = await bridge.fetchPatientDossier(patientId);
    if (!data || !data.dossier) return { ok: false, summary: "Dossier unavailable." };
    
    // Local 24B summarization
    const prompt = `You are a dental practice assistant. Summarize the following patient dossier for staff.
Rules:
- Use 'unknown' for missing financial values. Never invent $0.
- Do not hallucinate insurance benefits.
- Keep to 8-10 bullet points.

Dossier JSON:
${JSON.stringify(data.dossier, null, 2)}`;
    
    const reply = await ctx.localGenerate(prompt); // assumes ctx.localGenerate calls Ollama 24B
    return { ok: true, summary: reply.text, patientId };
  },
},
```

**File:** `desktop/bridge.py` (or relevant DesktopBridge impl)
```python
def fetchPatientDossier(self, patient_id: str):
    resp = requests.get(f"https://127.0.0.1:{self.port}/api/apex/patient-dossier/{patient_id}",
                        headers=self.headers, verify=self.ssl_verify)
    resp.raise_for_status()
    return resp.json()
```

### Phase 4: Prompt Engineering & Tests

**File:** `nr2_server/apex/prompts.py` (new)
```python
DOSSIER_SUMMARY_PROMPT = """You are NR2-HAL, a dental practice assistant. Produce a concise patient dossier summary.

STRICT RULES:
1. If a financial field is missing, null, or 0, output the word 'unknown'. Never output $0.00.
2. Do not invent insurance coverage details not present in the data.
3. Use clear headers: Demographics, Appointments, Procedures, Transactions, Claims, Notes.
4. Keep total response under 400 tokens.

DATA:
{dossier_json}
"""
```

**Validation:**  
```powershell
python -m unittest test_patient_dossier.py -v
# Tests: empty money fields return "unknown", no $0; audit log writes; 24B generates within 2s on R9700.
```

---

## 5. MUST / SHOULD / NICE ranked table

| Priority | Item | Phase |
|----------|------|-------|
| **MUST** | `build_patient_dossier` server function with `empty≠$0` enforcement (replace null/0 with "unknown") | 1 |
| **MUST** | Loopback endpoint `GET /api/apex/patient-dossier/{id}` with RBAC gate `hal:patient-dossier:read` | 1 |
| **MUST** | `summarize_patient_dossier` HAL tool in `hal-agent.js` using local 24B only | 3 |
| **MUST** | Audit table `hal_patient_query_audit` logging every patient-specific dossier request | 2 |
| **SHOULD** | Prompt template `DOSSIER_SUMMARY_PROMPT` optimized for 24B (tested for 8-10 bullet fidelity) | 4 |
| **SHOULD** | DesktopBridge method `fetchPatientDossier` wiring | 3 |
| **SHOULD** | Unit tests verifying `$0` never appears when source is empty | 4 |
| **NICE** | OM widget `patient-dossier-card` displaying raw JSON for power users | 4 |
| **NICE** | 5-minute server-side cache of dossier JSON to reduce DB load | 2 |
| **NICE** | Dossier export to PDF (local print-to-PDF) from OM widget | 4 |

---

## 6. Risks, PHI, SoftDent honesty, Rollback

| Risk | Mitigation |
|------|------------|
| **PHI Exposure** | Dossier never leaves loopback. Cloud models explicitly bypassed for this tool. Audit logs capture who queried what patient hash. |
| **SoftDent Write** | Code review: only `SELECT` statements in `build_patient_dossier`. No `INSERT/UPDATE/DELETE`. |
| **Empty≠$0 Violation** | Centralized `_safe_money()` helper converts `None`, `""`, `0` → `"unknown"`. Unit tests assert no `"$0.00"` in output when input is falsy. |
| **24B Hallucination** | Strict prompt rules + low temperature (0.1) for summarization. Dossier JSON provided as context, not training. |
| **Unauthorized Access** | RBAC gate on API route; HAL tool checks permission before fetch; audit log non-repudiable. |
| **Performance** | Dossier query joins 5 tables; limit 5–10 rows per section. Add index on `sd_appointments(patient_id, appt_date)` if slow. |

**Rollback Plan:**
1. Revert `hal-agent.js` (remove `summarize_patient_dossier` tool).
2. Revert `apex_routes.py` (remove `/api/apex/patient-dossier` route).
3. Drop `hal_patient_query_audit` table if migration was applied (or keep for compliance).
4. Restart loopback server; HAL falls back to discrete tools only.

---

## 7. Approval Checklist

- [ ] **Operator confirms** the 7-section dossier definition (3A) matches "everything in one summary" intent.
- [ ] **Staff roles defined**: Who receives `hal:patient-dossier:read`? (Dentist, OM, Insurance Coordinator default?)
- [ ] **Audit retention**: Confirm 7-year retention policy for `hal_patient_query_audit`.
- [ ] **SoftDent honesty**: Confirm `_safe_money` logic (empty → "unknown") is acceptable for financial summaries.
- [ ] **Local AI only**: Confirm 24B summarization is sufficient (no cloud fallback desired).
- [ ] **Proceed authorized**: Reply "approve / proceed" to begin Phase 1 coding.

**DO NOT APPLY** until operator says *approve / proceed*.