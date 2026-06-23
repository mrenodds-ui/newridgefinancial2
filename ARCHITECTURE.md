# Architecture Overview

## Structure

- `app/` — FastAPI backend, HAL services, import/report APIs, and Python tests
- `frontend/` — Active React SPA frontend for the supported browser experience
- `scripts/` — Utility, rebuild, and CI scripts

## Data Flow

1. Data is ingested by the FastAPI backend from SoftDent/QuickBooks exports and local rebuild scripts.
2. The backend exposes authenticated APIs for dashboard, HAL, admin, and reporting workflows.
3. The active `frontend/` SPA consumes those APIs and maintains browser-local caches where appropriate.

## Modernization & Scalability

- Backend and SPA are decoupled enough to evolve independently.
- Browser caching and worker-based parsing in `frontend/` reduce UI latency without changing backend ownership.

## Security

- Backend authentication and server-side integrations live in `app/`.
- HTTPS/HSTS are enforced in production via reverse proxy and backend security headers.

## CI/CD

- Backend pytest and frontend type/test/build checks are the supported validation paths.
- Automated deploy pipeline; see `.github/workflows/`.

## Containerization

- Deployment docs should be read as a split stack: FastAPI backend plus the active `frontend/` SPA.

## See Also

- `DEPLOYMENT.md`
- `ONBOARDING.md`
- `SECURITY_HEADERS.md`
