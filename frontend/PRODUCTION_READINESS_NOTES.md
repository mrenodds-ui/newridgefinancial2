# Browser App Production Readiness Notes

## Implemented in this pass

- Web app manifest and install metadata.
- Service worker update notification with user-controlled refresh activation.
- IndexedDB sync queue for failed admin refresh actions.
- Auto-retry of queued refresh actions when the browser reconnects on a stable network.
- Manual retry fallback button for queued actions.
- Conflict rule for KPI snapshot merges: newest `updatedAt` wins.
- Developer-only diagnostics card (`?diag=1`) for runtime and storage health.
- Changelog and IndexedDB migration compatibility tests.

## Explicit evaluations and scope decisions

### Background Sync API

- Evaluated and feature-detected capability.
- Full service-worker background sync handlers were not added because current mutations are narrow (`/api/admin/refresh`) and are already covered by the local queue + reconnect retry + manual retry path.
- This keeps behavior predictable and avoids fake offline guarantees.

### Passkeys / WebAuthn

- Not implemented because this browser app currently has no direct auth/session flow in the frontend and does not store auth tokens in localStorage.
- If frontend authentication is introduced later, auth should remain backend-managed and isolated in a dedicated module.

### Trusted Types

- Not implemented because this app does not render untrusted HTML (`innerHTML`, `dangerouslySetInnerHTML`, markdown HTML, or pasted HTML pipelines are not used).
- Add Trusted Types plus sanitization only if untrusted HTML rendering is introduced.

### View Transition API

- Implemented as subtle navigation polish around refresh-driven UI updates.
- Feature-detected and non-blocking.
