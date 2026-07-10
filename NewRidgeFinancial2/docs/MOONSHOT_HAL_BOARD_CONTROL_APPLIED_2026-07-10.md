# HAL Board Control — Applied

**Date:** 2026-07-10  
**Build:** **hal-10310**  
**Status:** Applied after operator proceed (“can HAL populate the widgets”)

## What HAL can do now

| Action | How | Honesty |
|--------|-----|---------|
| **Sync & refill board** | Sync SoftDent/QB imports → refresh mosaic | Widgets refill from imports only |
| **Refresh page** | Reload current mosaic from cache | No invented $ |
| **Navigate** | Open Financial / Taxes / A/R / QB / Documents / … | — |
| **Focus / highlight** | Scroll + focus + cyan pulse on a widget | Display only |
| **Import status banner** | Meta line from diagnostics | Non-dollar status |
| **Categorize assist** | Open QB categorize suggestions | Import-backed keywords; not posted to QB |

## What HAL still cannot do

- Invent production / A/R / tax / EBITDA dollars into KPIs
- Post categories to QuickBooks
- Fabricate tax-return PDFs

## How to use

On HAL page chips: **Sync & refill board**, **Import status**, **Focus EBITDA**, **Focus A/R**, **Categorize assist**  
Or say: “sync imports and populate the widgets”, “focus EBITDA”, “open categorize suggestions”

## API

`POST /api/apex/hal/board-actions` `{ query, page }` → `{ handled, reply, actions[] }`

## Files

- `apex_backend.py` — `resolve_hal_board_actions` + route
- `site/apex-core.js` — board-actions first in `askHal`, `runHalBoardActions`
- `site/apex-bridge.css` — `.apex-hal-highlight`
