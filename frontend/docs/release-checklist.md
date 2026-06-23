# Release Checklist

## CI & Build
- [ ] Clean checkout: `git clone ... && cd frontend`
- [ ] Install: `npm ci`
- [ ] Typecheck: `npm run typecheck`
- [ ] Lint: `npm run lint`
- [ ] Unit tests: `npm test`
- [ ] Playwright tests: `npm run test:e2e`
- [ ] Build: `npm run build`

## Preview & Deploy
- [ ] Preview: `npm run preview` (test in browser)
- [ ] Test refresh on deep link (e.g. `/app/admin`)
- [ ] Test local data migration (if schema changed)
- [ ] Test export/import (if supported)
- [ ] Confirm no secrets exposed (see audit below)
- [ ] Confirm security headers present
- [ ] Confirm app version shown in diagnostics

## Security & Secrets Audit
- [ ] Search for API keys, tokens, passwords, secrets, private keys
- [ ] Search for localStorage/sessionStorage usage
- [ ] Search for import.meta.env usage
- [ ] Confirm all VITE_ variables are safe for browser
- [ ] Confirm no secrets in diagnostics or exports

## Manual QA
- [ ] App loads in Chrome, Edge, Firefox, Safari
- [ ] App loads after refresh
- [ ] KPI record CRUD works
- [ ] Validation errors appear
- [ ] Empty state appears
- [ ] Offline/slow network tested
- [ ] Two tabs open: no data loss/corruption
- [ ] Duplicate record creation handled
- [ ] Corrupt import file handled
- [ ] Storage unavailable/quota exceeded handled
- [ ] User-facing messages for all failures
- [ ] Data export/backup before destructive changes
- [ ] Safe reset/recovery tested

## Definition of Done
- [ ] App works in all target browsers
- [ ] Survives refreshes and bad inputs
- [ ] Fails clearly, no silent errors
- [ ] Exposes no secrets
- [ ] Release is repeatable and documented
