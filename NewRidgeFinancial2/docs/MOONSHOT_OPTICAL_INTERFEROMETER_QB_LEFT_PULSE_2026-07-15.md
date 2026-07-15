# Moonshot AI — QB Left White Beam Pulse (CONSULT ONLY)

**Date:** 2026-07-15
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_interferometer_qb_left_pulse_consult.py`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> tell moonshot ai toremove claims etalon widget and narrative plate, move the bottom widget to the left bottom area where the white beam of light is at.  make it look like that widget has the pulsing light coming out of it

---

# Verdict
**Revision:** NR2-12008-PULSE-ORIGIN  
**Base Schema:** nr2-12007-interference → **Bumped:** nr2-12008-pulse-origin

## 0. Operator Intent (verbatim)
> tell moonshot ai toremove claims etalon widget and narrative plate, move the bottom widget to the left bottom area where the white beam of light is at. make it look like that widget has the pulsing light coming out of it

## 1. Cuts (Claims Etalon, Narrative Plate)
- **Claims Etalon:** Complete excision from viewport. Remove DOM node, CSS grid coordinates (`grid-area: claims-etalon` or absolute positioning), and associated SVG interference pattern. No ghost styling or collapsed placeholders.
- **Narrative Plate:** Complete excision. Remove text panel, ledger texture background, and narrative photon traces. Eliminate z-index layer to prevent occlusion of remaining beams.

## 2. QuickBooks → left-bottom white-beam origin + pulse emission
- **Relocation:** Move QuickBooks emitter widget from bottom-right (southeast) to **left-bottom (southwest)** quadrant, occupying the coordinates previously housing the white beam’s rolling light path terminus.
- **Beam Origin Redirection:** Redirect the white/HAL-colored beam SVG path so its **source anchor** is the QuickBooks emitter aperture (circular port), not a floating flank point.
- **Pulse Emission:**
  - Add `emitter-pulse` CSS keyframe animation to QB aperture ring (glow: 0px → 4px → 0px, opacity 0.6 → 1.0 → 0.6, 2s cycle).
  - Animate the beam stroke as a rolling photon packet traveling **from QB aperture toward HAL core**, creating the illusion that the pulse is physically exiting the widget housing.
  - Sync pulse timing with HAL core shimmer for interference coherence.

## 3. Remaining layout (HAL / SoftDent / Tax / controls)
- **HAL Core:** Remains absolute center (50%, 50%). Maintain interference chamber glow and acceptance cones.
- **SoftDent:** Stays positioned **left/upper (northwest)**. Retain "stale beam" (static or low-frequency shimmer) connecting to HAL; no write-back animation.
- **Tax Prism:** Stays positioned **right-side (east/southeast)**. Maintain its distinct rolling beam into HAL (color: amber/gold to differentiate from white QB beam).
- **QuickBooks:** Now **left-bottom (southwest)**, active pulsing white beam into HAL.
- **Center Corridor:** Clear radius of 20% viewport width around HAL; no widget overlap, ensuring unobstructed optical path visualization.

## 4. Bind map
| Emitter | Target | State | Beam Type |
|---------|--------|-------|-----------|
| SoftDent | HAL | Read-only (stale) | Static/dim |
| **QuickBooks** | **HAL** | **Active write** | **Pulsing white (animated)** |
| Tax Prism | HAL | Active read | Rolling amber |
| ~~Claims Etalon~~ | ~~HAL~~ | ~~REMOVED~~ | ~~N/A~~ |
| ~~Narrative Plate~~ | ~~HAL~~ | ~~REMOVED~~ | ~~N/A~~ |

*Empty values ≠ $0; no SoftDent write-back permitted.*

## 5. Mockup change list
1. **Delete:** `#claims-etalon-widget` and `#narrative-plate` DOM subtrees.
2. **Move:** `#quickbooks-emitter` to CSS coordinates `left: 10%; bottom: 15%;` (left-bottom zone).
3. **Redraw:** White beam SVG `<path>` from QB aperture center (x1,y1) to HAL ingress port (x2,y2).
4. **Animate:** Add `class="pulsing-source"` to QB aperture div; attach CSS animation for radial glow.
5. **Animate:** Implement `stroke-dashoffset` animation on white beam path to simulate photon travel from QB to HAL.
6. **Adjust:** Z-index layering (QB: 10, Beam: 5, HAL: 20) to ensure beam appears to pass behind QB housing lip but glows at aperture.
7. **Clear:** Verify `grid-template-areas` or absolute positioning removes all traces of cut widgets, ensuring no collapsed margin artifacts.
8. **Label:** Update QB widget label to "QuickBooks → HAL" with active sync indicator.

## 6. Schema bump justification
- **Topological Change:** Layout reduced from 5-component to 3-component optical array; Claims and Narrative nodes eliminated.
- **Optical Path Geometry:** White beam origin moved 135° (from left-flank to southwest), altering interference angle calculations.
- **Semantic Inversion:** QuickBooks transitions from passive data sink (bottom-right) to active emission source (left-bottom), requiring new binding logic in schema.
- **Breaking Change:** Removal of Narrative Plate destroys previous "story overlay" rendering layer; downstream parsers must expect absence of `narrative_context` field.

## 7. Executive Summary (5 bullets)
- Excise Claims Etalon and Narrative Plate entirely; no residual DOM or styling.
- Reposition QuickBooks to the left-bottom (southwest) origin point formerly occupied by the white beam terminus.
- Establish QuickBooks as the active pulsing emitter: white beam originates from its aperture with synchronized glow and rolling photon animation into HAL.
- Preserve HAL centrality with a clear 20% radius optical corridor; maintain SoftDent (upper-left, stale) and Tax Prism (right, rolling) positions.
- Bump schema to nr2-12008-pulse-origin to reflect the breaking topological and semantic changes.

## 8. Approval checklist
- [ ] **Claims Etalon** completely removed from DOM and CSS
- [ ] **Narrative Plate** completely removed from DOM and CSS
- [ ] **QuickBooks** repositioned to left-bottom (southwest) coordinates
- [ ] White beam SVG path re-originated from QB aperture (not floating)
- [ ] Pulse animation applied to QB emitter aperture (glow + opacity cycle)
- [ ] Rolling photon animation travels from QB to HAL along white beam
- [ ] SoftDent remains at left/upper with static/stale beam
- [ ] Tax Prism remains at right with rolling amber beam
- [ ] Center corridor verified clear (no widget overlap within 20% HAL radius)
- [ ] Schema version updated to **nr2-12008-pulse-origin**
- [ ] Bind map updated to exclude Claims/Narrative; confirm empty ≠ $0 logic
- [ ] No ERA/Quarantine widgets present

**DO NOT APPLY CODE.**
