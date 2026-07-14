# Moonshot AI — Page-by-Page Smoke Analyze & Repairs (CONSULT ONLY)

**Date:** 2026-07-13  
**UTC:** 2026-07-13T163422Z  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Bridge:** HAL-10608 (UI chip may still show hal-10576)  
**Script:** `scripts/run_moonshot_page_smoke_analyze_repairs_consult.py`  
**Apply:** DO NOT APPLY until operator approves. If code is present below, it is captured for review only.

## Operator request (verbatim)

> send to moonshot for analyze and repairs, recommendations consult only if he has code get it

---

# Verdict
Rate-limiting on widget endpoints causes warming-stall under aggressive poll; 39 gaps are data/OPS (Gold/ERA) — 3 code patches fix the UX stall and version skew without inventing financial data.

## 0. Operator Intent (quote verbatim; confirm consult-only)
> "Analyze the page-by-page smoke. Recommend repairs. CONSULT ONLY. If you have code patches for repairable bugs, INCLUDE them (full diffs). Do not invent Gold/ERA dollars. Separate code UX fixes from OPS blockers."

Confirmed: CONSULT-ONLY. Patches provided below are for operator review/staging; I have not applied them.

## 1. Analyze — Working vs Not (code bugs vs OPS/data)

| Category | Symptom | Root Cause | Type |
|----------|---------|------------|------|
| **MUST-Code** | Mosaic stuck on `warming-bridge` after Sync; HAL chat disappears | `/api/apex/widgets/*` returns HTTP 429; `RATE_LIMIT_EXEMPT_PATHS` missing widget prefix; warming poll retries immediately without backoff | Code |
| **MUST-Code** | UI chip shows `hal-10576`, telemetry reports `HAL-10608` | Browser IDB/cache serves stale build artifacts; warming stub lacks cache-busting headers; no buildId mismatch detector | Code |
| **SHOULD-Code** | Sync clears `_WIDGETS_CACHE` → stampede of warming requests | No "warming in progress" semaphore; exponential backoff missing in client | Code |
| **OPS-Data** | `GOLD_CSV_MISSING` (7 gaps), `ERA_835_REQUIRED` (6 gaps), `CLAIMS_AR_RECONCILE_MISMATCH` | SoftDent Print Preview not dropped to Gold CSV; ERA 835 files not imported; claims reconciliation pending | OPS |
| **Honest-Gaps** | Empty dossier, forecast, denial pareto, lib-storage | No underlying data (expected when Gold/ERA missing) | Data |

## 2. Recommended Repair Package (MUST / SHOULD / OPS — ranked)

### MUST (Code — apply first)
1. **Rate-limit exemption for widget polling** (`nr2_rate_limit.py`)  
   Add prefix exemption for `/api/apex/widgets` to prevent 429 warming-stall.
2. **Warming poll 429-backoff** (`apex-core.js`)  
   Detect 429, apply exponential backoff (max 30s), clear IDB on streak timeout.
3. **Cache-busting headers & buildId skew guard** (`apex_backend.py`, `apex-core.js`)  
   Serve `no-store` headers on warming stubs; reload client when `payload.buildId !== window.NR2_BUILD_ID`.

### SHOULD (Code — staging permitting)
4. **Sync warming semaphore** (`apex_backend.py`)  
   Return `503` with `Retry-After: 10` during active Sync to reduce stampede (alternative to full exemption).

### OPS (Data — no code changes)
5. **Gold CSV Drop**  
   SoftDent → Insurance Payment Analysis → Print Preview → save as CSV to `\\server\GoldDrop\` (v19 known issue: Print Preview does **not** auto-create Gold lines; manual drop required).
6. **ERA 835 Import**  
   Import ERA 835 files to close `ERA_835_REQUIRED` and `CLAIMS_AR_RECONCILE_MISMATCH` (61 claims pending).

## 3. Code Patches (if any) — full unified diffs or complete replacement functions

### Patch A: `NewRidgeFinancial2/nr2_rate_limit.py` — Widget exemption
```diff
--- a/NewRidgeFinancial2/nr2_rate_limit.py
+++ b/NewRidgeFinancial2/nr2_rate_limit.py
@@ -10,6 +10,8 @@ RATE_LIMIT_EXEMPT_PATHS = frozenset(
         "/api/import-sync-reset",
         "/api/webhooks/website-appointment",
         "/nr2-build.json",
+        "/api/apex/widgets",          # Moonshot: prevent 429 warming stall
+        "/api/apex/hal/orchestrate",  # Ensure HAL token auth never 429s
     }
 )
 
@@ -17,4 +19,9 @@ RATE_LIMIT_EXEMPT_PATHS = frozenset(
 def is_rate_limit_exempt(path: str) -> bool:
     p = str(path or "").split("?", 1)[0]
-    return p in RATE_LIMIT_EXEMPT_PATHS
+    if p in RATE_LIMIT_EXEMPT_PATHS:
+        return True
+    # Prefix match for all widget sub-endpoints (e.g., /api/apex/widgets/financial)
+    if p.startswith("/api/apex/widgets"):
+        return True
+    return False
```

### Patch B: `NewRidgeFinancial2/site/apex-core.js` — 429 backoff & buildId skew guard
Replace the warming poll block (around line where `warmingPollStreak` is used):

```javascript
// Moonshot warming coherence pack: 429 backoff + buildId skew detection
if (payload && payload.warming) {
  // BuildId skew guard: if server build differs from UI chrome, nuke IDB and reload
  if (payload.buildId && window.NR2_BUILD_ID && payload.buildId !== window.NR2_BUILD_ID) {
    console.warn(`[NR2] Build skew detected: UI=${window.NR2_BUILD_ID} Server=${payload.buildId}. Purging cache.`);
    if (idb && idb.clearWidgets) {
      idb.clearWidgets().catch(() => {}).finally(() => window.location.reload());
    } else {
      window.location.reload();
    }
    return; // Stop processing stale payload
  }

  warmingPollStreak += 1;
  
  // Exponential backoff capped at 30s to prevent 429 storm
  const backoffMs = Math.min(1000 * Math.pow(2, warmingPollStreak), 30000);
  
  if (warmingPollStreak >= WARMING_POLL_MAX) {
    warmingPollStreak = 0;
    // Hard reset: clear IDB and reload to clear potential version skew
    try {
      if (idb && idb.clearWidgets) {
        await idb.clearWidgets(currentPage, currentSub);
      }
    } catch (e) {
      console.error("[NR2] IDB clear failed", e);
    }
    window.location.reload();
  } else {
    // Schedule next poll with backoff instead of immediate tight loop
    setTimeout(() => {
      fetchWidgets(currentPage, currentSub, currentQuery).catch(err => {
        if (err.status === 429) {
          console.warn("[NR2] Widget 429; backoff active");
        }
      });
    }, backoffMs);
  }
} else {
  // Reset streak when warming resolves
  warmingPollStreak = 0;
  if (payload && !payload.fillFailed) {
    idb.cacheWidgets(currentPage, currentSub, currentQuery, payload).catch(() => {});
  }
  setMeta(payload);
}
```

### Patch C: `NewRidgeFinancial2/apex_backend.py` — Cache-busting headers for warming stubs
Insert headers before returning the stub (inside the `if not skip_cache and not _fill and stub_on:` block):

```diff
--- a/NewRidgeFinancial2/apex_backend.py
+++ b/NewRidgeFinancial2/apex_backend.py
@@ -45,6 +45,13 @@ def build_apex_widgets(pid, sub_key, skip_cache=False, sync=False):
             "cachedForSec": 0,
         }
         # Moonshot: prevent CDN/browser from caching warming stubs (buildId skew)
+        from bottle import response
+        response.set_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
+        response.set_header("Pragma", "no-cache")
+        response.set_header("Expires", "0")
+        response.set_header("X-NR2-Build-Id", BUILD_ID)
         return stub
```

## 4. What NOT to do / invent
- **Do not invent Gold CSV content** — The `GOLD_CSV_MISSING` gaps require actual SoftDent Insurance Payment Analysis CSV drops; code cannot fabricate `$641,566.92` lines.
- **Do not invent ERA 835 dollars** — `ERA_835_REQUIRED` indicates missing remittance files; only importing real ERA files will close the gaps.
- **Do not claim patches applied** — These are staged diffs for operator approval.
- **Do not enable `NR2_WIDGETS_STUB_FASTPATH=0`** — This would force cold-load and hide the warming UX issue rather than fix the 429 stall.

## 5. Acceptance criteria + validation gate
1. **Rate-limit exemption**: `curl -I /api/apex/widgets/financial` returns `200` (not `429`) when called 20×/sec from same IP.
2. **Warming resolution**: After Sync, widgets transition from `warming-bridge` to populated data within **60 seconds** (previously stuck indefinitely).
3. **BuildId coherence**: UI chip matches `X-NR2-Session-Token` telemetry (both `HAL-10608`); no `hal-10576` skew after hard refresh.
4. **Data honesty unchanged**: `softdent-gold-payment-pipeline` still reports `GOLD_CSV_MISSING` (no invented data).

## 6. Executive Summary (5 bullets)
- **138/177 widgets healthy**; 0 crashes. Navigation and HAL auth functional.
- **Root UX blocker**: Widget API 429s under poll pressure → warming stall. Fixed by exempting `/api/apex/widgets/*` from rate limits.
- **Version skew**: UI chip `hal-10576` vs `HAL-10608` fixed via cache-busting headers + client-side buildId mismatch reload.
- **39 gaps are data/OPS**: Gold CSV missing, ERA 835 required, claims reconciliation pending — require manual SoftDent operations, not code.
- **Risk**: Low; patches additive (exemptions, headers, backoff). No database schema changes.

## 7. Approval checklist (operator must approve before apply)
- [ ] Reviewed diffs for `nr2_rate_limit.py` (prefix exemption logic).
- [ ] Reviewed `apex-core.js` warming backoff (accepts 30s max delay).
- [ ] Reviewed `apex_backend.py` Bottle response header injection (framework compatibility OK).
- [ ] Confirmed **staging** environment available for 429-stress test (run `while true; do curl ...; done`).
- [ ] Acknowledged that Gold/ERA gaps remain until CSV/835 files manually imported (OPS task).
- [ ] Approved for `main` branch commit via standard NR2 PR process (not direct prod edit).

**Operator**: Reply "APPROVE PATCHES" to authorize staging deployment, or request modifications.