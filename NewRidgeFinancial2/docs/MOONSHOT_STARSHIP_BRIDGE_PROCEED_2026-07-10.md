# Moonshot Starship Bridge — Proceed Addendum

**Date:** 2026-07-10  
**Operator:** proceed (after starship consult)  
**Build:** `hal-10230`  
**Consult:** `MOONSHOT_STARSHIP_BRIDGE_UI_2026-07-10.md`

## Applied (S1–S5)

- Fixed mosaic instruments (no stretchy `1fr` elongation)
- Persistent left sidebar (nav + HAL + sync/print)
- Top scrolling ticker (`/api/apex/ticker`)
- Interactive Narratives 3-pane workspace
- Boot/scanline motion via `apex-bridge.css`

## Rollback

Restore `NewRidgeFinancial2/site/index.pre-bridge-hal-10220.html` over `index.html` and revert build stamps to `hal-10220`, or restore from `app_data/nr2-backup-P0/index.pre-bridge-hal-10220.html`.
