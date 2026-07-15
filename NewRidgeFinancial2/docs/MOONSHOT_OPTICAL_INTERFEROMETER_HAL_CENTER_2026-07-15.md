# Moonshot AI — HAL as Center AI Core (CONSULT ONLY)

**Date:** 2026-07-15
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_interferometer_hal_center_consult.py`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> looking great, but hal is the ai model core and should be in the middle recon circle

---

# Verdict: NR2 Optical Interferometer — HAL-Centric Recon Core  
**Schema stamp:** `nr2-12005-interference`

## 0. Operator Intent (verbatim)
> looking great, but hal is the ai model core and should be in the middle recon circle

## 1. HAL-as-core redesign (what moves into the circle; what leaves corners)
- **What enters the center:** HAL AI Core (spectral brain). The center recon circle is now the **HAL Reactor**—the active cognitive fusion chamber where reconciliation, narrative generation, and board-action orchestration occur. The previous generic "Phase Comparator" housing is rebranded as the HAL Core Interface.
- **What leaves corners:** SoftDent and QuickBooks relocate to **peripheral emitter positions** (left and right flanks, respectively). They function as pure data sources, firing coherent beams into the central HAL Core for processing.
- **Topology inversion:** Previous schema positioned HAL as a top-down emitter feeding a neutral comparator. New schema positions HAL as the gravitational center receiving horizontal beams from SD/QB satellites.
- **Vacuum integrity:** The Core exposes no "write-back" ports to SD; HAL ingests, analyzes, and projects upward only.

## 2. SoftDent / QuickBooks emitter roles vs HAL center
| Role | System | Position | Function |
|------|--------|----------|----------|
| **Left Emitter** | SoftDent | (240, 450) | Emits "AR Reality Beam" (patient ledgers, ERA 835 context, period-filtered data) eastward into HAL. Contains no processing logic; pure data transmission. |
| **Right Emitter** | QuickBooks | (1200, 450) | Emits "Financial Reality Beam" (payroll, AP, tax scenarios) westward into HAL. Contains no processing logic; pure data transmission. |
| **Central Core** | HAL | (720, 450) | **The AI Brain.** Receives both beams, performs interference pattern analysis (reconciliation), generates narratives, and projects unified reality upward. |

**Critical constraint:** SD and QB remain **emitters only**. They do not overlap the center circle, do not perform reconciliation, and do not display final composite data. HAL is the sole authority for fused output.

## 3. Bind map (updated; widget → systems → API)

| Widget | Location | SoftDent | QuickBooks | HAL | API / Capability | Honesty Rule |
|--------|----------|----------|------------|-----|------------------|--------------|
| **HAL Recon Core** | Center Circle | ✅ (ingest) | ✅ (ingest) | ✅ (process) | `POST /api/apex/hal/reconciliation`, `POST /api/apex/narratives/generate`, `GET /api/apex/hal/board-actions` | Displays interference fringes only when both beams present; vacuum (dark core) if either emitter null. |
| **SD Emitter Assembly** | Left Flank | ✅ | ❌ | ❌ | `POST /api/apex/softdent/refresh-period` | Source-only. Beam breaks (dashed) if SD auth expires. |
| **QB Emitter Assembly** | Right Flank | ❌ | ✅ | ❌ | `POST /api/apex/sync/qb-payroll-ap-export`, `POST /api/apex/tax/calculate-planning` | Source-only. "Empty OK" pilot light if QB company file null; never $0.00. |
| **Master Pulse Switch** | Left of Center (540,450) | ✅ | ✅ | ✅ | `POST /api/apex/sync/trigger` | Initiates HAL recon cycle; locks during flight. |
| **Period Filter Wheel** | On SD Housing (240,570) | ✅ | ❌ | ❌ | `POST /api/apex/softdent/refresh-period` | Mechanical detents for 30/60/90/120 days; corrosion texture if stale. |
| **Remittance Photodetector** | SD Beam Path (420,450) | ✅* | ❌ | ✅ | `POST /api/apex/hal/era835-ingest` | *Requires SD AR context. Amber detection → Green lock. |
| **Scenario Prism Rotator** | On QB Housing (1200,570) | ❌ | ✅ | ❌ | `POST /api/apex/tax/calculate-planning` | Refracts QB beam into Current/A/B paths before HAL ingestion. |
| **Auxiliary Beam Splitter** | QB Side-port (1320,450) | ❌ | ✅ | ❌ | `POST /api/apex/sync/qb-payroll-ap-export` | Tangential CSV export; bypasses HAL Core. |
| **Gantry Joystick** | Below HAL (720,630) | ❌ | ❌ | ✅ | `GET/POST /api/apex/hal/board-actions` | Navigates HAL action items; spring-return if queue empty. |
| **Holographic Plate** | Above HAL (720,270) | ✅ | ❌ | ✅ | `POST /api/apex/narratives/generate` | Projects HAL-generated draft narrative overlay. |
| **Alignment Laser Grid** | Full Viewport | ✅ | ✅ | ✅ | `GET /api/import-readiness` | Crosshair overlay: Red quadrant = missing critical beam; Green = coherent. |

## 4. No-overlap layout with HAL center coordinates
**Viewport:** 1440 × 900 px (sealed, zero-scroll, 16:10)  
**Base unit:** 24 px  
**Exclusion zone:** 48 px minimum gutter between bounding boxes  
**Hit target:** 48 × 48 px minimum

| Element | Center (x,y) | Bounding Box (x₁,y₁ → x₂,y₂) | Diameter/Size | Notes |
|---------|--------------|------------------------------|---------------|-------|
| **HAL AI Core** | (720, 450) | 630,360 → 810,540 | 180 px | **Center recon circle.** Spectral brain housing. |
| **SoftDent Emitter** | (240, 450) | 192,402 → 288,498 | 96 px | Left peripheral. Emits eastward. |
| **QuickBooks Emitter** | (1200, 450) | 1152,402 → 1248,498 | 96 px | Right peripheral. Emits westward. |
| **Period Filter Wheel** | (240, 570) | 204,534 → 276,606 | 72 px | Below SD emitter (48px gutter). |
| **Remittance Photodetector** | (420, 450) | 396,426 → 444,474 | 48 px | In SD beam path, midway to HAL. |
| **Scenario Prism Rotator** | (1200, 570) | 1164,534 → 1236,606 | 72 px | Below QB emitter (48px gutter). |
| **Auxiliary Beam Splitter** | (1320, 450) | 1296,426 → 1344,474 | 48 px | QB side-port (right of emitter). |
| **Master Pulse Switch** | (540, 450) | 516,426 → 564,474 | 48 px | Left of HAL Core (48px gutter). |
| **Gantry Joystick** | (720, 630) | 696,606 → 744,654 | 48 px | Below HAL Core (48px gutter). |
| **Holographic Plate** | (720, 270) | 672,222 → 768,318 | 96 px | Above HAL Core (48px gutter). |

**Beam Geometry:**
- **SD→HAL Beam:** 6px stroke, connects (288,450) to (630,450). Length: 342px.
- **QB→HAL Beam:** 6px stroke, connects (1152,450) to (810,450). Length: 342px.
- **HAL Output:** 6px stroke, connects (720,360) to (720,318). Projects narrative upward.

## 5. Mockup change list
1. **HAL Relocation:** Moved from top emitter position to center recon circle (720,450); diameter increased to 180px to signify core importance.
2. **SD/QB Repositioning:** Moved to horizontal flanks (Y=450) to create symmetrical interference bench.
3. **Core Rebranding:** "Phase Comparator" label retired; housing now labeled "HAL Spectral Core."
4. **Beam Directionality Inverted:** SD and QB now emit *into* HAL; previously HAL emitted *down* to a comparator.
5. **Control Repositioning:**
   - Master Pulse Switch moved to left of HAL (between SD and Core).
   - Gantry Joystick moved below HAL.
   - Holographic Plate moved above HAL (output projection).
6. **Period/Prism Mounting:** Filter wheels and prisms now physically mounted on emitter housings (SD and QB respectively) rather than floating in space.
7. **Removed:** "HAL Emitter" housing at top of viewport; HAL is now the destination, not a source.

## 6. Schema bump justification
- **nr2-12004 → nr2-12005-interference**
- **Architectural inversion:** Center-of-mass relocated from passive comparator to active AI agent (HAL). This changes the data-flow topology from "peripheral sources → central comparison" to "peripheral sources → central cognitive fusion."
- **API hierarchy shift:** HAL endpoints (`/hal/reconciliation`, `/hal/narratives`, `/hal/board-actions`) are now positioned as the primary consumer of SD and QB feeds, rather than peer-to-peer synchronization.
- **Binding topology:** The interferometer is reclassified from a "tri-source bench" to a "dual-emitter/single-core reactor." This warrants a minor version bump under the nr2 optical family.
- **Ontological clarity:** HAL is no longer one of three emitters; it is the singular brain with SD/QB as sensory organs.

## 7. Executive Summary (5 bullets)
- **HAL is the Heart:** The AI model core now physically and logically occupies the center recon circle (720,450), serving as the spectral fusion brain where SoftDent and QuickBooks data streams interfere and reconcile.
- **Peripheral Emitters:** SoftDent (left) and QuickBooks (right) function as pure data sources on the horizontal optical axis, feeding coherent beams into HAL without local processing or display authority.
- **Horizontal Interference Bench:** All three systems align on Y=450, creating a clean left-to-right beam topology with HAL at the convergence point, ensuring no overlaps and 48px gutters throughout.
- **Honest Vacuum States:** Empty QB or SD beams render as broken/dashed lines entering HAL; HAL never fabricates dollar values ($0.00) and performs reconciliation only when both beams are present (vacuum if null).
- **Full Bind Compliance:** Every widget maps to specific HAL, SD, or QB APIs; no decorative controls, no SoftDent write-back capability exists, and the Quarantine Dump widget remains excised per prior directive.

## 8. Approval checklist
- [ ] HAL occupies center recon circle (720,450) with 180px diameter
- [ ] SoftDent emitter positioned at left flank (240,450) — not in center
- [ ] QuickBooks emitter positioned at right flank (1200,450) — not in center
- [ ] All three systems aligned on horizontal optical axis (Y=450)
- [ ] 48px minimum gutters maintained between all bounding boxes (no overlaps)
- [ ] No Quarantine Dump widget present in layout
- [ ] No SoftDent write-back API bound to any widget
- [ ] Empty states render as vacuum/dashed beams, never $0.00
- [ ] Schema bumped to `nr2-12005-interference`
- [ ] All widgets in bind map connect to valid shipping APIs (`nr2-11000-clean` runtime)
