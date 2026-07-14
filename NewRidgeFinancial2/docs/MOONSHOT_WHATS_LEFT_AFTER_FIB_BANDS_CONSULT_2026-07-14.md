# Moonshot AI — What's left of the pages after Fibonacci bands (CONSULT ONLY)

**Date:** 2026-07-14
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Build:** hal-10617
**Script:** `scripts/run_moonshot_whats_left_after_fib_bands_consult.py`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> now ask moonshot what to do with what we have left of the pages

---

# Verdict
The main financial surface is zero-scroll complete and staff-ready; the leftovers are sparse OPS subpages with placeholder debris ("unknown-subpage"), thin singles (one-tile bands), and stale data warnings that need consolidation, not expansion.

## 0. Operator Intent (verbatim; consult-only)
> "now ask moonshot what to do with what we have left of the pages"

## 1. Read of current pages (what's left / quality of fill)
**Main Surface (Financial/Taxes/SoftDent/AR/QB/OM):** Dense, Fibonacci-compliant, zero-scroll achieved. All 5-tile layouts with proper 80/240/320 banding. SoftDent money widgets (sd-vitals, collections-gauge, collections-gap, outstanding-claims-bridge, sd-prod-trend) correctly preserved and populated.

**HAL:** Correctly uses the primary 320px band for chat (hal-ask), respecting the conversational height floor.

**Claims:** Anomaly—double micro bands (executive-strip + pipeline-summary) create 160px of vertical micro stack before secondary content, slightly breaking the rhythm.

**AR:** Anomaly—micro band (collection-bullet) inserted between secondary bands disrupts the 240px rhythm.

**Narratives:** Sparse—4 tiles with 1 empty (census confirms), 2 micro tiles (clinical-notes, template-library) that could merge, and OPS contains "unknown-subpage" placeholder.

**Documents:** 4 tiles populated but OPS contains "unknown-subpage" placeholder.

**Library:** Present in census (3/3 filled) but absent from detailed page spec—likely floating or using default layout.

**Data Truth:** Critical staleness—SoftDent AR (192 min), QuickBooks P&L/Revenue (1683 min), Production (1678 min). Widgets render but values are stale.

## 2. Per-page leftovers (keep / fix / demote / OPS)
| Page | Verdict | Action |
|------|---------|--------|
| **Financial** | Keep | Solid 2×2 secondary grid. OPS has 4 tiles—good density. |
| **Taxes** | Keep | Clean waterfall + planning split. OPS has 3 tiles—acceptable. |
| **SoftDent** | Keep | Money-first widgets correct. OPS has 5 tiles but **softdent-scheduling-gap** is a thin single (orphan in own band)—pair it or demote. |
| **Claims** | Fix | **claims-pipeline-summary** (micro) should merge into executive-strip or promote to secondary; eliminate double-micro stack. |
| **AR** | Fix | **collection-bullet** (micro) between secondaries breaks rhythm; demote to strip-level or merge into ar-vitals-strip. |
| **QuickBooks** | Keep | Clean gaps layout. OPS well-formed. |
| **Office-Manager** | Keep | Good huddle/util split. OPS has 5 tiles but **patient-responsibility-calc** is thin single—pair it. |
| **HAL** | Keep | Primary band correctly reserved for chat. OPS is sparse (2 tiles) but acceptable for system page. |
| **Narratives** | Consolidate | Empty slot (1 of 4) should be omitted. Merge clinical-notes + template-library into single micro strip. Move entire page to **Documents OPS** as "Clinical Narratives" tab, or demote to drawer. |
| **Documents** | Fix | Remove **unknown-subpage** placeholder from OPS. If Narratives merged here, use tabbed OPS (Docs / Narratives / Library). |
| **Library** | Merge | Census shows 3 tiles but no banding detail. Merge into Documents OPS as "Library" tab rather than standalone sparse page. |

## 3. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Package:** OPS Debris Cleanup (hal-10618)

**Why now:** The main financial UI is shipped and stable; these are the last uneven edges blocking "staff-ready" declaration. Fixes require only JSON layout edits—no new widgets, no data contracts.

**Effort:** Low (2-3 hours). Pure layout JSON surgery.

**REAL files to touch:**
- `site/config/page-layouts/claims-layout.json` — merge pipeline-summary into executive-strip or promote to secondary 240px tile.
- `site/config/page-layouts/ar-layout.json` — move collection-bullet into ar-vitals-strip (add as 5th pill) or demote to OPS.
- `site/config/page-layouts/softdent-ops-layout.json` — pair softdent-scheduling-gap with another gap widget or remove band.
- `site/config/page-layouts/office-manager-ops-layout.json` — pair patient-responsibility-calc with import-freshness or similar.
- `site/config/page-layouts/documents-layout.json` — replace "unknown-subpage" with actual document-queue-ops or remove.
- `site/config/page-layouts/narratives-layout.json` — collapse to 3 tiles, remove empty slot, prepare for merge.
- `site/config/page-layouts/content-hub-layout.json` (new) — optional merge target for Documents+Narratives+Library with tabbed OPS.

**Validation gate:**
- Zero "unknown-subpage" IDs in any OPS band.
- Zero single-tile secondary bands (width 100% orphans) in OPS.
- Claims and AR show clean Fibonacci stack (micro→secondary→secondary or micro→secondary→primary→secondary).
- Narratives/Documents either merged or Narratives removed from main nav (demoted to drawer).

## 4. Why this beats other candidates now
- **Data Freshness Dashboard:** Critical but backend/ETL issue, not a "pages" layout problem. Stale data doesn't break the zero-scroll contract; placeholder debris does.
- **Mobile Polish CSS Linking:** Technical debt, but files are already unlinked (no user impact yet). Layout integrity comes before responsive polish.
- **ERA Gauge Restoration:** Explicitly excluded per build notes ("chronic empty SoftDent-source widgets omitted"). Adding it back would violate the "omit empties" contract.
- **New Widget Invention:** Would break "do not invent SoftDent dollars" rule and expand scope when contraction is needed.

## 5. Runner-ups (2–3)
1. **Stale Data Alert Strip (hal-10619):** Add a non-scrolling "data freshness" micro-strip to Financial and SoftDent pages showing import age (e.g., "AR 192 min stale"). Why not now: Requires backend timestamp exposure; layout cleanup is pure frontend and unblocks staff faster.
2. **Mobile CSS Re-link (hal-10620):** Re-link apex-theme.css and apex-mobile-polish.css. Why not now: Current desktop financial surface is the priority; mobile can wait until desktop is debris-free.
3. **Unified Content Hub (hal-10621):** Full merge of Narratives/Documents/Library into single "Back Office" page with tabbed main view. Why not now: Slightly higher effort than OPS Cleanup; can be fast-follow if OPS Cleanup proves insufficient.

## 6. SoftDent / import honesty still open
- **softdent.ar:** Critical staleness (192 min > 120 min threshold). Widget renders but value is stale.
- **softdent.production:** Warning staleness (1678 min).
- **softdent.claims:** Warning staleness (1463 min).
- **quickbooks.profitAndLoss / revenue:** Critical staleness (1683 min).

**Action:** These require OPS backend pulls (import_loader refresh), not frontend widget changes. Do not fake these values with placeholders or "last known" caches.

## 7. What NOT to redo
- **Fibonacci band rewrite:** The 80/240/320 system works; don't change the math.
- **Invent widgets to fill empties:** Do not create "narratives-placeholder" or "library-placeholder" widgets to pad the 4th slot.
- **Restore deleted theme files:** apex-theme.css remains unlinked per hal-10617; don't revert.
- **Add vertical scroll:** Zero-scroll is the constraint. Don't "fix" sparse pages by allowing them to scroll—demote them instead.
- **Expand Narratives/Documents content:** Don't add fake clinical notes or document templates to fill space.

## 8. Acceptance criteria
- [ ] No page has more than one micro (80px) band except HAL (which uses primary).
- [ ] No OPS band contains only a single tile (thin singles eliminated).
- [ ] "unknown-subpage" ID does not exist in any layout JSON.
- [ ] Narratives empty slot removed (4 tiles → 3 tiles).
- [ ] SoftDent OPS scheduling gap is paired or removed.
- [ ] Claims pipeline-summary no longer occupies standalone micro band.
- [ ] AR collection-bullet merged into vitals strip or demoted to OPS.
- [ ] All changes validate against `designSchemaVersion: hal-10617` (no schema changes).

## 9. Executive Summary (5 bullets)
- **Main financial surface is done:** Zero-scroll achieved, Fibonacci bands stable, SoftDent money widgets preserved.
- **Leftovers are OPS debris:** Placeholder IDs ("unknown-subpage"), thin singles (one-tile bands), and double-micro anomalies in Claims/AR.
- **Narratives/Documents are too sparse:** 3-4 tiles vs 5 on financial pages; recommend merge into Content Hub or demote to drawer.
- **Data is stale, not empty:** Critical AR/QB staleness requires backend refresh, not frontend widgets.
- **Next step is cleanup, not expansion:** JSON-only layout consolidation (hal-10618) unblocks staff without inventing data or breaking scroll contract.

## 10. Approval checklist
- [ ] Operator confirms "unknown-subpage" placeholders can be deleted (not replaced).
- [ ] Operator confirms thin singles (softdent-scheduling-gap, patient-responsibility-calc) can be paired or demoted.
- [ ] Operator accepts Narratives/Documents may merge into single Content page or lose main-nav prominence.
- [ ] Operator acknowledges stale data (SoftDent AR/QB) is a separate backend ticket, not part of this layout cleanup.
- [ ] Desktop SoftDent Excel/Print Preview remains period-close truth (no widget claims primacy over source).
