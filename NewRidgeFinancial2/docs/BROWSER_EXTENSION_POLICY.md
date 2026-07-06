# NR2 Browser Extension Policy (Moonshot Sprint 3)

## Scope

Applies to staff workstations running NR2 Financial (8765) and NR2 Workstation (8766) on Windows 11.

## Allowed

- Microsoft Entra / Azure AD sign-in helpers required by IT
- Approved password manager extensions (1Password, Bitwarden enterprise)
- Accessibility extensions vetted by IT

## Blocked on NR2 hosts

- Generic ad blockers that rewrite loopback requests
- Clipboard / screen-capture extensions without BAA
- Crypto miners, shopping assistants, unknown CRX sideloads

## Enforcement

1. Deploy Chrome/Edge enterprise policy: `ExtensionInstallBlocklist` for `*`, allowlist IT-approved IDs only.
2. NR2 CSP (`nr2_browser_security.py`) blocks framing and limits script origins to loopback HTTPS.
3. Financial pages require fresh imports; HAL refuses stale financial queries server-side.

## Operator drill

Quarterly: verify no unauthorized extensions on front-desk profiles; confirm `https://127.0.0.1:8765` loads with valid localhost TLS cert.
