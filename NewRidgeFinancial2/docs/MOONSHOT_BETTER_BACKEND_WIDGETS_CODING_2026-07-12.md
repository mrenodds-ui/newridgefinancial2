# Moonshot AI — Better Backend Widgets CODING (CONTINUE / NO DEVIATE)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10566  
**Script:** `scripts/run_moonshot_better_backend_widgets_coding_consult.py`  
**Prior:** MOONSHOT_BETTER_BACKEND_WIDGETS_CONSULT_2026-07-12.md  
**Operator:** continue with moonshot — do not deviate  

## Operator request (verbatim)

> continue with moonhot and do not deviate

---

# Verdict

APPLY-READY CODING for Moonshot Better Backend Widgets (hal-10566). Delivers three MUST widgets adapted to live frontend contracts with minimal FE patches.

## 0. Operator Intent (verbatim continue / do not deviate)

> "continue with moonhot and do not deviate"
> "Continue the better-backend-widgets Moonshot package. DO NOT DEVIATE from MUST items. Deliver apply-ready coding adapted to LIVE FE contracts."

Confirmed: Ship Tax Planning Data-Table, Collections Radial-Gauge, and System Health Status-Matrix only. No new roadmap items. No deviation to SHOULD/NICE widgets.

## 1. MUST Adaptations (consult sketch → live contracts)

| MUST Widget | Consult Sketch | Live Contract Conflict | Adaptation |
|-------------|----------------|------------------------|------------|
| **Tax Planning Data-Table** | Generic columns/rows | None — data-table contract accepts arbitrary columns | Direct emit; columns=["Item","Type","Status","Impact","Due"] |
| **Collections Radial-Gauge** | Collection % to 98% target | FE hardcodes target=80%, labels (Due/Sch/Contacted), empty check on `data.due` | FE patch: support `data.target`, `data.pct` (alias), `data.mode` for label sets; backend emits `mode:"collections"` + mapped fields |
| **System Health Status-Matrix** | 2×2 grid of systems | FE hardcodes headers ("Elig","Ben","Break") and `patients[]` shape | FE patch: support `data.headers` array; backend emits `patients` mapped with hash=System, elig=Import, ben=Sync, breakdown=Feed |

## 2. Files to Touch

1. **NEW:** `apex_better_backend_widgets_pack.py` — three builders (data-table, radial-gauge adapter, status-matrix adapter)
2. **MODIFY:** `apex_backend.py` — wire builders into `_taxes_widgets`, `_financial_widgets_from_reports`, `_office_manager_widgets`
3. **PATCH:** `apex-core.js` — minimal extensions to radial-gauge (configurable target/labels) and status-matrix (configurable headers)

## 3. Paste-ready Code

### 3.1 apex_better_backend_widgets_pack.py (NEW FILE)

```python
"""
NR2 Apex — Better Backend Widgets Pack (Moonshot MUST items).
Emit denser widget types without KPI sprawl.

Honesty constraints:
- Never invents dollar amounts.
- empty ≠ $0 (DEF-001).
- Maps live FE contracts via minimal adaptation layer.
"""

from __future__ import annotations

from typing import Any


def _parse_money(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("$", "")
    if not text or text in {"—", "-", "N/A", "n/a"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _initials(name: str) -> str:
    parts = str(name).strip().split()
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[-1][0]}".upper()
    if parts:
        return parts[0][:2].upper()
    return "—"


def _iso_to_display(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        from datetime import datetime
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return d.strftime("%b %d")
    except Exception:
        return str(iso)[:10]


def build_tax_planning_data_table(bundle: dict[str, Any]) -> dict[str, Any] | None:
    """
    MUST: Tax Planning Data-Table for taxes page (main or planning).
    Emits dense table replacing KPI tiles for planning items.
    """
    plan: dict[str, Any] = {}
    try:
        from tax_engine import build_tax_plan_from_bundle
        plan = build_tax_plan_from_bundle(bundle) or {}
    except Exception:
        plan = {}

    items: list[dict[str, Any]] = []
    
    # K-1 / Owner pass-through items
    bridge = plan.get("bridgeLines") if isinstance(plan.get("bridgeLines"), list) else []
    for b in bridge:
        if not isinstance(b, dict):
            continue
        line = str(b.get("line") or "")
        amt = _parse_money(b.get("amount"))
        items.append({
            "Item": line or "Owner distribution",
            "Type": "Pass-through",
            "Status": "Mapped" if line else "Unmapped",
            "Impact": amt,
            "Due": "Year-end",
        })

    # Quarterly estimates
    quarterly = plan.get("quarterlyEstimates") if isinstance(plan.get("quarterlyEstimates"), list) else []
    for q in quarterly:
        if not isinstance(q, dict):
            continue
        quarter = str(q.get("quarter") or q.get("period") or "Q?")
        amt = _parse_money(q.get("amount") or q.get("estimatedTax"))
        due = q.get("dueDate") or q.get("deadline")
        items.append({
            "Item": f"Est. Tax {quarter}",
            "Type": "1040-ES",
            "Status": "Due" if amt else "TBD",
            "Impact": amt,
            "Due": _iso_to_display(due) if due else "TBD",
        })

    # Officer W-2 modeling (if present)
    w2s = plan.get("officerW2s") if isinstance(plan.get("officerW2s"), list) else []
    for w in w2s:
        if not isinstance(w, dict):
            continue
        name = str(w.get("officer") or w.get("name") or "Officer")
        wages = _parse_money(w.get("wages") or w.get("w2Wages"))
        items.append({
            "Item": f"W-2 {_initials(name)}",
            "Type": "Officer comp",
            "Status": "Modeled",
            "Impact": wages,
            "Due": "Jan 31",
        })

    if not items:
        return {
            "id": "tax-planning-table",
            "type": "data-table",
            "label": "Tax Planning Items",
            "size": "l",
            "status": "empty",
            "emptyMessage": "Import QuickBooks and SoftDent to populate planning items.",
            "hint": "Tax planning requires book data and tax_engine mapping.",
            "columns": ["Item", "Type", "Status", "Impact", "Due"],
            "rows": [],
        }

    # Format money for display handled by FE; keep raw numbers for sorting
    return {
        "id": "tax-planning-table",
        "type": "data-table",
        "label": "Tax Planning Items",
        "size": "l",
        "status": "ok",
        "columns": ["Item", "Type", "Status", "Impact", "Due"],
        "rows": items,
        "hint": f"{len(items)} planning items from tax_engine — CPA review required.",
        "collapseWhenEmpty": False,
    }


def build_collections_radial_gauge(bundle: dict[str, Any], reports: dict[str, Any]) -> dict[str, Any] | None:
    """
    MUST: Collections Radial-Gauge for financial/ar pages.
    Adapted to live radial-gauge contract via mode flag.
    """
    # Derive collection efficiency from reports
    rows = reports.get("productionCollectionsRows") or reports.get("financialRows") or []
    if not rows and isinstance(bundle.get("financial"), dict):
        rows = bundle["financial"].get("rows") or []
    
    chosen = None
    for row in reversed(rows):
        if not isinstance(row, dict):
            continue
        prod = _parse_money(row.get("production") or row.get("Production"))
        coll = _parse_money(row.get("collections") or row.get("Collections"))
        if prod and coll and prod > 0:
            # Check if collections reported (not pending)
            pending = row.get("collectionsPending") or row.get("pending")
            if not pending:
                chosen = (prod, coll, row.get("period") or row.get("year_month"))
                break
    
    if not chosen:
        return {
            "id": "collections-gauge",
            "type": "radial-gauge",
            "label": "Collection Efficiency",
            "size": "m",
            "status": "empty",
            "emptyMessage": "Collections pending or production not reported",
            "hint": "Ratio appears when both production and collections are finalized.",
            "data": {
                "due": None,
                "pctScheduled": None,
                "scheduled": None,
                "contacted": None,
                "mode": "collections",
                "target": 98,
            },
        }
    
    prod, coll, period = chosen
    ratio_pct = round((coll / prod) * 100, 1)
    
    return {
        "id": "collections-gauge",
        "type": "radial-gauge",
        "label": "Collection Efficiency",
        "size": "m",
        "status": "ok",
        "hint": f"Collections ÷ production for {period or 'period'} — target 98%.",
        "data": {
            # Map to live contract with mode flag for FE adaptation
            "due": 100.0,  # Reference denominator (100%)
            "pctScheduled": ratio_pct,  # Actual percentage
            "scheduled": coll,  # Actual collections
            "contacted": prod,  # Production basis
            "mode": "collections",  # FE patch uses this for labels
            "target": 98,  # FE patch uses this instead of hardcoded 80
            "period": period,
        },
    }


def build_system_health_status_matrix(bundle: dict[str, Any]) -> dict[str, Any]:
    """
    MUST: System Health Status-Matrix for office-manager.
    Maps SoftDent/QB/Claims/HAL into live status-matrix patients contract.
    """
    diag = bundle.get("diagnostics") if isinstance(bundle.get("diagnostics"), dict) else {}
    summary = diag.get("summary") if isinstance(diag.get("summary"), dict) else {}
    meta = bundle.get("import_meta") if isinstance(bundle.get("import_meta"), dict) else {}
    
    # Determine statuses
    def _status_from_freshness(fresh: bool | None, stale: bool | None, error: bool | None) -> str:
        if error:
            return "failed"
        if stale:
            return "pending"
        if fresh:
            return "verified"
        return "unknown"
    
    # SoftDent
    sd_connected = summary.get("softdent") or summary.get("dentrix") or False
    sd_stale = summary.get("stale") if isinstance(summary.get("stale"), list) and "softdent" in summary["stale"] else False
    sd_error = summary.get("errors") if isinstance(summary.get("errors"), list) and any("softdent" in str(e).lower() for e in summary["errors"]) else False
    sd_status = _status_from_freshness(sd_connected, sd_stale, sd_error)
    
    # QuickBooks
    qb_connected = summary.get("quickbooks") or summary.get("qb") or False
    qb_stale = summary.get("stale") if isinstance(summary.get("stale"), list) and "quickbooks" in summary["stale"] else False
    qb_status = _status_from_freshness(qb_connected, qb_stale, False)
    
    # Claims (from reports bundle or meta)
    claims_meta = meta.get("claims") if isinstance(meta.get("claims"), dict) else {}
    claims_last = claims_meta.get("lastRun") or claims_meta.get("lastSuccess")
    claims_stale = claims_meta.get("stale") or (claims_last is None)
    claims_status = "verified" if claims_last and not claims_stale else "pending" if claims_stale else "unknown"
    
    # HAL (self)
    hal_status = "verified"  # If we're running, HAL is up
    
    # Map to patients structure with headers override (FE patch required for headers, or use default)
    patients = [
        {"hash": "SoftDent", "elig": sd_status, "ben": "ok" if sd_connected else None, "breakdown": None},
        {"hash": "QuickBooks", "elig": qb_status, "ben": None, "breakdown": None},
        {"hash": "Claims", "elig": claims_status, "ben": None, "breakdown": None},
        {"hash": "HAL", "elig": hal_status, "ben": None, "breakdown": None},
    ]
    
    # Check if all unknown/empty
    all_empty = all(p["elig"] == "unknown" for p in patients)
    
    return {
        "id": "system-health-matrix",
        "type": "status-matrix",
        "label": "System Health",
        "size": "m",
        "status": "empty" if all_empty else "ok",
        "emptyMessage": "System diagnostics unavailable — refresh imports.",
        "hint": "Import freshness: ●Active ○Stale ◉Error",
        "data": {
            "patients": patients,
            "headers": ["System", "Import", "Sync", "Status"],  # FE patch uses this
            "emptyMessage": "System diagnostics unavailable",
        },
    }
```

### 3.2 apex_backend.py patches (INSERTIONS)

**Insertion A:** Import section (add near other pack imports)
```python
# Moonshot Better Backend Widgets (MUST items)
try:
    from apex_better_backend_widgets_pack import (
        build_collections_radial_gauge,
        build_system_health_status_matrix,
        build_tax_planning_data_table,
    )
except Exception:
    build_tax_planning_data_table = lambda b: None  # type: ignore
    build_collections_radial_gauge = lambda b, r: None  # type: ignore
    build_system_health_status_matrix = lambda b: None  # type: ignore
```

**Insertion B:** In `_taxes_widgets` (after existing widgets, before return)
```python
    # Moonshot MUST: Tax Planning Data-Table
    planning_table = build_tax_planning_data_table(bundle)
    if planning_table:
        widgets.append(planning_table)
```

**Insertion C:** In `_financial_widgets_from_reports` (after vitals, in chart row)
```python
        # Moonshot MUST: Collections Radial-Gauge alongside existing vitals
        coll_gauge = build_collections_radial_gauge(bundle, reports)
        if coll_gauge:
            widgets.append(coll_gauge)
```

**Insertion D:** In `_office_manager_widgets` (after vitals strip, before return)
```python
    # Moonshot MUST: System Health Status-Matrix
    health_matrix = build_system_health_status_matrix(bundle)
    if health_matrix:
        widgets.append(health_matrix)
```

**Insertion E:** In `_ar_widgets` (optional dual-emit alongside bullet)
```python
    # Moonshot MUST: Collections Radial-Gauge on A/R page too
    coll_gauge_ar = build_collections_radial_gauge(bundle, reports)
    if coll_gauge_ar:
        widgets.append(coll_gauge_ar)
```

### 3.3 apex-core.js patches (MINIMAL)

**Patch A:** radial-gauge extension (collections mode support)
Replace the radial-gauge block in `apex-core.js` with this enhanced version:

```javascript
      if (this.type === "radial-gauge") {
        const data = this.spec.data && typeof this.spec.data === "object" ? this.spec.data : {};
        const empty = this.spec.status === "empty" || data.due == null;
        const isCollections = data.mode === "collections" || (data.production != null && data.target === 98);
        const pct = data.pctScheduled != null && Number.isFinite(Number(data.pctScheduled))
          ? Math.max(0, Math.min(100, Number(data.pctScheduled)))
          : null;
        // Support configurable target (default 80 for recall, 98 for collections)
        const target = Number.isFinite(Number(data.target)) ? Number(data.target) : 80;
        const r = 42;
        const c = 2 * Math.PI * r;
        const fill = pct == null ? 0 : (pct / 100) * c * 0.75;
        const track = c * 0.75;
        // Target marker angle calculation (135° start, 270° sweep)
        const targetAngle = 135 + (target / 100) * 270;
        const rad = (targetAngle * Math.PI) / 180;
        const tx = 60 + r * Math.cos(rad);
        const ty = 58 + r * Math.sin(rad);
        
        // Label sets based on mode
        const labelDue = isCollections ? "Target" : "Due";
        const labelSched = isCollections ? "Collected" : "Sch";
        const labelContact = isCollections ? "Production" : "Contacted";
        const metaDue = isCollections ? `${target}%` : (data.due != null ? String(data.due) : "—");
        const metaSched = data.scheduled != null ? String(data.scheduled) : "—";
        const metaContact = data.contacted != null ? String(data.contacted) : "—";
        
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(
                  data.emptyMessage || (isCollections ? "Collections data unavailable" : "Recall tracking unavailable")
                )}</div>
                 <div class="apex-gauge apex-gauge--empty">
                   <svg viewBox="0 0 120 100" class="apex-gauge-svg" aria-hidden="true">
                     <circle class="apex-gauge-arc apex-gauge-arc--track" cx="60" cy="58" r="${r}"
                       stroke-dasharray="${track} ${c}" stroke-dashoffset="0" transform="rotate(135 60 58)" />
                     <text x="60" y="62" text-anchor="middle" class="apex-gauge-pct">—%</text>
                   </svg>
                 </div>`
              : `<div class="apex-gauge">
                   <svg viewBox="0 0 120 100" class="apex-gauge-svg" aria-hidden="true">
                     <circle class="apex-gauge-arc apex-gauge-arc--track" cx="60" cy="58" r="${r}"
                       stroke-dasharray="${track} ${c}" stroke-dashoffset="0" transform="rotate(135 60 58)" />
                     <circle class="apex-gauge-arc apex-gauge-arc--fill" cx="60" cy="58" r="${r}"
                       stroke-dasharray="${fill} ${c}" stroke-dashoffset="0" transform="rotate(135 60 58)" />
                     <circle class="apex-gauge-target" cx="${tx.toFixed(1)}" cy="${ty.toFixed(1)}" r="3.5" />
                     <text x="60" y="62" text-anchor="middle" class="apex-gauge-pct">${this.escape(
                       pct != null ? `${pct}%` : "—%"
                     )}</text>
                   </svg>
                   <div class="apex-gauge-meta">${labelDue}: ${this.escape(metaDue)} · Target: ${target}% · ${labelSched}: ${this.escape(metaSched)}${
                     data.contacted != null ? ` · ${labelContact}: ${this.escape(metaContact)}` : ""
                   }</div>
                 </div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }
```

**Patch B:** status-matrix extension (configurable headers)
In the status-matrix block, replace the hardcoded header line:
```javascript
            <div class="apex-matrix-head"><span></span><span>Elig</span><span>Ben</span><span>Break</span></div>
```
With:
```javascript
            const headers = Array.isArray(data.headers) && data.headers.length >= 4 
              ? data.headers 
              : ["", "Elig", "Ben", "Break"];
            const headHtml = headers.map(h => `<span>${this.escape(h)}</span>`).join("");
            // ... then use headHtml in the template
```
And update the template to use `<div class="apex-matrix-head">${headHtml}</div>`.

## 4. HAL focus_rules (if any)

```json
{
  "focus_rules": [
    {
      "trigger": "better-backend-widgets-apply",
      "context": "apex_backend.py wiring",
      "check": [
        "Import statements resolve without circular deps",
        "build_tax_planning_data_table returns None or valid widget dict",
        "build_collections_radial_gauge handles missing reports gracefully",
        "build_system_health_status_matrix maps all 4 systems"
      ],
      "halt_if": "Widget builder raises unhandled exception (should return empty widget instead)"
    }
  ]
}
```

## 5. Validation Gate

Before apply, verify:

1. **tax_engine availability**: `build_tax_plan_from_bundle` exists and returns dict with `bridgeLines` or `quarterlyEstimates`
2. **FE contract compatibility**: If `apex-core.js` cannot be patched immediately, radial-gauge will render with recall labels but correct percentages (acceptable interim state).
3. **Empty handling**: All three builders return `status: "empty"` with appropriate `emptyMessage` when source data missing.
4. **No dollar invention**: Code uses `_parse_money` and preserves `None` → FE displays "—".

## 6. Apply Order

1. **Create** `apex_better_backend_widgets_pack.py` with Section 3.1 content
2. **Patch** `apex_backend.py`:
   - Add imports (Insertion A)
   - Add to `_taxes_widgets` (Insertion B)
   - Add to `_financial_widgets_from_reports` (Insertion C)
   - Add to `_office_manager_widgets` (Insertion D)
   - Optional: Add to `_ar_widgets` (Insertion E)
3. **Patch** `apex-core.js` with Section 3.3 (radial-gauge mode support, status-matrix headers)
4. **Restart** NR2 backend (Python import refresh)
5. **Hard refresh** browser (new JS)
6. **Verify**:
   - Taxes page shows "Tax Planning Items" table (empty until QB connected)
   - Financial page shows "Collection Efficiency" gauge with 98% target marker
   - Office-Manager shows "System Health" 4-row matrix

## 7. What NOT to redo

- W-01..W-10 builders (already shipped in `apex_missing_widgets_pack.py`)
- KPI density/zero-scroll compliance (already achieved in hal-10562)
- DEF-001 fixes (empty≠$0 already honored)
- Claims pro, command strip, horizontal-bar/donut/waterfall (shipped)
- SHOULD/NICE items from consult (action-list, ai-insight, pareto-chart, patient-dossier, tax-calendar, timeline-lanes) — do not implement yet