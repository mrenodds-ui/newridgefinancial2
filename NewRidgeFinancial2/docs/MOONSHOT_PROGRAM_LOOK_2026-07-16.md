# Moonshot AI — What To Do With The LOOK Of The Program (CONSULT ONLY)

**Date:** 2026-07-16
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Status:** ok
**Repo root:** `C:\Users\mreno\newridgefamilyfinancial`
**Prior OPS:** `eee9168` desk smoke · `a753f31` SoftDent morning bundle
**Script:** `scripts/run_moonshot_program_look_consult.py`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> ask moonshot what to do with the look of the program and report

---

# Verdict
**Execute Candidate 1: Optical theme lock pass** — collapse the Hub card soup into a single-viewport money-face composition, harden the honesty strip typography, and reduce mono density without losing the laser/chrome signal.

## 0. Operator Intent (verbatim)
> ask moonshot what to do with the look of the program (visual/UX), and wants a clear report.

## 1. Current look diagnosis (what works / what's noisy)
**Strengths**
- **Color integrity**: SD (#00d4aa), QB (#ffaa00), HAL (#e0e6ed), Fringe (#ff0044) tokens are consistently mapped; the vacuum-dark chassis (#050607) correctly supports the interferometer metaphor.
- **Honesty surface present**: Banner shows "empty ≠ $0" and wire status; beamHash and period-close stamps are rendered.
- **Beam animation**: The `.beam` CSS keyframe reinforces optical "liveness."

**Visual Debt**
- **Hub card soup**: `nr2-optical-pages-hub.html` presents 12 cards in a responsive grid — a dashboard collage that violates the "one composition first viewport" rule. Cards are used for navigation links (non-interactive containers), creating cognitive overload.
- **Sci-fi mono dump**: CSS shows `--mono` applied to navigation, banners, card headings, and buttons simultaneously, reducing scannability for Office Manager staff.
- **Banner hierarchy failure**: The honesty strip ("WIRE · Pages Hub · empty ≠ $0...") is uppercase monospace at 13px with no typographic contrast; critical STALE/CLOSE states compete with build metadata.
- **Bolted-on OPS chrome**: Force Close and VERIFY BEAM buttons use generic `.card button` styling with standard borders, making high-stakes shadow-period actions look like generic UI controls rather than intentional mechanical stops.
- **Theme CSS undersized**: At 4,572 bytes, `nr2-optical-theme.css` lacks sufficient spacing scale and typography hierarchy to support 10+ subpages without drift.

## 2. Recommended NEXT look package (name, why now, effort, REAL files, validation gate)
**Package**: **Optical Theme Lock Pass — Hub Composition Collapse & Typography Hardening**  
**Why now**: The Hub is the entry face of the nr2-12038-desk-smoke build; if the first viewport is a card collage, the "interferometer" brand reads as generic admin dashboard. Shadow period-close honesty requires that Force Close/Verify Beam feel like physical safety locks, not web buttons.

**Effort**: Medium (2–3 days design, 1 day implementation). No new JS frameworks; pure CSS/HTML refactor.

**REAL files to touch**:
- `C:\Users\mreno\newridgefamilyfinancial\NewRidgeFinancial2\site\nr2-optical-theme.css` — expand spacing scale, introduce `.type-staff` (sans) vs `.type-laser` (mono) hierarchy, add `.mech-lock` chrome for OPS actions.
- `C:\Users\mreno\newridgefamilyfinancial\NewRidgeFinancial2\site\nr2-optical-pages-hub.html` — replace 12-card grid with single-viewport "Alignment Bench" composition: SoftDent beam left, QuickBooks beam right, HAL core center, period-close status as the central interference pattern. Subpage access moves to a tertiary nav or "Mode Wheel" interaction, not cards.
- `C:\Users\mreno\newridgefamilyfinancial\NewRidgeFinancial2\site\nr2-optical-beam-touch-mockup.html` — ensure main interferometer landing shares the same honesty strip and spacing tokens as the collapsed Hub.

**Validation gate**:
1. **First viewport rule**: Hub loads with zero cards visible; money beams ($7,714 SD / $78,399 QB) and period-close status are the dominant elements above the fold.
2. **Honesty preserved**: STALE datasets still render with `--fringe` (#ff0044) border/text; empty ≠ $0 remains readable in `--hal` against vacuum background.
3. **OPS chrome intentionality**: Force Close button uses `.mech-lock` class (amber `--lock` #c9a227, uppercase mono, minimum 48px hit target, disabled state with corrosion texture) distinct from standard buttons.
4. **Staff scannability**: Body text renders in `--sans` (Segoe UI); only beam hashes, timestamps, and currency values use `--mono`.

## 3. Why this beats the other candidates now
- **Beats Candidate 2 (Main landing polish)**: The Hub is the current program entry point; polishing the main bench while the Hub remains card soup leaves the first impression broken.
- **Beats Candidate 3 (Unify all subpages)**: Too broad for the next sprint; unification requires stable Hub tokens first. Attempting all pages now guarantees inconsistency.
- **Beats Candidate 4 (Desk smoke chrome alone)**: Force Close/Verify Beam styling requires the broader typography and spacing system defined in the theme lock; doing chrome in isolation creates visual debt that must be rebuilt later.
- **Beats Candidate 5 (Reduce sci-fi mono only)**: Typography changes without structural collapse (card soup → composition) leaves the viewport density problem unsolved.

## 4. Runner-ups (2–3)
1. **Candidate 4 — Desk smoke / Force Close / VERIFY BEAM control chrome**: Valid immediate need, but should be implemented *after* the theme lock establishes the `.mech-lock` and `.honesty-strip` component classes. Defer 1 week.
2. **Candidate 2 — Main interferometer landing polish**: Critical for daily use, but the landing is already closer to the intended single-viewport composition than the Hub is. Address once Hub tokens are stable.

## 5. What NOT to redo / must keep for money honesty
- **STALE watermarking**: The amber/red "STALE" text and fringe borders on datasets older than TTL must remain visible and high-contrast; do not "soften" into pastel warnings.
- **Empty ≠ $0 display**: The "∅" or "NO SIGNAL" state for QuickBooks AP/Payroll (currently showing 0 rows, stale 1667 min) must never be replaced with "$0" or hidden; keep the current honesty strip text.
- **Beam hash visibility**: `799234d863740753` and `887abf908c98136e` must remain rendered in monospace at readable size (minimum 14px) for desk verification.
- **SoftDent write-back prohibition**: Visual cues that SoftDent is read-only (greyed write controls, "read-only" badges) must not be removed or styled into ambiguity.
- **Live money beam colors**: SD (#00d4aa) and QB (#ffaa00) tokens must not shift hue; these are operational safety colors for staff.

## 6. Acceptance criteria (visual + honesty)
- [ ] Hub loads with no `.card` elements in the first viewport; navigation to subpages uses a persistent "Mode Strip" or collapsible menu, not a grid.
- [ ] Typography passes "staff scan" test: OM staff can identify the period-close status within 2 seconds without reading monospace body copy.
- [ ] Force Close button visually distinct from "RUN SMOKE" button (amber lock vs. teal action).
- [ ] CSS file size > 6KB (indicates expanded spacing/typography system) but < 15KB (indicates no framework bloat).
- [ ] `empty ≠ $0` appears in banner on all 10 optical pages (Hub, OM, HAL, SoftDent, QB, Claims, AR, Taxes, Content, Narratives).
- [ ] STALE datasets retain `--fringe` red border; FRESH datasets retain `--sd` green border (no neutralizing into "subtle" grays).

## 7. Executive Summary (5 bullets)
- The Hub currently violates the "one composition" rule with 12 navigation cards; collapse it into an interferometer alignment view (SD left, QB right, HAL center).
- Reduce "sci-fi mono dump" by moving UI chrome to Segoe UI while reserving monospace for beam hashes, currency, and timestamps.
- Harden Force Close/Verify Beam styling to look like physical safety locks (amber, uppercase, corrosion texture when disabled) rather than generic buttons.
- Do not soften or prettify STALE/empty≠$0 warnings; these are operational safety signals.
- Complete this theme lock before attempting unification of all subpages or additional widget polish.

## 8. Approval Checklist
- [ ] Operator confirms Hub card soup is the priority entry-point fix.
- [ ] OPS team confirms amber `--lock` (#c9a227) is acceptable for Force Close chrome (distinct from SD teal).
- [ ] Dev confirms no external UI frameworks (Bootstrap, Tailwind) will be introduced; only `nr2-optical-theme.css` expansion.
- [ ] SoftDent read-only visual indicators (badges/disabled states) preserved in mockups.
- [ ] Acceptance criteria 6 (STALE border color) explicitly acknowledged.
