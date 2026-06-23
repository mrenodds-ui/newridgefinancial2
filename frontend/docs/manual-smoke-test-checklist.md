# Manual Smoke Test Checklist

## Basic App Load
- [ ] App loads on first visit at `/app/`
- [ ] App loads after browser refresh at `/app/`

## KPI Record CRUD
- [ ] Create a KPI record (fill all fields, save)
- [ ] Edit a KPI record (change values, save)
- [ ] Delete a KPI record
- [ ] Validation errors appear for invalid/missing fields
- [ ] Empty state appears when no records exist

## Persistence & Offline
- [ ] Local data survives browser refresh
- [ ] App works offline (if supported)

## Export/Import
- [ ] Export works (if supported)
- [ ] Import works (if supported)

## Cross-Browser
- [ ] App works in Chrome (latest)
- [ ] App works in Edge (latest)

## Diagnostics
- [ ] Diagnostics panel shows app version, build date, environment, DB version, service worker status, storage status
- [ ] No secrets or sensitive data are visible
