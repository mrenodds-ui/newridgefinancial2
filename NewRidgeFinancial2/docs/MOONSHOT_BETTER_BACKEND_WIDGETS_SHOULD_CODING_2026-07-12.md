# Moonshot AI — Better Backend Widgets SHOULD CODING

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build base:** hal-10567  
**Script:** `scripts/run_moonshot_better_backend_widgets_should_coding.py`  
**Operator:** continue (SHOULD wave)  

## Operator request (verbatim)

> continue

---

# Verdict

**Status:** SHOULD wave ready for apply. Four gap-fill widgets to close Moonshot SHOULD items without duplicating MUST (shipped hal-10567) or entering NICE territory.

## 0. Operator Intent
> "Continue Moonshot better-backend-widgets with SHOULD wave only. Apply-ready coding. Do not redo MUST. Do not start NICE."

**Confirmed.** Deliver backend builders for:
1. **HAL Action-List** (recommended actions) – hal + office-manager  
2. **A/R Collection Task-List** – ar (main page; honest empty when no aging/denied)  
3. **AI Insight Card** – narratives (rule-backed variance; no invented $)  
4. **Patient Dossier Card** – softdent (empty placeholder until patient selected)

## 1. Gap vs Already-Shipped (per SHOULD)

| Widget | Target Page | Already Exists? | Gap Action |
|--------|-------------|-----------------|------------|
| `action-list` | office-manager | **YES** – `build_claims_needing_narrative` in `apex_missing_widgets_pack` | None (OM satisfied) |
| `action-list` | hal | **NO** – only chat/status tiles present | **Add** `build_hal_action_list` |
| `collection-task-list` | ar (collections subpage) | **YES** – `build_collections_workbench` in `apex_subpages_pack` | None (subpage satisfied) |
| `collection-task-list` | ar (main) | **NO** – only bullets/gauges on main | **Add** `build_ar_main_collection_task_list` |
| `ai-insight` | hal | **YES** – `ai_insight_widget` in `apex_structured_insight_pack` | None (HAL satisfied) |
| `ai-insight` | narratives | **NO** – only KPI counts present | **Add** `build_narratives_ai_insight` |
| `patient-dossier-card` | office-manager | **YES** – `build_patient_dossier_card` in `apex_missing_widgets_pack` | None (OM satisfied) |
| `patient-dossier-card` | softdent | **NO** – page lacks dossier | **Add** `build_softdent_patient_dossier` |

## 2. Files to Touch
- `apex_better_backend_widgets_pack.py` – append four new builders (SHOULD wave)
- `apex_backend.py` – thin wiring in `_hal_widgets`, `_ar_widgets`, `_narratives_widgets`, `_softdent_widgets`

## 3. Paste-ready Code

### File: `apex_better_backend_widgets_pack.py` (append at end)

```python
# ---------------------------------------------------------------------------
# Moonshot SHOULD wave — hal-10567 continuation
# Gap-fill widgets: action-list (hal), collection-task-list (ar main),
# ai-insight (narratives), patient-dossier-card (softdent)
# ---------------------------------------------------------------------------

def _patient_initials(name: str) -> str:
    parts = str(name).strip().split()
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[-1][0]}".upper()
    if parts:
        return parts[0][:2].upper()
    return "—"


def build_hal_action_list(bundle: dict[str, Any]) -> dict[str, Any]:
    """
    HAL recommended actions (action-list).
    Sources: diagnostics alerts, missing imports, efficiency audit flags.
    FE Contract: data.items[{label|id, payer, status, amount, serviceDate}]
    """
    items: list[dict[str, Any]] = []
    diag = bundle.get("diagnostics") if isinstance(bundle.get("diagnostics"), dict) else {}
    summary = diag.get("summary") if isinstance(diag.get("summary"), dict) else {}
    missing = summary.get("missing") or 0
    stale = summary.get("stale") or 0

    if missing:
        items.append({
            "id": "hal-act-missing-imports",
            "label": f"Reconnect {missing} missing data source(s)",
            "payer": "System",
            "status": "alert",
            "amount": None,
            "serviceDate": "",
        })
    if stale:
        items.append({
            "id": "hal-act-stale-imports",
            "label": f"Refresh {stale} stale dataset(s)",
            "payer": "System",
            "status": "warning",
            "amount": None,
            "serviceDate": "",
        })

    # Efficiency audit cross-check (if available)
    try:
        from apex_structured_insight_pack import load_last_insight
        insight = load_last_insight() or {}
        audit = insight.get("efficiency_audit") or {}
        if audit.get("flag"):
            items.append({
                "id": "hal-act-efficiency",
                "label": f"Efficiency alert: {audit.get('message', 'Review payroll vs production')}",
                "payer": "Practice",
                "status": "review",
                "amount": audit.get("variance_dollars"),
                "serviceDate": audit.get("period") or "",
            })
    except Exception:
        pass

    # Filing reminders (tax/quarterly) — honest empty if unknown
    tax = bundle.get("taxes") if isinstance(bundle.get("taxes"), dict) else {}
    if tax.get("next_deadline"):
        items.append({
            "id": "hal-act-filing",
            "label": f"Upcoming filing: {tax.get('next_deadline')}",
            "payer": "IRS/KDOR",
            "status": "scheduled",
            "amount": None,
            "serviceDate": tax.get("due_date") or "",
        })

    status = "ok" if items else "empty"
    return _wrap(
        widget_id="hal-recommended-actions",
        type_="action-list",
        title="Recommended Actions",
        page="hal",
        size="m",
        status=status,
        data={
            "items": items,
            "count": len(items),
            "emptyMessage": "No active recommendations — imports healthy and filings on track.",
        },
        hint="Rule-backed HAL prompts (no LLM inference).",
        collapse_when_empty=False,
    )


def build_ar_main_collection_task_list(bundle: dict[str, Any]) -> dict[str, Any]:
    """
    A/R MAIN page collection workbench (collection-task-list).
    Seeds from SoftDent aging 30/60/90+ and denied claims.
    Honest empty when no seeds and no local notes.
    FE Contract: seeds[{claimId, patientInitials, ageDays, bucket, billedAmount}], notes[]
    """
    seeds: list[dict[str, Any]] = []
    notes: list[dict[str, Any]] = []  # Main page seeds only; notes live on subpage/workbench

    try:
        from apex_claims_narratives_pack import build_aging_buckets, normalize_claim_row
        rows = (
            _section_rows(bundle, "softdent", "claims")
            or _section_rows(bundle, "softdent", "claimStatus")
            or []
        )
        aging = build_aging_buckets(rows)
        for bucket_key in ("90", "60", "30"):
            tiles = (aging.get("buckets") or {}).get(bucket_key) or []
            if not isinstance(tiles, list):
                continue
            for tile in tiles[:20]:  # Cap to avoid payload bloat
                if not isinstance(tile, dict):
                    continue
                seeds.append({
                    "claimId": tile.get("claimId"),
                    "patientInitials": _patient_initials(str(tile.get("patientName") or "")),
                    "ageDays": tile.get("ageDays"),
                    "bucket": bucket_key,
                    "billedAmount": tile.get("billedAmount"),
                })
        # Denied claims boost priority
        for row in rows:
            tile = normalize_claim_row(row)
            if tile and str(tile.get("status") or "").lower() in ("denied", "rejected"):
                seeds.append({
                    "claimId": tile.get("claimId"),
                    "patientInitials": _patient_initials(str(tile.get("patientName") or "")),
                    "ageDays": tile.get("ageDays"),
                    "bucket": tile.get("bucket") or "denied",
                    "billedAmount": tile.get("billedAmount"),
                })
        # Deduplicate by claimId
        seen = set()
        deduped = []
        for s in seeds:
            cid = s.get("claimId")
            if cid and cid not in seen:
                seen.add(cid)
                deduped.append(s)
        seeds = deduped[:40]
    except Exception:
        seeds = []

    has_data = bool(seeds) or bool(notes)
    return _wrap(
        widget_id="ar-collection-task-list",
        type_="collection-task-list",
        title="Collections Workbench",
        page="ar",
        size="full",
        status="ok" if has_data else "empty",
        data={
            "seeds": seeds,
            "notes": notes,
            "emptyMessage": "No aged claims or local notes — import SoftDent A/R and claims to populate.",
        },
        hint="Seeds from 30/60/90+ buckets and denied claims. PHI = initials only.",
        collapse_when_empty=False,
    )


def build_narratives_ai_insight(bundle: dict[str, Any]) -> dict[str, Any]:
    """
    Narratives page AI Insight (rule-backed variance).
    Compares draft count vs clinical notes availability.
    FE Contract: insight{widget_type, confidence, explanation, source_refs, data, action_cta}
    """
    state = _load_local_json("nr2:v2:narratives") or {}
    drafts = state.get("drafts") if isinstance(state.get("drafts"), list) else []
    draft_text = str(state.get("draftText") or "").strip()
    clinical = _section_rows(bundle, "softdent", "clinicalNotes") or []

    draft_count = len(drafts) + (1 if draft_text else 0)
    clinical_count = len(clinical)

    # Rule-backed logic only — no LLM, no invented dollars
    if draft_count == 0 and clinical_count > 0:
        explanation = f"{clinical_count} clinical note(s) available but no narrative drafts started."
        widget_type = "alert-banner"
        confidence = "high"
        action_cta = "Start draft from clinical notes"
    elif draft_count > 0 and clinical_count == 0:
        explanation = f"{draft_count} draft(s) saved without recent clinical notes import."
        widget_type = "alert-banner"
        confidence = "high"
        action_cta = "Import SoftDent clinical notes"
    elif draft_count > 0 and clinical_count > 0:
        explanation = f"Workflow active: {draft_count} draft(s), {clinical_count} note(s) available."
        widget_type = "kpi-card"
        confidence = "high"
        action_cta = "Review drafts"
    else:
        explanation = "No narrative drafts or clinical notes found."
        widget_type = "alert-banner"
        confidence = "high"
        action_cta = "Import clinical data"

    insight = {
        "widget_type": widget_type,
        "confidence": confidence,
        "explanation": explanation,
        "source_refs": ["nr2:v2:narratives", "softdent:clinicalNotes"],
        "data": {
            "draftCount": draft_count,
            "clinicalCount": clinical_count,
        },
        "action_cta": action_cta,
    }

    return _wrap(
        widget_id="narratives-ai-insight",
        type_="ai-insight",
        title="Narrative Insight",
        page="narratives",
        size="l",
        status="ok",
        data={"insight": insight},
        hint="Rule-backed variance (no LLM). source_refs required for audit.",
        collapse_when_empty=False,
    )


def build_softdent_patient_dossier(bundle: dict[str, Any]) -> dict[str, Any]:
    """
    SoftDent page patient dossier (empty until patient selected).
    FE Contract: data{patientHash, initials, primaryCarrier, openClaims, lastVisit, accountBalance, hasClinicalNotes, emptyMessage}
    """
    # Attempt to find a "selected" patient context from bundle (none = empty state)
    # SoftDent bridge does not yet provide single-patient selection; show honest empty.
    empty_msg = "Select a patient from the schedule (Mon–Thu) to load dossier."

    # If future bundle adds selectedPatient, populate here:
    selected = bundle.get("selectedPatient") if isinstance(bundle.get("selectedPatient"), dict) else None
    if selected:
        demo = selected.get("demographics") or {}
        payload = {
            "patientHash": selected.get("patientHash") or demo.get("nameHash") or "——",
            "initials": selected.get("initials") or demo.get("initials") or "P—",
            "primaryCarrier": selected.get("primaryCarrier") or demo.get("primaryCarrier"),
            "openClaims": selected.get("openClaims"),
            "lastVisit": selected.get("lastVisit") or demo.get("lastVisit") or "unknown",
            "accountBalance": selected.get("accountBalance") or "unavailable",
            "hasClinicalNotes": selected.get("hasClinicalNotes"),
            "emptyMessage": None,
        }
        st = "ok"
    else:
        payload = {
            "patientHash": "——",
            "initials": "P—",
            "primaryCarrier": None,
            "openClaims": None,
            "lastVisit": None,
            "accountBalance": None,
            "hasClinicalNotes": None,
            "emptyMessage": empty_msg,
        }
        st = "empty"

    return _wrap(
        widget_id="softdent-patient-dossier",
        type_="patient-dossier-card",
        title="Patient Dossier",
        page="softdent",
        size="l",
        status=st,
        data=payload,
        hint="PHI-safe hashes/initials · empty until patient selected.",
        collapse_when_empty=False,
    )
```

### File: `apex_backend.py` (wiring patches)

**In `_hal_widgets` (append before return):**
```python
    # Moonshot SHOULD: HAL recommended actions action-list
    from apex_better_backend_widgets_pack import build_hal_action_list
    widgets.append(build_hal_action_list(bundle))
```

**In `_ar_widgets` (append before return):**
```python
    # Moonshot SHOULD: A/R main page collection task list (honest empty when no seeds)
    from apex_better_backend_widgets_pack import build_ar_main_collection_task_list
    widgets.append(build_ar_main_collection_task_list(bundle))
```

**In `_narratives_widgets` (append before return):**
```python
    # Moonshot SHOULD: Narratives AI insight (rule-backed variance)
    from apex_better_backend_widgets_pack import build_narratives_ai_insight
    widgets.append(build_narratives_ai_insight(bundle))
```

**In `_softdent_widgets` (append before return):**
```python
    # Moonshot SHOULD: SoftDent patient dossier (empty placeholder)
    from apex_better_backend_widgets_pack import build_softdent_patient_dossier
    widgets.append(build_softdent_patient_dossier(bundle))
```

## 4. Validation Gate
```bash
# 1. Syntax/lint
python -m py_compile apex_better_backend_widgets_pack.py
python -m py_compile apex_backend.py

# 2. Import smoke test (within NR2 venv)
python -c "from apex_better_backend_widgets_pack import build_hal_action_list, build_ar_main_collection_task_list, build_narratives_ai_insight, build_softdent_patient_dossier; print('SHOULD builders import ok')"

# 3. FE contract validation (spot check)
# - /api/apex?page=hal should contain widget type "action-list" with data.items array
# - /api/apex?page=ar should contain widget type "collection-task-list" with data.seeds array (may be empty)
# - /api/apex?page=narratives should contain widget type "ai-insight" with data.insight.widget_type in {kpi-card,alert-banner}
# - /api/apex?page=softdent should contain widget type "patient-dossier-card" with data.emptyMessage when no patient selected

# 4. Honesty check
# - Verify no invented dollar amounts in seeds/insight
# - Verify emptyMessage present when datasets missing
# - Verify PHI limited to initials/hashes only
```

## 5. Apply Order
1. **Backup** `apex_better_backend_widgets_pack.py` and `apex_backend.py`
2. **Append** the four builders to `apex_better_backend_widgets_pack.py` (end of file)
3. **Patch** `apex_backend.py` – add the four import + append lines in respective widget functions
4. **Restart** backend service (hal-10567 assets already cached)
5. **Hard-refresh** browser and verify four new widgets appear per Validation Gate
6. **Commit** with message: `hal-10567-should: action-list (hal), collection-task-list (ar), ai-insight (narratives), patient-dossier (softdent)`

## 6. What NOT to redo
- **MUST (shipped hal-10567):** Tax Planning data-table, Collections radial-gauge, System Health status-matrix — already present, do not duplicate
- **NICE (future wave):** Aging Pareto chart, Tax calendar, Claim timeline-lanes — out of scope for this continue order
- **Existing OM widgets:** Claims needing narrative (action-list), Patient dossier card — already present via `apex_missing_widgets_pack`, do not duplicate on office-manager
- **Existing HAL widgets:** AI insight widget — already present via `apex_structured_insight_pack`, do not duplicate on hal (narratives gap only)