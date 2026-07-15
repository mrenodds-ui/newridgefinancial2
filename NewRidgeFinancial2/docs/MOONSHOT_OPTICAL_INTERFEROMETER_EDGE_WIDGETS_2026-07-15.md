# Moonshot AI — Edge-Pinned Instruments (CONSULT ONLY)

**Date:** 2026-07-15
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_interferometer_edge_widgets_consult.py`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> now tell moonshot to move the 4 widgets all the way over to the right and left side edge of the page

---

# Verdict: NR2 Optical Interferometer — Extreme Edge Column Layout  
**Schema stamp:** `nr2-12006-interference` (bump from nr2-12005)

## 0. Operator Intent (verbatim)
> now tell moonshot to move the 4 widgets all the way over to the right and left side edge of the page

## 1. Which 4 widgets + left/right assignment
| Widget | Side | Vertical Position | Function |
|--------|------|-------------------|----------|
| **Claims Etalon** | **LEFT EDGE** | Middle of left stack | Optical cavity for claims interference pattern analysis |
| **ERA-835 Detector** | **LEFT EDGE** | Bottom of left stack | Photodetector for remittance signal capture |
| **Tax Prism** | **RIGHT EDGE** | Middle of right stack | Refractive analyzer for tax scenario splitting |
| **Narrative Plate** | **RIGHT EDGE** | Bottom of right stack | Photographic recording surface for story output |

## 2. Edge layout coordinates / gutters (HAL center preserved)
**Canvas assumption:** 1440×900px absolute coordinate space (responsive scaling permitted).  
**HAL Center:** Fixed at `(720, 450)` — absolute recon circle, radius ~80px.

**Left Edge Column (flush x=60px):**
| Element | Coordinates | Gutters |
|---------|-------------|---------|
| SoftDent Emitter | `(60, 80)` | — |
| **Claims Etalon** | `(60, 280)` | 120px gutter (SD→Etalon) |
| **ERA-835 Detector** | `(60, 480)` | 120px gutter (Etalon→ERA) |

**Right Edge Column (flush x=1380px, right-aligned):**
| Element | Coordinates | Gutters |
|---------|-------------|---------|
| QuickBooks Emitter | `(1380, 80)` | — |
| **Tax Prism** | `(1380, 280)` | 120px gutter (QB→Prism) |
| **Narrative Plate** | `(1380, 480)` | 120px gutter (Prism→Plate) |

**Center Corridor:** Clear zone `x: 200–1240` reserved for beam transit. No widget overlap permitted in this band.

## 3. SoftDent / QuickBooks emitter placement vs edge stacks
- **Deconfliction strategy:** SD/QB nested **above** the instrument stacks at the same extreme x-coordinate (y=80), creating a vertical "source column" at each page edge.
- **Beam geometry:** Diagonal emission from `(60,80)` and `(1380,80)` converging on HAL `(720,450)`. 
  - Left beam slope: Δy/Δx = +0.56 (passes clear of Etalon/ERA at x=60 by vertical separation).
  - Right beam slope: Δy/Δx = -0.56 (passes clear of Prism/Plate at x=1380 by vertical separation).
- **Visual indication:** Beam paths rendered as dashed coherence lines traversing the cleared center corridor; instruments at x=60/1380 show "signal received" indicators without blocking beam geometry.

## 4. Mockup change list
1. **Relocate** Claims Etalon from `(420, 300)` → `(60, 280)` (flush left).
2. **Relocate** ERA-835 Detector from `(420, 450)` → `(60, 480)` (flush left, stacked).
3. **Relocate** Tax Prism from `(1020, 300)` → `(1380, 280)` (flush right).
4. **Relocate** Narrative Plate from `(1020, 600)` → `(1380, 480)` (flush right, stacked).
5. **Reposition** SoftDent Emitter from `(240, 450)` → `(60, 80)` (top of left stack).
6. **Reposition** QuickBooks Emitter from `(1200, 450)` → `(1380, 80)` (top of right stack).
7. **Adjust** beam path rendering from horizontal to diagonal (15° angle) to accommodate new emitter heights while maintaining HAL center target.
8. **Enforce** 120px vertical gutters between emitters and instruments to prevent UI overlap while preserving "same column" visual grouping.

## 5. Bind map (unchanged except positions)

| Widget | New Location | SoftDent | QuickBooks | HAL | API / Capability | Honesty Rule |
|--------|--------------|----------|------------|-----|------------------|--------------|
| **Claims Etalon** | `(60, 280)` Left | ✅ | ❌ | ✅ | `POST /api/apex/hal/claims-interference` | Vacuum display if SD beam null; no $0.00 writes. |
| **ERA-835 Detector** | `(60, 480)` Left | ✅* | ❌ | ✅ | `POST /api/apex/hal/era835-ingest` | *Requires SD AR context. Amber→Green lock detection. |
| **Tax Prism** | `(1380, 280)` Right | ❌ | ✅ | ✅ | `POST /api/apex/tax/calculate-planning` | Refracts QB payroll/AP beams; empty OK if no QB file. |
| **Narrative Plate** | `(1380, 480)` Right | ✅ | ✅ | ✅ | `POST /api/apex/narratives/generate` | Exposes HAL fused output; read-only plate. |
| **HAL Recon Core** | `(720, 450)` Center | ✅ (ingest) | ✅ (ingest) | ✅ (process) | `POST /api/apex/hal/reconciliation` | Dark core if either emitter null; no write-back to SD. |
| **SD Emitter** | `(60, 80)` Left | ✅ | ❌ | ❌ | `POST /api/apex/softdent/refresh-period` | Source-only. Dashed beam if auth expired. |
| **QB Emitter** | `(1380, 80)` Right | ❌ | ✅ | ❌ | `POST /api/apex/sync/qb-payroll-ap-export` | Source-only. "Empty OK" pilot light active. |

## 6. Schema bump justification
- **nr2-12005** assumed horizontal beam geometry with emitters at mid-flank `(240,450)` and `(1200,450)`.
- **nr2-12006** introduces **vertical edge stacking** and **diagonal beam geometry** to satisfy "flush to page edge" directive while preserving emitter-instrument binding integrity.
- Layout topology changed from "horizontal row" to "peripheral column" architecture; warrants minor revision bump.

## 7. Executive Summary (5 bullets)
- **Extreme edge positioning:** All 4 instrument widgets now occupy absolute left (x≈60) and right (x≈1380) page margins, stacked vertically with 120px gutters.
- **HAL centrality preserved:** AI core remains locked at `(720,450)`; no drift from absolute center recon circle.
- **Emitter nesting:** SoftDent and QuickBooks relocated to top of respective edge columns (y=80), avoiding overlap with instruments while maintaining source housing function.
- **Clear center corridor:** Diagonal beam geometry (15°) creates unobstructed transit zone between x=200–1240, ensuring optical interference visualization remains uncluttered.
- **Binding integrity:** All widget-to-system mappings (SD/QB/HAL) preserved; no quarantine states introduced, no SoftDent write-back paths created.

## 8. Approval checklist
- [ ] **HAL Center:** Confirmed fixed at `(720, 450)` — no positional drift.
- [ ] **Edge Flush:** Claims Etalon + ERA-835 at left edge; Tax Prism + Narrative Plate at right edge.
- [ ] **No Overlap:** 120px vertical gutters between emitters and instruments; no x-coordinate collision.
- [ ] **SD/QB Deconflict:** Emitters nested above stacks at y=80; instruments at y=280/480.
- [ ] **Center Corridor:** Cleared for beam transit; diagonal paths avoid edge-stack interference.
- [ ] **Empty States:** Preserved "empty ≠ $0" logic; SoftDent write-back remains disabled.
- [ ] **Schema Version:** Bumped to `nr2-12006-interference` to reflect layout topology change.

**DO NOT APPLY CODE.** Awaiting operator approval to commit to optical table.
