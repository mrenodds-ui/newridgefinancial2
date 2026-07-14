# Moonshot AI — Cache Problem Diagnosis & Report (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10562 + hal-local:32b  
**Prior:** KPI density applied; REC-007 HAL warm applied; widget stub ON  
**Script:** `scripts/run_moonshot_cache_problem_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> ask moonshot ai about the cachi problem and report

---

# Verdict
**Stale IndexedDB widget mosaics from pre-hal-10562 builds are flashing on navigation due to missing BUILD_ID invalidation in the client-side cache layer, while silent failures in the stub fast-path background fill thread leave operators stranded on the "warming-bridge" stub indefinitely.**

## 0. Operator Intent (verbatim; confirm consult-only; note cachi=cache)
> "ask moonshot ai about the cachi problem and report"

- **Interpretation:** "cachi" → **cache** coherence/staleness problem between browser IndexedDB and the newly deployed hal-10562 KPI density backend.
- **Mode:** CONSULT ONLY — No code changes applied; this report is diagnostic and prescriptive for operator approval.
- **Context:** hal-10562 KPI density fix (≤4 tiles) recently shipped, but Layer 4 (Browser IndexedDB) may still contain pre-10562 crowded mosaics.

## 1. Cache Map (layers + what each does)

| Layer | File / System | Function | TTL / Scope |
|-------|---------------|----------|-------------|
| **1** | `apex_backend.py` → `_WIDGETS_CACHE` (dict) | Server-side widget mosaic cache; stub fast-path returns `warming=True` immediately on cold miss while daemon thread fills this cache. | 15 seconds |
| **2** | `apex_hal_cache_warm_pack.py` | GPU/HAL model residency (Ollama keep-alive); primes CARC/payer explain prompts. **Distinct from widget cache.** | Infinite (`keep_alive=-1`) |
| **3** | `softdent_practice_exports.py` + export bundles | Import/Reports bundle cache + SoftDent SQLite reads. Fallback to stale exports on lock. | Varies by export |
| **4** | Browser `IndexedDB` (apex-core.js: `idb.loadWidgets`) | Stale-while-revalidate paint of widget mosaics **before** network fetch. No BUILD_ID validation visible in current path. | Persistent (until explicit clear) |

## 2. Diagnosis (which layer is the problem; evidence; failure modes)

### MUST FIX — Layer 4 (Browser IndexedDB) — Build Drift
**Evidence:** `apex-core.js` calls `idb.loadWidgets(...)` immediately on navigation and paints `cached.payload.widgets` if present **without comparing `cached.buildId` to the current `BUILD_ID` (hal-10562)**.
- **Failure Mode:** Operators with pre-10562 IDB entries see the old crowded KPI mosaic (8–12 tiles) flash for ~100–300ms, then potentially flicker to the warming stub, then to new sparse data. This visually contradicts the "KPI density fix" and trains users to distrust the "empty ≠ $0" messaging when they see stale non-empty data first.
- **Root Cause:** Missing cache invalidation contract between backend `BUILD_ID` bumps and client IDB schema.

### SHOULD FIX — Layer 1 (Widget Stub Fast-Path) — Silent Fill Failure
**Evidence:** `apex_backend.py` spawns a daemon thread for `_fill=True` but provides no error surface to the client if `build_apex_widgets` crashes (e.g., SQLite lock from Layer 3 interaction or unhandled exception in density packing logic).
- **Failure Mode:** If the background fill thread dies, the server-side `_WIDGETS_CACHE` remains cold. Every 750ms the client re-polls and receives the `warming-bridge` stub indefinitely. Operators see "Loading bridge instruments…" permanently, even though the backend is healthy (just failing to warm this specific cache key).
- **Risk:** Stuck warming state requires manual browser refresh or server restart to clear.

## 3. Fix Package (THE recommended work package)

**Name:** Cache Coherence & Stub Survivability Pack (proposed build **hal-10563**)  
**Why now:** Without this, the KPI density fix (hal-10562) is visually negated by stale IDB flashes, and production incidents of "infinite loading" will increase under SQLite contention.  
**Effort:** ½ sprint day; 2–3 files; zero database migration.

### Phase 1 — IDB BUILD_ID Gate (MUST)
**File:** `apex-core.js` (widget bootstrap sequence)  
**Change:** Before `applyWidgetPayload(cached.payload, { fromCache: true })`, assert:
```javascript
if (cached.payload.buildId !== window.NR2_BUILD_ID) {
  // Stale mosaic from pre-hal-10562 density era
  await idb.clearWidgets(currentPage); // or nuke entire widgets store
  paintedFromCache = false; // Force network fetch
} else {
  applyWidgetPayload(cached.payload, { fromCache: true });
}
```
**Validation:** Chrome DevTools → Application → IndexedDB → `nr2_widgets` store should self-clear on first hal-10563 load; Performance tab shows no "Layout Shift" from >4 KPI tiles.

### Phase 2 — Stub Failure Surface (SHOULD)
**File:** `apex_backend.py` (`build_apex_widgets` wrapper)  
**Change:** Wrap the `_fill=True` daemon thread logic in a try/except that:
1. Logs traceback to `stderr` (visible in `journalctl -u nr2-apex`).
2. On exception, explicitly delete the `warming_key` from the in-memory cache dictionary so subsequent requests attempt fill again (fail-open) rather than returning the stub forever.
3. Optionally: increment `nr2_widget_fill_failures_total` metric for alerting.

**Validation:** Simulate `raise RuntimeError("SoftDent lock")` inside fill thread → verify client receives 500 on next poll (triggering exponential backoff reload) rather than infinite warming stub.

### Phase 3 — Client Stub Timeout (SHOULD)
**File:** `apex-core.js`  
**Change:** If `payload.warming === true` for >5 consecutive polls (3.75s), force `window.location.reload()` (hard navigation) to clear any corrupted JS state.

## 4. What NOT to confuse / redo

- **Do NOT modify HAL Model Cache Warm (REC-007 / Layer 2).** That layer keeps the Qwen3 model GPU-resident; it has no relationship to widget mosaic caching. `keep_alive=-1` remains correct.
- **Do NOT re-apply SQLite timeout fixes.** The `database is locked` issue is Layer 3 (addressed in `MOONSHOT_WHY_ERRORS_CONSULT_2026-07-12.md`); this consult addresses the cache coherence layer above it.
- **Do NOT disable `NR2_WIDGETS_STUB_FASTPATH`.** The fast-path improves TTFB (Time To First Byte) significantly; we only need to fix the failure mode, not remove the optimization.
- **Do NOT write-back to SoftDent.** As per honesty constraints, remain read-only; no "cache warming" should attempt SQLite writes.

## 5. Report Summary (executive bullets)

- **Primary Defect:** Browser IndexedDB (Layer 4) lacks BUILD_ID validation, causing pre-hal-10562 crowded KPI mosaics to flash before network refresh, violating the new density contract.
- **Secondary Defect:** Widget stub fast-path (Layer 1) fails silently; background thread crashes leave users stuck on "warming-bridge" stubs indefinitely.
- **Fix Strategy:** Client-side BUILD_ID gate to invalidate stale IDB entries + backend exception hook to clear warming flags on fill failure.
- **Risk of Deferral:** Operators will see "empty ≠ $0" hints while staring at stale crowded tiles from last week; trust in density fix erodes.
- **HAL Cache Unchanged:** REC-007 GPU warm remains intact; no Ollama configuration changes required.

## 6. Approval checklist

- [ ] **Operator confirms** IDB invalidation strategy is acceptable (one-time cache clear for all users on hal-10563 rollout).
- [ ] **Staging data:** Verify presence of pre-10562 `nr2_widgets` IDB entries to test migration path.
- [ ] **Stub timeout:** Confirm 5-second client-side timeout threshold aligns with operator patience (vs. indefinite spinner).
- [ ] **No HAL changes:** Confirm REC-007 `keep_alive=-1` remains untouched.
- [ ] **SoftDent read-only:** Confirm no write-back logic introduced in cache warming paths.