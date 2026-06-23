# Developer Quickstart

## Install
```sh
npm install
```

## Dev Server
```sh
npm run dev
```

## Build
```sh
npm run build
```

## Test
```sh
npm run test
```

## Lint & Format
```sh
npm run lint
npm run format
npm run check
```

## Storage Architecture
- IndexedDB (Dexie) for local data
- No backend sync; all data is local
- Backup/export available in UI

## Offline Behavior
- No service worker; always live updates
- No offline/PWA caching

## Routing
- Centralized in `src/routes.ts`
- Uses `react-router-dom` with `<Link>`

## Forms
- Simple forms use local state
- Add React Hook Form + Zod only if forms become complex

## Deployment
- Standard Vite static build
- See `README.md` for production notes

## Performance
- Bundle size and Lighthouse budgets enforced in CI
- Run Lighthouse locally:
  ```sh
  npm run build
  npx serve dist
  # Then run Lighthouse in Chrome DevTools
  ```

## CI
- Runs install, typecheck, lint, format check, tests, build, bundle, and Lighthouse
