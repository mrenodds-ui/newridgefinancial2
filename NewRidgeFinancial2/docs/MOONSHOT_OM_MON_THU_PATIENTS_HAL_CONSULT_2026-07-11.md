# Moonshot AI — OM Mon–Thu Patients + Expanded Surfaces + HAL Patient Access (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Script:** `scripts/run_moonshot_om_mon_thu_patients_hal_consult.py`  
**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.

## Operator request (verbatim)

> ask moonshot how to program and code in the ofice manager page a list of patients sheduled from Monday to Thurdays and how to display them in a widget with information.  Also how to expland treatment planning, patient information clindical notes and claim reviews.  also how hal has total access to a patients data such as insurance clincial notes if we asked him about a patient

---

# Verdict — OM Mon–Thu schedule + expanded patient surfaces + HAL patient access

## 0. Operator Intent (quote; consult-only)

> "ask moonshot how to program and code in the ofice manager page a list of patients sheduled from Monday to Thurdays and how to display them in a widget with information. Also how to expland treatment planning, patient information clindical notes and claim reviews. also how hal has total access to a patients data such as insurance clincial notes if we asked him about a patient"

**Interpretation (consult-only):**  
A) Build a Monday–Thursday appointment **list** widget (distinct from the existing daily operatory board) that surfaces useful scheduling information.  
B) Expand OM surfaces for treatment planning, patient demographics, clinical note packs, and claim review details.  
C) Enable HAL to answer staff questions about a **specific** patient by giving it controlled, auditable, local-only access to that patient’s insurance and clinical data when staff explicitly selects the patient.

---

## 1. Current State Audit (OM schedule, tx planning, clinical notes, claims, HAL tools)

| Component | Live State (hal-10494) |
|-----------|------------------------|
| **OM Daily Schedule** | `appointments_today_snapshot()` + `build_operatory_board()` shipped. Uses `sd_appointments` (provider-as-chair, no operatory/time columns). Displays 4-char SHA256 patient hashes. |
| **Treatment Planning** | `softdent_treatment_planning.py` ingests insurance payments + ADA codes. HAL tool `lookup_treatment_estimate` available. No OM widget yet. |
| **Clinical Notes** | SoftDent narrative packs imported to local SQLite. HAL tool `read_clinical_summary` exists. No OM viewer. |
| **Claims** | `build_claims_needing_narrative` queue widget exists. HAL tool `draft_insurance_narrative` exists. No detail drill-down. |
| **Patient Data** | `sd_patients`, `sd_claims`, `sd_insurance_payment_lines` in analytics DB. No unified “dossier” API. |
| **HAL Architecture** | Single 24B local (Q4_K_M) on loopback. Tools: `read_clinical_summary`, `draft_insurance_narrative`, `lookup_treatment_estimate`, `read_claims_summary`, `softdent_extract_status`. No per-patient context setter. |
| **PHI Policy** | Local-only AI; widgets display hashes/initials by default; SoftDent read-only forever. |

---

## 2. Gap Map

| Area | Status | Gap | Effort | Depends on |
|------|--------|-----|--------|------------|
| **Mon–Thu Schedule List** | Partial | Only single-day snapshot exists; no multi-day list view; no “week-at-a-glance” OM widget. | M | `sd_appointments` date-range query |
| **Patient Info Surface** | Missing | No unified patient card/dossier in OM; demographics isolated in `sd_patients`. | M | Patient lookup API |
| **Treatment Planning Surface** | Partial | Backend HAL tool exists; no OM widget surfacing active tx plans or estimates. | S | Dossier join |
| **Clinical Notes Surface** | Partial | Narrative packs stored locally; no OM viewer widget. | S | Text rendering widget |
| **Claim Reviews Surface** | Partial | Queue exists; no detail view (amount, status history, narrative status). | S | Claims detail API |
| **HAL Patient Dossier** | Partial | Tools read tables but lack “selected patient” context; no audit log for patient-specific queries. | M | Context management + audit table |

---

## 3. Target Design

### 3A OM Mon–Thu scheduled patients widget (fields, PHI display rules)

**Widget ID:** `weekly-schedule-list`  
**Type:** `schedule-list` (table/card hybrid)  
**Size:** `xl` (full-width)  
**Page:** `office-manager`

**Data Model:**
- Query `sd_appointments` for dates between next Monday and Thursday (or configurable start).
- Join `sd_patients` for name (hashed) and type.
- Group by `appt_date` → ordered list of days.

**Display Fields (PHI-safe by default):**
| Field | Display Rule |
|-------|--------------|
| Day/Date | Full date (e.g., “Mon 07/14”) |
| Time | If available in narrative/appt notes; else “—” |
| Patient | 4-char hash (e.g., `A3F9`) or initials; full name gated behind click |
| Provider | `provider_code` from `sd_appointments` |
| Status | Normalized status (booked/checked-in/completed/open) |
| Procedure Hint | Short ADA code or description if available in sync |

**Interactivity:**
- Click patient hash → opens **Patient Dossier Modal** (sets HAL context).
- Empty day → honest message: “No SoftDent appointments for [Date].”

**API Endpoint:**
```
GET /api/softdent/appointments-range?start=2026-07-14&days=4
```

### 3B Expand treatment planning / patient info / clinical notes / claim reviews

**Treatment Planning Expansion:**
- **Widget:** `active-treatment-plans` (OM sidebar)
- **Data:** `softdent_treatment_planning` table filtered by selected patient.
- **Display:** Procedure code, estimate range (InsCo avg), insurance coverage %, patient portion.
- **HAL Integration:** Button “Estimate with HAL” calls `lookup_treatment_estimate` with patient’s insurance context.

**Patient Information Expansion:**
- **Widget:** `patient-dossier-mini` (appears when patient selected)
- **Fields:** Age/gender (hashed), primary insurance (carrier name only, no policy #), account balance (if available; empty ≠ $0), last visit date.
- **Security:** No SSN, full DOB, or full address displayed in widget; available to HAL only via tool after staff query.

**Clinical Notes Expansion:**
- **Widget:** `clinical-notes-summary`
- **Data:** SoftDent narrative packs (imported text) for selected patient, last 5 notes.
- **HAL Integration:** “Summarize notes” button calls `read_clinical_summary`.

**Claim Reviews Expansion:**
- **Widget:** `claim-review-detail` (enhances existing queue)
- **Data:** `sd_claims` joined with narrative status.
- **Fields:** Claim ID (hashed), service date, payer, claim amount (empty if unknown), status, narrative drafted (Y/N).
- **Action:** “Draft narrative” → HAL tool `draft_insurance_narrative`.

### 3C HAL patient dossier access model (tools, consent, audit, what HAL may/may not say)

**Access Model:** *Staff-Gated Contextual Retrieval*

1. **Selection Gate:** Staff must explicitly click a patient in the OM widget to “Ask HAL about this patient.” This sets an in-memory context token (`current_patient_id`) for that session/tab only.
2. **Local-Only Constraint:** HAL queries ONLY local SQLite stores (`sd_patients`, `sd_claims`, `sd_clinical_notes`, `softdent_treatment_planning`) via loopback Ollama. No cloud export.
3. **Tool Set:** When patient context is set, HAL gains access to:
   - `read_patient_summary(patient_id)` – demographics, insurance summary
   - `read_clinical_summary(patient_id)` – narrative notes
   - `read_insurance_claims(patient_id)` – claim history
   - `lookup_treatment_estimate(patient_id, ada_code)` – tx planning with patient’s InsCo
4. **Audit Trail:** Every patient-specific HAL query logs to `hal_patient_audit` table:
   - `user_id`, `patient_hash`, `timestamp`, `tools_invoked`, `query_summary` (sanitized).
5. **What HAL May Say:**
   - Summarize clinical notes in plain language.
   - Explain insurance benefits based on payment line history.
   - Draft narratives using claim + clinical data.
   - State when data is missing (SoftDent honesty).
6. **What HAL May NOT Say:**
   - Provide full SSN, DOB, or policy numbers in chat (stored locally but restricted).
   - Invent dollar amounts (tools return `null` if no data).
   - Retain patient context after logout/page change (ephemeral).

**PHI Display Rules:**
- Widgets: hashes/initials only.
- HAL Chat: Staff sees their own query + HAL’s answer; underlying PHI is referenced via tools but not echoed back unless explicitly requested and permitted by role.

---

## 4. Coding Plan by Phase (files · paste-ready sketches · validation)

### Phase 1: Mon–Thu List Widget Backend + API

**File:** `NewRidgeFinancial2/nr2_softdent_daily.py`
```python
def appointments_range_snapshot(
    start_iso: str,
    days: int = 4,
) -> dict[str, Any]:
    """Multi-day appointment list for OM (Mon–Thu). PHI-safe hashes.
    
    Args:
        start_iso: ISO date (e.g., '2026-07-14')
        days: Number of days to fetch (default 4 for Mon–Thu)
    """
    from datetime import datetime, timedelta
    import hashlib

    conn, db_path = _open_db()
    if not conn:
        return {"hasData": False, "days": [], "source": "none"}

    try:
        cursor = conn.cursor()
        start_dt = datetime.fromisoformat(start_iso[:10])
        dates = [(start_dt + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
        
        placeholders = ",".join("?" * len(dates))
        sql = f"""
        SELECT a.appt_date, a.patient_id, a.provider_code, a.status,
               p.first_name, p.last_name
        FROM sd_appointments a
        LEFT JOIN sd_patients p ON a.patient_id = p.patient_id
        WHERE a.appt_date IN ({placeholders})
        ORDER BY a.appt_date, a.provider_code
        """
        cursor.execute(sql, dates)
        rows = cursor.fetchall()

        days_out = []
        for d in dates:
            day_rows = [r for r in rows if r[0] == d]
            slots = []
            for r in day_rows:
                patient_raw = f"{r[4] or ''}{r[5] or ''}".strip()
                slots.append({
                    "patientHash": _hash_patient_id(r[1]),
                    "initials": _initials(patient_raw),
                    "provider": r[2],
                    "status": _normalize_appt_status(r[3]),
                    "time": "—",  # SoftDent schema lacks time; honest placeholder
                })
            days_out.append({
                "date": d,
                "dayName": datetime.fromisoformat(d).strftime("%a"),
                "slots": slots,
                "count": len(slots),
            })

        return {
            "hasData": any(d["count"] > 0 for d in days_out),
            "days": days_out,
            "dateRange": f"{dates[0]} to {dates[-1]}",
            "source": "sd_appointments",
        }
    finally:
        conn.close()
```

**File:** `NewRidgeFinancial2/apex_missing_widgets_pack.py`
```python
def build_weekly_schedule_list(
    bundle: dict[str, Any],
    live_range: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """OM widget: Mon–Thu patient list (PHI-safe)."""
    data = live_range if (live_range and live_range.get("hasData")) else {"days": [], "hasData": False}
    
    return _wrap(
        widget_id="weekly-schedule-list",
        type_="schedule-list",
        title="This Week’s Schedule (Mon–Thu)",
        page="office-manager",
        size="xl",
        status="ok" if data.get("hasData") else "empty",
        data={
            "days": data.get("days", []),
            "dateRange": data.get("dateRange", ""),
            "emptyMessage": "No appointments found for Mon–Thu — verify SoftDent sync.",
        },
        hint="Multi-day schedule view; click patient hash to open dossier.",
        collapse_when_empty=False,
    )
```

**File:** `NewRidgeFinancial2/site/app.js` (OM prefetch block)
```javascript
// Inside office-manager page init
if (page.id === "office-manager") {
  // Existing today fetch
  NR2SoftdentDaily.prefetchTodayForOM();
  
  // NEW: Mon–Thu fetch
  const monday = getMonday(new Date()).toISOString().split('T')[0];
  fetch(`/api/softdent/appointments-range?start=${monday}&days=4`)
    .then(r => r.json())
    .then(data => window.NR2_OM_WEEKLY_SCHEDULE = data);
}
```

**Validation:**
```powershell
python -m unittest test_appointments_range.py -v
# Test: 4 days returned, hashes present, empty days honest, no PII in JSON
```

### Phase 2: Patient Dossier + Expanded Surfaces

**File:** `NewRidgeFinancial2/om_patient_dossier.py` (new)
```python
"""Unified patient dossier for OM — local SQLite joins, PHI-safe exports."""

def get_patient_dossier(patient_id: str) -> dict[str, Any]:
    """Returns patient summary, insurance, active tx, recent claims.
    All identifiers hashed for widget display."""
    conn = _open_db()[0]
    try:
        cur = conn.cursor()
        # Demographics (hashed)
        cur.execute("SELECT first_name, last_name, dob FROM sd_patients WHERE patient_id=?", (patient_id,))
        row = cur.fetchone()
        if not row:
            return {"error": "Patient not found"}
        
        initials = _initials(f"{row[0] or ''}{row[1] or ''}")
        dob_year = str(row[2])[:4] if row[2] else None
        
        # Insurance (carrier only)
        cur.execute("SELECT payer FROM sd_insurance_payment_lines WHERE patient_id=? LIMIT 1", (patient_id,))
        ins = cur.fetchone()
        
        # Active claims count
        cur.execute("SELECT COUNT(*) FROM sd_claims WHERE patient_id=? AND claim_status NOT IN ('closed','paid')", (patient_id,))
        open_claims = cur.fetchone()[0]
        
        return {
            "patientHash": _hash_patient_id(patient_id),
            "initials": initials,
            "dobYear": dob_year,  # Partial only
            "primaryCarrier": ins[0] if ins else None,
            "openClaims": open_claims,
            "hasClinicalNotes": _check_clinical_notes_exist(patient_id),
        }
    finally:
        conn.close()
```

**Widgets to add in `apex_missing_widgets_pack.py`:**
- `build_patient_dossier_card(dossier)` – Info card
- `build_treatment_plan_mini(patient_id)` – Calls `softdent_treatment_planning` lookup
- `build_claims_review_detail(patient_id)` – Filtered `sd_claims` list

### Phase 3: HAL Patient Context + Audit

**File:** `NewRidgeFinancial2/hal-agent.js`
```javascript
// Patient context (ephemeral, per tab)
let omPatientContext = null;

function setOMPatientContext(patientId) {
  omPatientContext = patientId;
  // Audit log via beacon
  navigator.sendBeacon('/api/audit/hal-context', JSON.stringify({
    patientHash: hashPatientId(patientId),
    timestamp: new Date().toISOString(),
    action: 'set_context'
  }));
}

const HAL_TOOLS = {
  // ... existing tools ...
  
  read_patient_summary: async () => {
    if (!omPatientContext) return {error: "No patient selected in OM"};
    return await callLocalSql('get_patient_dossier', {patient_id: omPatientContext});
  },
  
  read_clinical_summary: async () => {
    if (!omPatientContext) return {error: "No patient selected"};
    return await callLocalTool('read_clinical_summary', {patient_id: omPatientContext});
  },
  
  clear_patient_context: () => {
    omPatientContext = null;
    return {status: "cleared"};
  }
};
```

**Audit Table Schema** (SQLite):
```sql
CREATE TABLE hal_patient_audit (
    id INTEGER PRIMARY KEY,
    user_id TEXT,
    patient_hash TEXT NOT NULL,
    action TEXT, -- 'set_context', 'query_summary', 'draft_narrative'
    tools_used TEXT, -- JSON array
    timestamp TEXT,
    ip TEXT
);
```

**Validation:**
```powershell
python -m unittest test_hal_patient_context.py -v
# Test: context sets, audit writes, clear on logout, no PHI in HAL chat payload
```

---

## 5. MUST / SHOULD / NICE ranked table

| Priority | Item | Justification |
|----------|------|---------------|
| **MUST** | Mon–Thu list widget with PHI hashes | Core operator request; extends existing OM-A0 pattern |
| **MUST** | HAL patient context setter + audit | Required for "total access" to be compliant (staff-gated, auditable) |
| **MUST** | Local-only enforcement | Cloud/OpenAI off by default; tools reject if cloud flag detected |
| **SHOULD** | Patient dossier mini-widget | Unifies demographics, insurance, open claims for OM efficiency |
| **SHOULD** | Treatment plan estimate surface | Leverages existing HAL tool; reduces staff clicks to SoftDent |
| **SHOULD** | Claims review detail view | Completes existing narrative queue with actionable data |
| **NICE** | Clinical notes viewer widget | Searchable narrative packs (can be deferred to HAL chat only) |
| **NICE** | Provider filter on Mon–Thu list | UX enhancement for multi-provider practices |
| **NICE** | Print-friendly schedule PDF | Export for front-desk walk-around |

---

## 6. Risks, PHI, SoftDent Honesty, Rollback

**Risks & Mitigations:**
- **PHI Leak in Widgets:** Mitigation: Strict use of 4-char hashes; full names only in gated modal with role check.
- **HAL Context Confusion:** Mitigation: Visual “Patient Context: [Hash]” indicator in HAL chat UI; auto-clear after 15 min inactivity.
- **Audit Bypass:** Mitigation: `sendBeacon` for context changes; server-side validation that HAL tools only accept server-verified context tokens.
- **SoftDent Schema Mismatch:** `sd_appointments` lacks `appt_time`; widget displays “—” honestly rather than inventing times.

**SoftDent Honesty:**
- Empty appointment days render “No appointments — verify SoftDent sync” rather than $0 or fake data.
- Treatment estimates return `{"estimate": null, "reason": "Insufficient sample size"}` when `MIN_SAMPLE_SIZE` not met.
- Insurance balances display as “unavailable” if not in SQLite (never assumed $0).

**Rollback Plan:**
1. Revert `nr2_softdent_daily.py` (remove `appointments_range_snapshot`).
2. Revert `apex_missing_widgets_pack.py` (remove `build_weekly_schedule_list` and dossier widgets).
3. Revert `site/app.js` (remove Mon–Thu prefetch).
4. Drop `hal_patient_audit` table if created (optional; keep for records).
5. `git checkout --` affected files or revert commit `hal-10495` (future).

---

## 7. Approval Checklist

- [ ] **Scope:** Confirm Mon–Thu list supplements (not replaces) the existing daily operatory board?
- [ ] **PHI:** Approve 4-char hash display for weekly list; confirm full-name gating for dossier modal?
- [ ] **HAL Access:** Approve staff-gated context model (click to select) vs. open search?
- [ ] **Audit:** Approve `hal_patient_audit` table schema and retention policy?
- [ ] **SoftDent:** Confirm read-only forever; no writeback expectations for appointment changes?
- [ ] **Cloud:** Re-confirm local AI only (24B); no OpenAI/Claude keys to be added?
- [ ] **Rollout:** Approve 3-phase implementation (1: Schedule list, 2: Dossier surfaces, 3: HAL integration)?

**DO NOT APPLY until operator replies "approve / proceed".**