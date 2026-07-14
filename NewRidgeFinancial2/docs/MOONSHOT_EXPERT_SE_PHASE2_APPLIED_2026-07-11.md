# Moonshot Expert SE Program Recommendations — Phase 2 Applied

**Date:** 2026-07-11  
**Build:** **hal-10500**  
**Consult:** `MOONSHOT_EXPERT_SE_PROGRAM_RECOMMENDATIONS_CONSULT_2026-07-11.md`  
**Prior:** Phase 1 (`MOONSHOT_EXPERT_SE_PHASE1_APPLIED_2026-07-11.md`)  
**Status:** Phase 2 applied per operator proceed (no deviation)

## Applied

| ID | Fix | Status |
|----|-----|--------|
| **REC-002** | Confirmed HTTPS `NR2SSLWSGIRefServer` uses `ThreadingMixIn` + `daemon_threads` so long Ollama `evaluate-query` cannot monopolize other GETs. Unit gate in `test_expert_se_phase2.py`. | Done (verified + tested) |
| **REC-004** | Import health chips: `NR2_DATA_FRESHNESS` default **ON**; age bands green &lt;24h / yellow 24h–7d / **red ≥7 days**; force-show when SoftDent critical; UI bar merges HAL `importDegraded`; background health monitor every **6h** (`classify_only`). | Done |

## Files

- `nr2_http_server.py` — already threaded (Phase 2 verifies)
- `apex_sync_status_pack.py` — 7-day critical, default ON, forceShow
- `site/nr2-data-freshness.js` — Import Degraded chip + critical titles
- `browser_app.py` — `nr2-health-monitor` APScheduler job every 6h
- `test_expert_se_phase2.py` — new gates
- Build **hal-10499 → hal-10500**

## Validation Gate (Phase 2)

| Check | Expected |
|-------|----------|
| ThreadingMixIn in SSL server | Present (`test_expert_se_phase2`) |
| SoftDent age ≥168h | chip level `critical` + alert text |
| Freshness bar | visible when stale/critical or importDegraded |
| Scheduler log | `health every 6h` on Start Program |

## Not applied (Phase 3 — next proceed)

- REC-005 ERA 835 parser pipeline (partial U1 pack may already exist — full Moonshot scope TBD)
- REC-006 Claims Workbench Phase 2 card actions
- REC-007 Cache warming enhancements
- NICE REC-008 / REC-009
