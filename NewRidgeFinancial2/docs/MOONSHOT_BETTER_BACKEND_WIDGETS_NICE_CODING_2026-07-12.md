# Moonshot AI — Better Backend Widgets NICE CODING

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build base:** hal-10569  
**Script:** `scripts/run_moonshot_better_backend_widgets_nice_coding.py`  
**Operator:** continue  

## Operator request

> cpntinue

---

# Verdict
**NICE Wave — Apply-Ready Coding**  
Deliver three backend widget builders matching the live FE contracts for `pareto-chart`, `tax-calendar`, and `timeline-lanes`. BUILD_ID increments to **hal-10570**.

## 0. Operator Intent
> "cpntinue" — Operator continues from hal-10569 (TXN ledger surface) and requests **NICE items ONLY** from `MOONSHOT_BETTER_BACKEND_WIDGETS_CONSULT` rendered as paste-ready Python that honors the published FE JSON contracts (no new JS, no dollar invention, empty ≠ $0).

## 1. Gap vs Already-Shipped
| NICE Item Requested | Already Exists (Do Not Duplicate) | Distinction |
|---------------------|-----------------------------------|-------------|
| **Aging Pareto Chart** (ar + financial) | `build_denial_pareto` in `apex_missing_widgets_pack.py` (denial **codes**) | This emits **A/R aging buckets** (Current, 1-30, 31-60, 61-90, 91-120, 120+) sorted 80/20 by dollar amount. |
| **Tax Calendar** (taxes MAIN) | `build_tax_calendar` in `apex_subpages_wave5_pack.py` (renders on `#taxes/calendar` subpage) | This emits the same widget type but wired for the **taxes main/index** page. |
| **Claim Timeline Lanes** (claims + documents) | `build_preauth_lanes` in `apex_missing_widgets_pack.py` (preauth **aging** buckets 0-30/31-60…) | This emits **claim status workflow** lanes (Submitted → Acknowledged → Pending → Paid/Denied). |

## 2. Files to Touch
1. `apex_better_backend_widgets_pack.py` — append three new builders.  
2. `apex_backend.py` — wire widgets into page pipelines; bump `BUILD_ID` → `hal-10570`.

## 3. Paste-ready Code

### A. `apex_better_backend_widgets_pack.py` — Append at end of file
```python
from collections import defaultdict
from typing import Any


def _parse_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip().replace(",", "")
    try:
        return int(text)
    except ValueError:
        return None


def build_ar_aging_pareto(bundle: dict[str, Any]) -> dict[str, Any]:
    """
    Aging Pareto Chart (pareto-chart) — NICE item.
    FE contract: data.bars[{code,amount,count,pct}], data.cumulative[], data.threshold
    """
    ar = bundle.get("ar") if isinstance(bundle.get("ar"), dict) else {}
    buckets = ar.get("aging_buckets") if isinstance(ar.get("aging_buckets"), list) else []

    # Fallback: aggregate from open invoice rows
    if not buckets:
        rows = ar.get("open_invoices") or ar.get("invoices") or []
        if not rows and isinstance(bundle.get("financial"), dict):
            rows = bundle["financial"].get("ar_detail") or []
        
        tally: dict[str, dict[str, Any]] = defaultdict(lambda: {"amount": 0.0, "count": 0})
        for row in rows:
            if not isinstance(row, dict):
                continue
            age = _parse_int(row.get("age_days") or row.get("Days") or row.get("Age")) or 0
            amt = _parse_money(row.get("amount") or row.get("Balance") or row.get("Due"))
            if amt is None:
                continue
            if age <= 0:
                bucket = "Current"
            elif age <= 30:
                bucket = "1-30"
            elif age <= 60:
                bucket = "31-60"
            elif age <= 90:
                bucket = "61-90"
            elif age <= 120:
                bucket = "91-120"
            else:
                bucket = "120+"
            tally[bucket]["amount"] += amt
            tally[bucket]["count"] += 1
        
        buckets = [{"bucket": k, "amount": v["amount"], "count": v["count"]} for k, v in tally.items()]

    # Sort by amount descending for 80/20
    buckets.sort(key=lambda x: _parse_money(x.get("amount")) or 0.0, reverse=True)
    
    total_amt = sum((_parse_money(b.get("amount")) or 0.0) for b in buckets)
    total_cnt = sum((b.get("count") or 0) for b in buckets)
    
    bars: list[dict[str, Any]] = []
    cumulative: list[float] = []
    running_pct = 0.0
    
    for b in buckets:
        amt = _parse_money(b.get("amount")) or 0.0
        cnt = b.get("count") or 0
        pct = round((amt / total_amt * 100), 1) if total_amt else 0.0
        running_pct += pct
        bars.append({
            "code": str(b.get("bucket") or b.get("code") or "—"),
            "amount": amt if amt != 0 else None,  # empty ≠ $0
            "count": cnt,
            "pct": pct
        })
        cumulative.append(round(running_pct, 1))
    
    status = "empty" if not bars else "ok"
    
    return _wrap(
        widget_id="ar-aging-pareto",
        type_="pareto-chart",
        label="A/R Aging Pareto",
        data={
            "bars": bars,
            "cumulative": cumulative,
            "threshold": 80
        },
        status=status,
        emptyMessage="No A/R aging data",
        hint="80/20 view of receivables by aging bucket"
    )


def build_tax_calendar_main(bundle: dict[str, Any]) -> dict[str, Any]:
    """
    Tax Calendar (tax-calendar) for Taxes MAIN page — NICE item.
    FE contract: items[{label,amount,due,logged}] on spec root (not inside data).
    """
    try:
        from tax_engine import build_tax_plan_from_bundle
        plan = build_tax_plan_from_bundle(bundle) or {}
        quarterly = plan.get("quarterlyEstimates") if isinstance(plan.get("quarterlyEstimates"), list) else []
    except Exception:
        quarterly = []
    
    # Fallback to raw bundle tax section
    if not quarterly:
        tax = bundle.get("taxes") or bundle.get("tax") or {}
        quarterly = tax.get("deadlines") or tax.get("quarterly") or []
    
    try:
        from nr2_local_db import list_tax_payments
        logged = {str(p.get("quarter") or ""): p for p in list_tax_payments()}
    except Exception:
        logged = {}
    
    items: list[dict[str, Any]] = []
    for q in quarterly[:8]:
        if not isinstance(q, dict):
            continue
        lab = str(q.get("label") or q.get("quarter") or q.get("Period") or "").strip()
        amt = _parse_money(q.get("amount") or q.get("estimate"))
        due = str(q.get("due") or q.get("dueDate") or "")[:40]
        items.append({
            "label": lab,
            "amount": amt,
            "due": due,
            "logged": bool(logged.get(lab))
        })
    
    status = "empty" if not items else "ok"
    
    # Return direct structure (items at root per FE contract)
    return {
        "id": "tax-calendar-main",
        "type": "tax-calendar",
        "label": "Quarterly Tax Calendar",
        "status": status,
        "items": items,
        "emptyMessage": "No upcoming tax deadlines",
        "hint": "Quarterly filing deadlines from tax_engine"
    }


def build_claim_status_lanes(bundle: dict[str, Any]) -> dict[str, Any]:
    """
    Claim Timeline Lanes (timeline-lanes) — NICE item.
    FE contract: data.lanes[{code,total,segments[{bucket,count,color}]}]
    Swimlanes show claim counts by payer across status workflow.
    """
    claims_data = bundle.get("claims") if isinstance(bundle.get("claims"), dict) else {}
    claims = claims_data.get("claims") or claims_data.get("rows") or []
    
    if not claims:
        sd = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
        claims = sd.get("claims") or sd.get("claimStatus") or []
    
    # Lane = payer (or code), Segments = status buckets
    lanes_data: dict[str, dict[str, int]] = defaultdict(lambda: {
        "Submitted": 0, "Acknowledged": 0, "Pending": 0, "Paid": 0, "Denied": 0
    })
    
    for c in claims:
        if not isinstance(c, dict):
            continue
        payer = str(c.get("payer") or c.get("Payer") or c.get("insurance") or "Unknown")[:12]
        status = str(c.get("status") or c.get("Status") or "").lower()
        
        if "paid" in status:
            bucket = "Paid"
        elif "den" in status or "rej" in status:
            bucket = "Denied"
        elif "ack" in status or "received" in status:
            bucket = "Acknowledged"
        elif "pend" in status or "waiting" in status or "hold" in status:
            bucket = "Pending"
        else:
            bucket = "Submitted"
        
        lanes_data[payer][bucket] += 1
    
    color_map = {
        "Submitted": "cyan",
        "Acknowledged": "blue",
        "Pending": "amber",
        "Paid": "green",
        "Denied": "magenta"
    }
    
    lanes: list[dict[str, Any]] = []
    for code, segs in sorted(lanes_data.items()):
        total = sum(segs.values())
        if total == 0:
            continue
        segments = [
            {"bucket": k, "count": v, "color": color_map[k]}
            for k, v in segs.items() if v > 0
        ]
        lanes.append({
            "code": code,
            "total": total,
            "segments": segments
        })
    
    status = "empty" if not lanes else "ok"
    
    return _wrap(
        widget_id="claim-status-lanes",
        type_="timeline-lanes",
        label="Claim Status Timeline",
        data={"lanes": lanes},
        status=status,
        emptyMessage="No claim status data",
        hint="Claims by payer across status workflow"
    )
```

### B. `apex_backend.py` — Wiring snippet (insert into page builders)
```python
from apex_better_backend_widgets_pack import (
    build_ar_aging_pareto,
    build_tax_calendar_main,
    build_claim_status_lanes,
    # ... existing imports
)

BUILD_ID = "hal-10570"  # Bump from hal-10569

def build_tax_widgets(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Taxes MAIN page widgets."""
    widgets: list[dict[str, Any]] = []
    # NICE: Tax Calendar on main (distinct from #taxes/calendar subpage)
    widgets.append(build_tax_calendar_main(bundle))
    # ... existing tax widgets (KPIs, etc.)
    return widgets

def build_ar_widgets(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """A/R page widgets."""
    widgets: list[dict[str, Any]] = []
    # NICE: Aging Pareto
    widgets.append(build_ar_aging_pareto(bundle))
    # ... existing A/R widgets
    return widgets

def build_financial_widgets(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Financial page widgets."""
    widgets: list[dict[str, Any]] = []
    # NICE: Aging Pareto also on financial
    widgets.append(build_ar_aging_pareto(bundle))
    # ... existing financial widgets
    return widgets

def build_claims_widgets(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Claims page widgets."""
    widgets: list[dict[str, Any]] = []
    # NICE: Claim Status Lanes
    widgets.append(build_claim_status_lanes(bundle))
    # ... existing claims widgets
    return widgets

def build_documents_widgets(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Documents page widgets."""
    widgets: list[dict[str, Any]] = []
    # NICE: Claim Status Lanes also on documents workflow view
    widgets.append(build_claim_status_lanes(bundle))
    # ... existing documents widgets
    return widgets
```

## 4. Validation Gate
```python
# test_nice_wave_hal10570.py
import unittest
from apex_better_backend_widgets_pack import (
    build_ar_aging_pareto,
    build_tax_calendar_main,
    build_claim_status_lanes,
)

class TestNiceWaveHal10570(unittest.TestCase):
    def test_aging_pareto_empty(self):
        bundle = {"ar": {}}
        w = build_ar_aging_pareto(bundle)
        self.assertEqual(w["type"], "pareto-chart")
        self.assertEqual(w["status"], "empty")
        self.assertEqual(w["data"]["bars"], [])
        self.assertEqual(w["data"]["threshold"], 80)

    def test_aging_pareto_cumulative_100(self):
        bundle = {
            "ar": {
                "aging_buckets": [
                    {"bucket": "120+", "amount": 8000, "count": 2},
                    {"bucket": "Current", "amount": 2000, "count": 5},
                ]
            }
        }
        w = build_ar_aging_pareto(bundle)
        self.assertEqual(w["status"], "ok")
        bars = w["data"]["bars"]
        self.assertEqual(bars[0]["code"], "120+")  # Sorted desc
        self.assertEqual(bars[0]["pct"], 80.0)
        self.assertEqual(w["data"]["cumulative"][-1], 100.0)

    def test_tax_calendar_main_root_items(self):
        bundle = {"taxes": {"deadlines": [{"label": "Q3", "amount": 1500, "due": "2026-09-15"}]}}
        w = build_tax_calendar_main(bundle)
        self.assertEqual(w["type"], "tax-calendar")
        self.assertIn("items", w)  # Must be on root, not data.items
        self.assertEqual(w["items"][0]["label"], "Q3")
        self.assertEqual(w["items"][0]["logged"], False)  # Never invent logged state

    def test_claim_lanes_segments(self):
        bundle = {
            "claims": {
                "claims": [
                    {"payer": "Delta", "status": "Paid"},
                    {"payer": "Delta", "status": "Pending"},
                    {"payer": "Aetna", "status": "Denied"},
                ]
            }
        }
        w = build_claim_status_lanes(bundle)
        self.assertEqual(w["type"], "timeline-lanes")
        lanes = w["data"]["lanes"]
        delta = next(l for l in lanes if l["code"] == "Delta")
        self.assertEqual(delta["total"], 2)
        segs = {s["bucket"]: s for s in delta["segments"]}
        self.assertEqual(segs["Paid"]["color"], "green")
        self.assertEqual(segs["Pending"]["color"], "amber")

if __name__ == "__main__":
    unittest.main()
```
Run:  
```bash
cd NewRidgeFinancial2
python -m unittest test_nice_wave_hal10570 -v
```

## 5. Apply Order
1. **Append** the three builders to `apex_better_backend_widgets_pack.py`.  
2. **Wire** the widgets into `apex_backend.py` page builders (ar, financial, taxes, claims, documents) and update `BUILD_ID = "hal-10570"`.  
3. **Run** `test_nice_wave_hal10570` — all green.  
4. **Verify** in browser:
   - Taxes main page shows quarterly cards (cyan/amber logged badges).  
   - A/R page shows Pareto bars with cumulative % line crossing 80% threshold.  
   - Claims page shows payer swimlanes with color-coded status segments.

## 6. What NOT to redo
- **MUST/SHOULD/TXN ledger** — Already shipped in hal-10569 (`build_transaction_ledger_table`, SoftDent API surface).  
- **Denial Pareto** — Exists in `apex_missing_widgets_pack.py` (`build_denial_pareto` for denial **codes**).  
- **Preauth Aging Lanes** — Exists in `apex_missing_widgets_pack.py` (`build_preauth_lanes` for preauth **aging buckets**).  
- **Tax Calendar Subpage** — Exists in `apex_subpages_wave5_pack.py` (`build_tax_calendar` for `#taxes/calendar`).