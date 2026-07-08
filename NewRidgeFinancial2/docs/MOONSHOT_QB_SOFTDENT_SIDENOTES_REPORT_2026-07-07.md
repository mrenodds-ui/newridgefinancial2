# Moonshot Re-Review — QuickBooks, SoftDent, SideNotes

**Date:** 2026-07-07  
**Build reviewed:** `hal-10059`  
**Model:** kimi-k2.5 (Moonshot API)  
**Full response:** `.local_logs/moonshot_financial_eval/MOONSHOT_QB_SOFTDENT_SIDENOTES_2026-07-07.md`

---

## Verdict

| Area | Moonshot |
|------|----------|
| QuickBooks | **CONDITIONAL APPROVE** |
| SoftDent | **CONDITIONAL APPROVE** |
| SideNotes / Hub | **CONDITIONAL APPROVE** |
| **Overall** | **CONDITIONAL APPROVE** — not ready for daily operator use until blockers below are closed |

Moonshot agrees the team implemented the reordered plan (0→1→2→4→5) and validators pass. It does **not** approve production rollout yet.

---

## QuickBooks

**What Moonshot likes**
- `dashboard-grid`, KPI cards, P&L trend, expense chart, reconciliation table match mockup intent
- Sync badge in header; widget keys split correctly
- Chart overlay bridge with double-mount guard in code

**What Moonshot wants before ship**
1. Manual F5 spike — confirm no duplicate `.nr2-chart-overlay` on reload
2. Confirm `ebitdaNormalization` tile placement vs mockup grid
3. Explicit empty-state copy when QuickBooks cache is cold (“Awaiting QuickBooks sync”)

---

## SoftDent

**What Moonshot likes**
- 4-stage funnel (Presented → Accepted → Scheduled → Completed) matches mockup structure
- Operatory grid widget + empty-state hook exists

**What Moonshot wants before ship**
1. **Canonical data contract** — replace `operatoryChairs || chairSchedule || scheduleChairs` fallback with one required field
2. **Dedicated export file** — don’t rely only on dashboard bundle fields
3. **Empty state UX** — visible “No operatory schedule available” copy, not a blank canvas
4. Side-by-side pixel check vs `softdent.html`

---

## SideNotes / Hub (8766 → 8765)

**What Moonshot likes**
- Protocol doc exists (`MOONSHOT_PHASE5_HUB_PROTOCOL.md`)
- Metadata-only badge on 8765 (no message text) — compliance OK
- Auto-record on office-wide posts

**What Moonshot wants before ship**
1. **Origin lock** on `/api/hub/notify` (8766-only or configurable `NR2_HUB_ORIGIN`)
2. **Shared secret / hub token** header on hub routes (CSRF/spoofing on localhost)
3. **Manual test** — Everyone send on 8766 → OFFICE BROADCAST on 8765 within poll interval (not yet recorded)

Note: `_lan_hal_hub_access_ok()` already gates hub routes in `nr2_http_server.py` — Moonshot’s context did not mention this; worth clarifying in protocol doc on next pass.

---

## Blockers (Moonshot — fix before daily use)

1. SoftDent operatory data contract + dedicated export
2. Hub security hardening (origin + token) + manual broadcast test
3. Operator sign-off checklist (mockup parity, chart reload, hub latency)

---

## Operator checklist (from Moonshot)

1. Side-by-side QB: gallery vs live (`8799/quickbooks.html` vs `8765/?v=hal-10059`)
2. Toggle `NR2_FLAGS.hal_commands` off/on — chips disappear/reappear
3. SoftDent funnel math (Accepted ≤ Presented, etc.)
4. Operatory empty state when all chair fields missing
5. 8766 Everyone → 8765 badge within ~15s, no message text
6. QB page F5×5 — no duplicate chart overlays in DevTools
7. Reconciliation table responsive at 768px
8. Test which fallback field (`chairSchedule` vs `scheduleChairs`) actually drives grid

---

## Bottom line

Moonshot says **implementation direction is correct** and **CONDITIONAL APPROVE** on all three areas — but **do not ship hal-10059 to daily operator use** until SoftDent contract, hub security, and manual mockup sign-off are done.

Want me to implement Moonshot’s blockers (operatory contract, hub token, empty states) next?
