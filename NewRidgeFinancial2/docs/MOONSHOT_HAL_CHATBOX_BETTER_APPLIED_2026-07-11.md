# Moonshot Better HAL Chat Box — Applied

**Date:** 2026-07-11  
**Build:** **hal-10463**  
**Consult:** `MOONSHOT_HAL_CHATBOX_BETTER_CONSULT_2026-07-11.md`  
**Status:** Applied after operator **approve and proceed**

## What shipped

Option B — **Apex HAL Console** custom redesign (no third-party chat library):

- Auto-resizing composer (`field-sizing` + JS fallback)
- Empty-state welcome when transcript is blank
- Copy button + timestamp on HAL replies (hover/focus)
- System **receipt** bubbles after board-actions (`HAL executed: ✓ navigate · …`)
- Horizontal-scroll suggestion chips
- Flex composer footer (no sticky keyboard trap)
- Live/busy indicator in header + Thinking… meta row
- Ctrl/Cmd+Enter send (Enter still sends; Shift+Enter newline)
- `role="log"` + `aria-live="polite"` on message stream
- Highlight overlay `z-index: 20` so focus does not bury the composer

## Files

| File | Change |
|------|--------|
| `site/apex-core.js` | HAL chat template, `appendHalMessage`, restore/empty, receipts, busy UI, wire auto-resize + chords |
| `site/apex-tokens.css` | `.apex-hal-chat*` Console v2 styles |
| `site/apex-bridge.css` | `.apex-hal-highlight` z-index |
| `site/index.html` / `sw.js` / `nr2-build.json` | **hal-10463** |

## Preserved

- `/api/hal/board-actions` → `/api/hal/evaluate-query` pipeline
- `halTranscript[]` persistence across soft remounts
- Ask-HAL from other widgets
- Plain `textContent` bubbles (no markdown injection)

## Validate

Hard-refresh HAL page with `?v=hal-10463`, confirm empty state, send a board command (e.g. sync/focus), confirm receipt + copy, confirm chips scroll horizontally.
