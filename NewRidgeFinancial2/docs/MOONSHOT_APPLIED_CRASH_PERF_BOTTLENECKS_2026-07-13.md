# Moonshot AI — Crash / Performance Bottlenecks (APPLIED)

**Date:** 2026-07-13  
**Build:** `hal-10608`  
**Consult:** `MOONSHOT_CRASH_PERF_BOTTLENECKS_2026-07-13.md`  
**Operator:** `proceed with moonshot recommendations and do not deviate`  
**Script:** `scripts/run_moonshot_crash_perf_bottlenecks_consult.py`

## Summary

Applied Moonshot MUST + SHOULD from the crash/perf consult. No Gold/ERA invent. OPS note: empty warming mosaic ≠ crash.

## Shipped

| Priority | Patch | Path | Change |
|----------|-------|------|--------|
| MUST OPS | Kill dual process | Task Manager | `taskkill /PID 46060 /F` — that PID was the **venv launcher parent** of the live child; killing it stopped the listener (Windows job/tree). Restarted as a single server afterward. Note: `.venv\Scripts\python.exe` normally leaves a small parent + real interpreter child; singleton guards the Python `main()`, not the native launcher stub. |
| MUST | Build skew alignment | `site/index.html` | All `?v=hal-10576` + chrome chip → `hal-10608` |
| MUST | Singleton guard | `browser_app.py` | Pidfile `.nr2_browser_app.pid` + Windows-safe `_pid_alive` / `ensure_singleton()` at `main()` — second launch exits with “already running” |
| SHOULD | Sync semaphore | `apex_backend.py` | `_SYNC_SEMAPHORE`; concurrent Sync → `status=sync_locked` + HTTP **423** / `retryAfter: 30` |
| SHOULD | Fill progress | `apex_backend.py`, `site/apex-core.js` | `_FILL_PROGRESS` on warming stub (`fillProgress` / `fillPage`); console.info on client |
| OPS | Runbook honesty | this doc | **Empty mosaic with warming badge = working fill, not a crash.** empty ≠ $0. |

## Tests

- `test_crash_perf_hal10608.py` — singleton, Sync 423/locked, fillProgress stub, index.html alignment
- Also: `test_moonshot_sprint.py`, `test_cache_coherence_hal10563.py`
- Result: **18 passed**

## Explicitly not done (per Moonshot / out of package)

- Inventing Gold/ERA dollars
- SoftDent write-back
- Re-diagnosing already-shipped SQLite timeout / widget rate-limit exemption
- Bumping `site/nr2-build.json` schemaVersion (consult MUST listed `index.html` only; chrome/assets aligned)

## Acceptance (consult §6)

1. Single `browser_app.py` process after restart  
2. UI asset query + chrome chip = `hal-10608` (matches `apex_backend.BUILD_ID` / `NR2_BUILD_ID`)  
3. Double Sync while held → HTTP 423 + `retryAfter`  
4. Warming stub exposes `fillProgress` when fill is running  
5. Operator brief: warming badge ≠ crash  

## Honesty

empty ≠ $0 · inventedGold=false · softDentWriteBack=false
