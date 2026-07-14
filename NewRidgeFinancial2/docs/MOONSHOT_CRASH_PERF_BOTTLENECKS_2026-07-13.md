# Moonshot AI — Crash / Performance Bottlenecks (CONSULT ONLY)

**Date:** 2026-07-13  
**UTC:** 2026-07-13T165351Z  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Bridge BUILD_ID:** hal-10608 (UI chrome may still show hal-10576)  
**Script:** `scripts/run_moonshot_crash_perf_bottlenecks_consult.py`  
**Apply:** DO NOT APPLY until operator approves. If code is present below, it is captured for review only.

## Operator request (verbatim)

> find why my application is crashing or performance bottlenecks. to moonshot and report

---

# Verdict  
Application is **NOT crashing**; the operator experiences **perceived crashes** (warming-bridge UX stalls) magnified by build-skew cache thrashing and a zombie sibling process. True bottleneck is the lack of back-pressure on the fill thread and un-guarded Sync concurrency.

## 0. Operator Intent (verbatim; confirm consult-only)  
> "find why my application is crashing or performance bottlenecks. to moonshot and report"  
> **CONFIRMED CONSULT-ONLY.** No code has been applied. Diffs below are advisory specifications only.

## 1. Crash analysis (fatal vs perceived; evidence)  

| Phenomenon | Classification | Evidence | Impact |
|------------|----------------|----------|--------|
| **PID 46060 browser_app.py** (4 MB, 0.02 s CPU) | **Process contamination** (zombie/launcher) | Same StartTime as main PID 3188; no window or port activity. | Port/socket contention; cache corruption risk. |
| **PWSvr.exe 0xc0000005** | **External fatal** (SoftDent, not NR2) | Windows Event Log 2026-07-12 13:11 local. | Requires SoftDent restart, not NR2 patch. |
| **/api/hal/status urllib errors** | **Recovered transient** | Intermittent failure earlier in session; health probe now `ok=True`. | No process death; network blip. |
| **Warming-bridge “blank mosaic”** | **Perceived crash** | HTTP 200 returned with `warming: true` stub; background fill pending. Operators see “Loading bridge instruments…” and assume hang. | High operator anxiety; unnecessary restarts. |
| **No Python Event Log errors** | **No fatal crash** | Last 24 h clean for `browser_app.py`. | — |

**Conclusion:** There are **zero fatal crashes** in the NR2 Python runtime today. The “crash” reports are warming-bridge UX stalls combined with the visual absence of data (39/177 widgets gap/empty).

## 2. Performance bottlenecks (ranked; evidence; impact)  

1. **Warming-bridge background fill latency** (UX stall)  
   - **Evidence:** `stub_on` logic serves instant 200 ms stub while `_fill` thread runs; mosaic remains “empty” until fill completes.  
   - **Impact:** Operator thinks session died; forces hard-refresh, which spawns second process (PID 46060).  

2. **Dual `browser_app.py` process contention**  
   - **Evidence:** PID 3188 (146 MB) + PID 46060 (4 MB). No singleton guard in `browser_app.py`.  
   - **Impact:** SQLite file locks (mitigated by `busy_timeout` but still serialize), port 8765 socket reuse risk, double memory footprint.  

3. **Build-skew cache purge storm**  
   - **Evidence:** `BUILD_ID="hal-10608"` vs `index.html?v=hal-10576`. `apex-core.js` triggers `idb.clearWidgets()` + reload on mismatch.  
   - **Impact:** Every page load nukes IndexedDB and refetches 177 widgets; adds 300–800 ms unnecessary latency.  

4. **Sync endpoint stampede (un-guarded)**  
   - **Evidence:** POST `/api/apex/import/sync` returns immediately; no semaphore. Rapid operator clicks or auto-retry scripts can queue multiple SoftDent/QuickBooks extraction jobs.  
   - **Impact:** SoftDent ODBC deadlocks, SQLite `BUSY` spikes (currently masked by 5 s timeout, but latency degrades).  

5. **SQLite locks** (mitigated)  
   - **Evidence:** `PRAGMA busy_timeout=5000` already applied per prior consult.  
   - **Impact:** Low; timeouts prevent crashes but serialize writes.  

## 3. Recommended fix package (MUST / SHOULD / OPS — ranked)  

| Priority | Fix | Owner | File(s) |
|----------|-----|-------|---------|
| **MUST** | **Kill zombie process** | OPS | Task Manager / `taskkill /PID 46060 /F` |
| **MUST** | **Align build IDs** (hal-10576 → hal-10608) | Dev | `site/index.html` |
| **MUST** | **Singleton guard** (prevent dual launch) | Dev | `browser_app.py` |
| **SHOULD** | **Sync semaphore** (1 concurrent import) | Dev | `apex_backend.py` |
| **SHOULD** | **Fill-progress telemetry** (reduce perceived hang) | Dev | `apex_backend.py`, `apex-core.js` |
| **OPS** | **Document warming-bridge** (empty ≠ crash) | Ops | Runbook update |

## 4. Code patches (if any) — full unified diffs  

### 4.1 Build-skew alignment (`site/index.html`)  
```diff
--- a/NewRidgeFinancial2/site/index.html
+++ b/NewRidgeFinancial2/site/index.html
@@ -12,7 +12,7 @@
-  <link rel="stylesheet" href="apex-tokens.css?v=hal-10576">
-  <link rel="stylesheet" href="apex-animations.css?v=hal-10576">
-  <link rel="stylesheet" href="apex-bridge.css?v=hal-10576">
-  <link rel="stylesheet" href="apex-theme.css?v=hal-10576">
-  <link rel="stylesheet" href="apex-chrome-flash.css?v=hal-10576">
-  <link rel="stylesheet" href="apex-hal-brain.css?v=hal-10576">
-  <link rel="stylesheet" href="apex-mobile-polish.css?v=hal-10576">
+  <link rel="stylesheet" href="apex-tokens.css?v=hal-10608">
+  <link rel="stylesheet" href="apex-animations.css?v=hal-10608">
+  <link rel="stylesheet" href="apex-bridge.css?v=hal-10608">
+  <link rel="stylesheet" href="apex-theme.css?v=hal-10608">
+  <link rel="stylesheet" href="apex-chrome-flash.css?v=hal-10608">
+  <link rel="stylesheet" href="apex-hal-brain.css?v=hal-10608">
+  <link rel="stylesheet" href="apex-mobile-polish.css?v=hal-10608">
   <div class="apex-version">hal-10576 · bridge</div>
+  <div class="apex-version">hal-10608 · bridge</div>
@@ -25,16 +25,16 @@
-  <script src="indexeddb-store.js?v=hal-10576"></script>
-  <script src="apex-chart-widget.js?v=hal-10576"></script>
-  <script src="nr2-dashboard-layout.js?v=hal-10576"></script>
-  <script src="apex-core.js?v=hal-10576"></script>
-  <script src="nr2-insight-sse.js?v=hal-10576"></script>
-  <script src="nr2-data-freshness.js?v=hal-10576"></script>
-  <script src="apex-quarantine-panel.js?v=hal-10576"></script>
-  <script src="apex-motion-helper.js?v=hal-10576"></script>
-  <script src="apex-ticker.js?v=hal-10576"></script>
-  <script src="apex-hal-bridge.js?v=hal-10576"></script>
-  <script src="apex-hal-brain.js?v=hal-10576"></script>
-  <script src="apex-narratives.js?v=hal-10576"></script>
-  <script src="hal-voice.js?v=hal-10576"></script>
-  <script src="hal-reports.js?v=hal-10576"></script>
+  <script src="indexeddb-store.js?v=hal-10608"></script>
+  <script src="apex-chart-widget.js?v=hal-10608"></script>
+  <script src="nr2-dashboard-layout.js?v=hal-10608"></script>
+  <script src="apex-core.js?v=hal-10608"></script>
+  <script src="nr2-insight-sse.js?v=hal-10608"></script>
+  <script src="nr2-data-freshness.js?v=hal-10608"></script>
+  <script src="apex-quarantine-panel.js?v=hal-10608"></script>
+  <script src="apex-motion-helper.js?v=hal-10608"></script>
+  <script src="apex-ticker.js?v=hal-10608"></script>
+  <script src="apex-hal-bridge.js?v=hal-10608"></script>
+  <script src="apex-hal-brain.js?v=hal-10608"></script>
+  <script src="apex-narratives.js?v=hal-10608"></script>
+  <script src="hal-voice.js?v=hal-10608"></script>
+  <script src="hal-reports.js?v=hal-10608"></script>
```

### 4.2 Singleton guard (`browser_app.py`) – add at top of `main()` or module init  
```diff
--- a/NewRidgeFinancial2/browser_app.py
+++ b/NewRidgeFinancial2/browser_app.py
@@ -1,6 +1,22 @@
 import os
 import sys
+import atexit
 
+PIDFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.nr2_browser_app.pid')
+
+def ensure_singleton():
+    if os.path.exists(PIDFILE):
+        with open(PIDFILE, 'r') as f:
+            old_pid = f.read().strip()
+        try:
+            os.kill(int(old_pid), 0)  # Check if process exists
+            print(f"ERROR: browser_app.py already running (PID {old_pid}). Exiting.")
+            sys.exit(1)
+        except (ValueError, OSError, ProcessLookupError):
+            pass  # Stale pidfile
+    with open(PIDFILE, 'w') as f:
+        f.write(str(os.getpid()))
+    atexit.register(lambda: os.remove(PIDFILE) if os.path.exists(PIDFILE) else None)
+
 def main():
+    ensure_singleton()
     # existing bootstrap
```

### 4.3 Sync semaphore + fill progress (`apex_backend.py`)  
```diff
--- a/NewRidgeFinancial2/apex_backend.py
+++ b/NewRidgeFinancial2/apex_backend.py
@@ -1,6 +1,7 @@
 import os
 import time
 import threading
 from typing import Any, Dict, Optional
 
 # Existing caches
@@ -10,6 +11,9 @@
 _REPORTS_BUNDLE_CACHE: dict[str, Any] = {"at": 0.0, "reports": None, "bundle": None, "errors": None}
 _WIDGETS_FILL_FAILURES = 0
 
+# Sync back-pressure
+_SYNC_SEMAPHORE = threading.Semaphore(1)
+_FILL_PROGRESS: Dict[str, Any] = {"page": None, "pct": 0, "ts": 0.0}
+
 def _utc_now() -> str:
     from datetime import datetime, timezone
     return datetime.now(timezone.utc).isoformat()
@@ -25,6 +29,8 @@
     stub_on = str(os.getenv("NR2_WIDGETS_STUB_FASTPATH") or "1").strip().lower() not in {"0", "false", "no", "off"}
     warming_key = f"{cache_key}:warming"
     if not skip_cache and not _fill and stub_on:
+        progress = _FILL_PROGRESS if _FILL_PROGRESS["page"] == pid else {"pct": 0}
         stub = {
             "page": pid,
             "sub": sub_key,
@@ -37,6 +43,8 @@
                     "status": "empty",
                     "label": "Loading bridge instruments…",
                     "message": "Warming import cache — KPIs appear when ready (empty ≠ $0).",
+                    "fillProgress": progress.get("pct", 0),
+                    "fillPage": progress.get("page"),
                     "hint": "Direct-first pipeline assembling SoftDent/QuickBooks.",
                 }
             ],
@@ -46,6 +54,26 @@
         return stub
     # ... existing fill logic
 
+def handle_import_sync(request_data: dict) -> dict:
+    """
+    POST /api/apex/import/sync handler.
+    Returns 423 Locked if another sync is active.
+    """
+    acquired = _SYNC_SEMAPHORE.acquire(blocking=False)
+    if not acquired:
+        return {"error": "Sync already in progress", "retryAfter": 30}, 423
+    try:
+        # Update progress tracker
+        _FILL_PROGRESS["page"] = request_data.get("page")
+        _FILL_PROGRESS["pct"] = 5
+        _FILL_PROGRESS["ts"] = time.time()
+        
+        # ... existing SoftDent/QB extraction logic ...
+        
+        _FILL_PROGRESS["pct"] = 100
+        return {"status": "complete", "widgetsRefreshed": True}
+    finally:
+        _SYNC_SEMAPHORE.release()
+
 def clear_widget_cache():
     """Call after successful import to force fresh data."""
     _WIDGETS_CACHE.clear()
```

### 4.4 Frontend progress display (`site/apex-core.js`) – minimal additive  
```diff
--- a/NewRidgeFinancial2/site/apex-core.js
+++ b/NewRidgeFinancial2/site/apex-core.js
@@ -120,6 +120,10 @@
       if (payload.warming) {
+        // Visual progress if fill is running
+        if (payload.fillProgress > 0 && payload.fillProgress < 100) {
+          console.info(`[NR2] Fill progress for ${payload.fillPage}: ${payload.fillProgress}%`);
+          // Optionally update DOM progress bar here
+        }
         // BuildId skew guard: if server build differs from UI chrome, nuke IDB and reload
         if (
           payload.buildId &&
```

## 5. What NOT to redo / invent  
- **SQLite timeout/busy_timeout** – already hardened in `softdent_practice_exports.py`.  
- **Widget rate-limit exemption** – already shipped (`/api/apex/widgets` prefix match in `nr2_rate_limit.py`).  
- **Cache-Control no-store** – already applied to warming responses.  
- **SoftDent Gold/ERA dollars** – do not invent missing financial data; gaps are honesty empties, not bugs.  
- **HAL chat "crash"** – intermittent `/api/hal/status` failures are network transients, not AI process death.

## 6. Acceptance criteria + validation gate  

| Gate | Test | Expected Result |
|------|------|-----------------|
| **Process** | Task Manager shows single `python.exe` for `browser_app.py` | PID count = 1 |
| **Build** | `window.NR2_BUILD_ID` in console matches `apex_backend.BUILD_ID` | Both `hal-10608` |
| **Sync** | Rapid double-click Sync button | Second request returns HTTP 423 with `retryAfter` |
| **UX** | Cold-load Financial page | Warming-bridge displays `fillProgress` > 0 within 2 s, updating to 100 % before mosaic render |
| **Stability** | 24 h uptime check | No Python Event Log errors; PWSvr.exe faults isolated to SoftDent host |

## 7. Executive Summary (5 bullets)  

- **No fatal crash** – the NR2 process is healthy; “crashes” are warming-bridge UX stalls where the mosaic appears blank while background fill runs.  
- **Zombie sibling** – PID 46060 (4 MB) is a leaked launcher process causing resource contention; terminate immediately.  
- **Build skew** – UI chrome at `hal-10576` fights backend `hal-10608`, triggering wasteful IndexedDB purges; align versions to stop cache thrashing.  
- **Sync stampede** – unprotected import endpoint risks concurrent SoftDent ODBC sessions; add semaphore to serialize.  
- **Data gaps** – 39 “empty” widgets reflect missing Gold/ERA source files, not application errors; do not fabricate dollars.

## 8. Approval checklist  

- [ ] OPS confirms PID 46060 terminated and `browser_app.py` restart policy enforces singleton.  
- [ ] Dev confirms `index.html` asset versions bumped to `hal-10608`.  
- [ ] Dev reviews semaphore placement in `apex_backend.py` (no deadlock on exception).  
- [ ] QA validates warming-bridge shows progress percentage during fill.  
- [ ] Operator briefed: “Empty mosaic with warming badge = working, not crashed.”