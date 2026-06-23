# Preview Deployment Guide

## Recommended Providers
- **Vercel** (recommended for Vite/React)
- **Netlify**
- **Cloudflare Pages**
- Or your existing hosting provider

## Production Build Command
```
npm run build
```

## Preview/Production Start Command
```
npm run preview
```

## Routing
- The app uses a base path (`/app/`).
- On Vercel/Netlify/Cloudflare Pages, set the output/public directory to `frontend/dist`.
- Ensure all routes under `/app/` are handled by the SPA (use a catch-all rewrite if needed).
- Test navigation and refresh on subroutes (e.g., `/app/`, `/app/admin`).

## Service Worker / PWA
- Service worker is registered in production builds.
- Test offline/refresh behavior in preview.
- If issues occur, disable the service worker for preview by setting `VITE_ENABLE_SW=false` in your preview environment.

## Environment Variables
- Only variables prefixed with `VITE_` are exposed to the browser.
- Use `.env.example` as a template for your deployment environment.

## Troubleshooting
- If you see a blank page, check the base path and SPA routing settings.
- If static assets 404, check the public path and output directory.
- If service worker caching causes issues, clear site data and reload.
