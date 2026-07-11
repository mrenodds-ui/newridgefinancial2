# Moonshot AI — Availity Eligibility in HAL Patient Dossier (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Script:** `scripts/run_moonshot_availity_dossier_eligibility_consult.py`  
**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.

## Operator request (verbatim)

> ask moonshot ai how to put Availity eligibility (benefits, deductibles, coverages)
into the HAL patient dossier so staff can capture dental patient insurance from
SoftDent patient context via Availity Coverages API (demo until Standard Plan live)

---

# Verdict — Availity eligibility in HAL patient dossier

## 0. Operator Intent (quote; consult-only)
> "how to wire **Availity eligibility** (benefits / deductibles / coverages 270→271) into the **HAL patient dossier** so staff can capture dental patient insurance from SoftDent patient context via Availity Coverages API (demo until Standard Plan live)"

**Consult-only directive:** Recommend integration architecture; do not commit code. Wait for explicit "approve / proceed".

---

## 1. Current State Audit (dossier vs clearinghouse/Availity vs HAL tools)

| Component | State | Notes |
|-----------|-------|-------|
| **Patient Dossier** (hal-10495) | Shipped | SoftDent read-only SELECT; sections: demographics, appointments, procedures, transactions, claims, estimates. **No eligibility section yet.** Empty money renders as `"unknown"`, never `$0`. |
| **Availity Backend** (hal-10496) | Live-ready | `fetch_availity_271` + `map_availity_eligibility_response` + `eligibility_cache_store`. Demo fallback (`AVAILITY_LIVE_FALLBACK_DEMO=1`) works when live scope unauthorized. |
| **HAL Tools** | Shipped | `fetch_eligibility_271` and `fetch_availity_eligibility` exist as **standalone** tools (separate from dossier). |
| **Dossier→Availity Bridge** | **Missing** | No code resolves SoftDent patient → `memberId`/`payerId`/`NPI` to feed Availity. |
| **Schema Gaps** | Documented | SoftDent extract often lacks `memberId`, `payerId`, `NPI` on `sd_patients` row. No insurance tables shown in current extract (may exist as `sd_patient_insurance` — to be verified). |

---

## 2. Gap Map

| Area | Status | Gap | Effort | Depends on |
|------|--------|-----|--------|------------|
| **Dossier Schema** | Missing | Add `eligibility` section with `benefits`, `gaps[]`, `demo` flag, `live` flag | Small | None |
| **Field Resolver** | Missing | Honest resolver: SoftDent insurance tables → `memberId`/`payerId`; fallback to gaps list (no invention) | Medium | SoftDent schema confirmation |
| **Availity Integration** | Partial | Wire `fetch_eligibility_271` into dossier build; respect `eligibility_cache_store` to avoid 60s blocking | Small | Field resolver |
| **HAL Summarize** | Partial | Update `DOSSIER_SUMMARY_PROMPT` to speak eligibility excerpt (PHI-safe: plan name, deductible status, demo warning) | Small | Dossier schema |
| **OM Widget** | Missing | `eligibility-card` widget showing plan, deductible remaining, annual max, demo banner | Medium | Dossier schema |
| **Audit/PHI** | Partial | Ensure eligibility cache keys use hashed patient IDs; audit log eligibility queries via `hal_patient_audit` | Small | Existing audit |

---

## 3. Target Design

### 3A Data contract (dossier.eligibility section; empty≠$0; demo flag)

```python
"eligibility": {
    "queriedAt": "2026-07-11T21:30:00Z",
    "source": "availity_271",
    "live": False,           # True only if live scope succeeded
    "demo": True,            # True if demo fallback used
    "scope": "demo",         # "demo" | "live" | None
    "gaps": ["memberId"],    # Honest list of missing SoftDent fields
    "benefits": {
        "planName": "Delta Dental PPO",
        "payerName": "Delta Dental",
        "memberIdRedacted": "AET***45",
        "deductibleRemaining": "unknown",  # empty≠$0 rule
        "annualMaxRemaining": 1200.00,
        "preventive": "100%",
        "basic": "80%",
        "major": "50%",
        "limitations": ["Waiting period on crowns 12mo", "Missing tooth clause applies"],
        "planYear": "2026",
        "serviceDate": "2026-07-11"
    },
    "error": None,           # Populated if fetch failed or gaps exist
    "cacheHit": False
}
```

**Invariants:**
- Financial `None`/`0`/`""` → `"unknown"` (never `$0.00`).
- `gaps` array explicitly lists missing SoftDent fields (e.g., `memberId`, `payerId`, `providerNPI`) so staff know why eligibility is absent.
- `demo: True` triggers UI/HAL warning: "Using demo coverage data — not live patient benefits until Standard Plan approved."

### 3B Fetch path (SoftDent patient → member/payer/NPI → Availity 271 → cache → dossier)

```text
build_patient_dossier(pid)
  └─ _resolve_eligibility(conn, pid, practice)
      ├─ 1. SoftDent READ-ONLY lookup (honest gaps):
      │      - SELECT sd_patient_insurance.member_id/subscriber_id (if table exists)
      │      - SELECT sd_insurance.payer_id/payer_name (if table exists)
      │      - NPI from NR2_PROVIDER_NPI env (practice-level, not patient row)
      │      - Any missing → append to gaps[]; skip external call
      ├─ 2. Cache check:
      │      - eligibility_cache_store.get(cache_key) 
      │      - Cache key: hash(pid + member_id + payer_id) for PHI safety
      │      - Hit < 5min → return cached benefits
      ├─ 3. Availity call (only if no cache AND gaps[] empty):
      │      - clearinghouse_eligibility_adapter.fetch_eligibility_271(req)
      │      - Request: {memberId, payerId, providerNpi, vendor:"availity"}
      │      - Handle demo fallback (AVAILITY_LIVE_FALLBACK_DEMO)
      │      - Map via map_availity_eligibility_response
      │      - Store to eligibility_cache_store (PHI-redacted)
      └─ 4. Return eligibility section (benefits or error + gaps)
```

**Critical:** If SoftDent lacks insurance fields, dossier **does not invent** placeholder IDs. It returns `gaps: ["memberId", "payerId"]` and `error: "SoftDent extract incomplete"`. Staff must use the standalone `fetch_eligibility_271` HAL tool with explicit arguments to populate cache for that patient.

### 3C HAL UX (tool + summarize + OM widget; spoken excerpt PHI-safe)

**HAL Tool `summarize_patient_dossier`:**
- Already fetches dossier via `DesktopBridge.fetchPatientDossier`.
- Receives new `eligibility` JSON (above).
- Prompt addition (see Phase 3 coding plan) instructs local 24B to output:
  > "Eligibility: Delta Dental PPO. Deductible remaining unknown. Annual maximum remaining one thousand two hundred dollars. Preventive covered at one hundred percent. **Note: eligibility data is simulated demo until Availity Standard Plan is active.**"

**OM Widget `patient-dossier-card` extension:**
- New sub-card "Insurance Eligibility".
- Shows: Plan name, Deductible (remaining/unknown), Annual Max (remaining/unknown), Preventive/Basic/Major percentages.
- **Demo banner:** Orange badge "DEMO DATA" when `eligibility.demo == True`.
- **Gaps banner:** Yellow badge "Missing SoftDent: memberId" when gaps exist, with tooltip "Run HAL fetch_eligibility_271 with insurance card details".

### 3D Live vs demo honesty (Standard Plan gate; fallback messaging)

- **Gate:** `AVAILITY_USE_DEMO` env (default `1` until Standard Plan approved).
- **Fallback:** If `AVAILITY_USE_DEMO=0` but live token returns `unauthorized_client`, and `AVAILITY_LIVE_FALLBACK_DEMO=1` (default), automatically use demo scope but set `eligibility.demo=True` and `eligibility.live=False`.
- **Transparency:** 
  - Dossier JSON includes `demo` boolean.
  - HAL spoken summary explicitly states "using demo coverage data" when true.
  - OM widget shows persistent orange "DEMO" chip.
- **No Live Leak:** Until Standard Plan approved, staff cannot accidentally view live 271 data because the fallback forces demo when live unauthorized.

---

## 4. Coding Plan by Phase (files · paste-ready sketches · validation)

### Phase 1 — Schema & Resolver (MUST)

**FILE:** `patient_dossier.py` — append eligibility resolver (local imports to avoid cycles)

```python
def _resolve_eligibility_for_patient(
    conn, patient_id: str, practice_id: str
) -> dict[str, Any]:
    """Build eligibility section from SoftDent (read-only) + Availity cache.
    
    Honest gaps: if SoftDent lacks memberId/payerId/NPI, return gaps list 
    and do not invent data.
    """
    import os
    from datetime import datetime, timezone
    
    eligibility: dict[str, Any] = {
        "queriedAt": datetime.now(timezone.utc).isoformat(),
        "source": "availity_271",
        "live": False,
        "demo": False,
        "scope": None,
        "gaps": [],
        "benefits": None,
        "error": None,
        "cacheHit": False,
    }
    
    # 1. SoftDent honest lookup (defensive table checks)
    member_id: str | None = None
    payer_id: str | None = None
    payer_name: str | None = None
    
    if _table_exists(conn, "sd_patient_insurance"):
        cur = conn.cursor()
        cur.execute(
            """SELECT member_id, subscriber_id, insurance_name, payer_id 
               FROM sd_patient_insurance 
               WHERE patient_id = ? LIMIT 1""",
            (patient_id,),
        )
        row = cur.fetchone()
        if row:
            member_id = (row.get("member_id") or row.get("subscriber_id") or "").strip() or None
            payer_name = (row.get("insurance_name") or "").strip() or None
            payer_id = (row.get("payer_id") or "").strip() or None
    
    # Practice NPI (not on patient row)
    provider_npi = os.environ.get("NR2_PROVIDER_NPI", "").strip()
    
    # 2. Honest gap detection
    if not member_id:
        eligibility["gaps"].append("memberId")
    if not payer_id and not payer_name:
        eligibility["gaps"].append("payerId")
    if not provider_npi:
        eligibility["gaps"].append("providerNPI")
    
    if eligibility["gaps"]:
        eligibility["error"] = f"SoftDent missing: {', '.join(eligibility['gaps'])}"
        return eligibility
    
    # 3. Cache check (PHI-safe key)
    try:
        from eligibility_cache_store import get_cached_eligibility
        from clearinghouse_eligibility_adapter import fetch_eligibility_271
        
        # Hash components for cache key to avoid raw PHI in cache index
        cache_seed = f"{patient_id}:{member_id}:{payer_id or payer_name}:{provider_npi}"
        cache_key = patient_hash(cache_seed)  # reuse existing hash util
        
        cached = get_cached_eligibility(cache_key)
        if cached:
            eligibility["benefits"] = cached
            eligibility["demo"] = cached.get("demo", False)
            eligibility["live"] = not eligibility["demo"]
            eligibility["scope"] = "demo" if eligibility["demo"] else "live"
            eligibility["cacheHit"] = True
            return eligibility
        
        # 4. Live fetch (blocking, 60s timeout handled downstream)
        req = {
            "memberId": member_id,
            "payerId": payer_id or "",
            "payerName": payer_name or "",
            "providerNpi": provider_npi,
            "vendor": "availity",
        }
        result = fetch_eligibility_271(req)
        
        if result.get("ok") and result.get("entry"):
            entry = result["entry"]
            # Normalize empty money to "unknown" per dossier rules
            for money_key in ("deductibleRemaining", "annualMaxRemaining", "annualMax"):
                if entry.get(money_key) in (None, 0, "", 0.0):
                    entry[money_key] = "unknown"
            
            eligibility["benefits"] = entry
            eligibility["demo"] = bool(result.get("demo"))
            eligibility["live"] = not eligibility["demo"] and not result.get("demo")
            eligibility["scope"] = "demo" if eligibility["demo"] else "live"
            
            # Store redacted snapshot
            from eligibility_cache_store import store_eligibility_snapshot
            store_eligibility_snapshot(cache_key, entry, ttl_sec=300)
        else:
            eligibility["error"] = result.get("message") or result.get("error", "Eligibility unavailable")
            eligibility["demo"] = bool(result.get("demo"))
            
    except Exception as exc:
        eligibility["error"] = f"Eligibility fetch failed: {exc}"
    
    return eligibility
```

**Integration point** in `build_patient_dossier`:
```python
# After demographics, before closing conn:
dossier["eligibility"] = _resolve_eligibility_for_patient(conn, pid, practice)
```

### Phase 2 — Prompt Update (MUST)

**FILE:** `patient_dossier_prompts.py`

```python
DOSSIER_SUMMARY_PROMPT = """You are NR2-HAL, a dental practice assistant. Produce a concise patient dossier summary.

STRICT RULES:
1. If a financial field is missing, null, or 0, output the word 'unknown'. Never output $0.00.
2. Do not invent insurance coverage details not present in the data.
3. Use clear headers: Demographics, Appointments, Procedures, Transactions, Claims, Eligibility, Notes.
4. Keep total response under 400 tokens.
5. Use patient hash/initials only — do not invent full names.
6. If a section is empty, say so honestly (SoftDent extract may be incomplete).
7. ELIGIBILITY SECTION:
   - If eligibility.demo is True, prepend "[DEMO DATA] " to every eligibility statement.
   - Speak deductible/annual max remaining values only if they are numbers; if 'unknown', say "deductible remaining unknown".
   - If eligibility.gaps lists missing fields, state: "Insurance details incomplete in SoftDent: missing {fields}. Use HAL fetch_eligibility_271 tool to query manually."

DATA:
{dossier_json}
"""
```

### Phase 3 — OM Widget (SHOULD)

**FILE:** `apex_missing_widgets_pack.py` — append renderer

```python
def render_eligibility_card(eligibility: dict) -> dict:
    """Return OM widget JSON for eligibility sub-card."""
    benefits = eligibility.get("benefits") or {}
    gaps = eligibility.get("gaps", [])
    is_demo = eligibility.get("demo", False)
    
    # Convert "unknown" or None to display string
    def fmt_money(val):
        if val in (None, "unknown", "", 0, 0.0):
            return "unknown"
        try:
            return f"${float(val):,.2f}"
        except (TypeError, ValueError):
            return "unknown"
    
    rows = [
        {"label": "Plan", "value": benefits.get("planName") or "—"},
        {"label": "Payer", "value": benefits.get("payerName") or "—"},
        {"label": "Deductible Remaining", "value": fmt_money(benefits.get("deductibleRemaining"))},
        {"label": "Annual Max Remaining", "value": fmt_money(benefits.get("annualMaxRemaining"))},
        {"label": "Preventive", "value": benefits.get("preventive") or "unknown"},
        {"label": "Basic", "value": benefits.get("basic") or "unknown"},
        {"label": "Major", "value": benefits.get("major") or "unknown"},
    ]
    
    return {
        "widget": "eligibility-card",
        "title": "Insurance Eligibility",
        "badge": "DEMO" if is_demo else None,
        "badgeColor": "orange" if is_demo else None,
        "warning": f"SoftDent gaps: {', '.join(gaps)}" if gaps else None,
        "rows": rows,
        "limitations": benefits.get("limitations", [])[:5],  # max 5
        "queriedAt": eligibility.get("queriedAt"),
    }
```

**FILE:** `site/apex-core.js` — add renderer case

```javascript
case 'eligibility-card':
  const demoBanner = w.badge ? `<span class="badge ${w.badgeColor}">${w.badge}</span>` : '';
  const gapBanner = w.warning ? `<div class="alert alert-warn">${w.warning}</div>` : '';
  const rows = (w.rows || []).map(r => `<tr><td>${r.label}</td><td>${r.value}</td></tr>`).join('');
  return `
    <div class="card eligibility-card">
      <h4>${w.title} ${demoBanner}</h4>
      ${gapBanner}
      <table class="mini">${rows}</table>
      ${(w.limitations || []).map(l => `<li class="small">${l}</li>`).join('')}
      <div class="meta">Queried: ${w.queriedAt || '—'}</div>
    </div>
  `;
```

### Phase 4 — Validation Tests

**FILE:** `test_patient_dossier.py` — add cases

```python
def test_eligibility_unknown_money_not_zero():
    """Empty financials in eligibility must be 'unknown', never $0.00."""
    # Mock eligibility response with 0 deductible
    # Assert dossier.eligibility.benefits.deductibleRemaining == "unknown"

def test_eligibility_gaps_when_softdent_incomplete():
    """If SoftDent lacks memberId, dossier.eligibility.gaps must include 'memberId'."""
    
def test_eligibility_demo_flag_propagates():
    """When AVAILITY_USE_DEMO=1, dossier.eligibility.demo must be True."""
```

---

## 5. MUST / SHOULD / NICE ranked table

| Priority | Item | File(s) | Validation |
|----------|------|---------|------------|
| **MUST** | Extend dossier schema with `eligibility` section (empty≠$0, gaps[], demo flag) | `patient_dossier.py` | Unit test: `test_eligibility_schema` |
| **MUST** | Honest resolver: read SoftDent insurance tables if present; else gaps list (no invention) | `patient_dossier.py` | Test with mock SoftDent missing columns |
| **MUST** | Integrate Availity fetch via existing `fetch_eligibility_271` + `eligibility_cache_store` | `patient_dossier.py` | Mock adapter, verify cache hit skips HTTP |
| **MUST** | PHI-safe audit: eligibility queries logged via `hal_patient_audit` with hashed IDs | `hal_patient_audit.py` (extend if needed) | Check JSONL for `patient_hash` usage |
| **MUST** | Update `DOSSIER_SUMMARY_PROMPT` to speak eligibility with demo warning | `patient_dossier_prompts.py` | Inspect prompt output contains "[DEMO]" when demo=True |
| **SHOULD** | OM widget `eligibility-card` with demo banner and gaps warning | `apex_missing_widgets_pack.py`, `site/apex-core.js` | Visual check in OM |
| **SHOULD** | 5-minute eligibility cache TTL (reuse `eligibility_cache_store` TTL) | `patient_dossier.py` | Test cache hit within 5min, miss after |
| **NICE** | HAL tool argument override: `summarize_patient_dossier` accepts optional `memberId`, `payerId` to bypass SoftDent gaps for one-off queries | `hal-agent.js`, `apex_backend.py` (query params) | Integration test |
| **NICE** | Background pre-fetch: when dossier loaded with gaps, trigger async eligibility fetch for next load | Threading/async queue | Deferred to future build |

---

## 6. Risks, PHI, SoftDent honesty, Rollback

### Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| **SoftDent schema unknown** | Resolver fails if insurance tables named differently | Defensive `_table_exists` checks; if missing, `gaps` list populated honestly |
| **Blocking 60s timeout** | Dossier API hangs if Availity slow | Cache-first design: dossier only reads cache; if miss, returns "not queried" instantly. Staff use separate HAL tool to populate cache. |
| **PHI in cache keys** | Member IDs exposed in cache index | Cache key uses `patient_hash(seed)` so raw memberId never appears in cache store index |
| **Demo/live confusion** | Staff treat demo benefits as real | Hardcoded `demo` flag in JSON + UI orange banner + HAL spoken "[DEMO DATA]" prefix |
| **Circular import** | `patient_dossier` importing `clearinghouse_eligibility_adapter` | Use local imports inside `_resolve_eligibility_for_patient` (as sketched) |

### SoftDent Honesty
- **READ-ONLY forever:** Only `SELECT` statements in resolver; no `UPDATE/INSERT` to SoftDent tables.
- **Empty≠$0:** Any `None`/`0`/`""` from `map_availity_eligibility_response` converted to `"unknown"` string before dossier storage.
- **Gaps≠Invent:** If `sd_patient_insurance` missing or columns null, `eligibility.gaps` explicitly lists missing fields. No placeholder IDs generated.

### PHI Protection
- All audit logs use `patient_hash()` (existing util).
- Eligibility cache stores redacted snapshot (existing `eligibility_cache_store` behavior).
- Local-only: No cloud AI processes eligibility JSON; summarization runs on local Ollama 24B via `hal-local:24b`.

### Rollback
- **Phase 1 only:** If issues arise, remove `dossier["eligibility"]` assignment in `build_patient_dossier`; dossier reverts to previous schema (eligibility section absent).
- **Feature flag:** Wrap eligibility resolution in env `DOSSIER_ELIGIBILITY_ENABLED` (default `0` until validated) for instant kill switch.

---

## 7. Approval Checklist

Before proceeding to implementation, confirm:

- [ ] **SoftDent Schema:** Confirm whether `sd_patient_insurance` table exists in extract; if not, accept "gaps" approach as primary path.
- [ ] **NPI Source:** Confirm `NR2_PROVIDER_NPI` env var is populated in production (practice-level NPI for Availity calls).
- [ ] **Data Contract:** Approve eligibility JSON schema (Section 3A) including `"unknown"` for missing money and `gaps[]` array.
- [ ] **Demo Behavior:** Confirm `AVAILITY_LIVE_FALLBACK_DEMO=1` (default) is acceptable until Standard Plan approved.
- [ ] **Blocking Strategy:** Approve cache-first non-blocking design (dossier shows cached data or "not queried", rather than waiting 60s).
- [ ] **PHI Redaction:** Verify `patient_hash()` is acceptable for eligibility cache keys.
- [ ] **Priorities:** Confirm MUST vs SHOULD vs NICE ranking (can defer OM widget to hal-10497 if urgent).
- [ ] **Rollback:** Agree to `DOSSIER_ELIGIBILITY_ENABLED` feature flag for safe deployment.

**Do not apply code until operator replies "approve / proceed".**