# Moonshot AI — HAL Collections Empty Inventory (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Script:** `scripts/run_moonshot_hal_collections_empty_consult.py`  
**Apply:** DO NOT APPLY / WAIT FOR OPERATOR APPROVAL.

## Operator request (verbatim)

> ask moonshot ai why hal says this and how to fix and code - age `hal` inventory: 8 with data, 1 empty (of 9). Showing: Ask HAL, Import Health, Program Posture, HAL Suggestion, Production, A/R, Claims, Local Categorize Assist Empty: Collections (Collections pending/missing.)
07:16 AM
Copy

---

# Verdict — Why HAL said this (one paragraph)

HAL emitted the inventory summary because the operator triggered a widget census query on the `hal` page. The Collections widget (`hal-mosaic-coll`) appears empty with the hint *"Collections pending/missing."* because the latest SoftDent period has `collectionsPending=true` (no daysheet/collections imported yet), causing the KPI value to be `None` rather than `$0` (intentional honesty to avoid false zeros). Additionally, the "Ask HAL" widget appears in the populated list erroneously due to a census skip-logic bug checking widget ID prefix `"hal-chat"` instead of widget type `"hal-chat"`, allowing ID `"hal-ask"` (type `"hal-chat"`) to be counted as data-bearing.

## 0. Operator Intent
Understand why the HAL page reports Collections as empty/missing, determine whether this is a data error or expected behavior, and receive both immediate operational steps (no code deploy) and optional code improvements to make the "pending" state actionable rather than ambiguous.

## 1. Causal Chain (query → board-actions → census → Collections empty)
1. **Query matches census intent** — The operator’s utterance matches `wants_inventory` or `wants_census` regex in the board-actions branch.
2. **`build_page_widget_census("hal")` executes** — Returns a census object with `populatedWidgets` and `emptyWidgets` lists.
3. **Collections evaluation** — `_hal_widgets` appends the Collections KPI using value `coll` derived from the latest SoftDent period. Because `_build_period_row` sets `collectionsPending=True` (no collections imported for current period), `coll` is `None`.
4. **Ask HAL miscount** — The census builder skips widgets where `wid.startswith("hal-chat")`, but the Ask HAL widget has ID `"hal-ask"` (type `"hal-chat"`), so it is not skipped and appears in `populatedWidgets`.
5. **`format_page_inventory_reply` renders** — Concatenates the counts and hints, producing: *"Page `hal` inventory: 8 with data, 1 empty (of 9)… Empty: Collections (Collections pending/missing.)"*.

## 2. Root Cause in SoftDent period merge (collectionsPending rules)
In `_build_period_row`, when `production > 0` and `collections_reported` is False, the code distinguishes between:
- **Explicit failure** (daysheet exists but collections missing) → sets `collectionsReported=False` and `collections=0.0` for past periods.
- **Pending state** (no daysheet, current month) → sets `collectionsPending=True` and **removes** the `collections` key entirely to avoid implying zero collections.

This `None`/`missing` state propagates to `_hal_widgets`, which correctly refuses to invent a dollar amount, resulting in the empty census slot.

## 3. Operational Fix (staff steps — no invented $)
Do not manually enter `$0` or any placeholder. The widget is intentionally empty to prevent misleading data.
1. **Import SoftDent Daysheet** — In NewRidge Import Health, pull the latest SoftDent daysheet for the current period (or use "Register for a Period" in SoftDent to close the prior period and open the current).
2. **Sync/Refresh** — Trigger a SoftDent period refresh in NewRidge (Settings → Sync SoftDent Periods or equivalent).
3. **Verify** — Once `collectionsReported=true` appears in the period row, the HAL Collections widget will populate automatically with the actual imported value.

## 4. Code Fix Options (ranked) + Recommended path

| Rank | Fix | Impact | Risk |
|------|-----|--------|------|
| **1** | **Fix census skip logic** — Exclude by `type == "hal-chat"` instead of ID prefix | Corrects "Ask HAL" appearing as data-bearing; accurate inventory counts | Low — type field already available |
| **2** | **Actionable board-actions** — When `hal-mosaic-coll` is empty with "pending" hint, append `show_action_button` pointing to Import Health | Transforms passive "missing" message into clickable fix path | Low — UI only |
| **3** | **Prior-period fallback** — When current period pending, display prior period collections with label "(Last reported)" | Provides context without inventing current data | Medium — requires period history lookup |
| **4** | **Visual "Pending" badge** — Render `"Pending"` text in widget instead of blank/null | Clearer UX but changes KPI contract from numeric\|None to string | Medium — may break numeric aggregations |

**Recommended:** Implement **#1** (bug fix) + **#2** (actionable guidance) immediately. Defer #3/#4 pending UX review.

## 5. Paste-Ready Code (CONSULT ONLY)

### Delta A: Fix hal-chat skip logic (summarize_widget_census or equivalent)
```python
# CONSULT ONLY — Locate summarize_widget_census or build_page_widget_census
# BEFORE:
# if wid.startswith("hal-chat"):
#     continue

# AFTER:
if wid.startswith("hal-chat") or widget.get("type") == "hal-chat":
    continue
```

### Delta B: Actionable board-action for pending collections
Insert in `board-actions` census branch after the `highlight_widget` block:

```python
# CONSULT ONLY — Add after highlight_widget actions in board-actions census branch
if empty_ids:
    actions.append({"type": "focus_widget", "widgetId": str(empty_ids[0])})
    actions.append({"type": "highlight_widget", "widgetId": str(empty_ids[0]), "ms": 4000})
    
    # NEW: Detect Collections pending and offer import path
    collections_pending = any(
        e.get("id") == "hal-mosaic-coll" and 
        "pending" in str(e.get("hint", "")).lower()
        for e in empties
    )
    if collections_pending:
        actions.append({
            "type": "set_status_banner",
            "message": "Collections pending: Import SoftDent daysheet or complete Register for a Period.",
            "hint": "Operational fix required — no collections imported for current SoftDent period.",
            "tone": "warn",
        })
        actions.append({
            "type": "show_action_button",
            "label": "Go to Import Health",
            "action": "navigate",
            "target": "import-health",
        })
```

### Delta C: Prior-period fallback in _hal_widgets (optional)
Modify the Collections KPI construction to fall back to prior period when current is pending:

```python
# CONSULT ONLY — In _hal_widgets where Collections KPI is built
# BEFORE:
# coll = latest_period.get("collections") if not latest_period.get("collectionsPending") else None

# AFTER (fallback strategy):
current_pending = latest_period.get("collectionsPending")
coll = latest_period.get("collections")
hint_text = "SoftDent dashboard."
if current_pending or coll is None:
    # Try prior period
    prior = get_prior_softdent_period(latest_period.get("period"))  # implement this helper
    if prior and prior.get("collections") is not None:
        coll = prior.get("collections")
        hint_text = f"Last reported {prior.get('period')} (current period pending)."
    else:
        coll = None
        hint_text = "Collections pending/missing."
        
widgets.append(
    _money_kpi(
        "hal-mosaic-coll",
        "Collections",
        coll,
        hint=hint_text,
    )
)
```

## 6. Files to Touch + Validation Gates

| File/Module | Change | Validation Gate |
|-------------|--------|-----------------|
| `summarize_widget_census` (or `build_page_widget_census`) | Delta A: Skip `type == "hal-chat"` | Ask HAL no longer appears in populated widgets count; inventory shows 7 with data, 2 empty (Ask HAL + Collections) or 7/1 if Collections fixed |
| `board_actions.py` (census branch) | Delta B: Add pending collections action | When Collections empty, banner appears with "Go to Import Health" button; clicking navigates to import-health page |
| `hal_page.py` or `_hal_widgets` | Delta C (optional): Prior-period fallback | When current period pending, widget shows last period value with "(Last reported)" hint; verify no `$0` displayed when truly pending |
| SoftDent import pipeline | N/A — operational | After daysheet import, verify `collectionsPending` becomes false and widget populates |

## 7. Approval Checklist

**STOP — Do not apply until operator confirms:**

- [ ] **Confirm operational state**: Staff will attempt SoftDent daysheet import first (operational fix) before any code deploy?
- [ ] **Bug fix approval**: Approve Delta A (fix hal-chat skip logic) to correct the "Ask HAL" miscount?
- [ ] **Actionable UX approval**: Approve Delta B (actionable board-actions) to show "Go to Import Health" button when Collections pending?
- [ ] **Fallback strategy**: Approve Delta C (prior-period fallback) or prefer to keep widget empty/honest when pending?
- [ ] **Testing window**: Confirm staging environment available to validate census counts after changes?
- [ ] **Rollback plan**: Revert to current behavior if widget counts become inaccurate?

**Reply "approve / proceed" with selected deltas to apply, or request modifications.**