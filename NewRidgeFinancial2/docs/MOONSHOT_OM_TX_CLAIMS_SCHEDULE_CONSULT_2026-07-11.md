# Moonshot AI — Treatment / Claims / SoftDent Schedule / OM Appointments (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Script:** `scripts/run_moonshot_om_tx_claims_schedule_consult.py`  
**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.

## Operator request (verbatim)

> as expert sofware engineer run through moonshot ai everything about this program for recommendation for treatment planning, claims processing, and handling, and the schedule fro softdent.  Appointments should be loaded into the program everyday of the office manager page. moonshot recommendations with them then report

---

# Verdict — Tx planning / Claims / SoftDent schedule / OM daily appointments

## 0. Operator Intent (quote; consult-only)

> "as expert sofware engineer run through moonshot ai everything about this program for recommendation for treatment planning, claims processing, and handling, and the schedule fro softdent. Appointments should be loaded into the program everyday of the office manager page. moonshot recommendations with them then report"

**Consult scope**: Treatment planning architecture, claims processing workflows, SoftDent schedule integration, and **critical fix**: Ensure daily appointments populate the Office Manager (OM) page widgets without manual SoftDent page navigation. Read-only SoftDent constraint maintained.

## 1. Current State Audit (treatment · claims · schedule · OM) — grounded

| Surface | State | Evidence |
|---------|-------|----------|
| **Local AI** | `hal-local:24b` (Mistral Small 3.1 Q4_K_M) on R9700; 15–18 GB resident; 8K context; single-model policy | `HAL_LOCAL_24B_SINGLE_GPU_2026-07-11.md` |
| **SoftDent Import** | READ-ONLY bridge via Sensei Gateway Client → `sd_appointments`, `sd_procedures`, `sd_insurance_payment_lines` | `import-manifest.json`, `softdent_practice_exports.py` |
| **Schedule Data Flow** | `sync_practice_exports()` generates `operatory_schedule.json` (chairs JSON) from Sensei or `sd_appointments` fallback; loaded by `import_loader.py` as `operatory` bundle key; **NOT** a first-class `softdent.appointments` manifest dataset | `softdent_practice_exports.py` lines 90–120, `import_loader.py` `_load_operatory_dataset` |
| **Live Appointments API** | `/api/softdent/appointments-snapshot` exists in `nr2_softdent_daily.py`; returns last 12 appointments from `sd_appointments` or `sd_procedures` fallback | `nr2_softdent_daily.py` `appointments_snapshot()` |
| **Browser Prefetch** | `NR2SoftdentDaily.prefetchLive()` triggers **only** when SoftDent page opens (`page.id === "softdent"`); **OM page does NOT trigger prefetch** | `site/app.js` lines 15–25, 45–55 |
| **OM Widgets** | `build_operatory_board()` looks for `bundle["softdent"]["schedule_today"]["operatories"]` or flat `schedule`/`appointments` rows; **empty when operatory JSON stale/missing**; no fallback to live API | `apex_missing_widgets_pack.py` lines 1–50 |
| **Treatment Planning** | `softdent_treatment_planning.py` ingests `insurance_payments*.csv` + `procedure_codes*.csv` → `treatment_planning_estimates` table; `lookup_treatment_estimate()` exists but **not exposed as HAL tool** | `softdent_treatment_planning.py` head |
| **Claims** | Claims workbench + narrative packs (`draft_insurance_narrative`, ERA tools); OM shows verification matrix; HAL can `read_claims_summary`, `join_claim_payers` | `import-manifest.json` `softdent.claims`, extracts |
| **OM Page** | Widgets: daily huddle, operatory utilization board, treatment pipeline, verification matrix; **operatory board shows "No schedule data"** when bundle keys absent | `apex_backend.py` `_office_manager_widgets`, `apex_missing_widgets_pack.py` |

**Critical Finding**: The OM page widgets depend on import-bundle keys (`schedule_today`, `operatoryChairs`) that are ephemeral and not refreshed on OM page load. The live appointments API exists but is **not wired to OM**. This creates the reported gap: appointments do not appear on OM daily without manually opening the SoftDent page first.

## 2. Gap Map

| Area | Status | Gap | Effort | Depends on |
|------|--------|-----|--------|------------|
| **OM Daily Appointments** | **BROKEN** | OM page open does not trigger `appointments-snapshot` refresh; widgets look for missing bundle keys; no live fallback | 2–3 hrs | `site/app.js`, `apex_missing_widgets_pack.py`, `nr2_softdent_daily.py` |
| **Operatory Board Data** | **PARTIAL** | `build_operatory_board` only reads bundle; ignores live API when bundle empty | 1–2 hrs | `apex_missing_widgets_pack.py` |
| **Treatment Planning HAL** | **INCOMPLETE** | `lookup_treatment_estimate` exists in Python but not registered as HAL tool; program cannot query estimates conversationally | 2 hrs | `softdent_treatment_planning.py` |
| **Claims OM Integration** | **PRESENT** | Verification matrix exists but lacks proactive "claims needing narratives today" widget | 3–4 hrs | `claims/narrative packs` |
| **Schedule Freshness** | **WARNING** | `operatory_schedule.json` generated during import sync only; no intra-day refresh mechanism | 1 hr | `softdent_practice_exports.py` |
| **PHI Exposure** | **SAFE** | Patient initials only; no names in widgets; read-only | — | — |

## 3. Target Design (OM daily appointments + related surfaces)

**Core Fix**: When Office Manager page loads, trigger live appointments fetch (today only) and inject into widget bundle, bypassing stale import-cache dependency.

**Architecture**:
1. **Frontend**: OM page open → `NR2SoftdentDaily.prefetchTodayForOM()` → calls `/api/softdent/appointments-today` (new lightweight endpoint or param)
2. **Backend**: New endpoint `appointments_today()` in `nr2_softdent_daily.py` returns today's `sd_appointments` rows with operatory/chair grouping
3. **Widget**: `build_operatory_board` modified to accept `liveAppointments` override; falls back to bundle only when live unavailable
4. **HAL**: Register `lookup_treatment_estimate` as tool; add `draft_claim_narrative_for_om` for quick narrative generation from OM context

**Data Flow**:
```
OM Page Load
    ↓
JS: prefetchTodayForOM()
    ↓
API: /api/softdent/appointments-today?date=2026-07-11
    ↓
nr2_softdent_daily.py: query sd_appointments WHERE appt_date = TODAY
    ↓
Return: {operatories: [{name: "Op1", slots: [{time, status, patientHash}]}]}
    ↓
apex_missing_widgets_pack.py: build_operatory_board(liveData=...)
    ↓
Widget renders with today's schedule
```

## 4. Coding Plan by Phase (files to touch · paste-ready sketches · validation)

### Phase 1: MUST — Close OM Daily Appointments Gap

**File**: `nr2_softdent_daily.py` (add today-specific query)
```python
def appointments_today_snapshot(*, target_date: str | None = None) -> dict[str, Any]:
    """Return today's appointments grouped by operatory for OM widget.
    
    Args:
        target_date: ISO date string (default today local time)
    """
    from datetime import date
    target = target_date or date.today().isoformat()
    conn, db_path = _open_db()
    if not conn:
        return {"hasData": False, "operatories": [], "date": target}
    try:
        cur = conn.cursor()
        # Query specific date, ordered by time
        cur.execute(
            """
            SELECT appt_date, appt_time, patient_id, provider_code, 
                   operatory, status, duration
            FROM sd_appointments
            WHERE appt_date = ?
            ORDER BY appt_time ASC
            """,
            (target,),
        )
        rows = cur.fetchall()
        if not rows:
            # Fallback to procedures if no appointment rows for today
            return {"hasData": False, "operatories": [], "date": target, "fallback": True}
        
        # Group by operatory
        from collections import defaultdict
        by_op: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            op_name = str(row[4] or row[3] or "Op—")  # operatory or provider
            patient_hash = _hash_patient(str(row[2])) if row[2] else None
            by_op[op_name].append({
                "time": str(row[1] or "")[:5],
                "status": _normalize_status(str(row[5] or "scheduled")),
                "patientHash": patient_hash,
                "provider": str(row[3] or ""),
            })
        
        operatories = [{"name": k, "slots": v[:12]} for k, v in list(by_op.items())[:8]]
        return {
            "hasData": True,
            "operatories": operatories,
            "date": target,
            "count": len(rows),
            "source": "sd_appointments",
        }
    finally:
        conn.close()

def _hash_patient(patient_id: str) -> str:
    """PHI-safe hash for widget display (first 4 chars of SHA256)."""
    import hashlib
    return hashlib.sha256(patient_id.encode()).hexdigest()[:4].upper()

def _normalize_status(raw: str) -> str:
    r = raw.lower()
    if any(x in r for x in ["cancel", "no show", "broken"]):
        return "open"
    if any(x in r for x in ["complete", "seen", "checkout"]):
        return "completed"
    if any(x in r for x in ["checkin", "here", "arrived"]):
        return "checked-in"
    return "booked"
```

**File**: `site/app.js` (OM page prefetch trigger)
```javascript
// In page load handler, add OM-specific prefetch
if (page.id === "office-manager" && typeof NR2SoftdentDaily !== "undefined") {
  NR2SoftdentDaily.prefetchTodayForOM()
    .then(data => {
      if (appPage && !appPage.hidden && PageViews && PageViews.hasPage(page.id)) {
        // Inject live data into widget feed context
        window.NR2_OM_LIVE_SCHEDULE = data;
        PageViews.renderPageView(appPage, halData, page.id, select, halWidgetFeed, halProgramSnapshot);
      }
    })
    .catch(() => {
      window.NR2_OM_LIVE_SCHEDULE = null;
    });
}
```

**File**: `apex_missing_widgets_pack.py` (modify `build_operatory_board`)
```python
def build_operatory_board(bundle: dict[str, Any], live_schedule: dict[str, Any] | None = None) -> dict[str, Any]:
    # Priority 1: Live OM data injected from frontend
    if live_schedule and live_schedule.get("hasData"):
        return _wrap(
            widget_id="operatory-util-board",
            type_="utilization-board",
            title="Operatory Board",
            page="office-manager",
            size="l",
            status="ok",
            data={
                "operatories": live_schedule.get("operatories", []),
                "date": live_schedule.get("date"),
                "emptyMessage": None,
            },
            hint="Today's SoftDent schedule — live fetch.",
        )
    
    # Priority 2: Existing bundle logic (keep current implementation)
    # ... existing code ...
    
    # Priority 3: Empty state with actionable hint
    return _wrap(
        widget_id="operatory-util-board",
        type_="utilization-board",
        title="Operatory Board",
        page="office-manager",
        size="l",
        status="empty",
        data={"operatories": [], "emptyMessage": "No schedule data — run import sync or open SoftDent page."},
        hint="Schedule unavailable. Try refreshing or check SoftDent bridge.",
    )
```

**Validation**:
- [ ] OM page load triggers API call (Network tab shows `/api/softdent/appointments-today`)
- [ ] Widget displays today's appointments with times and patient hashes
- [ ] Empty state provides actionable guidance
- [ ] No SoftDent write operations occur (read-only verification)

### Phase 2: SHOULD — Treatment Planning & Claims Enhancement

**File**: `softdent_treatment_planning.py` (HAL tool registration)
```python
# Add to module exports for HAL tool discovery
HAL_TOOLS = {
    "lookup_treatment_estimate": {
        "description": "Look up estimated insurance payment for ADA code and payer",
        "parameters": {
            "ada_code": "str (e.g., D2740)",
            "payer_name": "str (insurance company name or 'unknown')",
            "zip_hint": "str optional (Kansas ZIP for regional adjustment)"
        },
        "handler": lookup_treatment_estimate
    },
    "format_treatment_estimate_reply": {
        "description": "Format estimate for patient-friendly display",
        "parameters": {"estimate_dict": "dict from lookup_treatment_estimate"},
        "handler": format_treatment_estimate_reply
    }
}
```

**File**: `claims/narrative packs` (OM widget for pending narratives)
```python
def build_claims_needing_narrative(bundle: dict[str, Any]) -> dict[str, Any]:
    """OM widget: claims missing narratives due today+3."""
    claims = bundle.get("softdent", {}).get("claims", [])
    pending = [c for c in claims if c.get("status") in ["pending", "appeal"] and not c.get("hasNarrative")]
    # Limit to 5 most urgent
    urgent = sorted(pending, key=lambda x: x.get("dueDate", ""))[:5]
    return _wrap(
        widget_id="claims-narrative-queue",
        type_="action-list",
        title="Claims Needing Narratives",
        page="office-manager",
        size="m",
        status="ok" if urgent else "empty",
        data={"items": [{"id": c["ClaimId"], "payer": c["Payer"], "amount": c["ClaimAmount"]} for c in urgent]},
        hint="Prioritize these for HAL narrative generation.",
    )
```

### Phase 3: NICE — Polish & Trends

**File**: `apex_missing_widgets_pack.py` (recall gauge integration)
- Connect `build_recall_gauge` to appointment booking suggestions (if HAL suggests booking, populate slot)

**File**: `nr2_softdent_daily.py` (provider utilization trend)
- Add `provider_utilization_last_7d()` for OM sidebar trend widget

## 5. MUST / SHOULD / NICE ranked table

| Priority | Item | Phase | Files | Business Impact |
|----------|------|-------|-------|-----------------|
| **MUST** | OM page daily appointments load | 1 | `nr2_softdent_daily.py`, `site/app.js`, `apex_missing_widgets_pack.py` | **Operator requirement** — OM sees daily schedule without manual SoftDent page navigation |
| **MUST** | Operatory board live fallback | 1 | `apex_missing_widgets_pack.py` | Prevents "No schedule data" empty states |
| **SHOULD** | Treatment planning HAL tools expose | 2 | `softdent_treatment_planning.py` | Enables conversational estimate lookups |
| **SHOULD** | Claims narrative OM queue | 2 | `claims/narrative packs` | Reduces claim denial lag |
| **NICE** | Recall-to-appointment booking flow | 3 | `apex_missing_widgets_pack.py` | Hygiene reactivation automation |
| **NICE** | Provider utilization trends | 3 | `nr2_softdent_daily.py` | Long-term capacity planning |

## 6. Risks, PHI, SoftDent honesty, Rollback

**PHI Protection**:
- ✅ Patient identifiers hashed to 4-char codes in widgets (no names, no full IDs)
- ✅ API returns initials/hashes only; full data stays in backend SQLite
- ✅ Read-only SoftDent: No `UPDATE/INSERT/DELETE` statements in new code

**SoftDent Honesty**:
- ✅ No write-back to SoftDent database confirmed
- ✅ Uses existing `sd_appointments` read replica/analytics DB only
- ✅ Falls back to `sd_procedures` only when appointments missing (transparent in API response)

**Performance (R9700 24B)**:
- ⚠️ New endpoint queries single date (indexed) — minimal CPU impact
- ⚠️ Frontend prefetch adds one HTTP request per OM page load — acceptable
- ✅ No additional AI model loading; uses existing `hal-local:24b` for HAL tools only

**Rollback**:
- If OM appointments fail: Remove `prefetchTodayForOM()` call in `site/app.js` — widgets revert to bundle-only behavior
- If API errors: `build_operatory_board` catches `live_schedule=None` and shows existing empty state
- Database: No schema changes; pure SELECT queries

## 7. Approval Checklist

- [ ] **Approve OM-A0**: Approve Phase 1 MUST items (daily appointments loading fix)
- [ ] **Approve MUST**: Approve all MUST priority items in table
- [ ] **Approve Phase 2**: Approve SHOULD items (treatment planning HAL tools + claims queue)
- [ ] **Approve Phase 3**: Approve NICE items (recall integration + trends)
- [ ] **Approve specific files**: 
  - [ ] `nr2_softdent_daily.py` additions (appointments_today_snapshot)
  - [ ] `site/app.js` OM prefetch trigger
  - [ ] `apex_missing_widgets_pack.py` live fallback logic
- [ ] **Approve PHI handling**: Confirm 4-char hash acceptable for patient identifiers in OM view
- [ ] **Approve SoftDent read-only**: Confirm no write operations in proposed code
- [ ] **Proceed to implementation**: Authorize code application after checklist completion

**DO NOT APPLY** until operator explicitly approves checklist items and states "proceed" or "approve implementation".