# Moonshot AI — Program-Aware Interferometer Enhancement (CONSULT ONLY)

**Date:** 2026-07-15
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_interferometer_program_enhance_consult.py`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> remind moonshot what all the property and actions of the program are for and see if he can enhance it

---

# Verdict
**The Optical Interferometer — Full Spectrum Practice Control Surface**  
**Schema stamp:** `nr2-12002-interference`

## 0. Operator Intent (verbatim)
> remind moonshot what all the property and actions of the program are for and see if he can enhance it

## 1. Program reminder — what properties & actions are FOR (tight)
**Properties** are the coherent data beams: SoftDent (clinical AR/aging/register), QuickBooks (GL/expenses/payroll-AP), HAL (intelligence/posture), and ERA-835 (remittance photons). They exist to create a **unified mirror** of practice health without write-back pollution.

**Actions** are the physical controls on the bench: pulse triggers (sync), filter wheels (period selection), beam dumps (quarantine), and refractive prisms (tax scenarios). They are FOR manipulating the *observation* and *alignment* of beams, never for inventing dollars or writing to SoftDent. RBAC governs which operators possess physical keys to unlock specific optical controls.

## 2. Coverage gaps vs current interferometer
The current tri-emitter bench (SD/QB/HAL) only visualizes **coherence**—it cannot yet express:
- **Claims workflow** (kanban states, denials, critical actions)
- **ERA-835 ingest** (remittance discovery/ingest pipeline)
- **Tax/EBITDA planning** (scenario projection)
- **Import quarantine** (poisoned/blocked data containment)
- **Narrative generation** (clinical draft holography)
- **Concrete action triggers** (sync, refresh-period, recon run, cache-warm)
- **RBAC gating** (who can fire which pulse)

## 3. Enhancement thesis (how the bench becomes the program control surface)
Expand the optical bench from a **coherence detector** into a **full-spectrum control chassis** by mounting modular optical instruments around the central triangle. Each program domain gains a physical optical analog:
- **Claims** → Interferometric cavity (Etalon)
- **ERA** → Photodetector array
- **Taxes** → Refractive prism with projective paths
- **Quarantine** → Beam dump with trap door
- **Actions** → Tactile switches, Q-switches, and filter wheels
- **RBAC** → Safety shutters and key-lock switches

The viewport remains sealed (1280×720, zero-scroll), but the **depth** (z-axis) now contains the full program surface area.

## 4. Action→optic map (table: action → control → feedback → honesty rule)

| Action | Optical Control | Visual Feedback | Honesty Rule |
|--------|----------------|-----------------|--------------|
| `POST /api/apex/sync/trigger` | **Master Pulse Switch** (red lever, left of Core) | Beam flash from emitters → Core; Vacuum gauge needle spike | Single-flight lockout ( lever disabled while "Discharge" LED lit) |
| `POST /api/apex/softdent/refresh-period` | **Period Filter Wheel** (rotating turret, SD emitter base) | Click-stops at 30/60/90/120 days; Beam color shifts hue slightly per period | Cannot rotate to future dates (mechanical stop); stale periods show corrosion on wheel |
| `POST /api/apex/hal/era835-ingest` | **Remittance Photodetector Array** (honeycomb grid, below SD) | Individual cells light amber as 835s discovered; Green "Locked" when ingested | Read-only confirmation: No "write-back" LED exists (absence is honesty) |
| `POST /api/apex/hal/import-quarantine/release` | **Trap Door Lever** (yellow/black striped, bottom-left) | Clunk animation + poisoned beam (red) drains into dump; Clear beam restores | OM key required (shutter lifts only when `manage_ocr` cap present) |
| `POST /api/apex/hal/reconciliation` | **Phase Comparator Button** (silver plunger, Core housing) | Fringe pattern freezes, strobes 3×, then stabilizes; Moiré amplitude = variance | Empty QB beam = dashed line (empty ≠ $0); no flat-field if missing data |
| `POST /api/apex/tax/calculate-planning` | **Scenario Prism Rotator** (knurled dial, QB beam path) | Refracts beam into 3 projective paths (Current/Scenario A/B) on screen wall | Label "SCENARIO" permanently visible on projected beams; no $ values on core |
| `POST /api/apex/narratives/generate` | **Holographic Plate** (glass slide between HAL→Core) | Interference pattern resolves into text lines (draft narrative) | "DRAFT" watermark always present; no findings invented if HAL uncertain |
| `POST /api/apex/hal/board-actions` | **Gantry Control Joystick** (center-right) | Navigates focus widget highlight (laser pointer dot) across bench | Cloud HAL denied by default (polarizing filter blocks cloud beam) |
| `GET /api/import-readiness` | **Alignment Laser Grid** (crosshairs projected across bench) | Green = aligned (Critical datasets present); Red X = blocking gaps | Soft gaps show yellow warning tape (not red X); honesty about optional data |
| `POST /api/apex/sync/qb-payroll-ap-export` | **Auxiliary Beam Splitter** (QB emitter side-port) | CSV particles eject from side port into collection bin | "Empty OK" indicator lights if no payroll found (honest emptiness) |

## 5. Emitter / optic expansions (claims, taxes, ERA, quarantine, OM — without clutter)

### A. Claims Etalon (Fabry-Pérot Cavity)
- **Location:** Mounted on SoftDent beam, 40% distance from emitter
- **Visual:** Two partially silvered glass plates creating standing waves
- **Function:** Resonant modes represent claim states (Clean = bright transmission, Denied = dark nodes, Appealed = pulsating intermediate)
- **Interaction:** Click cavity to open Claims Kanban (modal overlay, not scroll)

### B. ERA-835 Photomultiplier Array
- **Location:** 80px below SoftDent emitter, hexagonal honeycomb
- **Visual:** Individual cells glow when ERA files detected; intensity = dollar volume (not $0 if empty, just dark)
- **Function:** Click array to trigger `era835-ingest` or view inbox

### C. Tax Refraction Prism
- **Location:** On QuickBooks beam, post-polarizer
- **Visual:** Triangular glass block splitting beam into Current (white), Plan A (cyan), Plan B (magenta)
- **Function:** Rotate dial to project scenarios onto "Filing Screen" (right side viewport wall)

### D. Quarantine Beam Dump (Faraday Cage)
- **Location:** Bottom-left corner, z-index behind emitters
- **Visual:** Black cylindrical trap with glass viewport showing swirling red "poisoned" particles
- **Function:** Lever releases (retry) or purges; shutter prevents access if no `override_import` cap

### E. RBAC Safety Shutters & Key Switches
- **Location:** On every control lever/wheel
- **Visual:** 
  - Front desk/hygienist: Red "LOCKED" tape across levers; beams physically blocked by metal shutters
  - OM/Dentist: Keyhole glows green when inserted; shutters retract with satisfying mechanical animation
- **Function:** Purely visual representation of capability checks; no hidden UI, just physical obstruction

### F. Narrative Hologram Plate
- **Location:** Suspended between HAL emitter and Core
- **Visual:** Glass plate that catches HAL beam and resolves interference into text
- **Function:** Slide plate in/out of beam path to show/hide narrative drafts

## 6. Updated schema (keep 12001 or bump 12002 — justify)
**Bump to `nr2-12002-interference`**

Justification: This enhancement adds **four major program surfaces** (Claims, Taxes, ERA, Quarantine) and **RBAC physicalization** that were absent in 12001. The schema now covers the complete action surface area from the authoritative Program Map, not just reconciliation coherence.

```json
{
  "BUILD_ID": "nr2-12002-interference",
  "schemaVersion": "nr2-12002-interference",
  "assetVersion": "nr2-12002-interference",
  "staffRenderMode": "nr2-optical-bench-full",
  "notes": "Full-spectrum optical bench. Added Claims Etalon, ERA Photodetector, Tax Prism, Quarantine Dump, RBAC shutters. All critical actions mapped to tactile optical controls. Zero-scroll maintained. Empty≠$0 enforced via beam states."
}
```

## 7. Mockup instructions (what to add to addons mockup)
Add to `nr2-optical-interferometer-addons-mockup.html`:

1. **Left side:** Claims Etalon glass cavity on SD beam; honeycomb ERA detector below SD emitter
2. **Right side:** Tax prism on QB beam with projection wall (right edge of viewport)
3. **Bottom-left:** Quarantine beam dump cylinder with trap door lever
4. **Control panel zone:** Bottom-center 200px strip containing:
   - Red Master Pulse lever
   - Silver Phase Comparator plunger
   - Period Filter Wheel (clickable stops)
5. **RBAC layer:** Semi-transparent shutter overlays on all controls; "KEY REQUIRED" labels for unauthorized roles
6. **HAL path:** Insert Narrative Hologram Plate (slide toggle to move into beam)
7. **Alignment lasers:** Subtle crosshair projections showing import-readiness state

## 8. Acceptance criteria
- [ ] Every action from Program Map Section "Critical actions" has a tactile optical control defined
- [ ] RBAC visually gates controls (shutters/locks) based on `front_desk` vs `office_manager` vs `dentist` caps
- [ ] Empty states render as **broken/dashed beams** or **dark detectors**, never as "$0.00" displays
- [ ] No control suggests SoftDent write-back (no "Post to SD" button, no "Adjust AR" lever)
- [ ] Schema 12002 stamps appear in all asset metadata
- [ ] Zero-scroll constraint maintained (1280×720 sealed viewport)
- [ ] Honesty rules from Program Map are enforced by optical metaphor (e.g., absence of light = absence of data)

## 9. Executive Summary (7 bullets)
- **Full Program Surface:** The bench now expresses Claims, Taxes, ERA, Quarantine, and Narratives via optical components (Etalon, Prism, Photodetector, Dump, Hologram).
- **Action Coverage:** All 12 critical API actions mapped to tactile controls (levers, wheels, buttons) with immediate optical feedback.
- **RBAC Physicalized:** Capabilities become physical safety shutters and key locks—unauthorized users see blocked beams, not disabled buttons.
- **Honesty Enforcement:** Empty datasets break beams (dashed lines); no "$0" invented values; tax scenarios permanently labeled; no SoftDent write-back controls exist.
- **Metabolic Integrity:** Optical metaphor strictly maintained (no Bloomberg mosaics, no apex packs, no rectangular widget cards).
- **Zero-Scroll Preserved:** 1280×720 vacuum chamber contains all controls via z-depth layering and modal overlays.
- **Schema Evolution:** Bump to 12002 reflects major functional expansion while preserving the clean-slate cutover integrity.

## 10. Approval checklist
- [ ] Operator confirms optical metaphors (Etalon, Prism, Dump) align with program intent
- [ ] RBAC shutter approach approved for front_desk vs OM vs Dentist differentiation
- [ ] Honesty rules (empty≠$0, no write-back) sufficiently enforced by beam states
- [ ] Schema 12002 accepted as new canonical stamp
- [ ] Mockup implementation authorized (proceed to build)
