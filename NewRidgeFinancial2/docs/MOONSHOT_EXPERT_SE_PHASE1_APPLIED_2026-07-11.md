# Moonshot Expert SE Program Recommendations — Phase 1 Applied

**Date:** 2026-07-11  
**Build:** **hal-10499**  
**Consult:** `MOONSHOT_EXPERT_SE_PROGRAM_RECOMMENDATIONS_CONSULT_2026-07-11.md`  
**Status:** Phase 1 applied per operator “proceed as moonshot ai directed”

## Applied (Phase 1 only)

| ID | Fix | Status |
|----|-----|--------|
| **REC-003** | Legacy task `NewRidgeDashboardServersAutoStart` — already absent (deleted 2026-07-10). Verified `schtasks` → file not found. `New Ridge NR2 Program` remains. | Verified done |
| **REC-001 (B)** | Split import gate: `SYSTEM_STATUS_PREFIXES` (connected) vs `FINANCIAL_DATA_PREFIXES` (fresh). `/api/apex/hal/status`, `/api/apex/import-health`, and related telemetry use connected; money/PHI paths keep fresh. | Done |
| **REC-001 (C)** | Status payload + Apex HAL bridge: **HAL Ready · Import Degraded** when imports not fresh; 403 honesty fallback; amber orb when degraded. | Done |

## Files

- `nr2_browser_security.py` — `SYSTEM_STATUS_PREFIXES`, `system_status_path()`, `financial_read_path` excludes telemetry
- `nr2_http_server.py` — before_request tier-2 `connected` vs tier-1 `fresh`
- `apex_backend.py` — `_build_hal_status_payload` readiness + Ready/Degraded labels
- `site/apex-hal-bridge.js` — UI labels + import_read_forbidden honesty
- `site/apex-core.js` — sync failure no longer forces false Standby
- `site/apex-tokens.css` — `.hal-orb.is-degraded` amber pulse
- Build bump **hal-10498 → hal-10499**

## Validation Gate (Phase 1)

| Check | Expected |
|-------|----------|
| `GET /api/apex/hal/status` while degraded | **200**, `statusLabel` contains Ready + Import Degraded |
| `GET /api/financial-reports` (or widgets) while degraded | **403** `import_read_forbidden` |
| Chat `/api/hal/evaluate-query` | Still exempt / operational |
| Sidebar | Not stuck on HAL Standby |

## Not applied yet (later phases — needs next proceed)

- **Phase 2:** REC-002 threaded/async HAL queue; REC-004 proactive import health monitor
- **Phase 3:** REC-005 ERA 835; REC-006 claims card actions; REC-007 cache warming; NICE items

## Honesty

- Telemetry tier must not leak PHI or dollar amounts
- UI shows Import Degraded so operators do not trust stale KPIs as fresh
