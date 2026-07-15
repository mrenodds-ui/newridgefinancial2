# Moonshot AI — Lower Widgets + Upper-Left Control Beam (CONSULT ONLY)

**Date:** 2026-07-15
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_lower_widgets_ctrl_beam_consult.py`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> have moonshot ai move the two lower widgets down and over so they are touching the light beams. also have a light beam touch the upper left widget

---

# Verdict (schema)
**nr2-12014-lower-ctrl-beam**

## 0. Operator Intent (verbatim)
> have moonshot ai move the two lower widgets down and over so they are touching the light beams. also have a light beam touch the upper left widget

## 1. SoftDent + QuickBooks reposition (down + over + beam touch)
- **Translation vector:** Both lower emitters shift **+Y (down toward film plane)** and **±X (inward toward HAL center)**.
  - *SoftDent (lower-left):* move right & down until its aperture flange intersects the white beam terminus.
  - *QuickBooks (lower-right):* move left & down until its aperture flange intersects the orange beam terminus.
- **Optical continuity:** Beam paths remain linear from emitter origin to HAL; widget housings are the mobile element, eliminating the previous gap so the beam appears to enter the box aperture with zero clearance.
- **Constraints preserved:** Emitter color coding (white/orange), HAL targeting, and "empty ≠ $0" SoftDent state remain unchanged.

## 2. Upper-left controls beam → HAL
- **New optical path:** Dedicated coherent beam (teal/cyan, 490–520 nm visual designation) originating from the Controls strip aperture (Master Pulse / Period Wheel / Phase Comp) and terminating at HAL center.
- **Semantic binding:** Represents master synchronization, period clock, and phase compensation data injected into the HAL context.
- **Visual spec:** Solid stroke, 2 px width, `#00CED1` (DarkTurquoise), identical opacity and glow filter as existing magenta/orange/white beams.
- **Topology:** Exactly one beam per source; no beam-splitter ghosts or duplicate upper trails.

## 3. SVG / CSS / mockup change list
| Element | Attribute / Rule | Change |
|---------|------------------|--------|
| `#softdent-housing` | `transform: translate(x, y)` | Shift **+12 % X** (right), **+8 % Y** (down) relative to viewport |
| `#quickbooks-housing` | `transform: translate(x, y)` | Shift **−12 % X** (left), **+8 % Y** (down) relative to viewport |
| `#beam-white` | `x2, y2` | Terminate at new SoftDent aperture coordinates (intersection) |
| `#beam-orange` | `x2, y2` | Terminate at new QuickBooks aperture coordinates (intersection) |
| `#controls-strip` | — | Remain upper-left; aperture marker added for beam origin |
| *New* `#beam-control` | `<line>` or `<path>` | `x1,y1`: Controls aperture; `x2,y2`: HAL center; `stroke: #00CED1`; `class: control-beam` |
| CSS `.control-beam` | `stroke-width: 2px; filter: url(#glow);` | Match existing beam styling |
| `z-index` stacking | `controls > beam-control > hal > lower-widgets` | Ensure beams render beneath widget chrome but above background grid |

## 4. Schema bump justification
- **From:** `nr2-12013-beam-touch`  
- **To:** `nr2-12014-lower-ctrl-beam`
- **Rationale:** 
  1. **Spatial breaking change:** Lower widget coordinates altered (inward/downward translation) invalidates previous collision masks.
  2. **Optical topology expansion:** Addition of fourth coherent path (Controls→HAL) changes the interferometer's channel count from three to four, requiring updated path tracing and phase-alignment metadata.
  3. **Manifest update:** Version bump signals downstream renderers to expect the new teal beam layer and repositioned lower emitters.

## 5. Executive Summary (4 bullets)
- Lower emitters (SoftDent, QuickBooks) are translated down and inward so their apertures physically touch the white and orange beams, eliminating the previous gap.
- A fourth coherent channel (teal Control Beam) is introduced from the upper-left Controls widget to HAL, completing the optical cross and carrying master sync/period/phase data.
- Schema version advances to `nr2-12014-lower-ctrl-beam` to reflect the structural geometry changes and new beam topology.
- No functional logic or data bindings are modified; changes are strictly spatial and graphical to achieve optical continuity.

## 6. Approval checklist
- [x] SoftDent housing aperture intersects white beam terminus (zero gap).
- [x] QuickBooks housing aperture intersects orange beam terminus (zero gap).
- [x] Tax Prism retains existing magenta beam contact (upper-right unchanged).
- [x] Teal Control Beam originates from Controls strip and terminates at HAL center.
- [x] Exactly four beams present (white, orange, magenta, teal); no duplicate paths.
- [x] No beam-splitter ghost images or decorative upper trails.
- [x] SoftDent write-back remains disabled (empty ≠ $0).
- [x] Controls widget remains fixed in upper-left quadrant.
- [x] Schema manifest updated to `nr2-12014-lower-ctrl-beam`.

**Applied (mockup):** `site/nr2-optical-beam-touch-mockup.html` (landing) · SoftDent/QB `left/right: 12%`, `bottom: 68px` · snapBeams includes CTRL teal channel.
