# NR2 Compact Professional Pages — Detailed Implementation Plan

**Date:** 2026-07-11  
**Base build:** `hal-10502`  
**Source consult:** `MOONSHOT_COMPACT_PROFESSIONAL_PAGES_CONSULT_2026-07-11.md`  
**Status:** CONDITIONAL APPROVE by Moonshot (see `MOONSHOT_COMPACT_PAGES_PLAN_VALIDATION_2026-07-11.md`) — amendments below incorporated; DO NOT APPLY until operator approve  
**Goal:** All Apex pages compact, stable (no wobble), professional first-viewport command surfaces with little/no scroll for primary work.

---

## 1. Problem statement (engineering)

| Symptom | Evidence | Impact |
|---------|----------|--------|
| Huge widgets | Many packs emit `size: l/xl/full`; CSS `min-height` 100–180px+; mosaic cols ~300px | First viewport dominated by monuments; operators scroll to find KPIs |
| Unorganized hierarchy | Ad-hoc page builders; Financial has strip console, others do not | Inconsistent “cockpit” vs warehouse dump |
| Empty monuments | `collapse_empty_large()` only applied selectively (Financial + a few packs) | Empty imports look like broken system |
| Wobble | `apexBreathe` on `.is-updating`; hover `translateY(-2px)` / chrome scale; `apexEnter` stagger; sweep/glitch | Large surfaces feel unstable / unprofessional |

**Non-goals:** Resurrect legacy mockups; invent dollars; remove honesty empty states; redesign brand chrome from scratch.

---

## 2. Design contracts (must hold after each phase)

### 2.1 First-viewport contract (1920×1080, chrome+ticker ≈100px)

| Zone | Max height | Allowed sizes | Content |
|------|------------|---------------|---------|
| Strip 1 — status | 60–80px | `strip` / `xs` / `full` as strip only | Import health + period/sync chips |
| Strip 2 — KPIs | 60–80px | `xs`/`s` chips (3–4) | Primary numbers only |
| Primary instrument | ≤200px | max one `m` or `l` | One chart OR compact table |
| Action row | ≤40px | buttons/links | Sync / open subpage / HAL action |
| **Total above fold** | **≤ ~380px** | **No `xl` above fold** | Secondary detail below fold or subpage |

#### 2.1.1 Functional exemptions (Moonshot R1/R2 — required)

- **HAL chat:** May occupy `l` (200px) as the **sole** large instrument on the HAL page (history scrolls inside), **or** use a chat-first split: summary strips above fold + chat ~400–500px below. Operator must pick one before Phase 3.
- **Claims kanban:** Must **not** be a clipped 200px card stack. Either (a) horizontal-scroll container at `l` height, or (b) pipeline summary strip (`s`: New/Review/Approved/Denied counts) + “Open Kanban” → full kanban subpage (Phase 4). Operator must pick one before Phase 3.
- **Financial dual-axis:** Prefer `m` (140px); Phase 3 gate must verify axis labels readable. If not, grant single `l` (200px) exception and keep EBITDA waterfall below fold.

#### 2.1.2 Responsive breakpoints (Moonshot R5)

| Viewport width | Rule |
|----------------|------|
| ≥1280px | Full contract (desktop bridge) |
| <1280px | `xl` forbidden; max one `l` |
| <768px | Instruments default to `s` or `strip`; grid gap → 4px |

### 2.2 Size taxonomy (enforce)

| Size | Target height | First viewport |
|------|---------------|----------------|
| xs / strip | ~60px | unlimited in strips |
| s | ~100px | max 4 |
| m | ~140px | max 2 |
| l | ~200px | max 1, prefer below fold |
| xl | ~280px | **forbidden above fold** |
| full (tall shelf) | → rewrite as strip | tall `full` forbidden above fold |

### 2.3 Empty-state honesty

- Empty `l`/`xl`/`full`/`large` **must** pass `collapse_empty_large()` → `size: strip`, `compact: true`.
- Chip copy names the **specific missing import** (not generic “No data”).
- Empty ≠ $0. Never fabricate KPI values to fill space.

### 2.4 Motion budget

| Motion | Policy |
|--------|--------|
| `apexBreathe` | Loading skeletons only (≤3s); never infinite on static/populated widgets |
| Hover lift | Border-color only **or** `translateY(-1px)` max; no scale |
| `apexEnter` | `translateY(4px)`, ≤3 staggered items, ≤200ms total; honor `prefers-reduced-motion` |
| `apexSweep` / ambient | Off by default; opt-in class only |
| `apexGlitch` | Error/alert only; not on every page title/nav |
| `halPulse` | HAL orb only |

---

## 3. Inventory — files & extension points

### 3.1 CSS / chrome (Phase 1 + 3)

| File | Role |
|------|------|
| `NewRidgeFinancial2/site/apex-tokens.css` | `--apex-grid-gap`, `--apex-widget-min`, `.apex-widget` enter/hover/breathe, instrument size classes |
| `NewRidgeFinancial2/site/apex-chrome-flash.css` | Hover lift/scale, sweep, glitch, alert pulse |
| `NewRidgeFinancial2/site/apex-bridge.css` | Mosaic column min (~300px legacy), page chrome |
| `NewRidgeFinancial2/site/apex-core.js` | Stagger `animStagger`, `is-updating` class that triggers breathe |

### 3.2 Empty collapse (Phase 2)

| File | Role |
|------|------|
| `apex_financial_console_pack.py` | Canonical `collapse_empty_large()` |
| `apex_backend.py` | `_PAGE_BUILDERS` for all pages; wire collapse on every builder exit |
| Page packs that emit large empty widgets | `apex_program_improve_pack.py`, `apex_sync_status_pack.py`, `apex_subpages_*`, `apex_softdent_production_pack.py`, `apex_unified_db_pack.py`, `apex_bar_trend_page_org_pack.py`, etc. |

### 3.3 Size discipline (Phase 3)

- Audit all `"size": "l|xl|full"` in Apex packs (grep inventory).
- Downsize first-viewport instruments; convert tall shelves to strips.
- Shared helper (new or extend): `normalize_first_viewport(widgets)` that caps sizes / reorders strips.

### 3.4 Subpages (Phase 4)

- Existing subpage expand pattern (`apex_subpages_*`, nav targets).
- Move tables >5 rows / editors / COA / register detail / operatory detail off main pages.

### 3.5 Polish (Phase 5)

- Density toggle (`localStorage`); keyboard strip nav; finalize reduced-motion.

---

## 4. Phased work plan (detailed)

### Phase 1 — Motion kill (build target `hal-10510`) — Effort XS

**Objective:** Stop wobble immediately with CSS (+ minimal JS) only.

**Tasks:**
1. `apex-tokens.css`
   - Remove infinite `apexBreathe` from `.apex-widget.is-updating` (or limit to skeleton class with finite iterations).
   - Soften `.apex-widget:hover` to border-only or `translateY(-1px)`.
   - Reduce `apexEnter` from `translateY(10px)` → `4px`; keep short duration.
   - Expand `@media (prefers-reduced-motion: reduce)` to zero transforms/opacity animations on widgets.
2. `apex-chrome-flash.css`
   - Soften holographic hover (`translateY(-3px) scale(1.015)` → border or −1px).
   - Gate `.apex-grid-floor` / `apexSweep` behind optional ambient class (default off).
   - Restrict `apexGlitch` to explicit error/active alert contexts.
3. `apex-core.js` (if needed)
   - Cap enter stagger to first 3 widgets; reduce `animStagger`.
   - Stop leaving `is-updating` on indefinitely after refresh.

**Validation gate:**
- [ ] Hard-refresh Financial + SoftDent + Claims: no continuous breathe/pulse on cards.
- [ ] Hover feels solid (no card “float”).
- [ ] No ambient sweep on default load.
- [ ] OS reduced-motion: no transform animations.

**Rollback:** Revert the three CSS files (+ JS touch) to `hal-10502`.

**Stop gate (objective — Moonshot R7):** “Dead UI” = operator reports lack of hover/click visual feedback within 3 seconds. Remedy: static border-color shift to cyan (`#00d2ff` / token), **no** transform/scale.

---

### Phase 2 — Empty collapse everywhere (build `hal-10520`) — Effort S

**Objective:** No empty monuments on any page.

**Tasks:**
1. Harden `collapse_empty_large()`: skip `status in ("loading", "skeleton")` and `isSkeleton: true` (Moonshot R3 — avoid strip→expand thrash).
2. Add shared post-process in `build_apex_widgets`:  
   `widgets = [collapse_empty_large(w) for w in widgets]`  
   so every page inherits Financial’s honesty pattern (loading/skeleton preserved by helper).
3. Ensure empty messages name specific imports (SoftDent Collections, QB P&L, etc.) where packs already have gap codes.
4. Unit test: empty `l`/`xl`/`full` → `strip` + `compact`; non-empty unchanged; `collapseWhenEmpty: false` respected; loading/skeleton **not** collapsed.

**Validation gate:**
- [ ] SoftDent / QB / Taxes with missing optional data show ~60px chips, not 300px voids.
- [ ] Financial still collapses collections/payer empties.
- [ ] Populated charts keep their size.

**Rollback:** Remove global collapse pass; restore per-call sites.

---

### Phase 3 — Size discipline + grid tighten (build `hal-10530`) — Effort S–M

**Objective:** First viewport fits KPI strip + primary chart + actions without scroll on 1080p for core pages.

**Tasks:**
1. Tokens: `--apex-grid-gap` / mosaic gap → `6px`; enforce `--apex-widget-min: 140px`; override bridge `300px` mosaic min where safe.
2. Typography: body ~12px; page title ~16px; keep KPI value prominence.
3. Size audit (Moonshot R4): static grep of `size: l|xl|full` **plus** dynamic assignment in builders (`size =`, `set_size(`, instrument kwargs). Runtime check via `normalize_first_viewport` where possible.
4. For **above-fold** instruments on each main page:
   - `xl` → `l` or move below fold
   - tall `full` shelves → strip composites
   - prefer `m` for primary charts (Financial dual-axis: escalate to `l` if labels clip)
5. Optional helper `apply_first_viewport_contract(widgets)`:
   - First strip-like widgets stay top
   - At most one `l` in first 6 widgets
   - Excess `l`/`xl` demoted or flagged for Phase 4 move
6. Page-specific first-viewport targets (from consult map):

| Page | Keep above fold | Demote / later |
|------|-----------------|----------------|
| Financial | status + KPI + dual-axis `m` (or `l` if labels clip) | EBITDA waterfall below / collapsible |
| Taxes | entity/year chips | workpapers table → subpage |
| SoftDent | import chips + sync | register detail → subpage |
| QuickBooks | connection + expense `s`/`m` | full COA → subpage |
| A/R | aging summary chips + `m` bar | aging detail table → subpage |
| Claims | volume KPIs + status `s` bar | kanban → horizontal `l` **or** summary strip + subpage |
| Narratives | counts + new | editor below / modal |
| Documents | storage + filters | preview modal |
| Library | search + chips | denser tables |
| Office Manager | util sparklines + task count | operatory detail → subpage |
| HAL | model status + chat as sole `l` **or** chat below fold | history/logs → subpage |

**Validation gate:**
- [ ] At 1920×1080: Financial, Taxes, SoftDent show primary work without scrolling.
- [ ] Claims uses chosen pattern (horizontal `l` OR summary strip + subpage) — cards readable.
- [ ] HAL uses chosen chat exception — last reply + input usable.
- [ ] Financial dual-axis labels readable at `m`, else escalated to `l`.
- [ ] Mobile/narrow: breakpoints in 2.1.2 hold (gap 4px <768px).

**Blocker before Phase 3 coding:** Operator chooses HAL exception mode + Claims kanban mode.

**Rollback:** Restore sizes/gaps; keep Phase 1–2.

---

### Phase 4 — Subpage migration (build `hal-10540`) — Effort M

**Objective:** Tall tables/editors leave main surfaces; summary strips remain.

**Tasks:**
1. Reuse existing subpage nav pattern; add missing routes only where needed:
   - `/taxes/workpapers`, `/softdent/register`, `/quickbooks/coa`, `/ar/aging-detail`, `/office-manager/operatory`, `/hal/history` (confirm which already exist via subpages packs).
2. Main page: replace detail with `s`/`strip` summary + “Open …” action.
3. Census test: main page widget count/size stays within contract; subpages may be denser.

**Validation gate:**
- [ ] Office Manager first viewport = util chips + task count; detail on subpage.
- [ ] No regression: subpage links work; back-nav works.
- [ ] Honesty preserved on subpages.

**Rollback:** Restore widgets to main page builders; leave routes inert.

---

### Phase 5 — Polish & preference (build `hal-10550`) — Effort M

**Objective:** Operator control + accessibility finish.

**Tasks:**
1. Density toggle Compact (default) / Comfortable → CSS variables via `document.documentElement` + `localStorage`.
2. Finalize reduced-motion coverage.
3. Optional: keyboard `j/k` between strips (only if strip landmarks exist).

**Validation gate:**
- [ ] Compact default matches Phase 3 density.
- [ ] Comfortable restores larger gaps.
- [ ] Reduced-motion OS setting disables transforms.

---

## 5. Cross-cutting constraints

1. **Honesty:** empty ≠ $0; collapse chips, don’t invent KPIs.
2. **PHI:** local only; no new telemetry off-box.
3. **HAL gate split:** keep status/connected vs money/fresh (already shipped); density work must not re-couple.
4. **Prefer additive:** extend `collapse_empty_large` + CSS tokens; avoid rewrite of entire Apex shell.
5. **Tests:** unit for collapse; optional snapshot of first-N widget sizes per page via census helper.
6. **Schema bumps:** one build id per phase (`hal-10510` … `hal-10550`).

---

## 6. Effort & dependency summary

| Phase | Effort | Depends | Risk |
|-------|--------|---------|------|
| 1 Motion | XS | — | Low — CSS |
| 2 Empty collapse | S | 1 recommended | Low — reuse helper |
| 3 Size/grid | S–M | 2 | Med — page audits |
| 4 Subpages | M | 3 | Med — nav/routing |
| 5 Polish | M | 3 | Low |

**Recommended ship order:** 1 → 2 → 3, then pause for operator UX review, then 4 → 5.

---

## 7. Explicit ask to Moonshot (validator)

Please validate this plan as principal engineer:
1. Is the phase order correct? Anything to reorder/merge/split?
2. Are the first-viewport contracts realistic for Claims kanban + HAL chat?
3. Missing risks (mobile, refresh flicker, chart clipping, accessibility)?
4. What would you change before coding Phase 1?
5. Approve / conditional approve / reject — with concrete edits to the plan.

**DO NOT APPLY CODE** in the validation response — opinion + plan edits only.
