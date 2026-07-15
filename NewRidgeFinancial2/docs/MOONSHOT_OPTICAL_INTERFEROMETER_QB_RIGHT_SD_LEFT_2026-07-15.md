# Moonshot AI — QB Right · SoftDent Flush Left (CONSULT ONLY)

**Date:** 2026-07-15
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_interferometer_qb_right_sd_left_consult.py`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> tell moonshot to place quickbooks widget back to the other side and move the lower widget all the way over to the left

---

# Verdict (nr2-12009-interference: Lateral Inversion Correction)

## 0. Operator Intent (verbatim)
> tell moonshot to place quickbooks widget back to the other side and move the lower widget all the way over to the left

## 1. QuickBooks → right side + beam
**Relocation:** QuickBooks vacates the left-bottom quadrant (x≈5%, y≈80%) and resets to the **right-bottom emitter** (x≈90%, y≈80%), restoring its canonical pre-inversion position.

**Optical Restoration:**  
- **Beam type:** Rolling gold/amber (λ≈590 nm, continuous phase).  
- **Path:** Right-bottom emitter → HAL center (incident angle 45° from lower-right).  
- **Interference role:** Re-establishes the right-flank financial fringe pattern, pairing with Tax Prism upper-right to create stable right-side heterodyne against SoftDent’s new left-side pulse.

## 2. SoftDent (lower) → flush left + white pulse origin
**Relocation:** SoftDent descends from upper-left (x≈10%, y≈20%) to **flush left-bottom** (x≈2%, y≈80%), occupying the vacuum left by QuickBooks’ departure.

**Optical Reassignment:**  
- **Beam type:** White pulsing (λ≈450–470 nm, 2 Hz strobe).  
- **Origin:** SoftDent housing now emits the left-bottom white pulse directly into HAL’s left aperture.  
- **Integrity State:** If SoftDent AR ledger is stale, the beam persists but exhibits *honesty filtration*—broken secondary filament produces dim flicker (empty ≠ $0), visually indicating unwritable-back status without beam collapse.

## 3. Layout coordinates
| Entity | Position (viewport %) | Anchor | Beam Target |
|--------|----------------------|--------|-------------|
| **HAL** | (50, 50) | Center | Interference nexus |
| **QuickBooks** | (90, 80) | Bottom-Right | HAL right input (gold/amber) |
| **SoftDent** | (2, 80) | Flush Left-Bottom | HAL left input (white pulse) |
| **Tax Prism** | (90, 20) | Upper-Right | HAL upper-right input (violet/indigo spectrum) |

*Z-index:* SoftDent and QuickBooks share y-plane (80%) but are separated by 88% horizontal margin to prevent emitter overlap.

## 4. Bind map
```
SoftDent.out (white_pulse) ───────┐
                                  │
QuickBooks.out (gold_rolling) ────┼──→ HAL.center (interference pattern)
                                  │
TaxPrism.out (prism_refract) ─────┘

HAL.center → (no outbound to Claims/Narrative; sinks only)
```

## 5. Mockup change list
1. **Migrate QB:** Translate widget from left-bottom (0.05,0.80) to right-bottom (0.90,0.80).
2. **Swap Beam Signature:** QB beam color `#FFD700` (gold) with rolling phase texture; remove white pulse shader.
3. **Migrate SoftDent:** Translate widget from upper-left (0.10,0.20) to flush left-bottom (0.02,0.80).
4. **Transfer Beam Ownership:** Attach white pulse shader (`#F0F8FF`, 2 Hz) to SoftDent emitter node; remove from QB.
5. **Honesty State Check:** Apply dim filament shader to SoftDent beam if `AR.stale == true`.
6. **Clean Slate:** Confirm Claims/Narrative/ERA/Quarantine widgets remain absent from viewport.

## 6. Schema bump justification
**nr2-12008-interference → nr2-12009-interference**

The lateral inversion of two primary financial emitters alters optical path lengths (OPL) and phase conjugation:
- **Left-flank recalibration:** SoftDent’s relocation to x≈2% changes the incident angle to HAL’s left aperture by ≈12°, requiring updated interference coefficients.
- **Right-flank restoration:** QB’s return to x≈90% re-establishes the original right-bottom node reference frame, invalidating the temporary left-white calibration of 12008.
- **Beam coherence:** Gold (QB) vs. white (SoftDent) wavelength separation prevents modal crosstalk; schema bump documents the new chromatic isolation protocol.

## 7. Executive Summary (5 bullets)
- **Reverses lateral inversion:** QB returns to canonical right-bottom financial emitter position; SoftDent assumes dedicated left-bottom zone.
- **Restores chromatic taxonomy:** Gold/amber rolling beam (QB) vs. white pulsing beam (SoftDent) eliminates spectral confusion.
- **Diagnostic transparency:** SoftDent’s white pulse carries visual honesty indicator (dim filament) when AR is stale, preventing false zero-balance illusions.
- **Maintains upper-right anchor:** Tax Prism remains fixed at upper-right, ensuring stable triangular interference geometry with HAL.
- **Zero contamination:** Complete absence of Claims/Narrative/ERA emitters prevents quarantine leakage into financial interference patterns.

## 8. Approval checklist
- [ ] QuickBooks widget positioned at right-bottom (x≈90%, y≈80%) with active gold/amber rolling beam.
- [ ] SoftDent widget positioned flush left-bottom (x≈2%, y≈80%) as sole white pulse originator.
- [ ] SoftDent beam exhibits dim/broken secondary filament when AR stale (honesty state).
- [ ] Tax Prism remains upper-right emitter (x≈90%, y≈20%).
- [ ] HAL center receives three clean inputs: left-white (SoftDent), right-gold (QB), upper-prism (Tax).
- [ ] No Claims, Narrative, ERA, or Quarantine widgets present in viewport.
- [ ] Optical path length (OPL) tables updated for new emitter coordinates in schema nr2-12009.
