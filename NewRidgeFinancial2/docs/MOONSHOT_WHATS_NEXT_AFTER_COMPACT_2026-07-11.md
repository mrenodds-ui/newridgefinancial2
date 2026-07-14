# Moonshot AI — What's Next (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10550  
**Script:** `scripts/run_moonshot_whats_next_after_compact_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Harden inbox sync coherence to eliminate AR/dashboard/QB file flapping between syncs before landing remaining NICE features.

## 0. Intent
Secure live data consistency; remove the sole remaining production risk so the shipped import gate and compact pages are stable under load.

## 1. Already Done (do not redo)
- Expert SE REC-001/002/003/004/005/006/007 (gate split, threaded HTTPS, import health, ERA CAS/claims actions)
- Compact professional pages Phases 1–5 (motion kill, empty collapse, size discipline, Claims pipeline+kanban, HAL sole-l, density toggle)
- Import gate hardening (softGaps warning/optional, stale+rows no hard-fail, QB expenses demoted to warning)
- Commits `2f51309`, `785eb0a`, `0384ddf` on `fix/main-validate-ci` (unmerged)

## 2. Recommended NEXT (single package)
**Package: Inbox Sync Coherence Hardening**  
- **Goal**: Eliminate state flapping in AR, Dashboard, and QB inbox files between sync cycles; guarantee idempotent sync results regardless of SoftDent criticals presence.  
- **Why now**: This is the only remaining risk in the live system; widgets currently 200 but files flap between syncs, undermining the import gate durability work already shipped.  
- **Effort**: Small–Medium (1–2 days).  
- **Files**: `sync/adapters/ar.py`, `sync/adapters/qb.py`, `inbox/aggregator.py`, `state/machines/sync_state.py`, `services/dashboard_sync.py`.  
- **Validation gate**:  
  1. AR/Dashboard/QB file states remain bit-identical across 10 consecutive no-op syncs.  
  2. Zero 200→empty→200 transitions observed in production logs over 24h.  
  3. SoftDent criticals present do not trigger inbox resets or file re-creation.

## 3. Runner-up options (max 3)
1. **Land Current Branch**: Open PR for `fix/main-validate-ci`, resolve gh auth blockage, merge to `main` (do this immediately if auth is unblocked, else parallelize).  
2. **REC-008 Batch Narratives**: Implement batch narrative generation for Expert SE (NICE—defer until flapping fixed).  
3. **REC-009 Voice Context Carry**: Implement context carry-over for voice interactions (NICE—defer until flapping fixed).

## 4. Approval checklist
- [ ] Inbox flapping reproduced and root-caused (likely non-idempotent sync timestamp or empty-set handling).  
- [ ] Fix scoped strictly to AR/Dashboard/QB sync stability (no new features).  
- [ ] REC-008/009 explicitly deferred until validation gate passes.  
- [ ] Decision made on whether `fix/main-validate-ci` merges before or after this coherence patch (recommend: merge first if auth resolved, then patch flapping on clean main).