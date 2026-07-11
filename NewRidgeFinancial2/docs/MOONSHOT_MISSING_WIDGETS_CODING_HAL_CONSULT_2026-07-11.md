# Moonshot AI — Missing Widgets Coding + HAL Wiring (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** ~hal-10441+  
**Prior look consult:** `MOONSHOT_MISSING_WIDGETS_LOOK_CONSULT_2026-07-11.md`  
**Script:** `scripts/run_moonshot_missing_widgets_coding_hal_consult.py`  
**Apply:** DO NOT APPLY / WAIT FOR OPERATOR APPROVAL.

## Operator request (verbatim)

> ask moonoshot for coding of thiese widgets and how to wire them to hal, report and wait for approval

---

# Verdict

## 0. Operator Intent (quote; confirm consult-only / wait for approval)

> *"ask moonoshot for coding of thiese widgets and how to wire them to hal, report and wait for approval"*

**Confirmed CONSULT-ONLY.** No code will be generated, committed, or applied to build `hal-10441` until the operator explicitly approves a specific phase or the full set. This report provides paste-ready specifications for widgets W-01 through W-10, HAL wiring maps, and phased implementation guidance.

---

## 1. Architecture (files to touch; pack vs core vs HAL)

| Layer | File | Purpose |
|-------|------|---------|
| **Backend Pack** | `apex_missing_widgets_pack.py` (new) | Ten builder functions emitting widget specs into `apex_backend` mosaic. Imports from `financial_reports`, `import_loader`, `local_store`. Never invents dollar amounts. |
| **Frontend Core** | `site/apex-core.js` (append) | New `case` branches in `Widget.render()` for types: `treemap`, `scatter-plot`, `pareto-chart`, `timeline-lanes`, `credit-float`, `status-matrix`, `utilization-board`, `radial-gauge`. Reuses existing `funnel`, `waterfall`, `horizontal-bar` where applicable. |
| **HAL Wiring** | `resolve_hal_board_actions()` (append) | New `focus_rules` tuples mapping voice phrases to `navigate` + `focus_widget` + `highlight_widget`. No new board action types required (reuse existing). |
| **Styles** | `site/apex-theme.css` (append) | CSS variables for new instrument types (treemap cells, scatter points, matrix dots). |

**Integration Pattern:**
1. Backend pack builders emit specs with `type`, `widgetId`, `page`, `status` (`"ok"` | `"empty"` | `"awaiting-migration"`), and `data` (nulls/placeholders when missing).
2. Frontend `Widget` class switches on `spec.type`, renders honest empty states when `status !== "ok"`.
3. HAL `focus_rules` regexes route voice commands to page navigation + widget focus/highlight.
4. Ask-HAL button on each widget posts `context.widgetId` to board actions; HAL responds with deterministic `focus_widget` + `highlight_widget`.

---

## 2. Coding Spec Per Widget (W-01..W-10)

### W-01 — Expense Category Treemap
- **type:** `treemap`
- **widgetId:** `expense-treemap`
- **page:** `financial` (also available on `quickbooks`)
- **Payload JSON shape:**
```json
{
  "type": "treemap",
  "widgetId": "expense-treemap",
  "page": "financial",
  "title": "Expense Concentration",
  "status": "ok",
  "size": "l",
  "data": {
    "total": null,
    "categories": [
      {"name": "PAYROLL", "value": null, "children": [{"name": "Clinical Wages", "value": null}]},
      {"name": "SUPPLIES", "value": null, "children": [{"name": "Dental Supplies", "value": null}, {"name": "Lab", "value": null}]},
      {"name": "TAXES", "value": null, "children": []}
    ],
    "currency": "$",
    "emptyMessage": "Expense hierarchy unavailable"
  }
}
```
- **Python builder sketch (CONSULT ONLY):**
```python
def build_expense_treemap(bundle: dict) -> dict:
    qb = bundle.get("quickbooks", {})
    coa = qb.get("chart_of_accounts", {})
    rows = coa.get("rows", []) if isinstance(coa, dict) else []
    
    # Build hierarchical tree without inventing amounts
    categories = []
    for parent in rows[:6]:  # Top-level expense parents only
        children = [{"name": c.get("name", "Sub—"), "value": None} 
                   for c in parent.get("children", [])[:4]]
        categories.append({
            "name": parent.get("name", "Category—"),
            "value": None,  # Honest: _parse_money returns None if missing
            "children": children
        })
    
    return {
        "type": "treemap",
        "widgetId": "expense-treemap",
        "page": "financial",
        "title": "Expense Concentration",
        "status": "empty" if not categories else "ok",
        "size": "l",
        "data": {
            "total": None,
            "categories": categories,
            "currency": "$",
            "emptyMessage": "Expense hierarchy unavailable"
        }
    }
```
- **JS/CSS render sketch (CONSULT ONLY):**
  - **Render:** SVG `<rect>` elements nested with `x`, `y`, `width`, `height` proportional to value (when status ok) or equal sizes (when empty).
  - **Empty state:** Flat gray rectangles with 1px cyan borders, centered amber text "Expense hierarchy unavailable".
  - **Interactions:** Hover phosphor glow (cyan), corner brackets frame container.
  - **CSS:** `.apex-treemap-cell { stroke: var(--apex-cyan); fill-opacity: 0.2; }`, `.apex-treemap-cell:hover { fill-opacity: 0.6; filter: drop-shadow(0 0 4px var(--apex-cyan)); }`
- **Honesty/empty:** When QB import lacks nesting or amounts, renders flat gray grid with placeholder labels and "$—" amounts. No fabricated spending figures.
- **Effort:** M (requires hierarchical layout algorithm)

### W-02 — Procedure Profitability Scatter
- **type:** `scatter-plot`
- **widgetId:** `procedure-profitability-scatter`
- **page:** `financial`
- **Payload JSON shape:**
```json
{
  "type": "scatter-plot",
  "widgetId": "procedure-profitability-scatter",
  "page": "financial",
  "title": "Procedure Profitability",
  "status": "ok",
  "size": "l",
  "data": {
    "points": [
      {"code": "D—", "x": null, "y": null, "r": 5, "label": "D2740"},
      {"code": "D—", "x": null, "y": null, "r": 3, "label": "D4341"}
    ],
    "xLabel": "Billed Fee",
    "yLabel": "Net Collection",
    "medianX": null,
    "medianY": null,
    "emptyMessage": "Cost data unavailable"
  }
}
```
- **Python builder sketch (CONSULT ONLY):**
```python
def build_procedure_scatter(bundle: dict) -> dict:
    sd = bundle.get("softdent", {})
    proc_rows = sd.get("procedures", {}).get("rows", [])
    
    points = []
    for row in proc_rows[:50]:  # Limit for perf
        code = row.get("code", "D—")
        fee = _parse_money(row.get("billed_fee"))
        collected = _parse_money(row.get("net_collection"))
        volume = _parse_int(row.get("count")) or 5
        
        points.append({
            "code": code,
            "x": fee,
            "y": collected,
            "r": min(max(volume, 3), 20),  # Bubble size clamped
            "label": code
        })
    
    return {
        "type": "scatter-plot",
        "widgetId": "procedure-profitability-scatter",
        "page": "financial",
        "title": "Procedure Profitability",
        "status": "empty" if not points else "ok",
        "size": "l",
        "data": {
            "points": points,
            "xLabel": "Billed Fee",
            "yLabel": "Net Collection",
            "medianX": None,
            "medianY": None,
            "emptyMessage": "Cost data unavailable"
        }
    }
```
- **JS/CSS render sketch (CONSULT ONLY):**
  - **Render:** Canvas or SVG `<circle>` elements. Quadrant lines at median splits (when data available) or center (when empty).
  - **Empty state:** All dots clustered at origin (0,0) with amber overlay text "Cost data unavailable"; axes labeled "$—".
  - **Interactions:** Crosshair laser cursor snaps to nearest dot on hover; tooltip shows code + placeholder amounts.
  - **CSS:** `.apex-scatter-point { fill: var(--apex-cyan); }`, `.apex-scatter-point--underpaid { fill: var(--apex-amber); }`, `.apex-scatter-point--low-collect { fill: var(--apex-magenta); }`
- **Honesty/empty:** When QB unlinked or cost data missing, dots cluster at origin with "Cost data unavailable" overlay. No invented profit margins.
- **Effort:** M (canvas rendering + quadrant math)

### W-03 — Denial Reason Pareto
- **type:** `pareto-chart` (composite: horizontal-bar + line overlay)
- **widgetId:** `denial-pareto`
- **page:** `claims`
- **Payload JSON shape:**
```json
{
  "type": "pareto-chart",
  "widgetId": "denial-pareto",
  "page": "claims",
  "title": "Denial Pareto",
  "status": "ok",
  "size": "l",
  "data": {
    "bars": [
      {"code": "CO-45", "amount": null, "count": null, "pct": 45},
      {"code": "PR-2", "amount": null, "count": null, "pct": 27}
    ],
    "cumulative": [45, 72, 85, 92],
    "threshold": 80,
    "emptyMessage": "No denials recorded"
  }
}
```
- **Python builder sketch (CONSULT ONLY):**
```python
def build_denial_pareto(bundle: dict) -> dict:
    claims = bundle.get("claims", {})
    denials = claims.get("denial_codes", [])
    
    bars = []
    cumulative = []
    running = 0
    
    # Sort by count desc (honest nulls when unavailable)
    for d in denials[:8]:
        code = d.get("code", "CO—")
        count = _parse_int(d.get("count"))
        amt = _parse_money(d.get("amount"))
        pct = d.get("pct", 0)
        running += pct
        bars.append({"code": code, "amount": amt, "count": count, "pct": pct})
        cumulative.append(min(running, 100))
    
    return {
        "type": "pareto-chart",
        "widgetId": "denial-pareto",
        "page": "claims",
        "title": "Denial Pareto",
        "status": "empty" if not bars else "ok",
        "size": "l",
        "data": {
            "bars": bars,
            "cumulative": cumulative,
            "threshold": 80,
            "emptyMessage": "No denials recorded"
        }
    }
```
- **JS/CSS render sketch (CONSULT ONLY):**
  - **Render:** Horizontal bars (cyan fill) sorted descending. Amber line tracks cumulative % across top. Magenta dashed vertical line at 80% threshold.
  - **Empty state:** Single gray bar with "No denials recorded"; cumulative line hugs 0% baseline.
  - **CSS:** `.apex-pareto-bar { fill: var(--apex-cyan); }`, `.apex-pareto-line { stroke: var(--apex-amber); stroke-width: 2; }`, `.apex-pareto-threshold { stroke: var(--apex-magenta); stroke-dasharray: 4; }`
- **Honesty/empty:** When no ERA 835 or denial data, displays "No denials recorded" with zeroed bars.
- **Effort:** S (extends existing horizontal-bar with line overlay)

### W-04 — Treatment Plan Conversion Pipeline
- **type:** `funnel` (reuse existing renderer)
- **widgetId:** `treatment-conversion-pipeline`
- **page:** `financial` (also `office-manager`)
- **Payload JSON shape:**
```json
{
  "type": "funnel",
  "widgetId": "treatment-conversion-pipeline",
  "page": "financial",
  "title": "Treatment Conversion",
  "status": "ok",
  "size": "l",
  "data": {
    "stages": [
      {"name": "Presented", "count": null, "value": null, "conversionRate": null},
      {"name": "Accepted", "count": null, "value": null, "conversionRate": null},
      {"name": "Scheduled", "count": null, "value": null, "conversionRate": null},
      {"name": "Completed", "count": null, "value": null, "conversionRate": null}
    ],
    "emptyMessage": "No treatment plan data"
  }
}
```
- **Python builder sketch (CONSULT ONLY):**
```python
def build_treatment_pipeline(bundle: dict) -> dict:
    sd = bundle.get("softdent", {})
    plans = sd.get("treatment_plans", {}).get("by_status", {})
    
    stages = []
    prev_count = None
    for status in ["Presented", "Accepted", "Scheduled", "Completed"]:
        count = _parse_int(plans.get(status, {}).get("count"))
        value = _parse_money(plans.get(status, {}).get("value"))
        rate = None
        if prev_count and count:
            rate = round((count / prev_count) * 100, 1)
        stages.append({
            "name": status,
            "count": count,
            "value": value,
            "conversionRate": rate
        })
        prev_count = count
    
    return {
        "type": "funnel",
        "widgetId": "treatment-conversion-pipeline",
        "page": "financial",
        "title": "Treatment Conversion",
        "status": "empty" if not any(s["count"] for s in stages) else "ok",
        "size": "l",
        "data": {
            "stages": stages,
            "emptyMessage": "No treatment plan data"
        }
    }
```
- **JS/CSS render sketch (CONSULT ONLY):**
  - **Render:** Reuse existing funnel renderer. Four trapezoid stages narrowing downward. Between stages, small magenta percentages display conversion rate.
  - **Empty state:** Single gray trapezoid with "No treatment plan data"; counts show "—" and values "$—".
  - **CSS:** Reuse `.apex-funnel-stage`, `.apex-funnel-connector` (magenta text for conversion %).
- **Honesty/empty:** When SoftDent treatment plan export missing, single gray funnel stage with placeholders.
- **Effort:** M (funnel layout math + conversion calc)

### W-05 — Pre-Authorization Aging Lanes
- **type:** `timeline-lanes`
- **widgetId:** `preauth-aging-lanes`
- **page:** `claims`
- **Payload JSON shape:**
```json
{
  "type": "timeline-lanes",
  "widgetId": "preauth-aging-lanes",
  "page": "claims",
  "title": "Pre-Auth Lanes",
  "status": "ok",
  "size": "m",
  "data": {
    "lanes": [
      {
        "code": "D0150",
        "total": null,
        "segments": [
          {"bucket": "0-30", "count": 0, "color": "cyan"},
          {"bucket": "31-60", "count": 0, "color": "amber"},
          {"bucket": "61-90", "count": 0, "color": "magenta"},
          {"bucket": "90+", "count": 0, "color": "alert"}
        ]
      }
    ],
    "emptyMessage": "No pending pre-auths"
  }
}
```
- **Python builder sketch (CONSULT ONLY):**
```python
def build_preauth_lanes(bundle: dict) -> dict:
    sd = bundle.get("softdent", {})
    preauths = sd.get("preauthorizations", [])
    
    from collections import defaultdict
    by_code = defaultdict(lambda: {"0-30": 0, "31-60": 0, "61-90": 0, "90+": 0})
    
    for p in preauths:
        code = p.get("procedure_code", "D—")
        age = _parse_int(p.get("age_days")) or 0
        if age <= 30:
            by_code[code]["0-30"] += 1
        elif age <= 60:
            by_code[code]["31-60"] += 1
        elif age <= 90:
            by_code[code]["61-90"] += 1
        else:
            by_code[code]["90+"] += 1
    
    lanes = []
    for code, segs in sorted(by_code.items()):
        total = sum(segs.values())
        lanes.append({
            "code": code,
            "total": total if total > 0 else None,
            "segments": [
                {"bucket": k, "count": v, "color": {"0-30": "cyan", "31-60": "amber", "61-90": "magenta", "90+": "alert"}[k]}
                for k, v in segs.items()
            ]
        })
    
    return {
        "type": "timeline-lanes",
        "widgetId": "preauth-aging-lanes",
        "page": "claims",
        "title": "Pre-Auth Lanes",
        "status": "empty" if not lanes else "ok",
        "size": "m",
        "data": {
            "lanes": lanes,
            "emptyMessage": "No pending pre-auths"
        }
    }
```
- **JS/CSS render sketch (CONSULT ONLY):**
  - **Render:** Horizontal stacked bar per procedure code. Segments: cyan (0-30d), amber (31-60d), magenta (61-90d), red-alert (90+d).
  - **Empty state:** Single line "No pending pre-auths" with all segments showing 0 counts.
  - **CSS:** `.apex-lane-segment--cyan { background: var(--apex-cyan); }`, `.apex-lane-segment--alert { background: var(--apex-red); }`
- **Honesty/empty:** When no pre-auth export, collapses to single line with zeroed segments.
- **Effort:** S (stacked bar variant)

### W-06 — Unapplied Credit Float Strip
- **type:** `credit-float`
- **widgetId:** `unapplied-credit-float`
- **page:** `ar`
- **Payload JSON shape:**
```json
{
  "type": "credit-float",
  "widgetId": "unapplied-credit-float",
  "page": "ar",
  "title": "Unapplied Float",
  "status": "ok",
  "size": "strip",
  "data": {
    "credits": [
      {"patientHash": "A—", "amount": null},
      {"patientHash": "B—", "amount": null}
    ],
    "total": null,
    "count": 0,
    "emptyMessage": "No unapplied credits"
  }
}
```
- **Python builder sketch (CONSULT ONLY):**
```python
def build_unapplied_float(bundle: dict) -> dict:
    sd = bundle.get("softdent", {})
    payments = sd.get("unapplied_payments", [])
    
    credits = []
    total = 0.0
    for p in payments[:20]:  # Limit display
        amt = _parse_money(p.get("amount"))
        if amt:
            total += amt
        # Anonymize: use initials or hash only
        raw_name = p.get("patient_name", "Patient")
        initials = "".join([x[0] for x in raw_name.split()[:2] if x]).upper() or "P—"
        credits.append({
            "patientHash": f"{initials}—",
            "amount": amt
        })
    
    return {
        "type": "credit-float",
        "widgetId": "unapplied-credit-float",
        "page": "ar",
        "title": "Unapplied Float",
        "status": "empty" if not credits else "ok",
        "size": "strip",
        "collapseWhenEmpty": True,
        "data": {
            "credits": credits,
            "total": total if total > 0 else None,
            "count": len(credits),
            "emptyMessage": "No unapplied credits"
        }
    }
```
- **JS/CSS render sketch (CONSULT ONLY):**
  - **Render:** Full-width strip (~80px). Left: cyan label. Center: flowing row of amber pills `[Patient A: $—]`. Right: cyan total. Horizontal scroll on overflow.
  - **Empty state:** Hides completely when zero (collapseWhenEmpty), or shows amber pill "No unapplied credits" when import missing.
  - **PHI:** Displays only initials + hash (e.g., "JD—").
  - **CSS:** `.apex-float-strip { display: flex; overflow-x: auto; }`, `.apex-float-pill { background: var(--apex-amber); color: var(--apex-bg); border-radius: 12px; padding: 2px 8px; margin-right: 8px; }`
- **Honesty/empty:** Hides when zero; never shows real names.
- **Effort:** XS (simple strip layout)

### W-07 — Cash Flow Bridge Waterfall
- **type:** `waterfall` (reuse existing renderer with vertical orientation)
- **widgetId:** `cash-flow-bridge`
- **page:** `financial`
- **Payload JSON shape:**
```json
{
  "type": "waterfall",
  "widgetId": "cash-flow-bridge",
  "page": "financial",
  "title": "Cash Flow Bridge — 30 Day",
  "status": "ok",
  "size": "l",
  "data": {
    "steps": [
      {"label": "Start Cash", "value": null, "type": "start"},
      {"label": "Expected Collections", "value": null, "type": "add"},
      {"label": "Overhead", "value": null, "type": "sub"},
      {"label": "Loan Service", "value": null, "type": "sub"},
      {"label": "Projected Cash", "value": null, "type": "end"}
    ],
    "start": null,
    "projected": null,
    "emptyMessage": "Cash projection unavailable"
  }
}
```
- **Python builder sketch (CONSULT ONLY):**
```python
def build_cash_bridge(bundle: dict) -> dict:
    qb = bundle.get("quickbooks", {})
    ar = bundle.get("ar", {})
    
    start = _parse_money(qb.get("cash_balance"))
    projected_collections = _parse_money(ar.get("projected_30d_collections"))
    overhead = _parse_money(qb.get("scheduled_overhead"))
    debt_service = _parse_money(qb.get("debt_service"))
    
    # Calculate only if all present; otherwise None
    projected = None
    if all([start, projected_collections, overhead, debt_service]):
        projected = start + projected_collections - overhead - debt_service
    
    return {
        "type": "waterfall",
        "widgetId": "cash-flow-bridge",
        "page": "financial",
        "title": "Cash Flow Bridge — 30 Day",
        "status": "empty" if start is None else "ok",
        "size": "l",
        "data": {
            "steps": [
                {"label": "Start Cash", "value": start, "type": "start"},
                {"label": "Expected Collections", "value": projected_collections, "type": "add"},
                {"label": "Overhead", "value": overhead, "type": "sub"},
                {"label": "Loan Service", "value": debt_service, "type": "sub"},
                {"label": "Projected Cash", "value": projected, "type": "end"}
            ],
            "start": start,
            "projected": projected,
            "emptyMessage": "Cash projection unavailable"
        }
    }
```
- **JS/CSS render sketch (CONSULT ONLY):**
  - **Render:** Vertical waterfall. Starting bar (cyan) full height. Floating bars: cyan upward (add), magenta downward (sub). Connector lines between bars. Ending bar (amber).
  - **Empty state:** Grays out intermediate bars; shows starting balance only (or "$—" if missing) with overlay text.
  - **CSS:** Reuse `.apex-waterfall-bar--start`, `.apex-waterfall-bar--add`, `.apex-waterfall-bar--sub`, `.apex-waterfall-bar--end`.
- **Honesty/empty:** When QB or A/R projection missing, grays out bars and shows "Cash projection unavailable".
- **Effort:** M (waterfall layout + connector lines)

### W-08 — Insurance Verification Matrix
- **type:** `status-matrix`
- **widgetId:** `verification-matrix`
- **page:** `claims` (also `office-manager`)
- **Payload JSON shape:**
```json
{
  "type": "status-matrix",
  "widgetId": "verification-matrix",
  "page": "claims",
  "title": "Verification Matrix — Next 3D",
  "status": "ok",
  "size": "m",
  "data": {
    "patients": [
      {"hash": "A—", "elig": "verified", "ben": "verified", "breakdown": "pending"},
      {"hash": "B—", "elig": "verified", "ben": null, "breakdown": null}
    ],
    "columns": ["Elig", "Ben", "Breakdown"],
    "nextDays": 3,
    "emptyMessage": "Verification tracking disabled"
  }
}
```
- **Python builder sketch (CONSULT ONLY):**
```python
def build_verification_matrix(bundle: dict) -> dict:
    sd = bundle.get("softdent", {})
    appts = sd.get("appointments_next_3d", [])
    
    patients = []
    for a in appts[:12]:  # Limit rows
        name = a.get("patient_name", "Patient")
        initials = "".join([x[0] for x in name.split()[:2] if x]).upper() or "P—"
        patients.append({
            "hash": f"{initials}—",
            "elig": a.get("eligibility_status"),  # verified, pending, failed, None
            "ben": a.get("benefits_status"),
            "breakdown": a.get("breakdown_status")
        })
    
    return {
        "type": "status-matrix",
        "widgetId": "verification-matrix",
        "page": "claims",
        "title": "Verification Matrix — Next 3D",
        "status": "empty" if not patients else "ok",
        "size": "m",
        "data": {
            "patients": patients,
            "columns": ["Elig", "Ben", "Breakdown"],
            "nextDays": 3,
            "emptyMessage": "Verification tracking disabled"
        }
    }
```
- **JS/CSS render sketch (CONSULT ONLY):**
  - **Render:** Compact grid (rows × 3 columns). Status dots: cyan (verified), amber (pending), magenta (failed), gray/empty (unknown).
  - **Empty state:** All gray dots with "Verification tracking disabled" header.
  - **PHI:** Shows only hashed initials (e.g., "JD—").
  - **CSS:** `.apex-matrix-dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }`, `.apex-matrix-dot--verified { background: var(--apex-cyan); }`
- **Honesty/empty:** When SoftDent field missing, matrix shows all gray dots.
- **Effort:** S (grid layout)

### W-09 — Operatory Utilization Board
- **type:** `utilization-board`
- **widgetId:** `operatory-util-board`
- **page:** `office-manager`
- **Payload JSON shape:**
```json
{
  "type": "utilization-board",
  "widgetId": "operatory-util-board",
  "page": "office-manager",
  "title": "Operatory Board",
  "status": "ok",
  "size": "l",
  "data": {
    "operatories": [
      {
        "name": "Op-1",
        "slots": [
          {"time": "08:00", "status": "booked", "patientHash": "A—"},
          {"time": "09:00", "status": "open", "patientHash": null}
        ]
      }
    ],
    "date": "2026-07-11",
    "emptyMessage": "No schedule data"
  }
}
```
- **Python builder sketch (CONSULT ONLY):**
```python
def build_operatory_board(bundle: dict) -> dict:
    sd = bundle.get("softdent", {})
    schedule = sd.get("schedule_today", {})
    ops = schedule.get("operatories", [])
    
    operatories = []
    for op in ops[:6]:
        slots = []
        for slot in op.get("slots", []):
            name = slot.get("patient_name", "")
            initials = "".join([x[0] for x in name.split()[:2] if x]).upper() if name else None
            slots.append({
                "time": slot.get("time", "—"),
                "status": slot.get("status", "open"),  # booked, open, blocked
                "patientHash": f"{initials}—" if initials else None
            })
        operatories.append({
            "name": op.get("name", "Op—"),
            "slots": slots
        })
    
    return {
        "type": "utilization-board",
        "widgetId": "operatory-util-board",
        "page": "office-manager",
        "title": "Operatory Board",
        "status": "empty" if not operatories else "ok",
        "size": "l",
        "data": {
            "operatories": operatories,
            "date": schedule.get("date"),
            "emptyMessage": "No schedule data"
        }
    }
```
- **JS/CSS render sketch (CONSULT ONLY):**
  - **Render:** Grid view: rows = operatories, columns = time slots. Booked slots show amber block with patient hash; open slots show cyan outline; blocked show gray.
  - **Empty state:** "No schedule data" with grayed grid.
  - **PHI:** Patient names hashed to initials + "—".
  - **CSS:** `.apex-op-slot { border: 1px solid var(--apex-cyan); }`, `.apex-op-slot--booked { background: var(--apex-amber); }`
- **Honesty/empty:** When schedule export missing, shows empty grid.
- **Effort:** M (grid layout + time bucketing)

### W-10 — Recall Gauge
- **type:** `radial-gauge`
- **widgetId:** `recall-gauge`
- **page:** `office-manager`
- **Payload JSON shape:**
```json
{
  "type": "radial-gauge",
  "widgetId": "recall-gauge",
  "page": "office-manager",
  "title": "Recall Status",
  "status": "ok",
  "size": "m",
  "data": {
    "due": null,
    "scheduled": null,
    "contacted": null,
    "totalActive": null,
    "pctScheduled": null,
    "emptyMessage": "Recall tracking unavailable"
  }
}
```
- **Python builder sketch (CONSULT ONLY):**
```python
def build_recall_gauge(bundle: dict) -> dict:
    sd = bundle.get("softdent", {})
    recall = sd.get("recall_stats", {})
    
    due = _parse_int(recall.get("due_count"))
    scheduled = _parse_int(recall.get("scheduled_count"))
    contacted = _parse_int(recall.get("contacted_count"))
    total = _parse_int(recall.get("total_active"))
    
    pct = None
    if due and scheduled:
        pct = round((scheduled / due) * 100, 1)
    
    return {
        "type": "radial-gauge",
        "widgetId": "recall-gauge",
        "page": "office-manager",
        "title": "Recall Status",
        "status": "empty" if due is None else "ok",
        "size": "m",
        "data": {
            "due": due,
            "scheduled": scheduled,
            "contacted": contacted,
            "totalActive": total,
            "pctScheduled": pct,
            "emptyMessage": "Recall tracking unavailable"
        }
    }
```
- **JS/CSS render sketch (CONSULT ONLY):**
  - **Render:** SVG arc gauge (0-100%). Cyan fill up to scheduled %, amber marker for target (80%), magenta background track.
  - **Empty state:** Gray arc with "Recall tracking unavailable" centered.
  - **CSS:** `.apex-gauge-arc { fill: none; stroke-width: 12; }`, `.apex-gauge-arc--fill { stroke: var(--apex-cyan); }`, `.apex-gauge-arc--track { stroke: var(--apex-magenta); opacity: 0.3; }`
- **Honesty/empty:** When recall data missing, shows gray empty gauge.
- **Effort:** S (SVG arc math)

---

## 3. HAL Wiring Map

| Phrase Patterns (regex) | Navigate Page | Focus widgetId | Notes |
|-------------------------|---------------|----------------|-------|
| `\bexpense treemap\|spending (map\|tree)\|where (is\|does) (the )?money go\b` | financial | expense-treemap | Shows QB expense hierarchy |
| `\bprocedure profitability\|procedure scatter\|dental code profit\|which procedures (lose\|make) money\b` | financial | procedure-profitability-scatter | Requires SoftDent + QB cost link |
| `\bdenial pareto\|denial (reason )?chart\|claim denials by impact\|top denial (codes\|reasons)\b` | claims | denial-pareto | Needs ERA 835 remittance |
| `\btreatment (plan )?conversion\|case acceptance\|treatment pipeline\|presented to accepted\b` | financial | treatment-conversion-pipeline | SoftDent treatment plan status |
| `\bpre[- ]?auth (aging\|lanes)\|preauthorization status\|pending preauths\|pre-auth timeline\b` | claims | preauth-aging-lanes | Pre-auth aging by procedure |
| `\bunapplied (credit\|payment)s?\|credit float\|floating money\|unallocated payments\b` | ar | unapplied-credit-float | Shows unapplied payment strip |
| `\bcash (flow )?bridge\|liquidity bridge\|cash projection\|30 day cash\b` | financial | cash-flow-bridge | QB + A/R projection |
| `\b(insurance )?verification matrix\|eligibility matrix\|verify (patients\|benefits)\|insurance check\b` | claims | verification-matrix | Next 3 days verification status |
| `\boperatory (util\|board\|schedule)\|chair (util\|schedule)\|room (board\|schedule)\|op schedule\b` | office-manager | operatory-util-board | Today's chair utilization |
| `\brecall gauge\|recall (status\|tracker)\|hygiene (recall\|due)\|recall (percent\|rate)\b` | office-manager | recall-gauge | Recall due vs scheduled |

**Paste-ready focus_rules tuples (CONSULT ONLY — append to resolve_hal_board_actions):**

```python
    # W-01..W-10 Missing Widgets (CONSULT ONLY — DO NOT APPLY UNTIL APPROVED)
    (r"\bexpense treemap|spending (map|tree)|where (is|does) (the )?money go\b", "expense-treemap", "financial"),
    (r"\bprocedure profitability|procedure scatter|dental code profit|which procedures (lose|make) money\b", "procedure-profitability-scatter", "financial"),
    (r"\bdenial pareto|denial (reason )?chart|claim denials by impact|top denial (codes|reasons)\b", "denial-pareto", "claims"),
    (r"\btreatment (plan )?conversion|case acceptance|treatment pipeline|presented to accepted\b", "treatment-conversion-pipeline", "financial"),
    (r"\bpre[- ]?auth (aging|lanes)|preauthorization status|pending preauths|pre-auth timeline\b", "preauth-aging-lanes", "claims"),
    (r"\bunapplied (credit|payment)s?|credit float|floating money|unallocated payments\b", "unapplied-credit-float", "ar"),
    (r"\bcash (flow )?bridge|liquidity bridge|cash projection|30 day cash\b", "cash-flow-bridge", "financial"),
    (r"\b(insurance )?verification matrix|eligibility matrix|verify (patients|benefits)|insurance check\b", "verification-matrix", "claims"),
    (r"\boperatory (util|board|schedule)|chair (util|schedule)|room (board|schedule)|op schedule\b", "operatory-util-board", "office-manager"),
    (r"\brecall gauge|recall (status|tracker)|hygiene (recall|due)|recall (percent|rate)\b", "recall-gauge", "office-manager"),
```

---

## 4. Ask-HAL / Board Action Integration

**Standard Integration (all widgets):**
- Each widget renders an Ask-HAL button (existing pattern in `apex-core.js`) that posts to `/api/hal/board` with payload:
```json
{
  "query": "Explain this widget",
  "context": {"widgetId": "expense-treemap", "page": "financial", "status": "ok"},
  "page": "financial"
}
```
- HAL responds with deterministic actions: `[{"type": "focus_widget", "widgetId": "expense-treemap"}, {"type": "highlight_widget", "widgetId": "expense-treemap", "ms": 4000}]`

**No New Board Action Types Required:**
- Reuse existing: `navigate`, `focus_widget`, `highlight_widget`, `refresh_page`, `sync_imports`
- Optional enhancement: `refresh_widget` (targeted refresh) can be added later but not required for Phase 1.

**Widget-Specific HAL Context:**
- W-06, W-08, W-09 include `patientHash` (anonymized) in context so HAL can reference "Patient A" without exposing PHI.
- W-03 includes `denialCodes` list for HAL to summarize top issues.

---

## 5. Implementation Phases + Validation Gates (DO NOT APPLY)

**Phase 1 — Quick Wins (XS/S Effort)**
1. **W-06** Unapplied Credit Float (XS) — strip layout, immediate A/R value
2. **W-03** Denial Pareto (S) — extends existing horizontal-bar
3. **W-05** Pre-Auth Lanes (S) — stacked bar variant
4. **W-08** Verification Matrix (S) — grid layout, PHI-safe
5. **W-10** Recall Gauge (S) — SVG radial

*Validation Gate 1:* All Phase 1 widgets render honest empty states when imports missing; no invented dollar amounts; PHI anonymized; HAL wiring responds to voice commands.

**Phase 2 — Medium Complexity (M Effort)**
6. **W-04** Treatment Pipeline (M) — funnel layout with conversion math
7. **W-09** Operatory Board (M) — time-grid layout
8. **W-01** Expense Treemap (M) — hierarchical layout algorithm
9. **W-02** Procedure Scatter (M) — canvas/SVG scatter with quadrants
10. **W-07** Cash Bridge (M) — waterfall with connector lines

*Validation Gate 2:* Phase 2 widgets integrate with existing QB/SoftDent imports; W-02 correctly handles null cost data; W-07 grays out when projections unavailable.

**Phase 3 — HAL Polish (S Effort)**
- Fine-tune regex patterns in `focus_rules` based on operator voice testing
- Add targeted `refresh_widget` actions if performance requires

---

## 6. Approval Checklist

**STOP. DO NOT APPLY CODE UNTIL OPERATOR EXPLICITLY APPROVES.**

- [ ] **Operator confirms:** CONSULT-ONLY mode understood; no files touched yet
- [ ] **Operator selects:** Phase 1 only / Phase 1+2 / All phases
- [ ] **Operator validates:** Widget IDs (`expense-treemap`, `denial-pareto`, etc.) match internal naming conventions
- [ ] **Operator confirms:** PHI handling (initials + hash) acceptable for W-06, W-08, W-09
- [ ] **Operator confirms:** "Honest empty" behavior acceptable (no fabricated dollars)
- [ ] **Operator provides:** Go-ahead to create `apex_missing_widgets_pack.py` and modify `apex-core.js` + `resolve_hal_board_actions`

**Awaiting operator instruction:** `approve phase 1` / `approve all` / `modify spec [X]` / `cancel`.