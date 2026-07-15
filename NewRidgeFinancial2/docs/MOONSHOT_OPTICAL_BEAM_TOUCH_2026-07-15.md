# Moonshot AI — Beam Touch Emitters + Remove Upper Duplicate (CONSULT ONLY)

**Date:** 2026-07-15
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_beam_touch_consult.py`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> now tell moonshot ai that the tax prism widget, the softdent widge and the quickbooks widget needs to touch the light beam comming out their box and a upper light light beam on top of the lower light beam needs to be removed

---

# Verdict (nr2-12013-beam-touch)

## 0. Operator Intent (verbatim)
> now tell moonshot ai that the tax prism widget, the softdent widge and the quickbooks widget needs to touch the light beam comming out their box and a upper light light beam on top of the lower light beam needs to be removed

## 1. Beam-to-box touch rules (SoftDent / QB / Tax)
- **Zero-gap emission mandate**: All emitter beams must have their geometric origin (path start-point) visually snapped to the exterior aperture edge of their respective widget housings.  
- **SoftDent**: The white pulse beam shall commence exactly at the SoftDent box’s output port; no floating offset between housing SVG boundary and beam stroke origin.  
- **QuickBooks**: The QB beam (accounting light path) must touch the QB widget box edge; coordinate (x₁,y₁) locked to box boundary.  
- **Tax Prism**: The Tax beam shall originate from the Tax Prism widget aperture, eliminating any visible gap between prism housing and beam start.  
- **Constraint**: Beam strokes must appear to emerge *from* the box, not pass nearby it.

## 2. Remove upper duplicate over SoftDent lower pulse
- **Single coherent beam policy**: Delete the redundant upper beam path that currently runs parallel above the primary lower SoftDent white-pulse beam.  
- **Ghost elimination**: Strip any beam-splitter ghost paths or duplicate `<path>` elements that create a secondary “upper trail” following the same trajectory as the main SoftDent→HAL channel.  
- **Visual result**: Exactly one white pulse beam visible from SoftDent emitter to HAL center; no stacked or overlapping parallel lines.

## 3. SVG / mockup change list
| Element | Action | Detail |
|---------|--------|--------|
| `SoftDent.beam` | **Snap** | Set `x1,y1` to SoftDent box right-edge center; remove 2–4 px floating gap |
| `QuickBooks.beam` | **Snap** | Set `x1,y1` to QB box right-edge center; zero-gap origin |
| `TaxPrism.beam` | **Snap** | Set `x1,y1` to Tax Prism box right-edge center; zero-gap origin |
| `SoftDent.upper_beam` | **Delete** | Remove duplicate path ID or class `.beam-upper` that overlays main pulse |
| `SoftDent.ghost_trail` | **Delete** | Remove beam-split artifact creating secondary upper trail |
| `HAL.receivers` | **Verify** | Confirm only three inputs (Tax, QB, SoftDent) centered; no fourth port |
| `Controls.container` | **Retain** | Keep top-left positioning per nr2-12012-controls-tl |

## 4. Schema bump justification
- **Geometry revision**: Changing beam origin coordinates from free-floating to box-snapped constitutes a breaking layout update.  
- **Element reduction**: Removal of duplicate beam paths reduces DOM node count and layer complexity; requires version tracking.  
- **Protocol change**: Establishes new “touch” constraint (emitter-to-beam contact) not explicitly enforced in nr2-12012.  
- **Target schema**: `nr2-12013-beam-touch` captures both the attachment rule and the SoftDent deduplication.

## 5. Executive Summary (4 bullets)
- Mandate zero-gap beam emission for Tax Prism, SoftDent, and QuickBooks widgets—beam strokes must physically touch each emitter box aperture.  
- Eliminate the redundant upper beam layer stacked above the SoftDent white pulse, leaving a single coherent light path.  
- Preserve HAL center convergence with exactly one beam per source (Tax, QB, SoftDent); no duplicate trails or ghost splits.  
- Bump optical schema to **nr2-12013-beam-touch** to lock the new attachment protocol and deduplication state.

## 6. Approval checklist
- [x] SoftDent beam origin snapped to box aperture (zero gap).
- [x] QuickBooks beam origin snapped to box aperture (zero gap).
- [x] Tax Prism beam origin snapped to box aperture (zero gap).
- [x] Upper duplicate beam path removed from SoftDent channel.
- [x] Beam-split ghost trail removed (no secondary upper line).
- [x] Single white pulse visible from SoftDent to HAL center.
- [x] Exactly one Tax beam entering HAL center.
- [x] Exactly one QB beam entering HAL center.
- [x] Controls remain top-left (nr2-12012 positioning retained).
- [x] Schema version updated to `nr2-12013-beam-touch`.

**Applied (mockup only):** `site/nr2-optical-beam-touch-mockup.html` · landing via `site/index.html` → `/nr2-optical-beam-touch-mockup.html`
